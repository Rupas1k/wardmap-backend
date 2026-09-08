import logging
import time
from collections import defaultdict
from typing import Any

from sqlalchemy import or_, select

from ..extensions import db
from ..integrations import opendota
from ..models import Match, players_matches
from ..team_metadata import refresh_stale_team_metadata
from .persistence import apply_match_team_data

logger = logging.getLogger(__name__)


def backfill_match_player_sides(
    league_ids: tuple[int, ...] = (),
    limit: int | None = None,
    delay_seconds: float = 1.5,
) -> tuple[int, int, int]:
    query = select(Match.id).join(players_matches, players_matches.c.match_id == Match.id).distinct()

    if league_ids:
        query = query.where(Match.league_id.in_(league_ids))
    else:
        query = query.where(players_matches.c.is_radiant.is_(None))

    if limit is not None:
        query = query.limit(limit)

    match_ids = db.session.execute(query.order_by(Match.id)).scalars().all()
    updated_matches = 0
    updated_players = 0
    failed = 0

    for match_id in match_ids:
        try:
            record = opendota.get_match(match_id)
            sides = {
                int(player["account_id"]): side
                for player in record.get("players", [])
                if player.get("account_id") is not None and (side := _player_side(player)) is not None
            }

            changed = 0
            for player_id, is_radiant in sides.items():
                result = db.session.execute(
                    players_matches.update()
                    .where(
                        players_matches.c.match_id == match_id,
                        players_matches.c.player_id == player_id,
                    )
                    .values(is_radiant=is_radiant)
                )
                changed += getattr(result, "rowcount", 0)

            db.session.commit()
            updated_matches += 1
            updated_players += changed
        except (opendota.OpenDotaError, ValueError, TypeError, KeyError):
            db.session.rollback()
            failed += 1
            logger.exception("Unable to backfill player sides for match %s", match_id)
        finally:
            if delay_seconds > 0:
                time.sleep(delay_seconds)

    return updated_matches, updated_players, failed


def _player_side(player: dict[str, Any]) -> bool | None:
    if player.get("isRadiant") is not None:
        return bool(player["isRadiant"])

    player_slot = player.get("player_slot")
    if player_slot is None:
        return None

    return int(player_slot) < 128


def backfill_match_teams(limit: int | None = None) -> tuple[int, int]:
    query = select(Match).where(
        or_(Match.radiant_team_id.is_(None), Match.dire_team_id.is_(None), Match.radiant_win.is_(None))
    )
    if limit is not None:
        query = query.limit(limit)
    matches = db.session.execute(query.order_by(Match.id)).scalars().all()
    matches_by_league: dict[int, list[Match]] = defaultdict(list)
    missing_league = 0
    for match in matches:
        if match.league_id is None:
            missing_league += 1
        else:
            matches_by_league[match.league_id].append(match)

    updated = 0
    failed = missing_league
    for league_id, league_matches in matches_by_league.items():
        try:
            records = {
                int(record["match_id"]): record
                for record in opendota.get_league_matches(league_id)
                if record.get("match_id") is not None
            }
            for match in league_matches:
                record = records.get(match.id)
                if record is None:
                    failed += 1
                    continue
                apply_match_team_data(match, _league_match_data(record))
                updated += 1
            db.session.commit()
        except (opendota.OpenDotaError, ValueError, TypeError, KeyError):
            db.session.rollback()
            failed += len(league_matches)
            logger.exception("Unable to backfill team metadata for league %s", league_id)
    _, team_failures = refresh_stale_team_metadata(missing_only=True)
    failed += team_failures
    return updated, failed


def _league_match_data(record: dict[str, Any]) -> dict[str, Any]:
    radiant_team = record.get("radiant_team") or {}
    dire_team = record.get("dire_team") or {}
    return {
        "radiant_team": {
            "id": record.get("radiant_team_id") or radiant_team.get("team_id"),
            "name": record.get("radiant_name") or radiant_team.get("name"),
            "tag": radiant_team.get("tag"),
            "logo_url": radiant_team.get("logo_url"),
        },
        "dire_team": {
            "id": record.get("dire_team_id") or dire_team.get("team_id"),
            "name": record.get("dire_name") or dire_team.get("name"),
            "tag": dire_team.get("tag"),
            "logo_url": dire_team.get("logo_url"),
        },
        "radiant_win": record.get("radiant_win"),
    }
