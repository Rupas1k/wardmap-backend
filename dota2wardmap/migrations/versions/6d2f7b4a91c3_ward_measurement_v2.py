"""Add versioned ward measurement evidence.

Revision ID: 6d2f7b4a91c3
Revises: e7b29a4c10d2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6d2f7b4a91c3"
down_revision: str | None = "e7b29a4c10d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("wards", sa.Column("measurement", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("wards", "measurement")
