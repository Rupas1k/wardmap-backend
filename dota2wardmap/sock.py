import json

from flask_sock import Server, Blueprint
from sqlalchemy import select

from models import Wards
from definitions import db, socket, redis_store


bp = Blueprint('sock', __name__)


@socket.route('/ws')
def echo(ws: Server):
    while True:
        fetched = json.loads(ws.receive())
        if fetched['type'] == 'wards':
            data = json.dumps([row._asdict() for row in db.session.execute(
            select(Wards.id, Wards.x_pos, Wards.y_pos, Wards.z_pos, Wards.duration, Wards.time_placed).where(
                Wards.is_obs == True).order_by(Wards.id.desc()).limit(50000)).all()])
            ws.send(json.dumps({
                'type': fetched['type'],
                'data': data
            }))
        elif fetched['type'] == 'raw_clusters':
            data = redis_store.lrange('raw_clusters', 0, -1)
            ws.send(json.dumps({
                'type': fetched['type'],
                'data': data
            }))
        elif fetched['type'] == 'clusters':
            data = redis_store.lrange('clusters', 0, -1)
            ws.send(json.dumps({
                'type': fetched['type'],
                'data': data
            }))
        db.session.close()