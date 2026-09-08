"""Add versioned observer scouting metrics.

Revision ID: e7b29a4c10d2
Revises: d4a18c7e21f0
"""

import sqlalchemy as sa
from alembic import op

revision = "e7b29a4c10d2"
down_revision = "d4a18c7e21f0"
branch_labels = None
depends_on = None


def upgrade():
    # Existing replays stay unmeasured until explicitly reparsed.
    op.add_column("wards", sa.Column("scouting_tracking_seconds", sa.Float(), nullable=True))
    op.add_column("wards", sa.Column("scouting_discovery_seconds", sa.Float(), nullable=True))
    op.add_column("wards", sa.Column("scouting_score", sa.Float(), nullable=True))
    op.add_column("wards", sa.Column("scouting_version", sa.SmallInteger(), nullable=True))
    op.add_column("wards", sa.Column("scouting_tau_seconds", sa.Float(), nullable=True))
    op.add_column("wards", sa.Column("scouting_complete", sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column("wards", "scouting_complete")
    op.drop_column("wards", "scouting_tau_seconds")
    op.drop_column("wards", "scouting_version")
    op.drop_column("wards", "scouting_score")
    op.drop_column("wards", "scouting_discovery_seconds")
    op.drop_column("wards", "scouting_tracking_seconds")
