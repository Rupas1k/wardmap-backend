"""Repair wards misclassified at their expected lifetime.

Revision ID: f57c8a9d31e4
Revises: e46ab93d8f20
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f57c8a9d31e4"
down_revision: str | None = "e46ab93d8f20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE wards
        SET outcome = 'expired',
            outcome_reason = 'expected_lifetime',
            is_destroyed = false,
            player_destroyed_id = NULL,
            npc_killed = NULL
        WHERE placed_at_seconds IS NOT NULL
          AND ended_at_seconds IS NOT NULL
          AND outcome <> 'match_ended'
          AND ABS(
              (ended_at_seconds - placed_at_seconds)
              - CASE WHEN is_obs THEN 360.0 ELSE 420.0 END
          ) <= 0.25
        """
    )


def downgrade() -> None:
    pass
