import bz2
import logging
import os
import time
from datetime import UTC, datetime
from multiprocessing import Process, Queue
from queue import Empty
from typing import Any

import requests
from d2wm_parser import parse_replay
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..integrations import opendota
from ..clustering.queue import enqueue_precompiled_clusters
from ..jobs import claim_job, complete_job, fail_job
from ..lifecycle import install_shutdown_handlers
from ..models import League, Match, Player, ReplayJob, Ward

logger = logging.getLogger(__name__)


def get_match_data(match_id: int) -> dict[str, Any]:
    response = opendota.get_match(match_id)
    league = response.get("league") or {}
    match_data = {
        "cluster": response.get("cluster"),
        "salt": response.get("replay_salt"),
        "league": response.get("leagueid") or league.get("leagueid"),
        "league_name": league.get("name"),
        "duration": response.get("duration"),
        "region": response.get("region"),
        "date": response.get("start_time"),
        "version": response.get("patch"),
        "players": [
            {
                "id": player["account_id"],
                "name": player.get("name") or player.get("personaname"),
            }
            for player in (response.get("players") or [])
            if player.get("account_id") is not None
        ],
    }
    return match_data


def get_replay(match_id):
    try:
        match_data = get_match_data(match_id)
        cluster, salt = match_data.get("cluster"), match_data.get("salt")
    except opendota.OpenDotaError:
        logger.exception("Invalid OpenDota response for match %s", match_id)
        return

    if cluster is None or salt is None:
        logger.warning("OpenDota has no replay location for match %s", match_id)
        return

    try:
        response = requests.get(f"http://replay{cluster}.valve.net/570/{match_id}_{salt}.dem.bz2", timeout=10)
    except requests.RequestException:
        logger.exception("Unable to download replay for match %s", match_id)
        return

    if response.status_code == 404:
        logger.warning("Replay for match %s is no longer available from Valve", match_id)
        return
    try:
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Unable to download replay for match %s", match_id)
        return

    try:
        replay = bz2.decompress(response.content)
    except OSError:
        logger.exception("Valve returned an invalid replay archive for match %s", match_id)
        return

    return replay, match_data


def download_and_parse_replay(match_id, result_queue):
    data = get_replay(match_id)
    if not data:
        result_queue.put((match_id, None, "Replay could not be downloaded"))
        return

    replay, match_data = data
    try:
        now = time.time()
        output = parse_replay(replay)
        output_dicts = []
        for out in output:
            d = {
                "time_placed": out.time_placed,
                "duration": out.duration,
                "is_obs": out.is_obs,
                "is_radiant": out.is_radiant,
                "event": out.event,
                "post_game": out.post_game,
                "player_placed_steam_id": out.player_placed_steam_id,
                "player_destroyed_steam_id": out.player_destroyed_steam_id,
                "npc_killed": out.npc_killed,
                "x": out.x,
                "y": out.y,
                "z": out.z,
                "vec_x": out.vec_x,
                "vec_y": out.vec_y,
                "vec_z": out.vec_z,
                "radiant_networth": out.radiant_networth,
                "dire_networth": out.dire_networth,
            }
            output_dicts.append(d)

        logger.info("Parsed match %s in %.3fs", match_id, time.time() - now)
        result_queue.put((match_id, (match_id, match_data, output_dicts), None))
    except BaseException as exc:
        logger.exception("Unable to parse match %s", match_id)
        error = str(exc) or f"{type(exc).__name__} while parsing"
        result_queue.put((match_id, None, error))


def parser_process(task_queue, result_queue):
    while True:
        match_id = task_queue.get()
        if match_id is None:
            break
        download_and_parse_replay(int(match_id), result_queue)


