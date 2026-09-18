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
