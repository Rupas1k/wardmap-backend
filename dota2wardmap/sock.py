import json

from flask_sock import Server, Sock, Blueprint

from models import Matches, Wards, db
from sqlalchemy import select, desc

bp = Blueprint('sock', __name__)
sock = Sock()


@sock.route('/ws')
def echo(ws: Server):
    while True:
        data = ws.receive()
        ws.send(json.dumps([row._asdict() for row in db.session.execute(select(Wards.id, Wards.x_pos, Wards.y_pos, Wards.z_pos, Wards.duration, Wards.time_placed).where(Wards.is_obs == True).order_by(Wards.id.desc()).limit(50000)).all()]))
        db.session.close()
