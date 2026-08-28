from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from .access import register_access
from .extensions import db, migrate, redis_store
from .logging_config import configure_logging
from .settings import get_settings
from .web import register_http_handlers


def create_app() -> Flask:
    configure_logging()
    app = Flask(__name__)
    settings = get_settings()
    if settings.trusted_proxy_hops:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=settings.trusted_proxy_hops)
    configure_connections(app)
    register_extensions(app)
    register_access(app)
    from .replay.cli import register_replay_commands

    register_replay_commands(app)
    register_blueprints(app)
    register_http_handlers(app)
    return app


def create_worker_app() -> Flask:
    configure_logging()
    app = Flask("dota2wardmap-worker")
    configure_connections(app)
    db.init_app(app)
    redis_store.init_app(app)
    return app


def configure_connections(app: Flask) -> None:
    settings = get_settings()
    app.config["SQLALCHEMY_DATABASE_URI"] = settings.database_url
    app.config["REDIS_URL"] = settings.redis_url


def register_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db)
    redis_store.init_app(app)


def register_blueprints(app: Flask) -> None:
    from .api import blueprints

    for blueprint in blueprints:
        app.register_blueprint(blueprint, url_prefix="/api/v1")
