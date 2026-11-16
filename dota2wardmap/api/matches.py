from datetime import UTC, datetime

from flask import Blueprint, current_app, request
from sqlalchemy import distinct, func, select
from werkzeug.exceptions import BadRequest, NotFound

from ..access import require_access
from ..domain import REPLAY_DELETED_ERROR, AccessLevel, JobStatus
from ..extensions import db
from ..integrations import opendota
from ..models import League, Match, Player, ReplayJob, Ward, players_matches
from ..replay.collector import sync_league
from .wards import ward_evidence_payload, ward_query, ward_response

bp = Blueprint("matches", __name__)


@bp.post("/matches/status")
@require_access(AccessLevel.ADMIN)
def match_statuses():
    body = request.get_json(silent=True) or {}
    match_ids = body.get("match_ids") if isinstance(body, dict) else None
    if not isinstance(match_ids, list) or not all(isinstance(match_id, int) for match_id in match_ids):
        raise BadRequest("match_ids must be an array of numeric IDs")
    if len(match_ids) > 100:
        raise BadRequest("match_ids cannot contain more than 100 IDs")

    parsed_ids = set(db.session.execute(select(Match.id).where(Match.id.in_(match_ids))).scalars().all())
    jobs = db.session.execute(select(ReplayJob).where(ReplayJob.match_id.in_(match_ids))).scalars().all()
    jobs_by_match_id = {job.match_id: job for job in jobs}
    history = []

    for match_id in match_ids:
        job = jobs_by_match_id.get(match_id)
        if job is not None and job.status in (JobStatus.PENDING, JobStatus.PROCESSING):
            status = job.status
        elif match_id in parsed_ids:
            status = "parsed"
        elif job is None:
            status = "queued"
        elif job.status == JobStatus.FAILED and job.last_error == REPLAY_DELETED_ERROR:
            status = "unavailable"
        else:
            status = job.status
        history.append({"match_id": match_id, "status": status})

    return {"history": history}


@bp.get("/matches/<int:match_id>/library")
@require_access(AccessLevel.ADMIN)
def library_match(match_id: int):
    match = db.session.get(Match, match_id)
    if match is None:
        raise NotFound(f"Match {match_id} has not been parsed")

    query, _, _, _ = ward_query()
    ward_rows = db.session.execute(query.where(Ward.match_id == match_id).order_by(Ward.id)).all()
    player_rows = db.session.execute(
        select(Player.id, Player.name, players_matches.c.is_radiant, players_matches.c.hero_name)
        .join(players_matches, players_matches.c.player_id == Player.id)
        .where(
            players_matches.c.match_id == match_id,
            players_matches.c.is_radiant.is_not(None),
        )
        .order_by(Player.id)
    ).all()

    map_version = match.league.map_asset_version if match.league is not None else 2
    wards = []
    for row in ward_rows:
        payload = ward_response(row)
        ward = db.session.get(Ward, payload["id"])
        if ward is not None:
            payload["measurement"]["sightings"] = ward_evidence_payload(ward)["sightings"]
        wards.append(payload)

    return {
        "library_revision": 2,
        "match_id": match.id,
        "map_version": map_version,
        "started_at": int(match.started_at.timestamp() * 1000) if match.started_at else None,
        "duration": match.duration,
        "radiant_won": match.radiant_win,
        "players": [
            {
                "id": player_id,
                "name": player_name or f"Player {player_id}",
                "is_radiant": is_radiant,
                "hero": hero_name,
            }
            for player_id, player_name, is_radiant, hero_name in player_rows
        ],
        "wards": wards,
    }


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
