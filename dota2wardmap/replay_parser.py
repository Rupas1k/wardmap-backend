import bz2
import logging
import time
from multiprocessing import Process, Queue, cpu_count
from typing import Any

import requests
from d2wm_parser import parse_replay
from flask import Flask
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from . import api
from .extensions import db, redis_store
from .models import Leagues, Matches, Wards
from .views import parse_league_players

logger = logging.getLogger(__name__)


def get_task():
    return redis_store.lpop("replays")


def get_match_data_odota(match_id):
    response = requests.get(f"https://api.opendota.com/api/matches/{match_id}").json()
    match_data = {
        "cluster": response.get("cluster"),
        "salt": response.get("replay_salt"),
        "league": response.get("league", {}).get("leagueid"),
        "duration": response.get("duration"),
        "region": response.get("region"),
        "date": response.get("start_time"),
        "version": response.get("patch"),
    }
    return match_data


def get_replay(match_id):
    match_data = get_match_data_odota(match_id)
    try:
        cluster, salt = match_data["cluster"], match_data["salt"]
    except (KeyError, TypeError):
        logger.exception("Invalid OpenDota response for match %s", match_id)
        return

    try:
        response = requests.get(f"http://replay{cluster}.valve.net/570/{match_id}_{salt}.dem.bz2", timeout=10)
    except requests.exceptions.ReadTimeout:
        # log
        return

    if response.status_code == 404:
        # log
        return

    replay = bz2.decompress(response.content)

    return replay, match_data


def parse(match_id, result_queue):
    data = get_replay(match_id)
    if data:
        replay, match_data = data
        if replay:
            try:
                now = time.time()
                output = parse_replay(replay)
                output_dicts = []
                for out in output:
                    d = {
                        "time_placed": out.time_placed,
                        "duration": out.duration,
                        "is_obs": out.is_obs,
                        "is_radiant": out.is_radiant,
                        "event": out.event,
                        "post_game": out.post_game,
                        "player_placed_steam_id": out.player_placed_steam_id,
                        "player_destroyed_steam_id": out.player_destroyed_steam_id,
                        "npc_killed": out.npc_killed,
                        "x": out.x,
                        "y": out.y,
                        "z": out.z,
                        "vec_x": out.vec_x,
                        "vec_y": out.vec_y,
                        "vec_z": out.vec_z,
                        "radiant_networth": out.radiant_networth,
                        "dire_networth": out.dire_networth,
                    }
                    output_dicts.append(d)

                print(f"{match_id} parsed, took {time.time() - now}")
                result_queue.put((match_id, match_data, output_dicts))
            except (KeyError, TypeError, ValueError):
                logger.exception("Unable to parse match %s", match_id)


def process_task(task_queue, result_queue, i):
    while True:
        match_id = task_queue.get()
        if match_id is None:
            break
        parse(int(match_id), result_queue)


def process_result(result: tuple[int, dict[str, Any], list[dict[str, Any]]]) -> None:
    match_id = result[0]
    match_data = result[1]
    ward_results = result[2]
    try:
        wards = []
        for ward_data in ward_results:
            if ward_data["event"] == "expired" or "guys" in ward_data["npc_killed"]:
                ward_data["player_destroyed_steam_id"] = None

            ward_data["player_placed_steam_id"] = ward_data["player_placed_steam_id"] - 76561197960265728

            if ward_data["player_destroyed_steam_id"] is not None:
                ward_data["player_destroyed_steam_id"] -= 76561197960265728

            ward = {
                "match_id": match_id,
                "is_obs": ward_data["is_obs"],
                "is_radiant": ward_data["is_radiant"],
                "is_destroyed": ward_data["event"] == "killed",
                "is_post_game": ward_data["post_game"],
                "player_placed_id": ward_data["player_placed_steam_id"],
                "player_destroyed_id": ward_data["player_destroyed_steam_id"],
                "time_placed": ward_data["time_placed"],
                "duration": ward_data["duration"],
                "x_pos": ward_data["x"] * 128 + round(ward_data["vec_x"]),
                "y_pos": ward_data["y"] * 128 + round(ward_data["vec_y"]),
                "z_pos": ward_data["z"] * 128 + round(ward_data["vec_z"]),
                "radiant_networth": ward_data["radiant_networth"],
                "dire_networth": ward_data["dire_networth"],
                "npc_killed": ward_data["npc_killed"],
            }
            wards.append(ward)

        if (
            match_data["league"] is not None
            and not db.session.query(Leagues).filter(Leagues.id == int(match_data["league"])).first()
        ):
            league_info = api.fetch_league_info(match_data["league"])
            db.session.add(Leagues(id=int(match_data["league"]), name=league_info["displayName"]))
            parse_league_players(match_data["league"])

        if not db.session.query(Matches).filter(Matches.id == match_id).first():
            new_match = Matches(
                id=match_id,
                league_id=match_data["league"],
                game_version=match_data["version"],
                date=match_data["date"],
                region=match_data["region"],
                duration=match_data["duration"],
            )
            db.session.add(new_match)

            if len(wards):
                db.session.execute(insert(Wards).values(wards))
            else:
                print(f"No wards for match {match_id}")
            # db.session.add_all([Wards(**ward) for ward in wards])
        else:
            print(f"{match_id} is already parsed")

        db.session.commit()
    except (KeyError, TypeError, ValueError, SQLAlchemyError):
        db.session.rollback()
        logger.exception("Unable to persist match %s", match_id)


def init_parser(app: Flask):
    with app.app_context():
        queue = Queue()
        result_queue = Queue()

        processes = []

        for i in range(cpu_count()):
            process = Process(target=process_task, args=(queue, result_queue, i))
            process.start()
            processes.append(process)

        while True:
            while not result_queue.empty():
                result = result_queue.get()
                process_result(result)

            task = get_task()
            if task is not None:
                queue.put(task)
            else:
                time.sleep(1)
