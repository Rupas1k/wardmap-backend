from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar, cast

from flask import g
from werkzeug.exceptions import Forbidden

from ..domain import AccessLevel
from ..models import ApiKey
from ..settings import get_settings

P = ParamSpec("P")
R = TypeVar("R")

ACCESS_RANK = {
    AccessLevel.ANONYMOUS: 0,
    AccessLevel.ADVANCED: 1,
    AccessLevel.ADMIN: 2,
}


def current_access_level() -> AccessLevel:
    return cast(AccessLevel, g.access_level)


def current_api_key() -> ApiKey | None:
    return cast(ApiKey | None, g.api_key)


def require_access(required_level: AccessLevel) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(view: Callable[P, R]) -> Callable[P, R]:
        @wraps(view)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            if ACCESS_RANK[current_access_level()] < ACCESS_RANK[required_level]:
                raise Forbidden(f"{required_level.value} access is required")
            return view(*args, **kwargs)

        return wrapped

    return decorator


def max_ward_page_size() -> int:
    settings = get_settings()
    return {
        AccessLevel.ANONYMOUS: settings.anonymous_max_ward_page_size,
        AccessLevel.ADVANCED: settings.advanced_max_ward_page_size,
        AccessLevel.ADMIN: settings.admin_max_ward_page_size,
    }[current_access_level()]
