from flask import Blueprint

from ..access.permissions import current_access_level, current_api_key

bp = Blueprint("access", __name__)


@bp.get("/auth/me")
def current_access() -> dict[str, object]:
    api_key = current_api_key()
    return {
        "access_level": current_access_level().value,
        "authenticated": api_key is not None,
        "key_prefix": api_key.key_prefix if api_key is not None else None,
        "owner": api_key.owner if api_key is not None else None,
    }
