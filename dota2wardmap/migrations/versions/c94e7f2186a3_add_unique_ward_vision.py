"""add unique ward vision

Revision ID: c94e7f2186a3
Revises: ba31d74fc821
Create Date: 2026-08-10

"""

import sqlalchemy as sa
from alembic import op

revision = "c94e7f2186a3"
down_revision = "ba31d74fc821"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("wards") as batch_op:
        batch_op.add_column(sa.Column("unique_enemy_hero_vision_seconds", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("wards") as batch_op:
        batch_op.drop_column("unique_enemy_hero_vision_seconds")
