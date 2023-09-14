import json
from models import db, Wards, Matches
from flask import Blueprint, Response, request
from sqlalchemy.dialects.postgresql import insert
from livegames.work_queue import WorkQueue

bp = Blueprint('views', __name__)
work_queue = WorkQueue()


@bp.route('/get_work_queue')
def send_work_queue():
    response = Response(json.dumps(work_queue.get()))
    response.headers['Content/type'] = 'Application/json'
    return response


@bp.route('/send_ward_data/<match_id>', methods=['POST'])
def receive_ward_data(match_id):
    match_id = int(match_id)
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
                                              league_id=match_data['league'],
                                              average_rank=work_queue.get_dict()[match_id]['averageRank'],
                                              tournament_id=match_data['tournament'],
                                              game_version=match_data['version'],
                                              date=match_data['date'],
                                              region=match_data['region'],
                                              duration=match_data['duration']))
    db.session.execute(insert(Wards).values(wards))
    db.session.commit()
    work_queue.remove(match_id)
    return Response()
