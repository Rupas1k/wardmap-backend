from flask import Flask

from .cli import register_key_commands
from .middleware import authenticate_request, enforce_auth_failure_limit, enforce_rate_limit
from .permissions import current_access_level, max_ward_page_size, require_access


def register_access(app: Flask) -> None:
    app.before_request(enforce_auth_failure_limit)
    app.before_request(authenticate_request)
    app.before_request(enforce_rate_limit)
    register_key_commands(app)


__all__ = [
    "current_access_level",
    "max_ward_page_size",
    "register_access",
    "require_access",
]
