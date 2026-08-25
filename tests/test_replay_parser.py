import bz2

from flask import Flask
from sqlalchemy import select

from dota2wardmap import create_worker_app
from dota2wardmap.extensions import db
from dota2wardmap.models import League, Match, Player, Team, Ward
from dota2wardmap.replay.download import decompress_replay_archive as _decompress_replay_archive
from dota2wardmap.replay.download import get_replay
from dota2wardmap.replay.persistence import persist_parsed_replay
from dota2wardmap.settings import get_settings


def test_worker_app_has_connections_without_api_routes(monkeypatch):
    monkeypatch.setenv("DB_URL", "sqlite://")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    get_settings.cache_clear()
    try:
        app = create_worker_app()
    finally:
        get_settings.cache_clear()

    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite://"
    assert app.config["REDIS_URL"] == "redis://localhost:6379/0"
    assert {rule.endpoint for rule in app.url_map.iter_rules()} == {"static"}


def test_decompress_replay_archive_handles_bzip2_and_zstd(monkeypatch):
    import io

    import zstandard as zstd

    original = b"replay-bytes"
    bzip2_content = bz2.compress(original)
    zstd_buffer = io.BytesIO()
    with zstd.ZstdCompressor().stream_writer(zstd_buffer, closefd=False) as writer:
        writer.write(original)
    zstd_content = zstd_buffer.getvalue()

    assert _decompress_replay_archive(bzip2_content) == original
    assert _decompress_replay_archive(zstd_content) == original


def test_get_replay_prefers_opendota_replay_url_without_salt(monkeypatch):
    import dota2wardmap.replay.download as download

    opendota_url = "http://replay413.dota2.com.cn/570/123_456.dem.bz2"
    match_response = {
        "match_id": 123,
        "cluster": 413,
        "replay_salt": None,
        "replay_url": opendota_url,
    }

    class Response:
        content = bz2.compress(b"replay")
        status_code = 200

        @staticmethod
        def raise_for_status():
            return None

    requested_urls = []
    monkeypatch.setattr(download.opendota, "get_match", lambda _match_id: match_response)
    monkeypatch.setattr(
        download.requests,
        "get",
        lambda url, timeout: requested_urls.append((url, timeout)) or Response(),
    )

    replay, match_data = get_replay(123) or (None, None)

    assert replay == b"replay"
    assert requested_urls == [(opendota_url, 10)]
    assert match_data is not None and match_data["replay_url"] == opendota_url


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
        "radiant_team": {"id": 10, "name": "Radiant Team", "tag": "RAD"},
        "dire_team": {"id": 20, "name": "Dire Team", "tag": "DIRE"},
        "radiant_win": True,
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
        radiant_team = db.session.get(Team, 10)

        assert player is not None and player.name == "SumaiL-"
        assert match is not None and player in match.players
        assert league is not None and match in league.matches
        assert ward.player_placed_id == account_id
        assert radiant_team is not None and radiant_team.name == "Radiant Team"
        assert radiant_team.metadata_updated_at is not None
        assert match.radiant_team_id == 10 and match.dire_team_id == 20
        assert match.radiant_win is True
