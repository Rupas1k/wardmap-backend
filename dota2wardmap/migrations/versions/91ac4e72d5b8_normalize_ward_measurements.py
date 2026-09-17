"""Normalize ward measurements.

Revision ID: 91ac4e72d5b8
Revises: 6d2f7b4a91c3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "91ac4e72d5b8"
down_revision: str | None = "6d2f7b4a91c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MEASUREMENT_COLUMNS = (
    sa.Column("measurement_version", sa.SmallInteger(), nullable=True),
    sa.Column("measurement_revision", sa.SmallInteger(), nullable=True),
    sa.Column("added_vision_seconds", sa.Float(), nullable=True),
    sa.Column("fresh_sightings", sa.Float(), nullable=True),
    sa.Column("fresh_sighting_threshold_seconds", sa.Float(), nullable=True),
    sa.Column("vision_measured_seconds", sa.Float(), nullable=True),
    sa.Column("vision_possible_seconds", sa.Float(), nullable=True),
    sa.Column("vision_coverage", sa.Float(), nullable=True),
    sa.Column("placed_at_seconds", sa.Float(), nullable=True),
    sa.Column("ended_at_seconds", sa.Float(), nullable=True),
    sa.Column("outcome", sa.String(length=24), nullable=True),
    sa.Column("outcome_reason", sa.String(length=32), nullable=True),
    sa.Column("vision_complete", sa.Boolean(), nullable=True),
    sa.Column("measurement_evidence", sa.JSON(), nullable=True),
)

OUTCOMES = {
    "enemy_destroyed": "dewarded",
    "inferred_expiry": "expired",
    "match_end": "match_ended",
    "replay_truncated": "replay_ended",
    "unknown_removal": "unknown",
}


def upgrade() -> None:
    for column in MEASUREMENT_COLUMNS:
        op.add_column("wards", column)

    wards = sa.table(
        "wards",
        sa.column("id", sa.Integer()),
        sa.column("measurement", sa.JSON()),
        *(sa.column(column.name, column.type) for column in MEASUREMENT_COLUMNS),
    )
    connection = op.get_bind()
    rows = connection.execute(sa.select(wards.c.id, wards.c.measurement).where(wards.c.measurement.is_not(None)))
    for ward_id, measurement in rows:
        evidence = {
            "sightings": measurement.get("sightings", []),
        }
        values = {
            "measurement_version": measurement.get("version"),
            "measurement_revision": measurement.get("revision"),
            "added_vision_seconds": measurement.get("added_vision_seconds"),
            "fresh_sightings": measurement.get("fresh_sightings"),
            "fresh_sighting_threshold_seconds": measurement.get("fresh_sighting_threshold_seconds"),
            "vision_measured_seconds": measurement.get("known_target_seconds"),
            "vision_possible_seconds": measurement.get("eligible_target_seconds"),
            "vision_coverage": measurement.get("coverage"),
            "placed_at_seconds": measurement.get("placed_at_seconds"),
            "ended_at_seconds": measurement.get("ended_at_seconds"),
            "outcome": OUTCOMES.get(measurement.get("outcome"), measurement.get("outcome")),
            "outcome_reason": measurement.get("outcome_reason"),
            "vision_complete": measurement.get("complete"),
            "measurement_evidence": evidence,
        }
        connection.execute(sa.update(wards).where(wards.c.id == ward_id).values(**values))

    op.drop_column("wards", "measurement")
    op.create_index("ix_wards_measurement_version_revision", "wards", ["measurement_version", "measurement_revision"])
    op.create_index("ix_wards_outcome", "wards", ["outcome"])


def downgrade() -> None:
    op.drop_index("ix_wards_outcome", table_name="wards")
    op.drop_index("ix_wards_measurement_version_revision", table_name="wards")
    op.add_column("wards", sa.Column("measurement", sa.JSON(), nullable=True))
    for column in reversed(MEASUREMENT_COLUMNS):
        op.drop_column("wards", column.name)
