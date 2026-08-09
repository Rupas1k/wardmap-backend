from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from dota2wardmap.integrations import opendota


def response(payload, status_code=200):
    result = Mock()
    result.status_code = status_code
    result.json.return_value = payload
    result.raise_for_status.return_value = None
    return result


def test_get_league_uses_opendota(monkeypatch):
    request = Mock(return_value=response({"leagueid": 19892, "name": "The International 2026"}))
    monkeypatch.setattr(opendota.requests, "get", request)
    monkeypatch.setattr(
        opendota,
        "get_settings",
        lambda: SimpleNamespace(
            opendota_api_url="https://api.opendota.com/api",
            opendota_api_key=None,
            opendota_timeout=30,
        ),
    )

    league = opendota.get_league(19892)

    assert league == {"leagueid": 19892, "name": "The International 2026"}
    request.assert_called_once_with(
        "https://api.opendota.com/api/leagues/19892",
        params=None,
        timeout=30,
    )


def test_get_league_returns_none_for_missing_league(monkeypatch):
    monkeypatch.setattr(opendota.requests, "get", Mock(return_value=response({}, status_code=404)))

    assert opendota.get_league(999999) is None


def test_get_league_matches_rejects_invalid_response(monkeypatch):
    monkeypatch.setattr(opendota.requests, "get", Mock(return_value=response({"error": "invalid"})))

    with pytest.raises(opendota.OpenDotaError, match="invalid matches"):
        opendota.get_league_matches(19892)


def test_api_key_is_sent_when_configured(monkeypatch):
    request = Mock(return_value=response({"match_id": 8871520485}))
    monkeypatch.setattr(opendota.requests, "get", request)
    monkeypatch.setattr(
        opendota,
        "get_settings",
        lambda: SimpleNamespace(
            opendota_api_url="https://api.opendota.com/api",
            opendota_api_key="secret",
            opendota_timeout=30,
        ),
    )

    opendota.get_match(8871520485)

    assert request.call_args.kwargs["params"] == {"api_key": "secret"}
