from datetime import UTC, datetime, timedelta
from typing import Any, overload

from sqlalchemy import or_, select

from .domain import JobStatus
from .extensions import db
from .models import ClusteringJob, ReplayJob

CLAIM_TIMEOUT = timedelta(minutes=15)
MAX_ATTEMPTS = 5


@overload
def claim_job(model: type[ReplayJob]) -> ReplayJob | None: ...


@overload
def claim_job(model: type[ClusteringJob]) -> ClusteringJob | None: ...


def claim_job(model: type[ReplayJob] | type[ClusteringJob]) -> ReplayJob | ClusteringJob | None:
    now = datetime.now(UTC)
    stale_before = now - CLAIM_TIMEOUT
    conditions: list[Any] = [
        model.attempts < MAX_ATTEMPTS,
        or_(
            model.status == JobStatus.PENDING,
            (model.status == JobStatus.PROCESSING) & (model.claimed_at < stale_before),
        ),
    ]
    if model is ClusteringJob:
        conditions.append(ClusteringJob.available_at <= now)

    job = db.session.execute(
        select(model).where(*conditions).order_by(model.created_at).with_for_update(skip_locked=True).limit(1)
    ).scalar_one_or_none()
    if job is None:
        db.session.rollback()
        return None

    job.status = JobStatus.PROCESSING
    job.attempts += 1
    job.claimed_at = now
    job.last_error = None
    db.session.commit()
    return job


def complete_job(job: ReplayJob | ClusteringJob) -> None:
    job.status = JobStatus.COMPLETED
    job.completed_at = datetime.now(UTC)
    job.last_error = None
    db.session.commit()


def fail_job(job: ReplayJob | ClusteringJob, error: str) -> None:
    job.status = JobStatus.FAILED if job.attempts >= MAX_ATTEMPTS else JobStatus.PENDING
    job.last_error = error[:4000]
    if isinstance(job, ClusteringJob) and job.status == JobStatus.PENDING:
        retry_delay = min(300, 30 * (2 ** (job.attempts - 1)))
        job.available_at = datetime.now(UTC) + timedelta(seconds=retry_delay)
    db.session.commit()
