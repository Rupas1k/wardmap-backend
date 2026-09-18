from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..domain import LeagueTrackingStatus
from ..extensions import db

players_matches = db.Table(
    "players_matches",
    db.metadata,
    Column("player_id", BigInteger, ForeignKey("players.id"), primary_key=True),
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
    player_placed_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("players.id"), index=True)
    player_destroyed_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("players.id"))
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
    scouting_tracking_seconds: Mapped[float | None] = mapped_column(Float)
    scouting_discovery_seconds: Mapped[float | None] = mapped_column(Float)
    scouting_score: Mapped[float | None] = mapped_column(Float)
    scouting_version: Mapped[int | None] = mapped_column(SmallInteger)
    scouting_tau_seconds: Mapped[float | None] = mapped_column(Float)
    scouting_complete: Mapped[bool | None] = mapped_column(Boolean)
    measurement_version: Mapped[int | None] = mapped_column(SmallInteger)
    measurement_revision: Mapped[int | None] = mapped_column(SmallInteger)
    added_vision_seconds: Mapped[float | None] = mapped_column(Float)
    fresh_sightings: Mapped[float | None] = mapped_column(Float)
    fresh_sighting_threshold_seconds: Mapped[float | None] = mapped_column(Float)
    vision_measured_seconds: Mapped[float | None] = mapped_column(Float)
    vision_possible_seconds: Mapped[float | None] = mapped_column(Float)
    vision_coverage: Mapped[float | None] = mapped_column(Float)
    placed_at_seconds: Mapped[float | None] = mapped_column(Float)
    ended_at_seconds: Mapped[float | None] = mapped_column(Float)
    outcome: Mapped[str | None] = mapped_column(String(24), index=True)
    outcome_reason: Mapped[str | None] = mapped_column(String(32))
    vision_complete: Mapped[bool | None] = mapped_column(Boolean)
    measurement_evidence: Mapped[dict[str, object] | None] = mapped_column(JSON(none_as_null=True))

    npc_killed: Mapped[str | None] = mapped_column(String)

    match: Mapped[Match | None] = relationship(back_populates="wards")
    player_placed: Mapped[Player | None] = relationship(foreign_keys=[player_placed_id], back_populates="wards_placed")
    player_destroyed: Mapped[Player | None] = relationship(
        foreign_keys=[player_destroyed_id], back_populates="wards_destroyed"
    )


class Player(db.Model):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
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


class FreshSightingEvent(db.Model):
    __tablename__ = "fresh_sighting_events"
    __table_args__ = (
        UniqueConstraint("match_id", "sample_tick", "target_player_slot", name="uq_fresh_sighting_match_tick_slot"),
        Index("ix_fresh_sighting_target_time", "target_player_id", "time_seconds"),
        Index("ix_fresh_sighting_hero_time", "target_hero_name", "time_seconds"),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    sample_tick: Mapped[int] = mapped_column(Integer, nullable=False)
    time_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    target_player_slot: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    target_steam_id: Mapped[str | None] = mapped_column(String(20))
    target_player_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("players.id"), index=True)
    target_hero_name: Mapped[str] = mapped_column(String(96), nullable=False)
    target_is_radiant: Mapped[bool] = mapped_column(Boolean, nullable=False)
    target_x: Mapped[float] = mapped_column(Float, nullable=False)
    target_y: Mapped[float] = mapped_column(Float, nullable=False)
    target_z: Mapped[float] = mapped_column(Float, nullable=False)
    hidden_seconds: Mapped[float] = mapped_column(Float, nullable=False)

    def __init__(
        self,
        match_id: int,
        sample_tick: int,
        time_seconds: float,
        target_player_slot: int,
        target_steam_id: str | None,
        target_player_id: int | None,
        target_hero_name: str,
        target_is_radiant: bool,
        target_x: float,
        target_y: float,
        target_z: float,
        hidden_seconds: float,
    ) -> None:
        self.match_id = match_id
        self.sample_tick = sample_tick
        self.time_seconds = time_seconds
        self.target_player_slot = target_player_slot
        self.target_steam_id = target_steam_id
        self.target_player_id = target_player_id
        self.target_hero_name = target_hero_name
        self.target_is_radiant = target_is_radiant
        self.target_x = target_x
        self.target_y = target_y
        self.target_z = target_z
        self.hidden_seconds = hidden_seconds


class WardFreshSightingCredit(db.Model):
    __tablename__ = "ward_fresh_sighting_credits"

    event_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("fresh_sighting_events.id", ondelete="CASCADE"),
        primary_key=True,
    )
    ward_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("wards.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    credit: Mapped[float] = mapped_column(Float, nullable=False)

    def __init__(self, event_id: int, ward_id: int, credit: float) -> None:
        self.event_id = event_id
        self.ward_id = ward_id
        self.credit = credit


class WardSightingSegment(db.Model):
    __tablename__ = "ward_sighting_segments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["event_id", "ward_id"],
            ["ward_fresh_sighting_credits.event_id", "ward_fresh_sighting_credits.ward_id"],
            ondelete="CASCADE",
        ),
    )

    event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ward_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    time_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    gap_seconds: Mapped[float | None] = mapped_column(Float)
    start_x: Mapped[float] = mapped_column(Float, nullable=False)
    start_y: Mapped[float] = mapped_column(Float, nullable=False)
    start_z: Mapped[float] = mapped_column(Float, nullable=False)
    visible_seconds: Mapped[float | None] = mapped_column(Float)
    lost_x: Mapped[float | None] = mapped_column(Float)
    lost_y: Mapped[float | None] = mapped_column(Float)
    lost_z: Mapped[float | None] = mapped_column(Float)

    def __init__(
        self,
        event_id: int,
        ward_id: int,
        sequence: int,
        time_seconds: float,
        gap_seconds: float | None,
        start_x: float,
        start_y: float,
        start_z: float,
        visible_seconds: float | None,
        lost_x: float | None,
        lost_y: float | None,
        lost_z: float | None,
    ) -> None:
        self.event_id = event_id
        self.ward_id = ward_id
        self.sequence = sequence
        self.time_seconds = time_seconds
        self.gap_seconds = gap_seconds
        self.start_x = start_x
        self.start_y = start_y
        self.start_z = start_z
        self.visible_seconds = visible_seconds
        self.lost_x = lost_x
        self.lost_y = lost_y
        self.lost_z = lost_z


class FreshSightingRoutePoint(db.Model):
    __tablename__ = "fresh_sighting_route_points"
    __table_args__ = (
        ForeignKeyConstraint(
            ["event_id", "ward_id", "segment_sequence"],
            ["ward_sighting_segments.event_id", "ward_sighting_segments.ward_id", "ward_sighting_segments.sequence"],
            ondelete="CASCADE",
        ),
    )

    event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ward_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    segment_sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    time_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    z: Mapped[float] = mapped_column(Float, nullable=False)

    def __init__(
        self,
        event_id: int,
        ward_id: int,
        segment_sequence: int,
        sequence: int,
        time_seconds: float,
        x: float,
        y: float,
        z: float,
    ) -> None:
        self.event_id = event_id
        self.ward_id = ward_id
        self.segment_sequence = segment_sequence
        self.sequence = sequence
        self.time_seconds = time_seconds
        self.x = x
        self.y = y
        self.z = z
