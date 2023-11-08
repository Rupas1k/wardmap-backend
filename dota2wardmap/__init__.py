import os
import dotenv

from flask import Flask


dotenv.load_dotenv()


def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DB_URL']
    app.config['REDIS_URL'] = os.environ['REDIS_URL']

    from definitions import db, migrate, socket, redis_store, scheduler
    db.init_app(app)
    migrate.init_app(app, db)
    socket.init_app(app)
    redis_store.init_app(app)
    scheduler.init_app(app)

    import views
    import parser
    app.register_blueprint(views.bp)
    app.register_blueprint(parser.bp)

    with app.app_context():
        db.create_all()
        if int(os.environ['PARSER']):
            scheduler.start()
        if int(os.environ['INITIAL_PARSING']):
            parser.parse()

    return app
