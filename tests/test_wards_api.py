import pytest
from flask import Flask, g

from dota2wardmap.api.players import bp as players_bp
from dota2wardmap.api.teams import bp as teams_bp
from dota2wardmap.api.wards import MAX_FILTER_IDS, bp
from dota2wardmap.extensions import db
from dota2wardmap.models import League, Match, Player, Team, Ward


def test_query_wards_applies_dataset_filters():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    db.init_app(app)
    app.register_blueprint(bp)
    app.register_blueprint(teams_bp)
    app.register_blueprint(players_bp)
    app.before_request(lambda: setattr(g, "access_level", "anonymous"))

    with app.app_context():
        db.create_all()
        db.session.add(League(id=42, name="Test League"))
        db.session.add(Player(id=7, name="Support"))
        db.session.add(Team(id=10, name="Radiant Team", tag="RAD"))
        db.session.add(Team(id=20, name="Dire Team", tag="DIRE"))
        db.session.add(
            Match(
                id=100,
                league_id=42,
                duration=2400,
                radiant_team_id=10,
                dire_team_id=20,
                radiant_win=True,
            )
        )
        db.session.add(
            Ward(
                match_id=100,
                is_obs=True,
                is_radiant=True,
                is_destroyed=False,
                is_post_game=False,
                player_placed_id=7,
                time_placed=600,
                duration=360,
                x_pos=10,
                y_pos=20,
                z_pos=30,
            )
        )
        db.session.commit()

        with app.test_client() as client:
            response = client.post(
                "/wards/query",
                json={
                    "league_ids": [42],
                    "player_ids": [7],
                    "team_ids": [10],
                    "opponent_team_ids": [20],
                    "team_result": "won",
                    "side": "radiant",
                    "ward_type": "observer",
                    "outcome": "survived",
                    "minimum_game_minute": 5,
                    "maximum_game_minute": 15,
                    "minimum_match_duration": 30,
                    "maximum_match_duration": 60,
                    "minimum_ward_lifetime": 300,
                    "maximum_ward_lifetime": 400,
                },
            )
            count_response = client.post(
                "/wards/query",
                json={
                    "league_ids": [42],
                    "team_ids": [10],
                    "ward_type": "observer",
                    "count_only": True,
                },
            )

    assert response.status_code == 200
    assert count_response.status_code == 200
    assert count_response.get_json() == {"count": 1}
    assert response.get_json() == {
        "data": [
            {
                "id": 1,
                "match_id": 100,
                "player_placed_id": 7,
                "player_name": "Support",
                "is_radiant": True,
                "is_obs": True,
                "is_destroyed": False,
                "time_placed": 600,
                "duration": 360,
                "x_pos": 10,
                "y_pos": 20,
                "z_pos": 30,
                "radiant_networth": None,
                "dire_networth": None,
                "enemy_hero_vision_seconds": None,
                "unique_enemy_hero_vision_seconds": None,
                "heroes_spotted": None,
                "hero_reveal_events": None,
                "unique_hero_reveal_events": None,
                "scouting_tracking_seconds": None,
                "scouting_discovery_seconds": None,
                "scouting_score": None,
                "scouting_version": None,
                "scouting_tau_seconds": None,
                "scouting_complete": None,
                "match_duration": 2400,
                "team_id": 10,
                "team_name": "Radiant Team",
                "opponent_team_id": 20,
                "opponent_team_name": "Dire Team",
                "team_won": True,
            }
        ],
        "pagination": {"page_size": 2000, "has_more": False, "next_cursor": None},
    }

    with app.test_client() as client:
        teams_response = client.get("/teams?league_ids=42")
    assert teams_response.status_code == 200
    assert teams_response.get_json() == {
        "data": [
            {"id": 20, "name": "Dire Team", "tag": "DIRE", "logo_url": None},
            {"id": 10, "name": "Radiant Team", "tag": "RAD", "logo_url": None},
        ]
    }

    with app.test_client() as client:
        players_response = client.get("/players?league_ids=42")
    assert players_response.status_code == 200
    assert players_response.get_json() == {"data": [{"id": 7, "name": "Support", "ward_count": 1}]}


def test_query_wards_rejects_non_numeric_ids():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    db.init_app(app)
    app.register_blueprint(bp)

    with app.test_client() as client:
        response = client.post("/wards/query", json={"player_ids": ["player name"]})

    assert response.status_code == 400


def test_query_wards_rejects_non_array_ids():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    db.init_app(app)
    app.register_blueprint(bp)

    with app.test_client() as client:
        response = client.post("/wards/query", json={"player_ids": "123"})

    assert response.status_code == 400


def test_query_wards_rejects_too_many_ids():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    db.init_app(app)
    app.register_blueprint(bp)

    with app.test_client() as client:
        response = client.post("/wards/query", json={"player_ids": list(range(MAX_FILTER_IDS + 1))})

    assert response.status_code == 400


def test_query_wards_rejects_non_boolean_count_only():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    db.init_app(app)
    app.register_blueprint(bp)

    with app.test_client() as client:
        response = client.post("/wards/query", json={"count_only": "yes"})

    assert response.status_code == 400


def test_query_wards_rejects_unscoped_count():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    db.init_app(app)
    app.register_blueprint(bp)

    with app.test_client() as client:
        response = client.post("/wards/query", json={"count_only": True})

    assert response.status_code == 400


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_query_wards_rejects_non_finite_numbers(value):
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    db.init_app(app)
    app.register_blueprint(bp)

    with app.test_client() as client:
        response = client.post("/wards/query", json={"minimum_game_minute": value})

    assert response.status_code == 400


def test_query_wards_accepts_ninety_seconds_of_pregame_time():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    db.init_app(app)
    app.register_blueprint(bp)
    app.before_request(lambda: setattr(g, "access_level", "anonymous"))

    with app.app_context():
        db.create_all()
        db.session.add(Match(id=200, duration=2400))
        db.session.add(
            Ward(
                match_id=200,
                is_obs=True,
                is_radiant=True,
                is_destroyed=False,
                is_post_game=False,
                time_placed=-90,
                duration=120,
                x_pos=10,
                y_pos=20,
                z_pos=30,
            )
        )
        db.session.commit()
        with app.test_client() as client:
            response = client.post(
                "/wards/query",
                json={
                    "minimum_game_minute": -1.5,
                    "maximum_game_minute": 0,
                    "minimum_match_duration": 0,
                    "maximum_match_duration": 60,
                    "minimum_ward_lifetime": 0,
                    "maximum_ward_lifetime": 600,
                },
            )

    assert response.status_code == 200
    assert [ward["time_placed"] for ward in response.get_json()["data"]] == [-90]


def test_query_wards_rejects_time_before_pregame_limit():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    db.init_app(app)
    app.register_blueprint(bp)

    with app.test_client() as client:
        response = client.post(
            "/wards/query",
            json={"minimum_game_minute": -1.51, "maximum_game_minute": 60},
        )

    assert response.status_code == 400
