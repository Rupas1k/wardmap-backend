"""Add match-specific player side.

Revision ID: 9d2f6a7b4c11
Revises: 5a79e1c3d442
"""

import sqlalchemy as sa
from alembic import op

revision = "9d2f6a7b4c11"
down_revision = "5a79e1c3d442"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("players_matches") as batch_op:
        batch_op.add_column(sa.Column("is_radiant", sa.Boolean(), nullable=True))
        batch_op.create_index(
            "ix_players_matches_opponent_lookup",
            ["match_id", "is_radiant", "player_id"],
            unique=False,
        )

    op.execute(
        """
        UPDATE players_matches
        SET is_radiant = (
            SELECT wards.is_radiant
            FROM wards
            WHERE wards.match_id = players_matches.match_id
              AND wards.player_placed_id = players_matches.player_id
              AND wards.is_radiant IS NOT NULL
            LIMIT 1
        )
        WHERE is_radiant IS NULL
        """
    )
    op.execute(
        """
        UPDATE players_matches
        SET is_radiant = (
            SELECT NOT wards.is_radiant
            FROM wards
            WHERE wards.match_id = players_matches.match_id
              AND wards.player_destroyed_id = players_matches.player_id
              AND wards.is_radiant IS NOT NULL
            LIMIT 1
        )
        WHERE is_radiant IS NULL
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("players_matches") as batch_op:
        batch_op.drop_index("ix_players_matches_opponent_lookup")
        batch_op.drop_column("is_radiant")
