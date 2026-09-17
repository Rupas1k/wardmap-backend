"""Normalize fresh sighting evidence.

Revision ID: c24e9a71f6b2
Revises: b13f6c8d2a40
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c24e9a71f6b2"
down_revision: str | None = "b13f6c8d2a40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("players") as batch:
        batch.alter_column("id", existing_type=sa.Integer(), type_=sa.BigInteger(), existing_nullable=False)
    with op.batch_alter_table("players_matches") as batch:
        batch.alter_column("player_id", existing_type=sa.Integer(), type_=sa.BigInteger(), existing_nullable=False)
    with op.batch_alter_table("wards") as batch:
        batch.alter_column("player_placed_id", existing_type=sa.Integer(), type_=sa.BigInteger(), existing_nullable=True)
        batch.alter_column("player_destroyed_id", existing_type=sa.Integer(), type_=sa.BigInteger(), existing_nullable=True)

    op.create_table(
        "fresh_sighting_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("sample_tick", sa.Integer(), nullable=False),
        sa.Column("time_seconds", sa.Float(), nullable=False),
        sa.Column("target_player_slot", sa.SmallInteger(), nullable=False),
        sa.Column("target_steam_id", sa.String(length=20), nullable=True),
        sa.Column("target_player_id", sa.BigInteger(), nullable=True),
        sa.Column("target_hero_name", sa.String(length=96), nullable=False),
        sa.Column("target_is_radiant", sa.Boolean(), nullable=False),
        sa.Column("target_x", sa.Float(), nullable=False),
        sa.Column("target_y", sa.Float(), nullable=False),
        sa.Column("target_z", sa.Float(), nullable=False),
        sa.Column("hidden_seconds", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_player_id"], ["players.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("match_id", "sample_tick", "target_player_slot", name="uq_fresh_sighting_match_tick_slot"),
    )
    op.create_index("ix_fresh_sighting_events_match_id", "fresh_sighting_events", ["match_id"])
    op.create_index("ix_fresh_sighting_events_target_player_id", "fresh_sighting_events", ["target_player_id"])
    op.create_index(
        "ix_fresh_sighting_target_time",
        "fresh_sighting_events",
        ["target_player_id", "time_seconds"],
    )
    op.create_index(
        "ix_fresh_sighting_hero_time",
        "fresh_sighting_events",
        ["target_hero_name", "time_seconds"],
    )

    op.create_table(
        "ward_fresh_sighting_credits",
        sa.Column("event_id", sa.BigInteger(), nullable=False),
        sa.Column("ward_id", sa.Integer(), nullable=False),
        sa.Column("credit", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["fresh_sighting_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ward_id"], ["wards.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id", "ward_id"),
    )
    op.create_index("ix_ward_fresh_sighting_credits_ward_id", "ward_fresh_sighting_credits", ["ward_id"])


def downgrade() -> None:
    op.drop_index("ix_ward_fresh_sighting_credits_ward_id", table_name="ward_fresh_sighting_credits")
    op.drop_table("ward_fresh_sighting_credits")
    op.drop_index("ix_fresh_sighting_hero_time", table_name="fresh_sighting_events")
    op.drop_index("ix_fresh_sighting_target_time", table_name="fresh_sighting_events")
    op.drop_index("ix_fresh_sighting_events_target_player_id", table_name="fresh_sighting_events")
    op.drop_index("ix_fresh_sighting_events_match_id", table_name="fresh_sighting_events")
    op.drop_table("fresh_sighting_events")

    with op.batch_alter_table("wards") as batch:
        batch.alter_column("player_destroyed_id", existing_type=sa.BigInteger(), type_=sa.Integer(), existing_nullable=True)
        batch.alter_column("player_placed_id", existing_type=sa.BigInteger(), type_=sa.Integer(), existing_nullable=True)
    with op.batch_alter_table("players_matches") as batch:
        batch.alter_column("player_id", existing_type=sa.BigInteger(), type_=sa.Integer(), existing_nullable=False)
    with op.batch_alter_table("players") as batch:
        batch.alter_column("id", existing_type=sa.BigInteger(), type_=sa.Integer(), existing_nullable=False)
