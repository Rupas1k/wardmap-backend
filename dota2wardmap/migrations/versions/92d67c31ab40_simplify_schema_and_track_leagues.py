"""simplify schema and track leagues

Revision ID: 92d67c31ab40
Revises: 6de384f2c1a7
Create Date: 2026-08-06
"""

import sqlalchemy as sa
from alembic import op

revision = "92d67c31ab40"
down_revision = "6de384f2c1a7"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("players_leagues")
    op.drop_table("maps")

    op.add_column("leagues", sa.Column("tier", sa.String(length=32), nullable=True))
    op.add_column(
        "leagues",
        sa.Column("map_asset_version", sa.SmallInteger(), server_default="1", nullable=False),
    )
    op.add_column(
        "leagues",
        sa.Column("tracking_status", sa.String(length=16), server_default="active", nullable=False),
    )
    op.add_column("leagues", sa.Column("first_match_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("leagues", sa.Column("last_match_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("leagues", sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("leagues", sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "leagues",
        sa.Column("consecutive_empty_checks", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("leagues", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_leagues_tracking_status",
        "leagues",
        "tracking_status IN ('active', 'paused', 'completed')",
    )
    op.create_index(
        "ix_leagues_collection_schedule",
        "leagues",
        ["tracking_status", "next_check_at"],
    )
    op.execute("UPDATE leagues SET map_asset_version = 0 WHERE id IN (15728, 15475)")

    op.alter_column(
        "matches",
        "date",
        new_column_name="started_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="to_timestamp(date)",
    )
    op.execute(
        """
        UPDATE leagues AS league
        SET first_match_at = aggregate.first_match_at,
            last_match_at = aggregate.last_match_at
        FROM (
            SELECT league_id,
                   min(started_at) AS first_match_at,
                   max(started_at) AS last_match_at
            FROM matches
            WHERE league_id IS NOT NULL
            GROUP BY league_id
        ) AS aggregate
        WHERE league.id = aggregate.league_id
        """
    )


def downgrade():
    op.alter_column(
        "matches",
        "started_at",
        new_column_name="date",
        type_=sa.BigInteger(),
        postgresql_using="extract(epoch FROM started_at)::bigint",
    )

    op.drop_index("ix_leagues_collection_schedule", table_name="leagues")
    op.drop_constraint("ck_leagues_tracking_status", "leagues", type_="check")
    op.drop_column("leagues", "completed_at")
    op.drop_column("leagues", "consecutive_empty_checks")
    op.drop_column("leagues", "next_check_at")
    op.drop_column("leagues", "last_checked_at")
    op.drop_column("leagues", "last_match_at")
    op.drop_column("leagues", "first_match_at")
    op.drop_column("leagues", "tracking_status")
    op.drop_column("leagues", "map_asset_version")
    op.drop_column("leagues", "tier")

    op.create_table(
        "maps",
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("is_obs", sa.Boolean(), nullable=False),
        sa.Column("public", sa.Boolean(), nullable=True),
        sa.Column("min_cluster_size", sa.SmallInteger(), nullable=True),
        sa.Column("min_samples", sa.SmallInteger(), nullable=True),
        sa.Column("cluster_selection_epsilon", sa.SmallInteger(), nullable=True),
        sa.Column("cluster_selection_method", sa.String(), nullable=True),
        sa.Column("version", sa.SmallInteger(), nullable=True),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"]),
        sa.PrimaryKeyConstraint("league_id", "is_obs"),
    )
    op.create_table(
        "players_leagues",
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"]),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.PrimaryKeyConstraint("player_id", "league_id"),
    )
