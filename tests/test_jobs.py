from datetime import UTC, datetime, timedelta

from flask import Flask

from dota2wardmap.extensions import db
from dota2wardmap.jobs import claim_job, complete_job, fail_job
from dota2wardmap.models import ReplayJob


def create_test_app() -> Flask:
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    db.init_app(app)
    return app


def test_replay_job_is_claimed_and_completed():
    app = create_test_app()
    with app.app_context():
        db.create_all()
        db.session.add(ReplayJob(match_id=123))
        db.session.commit()

        job = claim_job(ReplayJob)

        assert job is not None
        assert job.status == "processing"
        assert job.attempts == 1

        complete_job(job)
        assert job.status == "completed"
        assert claim_job(ReplayJob) is None


def test_failed_replay_job_waits_before_retry():
    app = create_test_app()
    with app.app_context():
        db.create_all()
        db.session.add(ReplayJob(match_id=123))
        db.session.commit()

        job = claim_job(ReplayJob)
        assert job is not None

        fail_job(job, "OpenDota unavailable")

        assert job.status == "pending"
        assert job.next_attempt_at is not None
        assert job.next_attempt_at.replace(tzinfo=UTC) > datetime.now(UTC)
        assert claim_job(ReplayJob) is None

        job.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        db.session.commit()

        retried = claim_job(ReplayJob)
        assert retried is not None
        assert retried.attempts == 2
