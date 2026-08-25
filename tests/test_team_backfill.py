from dota2wardmap.replay.backfill import _league_match_data


def test_league_match_data_normalizes_team_context():
    assert _league_match_data(
        {
            "match_id": 100,
            "radiant_team_id": 10,
            "radiant_name": "Radiant Team",
            "dire_team_id": 20,
            "dire_name": "Dire Team",
            "radiant_win": True,
        }
    ) == {
        "radiant_team": {"id": 10, "name": "Radiant Team", "tag": None, "logo_url": None},
        "dire_team": {"id": 20, "name": "Dire Team", "tag": None, "logo_url": None},
        "radiant_win": True,
    }
