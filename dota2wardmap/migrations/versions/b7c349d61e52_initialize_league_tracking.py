"""initialize league tracking state

Revision ID: b7c349d61e52
Revises: 92d67c31ab40
Create Date: 2026-08-06
"""

from alembic import op

revision = "b7c349d61e52"
down_revision = "92d67c31ab40"
branch_labels = None
depends_on = None


def upgrade():
    # Existing imported leagues are historical until an administrator explicitly
    # resumes them. Newly created leagues continue to use the active default.
    op.execute(
        """
        UPDATE leagues
        SET tracking_status = 'completed',
            completed_at = now(),
            next_check_at = NULL
        """
    )


def downgrade():
    op.execute(
        """
        UPDATE leagues
        SET tracking_status = 'active',
            completed_at = NULL,
            next_check_at = NULL
        """
    )
