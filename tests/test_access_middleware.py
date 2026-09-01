from unittest.mock import Mock

import pytest
from flask import Flask
from werkzeug.exceptions import TooManyRequests

from dota2wardmap.access import middleware


def test_blocked_authentication_ip_does_not_query_database(monkeypatch):
    app = Flask(__name__)
    database_execute = Mock()
    monkeypatch.setattr(middleware.redis_store, "get", Mock(return_value=b"30"), raising=False)
    monkeypatch.setattr(middleware.db.session, "execute", database_execute)

    with app.test_request_context(headers={"Authorization": "Bearer invalid"}):
        with pytest.raises(TooManyRequests):
            middleware.enforce_auth_failure_limit()

    database_execute.assert_not_called()
