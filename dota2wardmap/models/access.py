from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..domain import AccessLevel
from ..extensions import db


class ApiKey(db.Model):
    __tablename__ = "api_keys"
    __table_args__ = (CheckConstraint("access_level IN ('advanced', 'admin')", name="ck_api_keys_access_level"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    access_level: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    def __init__(
        self,
        owner: str | None = None,
        key_prefix: str | None = None,
        key_hash: str | None = None,
        access_level: AccessLevel | None = None,
    ) -> None:
        if owner is not None:
            self.owner = owner
        if key_prefix is not None:
            self.key_prefix = key_prefix
        if key_hash is not None:
            self.key_hash = key_hash
        if access_level is not None:
            self.access_level = access_level
