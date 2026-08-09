from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select

from .domain import JobStatus
from .extensions import db
from .models import ReplayJob

CLAIM_TIMEOUT = timedelta(minutes=15)
MAX_ATTEMPTS = 5


def claim_job(model: type[ReplayJob]) -> ReplayJob | None:
    now = datetime.now(UTC)
    stale_before = now - CLAIM_TIMEOUT
    conditions = [
        model.attempts < MAX_ATTEMPTS,
        or_(
            model.status == JobStatus.PENDING,
            (model.status == JobStatus.PROCESSING) & (model.claimed_at < stale_before),
        ),
    ]
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


def complete_job(job: ReplayJob) -> None:
    job.status = JobStatus.COMPLETED
    job.completed_at = datetime.now(UTC)
    job.last_error = None
    db.session.commit()


def fail_job(job: ReplayJob, error: str) -> None:
    job.status = JobStatus.FAILED if job.attempts >= MAX_ATTEMPTS else JobStatus.PENDING
    job.last_error = error[:4000]
    db.session.commit()
