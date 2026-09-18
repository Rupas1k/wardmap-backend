import logging
import os
from multiprocessing import Process, Queue
from queue import Empty

from ..extensions import db
from ..jobs import claim_job, complete_job, fail_job
from ..lifecycle import install_shutdown_handlers
from ..models import ReplayJob
from .parser import parser_process
from .persistence import persist_parsed_replay

logger = logging.getLogger(__name__)


def run_replay_worker() -> None:
    shutdown = install_shutdown_handlers(logger)
    worker_count = max(1, int(os.getenv("PARSER_WORKERS", "2")))
    result_queue = Queue()
    task_queues = [Queue() for _ in range(worker_count)]
    processes: list[Process] = []
    assignments: dict[int, int] = {}

    logger.info("Starting replay parser with %s child processes", worker_count)

    for index in range(worker_count):
        process = Process(
            name=f"replay-parser-{index + 1}",
            target=parser_process,
            args=(task_queues[index], result_queue),
        )
        process.start()
        processes.append(process)

    try:
        while not shutdown.is_set():
            try:
                _restart_failed_processes(processes, task_queues, result_queue, assignments)
                _collect_results(result_queue, assignments)
                _assign_pending_jobs(processes, task_queues, assignments)
            except Exception:
                db.session.rollback()
                logger.exception("Replay worker cycle failed; retrying")
                shutdown.wait(1.0)
            shutdown.wait(0.2)
    finally:
        _stop_processes(processes, task_queues, assignments)


def _restart_failed_processes(processes, task_queues, result_queue, assignments) -> None:
    for index, process in enumerate(processes):
        if process.is_alive():
            continue
        exit_code = process.exitcode
        process.join()
        logger.error("%s exited unexpectedly with code %s; restarting it", process.name, exit_code)

        interrupted_match_id = assignments.pop(index, None)
        if interrupted_match_id is not None:
            db.session.expire_all()
            interrupted_job = db.session.get(ReplayJob, interrupted_match_id)
            if interrupted_job is not None and interrupted_job.status == "processing":
                fail_job(interrupted_job, f"{process.name} exited with code {exit_code}")
            logger.warning("Returned interrupted match %s to the replay queue", interrupted_match_id)

        task_queues[index].close()
        task_queues[index].cancel_join_thread()
        task_queues[index] = Queue()
        replacement = Process(
            name=process.name,
            target=parser_process,
            args=(task_queues[index], result_queue),
        )
        replacement.start()
        processes[index] = replacement


def _collect_results(result_queue, assignments) -> None:
    while True:
        try:
            match_id, result, error = result_queue.get_nowait()
        except Empty:
            break

        try:
            job = db.session.get(ReplayJob, match_id)
            if job is not None:
                if result is not None and persist_parsed_replay(result):
                    complete_job(job)
                else:
                    fail_job(job, error or "Unable to persist parsed replay")
        except Exception as exc:
            db.session.rollback()
            logger.exception("Unable to process replay result for match %s", match_id)

            job = db.session.get(ReplayJob, match_id)
            if job is not None and job.status == "processing":
                fail_job(job, str(exc))
        finally:
            for index, assigned_match_id in tuple(assignments.items()):
                if assigned_match_id == match_id:
                    assignments.pop(index)
                    break


def _assign_pending_jobs(processes, task_queues, assignments) -> None:
    for index, process in enumerate(processes):
        if index in assignments or not process.is_alive():
            continue
        job = claim_job(ReplayJob)
        if job is None:
            break
        try:
            task_queues[index].put(job.match_id)
        except Exception as exc:
            db.session.rollback()
            fail_job(job, str(exc))
            logger.exception("Unable to dispatch match %s to %s", job.match_id, process.name)
            continue

        assignments[index] = job.match_id


def _stop_processes(processes, task_queues, assignments) -> None:
    logger.info("Stopping replay parser children")
    for task_queue in task_queues:
        task_queue.put(None)
    for process in processes:
        process.join(timeout=10)
        if process.is_alive():
            logger.warning("Terminating unresponsive parser child %s", process.name)
            process.terminate()
            process.join(timeout=5)
        if process.is_alive():
            logger.error("Killing parser child %s after graceful shutdown timed out", process.name)
            process.kill()
            process.join(timeout=5)
    for match_id in assignments.values():
        db.session.expire_all()
        job = db.session.get(ReplayJob, match_id)
        if job is not None and job.status == "processing":
            fail_job(job, "Replay worker stopped before the parser returned a result")
            logger.info("Returned match %s to the replay queue during shutdown", match_id)
