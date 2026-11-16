"""track player matches

Revision ID: a91c8ecf3e21
Revises: c31d8e4f72a6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a91c8ecf3e21"
down_revision: str | None = "c31d8e4f72a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tracked_players",
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("tracking_status", sa.String(length=16), nullable=False),
        sa.Column("last_match_id", sa.BigInteger()),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("next_check_at", sa.DateTime(timezone=True)),
        sa.Column("consecutive_empty_checks", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(length=512)),
        sa.CheckConstraint("tracking_status IN ('active', 'paused')", name="ck_tracked_players_status"),
        sa.ForeignKeyConstraint(["account_id"], ["players.id"]),
        sa.PrimaryKeyConstraint("account_id"),
    )
    op.create_index(
        "ix_tracked_players_schedule",
        "tracked_players",
        ["tracking_status", "next_check_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_tracked_players_schedule", table_name="tracked_players")
    op.drop_table("tracked_players")
