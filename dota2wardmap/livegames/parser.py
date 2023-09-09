import sqlalchemy as sa
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


@scheduler.task('interval', id='do_job_1', seconds=300)
def parse():
    with scheduler.app.app_context():
        print('Task is running')
        live_games = api.fetch_live_games(LIVE_MATCHES_STEP, MMR_THRESHOLD)
        ids = set([match['matchId'] for match in live_games])

        db_ids = set(db.session.execute(select(Matches.id).filter(Matches.id.in_(ids))).scalars())

        work_queue.add(ids - db_ids)

        print(f'{len(live_games)} games added to work queue {len(ids)}')
        print(f'{len(work_queue._queue)} wq length')

