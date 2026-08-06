import json

from flask import Blueprint, request
from werkzeug.exceptions import BadRequest, NotFound

from ..access import require_access
from ..domain import AccessLevel
from ..extensions import db, redis_store
from ..models import ClusteringJob

bp = Blueprint("clusters", __name__)


@bp.post("/clusters")
@require_access(AccessLevel.ADMIN)
def queue_clusters():
    defaults = {
        "cluster_selection_epsilon": 0,
        "min_samples": 10,
        "min_cluster_size": 10,
        "cluster_selection_method": "eom",
        "league_id": 15909,
        "min_match": 0,
        "is_obs": 1,
        "n_jobs": -1,
    }
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        raise BadRequest("request body must be a JSON object")
    job = defaults.copy()
    for name in ("cluster_selection_epsilon", "min_samples", "min_cluster_size", "league_id", "min_match", "n_jobs"):
        try:
            job[name] = int(body.get(name, job[name]))
        except (TypeError, ValueError) as exc:
            raise BadRequest(f"{name} must be an integer") from exc
    job["cluster_selection_method"] = str(body.get("cluster_selection_method", job["cluster_selection_method"]))
    try:
        job["is_obs"] = int(body.get("is_obs", job["is_obs"]))
    except (TypeError, ValueError) as exc:
        raise BadRequest("is_obs must be 0 or 1") from exc

    if job["is_obs"] not in (0, 1):
        raise BadRequest("is_obs must be 0 or 1")
    if job["min_cluster_size"] < 2 or job["min_cluster_size"] > 10000:
        raise BadRequest("min_cluster_size must be between 2 and 10000")
    if job["min_samples"] < 1 or job["min_samples"] > 10000:
        raise BadRequest("min_samples must be between 1 and 10000")
    if job["cluster_selection_method"] not in ("eom", "leaf"):
        raise BadRequest("cluster_selection_method must be eom or leaf")
    if job["n_jobs"] < -1 or job["n_jobs"] == 0 or job["n_jobs"] > 32:
        raise BadRequest("n_jobs must be -1 or between 1 and 32")

    clustering_job = ClusteringJob(parameters=job)
    db.session.add(clustering_job)
    db.session.commit()
    return {
        "queued": True,
        "job_id": clustering_job.id,
        "league_id": job["league_id"],
        "is_obs": bool(job["is_obs"]),
    }, 202


@bp.get("/leagues/<int:league_id>/clusters/<ward_type>")
def get_clusters(league_id: int, ward_type: str):
    types = {"sentry": 0, "observer": 1}
    if ward_type not in types:
        raise NotFound("ward type must be observer or sentry")
    data = [json.loads(cluster) for cluster in redis_store.lrange(f"{league_id}-{types[ward_type]}", 0, -1)]
    return {"data": data}
