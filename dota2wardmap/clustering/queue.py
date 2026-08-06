from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from ..domain import JobStatus
from ..extensions import db
from ..models import ClusteringJob
from ..settings import get_settings


def enqueue_precompiled_clusters(league_id: int) -> None:
    settings = get_settings()
    delay = settings.cluster_batch_delay_seconds
    max_wait = max(delay, settings.cluster_batch_max_wait_seconds)
    available_at = datetime.now(UTC) + timedelta(seconds=delay)
    for is_obs in (0, 1):
        parameters = {
            "cluster_selection_epsilon": 0,
            "min_samples": 10,
            "min_cluster_size": 10,
            "cluster_selection_method": "eom",
            "league_id": league_id,
            "min_match": 0,
            "is_obs": is_obs,
            "n_jobs": -1,
        }
        pending_job = db.session.execute(
            select(ClusteringJob)
            .where(
                ClusteringJob.status == JobStatus.PENDING,
                ClusteringJob.parameters["league_id"].as_integer() == league_id,
                ClusteringJob.parameters["is_obs"].as_integer() == is_obs,
            )
            .limit(1)
        ).scalar_one_or_none()
        if pending_job is not None:
            pending_job.parameters = parameters
            created_at = pending_job.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)
            pending_job.available_at = min(available_at, created_at + timedelta(seconds=max_wait))
        else:
            job = ClusteringJob()
            job.available_at = available_at
            job.parameters = parameters
            db.session.add(job)
    db.session.commit()
