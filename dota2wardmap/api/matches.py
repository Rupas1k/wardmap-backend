from datetime import UTC, datetime

from flask import Blueprint, current_app, request
from sqlalchemy import distinct, func, select
from werkzeug.exceptions import BadRequest, NotFound

from ..access import require_access
from ..domain import AccessLevel
from ..extensions import db
from ..integrations import opendota
from ..models import League, Match, Ward
from ..replay.collector import sync_league

bp = Blueprint("matches", __name__)


@bp.post("/leagues/<int:league_id>/queue")
@require_access(AccessLevel.ADMIN)
def queue_league(league_id: int):
    try:
        queued, matches = sync_league(league_id)
    except ValueError:
        db.session.rollback()
        return {"error": f"League {league_id} was not found in OpenDota"}, 404
    except opendota.OpenDotaError:
        db.session.rollback()
        current_app.logger.exception("Unable to load OpenDota league %s", league_id)
        return {"error": "OpenDota is temporarily unavailable"}, 502

    return {"queued": queued, "matches": matches}


@bp.post("/leagues/<int:league_id>/tracking")
@require_access(AccessLevel.ADMIN)
def update_league_tracking(league_id: int):
    league = db.session.get(League, league_id)
    if league is None:
        raise NotFound(f"League {league_id} does not exist")
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        raise BadRequest("request body must be a JSON object")
    status = body.get("status")
    if status not in ("active", "paused", "completed"):
        raise BadRequest("status must be active, paused, or completed")

    now = datetime.now(UTC)
    league.tracking_status = status
    if status == "completed":
        league.completed_at = now
        league.next_check_at = None
    elif status == "active":
        league.completed_at = None
        league.next_check_at = now
        league.consecutive_empty_checks = 0
    else:
        league.next_check_at = None
    db.session.commit()
    return {"league_id": league.id, "tracking_status": league.tracking_status}


@bp.route("/leagues")
def leagues():
    parsed = (
        select(
            Match.league_id.label("league_id"),
            func.count(distinct(Match.id)).label("parsed_matches"),
            func.max(Match.id).label("latest_parsed_match_id"),
        )
        .join(Ward, Ward.match_id == Match.id)
        .where(Match.league_id.is_not(None))
        .group_by(Match.league_id)
        .subquery()
    )
    rows = db.session.execute(
        select(League, parsed.c.parsed_matches, parsed.c.latest_parsed_match_id)
        .outerjoin(parsed, parsed.c.league_id == League.id)
        .order_by(parsed.c.latest_parsed_match_id.desc().nullslast(), League.id.desc())
    ).all()
    return {
        "data": [
            {
                "id": league.id,
                "name": league.name or f"League {league.id}",
                "version": league.map_asset_version,
                "tier": league.tier,
                "tracking_status": league.tracking_status,
                "parsed_matches": parsed_matches or 0,
                "latest_parsed_match_id": latest_parsed_match_id,
            }
            for league, parsed_matches, latest_parsed_match_id in rows
        ]
    }
