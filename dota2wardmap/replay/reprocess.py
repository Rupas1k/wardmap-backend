import argparse
import logging

from sqlalchemy import select

from .. import create_worker_app
from ..extensions import db
from ..models import Match, Ward
from .download import get_replay
from .parser import parse_wards
from .persistence import persist_parsed_replay

logger = logging.getLogger(__name__)


def reprocess_league(league_id: int) -> int:
    match_ids = db.session.execute(
        select(Match.id).where(Match.league_id == league_id).order_by(Match.id)
    ).scalars().all()
    failed = 0

    for index, match_id in enumerate(match_ids, 1):
        current = db.session.execute(
            select(Ward.measurement_version, Ward.measurement_revision).where(Ward.match_id == match_id)
        ).all()
        if current and all(version == 2 and revision == 1 for version, revision in current):
            logger.info("[%s/%s] Match %s already processed", index, len(match_ids), match_id)
            continue

        downloaded = get_replay(match_id)
        if downloaded is None:
            failed += 1
            logger.error("[%s/%s] Match %s could not be downloaded", index, len(match_ids), match_id)
            continue

        replay, match_data = downloaded
        try:
            wards = parse_wards(replay)
            if not persist_parsed_replay((match_id, match_data, wards)):
                raise RuntimeError("persistence rejected parsed replay")
        except Exception:
            failed += 1
            logger.exception("[%s/%s] Match %s failed", index, len(match_ids), match_id)
            continue

        logger.info("[%s/%s] Match %s updated (%s wards)", index, len(match_ids), match_id, len(wards))

    logger.info("Reprocess finished: %s matches, %s failures", len(match_ids), failed)

    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("league_id", type=int)
    args = parser.parse_args()
    app = create_worker_app()

    with app.app_context():
        return reprocess_league(args.league_id)


if __name__ == "__main__":
    raise SystemExit(main())
