import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.cluster import HDBSCAN

import sqlalchemy as sa
from sqlalchemy import select
from flask import Blueprint, Response, request
from sqlalchemy.dialects.postgresql import insert

from models import Wards, Matches
from definitions import db, redis_store

bp = Blueprint('views', __name__)

pd.set_option('display.max_columns', None)


@bp.route('/plots')
def plots():
    data = redis_store.lrange('raw_clusters', 0, -1)
    for cluster in data:
        df = pd.DataFrame(json.loads(cluster))
        plt.scatter(x=df['x_pos'].mean(), y=df['y_pos'].mean(), s=1)
        # print(df)
    plt.show()

    response = Response()
    response.headers['Content-type'] = 'Application/json'
    return response


@bp.route('/process_clusters')
def process_clusters():
    raw_clusters = [json.loads(raw_cluster) for raw_cluster in redis_store.lrange('raw_clusters', 0, -1)]
    data = []
    for cluster_id, cluster_data in enumerate(raw_clusters):
        for record in cluster_data:
            data.append({'cluster_id': cluster_id, **record})
    df = pd.DataFrame(data)

    agg_functions = {
        'x_pos': 'mean',
        'y_pos': 'mean',
        'z_pos': lambda x: x.mode().iloc[0], #- 16384,
        'average_rank': 'mean',
        'duration': 'mean',
        'time_placed': 'mean',
        'is_radiant': lambda x: "{:.2%}".format(x.mean())
    }

    # df['average_rank'] = df['average_rank'].replace([np.nan, np.inf, -np.inf], -1).astype(int)

    group_sizes = df.groupby('cluster_id').size().reset_index(name='amount')
    result_df = (
        df.groupby('cluster_id')
        .agg(agg_functions)
        .round()
        .astype({'x_pos': int, 'y_pos': int, 'duration': int, 'z_pos': int, 'time_placed': int})
        .merge(group_sizes, on='cluster_id', how='inner')
    )

    redis_store.delete('clusters')
    for cluster in result_df.to_dict(orient='records'):
        redis_store.rpush('clusters', json.dumps(cluster))

    response = Response()
    response.headers['Content-type'] = 'Application/json'
    return response


@bp.route('/clusters')
def clusters():
    data = db.session.execute(
        select(Wards.duration, Wards.x_pos, Wards.y_pos, Wards.z_pos, Wards.is_radiant, Wards.is_destroyed,
               Wards.time_placed, Wards.radiant_networth, Wards.dire_networth, Matches.average_rank,
               Matches.game_version).join(Matches).where(
            sa.and_(Wards.is_obs)).order_by(Wards.id.desc()).limit(100000)).all()
    df = pd.DataFrame(data)
    hdbscan = HDBSCAN(
        cluster_selection_epsilon=32,
        min_samples=50,
        min_cluster_size=30,
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
        # print(len(redis_store.lrange('replays', 0, -1)))
    except:
        import traceback
        traceback.print_exc()
        redis_store.rpush('replays', redis_store.lpop('replays'))
    return Response()
