"""add durable job tables

Revision ID: f78d9bf2a314
Revises: 18463ae5da25
Create Date: 2026-08-04
"""

import sqlalchemy as sa
from alembic import op

revision = "f78d9bf2a314"
down_revision = "18463ae5da25"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "replay_jobs",
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("match_id"),
    )
    op.create_index("ix_replay_jobs_status", "replay_jobs", ["status"])
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clustering_jobs_status", "clustering_jobs", ["status"])


def downgrade():
    op.drop_index("ix_clustering_jobs_status", table_name="clustering_jobs")
    op.drop_table("clustering_jobs")
    op.drop_index("ix_replay_jobs_status", table_name="replay_jobs")
    op.drop_table("replay_jobs")
