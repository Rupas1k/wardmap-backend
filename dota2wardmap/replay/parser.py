import logging
import time
from multiprocessing.queues import Queue

from d2wm_parser import parse_replay

from .download import get_replay

logger = logging.getLogger(__name__)


def download_and_parse_replay(match_id: int, result_queue: Queue) -> None:
    data = get_replay(match_id)
    if not data:
        result_queue.put((match_id, None, "Replay could not be downloaded"))
        return

    replay, match_data = data
    try:
        started_at = time.time()
        output = parse_replay(replay)
        output_dicts = [
            {
                "time_placed": item.time_placed,
                "duration": item.duration,
                "is_obs": item.is_obs,
                "is_radiant": item.is_radiant,
                "event": item.event,
                "post_game": item.post_game,
                "player_placed_steam_id": item.player_placed_steam_id,
                "player_destroyed_steam_id": item.player_destroyed_steam_id,
                "npc_killed": item.npc_killed,
                "x": item.x,
                "y": item.y,
                "z": item.z,
                "vec_x": item.vec_x,
                "vec_y": item.vec_y,
                "vec_z": item.vec_z,
                "radiant_networth": item.radiant_networth,
                "dire_networth": item.dire_networth,
            }
            for item in output
        ]

        logger.info("Parsed match %s in %.3fs", match_id, time.time() - started_at)
        result_queue.put((match_id, (match_id, match_data, output_dicts), None))
    except BaseException as exc:
        logger.exception("Unable to parse match %s", match_id)
        error = str(exc) or f"{type(exc).__name__} while parsing"
        result_queue.put((match_id, None, error))


def parser_process(task_queue: Queue, result_queue: Queue) -> None:
    while True:
        match_id = task_queue.get()
        if match_id is None:
            break
        download_and_parse_replay(int(match_id), result_queue)
