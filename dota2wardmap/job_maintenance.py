from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, delete, or_, select

from .domain import JobStatus
from .extensions import db
from .models import ClusteringJob, ReplayJob
from .settings import get_settings

DEFAULT_CLEANUP_BATCH_SIZE = 1000


def cleanup_terminal_jobs(batch_size: int = DEFAULT_CLEANUP_BATCH_SIZE) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=get_settings().job_retention_days)
    deleted = 0

    while True:
        replay_ids = (
            db.session.execute(
                select(ReplayJob.match_id)
                .where(
                    or_(
                        (ReplayJob.status == JobStatus.COMPLETED) & (ReplayJob.completed_at < cutoff),
                        (ReplayJob.status == JobStatus.FAILED) & (ReplayJob.claimed_at < cutoff),
                    )
                )
                .limit(batch_size)
            )
            .scalars()
            .all()
        )
        if not replay_ids:
            break
        result = cast(CursorResult[Any], db.session.execute(delete(ReplayJob).where(ReplayJob.match_id.in_(replay_ids))))
        deleted += result.rowcount
        db.session.commit()

    while True:
        cluster_ids = (
            db.session.execute(
                select(ClusteringJob.id)
                .where(
                    or_(
                        (ClusteringJob.status == JobStatus.COMPLETED) & (ClusteringJob.completed_at < cutoff),
                        (ClusteringJob.status == JobStatus.FAILED) & (ClusteringJob.claimed_at < cutoff),
                    )
                )
                .limit(batch_size)
            )
            .scalars()
            .all()
        )
        if not cluster_ids:
            break
        result = cast(
            CursorResult[Any],
            db.session.execute(delete(ClusteringJob).where(ClusteringJob.id.in_(cluster_ids))),
        )
        deleted += result.rowcount
        db.session.commit()

    return deleted
