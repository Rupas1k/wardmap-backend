import sqlalchemy as sa
from sqlalchemy import select

from models import db, Matches, Wards, Leagues


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
