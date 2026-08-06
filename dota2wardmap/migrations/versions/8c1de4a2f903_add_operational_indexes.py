"""add operational indexes and job status constraints

Revision ID: 8c1de4a2f903
Revises: a42a1e079f36
Create Date: 2026-08-05
"""

from alembic import op

revision = "8c1de4a2f903"
down_revision = "a42a1e079f36"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_matches_league_id", "matches", ["league_id"])
    op.create_index("ix_wards_match_id", "wards", ["match_id"])
    op.create_index("ix_wards_player_placed_id", "wards", ["player_placed_id"])
    op.create_index("ix_replay_jobs_claim", "replay_jobs", ["status", "created_at"])
    op.create_index(
        "ix_clustering_jobs_claim",
        "clustering_jobs",
        ["status", "available_at", "created_at"],
    )
    op.create_check_constraint(
        "ck_replay_jobs_status",
        "replay_jobs",
        "status IN ('pending', 'processing', 'completed', 'failed')",
    )
    op.create_check_constraint(
        "ck_clustering_jobs_status",
        "clustering_jobs",
        "status IN ('pending', 'processing', 'completed', 'failed')",
    )


def downgrade():
    op.drop_constraint("ck_clustering_jobs_status", "clustering_jobs", type_="check")
    op.drop_constraint("ck_replay_jobs_status", "replay_jobs", type_="check")
    op.drop_index("ix_clustering_jobs_claim", table_name="clustering_jobs")
    op.drop_index("ix_replay_jobs_claim", table_name="replay_jobs")
    op.drop_index("ix_wards_player_placed_id", table_name="wards")
    op.drop_index("ix_wards_match_id", table_name="wards")
    op.drop_index("ix_matches_league_id", table_name="matches")
