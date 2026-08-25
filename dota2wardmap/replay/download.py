import bz2
import io
import logging
from typing import Any

import requests

from ..integrations import opendota

logger = logging.getLogger(__name__)

_ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
_CHINA_REPLAY_CLUSTERS = frozenset({413, 415, 417})


def replay_url(match_id: int, cluster: int, salt: int) -> str:
    domain = "dota2.com.cn" if cluster in _CHINA_REPLAY_CLUSTERS else "valve.net"

    return f"http://replay{cluster}.{domain}/570/{match_id}_{salt}.dem.bz2"


def _decompress_zstd(content: bytes) -> bytes:
    try:
        import zstandard as zstd
    except ImportError as exc:  # pragma: no cover - deployment dependency issue
        raise RuntimeError("zstd replay archives require the zstandard package") from exc

    try:
        with zstd.ZstdDecompressor().stream_reader(io.BytesIO(content)) as reader:
            return reader.read()
    except zstd.ZstdError as exc:
        raise OSError("Invalid data stream") from exc


def decompress_replay_archive(content: bytes) -> bytes:
    if content.startswith(b"BZh"):
        return bz2.decompress(content)

    if content.startswith(_ZSTD_MAGIC):
        return _decompress_zstd(content)

    try:
        return bz2.decompress(content)
    except OSError:
        return _decompress_zstd(content)


def get_match_data(match_id: int) -> dict[str, Any]:
    response = opendota.get_match(match_id)
    league = response.get("league") or {}
    radiant_team = response.get("radiant_team") or {}
    dire_team = response.get("dire_team") or {}
    return {
        "cluster": response.get("cluster"),
        "salt": response.get("replay_salt"),
        "replay_url": response.get("replay_url"),
        "league": response.get("leagueid") or league.get("leagueid"),
        "league_name": league.get("name"),
        "duration": response.get("duration"),
        "region": response.get("region"),
        "date": response.get("start_time"),
        "version": response.get("patch"),
        "radiant_team": {
            "id": response.get("radiant_team_id") or radiant_team.get("team_id"),
            "name": radiant_team.get("name") or response.get("radiant_name"),
            "tag": radiant_team.get("tag"),
            "logo_url": radiant_team.get("logo_url"),
        },
        "dire_team": {
            "id": response.get("dire_team_id") or dire_team.get("team_id"),
            "name": dire_team.get("name") or response.get("dire_name"),
            "tag": dire_team.get("tag"),
            "logo_url": dire_team.get("logo_url"),
        },
        "radiant_win": response.get("radiant_win"),
        "players": [
            {
                "id": player["account_id"],
                "name": player.get("name") or player.get("personaname"),
                "is_radiant": (
                    player.get("isRadiant")
                    if player.get("isRadiant") is not None
                    else player["player_slot"] < 128
                    if player.get("player_slot") is not None
                    else None
                ),
            }
            for player in (response.get("players") or [])
            if player.get("account_id") is not None
        ],
    }


def get_replay(match_id: int) -> tuple[bytes, dict[str, Any]] | None:
    try:
        match_data = get_match_data(match_id)
        cluster, salt = match_data.get("cluster"), match_data.get("salt")
    except opendota.OpenDotaError:
        logger.exception("Invalid OpenDota response for match %s", match_id)
        return None

    url = match_data.get("replay_url")
    if not url and cluster is not None and salt is not None:
        url = replay_url(match_id, cluster, salt)
    if not url:
        logger.warning("OpenDota has no replay location for match %s", match_id)
        return None

    try:
        response = requests.get(url, timeout=10)
    except requests.RequestException:
        logger.exception("Unable to download replay for match %s", match_id)
        return None

    if response.status_code == 404:
        logger.warning("Replay for match %s is no longer available from Valve", match_id)
        return None
    try:
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Unable to download replay for match %s", match_id)
        return None

    try:
        replay = decompress_replay_archive(response.content)
    except (OSError, RuntimeError):
        logger.exception("Valve returned an invalid replay archive for match %s", match_id)
        return None

    return replay, match_data
