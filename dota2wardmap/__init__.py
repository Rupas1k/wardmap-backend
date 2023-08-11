import os
import dotenv
from flask import Flask

import sys
sys.path.insert(0, '.')


def create_app():
    dotenv.load_dotenv()

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ['DB_URL']

    from models import db, migrate
    db.init_app(app)
    migrate.init_app(app, db)

    with app.app_context():
        db.create_all()

        from main import get_all_matches
        print(get_all_matches())

    import views
    app.register_blueprint(views.bp)

    return app

# Flask-APScheduler
# from parser import Parser
# with app.app_context():
#     parser = Parser()
