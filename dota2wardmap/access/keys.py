import hashlib
import secrets


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    api_key = f"wm_{secrets.token_urlsafe(32)}"
    return api_key, api_key[:11], hash_api_key(api_key)
