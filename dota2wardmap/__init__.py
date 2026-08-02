import os
import threading

import dotenv
from flask import Flask

from . import parser, views
from .extensions import db, migrate, redis_store, scheduler

dotenv.load_dotenv()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DB_URL"]
    app.config["REDIS_URL"] = os.environ["REDIS_URL"]

    register_extensions(app)
    register_blueprints(app)

    init_scheduler(app)

    return app


def register_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db)
    redis_store.init_app(app)
    scheduler.init_app(app)


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(views.bp)
    app.register_blueprint(parser.bp)


def init_scheduler(app: Flask) -> None:
    # if int(os.environ['PARSER']):
    #     scheduler.start()
    if int(os.getenv("INITIAL_PARSING", "0")):
        from . import replay_parser

        thread = threading.Thread(target=replay_parser.init_parser, args=(app,), daemon=True)
        thread.start()
