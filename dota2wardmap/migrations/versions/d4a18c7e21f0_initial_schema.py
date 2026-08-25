"""Create the current application schema.

Revision ID: d4a18c7e21f0
Revises:
Create Date: 2026-08-25

"""

import sqlalchemy as sa
from alembic import op

revision = "d4a18c7e21f0"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leagues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("tier", sa.String(length=32), nullable=True),
        sa.Column("map_asset_version", sa.SmallInteger(), nullable=False),
        sa.Column("tracking_status", sa.String(length=16), nullable=False),
        sa.Column("first_match_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_match_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consecutive_empty_checks", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "tracking_status IN ('active', 'paused', 'completed')",
            name="ck_leagues_tracking_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leagues_collection_schedule", "leagues", ["tracking_status", "next_check_at"])

    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("tag", sa.String(length=64), nullable=True),
        sa.Column("logo_url", sa.String(length=512), nullable=True),
        sa.Column("metadata_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "matches",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=True),
        sa.Column("duration", sa.SmallInteger(), nullable=True),
        sa.Column("region", sa.SmallInteger(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("game_version", sa.SmallInteger(), nullable=True),
        sa.Column("radiant_team_id", sa.Integer(), nullable=True),
        sa.Column("dire_team_id", sa.Integer(), nullable=True),
        sa.Column("radiant_win", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["dire_team_id"], ["teams.id"]),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"]),
        sa.ForeignKeyConstraint(["radiant_team_id"], ["teams.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_matches_dire_team_id", "matches", ["dire_team_id"])
    op.create_index("ix_matches_league_id", "matches", ["league_id"])
    op.create_index("ix_matches_radiant_team_id", "matches", ["radiant_team_id"])

    op.create_table(
        "players_matches",
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("is_radiant", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"]),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.PrimaryKeyConstraint("player_id", "match_id"),
    )
    op.create_index(
        "ix_players_matches_opponent_lookup",
        "players_matches",
        ["match_id", "is_radiant", "player_id"],
    )

    op.create_table(
        "wards",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.BigInteger(), nullable=True),
        sa.Column("is_obs", sa.Boolean(), nullable=False),
        sa.Column("is_radiant", sa.Boolean(), nullable=True),
        sa.Column("is_destroyed", sa.Boolean(), nullable=False),
        sa.Column("is_post_game", sa.Boolean(), nullable=False),
        sa.Column("player_placed_id", sa.Integer(), nullable=True),
        sa.Column("player_destroyed_id", sa.Integer(), nullable=True),
        sa.Column("time_placed", sa.SmallInteger(), nullable=False),
        sa.Column("duration", sa.SmallInteger(), nullable=False),
        sa.Column("x_pos", sa.SmallInteger(), nullable=False),
        sa.Column("y_pos", sa.SmallInteger(), nullable=False),
        sa.Column("z_pos", sa.SmallInteger(), nullable=False),
        sa.Column("radiant_networth", sa.Integer(), nullable=True),
        sa.Column("dire_networth", sa.Integer(), nullable=True),
        sa.Column("enemy_hero_vision_seconds", sa.Float(), nullable=True),
        sa.Column("unique_enemy_hero_vision_seconds", sa.Float(), nullable=True),
        sa.Column("heroes_spotted", sa.SmallInteger(), nullable=True),
        sa.Column("hero_reveal_events", sa.SmallInteger(), nullable=True),
        sa.Column("unique_hero_reveal_events", sa.SmallInteger(), nullable=True),
        sa.Column("npc_killed", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"]),
        sa.ForeignKeyConstraint(["player_destroyed_id"], ["players.id"]),
        sa.ForeignKeyConstraint(["player_placed_id"], ["players.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wards_match_id", "wards", ["match_id"])
    op.create_index("ix_wards_player_placed_id", "wards", ["player_placed_id"])

    op.create_table(
        "replay_jobs",
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_replay_jobs_status",
        ),
        sa.PrimaryKeyConstraint("match_id"),
    )
    op.create_index("ix_replay_jobs_claim", "replay_jobs", ["status", "created_at"])
    op.create_index("ix_replay_jobs_status", "replay_jobs", ["status"])

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


def downgrade() -> None:
    op.drop_table("api_keys")
    op.drop_table("replay_jobs")
    op.drop_table("wards")
    op.drop_table("players_matches")
    op.drop_table("matches")
    op.drop_table("teams")
    op.drop_table("players")
    op.drop_table("leagues")
