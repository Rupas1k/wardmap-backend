import os

import pytest

from dota2wardmap import create_app
from dota2wardmap.settings import get_settings


@pytest.fixture(autouse=True)
def test_environment(monkeypatch):
    monkeypatch.setenv("DB_URL", "sqlite://")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def test_client():
    os.environ["CONFIG_TYPE"] = "config.TestingConfig"
    flask_app = create_app()

    with flask_app.test_client() as testing_client, flask_app.app_context():
        yield testing_client
