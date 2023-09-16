import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.cluster import HDBSCAN

import sqlalchemy as sa
from sqlalchemy import select
from flask import Blueprint, Response, request
from sqlalchemy.dialects.postgresql import insert

from models import db, Wards, Matches
from definitions import redis_store

bp = Blueprint('views', __name__)


@bp.route('/clusters')
def clusters():
    data = db.session.execute(
        select(Wards.duration, Wards.x_pos, Wards.y_pos, Wards.z_pos, Wards.is_radiant, Wards.is_destroyed,
               Wards.time_placed, Wards.radiant_networth, Wards.dire_networth, Matches.average_rank,
               Matches.game_version).join(Matches).where(
            sa.and_(Wards.is_obs)).order_by(Wards.id.desc()).limit(100000)).all()
    df = pd.DataFrame(data)
    hdbscan = HDBSCAN(
        min_samples=100,
        cluster_selection_epsilon=32,
        max_cluster_size=100000,
        cluster_selection_method='leaf',
        n_jobs=-1,
    )
    hdbscan.fit(df[['x_pos', 'y_pos']])
    labels = hdbscan.labels_
    unique = np.unique(hdbscan.labels_[hdbscan.labels_ != -1])

    redis_store.delete('raw_clusters')
    for label in unique:
        label_arg = np.argwhere(labels == label).ravel()
        cluster = df.iloc[label_arg]
        redis_store.rpush('raw_clusters', cluster.to_json(orient='records'))

    response = Response(
        json.dumps([row._asdict() for row in data])
    )
    response.headers['Content-type'] = 'Application/json'
    return response


@bp.route('/get_task')
def send_task():
    response = Response(redis_store.lindex('replays', 0) or json.dumps([]))
    response.headers['Content-type'] = 'Application/json'
    return response


@bp.route('/send_ward_data/<match_id>', methods=['POST'])
def receive_ward_data(match_id):
    try:
        match_id = int(json.loads(redis_store.lrange('replays', 0, 0)[0])['matchId'])
        average_rank = int(json.loads(redis_store.lrange('replays', 0, 0)[0])['averageRank'])
        data = request.get_json(force=True)
        match_data = data.pop(0)
        wards = []
        for ward_data in data:
            if ward_data['event'] == 'expired' or 'guys' in ward_data['npc_killed']:
                ward_data['playerDestroyedSteamId'] = None
            if 'playerPlacedSteamId' not in ward_data:
                ward_data['playerPlacedSteamId'] = None
            if 'playerDestroyedSteamId' not in ward_data:
                ward_data['playerDestroyedSteamId'] = None
            if 'isRadiant' not in ward_data:
                ward_data['isRadiant'] = None
            ward = {
                'match_id': match_id,
                'is_obs': ward_data['isObs'],
                'is_radiant': ward_data['isRadiant'],
                'is_destroyed': ward_data['event'] == 'killed',
                'is_post_game': ward_data['postGame'],
                'player_placed_id': ward_data['playerPlacedSteamId'],
                'player_destroyed_id': ward_data['playerDestroyedSteamId'],
                'time_placed': ward_data['timePlaced'],
                'duration': ward_data['duration'],
                'x_pos': ward_data['x'] * 128 + round(ward_data['vec_x']),
                'y_pos': ward_data['y'] * 128 + round(ward_data['vec_y']),
                'z_pos': ward_data['z'] * 128 + round(ward_data['vec_z']),
                'radiant_networth': ward_data['radiantNetworth'],
                'dire_networth': ward_data['direNetworth'],
            }
            wards.append(ward)
        db.session.execute(insert(Matches).values(id=match_id,
                                                  average_rank=average_rank,
                                                  league_id=match_data['league'],
                                                  tournament_id=match_data['tournament'],
                                                  game_version=match_data['version'],
                                                  date=match_data['date'],
                                                  region=match_data['region'],
                                                  duration=match_data['duration']))
        db.session.execute(insert(Wards).values(wards))
        db.session.commit()
        redis_store.lpop('replays')
        print(len(redis_store.lrange('replays', 0, -1)))
    except:
        import traceback
        traceback.print_exc()
        redis_store.rpush('replays', redis_store.lpop('replays'))
    return Response()
