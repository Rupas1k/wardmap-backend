from unittest.mock import Mock, patch

import pytest

from dota2wardmap.integrations import dota_gc
from dota2wardmap.settings import get_settings


def test_get_player_matches(monkeypatch):
    monkeypatch.setenv("DOTA_GC_URL", "http://gc:5700")
    monkeypatch.setenv("DOTA_GC_TOKEN", "secret")
    get_settings.cache_clear()
    response = Mock()
    response.json.return_value = {"matches": [9000000001]}

    with patch("dota2wardmap.integrations.dota_gc.requests.get", return_value=response) as request:
        assert dota_gc.get_player_matches(123, start_at_match_id=8000000000) == [9000000001]

    request.assert_called_once_with(
        "http://gc:5700/players/123/matches?limit=20&start_at_match_id=8000000000",
        headers={"Authorization": "Bearer secret"},
        timeout=30.0,
    )


def test_get_player_matches_rejects_invalid_payload(monkeypatch):
    monkeypatch.setenv("DOTA_GC_URL", "http://gc:5700")
    get_settings.cache_clear()
    response = Mock()
    response.json.return_value = {"matches": ["9000000001"]}

    with (
        patch("dota2wardmap.integrations.dota_gc.requests.get", return_value=response),
        pytest.raises(dota_gc.DotaGCError),
    ):
        dota_gc.get_player_matches(123)


def test_get_account_id(monkeypatch):
    monkeypatch.setenv("DOTA_GC_URL", "http://gc:5700")
    get_settings.cache_clear()
    response = Mock()
    response.json.return_value = {"account_id": 123}

    with patch("dota2wardmap.integrations.dota_gc.requests.get", return_value=response):
        assert dota_gc.get_account_id() == 123
