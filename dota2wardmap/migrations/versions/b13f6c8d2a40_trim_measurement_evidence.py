"""Keep only fresh-sighting measurement evidence.

Revision ID: b13f6c8d2a40
Revises: 91ac4e72d5b8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b13f6c8d2a40"
down_revision: str | None = "91ac4e72d5b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    wards = sa.table(
        "wards",
        sa.column("id", sa.Integer()),
        sa.column("measurement_evidence", sa.JSON()),
    )
    connection = op.get_bind()
    rows = connection.execute(
        sa.select(wards.c.id, wards.c.measurement_evidence).where(wards.c.measurement_evidence.is_not(None))
    )

    for ward_id, evidence in rows:
        sightings = evidence.get("sightings", []) if isinstance(evidence, dict) else []
        connection.execute(
            sa.update(wards).where(wards.c.id == ward_id).values(measurement_evidence={"sightings": sightings})
        )


def downgrade() -> None:
    pass
