"""add ward reveal metrics

Revision ID: d4a18c7e21f0
Revises: c94e7f2186a3
Create Date: 2026-08-13

"""

import sqlalchemy as sa
from alembic import op

revision = "d4a18c7e21f0"
down_revision = "c94e7f2186a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("wards") as batch_op:
        batch_op.add_column(sa.Column("hero_reveal_events", sa.SmallInteger(), nullable=True))
        batch_op.add_column(sa.Column("unique_hero_reveal_events", sa.SmallInteger(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("wards") as batch_op:
        batch_op.drop_column("unique_hero_reveal_events")
        batch_op.drop_column("hero_reveal_events")
