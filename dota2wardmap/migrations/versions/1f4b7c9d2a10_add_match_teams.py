"""add teams and match results

Revision ID: 1f4b7c9d2a10
Revises: 7d1f43a9c2e8
Create Date: 2026-08-09
"""

import sqlalchemy as sa
from alembic import op

revision = "1f4b7c9d2a10"
down_revision = "7d1f43a9c2e8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("tag", sa.String(length=64), nullable=True),
        sa.Column("logo_url", sa.String(length=512), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("matches", sa.Column("radiant_team_id", sa.Integer(), nullable=True))
    op.add_column("matches", sa.Column("dire_team_id", sa.Integer(), nullable=True))
    op.add_column("matches", sa.Column("radiant_win", sa.Boolean(), nullable=True))
    op.create_foreign_key("fk_matches_radiant_team", "matches", "teams", ["radiant_team_id"], ["id"])
    op.create_foreign_key("fk_matches_dire_team", "matches", "teams", ["dire_team_id"], ["id"])
    op.create_index("ix_matches_radiant_team_id", "matches", ["radiant_team_id"])
    op.create_index("ix_matches_dire_team_id", "matches", ["dire_team_id"])


def downgrade():
    op.drop_index("ix_matches_dire_team_id", table_name="matches")
    op.drop_index("ix_matches_radiant_team_id", table_name="matches")
    op.drop_constraint("fk_matches_dire_team", "matches", type_="foreignkey")
    op.drop_constraint("fk_matches_radiant_team", "matches", type_="foreignkey")
    op.drop_column("matches", "radiant_win")
    op.drop_column("matches", "dire_team_id")
    op.drop_column("matches", "radiant_team_id")
    op.drop_table("teams")
