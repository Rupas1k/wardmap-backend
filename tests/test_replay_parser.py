from flask import Flask
from sqlalchemy import select

from dota2wardmap import create_worker_app
from dota2wardmap.extensions import db
from dota2wardmap.models import League, Match, Player, Ward
from dota2wardmap.replay.service import persist_parsed_replay


def test_worker_app_has_connections_without_api_routes(monkeypatch):
    monkeypatch.setenv("DB_URL", "sqlite://")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    app = create_worker_app()

    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite://"
    assert app.config["REDIS_URL"] == "redis://localhost:6379/0"
    assert {rule.endpoint for rule in app.url_map.iter_rules()} == {"static"}


def test_persist_parsed_replay_persists_opendota_participants():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    db.init_app(app)

    account_id = 111620041
    steam_id = account_id + 76561197960265728
    match_id = 8871520485
    match_data = {
        "league": 19892,
        "league_name": "The International 2026 - Regional Qualifier Europe",
        "duration": 3890,
        "region": 3,
        "date": 1782667298,
        "version": 60,
        "players": [{"id": account_id, "name": "SumaiL-"}],
    }
    ward_data = {
        "event": "expired",
        "npc_killed": "",
        "player_placed_steam_id": steam_id,
        "player_destroyed_steam_id": None,
        "is_obs": True,
        "is_radiant": True,
        "post_game": False,
        "time_placed": 100,
        "duration": 360,
        "x": 1,
        "y": 2,
        "z": 3,
        "vec_x": 0,
        "vec_y": 0,
        "vec_z": 0,
        "radiant_networth": 1000,
        "dire_networth": 900,
    }

    with app.app_context():
        db.create_all()
        persist_parsed_replay((match_id, match_data, [ward_data]))

        player = db.session.get(Player, account_id)
        match = db.session.get(Match, match_id)
        league = db.session.get(League, 19892)
        ward = db.session.execute(select(Ward)).scalar_one()

        assert player is not None and player.name == "SumaiL-"
        assert match is not None and player in match.players
        assert league is not None and player in league.players
        assert ward.player_placed_id == account_id
