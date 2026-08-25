"""track team metadata refresh

Revision ID: 5a79e1c3d442
Revises: 1f4b7c9d2a10
Create Date: 2026-08-09
"""

import sqlalchemy as sa
from alembic import op

revision = "5a79e1c3d442"
down_revision = "1f4b7c9d2a10"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("teams", sa.Column("metadata_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE teams SET metadata_updated_at = now()")
    op.create_index("ix_teams_metadata_updated_at", "teams", ["metadata_updated_at"])


def downgrade():
    op.drop_index("ix_teams_metadata_updated_at", table_name="teams")
    op.drop_column("teams", "metadata_updated_at")
