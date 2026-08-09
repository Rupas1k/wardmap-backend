"""drop retired clustering jobs

Revision ID: 7d1f43a9c2e8
Revises: 4a8f12d93c6e
Create Date: 2026-08-09
"""

import sqlalchemy as sa
from alembic import op

revision = "7d1f43a9c2e8"
down_revision = "4a8f12d93c6e"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("clustering_jobs")


def downgrade():
    op.create_table(
        "clustering_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_clustering_jobs_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clustering_jobs_status", "clustering_jobs", ["status"])
    op.create_index("ix_clustering_jobs_available_at", "clustering_jobs", ["available_at"])
    op.create_index(
        "ix_clustering_jobs_claim",
        "clustering_jobs",
        ["status", "available_at", "created_at"],
    )
