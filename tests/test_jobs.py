from datetime import UTC, datetime, timedelta

from flask import Flask
from sqlalchemy import select

from dota2wardmap.extensions import db
from dota2wardmap.clustering.queue import enqueue_precompiled_clusters
from dota2wardmap.jobs import claim_job, complete_job, fail_job
from dota2wardmap.models import ClusteringJob, ReplayJob


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


def test_failed_clustering_job_returns_to_pending():
    app = create_test_app()
    with app.app_context():
        db.create_all()
        db.session.add(ClusteringJob(parameters={"league_id": 42}))
        db.session.commit()

        job = claim_job(ClusteringJob)
        assert job is not None

        fail_job(job, "temporary failure")
        assert job.status == "pending"
        assert job.last_error == "temporary failure"
        assert claim_job(ClusteringJob) is None


def test_future_clustering_job_is_not_claimed():
    app = create_test_app()
    with app.app_context():
        db.create_all()
        db.session.add(
            ClusteringJob(
                parameters={"league_id": 42},
                available_at=datetime.now(UTC) + timedelta(minutes=1),
            )
        )
        db.session.commit()

        assert claim_job(ClusteringJob) is None


def test_precompiled_cluster_jobs_are_debounced(monkeypatch):
    app = create_test_app()
    monkeypatch.setenv("CLUSTER_BATCH_DELAY_SECONDS", "30")
    with app.app_context():
        db.create_all()

        enqueue_precompiled_clusters(42)
        first_schedule = db.session.execute(
            select(ClusteringJob.available_at).where(
                ClusteringJob.parameters["league_id"].as_integer() == 42,
                ClusteringJob.parameters["is_obs"].as_integer() == 1,
            )
        ).scalar_one()
        enqueue_precompiled_clusters(42)

        jobs = db.session.execute(select(ClusteringJob)).scalars().all()
        observer_job = next(job for job in jobs if job.parameters["is_obs"] == 1)
        assert len(jobs) == 2
        assert observer_job.available_at >= first_schedule
        assert observer_job.parameters["cluster_selection_epsilon"] == 0


def test_precompiled_cluster_batch_has_maximum_wait(monkeypatch):
    app = create_test_app()
    monkeypatch.setenv("CLUSTER_BATCH_DELAY_SECONDS", "30")
    monkeypatch.setenv("CLUSTER_BATCH_MAX_WAIT_SECONDS", "120")
    with app.app_context():
        db.create_all()
        enqueue_precompiled_clusters(42)

        jobs = db.session.execute(select(ClusteringJob)).scalars().all()
        old_batch_start = datetime.now(UTC) - timedelta(minutes=3)
        for job in jobs:
            job.created_at = old_batch_start
        db.session.commit()

        enqueue_precompiled_clusters(42)

        observer_job = next(job for job in jobs if job.parameters["is_obs"] == 1)
        available_at = observer_job.available_at
        if available_at.tzinfo is None:
            available_at = available_at.replace(tzinfo=UTC)
        assert available_at <= datetime.now(UTC)
