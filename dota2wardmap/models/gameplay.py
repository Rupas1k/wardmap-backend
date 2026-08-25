from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..domain import LeagueTrackingStatus
from ..extensions import db

players_matches = db.Table(
    "players_matches",
    db.metadata,
    Column("player_id", Integer, ForeignKey("players.id"), primary_key=True),
    Column("match_id", BigInteger, ForeignKey("matches.id"), primary_key=True),
    Column("is_radiant", Boolean),
    Index("ix_players_matches_opponent_lookup", "match_id", "is_radiant", "player_id"),
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
    map_asset_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=2)
    tracking_status: Mapped[str] = mapped_column(String(16), nullable=False, default=LeagueTrackingStatus.ACTIVE)
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
    radiant_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), index=True)
    dire_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), index=True)
    radiant_win: Mapped[bool | None] = mapped_column(Boolean)

    league: Mapped[League | None] = relationship(back_populates="matches")
    wards: Mapped[list[Ward]] = relationship(back_populates="match")
    players: Mapped[list[Player]] = relationship(secondary=players_matches, back_populates="matches")
    radiant_team: Mapped[Team | None] = relationship(foreign_keys=[radiant_team_id])
    dire_team: Mapped[Team | None] = relationship(foreign_keys=[dire_team_id])

    def __init__(
        self,
        id: int,
        league_id: int | None = None,
        duration: int | None = None,
        region: int | None = None,
        started_at: datetime | None = None,
        game_version: int | None = None,
        radiant_team_id: int | None = None,
        dire_team_id: int | None = None,
        radiant_win: bool | None = None,
    ) -> None:
        self.id = id
        self.league_id = league_id
        self.duration = duration
        self.region = region
        self.started_at = started_at
        self.game_version = game_version
        self.radiant_team_id = radiant_team_id
        self.dire_team_id = dire_team_id
        self.radiant_win = radiant_win


class Team(db.Model):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255))
    tag: Mapped[str | None] = mapped_column(String(64))
    logo_url: Mapped[str | None] = mapped_column(String(512))
    metadata_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __init__(
        self,
        id: int,
        name: str | None = None,
        tag: str | None = None,
        logo_url: str | None = None,
    ) -> None:
        self.id = id
        self.name = name
        self.tag = tag
        self.logo_url = logo_url


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
    enemy_hero_vision_seconds: Mapped[float | None] = mapped_column(Float)
    unique_enemy_hero_vision_seconds: Mapped[float | None] = mapped_column(Float)
    heroes_spotted: Mapped[int | None] = mapped_column(SmallInteger)
    hero_reveal_events: Mapped[int | None] = mapped_column(SmallInteger)
    unique_hero_reveal_events: Mapped[int | None] = mapped_column(SmallInteger)

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
