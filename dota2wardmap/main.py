import sqlalchemy as sa
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


def main():
    import pandas as pd
    import numpy as np
    import time
    from sklearn.cluster import DBSCAN, HDBSCAN
    with db.session() as session:
        start_time = time.time()
        wards = session.execute(
            select(Wards.x_pos, Wards.y_pos, Wards.z_pos, Wards.is_obs, Wards.is_radiant, Wards.time_placed, Wards.duration, Wards.radiant_networth, Wards.dire_networth).where(
                sa.and_(Wards.is_obs))).all()
        print(time.time() - start_time)
        start_time = time.time()

        df = pd.DataFrame(wards)
        print(len(wards))
        dbscan = DBSCAN(
                        min_samples=100,
                        metric='euclidean',
                        )
        dbscan.fit_predict(df[['x_pos', 'y_pos']])
        # print(dbscan.labels_)
        labels_unique = np.unique(dbscan.labels_)
        labels_unique = labels_unique[labels_unique != -1]
        # print(dbscan.labels_, labels_unique)
        print(time.time() - start_time)

        start_time = time.time()
        import matplotlib.pyplot as plt
        for label in labels_unique:
            label_arg = np.argwhere(dbscan.labels_ == label).ravel()
            df_label_cluster = df.iloc[label_arg]
            # print(df_label_cluster)
            # print(f'{df_label_cluster["x_pos"].mean():.2f}')
            # print(f'{len(df_label_cluster):}')
            plt.scatter(df_label_cluster['x_pos'], df_label_cluster['y_pos'], s=1)
        plt.show()
        print(time.time() - start_time)

        # names = ('x', 'y', 'is_radiant', 'radiant_lead')
        # dtype = dict(names=names, format=[int, int, int, int])
        # wards_np = np.fromiter(wards, dtype=dtype)
        # print(wards_np)
        # print(np.array_repr(wards_np))
