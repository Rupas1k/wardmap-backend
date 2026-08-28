from flask import request

from dota2wardmap import create_app
from dota2wardmap.settings import get_settings


def client_ip(trusted_proxy_hops: int, monkeypatch) -> str:
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", str(trusted_proxy_hops))
    get_settings.cache_clear()
    app = create_app()

    @app.get("/health/client-ip")
    def health_client_ip():
        return {"client_ip": request.remote_addr}

    with app.test_client() as client:
        response = client.get(
            "/health/client-ip",
            headers={"X-Forwarded-For": "203.0.113.7"},
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )

    return response.get_json()["client_ip"]


def test_proxy_hop_uses_forwarded_client_ip(monkeypatch):
    assert client_ip(1, monkeypatch) == "203.0.113.7"


def test_untrusted_forwarded_client_ip_is_ignored(monkeypatch):
    assert client_ip(0, monkeypatch) == "127.0.0.1"


def test_cors_exposes_rate_limit_retry_header():
    app = create_app()

    with app.test_client() as client:
        response = client.get("/health/live", headers={"Origin": "http://localhost:5173"})

    assert response.headers["Access-Control-Expose-Headers"] == "Retry-After"
