import json

import pandas as pd
import matplotlib.pyplot as plt

from sqlalchemy import select
from flask import Blueprint, Response, request
from sqlalchemy.dialects.postgresql import insert

import api
from models import Wards, Matches, Leagues, Players
from definitions import db, redis_store
from main import perform_clustering

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
    perform_clustering(**request.args)

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
    metadata = redis_store.get('metadata')
    response = Response(json.dumps({
        # 'metadata': metadata,
        'data': data
    }))
    response.headers['Content-type'] = 'Application/json'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

@bp.route('/get_task')
def send_task():
    # response = Response(redis_store.lindex('replays', 0) or '')
    response = Response(redis_store.lpop('replays') or '')
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

@bp.route('/parse_league_players/<league_id>')
def parse_league_players(league_id):
    db_ids = set(db.session.execute(select(Players.id)).scalars().all())
    players = api.fetch_league_players(int(league_id))
    for player in players:
        if player['id'] not in db_ids:
            db.session.execute(insert(Players).values({
                'id': player['id'],
                'name': player['name']
            }))
    db.session.commit()

@bp.route('/send_ward_data/<match_id>', methods=['POST'])
def receive_ward_data(match_id):
    if 'skip' in request.get_json(force=True):
        return Response()

    try:
        match_id = int(match_id)
        data = request.get_json(force=True)
        match_data = data.pop(0)
        wards = []
        for ward_data in data:
            if ward_data['event'] == 'expired' or 'guys' in ward_data['npc_killed']:
                ward_data['playerDestroyedSteamId'] = None

            if 'playerPlacedSteamId' not in ward_data:
                ward_data['playerPlacedSteamId'] = None
            else:
                ward_data['playerPlacedSteamId'] = ward_data['playerPlacedSteamId'] - 76561197960265728

            if 'playerDestroyedSteamId' not in ward_data:
                ward_data['playerDestroyedSteamId'] = ward_data['playerDestroyedSteamId'] - 76561197960265728

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
    except:
        import traceback
        traceback.print_exc()
        print(request.get_json(force=True))
    return Response()
