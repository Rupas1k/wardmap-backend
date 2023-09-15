import json
from sqlalchemy import select
from flask import Blueprint

import api
from models import db, Matches

from definitions import scheduler, redis_store


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

        db_ids = set(db.session.execute(select(Matches.id).filter(Matches.id.in_(ids))).scalars())
        redis_ids = set(int(json.loads(replay)['matchId']) for replay in redis_store.lrange('replays', 0, -1))

        to_add = list(matches[match_id] for match_id in matches if matches[match_id]['matchId'] in ids - db_ids - redis_ids)

        for replay in to_add:
            redis_store.rpush('replays', json.dumps(replay))

        print(f'{len(live_games)} games added to work queue {len(ids)}')
        print(f'{len(redis_store.lrange("replays", 0, -1))} wq length')
