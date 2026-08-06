"""add revocable API keys

Revision ID: 6de384f2c1a7
Revises: 8c1de4a2f903
Create Date: 2026-08-05
"""

import sqlalchemy as sa
from alembic import op

revision = "6de384f2c1a7"
down_revision = "8c1de4a2f903"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner", sa.String(length=255), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("access_level", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("access_level IN ('advanced', 'admin')", name="ck_api_keys_access_level"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
        sa.UniqueConstraint("key_prefix"),
    )
    op.create_index("ix_api_keys_access_level", "api_keys", ["access_level"])
    op.create_index("ix_api_keys_revoked_at", "api_keys", ["revoked_at"])


def downgrade():
    op.drop_index("ix_api_keys_revoked_at", table_name="api_keys")
    op.drop_index("ix_api_keys_access_level", table_name="api_keys")
    op.drop_table("api_keys")
