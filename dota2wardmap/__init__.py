import os
import dotenv

from flask import Flask

import views
import parser

from extensions import db, migrate, redis_store, scheduler


dotenv.load_dotenv()


def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DB_URL']
    app.config['REDIS_URL'] = os.environ['REDIS_URL']

    register_extensions(app)
    register_blueprints(app)

    with app.app_context():
        db.create_all()
        init_scheduler()

    return app

def register_extensions(app):
    db.init_app(app)
    migrate.init_app(app, db)
    redis_store.init_app(app)
    scheduler.init_app(app)


def register_blueprints(app):
    app.register_blueprint(views.bp)
    app.register_blueprint(parser.bp)


def init_scheduler():
    if int(os.environ['PARSER']):
        scheduler.start()
    if int(os.environ['INITIAL_PARSING']):
        parser.parse()