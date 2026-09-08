from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from ..domain import JobStatus
from ..extensions import db
from ..models import League, Match, ReplayJob, Ward, players_matches


@dataclass(frozen=True)
class LeagueReparsePlan:
    league_ids: tuple[int, ...]
    match_ids: tuple[int, ...]
    ward_count: int


def plan_league_reparse(league_ids: tuple[int, ...]) -> LeagueReparsePlan:
    unique_ids = tuple(dict.fromkeys(league_ids))
    known_ids = set(db.session.execute(select(League.id).where(League.id.in_(unique_ids))).scalars().all())
    missing_ids = [league_id for league_id in unique_ids if league_id not in known_ids]
    if missing_ids:
        missing = ", ".join(map(str, missing_ids))
        raise ValueError(f"Unknown league IDs: {missing}")

    match_ids = tuple(
        db.session.execute(select(Match.id).where(Match.league_id.in_(unique_ids)).order_by(Match.id)).scalars()
    )
    ward_count = db.session.scalar(select(func.count()).select_from(Ward).where(Ward.match_id.in_(match_ids)))

    return LeagueReparsePlan(unique_ids, match_ids, ward_count or 0)


def queue_league_reparse(plan: LeagueReparsePlan) -> int:
    if not plan.match_ids:
        return 0

    processing_ids = tuple(
        db.session.execute(
            select(ReplayJob.match_id).where(
                ReplayJob.match_id.in_(plan.match_ids),
                ReplayJob.status == JobStatus.PROCESSING,
            )
        ).scalars()
    )
    if processing_ids:
        matches = ", ".join(map(str, processing_ids))
        raise ValueError(f"Cannot reparse while these matches are processing: {matches}")

    db.session.execute(delete(Ward).where(Ward.match_id.in_(plan.match_ids)))
    db.session.execute(delete(players_matches).where(players_matches.c.match_id.in_(plan.match_ids)))
    db.session.execute(delete(ReplayJob).where(ReplayJob.match_id.in_(plan.match_ids)))
    db.session.execute(delete(Match).where(Match.id.in_(plan.match_ids)))
    db.session.execute(insert(ReplayJob).values([{"match_id": match_id} for match_id in plan.match_ids]))
    db.session.commit()

    return len(plan.match_ids)
