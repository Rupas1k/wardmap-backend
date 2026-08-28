import re
from typing import Any

from flask import Flask, Response, request
from sqlalchemy import text
from werkzeug.exceptions import HTTPException

from .extensions import db, redis_store
from .settings import get_settings


def _error_code(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def register_http_handlers(app: Flask) -> None:
    allowed_origins = set(get_settings().cors_origins)

    @app.get("/health/live")
    def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def health_ready() -> tuple[dict[str, str], int] | dict[str, str]:
        try:
            db.session.execute(text("SELECT 1"))
            redis_store.ping()
        except Exception:
            db.session.rollback()
            app.logger.exception("Readiness check failed")
            return {"status": "unavailable"}, 503
        return {"status": "ok"}

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException) -> tuple[dict[str, Any], int]:
        status = error.code or 500
        return {"error": {"code": _error_code(error.name), "message": error.description}}, status

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception) -> tuple[dict[str, Any], int]:
        app.logger.exception("Unhandled request error", exc_info=error)
        db.session.rollback()
        return {
            "error": {"code": "internal_server_error", "message": "An unexpected error occurred"}
        }, 500

    @app.after_request
    def add_cors_headers(response: Response) -> Response:
        origin = request.headers.get("Origin")
        if origin in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Expose-Headers"] = "Retry-After"
            response.headers["Vary"] = "Origin"
        return response
