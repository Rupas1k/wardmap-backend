import os
import dotenv
from flask import Flask
import views


def create_app():
    dotenv.load_dotenv()

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ['DB_URL']

    from models import db
    db.init_app(app)

    with app.app_context():
        from main import get_all_matches
        print(get_all_matches())

    app.register_blueprint(views.bp)

    # Flask-APScheduler
    # from parser import Parser
    # with app.app_context():
    #     parser = Parser()

    return app
