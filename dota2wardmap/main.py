import os
import json

import numpy as np
import pandas as pd
from sklearn.cluster import HDBSCAN

import sqlalchemy as sa
from sqlalchemy import select

from definitions import db, redis_store
from models import Wards, Matches


def perform_clustering(
        cluster_selection_epsilon=70,
        min_samples=5,
        min_cluster_size=5,
        cluster_selection_method='eom',
        n_jobs=-1,
):
    df = pd.DataFrame(pd.read_sql(
        sql=select(Wards, Matches).join(Matches).where(sa.and_(Wards.is_obs, Matches.league_id == 15728)).order_by(
            Matches.id.desc()),
        con=db.engine
    ))

    hdbscan = HDBSCAN(
        cluster_selection_epsilon=int(cluster_selection_epsilon),
        min_samples=int(min_samples),
        min_cluster_size=int(min_cluster_size),
        cluster_selection_method=cluster_selection_method,
        n_jobs=int(n_jobs),
    )
    hdbscan.fit(df[['x_pos', 'y_pos']])

    df['cluster_id'] = hdbscan.labels_
    df['duration'] = df[['duration', 'duration_1', 'time_placed']].apply(lambda row: min(row['duration'], row['duration_1'] - row['time_placed']), axis=1)
    df['advantage'] = df[['is_radiant', 'radiant_networth', 'dire_networth']].apply(lambda row: (row['radiant_networth'] - row['dire_networth']) if row['is_radiant'] else (row['dire_networth'] - row['radiant_networth']), axis=1)

    grouped = df.groupby(['cluster_id', 'is_radiant']).agg({
        'x_pos': lambda x: round(x.mean()),
        'y_pos': lambda x: round(x.mean()),
        'z_pos': lambda x: x.mode().iloc[0],  # - 16384,
        'duration': lambda x: round(x.mean()),
        'time_placed': lambda x: round(x.mean()),
        'advantage': lambda x: round(x.mean()),
        'is_destroyed': 'sum'
    })
    grouped['amount'] = df.groupby(['cluster_id', 'is_radiant']).size()

    redis_store.delete('clusters')
    for i in range(len(set(hdbscan.labels_)) - 1):
        current = grouped.loc[i]
        wards = df[df['cluster_id'] == i]

        interval = 60 * 5
        bins = [*range(-interval, 13 * interval, interval), 99999]
        cuts = pd.cut(wards['time_placed'], bins=bins).value_counts().sort_index().tolist()

        cluster = {
            'cluster_id': i,
            'x_pos': round(current['x_pos'].mean()),
            'y_pos': round(current['y_pos'].mean()),
            'z_pos': round(current['z_pos'].mean()),
            'radiant': {
                'amount': current.loc[True]['amount'],
                'destroyed': current.loc[True]['is_destroyed'],
                'advantage': current.loc[True]['advantage'],
                'duration': current.loc[True]['duration'],
                'time_placed': current.loc[True]['time_placed']
            } if True in current.index else None,
            'dire': {
                'amount': current.loc[False]['amount'],
                'destroyed': current.loc[False]['is_destroyed'],
                'advantage': current.loc[False]['advantage'],
                'duration': current.loc[False]['duration'],
                'time_placed': current.loc[False]['time_placed']
            } if False in current.index else None,
            'all': {
                'amount': current['amount'].sum(),
                'destroyed': current['is_destroyed'].sum(),
                'advantage': None,
                'duration': round(current['duration'].mean()),
                'time_placed': round(current['time_placed'].mean())
            },
            'graphs': {
                'wards': cuts
            }
        }
        redis_store.rpush('clusters', json.dumps(cluster, allow_nan=False, default=int))

    average_df = grouped.reset_index('is_radiant')
    average_radiant = average_df[average_df['is_radiant'] == True]
    average_dire = average_df[average_df['is_radiant'] == False]
    average = {
        'cluster_id': -1,
        'radiant': {
            'advantage': round(average_radiant['advantage'].mean()),
            'duration': round(average_radiant['duration'].mean()),
        },
        'dire': {
            'advantage': round(average_dire['advantage'].mean()),
            'duration': round(average_dire['duration'].mean()),
        },
        'all': {
            'advantage': None,
            'duration': round(average_df['duration'].mean()),
        }
    }
    redis_store.rpush('clusters', json.dumps(average, allow_nan=False, default=int))

#     metadata = {
#         'clustering': {
#             'algorithm': 'HDBSCAN',
#             'cluster_selection_method': 'eom',
#             'cluster_selection_epsilon': 64,
#             'min_cluster_size': 5,
#         },
#         'league_id': 15728,
#         'ward_type': 'obs',
#         'matches_amount': matches_amount,
#         'total_entries': initial_data_length,
#         'entries_in_dataset': int(result_df['amount'].sum())
#     }
#     redis_store.set('metadata', json.dumps(metadata))