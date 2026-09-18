from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..domain import JobStatus
from ..extensions import db


class ReplayJob(db.Model):
    __tablename__ = "replay_jobs"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed')", name="ck_replay_jobs_status"),
        Index("ix_replay_jobs_claim", "status", "next_attempt_at", "created_at"),
    )

    match_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=JobStatus.PENDING, index=True)
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __init__(self, match_id: int) -> None:
        self.match_id = match_id
