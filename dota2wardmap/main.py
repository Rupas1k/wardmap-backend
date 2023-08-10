from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from models import db, Matches, Wards, Leagues

import api


def insert_matches_data(matches: dict):
    with db.session() as session:
        inserted = session.scalars(select(Matches.id).where(Matches.id.in_([match['id'] for match in matches]))).all()
        wards = [ward for match in matches for ward in match['wards'] if match['id'] not in inserted]
        session.execute(insert(Matches).on_conflict_do_nothing(), [{
            'league_id': match['league_id'],
            'id': match['id']
        } for match in matches if match not in inserted])
        if len(wards):
            session.execute(insert(Wards), wards)


def insert_league_matches(league_id: int, step: int, skip=0):
    while True:
        matches = api.fetch_league_games_data(league_id, step, skip)
        if len(matches) == 0:
            break
        insert_matches_data(matches)
        skip += step
    return True


def get_all_matches():
    with db.session() as session:
        return session.scalars(select(Matches.id)).all()


if __name__ == '__main__':
    pass
