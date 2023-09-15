import os
import sys
import dotenv

from flask import Flask

from definitions import db, migrate, socket, redis_store, scheduler


sys.path.insert(0, '.')
dotenv.load_dotenv()


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ['DB_URL']
    app.config['REDIS_URL'] = os.environ['REDIS_URL']

    db.init_app(app)
    migrate.init_app(app, db)
    socket.init_app(app)
    redis_store.init_app(app)
    scheduler.init_app(app)

    import views, sock, livegames.parser
    app.register_blueprint(views.bp)
    app.register_blueprint(sock.bp)
    app.register_blueprint(livegames.parser.bp)

    with app.app_context():
        db.create_all()
        scheduler.start()
        # livegames.parser.parse()

    return app
