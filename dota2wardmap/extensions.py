from pathlib import Path

from flask_apscheduler import APScheduler
from flask_migrate import Migrate
from flask_redis import FlaskRedis
from flask_sqlalchemy import SQLAlchemy

ROOT_DIR = Path(__file__).resolve().parent

db = SQLAlchemy()
migrate = Migrate(directory=str(ROOT_DIR / "migrations"))
redis_store = FlaskRedis(decode_responses=True)
scheduler = APScheduler()
