"""Add repeated ward sighting segments.

Revision ID: a68d2f4e90b1
Revises: f57c8a9d31e4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a68d2f4e90b1"
down_revision: str | None = "f57c8a9d31e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ward_sighting_segments",
        sa.Column("event_id", sa.BigInteger(), nullable=False),
        sa.Column("ward_id", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("time_seconds", sa.Float(), nullable=False),
        sa.Column("gap_seconds", sa.Float(), nullable=True),
        sa.Column("start_x", sa.Float(), nullable=False),
        sa.Column("start_y", sa.Float(), nullable=False),
        sa.Column("start_z", sa.Float(), nullable=False),
        sa.Column("visible_seconds", sa.Float(), nullable=True),
        sa.Column("lost_x", sa.Float(), nullable=True),
        sa.Column("lost_y", sa.Float(), nullable=True),
        sa.Column("lost_z", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["event_id", "ward_id"],
            ["ward_fresh_sighting_credits.event_id", "ward_fresh_sighting_credits.ward_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("event_id", "ward_id", "sequence"),
    )
    op.execute(
        """
        INSERT INTO ward_sighting_segments
            (event_id, ward_id, sequence, time_seconds, gap_seconds,
             start_x, start_y, start_z, visible_seconds, lost_x, lost_y, lost_z)
        SELECT credit.event_id, credit.ward_id, 0, event.time_seconds, NULL,
               event.target_x, event.target_y, event.target_z,
               credit.visible_seconds, credit.lost_x, credit.lost_y, credit.lost_z
        FROM ward_fresh_sighting_credits AS credit
        JOIN fresh_sighting_events AS event ON event.id = credit.event_id
        """
    )

    op.create_table(
        "fresh_sighting_route_points_v3",
        sa.Column("event_id", sa.BigInteger(), nullable=False),
        sa.Column("ward_id", sa.Integer(), nullable=False),
        sa.Column("segment_sequence", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("time_seconds", sa.Float(), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("z", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id", "ward_id", "segment_sequence"],
            ["ward_sighting_segments.event_id", "ward_sighting_segments.ward_id", "ward_sighting_segments.sequence"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("event_id", "ward_id", "segment_sequence", "sequence"),
    )
    op.execute(
        """
        INSERT INTO fresh_sighting_route_points_v3
            (event_id, ward_id, segment_sequence, sequence, time_seconds, x, y, z)
        SELECT event_id, ward_id, 0, sequence, time_seconds, x, y, z
        FROM fresh_sighting_route_points
        """
    )
    op.drop_table("fresh_sighting_route_points")
    op.rename_table("fresh_sighting_route_points_v3", "fresh_sighting_route_points")

    with op.batch_alter_table("ward_fresh_sighting_credits") as batch:
        batch.drop_column("lost_z")
        batch.drop_column("lost_y")
        batch.drop_column("lost_x")
        batch.drop_column("visible_seconds")


def downgrade() -> None:
    with op.batch_alter_table("ward_fresh_sighting_credits") as batch:
        batch.add_column(sa.Column("visible_seconds", sa.Float(), nullable=True))
        batch.add_column(sa.Column("lost_x", sa.Float(), nullable=True))
        batch.add_column(sa.Column("lost_y", sa.Float(), nullable=True))
        batch.add_column(sa.Column("lost_z", sa.Float(), nullable=True))

    op.execute(
        """
        UPDATE ward_fresh_sighting_credits AS credit
        SET visible_seconds = segment.visible_seconds,
            lost_x = segment.lost_x,
            lost_y = segment.lost_y,
            lost_z = segment.lost_z
        FROM ward_sighting_segments AS segment
        WHERE segment.event_id = credit.event_id
          AND segment.ward_id = credit.ward_id
          AND segment.sequence = 0
        """
    )

    op.create_table(
        "fresh_sighting_route_points_v2",
        sa.Column("event_id", sa.BigInteger(), nullable=False),
        sa.Column("ward_id", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("time_seconds", sa.Float(), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("z", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id", "ward_id"],
            ["ward_fresh_sighting_credits.event_id", "ward_fresh_sighting_credits.ward_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("event_id", "ward_id", "sequence"),
    )
    op.execute(
        """
        INSERT INTO fresh_sighting_route_points_v2
            (event_id, ward_id, sequence, time_seconds, x, y, z)
        SELECT event_id, ward_id, sequence, time_seconds, x, y, z
        FROM fresh_sighting_route_points
        WHERE segment_sequence = 0
        """
    )
    op.drop_table("fresh_sighting_route_points")
    op.rename_table("fresh_sighting_route_points_v2", "fresh_sighting_route_points")
    op.drop_table("ward_sighting_segments")
