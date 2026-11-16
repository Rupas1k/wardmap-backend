from datetime import UTC, datetime

from flask import Blueprint, request
from sqlalchemy import String, and_, case, exists, func, or_, select
from werkzeug.exceptions import BadRequest, Forbidden, ServiceUnavailable

from ..access import require_access
from ..domain import AccessLevel
from ..extensions import db
from ..integrations import dota_gc
from ..models import Match, Player, TrackedPlayer, Ward, players_matches
from ..replay.collector import sync_player
from .wards import integer_list

bp = Blueprint("players", __name__)


def _tracked_player_payload(tracked: TrackedPlayer) -> dict[str, object]:
    return {
        "account_id": tracked.account_id,
        "tracking_status": tracked.tracking_status,
        "last_match_id": tracked.last_match_id,
        "last_checked_at": tracked.last_checked_at.isoformat() if tracked.last_checked_at else None,
        "next_check_at": tracked.next_check_at.isoformat() if tracked.next_check_at else None,
        "last_error": tracked.last_error,
    }


@bp.get("/tracked-players")
@require_access(AccessLevel.ADMIN)
def list_tracked_players():
    tracked = db.session.execute(select(TrackedPlayer).order_by(TrackedPlayer.account_id)).scalars().all()

    return {"data": [_tracked_player_payload(player) for player in tracked]}


@bp.put("/tracked-players/<int:account_id>")
@require_access(AccessLevel.ADMIN)
def update_tracked_player(account_id: int):
    if account_id <= 0 or account_id > 0xFFFFFFFF:
        raise BadRequest("account ID must be an unsigned 32-bit integer")

    body = request.get_json(silent=True) or {}
    status = body.get("status", "active") if isinstance(body, dict) else None
    if status not in ("active", "paused"):
        raise BadRequest("status must be active or paused")

    if status == "active":
        try:
            authenticated_account_id = dota_gc.get_account_id()
        except dota_gc.DotaGCError as exc:
            raise ServiceUnavailable("Dota Game Coordinator is temporarily unavailable") from exc
        if account_id != authenticated_account_id:
            raise Forbidden("only the authenticated Steam account can be tracked")

    player = db.session.get(Player, account_id)
    if player is None:
        db.session.add(Player(id=account_id))

    tracked = db.session.get(TrackedPlayer, account_id)
    if tracked is None:
        tracked = TrackedPlayer(account_id)
        db.session.add(tracked)

    tracked.tracking_status = status
    tracked.next_check_at = datetime.now(UTC) if status == "active" else None
    tracked.consecutive_empty_checks = 0
    tracked.last_error = None
    db.session.commit()

    return _tracked_player_payload(tracked)


@bp.post("/tracked-players/<int:account_id>/sync")
@require_access(AccessLevel.ADMIN)
def synchronize_tracked_player(account_id: int):
    if account_id <= 0 or account_id > 0xFFFFFFFF:
        raise BadRequest("account ID must be an unsigned 32-bit integer")

    tracked = db.session.get(TrackedPlayer, account_id)
    if tracked is None:
        try:
            authenticated_account_id = dota_gc.get_account_id()
        except dota_gc.DotaGCError as exc:
            raise ServiceUnavailable("Dota Game Coordinator is temporarily unavailable") from exc
        if account_id != authenticated_account_id:
            raise Forbidden("only the authenticated Steam account can be tracked")

        if db.session.get(Player, account_id) is None:
            db.session.add(Player(id=account_id))
        tracked = TrackedPlayer(account_id)
        db.session.add(tracked)
        db.session.flush()

    tracked.tracking_status = "active"

    try:
        result = sync_player(account_id)
    except ValueError as exc:
        raise BadRequest(str(exc)) from exc
    except dota_gc.DotaGCError:
        db.session.rollback()
        return {"error": "Dota Game Coordinator is temporarily unavailable"}, 502

    return result.to_dict()


@bp.get("/players")
def list_players():
    league_ids = integer_list(request.args, "league_ids")
    team_ids = integer_list(request.args, "team_ids")
    role = request.args.get("role", "participant")

    query = _ward_placers_query(league_ids, team_ids) if role == "placer" else _participants_query(league_ids, team_ids)

    search = request.args.get("q", "").strip()
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(Player.name.ilike(pattern), Player.id.cast(String).ilike(pattern)))

    players = db.session.execute(query.order_by(query.selected_columns.ward_count.desc(), Player.name, Player.id)).all()

    return {"data": [{"id": player.id, "name": player.name, "ward_count": player.ward_count} for player in players]}


def _ward_placers_query(league_ids: list[int], team_ids: list[int]):
    ward_count = func.count(case((Ward.is_obs.is_(True), Ward.id))).label("ward_count")
    placing_team_id = case(
        (Ward.is_radiant.is_(True), Match.radiant_team_id),
        (Ward.is_radiant.is_(False), Match.dire_team_id),
    )
    query = (
        select(Player.id, Player.name, ward_count)
        .join(Ward, Ward.player_placed_id == Player.id)
        .join(Match, Match.id == Ward.match_id)
        .group_by(Player.id, Player.name)
    )

    if league_ids:
        query = query.where(Match.league_id.in_(league_ids))
    if team_ids:
        query = query.where(placing_team_id.in_(team_ids))

    return query


def _participants_query(league_ids: list[int], team_ids: list[int]):
    ward_count = func.count(Ward.id).label("ward_count")
    participation = (
        select(
            players_matches.c.player_id.label("player_id"),
            players_matches.c.match_id.label("match_id"),
            players_matches.c.is_radiant.label("is_radiant"),
        )
        .union(
            select(Ward.player_placed_id, Ward.match_id, Ward.is_radiant).where(
                Ward.player_placed_id.is_not(None),
                ~exists(
                    select(1).where(
                        players_matches.c.match_id == Ward.match_id,
                        players_matches.c.player_id == Ward.player_placed_id,
                    )
                ),
            )
        )
        .subquery()
    )
    participant_team_id = case(
        (participation.c.is_radiant.is_(True), Match.radiant_team_id),
        (participation.c.is_radiant.is_(False), Match.dire_team_id),
    )
    query = (
        select(Player.id, Player.name, ward_count)
        .join(participation, participation.c.player_id == Player.id)
        .join(Match, Match.id == participation.c.match_id)
        .outerjoin(
            Ward,
            and_(
                Ward.match_id == Match.id,
                Ward.player_placed_id == Player.id,
                Ward.is_obs.is_(True),
            ),
        )
        .group_by(Player.id, Player.name)
    )
    if league_ids:
        query = query.where(Match.league_id.in_(league_ids))
    if team_ids:
        query = query.where(participant_team_id.in_(team_ids))

    return query
