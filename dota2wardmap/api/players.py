from flask import Blueprint, request
from sqlalchemy import String, and_, case, exists, func, or_, select

from ..extensions import db
from ..models import Match, Player, Ward, players_matches
from .wards import integer_list

bp = Blueprint("players", __name__)


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
