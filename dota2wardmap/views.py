from models import db, Matches
from flask import Blueprint
from sqlalchemy import select

bp = Blueprint('views', __name__)


@bp.route('/')
def hello_world():  # put application's code here
    return db.session.scalars(select(Matches.id)).all()
