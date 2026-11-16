import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from ..domain import JobStatus
from ..extensions import db
from ..integrations import dota_gc, opendota
from ..job_maintenance import cleanup_terminal_jobs
from ..lifecycle import install_shutdown_handlers
from ..models import League, Match, ReplayJob, TrackedPlayer
from ..settings import get_settings
from ..team_metadata import refresh_stale_team_metadata

logger = logging.getLogger("dota2wardmap.replay.collector")


@dataclass(frozen=True)
class PlayerSyncResult:
    matches: int
    queued: int
    parsed: int
    pending: int
    unavailable: int
    failed: int
    history: list[dict[str, int | str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def sync_player(account_id: int) -> PlayerSyncResult:
    tracked = db.session.get(TrackedPlayer, account_id)
    if tracked is None:
        raise ValueError(f"Player {account_id} is not tracked")

    match_ids = set(dota_gc.get_player_matches(account_id))
    parsed_ids = set(db.session.execute(select(Match.id).where(Match.id.in_(match_ids))).scalars().all())
    existing_jobs = db.session.execute(select(ReplayJob).where(ReplayJob.match_id.in_(match_ids))).scalars().all()
    existing_job_ids = {job.match_id for job in existing_jobs}
    queued_ids = match_ids - parsed_ids - existing_job_ids

    if queued_ids:
        db.session.execute(
            insert(ReplayJob).values([{"match_id": match_id} for match_id in queued_ids]).on_conflict_do_nothing()
        )

    now = datetime.now(UTC)
    tracked.last_match_id = max(match_ids, default=tracked.last_match_id)
    tracked.last_checked_at = now
    tracked.last_error = None

    if queued_ids:
        tracked.consecutive_empty_checks = 0
        tracked.next_check_at = now + timedelta(minutes=5)
    else:
        tracked.consecutive_empty_checks += 1
        delay = timedelta(hours=1) if tracked.consecutive_empty_checks >= 3 else timedelta(minutes=15)
        tracked.next_check_at = now + delay

    db.session.commit()

    unparsed_jobs = [job for job in existing_jobs if job.match_id not in parsed_ids]
    unavailable = sum(
        job.status == JobStatus.FAILED and job.last_error == "Replay could not be downloaded"
        for job in unparsed_jobs
    )
    failed = sum(
        job.status == JobStatus.FAILED and job.last_error != "Replay could not be downloaded"
        for job in unparsed_jobs
    )
    pending = len(unparsed_jobs) - unavailable - failed
    jobs_by_match_id = {job.match_id: job for job in existing_jobs}
    history = []
    for match_id in sorted(match_ids, reverse=True):
        job = jobs_by_match_id.get(match_id)
        if job is not None and job.status in (JobStatus.PENDING, JobStatus.PROCESSING):
            status = job.status
        elif match_id in parsed_ids:
            status = "parsed"
        elif match_id in queued_ids or job is None:
            status = "queued"
        elif job.status == JobStatus.FAILED and job.last_error == "Replay could not be downloaded":
            status = "unavailable"
        else:
            status = job.status

        history.append({"match_id": match_id, "status": status})

    return PlayerSyncResult(
        matches=len(match_ids),
        queued=len(queued_ids),
        parsed=len(parsed_ids),
        pending=pending,
        unavailable=unavailable,
        failed=failed,
        history=history,
    )


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
    existing_jobs = db.session.execute(select(ReplayJob).where(ReplayJob.match_id.in_(match_ids))).scalars().all()
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
            job.next_attempt_at = None
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
        player_ids = (
            db.session.execute(
                select(TrackedPlayer.account_id)
                .where(
                    TrackedPlayer.tracking_status == "active",
                    (TrackedPlayer.next_check_at.is_(None)) | (TrackedPlayer.next_check_at <= now),
                )
                .order_by(TrackedPlayer.next_check_at.asc().nullsfirst(), TrackedPlayer.account_id)
            )
            .scalars()
            .all()
        )
        for account_id in player_ids:
            if shutdown.is_set():
                break
            try:
                result = sync_player(account_id)
                logger.info(
                    "Player %s: queued %s of %s recent matches; %s parsed, %s unavailable",
                    account_id,
                    result.queued,
                    result.matches,
                    result.parsed,
                    result.unavailable,
                )
            except (dota_gc.DotaGCError, ValueError) as exc:
                db.session.rollback()
                tracked = db.session.get(TrackedPlayer, account_id)
                if tracked is not None:
                    tracked.last_checked_at = now
                    tracked.next_check_at = now + timedelta(minutes=15)
                    tracked.last_error = str(exc)[:512]
                    db.session.commit()
                logger.exception("Unable to synchronize player %s", account_id)

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
