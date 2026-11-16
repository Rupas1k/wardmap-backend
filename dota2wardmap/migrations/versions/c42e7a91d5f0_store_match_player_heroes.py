"""store match player heroes

Revision ID: c42e7a91d5f0
Revises: a91c8ecf3e21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c42e7a91d5f0"
down_revision: str | None = "a91c8ecf3e21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("players_matches", sa.Column("hero_name", sa.String(length=96)))


def downgrade() -> None:
    op.drop_column("players_matches", "hero_name")
