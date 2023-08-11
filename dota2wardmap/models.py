from sqlalchemy import String, Integer, BigInteger, SmallInteger, Boolean, ForeignKey
from sqlalchemy.orm import mapped_column, relationship

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate


db = SQLAlchemy()
migrate = Migrate()


class Leagues(db.Model):
    id = mapped_column(Integer, primary_key=True, nullable=False)
    name = mapped_column(String)

    matches = relationship('Matches', back_populates='league')


class Tournaments(db.Model):
    id = mapped_column(Integer, primary_key=True, nullable=False)

    matches = relationship('Matches', back_populates='tournament')


class Matches(db.Model):
    id = mapped_column(BigInteger, primary_key=True, nullable=False)
    league_id = mapped_column(Integer, ForeignKey('leagues.id'))
    tournament_id = mapped_column(Integer, ForeignKey('tournaments.id')
                                  )
    league = relationship('Leagues', back_populates='matches')
    tournament = relationship('Tournaments', back_populates='matches')
    wards = relationship('Wards', back_populates='match')


class Wards(db.Model):
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id = mapped_column(BigInteger, ForeignKey('matches.id'))
    player_placed_id = mapped_column(BigInteger, nullable=False)
    player_destroyed_id = mapped_column(BigInteger)
    is_obs = mapped_column(Boolean, nullable=False)
    is_radiant = mapped_column(Boolean, nullable=False)
    time_placed = mapped_column(SmallInteger, nullable=False)
    duration = mapped_column(SmallInteger, nullable=False)
    x_pos = mapped_column(SmallInteger, nullable=False)
    y_pos = mapped_column(SmallInteger, nullable=False)
    radiant_networth_lead = mapped_column(Integer)

    match = relationship('Matches', back_populates='wards')


if __name__ == '__main__':
    db.create_all()

