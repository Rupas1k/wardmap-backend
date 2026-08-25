"""add ward vision metrics

Revision ID: ba31d74fc821
Revises: 9d2f6a7b4c11
Create Date: 2026-08-10

"""

import sqlalchemy as sa
from alembic import op

revision = "ba31d74fc821"
down_revision = "9d2f6a7b4c11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("wards") as batch_op:
        batch_op.add_column(sa.Column("enemy_hero_vision_seconds", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("heroes_spotted", sa.SmallInteger(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("wards") as batch_op:
        batch_op.drop_column("heroes_spotted")
        batch_op.drop_column("enemy_hero_vision_seconds")