def persist_parsed_replay(result: tuple[int, dict[str, Any], list[dict[str, Any]]]) -> bool:
    match_id = result[0]
    match_data = result[1]
    ward_results = result[2]
    try:
        wards = []
        for ward_data in ward_results:
            if ward_data["event"] == "expired" or "guys" in ward_data["npc_killed"]:
                ward_data["player_destroyed_steam_id"] = None

            ward_data["player_placed_steam_id"] = ward_data["player_placed_steam_id"] - 76561197960265728

            if ward_data["player_destroyed_steam_id"] is not None:
                ward_data["player_destroyed_steam_id"] -= 76561197960265728

            ward = {
                "match_id": match_id,
                "is_obs": ward_data["is_obs"],
                "is_radiant": ward_data["is_radiant"],
                "is_destroyed": ward_data["event"] == "killed",
                "is_post_game": ward_data["post_game"],
                "player_placed_id": ward_data["player_placed_steam_id"],
                "player_destroyed_id": ward_data["player_destroyed_steam_id"],
                "time_placed": ward_data["time_placed"],
                "duration": ward_data["duration"],
                "x_pos": ward_data["x"] * 128 + round(ward_data["vec_x"]),
                "y_pos": ward_data["y"] * 128 + round(ward_data["vec_y"]),
                "z_pos": ward_data["z"] * 128 + round(ward_data["vec_z"]),
                "radiant_networth": ward_data["radiant_networth"],
                "dire_networth": ward_data["dire_networth"],
                "npc_killed": ward_data["npc_killed"],
            }
            wards.append(ward)

        league = None
        if match_data["league"] is not None:
            league = db.session.get(League, int(match_data["league"]))
            if league is None:
                league = League(id=int(match_data["league"]), name=match_data.get("league_name"))
                db.session.add(league)

        match = db.session.get(Match, match_id)
        if match is None:
            started_at = match_data.get("date")
            match = Match(
                id=match_id,
                league_id=match_data["league"],
                game_version=match_data["version"],
                started_at=datetime.fromtimestamp(started_at, UTC) if started_at is not None else None,
                region=match_data["region"],
                duration=match_data["duration"],
            )
            db.session.add(match)

            player_names = {player["id"]: player.get("name") for player in match_data.get("players", [])}
            player_ids = set(player_names)
            player_ids.update(ward["player_placed_id"] for ward in wards if ward["player_placed_id"] is not None)
            player_ids.update(ward["player_destroyed_id"] for ward in wards if ward["player_destroyed_id"] is not None)

            existing_players = {
                player.id: player
                for player in db.session.execute(select(Player).where(Player.id.in_(player_ids))).scalars().all()
            }
            for player_id in player_ids:
                player = existing_players.get(player_id)
                if player is None:
                    player = Player(id=player_id, name=player_names.get(player_id))
                    db.session.add(player)
                elif player.name is None and player_names.get(player_id):
                    player.name = player_names[player_id]

                if player not in match.players:
                    match.players.append(player)
            db.session.flush()

            if len(wards):
                db.session.execute(insert(Ward).values(wards))
            else:
                logger.warning("Parsed match %s contains no wards", match_id)
        else:
            logger.info("Match %s is already parsed", match_id)

        db.session.commit()
        return True
    except (KeyError, TypeError, ValueError, SQLAlchemyError):
        db.session.rollback()
        logger.exception("Unable to persist match %s", match_id)
        return False


def run_replay_worker() -> None:
    shutdown = install_shutdown_handlers(logger)
    worker_count = max(1, int(os.getenv("PARSER_WORKERS", "2")))
    result_queue = Queue()
    task_queues = [Queue() for _ in range(worker_count)]
    processes: list[Process] = []
    assignments: dict[int, int] = {}

    logger.info("Starting replay parser with %s child processes", worker_count)

    for i in range(worker_count):
        process = Process(
            name=f"replay-parser-{i + 1}",
            target=parser_process,
            args=(task_queues[i], result_queue),
        )
        process.start()
        processes.append(process)

    try:
        while not shutdown.is_set():
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

            while True:
                try:
                    match_id, result, error = result_queue.get_nowait()
                except Empty:
                    break

                job = db.session.get(ReplayJob, match_id)
                if job is not None:
                    if result is not None and persist_parsed_replay(result):
                        complete_job(job)
                        league_id = result[1].get("league")
                        if league_id is not None:
                            enqueue_precompiled_clusters(int(league_id))
                    else:
                        fail_job(job, error or "Unable to persist parsed replay")
                for index, assigned_match_id in tuple(assignments.items()):
                    if assigned_match_id == match_id:
                        assignments.pop(index)
                        break

            for index in range(worker_count):
                if index in assignments or not processes[index].is_alive():
                    continue
                job = claim_job(ReplayJob)
                if job is None:
                    break
                assignments[index] = job.match_id
                task_queues[index].put(job.match_id)

            shutdown.wait(0.2)
    finally:
        logger.info("Stopping replay parser children")
        for queue in task_queues:
            queue.put(None)
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
