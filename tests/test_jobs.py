from flask import Flask

from dota2wardmap.extensions import db
from dota2wardmap.jobs import claim_job, complete_job
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
