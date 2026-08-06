from flask import Flask

from dota2wardmap.extensions import db
from dota2wardmap.models import League, ReplayJob
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
