import os
import json

import numpy as np
import pandas as pd
from sklearn.cluster import HDBSCAN
import matplotlib.pyplot as plt

import sqlalchemy as sa
from sqlalchemy import select

from definitions import db, redis_store
from models import Wards, Matches


def perform_clustering():
    df = pd.DataFrame(pd.read_sql(
        sql=select(Wards, Matches).join(Matches).where(sa.and_(Wards.is_obs, Matches.league_id == 15728)).order_by(
            Matches.id.desc()),
        con=db.engine
    ))

    hdbscan = HDBSCAN(
        cluster_selection_epsilon=70,
        min_samples=5,
        min_cluster_size=5,
        cluster_selection_method='eom',
        n_jobs=-1,
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


# def perform_clustering_legacy():
#     query = select(Wards, Matches).join(Matches).where(sa.and_(Wards.is_obs, Matches.league_id == 15728)).order_by(Matches.id.desc())
#
#     data = db.session.execute(query).all()
#
#     for i, row in enumerate(data):
#         if row.Wards.is_post_game:
#             data[i].Wards.duration = min(row.Wards.duration, row.Matches.duration - row.Wards.time_placed)
#
#     wards = [row[0].__dict__ for row in data]
#     matches = [row[1].__dict__ for row in data]
#
#
#     initial_data_length = len(data)
#     matches_amount = len(set(row.Matches.id for row in data))
#
#
#     df = pd.DataFrame(wards)
#
#     hdbscan = HDBSCAN(
#         cluster_selection_epsilon=int(os.environ['CLUSTER_SELECTION_EPSILON']),
#         min_samples=int(os.environ['MIN_SAMPLES']),
#         min_cluster_size=int(os.environ['MIN_CLUSTER_SIZE']),
#         cluster_selection_method=os.environ['CLUSTER_SELECTION_METHOD'],
#         n_jobs=int(os.environ['N_JOBS']),
#     )
#
#     hdbscan.fit(df[['x_pos', 'y_pos']])
#     unique = np.unique(hdbscan.labels_[hdbscan.labels_ != -1])
#
#     raw_clusters = [
#         df.iloc[np.argwhere(hdbscan.labels_ == label).ravel()].to_dict(orient='records')
#         for label in unique
#     ]
#
#     data = [
#         {'cluster_id': cluster_id, **record}
#         for cluster_id, cluster_data in enumerate(raw_clusters)
#         for record in cluster_data
#     ]
#
#     df = pd.DataFrame(data)
#
#     df['radiant_advantage'] = df[df['is_radiant'] == True][['radiant_networth', 'dire_networth']].apply(lambda row: row['radiant_networth'] - row['dire_networth'], axis=1)
#     df['dire_advantage'] = df[df['is_radiant'] == False][['radiant_networth', 'dire_networth']].apply(lambda row: row['dire_networth'] - row['radiant_networth'], axis=1)
#
#     df['destroyed_radiant'] = df[df['is_radiant'] == True]['is_destroyed']
#     df['destroyed_dire'] = df[df['is_radiant'] == False]['is_destroyed']
#
#     df['duration_radiant'] = df[df['is_radiant'] == True]['duration']
#     df['duration_dire'] = df[df['is_radiant'] == False]['duration']
#
#     df['time_placed_radiant'] = df[df['is_radiant'] == True]['time_placed']
#     df['time_placed_dire'] = df[df['is_radiant'] == False]['time_placed']
#
#     agg_functions = {
#         'x_pos': 'mean',
#         'y_pos': 'mean',
#         'z_pos': lambda x: x.mode().iloc[0], #- 16384,
#         'duration': 'mean',
#         'time_placed': 'mean',
#         'radiant_advantage': 'mean',
#         'dire_advantage': 'mean',
#         'destroyed_radiant': 'sum',
#         'destroyed_dire': 'sum',
#         'duration_radiant': 'mean',
#         'duration_dire': 'mean',
#         'time_placed_radiant': 'mean',
#         'time_placed_dire': 'mean',
#         'is_radiant': 'sum',
#         'is_destroyed': 'sum'
#     }
#
#     grouped = df.groupby('cluster_id')
#
#     group_sizes = grouped.size().reset_index(name='amount')
#
#     result_df = (
#         df.groupby('cluster_id')
#         .agg(agg_functions)
#         .round()
#         .astype({'x_pos': int,
#                  'y_pos': int,
#                  'z_pos': int,
#                  'duration': int,
#                  'time_placed': int})
#         .merge(group_sizes, on='cluster_id', how='inner')
#     )
#
#     result_df = result_df.replace({np.nan: None})
#
#     df['duration'].plot.hist()
#     plt.show()
#
#     average = {
#         'cluster_id': -1,
#         'radiant': {
#             'amount': round(result_df['is_radiant'].mean()),
#             'destroyed': round(result_df['destroyed_radiant'].mean()),
#             'advantage': round(result_df['radiant_advantage'].mean()),
#             'duration': round(result_df['duration_radiant'].mean()),
#             'time_placed': round(result_df['time_placed_radiant'].mean())
#         },
#         'dire': {
#             'amount': round(result_df['amount'].mean() - result_df['is_radiant'].mean()),
#             'destroyed': round(result_df['destroyed_dire'].mean()),
#             'advantage': round(result_df['dire_advantage'].mean()),
#             'duration': round(result_df['duration_dire'].mean()),
#             'time_placed': round(result_df['time_placed_dire'].mean())
#         },
#         'all': {
#             'amount': round(result_df['amount'].mean()),
#             'destroyed': round(result_df['is_destroyed'].mean()),
#             'advantage': None,
#             'duration': round(result_df['duration'].mean()),
#             'time_placed': round(result_df['time_placed'].mean())
#         },
#     }
#
#     players_placed = df.groupby(['cluster_id', 'player_placed_id']).size()
#
#     redis_store.delete('clusters')
#     for cluster in result_df.to_dict(orient='records'):
#
#         interval = 60 * 5
#         wards = df[['cluster_id', 'time_placed', 'time_placed_radiant', 'time_placed_dire']][df['cluster_id'] == cluster['cluster_id']]
#         bins = list(range(-interval, 13 * interval, interval))
#         bins.append(99999)
#         cuts = pd.cut(wards['time_placed'], bins=bins).value_counts().sort_index().tolist()
#
#         this_players = players_placed.loc[cluster['cluster_id']].sort_values(ascending=False).head(5)
#         this_players.name = 'amount'
#         this_players = this_players.reset_index().astype('uint32').to_dict(orient='records')
#
#         new_dict = {
#             'cluster_id': cluster['cluster_id'],
#             'x_pos': cluster['x_pos'],
#             'y_pos': cluster['y_pos'],
#             'z_pos': cluster['z_pos'],
#             'players': this_players,
#             'radiant': {
#                 'amount': cluster['is_radiant'],
#                 'destroyed': int(cluster['destroyed_radiant']),
#                 'advantage': cluster['radiant_advantage'],
#                 'duration': cluster['duration_radiant'],
#                 'time_placed': cluster['time_placed_radiant']
#             },
#             'dire': {
#                 'amount': cluster['amount'] - cluster['is_radiant'],
#                 'destroyed': int(cluster['destroyed_dire']),
#                 'advantage': cluster['dire_advantage'],
#                 'duration': cluster['duration_dire'],
#                 'time_placed': cluster['time_placed_dire']
#             },
#             'all': {
#                 'amount': cluster['amount'],
#                 'destroyed': int(cluster['is_destroyed']),
#                 'advantage': None,
#                 'duration': cluster['duration'],
#                 'time_placed': cluster['time_placed']
#             },
#             'graphs': {
#                 'wards': cuts
#             }
#         }
#         redis_store.rpush('clusters', json.dumps(new_dict, allow_nan=False, default=int))
#     redis_store.rpush('clusters', json.dumps(average, allow_nan=False, default=int))
#
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
#
#     print(initial_data_length, matches_amount, result_df['amount'].sum())
