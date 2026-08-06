"""add clustering job schedule

Revision ID: a42a1e079f36
Revises: f78d9bf2a314
Create Date: 2026-08-04
"""

import sqlalchemy as sa
from alembic import op

revision = "a42a1e079f36"
down_revision = "f78d9bf2a314"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "clustering_jobs",
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_clustering_jobs_available_at", "clustering_jobs", ["available_at"])


def downgrade():
    op.drop_index("ix_clustering_jobs_available_at", table_name="clustering_jobs")
    op.drop_column("clustering_jobs", "available_at")
