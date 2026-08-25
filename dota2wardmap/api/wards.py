from typing import Any

from flask import Blueprint, request
from sqlalchemy import case, exists, select
from sqlalchemy.orm import aliased
from werkzeug.exceptions import BadRequest

from ..access import max_ward_page_size
from ..extensions import db
from ..models import Match, Player, Team, Ward, players_matches

bp = Blueprint("wards", __name__)


def unit_display_name(unit_name: str | None) -> str | None:
    if not unit_name:
        return None

    prefixes = {
        "npc_dota_hero_": "",
        "npc_dota_creep_goodguys_": "Radiant ",
        "npc_dota_creep_badguys_": "Dire ",
    }
    for prefix, label in prefixes.items():
        if unit_name.startswith(prefix):
            words = unit_name.removeprefix(prefix).replace("_", " ")
            suffix = " creep" if "creep_" in prefix else ""

            return f"{label}{words}{suffix}".title()

    return unit_name.removeprefix("npc_dota_").replace("_", " ").title()


def ward_response(row: Any) -> dict[str, Any]:
    data = row._asdict()
    npc_killed = data.pop("npc_killed")

    if not data["is_destroyed"]:
        data.pop("player_destroyed_id")
        data.pop("player_destroyed_name")
    elif data["player_destroyed_name"] is None:
        data["player_destroyed_name"] = unit_display_name(npc_killed)

    return data


def integer_list(filters: Any, name: str) -> list[int]:
    try:
        values = filters.getlist(name) if hasattr(filters, "getlist") else filters.get(name, [])
        return [int(value) for value in values]
    except (TypeError, ValueError) as exc:
        raise BadRequest(f"{name} must contain numeric IDs") from exc


def integer_filter(filters: dict[str, Any], name: str, default: int) -> int:
    try:
        return int(filters.get(name, default))
    except (TypeError, ValueError) as exc:
        raise BadRequest(f"{name} must be an integer") from exc


def number_filter(filters: dict[str, Any], name: str, default: float) -> float:
    try:
        return float(filters.get(name, default))
    except (TypeError, ValueError) as exc:
        raise BadRequest(f"{name} must be a number") from exc


