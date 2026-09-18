from sqlalchemy import create_engine, inspect

from dota2wardmap import create_app
from dota2wardmap.extensions import db
from dota2wardmap.settings import get_settings


def test_upgrade_creates_schema_from_single_baseline(monkeypatch, tmp_path):
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
    assert version == "c31d8e4f72a6"
    ward_columns = {column["name"] for column in inspect(engine).get_columns("wards")}
    assert {
        "scouting_score",
        "scouting_tracking_seconds",
        "scouting_discovery_seconds",
        "measurement_version",
        "added_vision_seconds",
        "measurement_evidence",
    } <= ward_columns
    assert "measurement" not in ward_columns


def test_scouting_upgrade_preserves_existing_wards_as_unmeasured(monkeypatch, tmp_path):
    database_path = tmp_path / "existing.sqlite"
    monkeypatch.setenv("DB_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    get_settings.cache_clear()
    app = create_app()
    runner = app.test_cli_runner()
    result = runner.invoke(args=["db", "upgrade", "d4a18c7e21f0"])
    assert result.exit_code == 0, result.output

    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO wards (is_obs, is_destroyed, is_post_game, time_placed, duration, x_pos, y_pos, z_pos) "
            "VALUES (1, 0, 0, 100, 360, 10, 20, 30)"
        )
    result = runner.invoke(args=["db", "upgrade"])
    assert result.exit_code == 0, result.output
    with engine.connect() as connection:
        row = connection.exec_driver_sql(
            "SELECT duration, scouting_score, scouting_version, scouting_complete, measurement_version FROM wards"
        ).one()
    assert tuple(row) == (360, None, None, None, None)
