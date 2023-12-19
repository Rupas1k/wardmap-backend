from sqlalchemy import Column, String, Integer, BigInteger, SmallInteger, Boolean, ForeignKey
from sqlalchemy.orm import mapped_column, relationship

from extensions import db

players_matches = db.Table('players_matches', db.metadata,
                           Column('player_id', Integer, ForeignKey('players.id'), primary_key=True),
                           Column('match_id', BigInteger, ForeignKey('matches.id'), primary_key=True)
                           )

players_leagues = db.Table('players_leagues', db.metadata,
                           Column('player_id', Integer, ForeignKey('players.id'), primary_key=True),
                           Column('league_id', BigInteger, ForeignKey('leagues.id'), primary_key=True)
                           )

class Leagues(db.Model):
    id = mapped_column(Integer, primary_key=True, nullable=False)
    name = mapped_column(String)

    matches = relationship('Matches', back_populates='league')
    maps = relationship('Maps', back_populates='league')
    players = relationship('Players', secondary=players_leagues, back_populates='leagues')


class Matches(db.Model):
    id = mapped_column(BigInteger, primary_key=True, nullable=False)
    league_id = mapped_column(Integer, ForeignKey('leagues.id'))
    duration = mapped_column(SmallInteger)
    region = mapped_column(SmallInteger)
    date = mapped_column(BigInteger)
    game_version = mapped_column(SmallInteger)

    league = relationship('Leagues', back_populates='matches')
    wards = relationship('Wards', back_populates='match')
    players = relationship('Players', secondary=players_matches, back_populates='matches')


class Wards(db.Model):
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id = mapped_column(BigInteger, ForeignKey('matches.id'))
    is_obs = mapped_column(Boolean, nullable=False)
    is_radiant = mapped_column(Boolean, nullable=True)
    is_destroyed = mapped_column(Boolean, nullable=False)
    is_post_game = mapped_column(Boolean, nullable=False)
    player_placed_id = mapped_column(Integer, ForeignKey('players.id'))
    player_destroyed_id = mapped_column(Integer, ForeignKey('players.id'))
    time_placed = mapped_column(SmallInteger, nullable=False)
    duration = mapped_column(SmallInteger, nullable=False)

    x_pos = mapped_column(SmallInteger, nullable=False)
    y_pos = mapped_column(SmallInteger, nullable=False)
    z_pos = mapped_column(SmallInteger, nullable=False)

    radiant_networth = mapped_column(Integer, nullable=True)
    dire_networth = mapped_column(Integer, nullable=True)

    match = relationship('Matches', back_populates='wards')
    player_placed = relationship('Players', foreign_keys=[player_placed_id], back_populates='wards_placed')
    player_destroyed = relationship('Players', foreign_keys=[player_destroyed_id], back_populates='wards_destroyed')


class Players(db.Model):
    id = mapped_column(Integer, primary_key=True)
    name = mapped_column(String, nullable=True)

    wards_placed = relationship('Wards', foreign_keys=[Wards.player_placed_id], back_populates='player_placed')
    wards_destroyed = relationship('Wards', foreign_keys=[Wards.player_destroyed_id], back_populates='player_destroyed')

    matches = relationship('Matches', secondary=players_matches, back_populates='players')
    leagues = relationship('Leagues', secondary=players_leagues, back_populates='players')

class Maps(db.Model):
    # id = mapped_column(Integer, primary_key=True, autoincrement=True)
    league_id = mapped_column(Integer, ForeignKey('leagues.id'), primary_key=True)
    public = mapped_column(Boolean)
    min_cluster_size = mapped_column(SmallInteger)
    min_samples = mapped_column(SmallInteger)
    cluster_selection_epsilon = mapped_column(SmallInteger)
    cluster_selection_method = mapped_column(String)
    version = mapped_column(SmallInteger)

    league = relationship('Leagues', back_populates='maps')
