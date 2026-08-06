from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .domain import AccessLevel, JobStatus, LeagueTrackingStatus
from .extensions import db

players_matches = db.Table(
    "players_matches",
    db.metadata,
    Column("player_id", Integer, ForeignKey("players.id"), primary_key=True),
    Column("match_id", BigInteger, ForeignKey("matches.id"), primary_key=True),
)


class League(db.Model):
    __tablename__ = "leagues"
    __table_args__ = (
        CheckConstraint(
            "tracking_status IN ('active', 'paused', 'completed')",
            name="ck_leagues_tracking_status",
        ),
        Index("ix_leagues_collection_schedule", "tracking_status", "next_check_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String)
    tier: Mapped[str | None] = mapped_column(String(32))
    map_asset_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    tracking_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=LeagueTrackingStatus.ACTIVE
    )
    first_match_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_match_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_empty_checks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    matches: Mapped[list[Match]] = relationship(back_populates="league")

    def __init__(self, id: int, name: str | None = None) -> None:
        self.id = id
        self.name = name


class Match(db.Model):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    league_id: Mapped[int | None] = mapped_column(ForeignKey("leagues.id"), index=True)
    duration: Mapped[int | None] = mapped_column(SmallInteger)
    region: Mapped[int | None] = mapped_column(SmallInteger)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    game_version: Mapped[int | None] = mapped_column(SmallInteger)

    league: Mapped[League | None] = relationship(back_populates="matches")
    wards: Mapped[list[Ward]] = relationship(back_populates="match")
    players: Mapped[list[Player]] = relationship(secondary=players_matches, back_populates="matches")

    def __init__(
        self,
        id: int,
        league_id: int | None = None,
        duration: int | None = None,
        region: int | None = None,
        started_at: datetime | None = None,
        game_version: int | None = None,
    ) -> None:
        self.id = id
        self.league_id = league_id
        self.duration = duration
        self.region = region
        self.started_at = started_at
        self.game_version = game_version


class Ward(db.Model):
    __tablename__ = "wards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"), index=True)
    is_obs: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_radiant: Mapped[bool | None] = mapped_column(Boolean)
    is_destroyed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_post_game: Mapped[bool] = mapped_column(Boolean, nullable=False)
    player_placed_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"), index=True)
    player_destroyed_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"))
    time_placed: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    duration: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    x_pos: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    y_pos: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    z_pos: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    radiant_networth: Mapped[int | None] = mapped_column(Integer)
    dire_networth: Mapped[int | None] = mapped_column(Integer)

    npc_killed: Mapped[str | None] = mapped_column(String)

    match: Mapped[Match | None] = relationship(back_populates="wards")
    player_placed: Mapped[Player | None] = relationship(foreign_keys=[player_placed_id], back_populates="wards_placed")
    player_destroyed: Mapped[Player | None] = relationship(
        foreign_keys=[player_destroyed_id], back_populates="wards_destroyed"
    )


class Player(db.Model):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String)

    wards_placed: Mapped[list[Ward]] = relationship(
        foreign_keys=[Ward.player_placed_id], back_populates="player_placed"
    )
    wards_destroyed: Mapped[list[Ward]] = relationship(
        foreign_keys=[Ward.player_destroyed_id], back_populates="player_destroyed"
    )

    matches: Mapped[list[Match]] = relationship(secondary=players_matches, back_populates="players")

    def __init__(self, id: int, name: str | None = None) -> None:
        self.id = id
        self.name = name


class ReplayJob(db.Model):
    __tablename__ = "replay_jobs"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed')", name="ck_replay_jobs_status"),
        Index("ix_replay_jobs_claim", "status", "created_at"),
    )

    match_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=JobStatus.PENDING, index=True)
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __init__(self, match_id: int) -> None:
        self.match_id = match_id


class ClusteringJob(db.Model):
    __tablename__ = "clustering_jobs"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed')", name="ck_clustering_jobs_status"),
        Index("ix_clustering_jobs_claim", "status", "available_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=JobStatus.PENDING, index=True)
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    def __init__(self, parameters: dict[str, Any] | None = None, available_at: datetime | None = None) -> None:
        if parameters is not None:
            self.parameters = parameters
        if available_at is not None:
            self.available_at = available_at


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
