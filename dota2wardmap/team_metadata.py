import logging
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select

from .extensions import db
from .integrations import opendota
from .models import Team

logger = logging.getLogger(__name__)


def refresh_stale_team_metadata(
    max_age_days: int = 30,
    limit: int | None = None,
    *,
    missing_only: bool = False,
    request_delay_seconds: float = 1.1,
) -> tuple[int, int]:
    cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
    query = select(Team)
    if missing_only:
        query = query.where(or_(Team.name.is_(None), Team.name == ""))
    else:
        query = query.where(or_(Team.metadata_updated_at.is_(None), Team.metadata_updated_at < cutoff))
    query = query.order_by(Team.metadata_updated_at.asc().nullsfirst(), Team.id)
    if limit is not None:
        query = query.limit(limit)

    teams = db.session.execute(query).scalars().all()
    updated = 0
    failed = 0
    for team in teams:
        try:
            team_data = opendota.get_team(team.id)
            if team_data is None:
                failed += 1
                continue
            team.name = team_data.get("name") or team.name
            team.tag = team_data.get("tag") or team.tag
            team.logo_url = team_data.get("logo_url") or team.logo_url
            team.metadata_updated_at = datetime.now(UTC)
            db.session.commit()
            updated += 1
            time.sleep(request_delay_seconds)
        except opendota.OpenDotaError:
            db.session.rollback()
            failed += 1
            logger.exception("Unable to refresh metadata for team %s", team.id)
            time.sleep(max(5, request_delay_seconds))
    return updated, failed
