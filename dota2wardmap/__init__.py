import os
import sys

import dotenv
from flask import Flask

sys.path.insert(0, '.')
dotenv.load_dotenv()


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ['DB_URL']

    from models import db, migrate
    from sock import sock
    db.init_app(app)
    migrate.init_app(app, db)
    sock.init_app(app)

    import views
    app.register_blueprint(views.bp)

    import sock
    app.register_blueprint(sock.bp)

    import livegames.parser
    app.register_blueprint(livegames.parser.bp)
    livegames.parser.scheduler.init_app(app)

    with app.app_context():
        db.create_all()

        livegames.parser.scheduler.start()
        # livegames.parser.parse()

        from main import main
        # main()


    return app
