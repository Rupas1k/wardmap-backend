# pyright: reportAttributeAccessIssue=false, reportIndexIssue=false

import pandas as pd
import sqlalchemy as sa
from sklearn.cluster import HDBSCAN
from sqlalchemy import select

from .extensions import db
from .models import Matches, Players, Wards

pd.set_option("display.max_columns", None)


def perform_clustering(
    cluster_selection_epsilon=64,
    min_samples=10,
    min_cluster_size=10,
    cluster_selection_method="eom",
    league_id=15910,
    min_match=0,
    is_obs=True,
    n_jobs=-1,
):
    clusters = []

    df = pd.DataFrame(
        pd.read_sql(
            sql=select(Wards, Matches, Players)
            .join(Players, Wards.player_placed)
            .join(Matches)
            .where(sa.and_(Wards.is_obs == is_obs, Matches.league_id == league_id, Matches.id >= min_match))
            .order_by(Matches.id.desc()),
            con=db.engine,
        )
    )

    hdbscan = HDBSCAN(
        cluster_selection_epsilon=int(cluster_selection_epsilon),
        min_samples=int(min_samples),
        min_cluster_size=int(min_cluster_size),
        cluster_selection_method=cluster_selection_method,
        n_jobs=int(n_jobs),
    )
    hdbscan.fit(df[["x_pos", "y_pos"]])

    df["cluster_id"] = hdbscan.labels_
    df["duration"] = df[["duration", "duration_1", "time_placed"]].apply(
        lambda row: min(row["duration"], row["duration_1"] - row["time_placed"]), axis=1
    )
    df["advantage"] = df[["is_radiant", "radiant_networth", "dire_networth"]].apply(
        lambda row: (
            (row["radiant_networth"] - row["dire_networth"])
            if row["is_radiant"]
            else (row["dire_networth"] - row["radiant_networth"])
        ),
        axis=1,
    )

    grouped = df.groupby(["cluster_id", "is_radiant"]).agg(
        {
            "x_pos": lambda x: round(x.mean()),
            "y_pos": lambda x: round(x.mean()),
            "z_pos": lambda x: x.mode().iloc[0],
            "duration": lambda x: round(x.mean()),
            "time_placed": lambda x: round(x.mean()),
            "advantage": lambda x: round(x.mean()),
            "is_destroyed": "sum",
        }
    )
    grouped["amount"] = df.groupby(["cluster_id", "is_radiant"]).size()

    # redis_store.delete('clusters')
    for i in range(len(set(hdbscan.labels_)) - 1):
        current = grouped.loc[i]
        wards = df[df["cluster_id"] == i]

        interval = 60 * 5
        bins = [*range(-interval, 13 * interval, interval), 99999]

        players_dict = (
            wards[["player_placed_id", "name"]]
            .groupby(["player_placed_id", "name"])
            .size()
            .to_frame("amount")
            .sort_values(by="amount", ascending=False)
            .reset_index()
            .to_dict(orient="records")
        )
        radiant_players_dict = (
            wards[["player_placed_id", "name"]][wards["is_radiant"].eq(True)]
            .groupby(["player_placed_id", "name"])
            .size()
            .to_frame("amount")
            .sort_values(by="amount", ascending=False)
            .reset_index()
            .to_dict(orient="records")
        )
        dire_players_dict = (
            wards[["player_placed_id", "name"]][wards["is_radiant"].eq(False)]
            .groupby(["player_placed_id", "name"])
            .size()
            .to_frame("amount")
            .sort_values(by="amount", ascending=False)
            .reset_index()
            .to_dict(orient="records")
        )

        cluster = {
            "cluster_id": i,
            "x_pos": round(current["x_pos"].mean()),
            "y_pos": round(current["y_pos"].mean()),
            "z_pos": round(current["z_pos"].mean()),
            "radiant": {
                "amount": current.loc[True]["amount"],
                "destroyed": current.loc[True]["is_destroyed"],
                "advantage": current.loc[True]["advantage"],
                "duration": current.loc[True]["duration"],
                "time_placed": current.loc[True]["time_placed"],
                "players": radiant_players_dict,
                "graphs": {
                    "wards": {
                        "placed": pd.cut(wards[wards["is_radiant"].eq(True)]["time_placed"], bins=bins)
                        .value_counts()
                        .sort_index()
                        .tolist(),
                        "destroyed": pd.cut(
                            wards[wards["is_radiant"].eq(True) & wards["is_destroyed"].eq(True)]["time_placed"],
                            bins=bins,
                        )
                        .value_counts()
                        .sort_index()
                        .tolist(),
                    }
                },
            }
            if True in current.index
            else None,
            "dire": {
                "amount": current.loc[False]["amount"],
                "destroyed": current.loc[False]["is_destroyed"],
                "advantage": current.loc[False]["advantage"],
                "duration": current.loc[False]["duration"],
                "time_placed": current.loc[False]["time_placed"],
                "players": dire_players_dict,
                "graphs": {
                    "wards": {
                        "placed": pd.cut(wards[wards["is_radiant"].eq(False)]["time_placed"], bins=bins)
                        .value_counts()
                        .sort_index()
                        .tolist(),
                        "destroyed": pd.cut(
                            wards[wards["is_radiant"].eq(False) & wards["is_destroyed"].eq(True)]["time_placed"],
                            bins=bins,
                        )
                        .value_counts()
                        .sort_index()
                        .tolist(),
                    }
                },
            }
            if False in current.index
            else None,
            "all": {
                "amount": current["amount"].sum(),
                "destroyed": current["is_destroyed"].sum(),
                "advantage": None,
                "duration": round(current["duration"].mean()),
                "time_placed": round(current["time_placed"].mean()),
                "players": players_dict,
                "graphs": {
                    "wards": {
                        "placed": pd.cut(wards["time_placed"], bins=bins).value_counts().sort_index().tolist(),
                        "destroyed": pd.cut(wards[wards["is_destroyed"].eq(True)]["time_placed"], bins=bins)
                        .value_counts()
                        .sort_index()
                        .tolist(),
                    }
                },
            },
        }
        clusters.append(cluster)

    average_df = grouped.reset_index("is_radiant")
    average_radiant = average_df[average_df["is_radiant"].eq(True)]
    average_dire = average_df[average_df["is_radiant"].eq(False)]
    average = {
        "cluster_id": -1,
        "radiant": {
            "advantage": round(average_radiant["advantage"].mean()),
            "duration": round(average_radiant["duration"].mean()),
        },
        "dire": {
            "advantage": round(average_dire["advantage"].mean()),
            "duration": round(average_dire["duration"].mean()),
        },
        "all": {
            "advantage": None,
            "duration": round(average_df["duration"].mean()),
        },
    }
    clusters.append(average)

    return clusters
