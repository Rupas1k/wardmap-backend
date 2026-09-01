from datetime import UTC, datetime, timedelta

from flask import g, request
from sqlalchemy import select
from werkzeug.exceptions import TooManyRequests, Unauthorized

from ..domain import AccessLevel
from ..extensions import db, redis_store
from ..models import ApiKey
from ..settings import get_settings
from .keys import hash_api_key
from .permissions import current_access_level, current_api_key


def _rate_limit_key(kind: str, identity: str) -> str:
    window = int(datetime.now(UTC).timestamp() // 60)
    return f"wardmap:rate-limit:{kind}:{identity}:{window}"


def _increment_rate_limit(cache_key: str) -> int:
    pipeline = redis_store.pipeline(transaction=True)
    pipeline.incr(cache_key)
    pipeline.expire(cache_key, 120)
    count, _ = pipeline.execute()
    return int(count)


def _auth_failure_key() -> str:
    return _rate_limit_key("auth-failure", request.remote_addr or "unknown")


def _record_auth_failure() -> None:
    limit = get_settings().authentication_failure_rate_limit
    count = _increment_rate_limit(_auth_failure_key())
    if count > limit:
        raise TooManyRequests(
            f"Too many failed authentication attempts; maximum is {limit} per minute",
            retry_after=60,
        )


def _is_exempt_request() -> bool:
    return request.method == "OPTIONS" or request.path.startswith("/health/")


def enforce_auth_failure_limit() -> None:
    if _is_exempt_request() or not request.headers.get("Authorization"):
        return

    raw_count = redis_store.get(_auth_failure_key())
    if (
        raw_count is not None
        and int(raw_count) >= get_settings().authentication_failure_rate_limit
    ):
        raise TooManyRequests("Too many failed authentication attempts", retry_after=60)


def authenticate_request() -> None:
    g.access_level = AccessLevel.ANONYMOUS
    g.api_key = None
    if _is_exempt_request():
        return

    authorization = request.headers.get("Authorization")
    if not authorization:
        return
    scheme, separator, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not value:
        _record_auth_failure()
        raise Unauthorized("Authorization must use a Bearer API key")

    api_key = db.session.execute(select(ApiKey).where(ApiKey.key_hash == hash_api_key(value))).scalar_one_or_none()
    if api_key is None or api_key.revoked_at is not None:
        _record_auth_failure()
        raise Unauthorized("API key is invalid or revoked")

    g.access_level = AccessLevel(api_key.access_level)
    g.api_key = api_key
    now = datetime.now(UTC)
    last_used = api_key.last_used_at
    if last_used is None or now - last_used.replace(tzinfo=last_used.tzinfo or UTC) >= timedelta(hours=1):
        api_key.last_used_at = now
        db.session.commit()


def enforce_rate_limit() -> None:
    if _is_exempt_request():
        return

    settings = get_settings()
    limit = {
        AccessLevel.ANONYMOUS: settings.anonymous_rate_limit,
        AccessLevel.ADVANCED: settings.advanced_rate_limit,
        AccessLevel.ADMIN: settings.admin_rate_limit,
    }[current_access_level()]
    if limit == 0:
        return

    api_key = current_api_key()
    identity = f"key:{api_key.id}" if api_key is not None else f"ip:{request.remote_addr or 'unknown'}"
    cache_key = _rate_limit_key("request", identity)
    count = _increment_rate_limit(cache_key)
    if count > limit:
        raise TooManyRequests(
            f"Rate limit exceeded; maximum is {limit} requests per minute",
            retry_after=60,
        )
