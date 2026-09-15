import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import League, Match, Player, Team, Ward, players_matches

logger = logging.getLogger(__name__)

ParsedReplay = tuple[int, dict[str, Any], list[dict[str, Any]]]


def persist_parsed_replay(result: ParsedReplay) -> bool:
    match_id, match_data, ward_results = result
    try:
        wards = []
        for raw_ward_data in ward_results:
            ward_data = raw_ward_data.copy()
            npc_killed = ward_data.get("npc_killed")
            if ward_data["event"] == "expired" or (npc_killed is not None and "guys" in npc_killed):
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
                    "enemy_hero_vision_seconds": ward_data["enemy_hero_vision_seconds"],
                    "unique_enemy_hero_vision_seconds": ward_data["unique_enemy_hero_vision_seconds"],
                    "heroes_spotted": ward_data["heroes_spotted"],
                    "hero_reveal_events": ward_data["hero_reveal_events"],
                    "unique_hero_reveal_events": ward_data["unique_hero_reveal_events"],
                    "scouting_tracking_seconds": ward_data.get("scouting_tracking_seconds"),
                    "scouting_discovery_seconds": ward_data.get("scouting_discovery_seconds"),
                    "scouting_score": ward_data.get("scouting_score"),
                    "scouting_version": ward_data.get("scouting_version"),
                    "scouting_tau_seconds": ward_data.get("scouting_tau_seconds"),
                    "scouting_complete": ward_data.get("scouting_complete"),
                    "measurement": ward_data.get("measurement"),
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
            apply_match_team_data(match, match_data)
            _attach_players(match, match_data, wards)
            db.session.flush()

            if wards:
                db.session.execute(insert(Ward).values(wards))
            else:
                logger.warning("Parsed match %s contains no wards", match_id)
        else:
            updated = _update_existing_measurements(match_id, wards)
            logger.info("Match %s is already parsed; updated %s measurements", match_id, updated)

        db.session.commit()
        return True
    except (KeyError, TypeError, ValueError, SQLAlchemyError):
        db.session.rollback()
        logger.exception("Unable to persist match %s", match_id)
        return False


def _ward_signature(ward: Ward | dict[str, Any]) -> tuple[object, ...]:
    names = ("is_obs", "is_radiant", "player_placed_id", "time_placed", "duration", "x_pos", "y_pos", "z_pos")

    if isinstance(ward, dict):
        return tuple(ward.get(name) for name in names)

    return tuple(getattr(ward, name) for name in names)


def _update_existing_measurements(match_id: int, parsed_wards: list[dict[str, Any]]) -> int:
    candidates = [ward for ward in parsed_wards if ward.get("measurement") is not None]
    if not candidates:
        return 0

    existing = db.session.execute(select(Ward).where(Ward.match_id == match_id)).scalars().all()
    by_signature: dict[tuple[object, ...], list[Ward]] = {}
    for ward in existing:
        by_signature.setdefault(_ward_signature(ward), []).append(ward)

    matches: list[tuple[Ward, Any]] = []
    for candidate in candidates:
        rows = by_signature.get(_ward_signature(candidate), [])
        if len(rows) != 1:
            raise ValueError(f"Measurement backfill for match {match_id} is ambiguous or incomplete")
        matches.append((rows.pop(), candidate["measurement"]))

    for ward, measurement in matches:
        ward.measurement = measurement

    return len(matches)


def _upsert_team(team_data: dict[str, Any] | None) -> int | None:
    if not team_data or team_data.get("id") is None:
        return None
    team_id = int(team_data["id"])
    team = db.session.get(Team, team_id)
    if team is None:
        team = Team(id=team_id)
        db.session.add(team)
    team.name = team_data.get("name") or team.name
    team.tag = team_data.get("tag") or team.tag
    team.logo_url = team_data.get("logo_url") or team.logo_url
    if any(team_data.get(field) for field in ("name", "tag", "logo_url")):
        team.metadata_updated_at = datetime.now(UTC)
    return team_id


def apply_match_team_data(match: Match, match_data: dict[str, Any]) -> None:
    match.radiant_team_id = _upsert_team(match_data.get("radiant_team"))
    match.dire_team_id = _upsert_team(match_data.get("dire_team"))
    match.radiant_win = match_data.get("radiant_win")


def _attach_players(match: Match, match_data: dict[str, Any], wards: list[dict[str, Any]]) -> None:
    player_names = {player["id"]: player.get("name") for player in match_data.get("players", [])}
    player_sides = {
        player["id"]: player.get("is_radiant")
        for player in match_data.get("players", [])
        if player.get("is_radiant") is not None
    }

    for ward in wards:
        if ward["player_placed_id"] is not None and ward["is_radiant"] is not None:
            player_sides.setdefault(ward["player_placed_id"], ward["is_radiant"])
        if ward["player_destroyed_id"] is not None and ward["is_radiant"] is not None:
            player_sides.setdefault(ward["player_destroyed_id"], not ward["is_radiant"])

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

    db.session.flush()

    if player_ids:
        db.session.execute(
            players_matches.insert(),
            [
                {
                    "player_id": player_id,
                    "match_id": match.id,
                    "is_radiant": player_sides.get(player_id),
                }
                for player_id in player_ids
            ],
        )
