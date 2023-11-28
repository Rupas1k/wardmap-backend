import json

from sqlalchemy import select
from flask import Blueprint

import api
from models import Matches
from extensions import db, scheduler, redis_store


bp = Blueprint('parser', __name__)

LIVE_MATCHES_STEP = 50
MMR_THRESHOLD = 8000


@scheduler.task('interval', id='parser', seconds=600)
def parse():
    with scheduler.app.app_context():
        print('Task is running')

        live_games = api.fetch_live_games(LIVE_MATCHES_STEP, MMR_THRESHOLD)
        matches = dict((match['matchId'], match) for match in live_games)
        ids = set(list(matches.keys()))

        db_ids = set(db.session.execute(select(Matches.id).filter(Matches.id.in_(ids))).scalars().all())
        redis_ids = set(int(replay) for replay in redis_store.lrange('replays', 0, -1))

        print(set(db.session.execute(select(Matches.id).filter(Matches.id.in_(redis_ids))).scalars().all()))

        to_add = list(match_id for match_id in matches if matches[match_id]['matchId'] in ids - db_ids - redis_ids)

        for replay in to_add:
            redis_store.rpush('replays', replay)

        print(f'{len(live_games)} games added to work queue {len(ids)}')
        print(f'{len(redis_store.lrange("replays", 0, -1))} wq length')
