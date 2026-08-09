import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import League, Match, Player, Ward

logger = logging.getLogger(__name__)

ParsedReplay = tuple[int, dict[str, Any], list[dict[str, Any]]]


def persist_parsed_replay(result: ParsedReplay) -> bool:
    match_id, match_data, ward_results = result
    try:
        wards = []
        for ward_data in ward_results:
            if ward_data["event"] == "expired" or "guys" in ward_data["npc_killed"]:
                ward_data["player_destroyed_steam_id"] = None

            ward_data["player_placed_steam_id"] -= 76561197960265728

            if ward_data["player_destroyed_steam_id"] is not None:
                ward_data["player_destroyed_steam_id"] -= 76561197960265728

            wards.append(
                {
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
            )

        if match_data["league"] is not None:
            league = db.session.get(League, int(match_data["league"]))
            if league is None:
                db.session.add(League(id=int(match_data["league"]), name=match_data.get("league_name")))

        match = db.session.get(Match, match_id)
        if match is None:
            started_at = match_data.get("date")
            match = Match(
                id=match_id,
                league_id=match_data["league"],
                game_version=match_data["version"],
                started_at=datetime.fromtimestamp(started_at, UTC) if started_at is not None else None,
                region=match_data["region"],
                duration=match_data["duration"],
            )
            db.session.add(match)
            _attach_players(match, match_data, wards)
            db.session.flush()

            if wards:
                db.session.execute(insert(Ward).values(wards))
            else:
                logger.warning("Parsed match %s contains no wards", match_id)
        else:
            logger.info("Match %s is already parsed", match_id)

        db.session.commit()
        return True
    except (KeyError, TypeError, ValueError, SQLAlchemyError):
        db.session.rollback()
        logger.exception("Unable to persist match %s", match_id)
        return False


def _attach_players(match: Match, match_data: dict[str, Any], wards: list[dict[str, Any]]) -> None:
    player_names = {player["id"]: player.get("name") for player in match_data.get("players", [])}
    player_ids = set(player_names)
    player_ids.update(ward["player_placed_id"] for ward in wards if ward["player_placed_id"] is not None)
    player_ids.update(ward["player_destroyed_id"] for ward in wards if ward["player_destroyed_id"] is not None)

    existing_players = {
        player.id: player
        for player in db.session.execute(select(Player).where(Player.id.in_(player_ids))).scalars().all()
    }
    for player_id in player_ids:
        player = existing_players.get(player_id)
        if player is None:
            player = Player(id=player_id, name=player_names.get(player_id))
            db.session.add(player)
        elif player.name is None and player_names.get(player_id):
            player.name = player_names[player_id]

        if player not in match.players:
            match.players.append(player)
