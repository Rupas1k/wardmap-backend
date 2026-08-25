from typing import Any

import requests

from ..settings import get_settings


class OpenDotaError(RuntimeError):
    """Raised when OpenDota cannot provide a valid response."""


def _get(path: str) -> Any:
    settings = get_settings()
    params = {"api_key": settings.opendota_api_key} if settings.opendota_api_key else None
    try:
        response = requests.get(
            f"{settings.opendota_api_url}/{path.lstrip('/')}",
            params=params,
            timeout=settings.opendota_timeout,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise OpenDotaError(f"OpenDota request failed for {path}") from exc


def get_league(league_id: int) -> dict[str, Any] | None:
    league = _get(f"leagues/{league_id}")
    if not isinstance(league, dict) or league.get("leagueid") is None:
        return None
    return league


def get_league_matches(league_id: int) -> list[dict[str, Any]]:
    matches = _get(f"leagues/{league_id}/matches")
    if not isinstance(matches, list):
        raise OpenDotaError(f"OpenDota returned invalid matches for league {league_id}")
    return matches


def get_match(match_id: int) -> dict[str, Any]:
    match = _get(f"matches/{match_id}")
    if not isinstance(match, dict) or match.get("match_id") is None:
        raise OpenDotaError(f"Match {match_id} was not found in OpenDota")
    return match


def get_team(team_id: int) -> dict[str, Any] | None:
    team = _get(f"teams/{team_id}")
    if not isinstance(team, dict) or team.get("team_id") is None:
        return None
    return team
