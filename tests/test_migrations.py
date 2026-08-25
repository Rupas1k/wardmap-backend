from sqlalchemy import create_engine, inspect

from dota2wardmap import create_app
from dota2wardmap.extensions import db
from dota2wardmap.settings import get_settings


def test_upgrade_bootstraps_an_empty_database(monkeypatch, tmp_path):
    database_path = tmp_path / "fresh.sqlite"
    monkeypatch.setenv("DB_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    get_settings.cache_clear()

    app = create_app()
    result = app.test_cli_runner().invoke(args=["db", "upgrade"])

    assert result.exit_code == 0, result.output
    second_result = app.test_cli_runner().invoke(args=["db", "upgrade"])
    assert second_result.exit_code == 0, second_result.output

    engine = create_engine(f"sqlite:///{database_path}")
    tables = set(inspect(engine).get_table_names())
    assert set(db.metadata.tables).issubset(tables)
    assert "alembic_version" in tables

    with engine.connect() as connection:
        version = connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
    assert version == "d4a18c7e21f0"
