"""Fix sighting segment game times.

Revision ID: c31d8e4f72a6
Revises: b79e3a5f12c4
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c31d8e4f72a6"
down_revision: str | None = "b79e3a5f12c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        WITH offsets AS (
            SELECT segment.event_id,
                   segment.ward_id,
                   segment.time_seconds - event.time_seconds AS seconds
            FROM ward_sighting_segments AS segment
            JOIN fresh_sighting_events AS event ON event.id = segment.event_id
            WHERE segment.sequence = 0
        )
        UPDATE fresh_sighting_route_points AS point
        SET time_seconds = point.time_seconds - offsets.seconds
        FROM offsets
        WHERE point.event_id = offsets.event_id
          AND point.ward_id = offsets.ward_id
        """
    )
    op.execute(
        """
        WITH offsets AS (
            SELECT segment.event_id,
                   segment.ward_id,
                   segment.time_seconds - event.time_seconds AS seconds
            FROM ward_sighting_segments AS segment
            JOIN fresh_sighting_events AS event ON event.id = segment.event_id
            WHERE segment.sequence = 0
        )
        UPDATE ward_sighting_segments AS segment
        SET time_seconds = segment.time_seconds - offsets.seconds
        FROM offsets
        WHERE segment.event_id = offsets.event_id
          AND segment.ward_id = offsets.ward_id
        """
    )


def downgrade() -> None:
    pass