@bp.post("/wards/query")
def query_wards():
    filters = request.get_json(silent=True) or {}
    if not isinstance(filters, dict):
        raise BadRequest("request body must be a JSON object")
    owner_team = aliased(Team)
    opponent_team = aliased(Team)
    destroying_player = aliased(Player)
    owner_team_id = case(
        (Ward.is_radiant.is_(True), Match.radiant_team_id),
        (Ward.is_radiant.is_(False), Match.dire_team_id),
    )
    opponent_team_id = case(
        (Ward.is_radiant.is_(True), Match.dire_team_id),
        (Ward.is_radiant.is_(False), Match.radiant_team_id),
    )
    team_won = case(
        (Match.radiant_win.is_(None), None),
        (Ward.is_radiant.is_(True), Match.radiant_win),
        (Ward.is_radiant.is_(False), ~Match.radiant_win),
    )
    query = (
        select(
            Ward.id,
            Ward.match_id,
            Ward.player_placed_id,
            Player.name.label("player_name"),
            Ward.player_destroyed_id,
            destroying_player.name.label("player_destroyed_name"),
            Ward.is_radiant,
            Ward.is_obs,
            Ward.is_destroyed,
            Ward.time_placed,
            Ward.duration,
            Ward.npc_killed,
            Ward.x_pos,
            Ward.y_pos,
            Ward.z_pos,
            Ward.radiant_networth,
            Ward.dire_networth,
            Ward.enemy_hero_vision_seconds,
            Ward.unique_enemy_hero_vision_seconds,
            Ward.heroes_spotted,
            Ward.hero_reveal_events,
            Ward.unique_hero_reveal_events,
            Match.duration.label("match_duration"),
            owner_team_id.label("team_id"),
            owner_team.name.label("team_name"),
            opponent_team_id.label("opponent_team_id"),
            opponent_team.name.label("opponent_team_name"),
            team_won.label("team_won"),
        )
        .select_from(Ward)
        .join(Match, Match.id == Ward.match_id)
        .outerjoin(Player, Player.id == Ward.player_placed_id)
        .outerjoin(destroying_player, destroying_player.id == Ward.player_destroyed_id)
        .outerjoin(owner_team, owner_team.id == owner_team_id)
        .outerjoin(opponent_team, opponent_team.id == opponent_team_id)
    )

    league_ids = integer_list(filters, "league_ids")
    match_ids = integer_list(filters, "match_ids")
    player_ids = integer_list(filters, "player_ids")
    opponent_player_ids = integer_list(filters, "opponent_player_ids")
    destroyed_by_player_ids = integer_list(filters, "destroyed_by_player_ids")
    team_ids = integer_list(filters, "team_ids")
    opponent_team_ids = integer_list(filters, "opponent_team_ids")
    if league_ids:
        query = query.where(Match.league_id.in_(league_ids))
    if match_ids:
        query = query.where(Ward.match_id.in_(match_ids))
    if player_ids:
        query = query.where(Ward.player_placed_id.in_(player_ids))
    if destroyed_by_player_ids:
        query = query.where(Ward.player_destroyed_id.in_(destroyed_by_player_ids))
    if opponent_player_ids:
        opponent_players = players_matches.alias("opponent_players")
        query = query.where(
            Ward.is_radiant.is_not(None),
            exists(
                select(1).where(
                    opponent_players.c.match_id == Ward.match_id,
                    opponent_players.c.is_radiant.is_not(None),
                    opponent_players.c.is_radiant != Ward.is_radiant,
                    opponent_players.c.player_id.in_(opponent_player_ids),
                )
            ),
        )
    if team_ids:
        query = query.where(owner_team_id.in_(team_ids))
    if opponent_team_ids:
        query = query.where(opponent_team_id.in_(opponent_team_ids))

    team_result = filters.get("team_result", "all")
    if team_result not in ("all", "won", "lost"):
        raise BadRequest("team_result must be all, won, or lost")
    if team_result in ("won", "lost"):
        query = query.where(team_won.is_(team_result == "won"))

    side = filters.get("side", "all")
    if side not in ("all", "radiant", "dire"):
        raise BadRequest("side must be all, radiant, or dire")
    if side in ("radiant", "dire"):
        query = query.where(Ward.is_radiant.is_(side == "radiant"))

    ward_type = filters.get("ward_type", "all")
    if ward_type not in ("all", "observer", "sentry"):
        raise BadRequest("ward_type must be all, observer, or sentry")
    if ward_type in ("observer", "sentry"):
        query = query.where(Ward.is_obs.is_(ward_type == "observer"))

    outcome = filters.get("outcome", "all")
    if outcome not in ("all", "destroyed", "survived"):
        raise BadRequest("outcome must be all, destroyed, or survived")
    if outcome in ("destroyed", "survived"):
        query = query.where(Ward.is_destroyed.is_(outcome == "destroyed"))

    ranges = (
        (
            "game minute",
            number_filter(filters, "minimum_game_minute", -1.5),
            number_filter(filters, "maximum_game_minute", 60),
        ),
        (
            "match duration",
            integer_filter(filters, "minimum_match_duration", 0),
            integer_filter(filters, "maximum_match_duration", 180),
        ),
        (
            "ward lifetime",
            integer_filter(filters, "minimum_ward_lifetime", 0),
            integer_filter(filters, "maximum_ward_lifetime", 600),
        ),
    )
    for name, minimum, maximum in ranges:
        minimum_allowed = -1.5 if name == "game minute" else 0
        if minimum < minimum_allowed or maximum < minimum:
            raise BadRequest(f"invalid {name} range")
    query = query.where(
        Ward.time_placed >= ranges[0][1] * 60,
        Ward.time_placed <= ranges[0][2] * 60,
        Match.duration >= ranges[1][1] * 60,
        Match.duration <= ranges[1][2] * 60,
        Ward.duration >= ranges[2][1],
        Ward.duration <= ranges[2][2],
    )
    try:
        page_size = integer_filter(filters, "page_size", 2000)
        cursor = filters.get("cursor")
        cursor = int(cursor) if cursor is not None else None
    except (TypeError, ValueError) as exc:
        raise BadRequest("page_size and cursor must be integers") from exc
    if page_size < 1:
        raise BadRequest("page_size must be greater than zero")
    page_size = min(page_size, max_ward_page_size())
    if cursor is not None:
        query = query.where(Ward.id < cursor)

    rows = db.session.execute(query.order_by(Ward.id.desc()).limit(page_size + 1)).all()
    has_more = len(rows) > page_size
    rows = rows[:page_size]
    return {
        "data": [ward_response(row) for row in rows],
        "pagination": {
            "page_size": page_size,
            "has_more": has_more,
            "next_cursor": rows[-1].id if has_more and rows else None,
        },
    }
