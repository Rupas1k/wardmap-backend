from sqlalchemy import select
from models import db, Matches
from flask import Blueprint
from flask_apscheduler import APScheduler
from views import work_queue

import api

bp = Blueprint('parser', __name__)
scheduler = APScheduler()

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

        to_add = dict((matches[match_id]['matchId'], matches[match_id]) for match_id in matches if matches[match_id]['matchId'] in ids - db_ids)

        work_queue.add(to_add)

        print(f'{len(live_games)} games added to work queue {len(ids)}')
        print(f'{len(work_queue.get())} wq length')
