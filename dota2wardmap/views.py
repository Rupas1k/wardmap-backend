import os
import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.cluster import HDBSCAN

import sqlalchemy as sa
from sqlalchemy import select
from flask import Blueprint, Response, request
from sqlalchemy.dialects.postgresql import insert

import api
from models import Wards, Matches, Leagues
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


@bp.route('/clusters')
def clusters():
    query = select(
        Wards.duration, Wards.x_pos, Wards.y_pos, Wards.z_pos, Wards.is_radiant, Wards.is_destroyed,
        Wards.time_placed, Wards.radiant_networth, Wards.dire_networth,
        Matches.game_version
    ).join(Matches).where(sa.and_(Wards.is_obs, Wards.is_post_game == False)).order_by(Wards.id.desc()).limit(int(os.environ['AMOUNT']))

    # subquery = (
    #     select(Matches.id)
    #     .order_by(Matches.id.desc())
    #     .limit(7000)
    # )
    #
    # query = (
    #     select(
    #         Wards.duration, Wards.x_pos, Wards.y_pos, Wards.z_pos, Wards.is_radiant, Wards.is_destroyed,
    #         Wards.time_placed, Wards.radiant_networth, Wards.dire_networth,
    #         Matches.game_version
    #     )
    #     .join(Matches)
    #     .where(sa.and_(Wards.is_obs))
    #     .where(Matches.id.in_(select(subquery)))
    #     .order_by(Wards.id.desc())
    # )

    data = db.session.execute(query).all()
    df = pd.DataFrame(data)

    hdbscan = HDBSCAN(
        cluster_selection_epsilon=int(os.environ['CLUSTER_SELECTION_EPSILON']),
        min_samples=int(os.environ['MIN_SAMPLES']),
        min_cluster_size=int(os.environ['MIN_CLUSTER_SIZE']),
        max_cluster_size=int(os.environ['MAX_CLUSTER_SIZE']),
        cluster_selection_method=os.environ['CLUSTER_SELECTION_METHOD'],
        n_jobs=int(os.environ['N_JOBS']),
    )

    hdbscan.fit(df[['x_pos', 'y_pos']])
    unique = np.unique(hdbscan.labels_[hdbscan.labels_ != -1])

    raw_clusters = [
        df.iloc[np.argwhere(hdbscan.labels_ == label).ravel()].to_dict(orient='records')
        for label in unique
    ]

    data = [
        {'cluster_id': cluster_id, **record}
        for cluster_id, cluster_data in enumerate(raw_clusters)
        for record in cluster_data
    ]

    df = pd.DataFrame(data)

    agg_functions = {
        'x_pos': 'mean',
        'y_pos': 'mean',
        'z_pos': lambda x: x.mode().iloc[0], #- 16384,
        'duration': 'mean',
        'time_placed': 'mean',
        'radiant_networth': 'mean',
        'dire_networth': 'mean',
        'is_radiant': 'sum',
        'is_destroyed': 'sum'
    }


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


@bp.route('/get_wards')
def send_wards():
    data = json.dumps([row._asdict() for row in db.session.execute(
        select(Wards.id, Wards.x_pos, Wards.y_pos, Wards.z_pos, Wards.duration, Wards.time_placed).where(
            Wards.is_obs == True).order_by(Wards.id.desc()).limit(50000)).all()])
    response = Response(data)
    response.headers['Content-type'] = 'Application/json'
    return response

@bp.route('/get_clusters')
def send_clusters():
    data = redis_store.lrange('clusters', 0, -1)
    response = Response(data)
    response.headers['Content-type'] = 'Application/json'
    return response

@bp.route('/get_task')
def send_task():
    response = Response(redis_store.lindex('replays', 0) or '')
    response.headers['Content-type'] = 'Application/json'
    return response

@bp.route('/queue_league/<league_id>')
def queue_league(league_id):
    db_ids = set(db.session.execute(select(Matches.id, Matches.league_id).filter(Matches.league_id == int(league_id))).scalars().all())
    redis_ids = set(int(replay) for replay in redis_store.lrange('replays', 0, -1))
    matches = {match['id'] for match in api.fetch_league_games(int(league_id))}
    for match_id in matches - db_ids - redis_ids:
        redis_store.rpush('replays', match_id)
    response = Response()
    return response

@bp.route('/send_ward_data/<match_id>', methods=['POST'])
def receive_ward_data(match_id):
    if 'skip' in request.get_json(force=True):
        redis_store.rpush('replays', redis_store.lpop('replays'))
        return Response()

    try:
        match_id = redis_store.lindex('replays', 0)
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
        if match_data['league'] is not None:
            if not db.session.query(Leagues).filter(Leagues.id == int(match_data['league'])).first():
                db.session.execute(insert(Leagues).values(id=int(match_data['league'])))

        if not db.session.query(Matches).filter(Matches.id == match_id).first():
            db.session.execute(insert(Matches).values(id=match_id,
                                                      league_id=match_data['league'],
                                                      game_version=match_data['version'],
                                                      date=match_data['date'],
                                                      region=match_data['region'],
                                                      duration=match_data['duration']))
            db.session.execute(insert(Wards).values(wards))
        else:
            print(f'{match_id} is already parsed')
        db.session.commit()
        redis_store.lpop('replays')
    except:
        import traceback
        traceback.print_exc()
        redis_store.rpush('replays', redis_store.lpop('replays'))
        print(request.get_json(force=True))
    return Response()
