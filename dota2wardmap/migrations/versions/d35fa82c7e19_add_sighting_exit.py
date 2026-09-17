"""Add fresh sighting exit evidence.

Revision ID: d35fa82c7e19
Revises: c24e9a71f6b2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d35fa82c7e19"
down_revision: str | None = "c24e9a71f6b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("fresh_sighting_events") as batch:
        batch.add_column(sa.Column("visible_seconds", sa.Float(), nullable=True))
        batch.add_column(sa.Column("lost_x", sa.Float(), nullable=True))
        batch.add_column(sa.Column("lost_y", sa.Float(), nullable=True))
        batch.add_column(sa.Column("lost_z", sa.Float(), nullable=True))

    op.create_table(
        "fresh_sighting_route_points",
        sa.Column("event_id", sa.BigInteger(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("time_seconds", sa.Float(), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("z", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["fresh_sighting_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id", "sequence"),
    )


def downgrade() -> None:
    op.drop_table("fresh_sighting_route_points")

    with op.batch_alter_table("fresh_sighting_events") as batch:
        batch.drop_column("lost_z")
        batch.drop_column("lost_y")
        batch.drop_column("lost_x")
        batch.drop_column("visible_seconds")
