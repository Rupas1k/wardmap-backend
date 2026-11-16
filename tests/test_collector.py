from flask import Flask

from dota2wardmap.domain import JobStatus
from dota2wardmap.extensions import db
from dota2wardmap.models import League, Match, Player, ReplayJob, TrackedPlayer
from dota2wardmap.replay import collector


def test_sync_league_discovers_and_deduplicates_matches(monkeypatch):
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    db.init_app(app)
    monkeypatch.setattr(
        collector.opendota,
        "get_league",
        lambda league_id: {"leagueid": league_id, "name": "Test League"},
    )
    monkeypatch.setattr(
        collector.opendota,
        "get_league_matches",
        lambda league_id: [{"match_id": 100}, {"match_id": 101}],
    )

    with app.app_context():
        db.create_all()

        first_queued, first_total = collector.sync_league(42)
        second_queued, second_total = collector.sync_league(42)

        assert db.session.get(League, 42).name == "Test League"
        assert {job.match_id for job in db.session.query(ReplayJob).all()} == {100, 101}

    assert (first_queued, first_total) == (2, 2)
    assert (second_queued, second_total) == (0, 2)


def test_sync_league_refreshes_only_unparsed_inactive_jobs(monkeypatch):
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    db.init_app(app)
    monkeypatch.setattr(
        collector.opendota,
        "get_league_matches",
        lambda league_id: [{"match_id": match_id} for match_id in range(100, 105)],
    )

    with app.app_context():
        db.create_all()
        league = League(42, "Test League")
        league.tier = "premium"
        failed = ReplayJob(101)
        failed.status = JobStatus.FAILED
        failed.attempts = 5
        failed.last_error = "timeout"
        processing = ReplayJob(102)
        processing.status = JobStatus.PROCESSING
        processing.attempts = 2
        pending = ReplayJob(103)
        pending.attempts = 3
        db.session.add_all([league, Match(100, league_id=42), failed, processing, pending])
        db.session.commit()

        refreshed, total = collector.sync_league(42, refresh_unparsed_jobs=True)

        assert (refreshed, total) == (3, 5)
        assert db.session.get(ReplayJob, 101).status == JobStatus.PENDING
        assert db.session.get(ReplayJob, 101).attempts == 0
        assert db.session.get(ReplayJob, 101).last_error is None
        assert db.session.get(ReplayJob, 102).status == JobStatus.PROCESSING
        assert db.session.get(ReplayJob, 102).attempts == 2
        assert db.session.get(ReplayJob, 103).attempts == 0
        assert db.session.get(ReplayJob, 104).status == JobStatus.PENDING


def test_sync_player_discovers_and_deduplicates_matches(monkeypatch):
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    db.init_app(app)
    monkeypatch.setattr(collector.dota_gc, "get_player_matches", lambda account_id: [100, 101])

    with app.app_context():
        db.create_all()
        db.session.add_all([Player(42), TrackedPlayer(42), Match(100)])
        db.session.commit()

        first = collector.sync_player(42)
        second = collector.sync_player(42)
        tracked = db.session.get(TrackedPlayer, 42)

        assert {job.match_id for job in db.session.query(ReplayJob).all()} == {101}
        assert tracked.last_match_id == 101
        assert tracked.last_checked_at is not None
        assert tracked.last_error is None

    assert first.to_dict() == {
        "matches": 2,
        "queued": 1,
        "parsed": 1,
        "pending": 0,
        "unavailable": 0,
        "failed": 0,
        "history": [
            {"match_id": 101, "status": "queued"},
            {"match_id": 100, "status": "parsed"},
        ],
    }
    assert second.to_dict() == {
        "matches": 2,
        "queued": 0,
        "parsed": 1,
        "pending": 1,
        "unavailable": 0,
        "failed": 0,
        "history": [
            {"match_id": 101, "status": "pending"},
            {"match_id": 100, "status": "parsed"},
        ],
    }


def test_sync_player_reports_terminal_jobs_without_requeueing(monkeypatch):
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    db.init_app(app)
    monkeypatch.setattr(collector.dota_gc, "get_player_matches", lambda account_id: [100, 101])

    with app.app_context():
        db.create_all()
        unavailable = ReplayJob(100)
        unavailable.status = JobStatus.FAILED
        unavailable.last_error = "Replay could not be downloaded"
        failed = ReplayJob(101)
        failed.status = JobStatus.FAILED
        failed.last_error = "Invalid replay"
        db.session.add_all([Player(42), TrackedPlayer(42), unavailable, failed])
        db.session.commit()

        result = collector.sync_player(42)

        assert db.session.query(ReplayJob).count() == 2

    assert result.unavailable == 1
    assert result.failed == 1
    assert result.queued == 0
