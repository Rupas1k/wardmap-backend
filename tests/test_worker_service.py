from datetime import UTC, datetime, timedelta
from queue import Queue

from flask import Flask

from dota2wardmap.extensions import db
from dota2wardmap.models import ReplayJob
from dota2wardmap.replay import worker_service


def create_test_app() -> Flask:
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    db.init_app(app)

    return app


def test_result_failure_requeues_job_and_releases_worker(monkeypatch):
    app = create_test_app()

    with app.app_context():
        db.create_all()
        job = ReplayJob(match_id=123)
        job.status = "processing"
        job.attempts = 1
        db.session.add(job)
        db.session.commit()

        result_queue = Queue()
        result_queue.put((123, object(), None))
        assignments = {0: 123}

        def fail_persistence(_result):
            raise RuntimeError("database unavailable")

        monkeypatch.setattr(worker_service, "persist_parsed_replay", fail_persistence)

        worker_service._collect_results(result_queue, assignments)

        db.session.refresh(job)
        assert assignments == {}
        assert job.status == "pending"
        assert job.next_attempt_at is not None
        assert job.last_error == "database unavailable"


def test_worker_recovers_unparsed_jobs_on_startup():
    app = create_test_app()

    with app.app_context():
        db.create_all()
        pending = ReplayJob(match_id=123)
        pending.next_attempt_at = datetime.now(UTC) + timedelta(hours=1)
        processing = ReplayJob(match_id=124)
        processing.status = "processing"
        processing.claimed_at = datetime.now(UTC)
        db.session.add_all([pending, processing])
        db.session.commit()

        assert worker_service.recover_unparsed_jobs() == 2
        assert pending.status == "pending"
        assert pending.next_attempt_at is not None
        assert pending.next_attempt_at.replace(tzinfo=UTC) <= datetime.now(UTC)
        assert processing.status == "pending"
        assert processing.claimed_at is None
