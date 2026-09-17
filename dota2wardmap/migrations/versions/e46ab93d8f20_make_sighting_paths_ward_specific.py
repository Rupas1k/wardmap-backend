"""Make fresh sighting paths ward specific.

Revision ID: e46ab93d8f20
Revises: d35fa82c7e19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e46ab93d8f20"
down_revision: str | None = "d35fa82c7e19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("ward_fresh_sighting_credits") as batch:
        batch.add_column(sa.Column("visible_seconds", sa.Float(), nullable=True))
        batch.add_column(sa.Column("lost_x", sa.Float(), nullable=True))
        batch.add_column(sa.Column("lost_y", sa.Float(), nullable=True))
        batch.add_column(sa.Column("lost_z", sa.Float(), nullable=True))

    op.execute(
        """
        UPDATE ward_fresh_sighting_credits AS credit
        SET visible_seconds = event.visible_seconds,
            lost_x = event.lost_x,
            lost_y = event.lost_y,
            lost_z = event.lost_z
        FROM fresh_sighting_events AS event
        WHERE event.id = credit.event_id
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
        SELECT route.event_id, credit.ward_id, route.sequence,
               route.time_seconds, route.x, route.y, route.z
        FROM fresh_sighting_route_points AS route
        JOIN ward_fresh_sighting_credits AS credit
          ON credit.event_id = route.event_id
        """
    )
    op.drop_table("fresh_sighting_route_points")
    op.rename_table("fresh_sighting_route_points_v2", "fresh_sighting_route_points")

    with op.batch_alter_table("fresh_sighting_events") as batch:
        batch.drop_column("lost_z")
        batch.drop_column("lost_y")
        batch.drop_column("lost_x")
        batch.drop_column("visible_seconds")


def downgrade() -> None:
    with op.batch_alter_table("fresh_sighting_events") as batch:
        batch.add_column(sa.Column("visible_seconds", sa.Float(), nullable=True))
        batch.add_column(sa.Column("lost_x", sa.Float(), nullable=True))
        batch.add_column(sa.Column("lost_y", sa.Float(), nullable=True))
        batch.add_column(sa.Column("lost_z", sa.Float(), nullable=True))

    op.create_table(
        "fresh_sighting_route_points_v1",
        sa.Column("event_id", sa.BigInteger(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("time_seconds", sa.Float(), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("z", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["fresh_sighting_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id", "sequence"),
    )
    op.execute(
        """
        INSERT INTO fresh_sighting_route_points_v1
            (event_id, sequence, time_seconds, x, y, z)
        SELECT DISTINCT ON (event_id, sequence)
               event_id, sequence, time_seconds, x, y, z
        FROM fresh_sighting_route_points
        ORDER BY event_id, sequence, ward_id
        """
    )
    op.drop_table("fresh_sighting_route_points")
    op.rename_table("fresh_sighting_route_points_v1", "fresh_sighting_route_points")

    with op.batch_alter_table("ward_fresh_sighting_credits") as batch:
        batch.drop_column("lost_z")
        batch.drop_column("lost_y")
        batch.drop_column("lost_x")
        batch.drop_column("visible_seconds")
