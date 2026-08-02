import json

import sqlalchemy as sa
from sqlalchemy import select
from flask import Blueprint, Response, request
from sqlalchemy.dialects.postgresql import insert

import api
from models import Wards, Matches, Leagues, Players, Maps
from extensions import db, redis_store
from main import perform_clustering

bp = Blueprint('views', __name__)


@bp.route('/clusters')
def clusters():
    clustered = perform_clustering(**request.args)

    default_values = {
        'cluster_selection_epsilon': 64,
        'min_samples': 10,
        'min_cluster_size': 10,
        'cluster_selection_method': 'eom',
        'league_id': 15909,
        'public': False,
        'is_obs': True
    }

    values = {**default_values, **request.args}

    # league_map = db.session.execute(select(Maps, Leagues).join(Leagues).filter(Leagues.id == int(values['league_id']))).all()

    db.session.execute(insert(Maps).values(
        league_id=values['league_id'],
        cluster_selection_epsilon=values['cluster_selection_epsilon'],
        min_samples=values['min_samples'],
        min_cluster_size=values['min_cluster_size'],
        cluster_selection_method=values['cluster_selection_method'],
        version=int(redis_store.get('version')),
        is_obs=bool(int(values['is_obs']))
    ).on_conflict_do_update(
        constraint='maps_pkey',
        set_=dict(
            cluster_selection_epsilon=values['cluster_selection_epsilon'],
            min_samples=values['min_samples'],
            min_cluster_size=values['min_cluster_size'],
            cluster_selection_method=values['cluster_selection_method'],
            version=int(redis_store.get('version'))
        )
    ))

    redis_store.delete(f"{values['league_id']}-{values['is_obs']}")
    for cluster in clustered:
        redis_store.rpush(f"{values['league_id']}-{values['is_obs']}", json.dumps(cluster, allow_nan=False, default=int))

    db.session.commit()

    response = Response()
    response.headers['Content-type'] = 'Application/json'
    return response


@bp.route('/set_version/<int:version>')
def set_version(version):
    redis_store.set('version', version)
    return Response(version)


@bp.route('/get_version')
def get_version():
    return Response(redis_store.get('version'))


@bp.route('/get_wards')
def get_wards():
    data = json.dumps([row._asdict() for row in db.session.execute(
        select(Wards.id, Wards.x_pos, Wards.y_pos, Wards.z_pos, Wards.duration, Wards.time_placed).join(Matches).where(
            sa.and_(Wards.is_obs == True, Matches.league_id == 15910)).order_by(Wards.id.desc()).limit(50000)).all()])
    response = Response(data)
    response.headers['Content-type'] = 'Application/json'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@bp.route('/get_clusters/<int:league_id>/<int:is_obs>')
def get_clusters(league_id: int, is_obs: int):
    data = [json.loads(cluster) for cluster in redis_store.lrange(f"{league_id}-{is_obs}", 0, -1)]
    metadata = redis_store.get('metadata')
    response = Response(json.dumps({
        # 'metadata': metadata,
        'data': data
    }))
    response.headers['Content-type'] = 'Application/json'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

@bp.route('/get_task')
def get_task():
    response = Response(redis_store.lpop('replays') or '')
    response.headers['Content-type'] = 'Application/json'
    return response


@bp.route('/queue_league/<int:league_id>')
def queue_league(league_id: int):
    if not db.session.query(Leagues).filter(Leagues.id == league_id).first():
        league_info = api.fetch_league_info(league_id)
        db.session.add(Leagues(id=league_id, name=league_info['displayName']))
        parse_league_players(league_id)

    db_ids = set(db.session.execute(select(Matches.id, Matches.league_id).filter(Matches.league_id == league_id)).scalars().all())
    redis_ids = set(int(replay) for replay in redis_store.lrange('replays', 0, -1))
    matches = {match['id'] for match in api.fetch_league_games(league_id)}
    for match_id in matches - db_ids - redis_ids:
        redis_store.rpush('replays', match_id)
    response = Response()
    return response


@bp.route('/parse_league_players/<int:league_id>')
def parse_league_players(league_id: int):
    db_ids = set(db.session.execute(select(Players.id)).scalars().all())
    players = api.fetch_league_players(league_id)
    league = db.session.query(Leagues).filter(Leagues.id == league_id).first()
    for player in players:
        if player['id'] not in db_ids:
            new_player = Players(id=player['id'], name=player.get('name'))
            new_player.leagues.append(league)
            db.session.add(new_player)
        else:
            old_player = db.session.query(Players).filter(Players.id == int(player['id'])).first()
            old_player.leagues.append(league)
            db.session.add(old_player)
    db.session.commit()


@bp.route('/send_ward_data/<int:match_id>', methods=['POST'])
def get_ward_data(match_id):
    if 'skip' in request.get_json(force=True):
        return Response()

    try:
        data = request.get_json(force=True)
        match_data = data.pop(0)
        wards = []
        for ward_data in data:
            if ward_data['event'] == 'expired' or 'guys' in ward_data['npc_killed']:
                ward_data['playerDestroyedSteamId'] = None

            if 'playerPlacedSteamId' not in ward_data:
                # TODO: LOG
                ward_data['playerPlacedSteamId'] = None
            else:
                ward_data['playerPlacedSteamId'] = ward_data['playerPlacedSteamId'] - 76561197960265728

            if 'playerDestroyedSteamId' not in ward_data:
                # TODO: LOG
                ward_data['playerDestroyedSteamId'] = None
            elif ward_data['playerDestroyedSteamId'] is not None:
                ward_data['playerDestroyedSteamId'] = ward_data['playerDestroyedSteamId'] - 76561197960265728

            if 'isRadiant' not in ward_data:
                # TODO: LOG
                ward_data['isRadiant'] = None

            if 'radiantNetworth' not in ward_data:
                ward_data['radiantNetworth'] = None

            if 'direNetworth' not in ward_data:
                ward_data['direNetworth'] = None

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
                league_info = api.fetch_league_info(match_data['league'])
                db.session.add(Leagues(id=int(match_data['league']), name=league_info['displayName']))
                parse_league_players(match_data['league'])

        if not db.session.query(Matches).filter(Matches.id == match_id).first():
            new_match = Matches(
                id=match_id,
                league_id=match_data['league'],
                game_version=match_data['version'],
                date=match_data['date'],
                region=match_data['region'],
                duration=match_data['duration']
            )
            db.session.add(new_match)
            db.session.execute(insert(Wards).values(wards))
            # db.session.add_all([Wards(**ward) for ward in wards])
        else:
            print(f'{match_id} is already parsed')

        db.session.commit()
    except:
        import traceback
        traceback.print_exc()
        print(request.get_json(force=True))
    return Response()
