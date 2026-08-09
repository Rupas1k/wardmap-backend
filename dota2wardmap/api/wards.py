from typing import Any

from flask import Blueprint, request
from sqlalchemy import select
from werkzeug.exceptions import BadRequest

from ..access import max_ward_page_size
from ..extensions import db
from ..models import Match, Player, Ward

bp = Blueprint("wards", __name__)


def integer_list(filters: dict[str, Any], name: str) -> list[int]:
    try:
        return [int(value) for value in filters.get(name, [])]
    except (TypeError, ValueError) as exc:
        raise BadRequest(f"{name} must contain numeric IDs") from exc


def integer_filter(filters: dict[str, Any], name: str, default: int) -> int:
    try:
        return int(filters.get(name, default))
    except (TypeError, ValueError) as exc:
        raise BadRequest(f"{name} must be an integer") from exc


@bp.post("/wards/query")
def query_wards():
    filters = request.get_json(silent=True) or {}
    if not isinstance(filters, dict):
        raise BadRequest("request body must be a JSON object")
    query = (
        select(
            Ward.id,
            Ward.match_id,
            Ward.player_placed_id,
            Player.name.label("player_name"),
            Ward.is_radiant,
            Ward.is_obs,
            Ward.is_destroyed,
            Ward.time_placed,
            Ward.duration,
            Ward.x_pos,
            Ward.y_pos,
            Ward.z_pos,
            Ward.radiant_networth,
            Ward.dire_networth,
            Match.duration.label("match_duration"),
        )
        .join(Match)
        .outerjoin(Player, Player.id == Ward.player_placed_id)
    )

    league_ids = integer_list(filters, "league_ids")
    match_ids = integer_list(filters, "match_ids")
    player_ids = integer_list(filters, "player_ids")
    if league_ids:
        query = query.where(Match.league_id.in_(league_ids))
    if match_ids:
        query = query.where(Ward.match_id.in_(match_ids))
    if player_ids:
        query = query.where(Ward.player_placed_id.in_(player_ids))

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
            integer_filter(filters, "minimum_game_minute", 0),
            integer_filter(filters, "maximum_game_minute", 60),
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
        if minimum < 0 or maximum < minimum:
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
        "data": [row._asdict() for row in rows],
        "pagination": {
            "page_size": page_size,
            "has_more": has_more,
            "next_cursor": rows[-1].id if has_more and rows else None,
        },
    }
