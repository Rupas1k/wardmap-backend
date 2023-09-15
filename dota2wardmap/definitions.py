from pathlib import Path

from flask_redis import FlaskRedis
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_sock import Sock
from flask_apscheduler import APScheduler


ROOT_DIR = Path(__file__).resolve().parent

db = SQLAlchemy()
migrate = Migrate()
redis_store = FlaskRedis()
socket = Sock()
scheduler = APScheduler()
