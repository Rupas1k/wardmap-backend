"""default map asset version to 2

Revision ID: 4a8f12d93c6e
Revises: b7c349d61e52
Create Date: 2026-08-08
"""

import sqlalchemy as sa
from alembic import op

revision = "4a8f12d93c6e"
down_revision = "b7c349d61e52"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "leagues",
        "map_asset_version",
        existing_type=sa.SmallInteger(),
        server_default="2",
        existing_nullable=False,
    )


def downgrade():
    op.alter_column(
        "leagues",
        "map_asset_version",
        existing_type=sa.SmallInteger(),
        server_default="1",
        existing_nullable=False,
    )
