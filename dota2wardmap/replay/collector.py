import logging
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from ..extensions import db
from ..integrations import opendota
from ..job_maintenance import cleanup_terminal_jobs
from ..lifecycle import install_shutdown_handlers
from ..domain import JobStatus
from ..models import League, Match, ReplayJob
from ..settings import get_settings
from ..team_metadata import refresh_stale_team_metadata

logger = logging.getLogger("dota2wardmap.replay.collector")


def sync_league(league_id: int, *, refresh_unparsed_jobs: bool = False) -> tuple[int, int]:
    league = db.session.get(League, league_id)
    if league is None or league.tier is None:
        league_info = opendota.get_league(league_id)
        if league_info is None:
            raise ValueError(f"League {league_id} was not found in OpenDota")
        if league is None:
            league = League(id=league_id, name=league_info.get("name"))
            db.session.add(league)
        else:
            league.name = league_info.get("name") or league.name
        league.tier = league_info.get("tier")

    match_records = opendota.get_league_matches(league_id)
    match_ids = {match["match_id"] for match in match_records if match.get("match_id") is not None}
    parsed_ids = set(db.session.execute(select(Match.id).where(Match.id.in_(match_ids))).scalars().all())
    existing_jobs = db.session.execute(
        select(ReplayJob).where(ReplayJob.match_id.in_(match_ids))
    ).scalars().all()
    existing_job_ids = {job.match_id for job in existing_jobs}
    queued_ids = match_ids - parsed_ids - existing_job_ids
    refreshed_ids: set[int] = set()
    if refresh_unparsed_jobs:
        for job in existing_jobs:
            if job.match_id in parsed_ids or job.status == JobStatus.PROCESSING:
                continue
            job.status = JobStatus.PENDING
            job.attempts = 0
            job.claimed_at = None
            job.completed_at = None
            job.last_error = None
            refreshed_ids.add(job.match_id)
    if queued_ids:
        db.session.execute(
            insert(ReplayJob).values([{"match_id": match_id} for match_id in queued_ids]).on_conflict_do_nothing()
        )
    now = datetime.now(UTC)
    match_times = [
        datetime.fromtimestamp(match["start_time"], UTC)
        for match in match_records
        if match.get("start_time") is not None
    ]
    if match_times:
        league.first_match_at = min(match_times)
        league.last_match_at = max(match_times)
    league.last_checked_at = now
    if queued_ids or refreshed_ids:
        league.consecutive_empty_checks = 0
        league.next_check_at = now + timedelta(minutes=5)
    else:
        league.consecutive_empty_checks += 1
        if league.consecutive_empty_checks >= 10:
            delay = timedelta(hours=6)
        elif league.consecutive_empty_checks >= 3:
            delay = timedelta(hours=1)
        else:
            delay = timedelta(minutes=15)
        league.next_check_at = now + delay

    db.session.commit()
    return len(queued_ids | refreshed_ids), len(match_ids)


def refresh_missing_league_metadata() -> int:
    leagues = db.session.execute(select(League).where(League.tier.is_(None))).scalars().all()
    updated = 0
    for league in leagues:
        try:
            league_info = opendota.get_league(league.id)
            if league_info is None:
                continue
            league.name = league_info.get("name") or league.name
            league.tier = league_info.get("tier")
            db.session.commit()
            updated += 1
        except opendota.OpenDotaError:
            db.session.rollback()
            logger.exception("Unable to refresh metadata for league %s", league.id)
    return updated


def run_collector() -> None:
    shutdown = install_shutdown_handlers(logger)
    settings = get_settings()
    interval = settings.collector_interval_seconds
    cleanup_interval = settings.job_cleanup_interval_seconds
    next_cleanup = 0.0
    logger.info("League collector is ready; PostgreSQL tracking state is authoritative")
    refreshed = refresh_missing_league_metadata()
    logger.info("League metadata refresh complete: updated %s leagues", refreshed)
    teams_refreshed, team_failures = refresh_stale_team_metadata()
    logger.info(
        "Team metadata refresh complete: updated %s teams; %s failed",
        teams_refreshed,
        team_failures,
    )

    while not shutdown.is_set():
        if time.monotonic() >= next_cleanup:
            try:
                deleted = cleanup_terminal_jobs()
                logger.info("Queue cleanup complete: deleted %s terminal jobs", deleted)
            except Exception:
                db.session.rollback()
                logger.exception("Queue cleanup failed")
            next_cleanup = time.monotonic() + cleanup_interval

        now = datetime.now(UTC)
        league_ids = (
            db.session.execute(
                select(League.id)
                .where(
                    League.tracking_status == "active",
                    (League.next_check_at.is_(None)) | (League.next_check_at <= now),
                )
                .order_by(League.next_check_at.asc().nullsfirst(), League.id)
            )
            .scalars()
            .all()
        )
        if league_ids:
            logger.info("Due league checks: %s", ", ".join(map(str, league_ids)))
        for league_id in league_ids:
            if shutdown.is_set():
                break
            try:
                queued, total = sync_league(league_id)
                logger.info("League %s: queued %s of %s matches", league_id, queued, total)
            except (opendota.OpenDotaError, ValueError):
                db.session.rollback()
                logger.exception("Unable to synchronize league %s", league_id)
        shutdown.wait(interval)


def main() -> None:
    from .. import create_worker_app

    app = create_worker_app()
    with app.app_context():
        run_collector()


if __name__ == "__main__":
    main()
