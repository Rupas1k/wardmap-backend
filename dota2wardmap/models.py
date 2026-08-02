from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Column, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .extensions import db

players_matches = db.Table(
    "players_matches",
    db.metadata,
    Column("player_id", Integer, ForeignKey("players.id"), primary_key=True),
    Column("match_id", BigInteger, ForeignKey("matches.id"), primary_key=True),
)

players_leagues = db.Table(
    "players_leagues",
    db.metadata,
    Column("player_id", Integer, ForeignKey("players.id"), primary_key=True),
    Column("league_id", Integer, ForeignKey("leagues.id"), primary_key=True),
)


class Leagues(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String)

    matches: Mapped[list[Matches]] = relationship(back_populates="league")
    maps: Mapped[list[Maps]] = relationship(back_populates="league")
    players: Mapped[list[Players]] = relationship(secondary=players_leagues, back_populates="leagues")

    def __init__(self, id: int, name: str | None = None) -> None:
        self.id = id
        self.name = name


class Matches(db.Model):
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    league_id: Mapped[int | None] = mapped_column(ForeignKey("leagues.id"))
    duration: Mapped[int | None] = mapped_column(SmallInteger)
    region: Mapped[int | None] = mapped_column(SmallInteger)
    date: Mapped[int | None] = mapped_column(BigInteger)
    game_version: Mapped[int | None] = mapped_column(SmallInteger)

    league: Mapped[Leagues | None] = relationship(back_populates="matches")
    wards: Mapped[list[Wards]] = relationship(back_populates="match")
    players: Mapped[list[Players]] = relationship(secondary=players_matches, back_populates="matches")

    def __init__(
        self,
        id: int,
        league_id: int | None = None,
        duration: int | None = None,
        region: int | None = None,
        date: int | None = None,
        game_version: int | None = None,
    ) -> None:
        self.id = id
        self.league_id = league_id
        self.duration = duration
        self.region = region
        self.date = date
        self.game_version = game_version


class Wards(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"))
    is_obs: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_radiant: Mapped[bool | None] = mapped_column(Boolean)
    is_destroyed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_post_game: Mapped[bool] = mapped_column(Boolean, nullable=False)
    player_placed_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"))
    player_destroyed_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"))
    time_placed: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    duration: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    x_pos: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    y_pos: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    z_pos: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    radiant_networth: Mapped[int | None] = mapped_column(Integer)
    dire_networth: Mapped[int | None] = mapped_column(Integer)

    npc_killed: Mapped[str | None] = mapped_column(String)

    match: Mapped[Matches | None] = relationship(back_populates="wards")
    player_placed: Mapped[Players | None] = relationship(foreign_keys=[player_placed_id], back_populates="wards_placed")
    player_destroyed: Mapped[Players | None] = relationship(
        foreign_keys=[player_destroyed_id], back_populates="wards_destroyed"
    )


class Players(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String)

    wards_placed: Mapped[list[Wards]] = relationship(
        foreign_keys=[Wards.player_placed_id], back_populates="player_placed"
    )
    wards_destroyed: Mapped[list[Wards]] = relationship(
        foreign_keys=[Wards.player_destroyed_id], back_populates="player_destroyed"
    )

    matches: Mapped[list[Matches]] = relationship(secondary=players_matches, back_populates="players")
    leagues: Mapped[list[Leagues]] = relationship(secondary=players_leagues, back_populates="players")

    def __init__(self, id: int, name: str | None = None) -> None:
        self.id = id
        self.name = name


class Maps(db.Model):
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"), primary_key=True)
    is_obs: Mapped[bool] = mapped_column(Boolean, primary_key=True)
    public: Mapped[bool | None] = mapped_column(Boolean)
    min_cluster_size: Mapped[int | None] = mapped_column(SmallInteger)
    min_samples: Mapped[int | None] = mapped_column(SmallInteger)
    cluster_selection_epsilon: Mapped[int | None] = mapped_column(SmallInteger)
    cluster_selection_method: Mapped[str | None] = mapped_column(String)
    version: Mapped[int | None] = mapped_column(SmallInteger)

    league: Mapped[Leagues] = relationship(back_populates="maps")
