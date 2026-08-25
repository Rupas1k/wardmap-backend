from flask import Blueprint, request
from sqlalchemy import or_, select

from ..extensions import db
from ..models import Match, Team
from .wards import integer_list

bp = Blueprint("teams", __name__)


@bp.get("/teams")
def list_teams():
    league_ids = integer_list(request.args, "league_ids")
    query = (
        select(Team)
        .join(
            Match,
            or_(Match.radiant_team_id == Team.id, Match.dire_team_id == Team.id),
        )
        .distinct()
    )
    if league_ids:
        query = query.where(Match.league_id.in_(league_ids))
    search = request.args.get("q", "").strip()
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(Team.name.ilike(pattern), Team.tag.ilike(pattern)))
    teams = db.session.execute(query.order_by(Team.name, Team.id)).scalars().all()
    return {"data": [{"id": team.id, "name": team.name, "tag": team.tag, "logo_url": team.logo_url} for team in teams]}
