from typing import Any

import requests

from ..settings import get_settings


class DotaGCError(RuntimeError):
    pass


def _get(path: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.dota_gc_url:
        raise DotaGCError("DOTA_GC_URL is not configured")

    headers = {"Authorization": f"Bearer {settings.dota_gc_token}"} if settings.dota_gc_token else {}

    try:
        response = requests.get(
            f"{settings.dota_gc_url}{path}",
            headers=headers,
            timeout=settings.dota_gc_timeout,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise DotaGCError(f"Dota GC request failed for {path}") from exc

    if not isinstance(payload, dict):
        raise DotaGCError(f"Dota GC returned an invalid response for {path}")

    return payload


def get_player_matches(account_id: int, limit: int = 100) -> list[int]:
    payload = _get(f"/players/{account_id}/matches?limit={limit}")
    matches = payload.get("matches")

    if not isinstance(matches, list) or not all(isinstance(match_id, int) for match_id in matches):
        raise DotaGCError(f"Dota GC returned invalid match history for player {account_id}")

    return matches


def get_account_id() -> int:
    payload = _get("/account")
    account_id = payload.get("account_id")

    if not isinstance(account_id, int) or account_id <= 0 or account_id > 0xFFFFFFFF:
        raise DotaGCError("Dota GC returned an invalid authenticated account ID")

    return account_id


def get_match(match_id: int) -> dict[str, Any]:
    payload = _get(f"/matches/{match_id}")
    match = payload.get("match")

    if not isinstance(match, dict):
        raise DotaGCError(f"Dota GC returned invalid match details for match {match_id}")

    return match
