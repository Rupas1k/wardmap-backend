"""Schedule replay job retries.

Revision ID: b79e3a5f12c4
Revises: a68d2f4e90b1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b79e3a5f12c4"
down_revision: str | None = "a68d2f4e90b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("replay_jobs", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.drop_index("ix_replay_jobs_claim", table_name="replay_jobs")
    op.create_index(
        "ix_replay_jobs_claim",
        "replay_jobs",
        ["status", "next_attempt_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_replay_jobs_claim", table_name="replay_jobs")
    op.create_index("ix_replay_jobs_claim", "replay_jobs", ["status", "created_at"])
    op.drop_column("replay_jobs", "next_attempt_at")
