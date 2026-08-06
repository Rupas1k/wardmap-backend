import json

from flask import Flask

from dota2wardmap.api.clusters import bp
from dota2wardmap.extensions import db
from dota2wardmap.models import ClusteringJob


def test_clusters_enqueues_typed_job_without_running_clustering():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    db.init_app(app)
    app.register_blueprint(bp)

    with app.app_context():
        db.create_all()
        with app.test_client() as client:
            response = client.get("/clusters?league_id=42&is_obs=0&min_samples=20")

        job = db.session.get(ClusteringJob, 1)

    assert response.status_code == 202
    assert response.get_json() == {"queued": True, "job_id": 1, "league_id": 42, "is_obs": False}
    assert job is not None
    assert json.loads(json.dumps(job.parameters))["league_id"] == 42
    assert job.parameters["is_obs"] == 0
    assert job.parameters["min_samples"] == 20
