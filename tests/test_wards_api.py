from flask import Flask

from dota2wardmap.api.wards import bp
from dota2wardmap.extensions import db
from dota2wardmap.models import League, Match, Player, Ward


def test_query_wards_applies_dataset_filters():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    db.init_app(app)
    app.register_blueprint(bp)

    with app.app_context():
        db.create_all()
        db.session.add(League(id=42, name="Test League"))
        db.session.add(Player(id=7, name="Support"))
        db.session.add(Match(id=100, league_id=42, duration=2400))
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

    assert response.status_code == 200
    assert response.get_json() == {"data": [{"id": 1, "x_pos": 10, "y_pos": 20, "z_pos": 30}]}


def test_query_wards_rejects_non_numeric_ids():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    db.init_app(app)
    app.register_blueprint(bp)

    with app.test_client() as client:
        response = client.post("/wards/query", json={"player_ids": ["player name"]})

    assert response.status_code == 400
