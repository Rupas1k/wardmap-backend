import json
import logging
import time
from typing import Any

from sqlalchemy import select

from .. import create_worker_app
from ..extensions import db, redis_store
from ..jobs import claim_job, complete_job, fail_job
from ..lifecycle import install_shutdown_handlers
from ..models import ClusteringJob, Match
from .queue import enqueue_precompiled_clusters
from .service import calculate_clusters

logger = logging.getLogger("dota2wardmap.clustering.worker")


def enqueue_missing_cluster_caches() -> int:
    league_ids = db.session.execute(select(Match.league_id).where(Match.league_id.is_not(None)).distinct()).scalars()
    queued_leagues = 0
    for league_id in league_ids:
        if redis_store.exists(f"{league_id}-0:ready") and redis_store.exists(f"{league_id}-1:ready"):
            continue
        enqueue_precompiled_clusters(int(league_id))
        queued_leagues += 1
        logger.info("Scheduled missing cluster cache for league %s", league_id)
    return queued_leagues


def calculate_and_cache_clusters(job: dict[str, Any]) -> int:
    is_obs = bool(int(job["is_obs"]))
    clusters = calculate_clusters(
        cluster_selection_epsilon=int(job["cluster_selection_epsilon"]),
        min_samples=int(job["min_samples"]),
        min_cluster_size=int(job["min_cluster_size"]),
        cluster_selection_method=str(job["cluster_selection_method"]),
        league_id=int(job["league_id"]),
        min_match=int(job["min_match"]),
        is_obs=is_obs,
        n_jobs=int(job["n_jobs"]),
    )

    cache_key = f"{int(job['league_id'])}-{int(is_obs)}"
    encoded_clusters = [json.dumps(cluster, allow_nan=False, default=int) for cluster in clusters]
    pipeline = redis_store.pipeline(transaction=True)
    pipeline.delete(cache_key)
    if encoded_clusters:
        pipeline.rpush(cache_key, *encoded_clusters)
    pipeline.set(f"{cache_key}:ready", "1")
    pipeline.execute()
    db.session.commit()
    return len(clusters)


def run_clustering_worker() -> None:
    shutdown = install_shutdown_handlers(logger)
    logger.info("Clustering worker is ready")
    queued_leagues = enqueue_missing_cluster_caches()
    logger.info("Cluster cache recovery complete: scheduled %s leagues", queued_leagues)
    while not shutdown.is_set():
        job = claim_job(ClusteringJob)
        if job is None:
            shutdown.wait(1)
            continue

        parameters = job.parameters
        league_id = int(parameters["league_id"])
        ward_type = "observer" if bool(int(parameters["is_obs"])) else "sentry"
        started_at = time.monotonic()
        logger.info(
            "Starting clustering job %s: league=%s, ward_type=%s, attempt=%s",
            job.id,
            league_id,
            ward_type,
            job.attempts,
        )
        try:
            cluster_count = calculate_and_cache_clusters(parameters)
            complete_job(job)
            logger.info(
                "Completed clustering job %s: league=%s, ward_type=%s, clusters=%s, took=%.2fs",
                job.id,
                league_id,
                ward_type,
                cluster_count,
                time.monotonic() - started_at,
            )
        except Exception as exc:
            db.session.rollback()
            fail_job(job, str(exc))
            logger.exception(
                "Failed clustering job %s: league=%s, ward_type=%s, took=%.2fs",
                job.id,
                league_id,
                ward_type,
                time.monotonic() - started_at,
            )


def main() -> None:
    app = create_worker_app()
    with app.app_context():
        run_clustering_worker()


if __name__ == "__main__":
    main()
