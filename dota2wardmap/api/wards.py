import math
from typing import Any

from flask import Blueprint, request
from sqlalchemy import Boolean, case, cast, exists, false, func, literal, select, true, union_all
from sqlalchemy.orm import aliased
from werkzeug.exceptions import BadRequest, NotFound

from ..access import max_ward_page_size
from ..extensions import db
from ..models import (
    FreshSightingEvent,
    FreshSightingRoutePoint,
    League,
    Match,
    Player,
    Team,
    Ward,
    WardFreshSightingCredit,
    WardSightingSegment,
    players_matches,
)

bp = Blueprint("wards", __name__)
MAX_FILTER_IDS = 500

ID_FILTER_NAMES = (
    "league_ids",
    "match_ids",
    "player_ids",
    "opponent_player_ids",
    "destroyed_by_player_ids",
    "team_ids",
    "opponent_team_ids",
)


def unit_display_name(unit_name: str | None) -> str | None:
    if not unit_name:
        return None

    prefixes = {
        "npc_dota_hero_": "",
        "npc_dota_creep_goodguys_": "Radiant ",
        "npc_dota_creep_badguys_": "Dire ",
    }
    for prefix, label in prefixes.items():
        if unit_name.startswith(prefix):
            words = unit_name.removeprefix(prefix).replace("_", " ")
            suffix = " creep" if "creep_" in prefix else ""

            return f"{label}{words}{suffix}".title()

    return unit_name.removeprefix("npc_dota_").replace("_", " ").title()


def ward_response(row: Any) -> dict[str, Any]:
    data = row._asdict()
    if data["measurement_version"] is None:
        data["measurement"] = None
    else:
        data["measurement"] = {
            "version": data.pop("measurement_version"),
            "revision": data.pop("measurement_revision"),
            "added_vision_seconds": data.pop("added_vision_seconds"),
            "fresh_sightings": data.pop("fresh_sightings"),
            "fresh_sighting_threshold_seconds": data.pop("fresh_sighting_threshold_seconds"),
            "vision_measured_seconds": data.pop("vision_measured_seconds"),
            "vision_possible_seconds": data.pop("vision_possible_seconds"),
            "vision_coverage": data.pop("vision_coverage"),
            "placed_at_seconds": data.pop("placed_at_seconds"),
            "ended_at_seconds": data.pop("ended_at_seconds"),
            "outcome": data.pop("outcome"),
            "outcome_reason": data.pop("outcome_reason"),
            "vision_complete": data.pop("vision_complete"),
            "sightings": [],
        }
    for name in (
        "measurement_version",
        "measurement_revision",
        "added_vision_seconds",
        "fresh_sightings",
        "fresh_sighting_threshold_seconds",
        "vision_measured_seconds",
        "vision_possible_seconds",
        "vision_coverage",
        "placed_at_seconds",
        "ended_at_seconds",
        "outcome",
        "outcome_reason",
        "vision_complete",
    ):
        data.pop(name, None)
    npc_killed = data.pop("npc_killed")

    if not data["is_destroyed"]:
        data.pop("player_destroyed_id")
        data.pop("player_destroyed_name")
    elif data["player_destroyed_name"] is None:
        data["player_destroyed_name"] = unit_display_name(npc_killed)

    return data


@bp.get("/wards/<int:ward_id>/evidence")
def ward_evidence(ward_id: int):
    ward = db.session.get(Ward, ward_id)
    if ward is None:
        raise NotFound("Ward not found")

    rows = db.session.execute(
        select(
            FreshSightingEvent,
            WardFreshSightingCredit,
            Player.name.label("target_player_name"),
        )
        .join(WardFreshSightingCredit, WardFreshSightingCredit.event_id == FreshSightingEvent.id)
        .outerjoin(Player, Player.id == FreshSightingEvent.target_player_id)
        .where(WardFreshSightingCredit.ward_id == ward_id)
        .order_by(FreshSightingEvent.time_seconds, FreshSightingEvent.id)
    ).all()
    event_ids = [event.id for event, _, _ in rows]
    segments: dict[tuple[int, int], list[WardSightingSegment]] = {}
    if event_ids:
        segment_rows = db.session.execute(
            select(WardSightingSegment)
            .where(
                WardSightingSegment.event_id.in_(event_ids),
                WardSightingSegment.ward_id == ward_id,
            )
            .order_by(
                WardSightingSegment.event_id,
                WardSightingSegment.ward_id,
                WardSightingSegment.sequence,
            )
        ).scalars()
        for segment in segment_rows:
            segments.setdefault((segment.event_id, segment.ward_id), []).append(segment)

    routes: dict[tuple[int, int, int], list[dict[str, object]]] = {}
    if event_ids:
        route_rows = db.session.execute(
            select(FreshSightingRoutePoint)
            .where(
                FreshSightingRoutePoint.event_id.in_(event_ids),
                FreshSightingRoutePoint.ward_id == ward_id,
            )
            .order_by(
                FreshSightingRoutePoint.event_id,
                FreshSightingRoutePoint.ward_id,
                FreshSightingRoutePoint.segment_sequence,
                FreshSightingRoutePoint.sequence,
            )
        ).scalars()
        for point in route_rows:
            routes.setdefault((point.event_id, point.ward_id, point.segment_sequence), []).append(
                {"time": point.time_seconds, "position": [point.x, point.y, point.z]}
            )

    return {
        "ward_id": ward.id,
        "measurement_version": ward.measurement_version,
        "measurement_revision": ward.measurement_revision,
        "sightings": [
            {
                "event_id": event.id,
                "sample_tick": event.sample_tick,
                "time": event.time_seconds,
                "target_player_slot": event.target_player_slot,
                "target_steam_id": event.target_steam_id,
                "target_player_id": event.target_player_id,
                "target_player_name": player_name,
                "target_hero_name": event.target_hero_name,
                "target_is_radiant": event.target_is_radiant,
                "target_position": [event.target_x, event.target_y, event.target_z],
                "hidden_seconds": event.hidden_seconds,
                "segments": [
                    {
                        "time": segment.time_seconds,
                        "gap_seconds": segment.gap_seconds,
                        "start_position": [segment.start_x, segment.start_y, segment.start_z],
                        "visible_seconds": segment.visible_seconds,
                        "lost_position":
                            [segment.lost_x, segment.lost_y, segment.lost_z]
                            if segment.lost_x is not None
                            else None,
                        "route": routes.get((event.id, credit.ward_id, segment.sequence), []),
                    }
                    for segment in segments.get((event.id, credit.ward_id), [])
                ],
                "observer_handles": [],
                "credit": credit.credit,
            }
            for event, credit, player_name in rows
        ],
    }


def integer_list(filters: Any, name: str) -> list[int]:
    try:
        values = filters.getlist(name) if hasattr(filters, "getlist") else filters.get(name, [])
        if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple)):
            raise BadRequest(f"{name} must be an array of numeric IDs")
        if len(values) > MAX_FILTER_IDS:
            raise BadRequest(f"{name} cannot contain more than {MAX_FILTER_IDS} IDs")
        return [int(value) for value in values]
    except (TypeError, ValueError) as exc:
        raise BadRequest(f"{name} must contain numeric IDs") from exc


def integer_filter(filters: dict[str, Any], name: str, default: int) -> int:
    try:
        return int(filters.get(name, default))
    except (TypeError, ValueError) as exc:
        raise BadRequest(f"{name} must be an integer") from exc


def number_filter(filters: dict[str, Any], name: str, default: float) -> float:
    try:
        value = float(filters.get(name, default))
    except (TypeError, ValueError) as exc:
        raise BadRequest(f"{name} must be a number") from exc

    if not math.isfinite(value):
        raise BadRequest(f"{name} must be a finite number")

    return value


def optional_number_filter(filters: dict[str, Any], name: str) -> float | None:
    if filters.get(name) is None:
        return None

    return number_filter(filters, name, 0)


def ward_query():
    owner_team = aliased(Team)
    opponent_team = aliased(Team)
    destroying_player = aliased(Player)

    owner_team_id = case(
        (Ward.is_radiant.is_(True), Match.radiant_team_id),
        (Ward.is_radiant.is_(False), Match.dire_team_id),
    )
    opponent_team_id = case(
        (Ward.is_radiant.is_(True), Match.dire_team_id),
        (Ward.is_radiant.is_(False), Match.radiant_team_id),
    )
    team_won = case(
        (Match.radiant_win.is_(None), None),
        (Ward.is_radiant.is_(True), Match.radiant_win),
        (Ward.is_radiant.is_(False), ~Match.radiant_win),
    )

    query = (
        select(
            Ward.id,
            Ward.match_id,
            Ward.player_placed_id,
            Player.name.label("player_name"),
            Ward.player_destroyed_id,
            destroying_player.name.label("player_destroyed_name"),
            Ward.is_radiant,
            Ward.is_obs,
            Ward.is_destroyed,
            Ward.time_placed,
            Ward.duration,
            Ward.npc_killed,
            Ward.x_pos,
            Ward.y_pos,
            Ward.z_pos,
            Ward.radiant_networth,
            Ward.dire_networth,
            Ward.enemy_hero_vision_seconds,
            Ward.unique_enemy_hero_vision_seconds,
            Ward.heroes_spotted,
            Ward.hero_reveal_events,
            Ward.unique_hero_reveal_events,
            Ward.scouting_tracking_seconds,
            Ward.scouting_discovery_seconds,
            Ward.scouting_score,
            Ward.scouting_version,
            Ward.scouting_tau_seconds,
            Ward.scouting_complete,
            Ward.measurement_version,
            Ward.measurement_revision,
            Ward.added_vision_seconds,
            Ward.fresh_sightings,
            Ward.fresh_sighting_threshold_seconds,
            Ward.vision_measured_seconds,
            Ward.vision_possible_seconds,
            Ward.vision_coverage,
            Ward.placed_at_seconds,
            Ward.ended_at_seconds,
            Ward.outcome,
            Ward.outcome_reason,
            Ward.vision_complete,
            Match.duration.label("match_duration"),
            Match.game_version,
            League.map_asset_version,
            owner_team_id.label("team_id"),
            owner_team.name.label("team_name"),
            opponent_team_id.label("opponent_team_id"),
            opponent_team.name.label("opponent_team_name"),
            team_won.label("team_won"),
        )
        .select_from(Ward)
        .join(Match, Match.id == Ward.match_id)
        .outerjoin(League, League.id == Match.league_id)
        .outerjoin(Player, Player.id == Ward.player_placed_id)
        .outerjoin(destroying_player, destroying_player.id == Ward.player_destroyed_id)
        .outerjoin(owner_team, owner_team.id == owner_team_id)
        .outerjoin(opponent_team, opponent_team.id == opponent_team_id)
    )

    return query, owner_team_id, opponent_team_id, team_won


def id_filters(filters: dict[str, Any]) -> dict[str, list[int]]:
    return {name: integer_list(filters, name) for name in ID_FILTER_NAMES}


def apply_id_filters(query, ids, owner_team_id, opponent_team_id):
    if ids["league_ids"]:
        query = query.where(Match.league_id.in_(ids["league_ids"]))
    if ids["match_ids"]:
        query = query.where(Ward.match_id.in_(ids["match_ids"]))
    if ids["player_ids"]:
        query = query.where(Ward.player_placed_id.in_(ids["player_ids"]))
    if ids["destroyed_by_player_ids"]:
        query = query.where(Ward.player_destroyed_id.in_(ids["destroyed_by_player_ids"]))
    if ids["opponent_player_ids"]:
        opponent_players = players_matches.alias("opponent_players")
        query = query.where(
            Ward.is_radiant.is_not(None),
            exists(
                select(1).where(
                    opponent_players.c.match_id == Ward.match_id,
                    opponent_players.c.is_radiant.is_not(None),
                    opponent_players.c.is_radiant != Ward.is_radiant,
                    opponent_players.c.player_id.in_(ids["opponent_player_ids"]),
                )
            ),
        )
    if ids["team_ids"]:
        query = query.where(owner_team_id.in_(ids["team_ids"]))
    if ids["opponent_team_ids"]:
        query = query.where(opponent_team_id.in_(ids["opponent_team_ids"]))

    return query


def apply_category_filters(query, filters: dict[str, Any], team_won):
    team_result = filters.get("team_result", "all")
    if team_result not in ("all", "won", "lost"):
        raise BadRequest("team_result must be all, won, or lost")
    if team_result in ("won", "lost"):
        query = query.where(team_won.is_(team_result == "won"))

    side = filters.get("side", "all")
    if side not in ("all", "radiant", "dire"):
        raise BadRequest("side must be all, radiant, or dire")
    if side in ("radiant", "dire"):
        query = query.where(Ward.is_radiant.is_(side == "radiant"))

    ward_type = filters.get("ward_type", "all")
    if ward_type not in ("all", "observer", "sentry"):
        raise BadRequest("ward_type must be all, observer, or sentry")
    if ward_type in ("observer", "sentry"):
        query = query.where(Ward.is_obs.is_(ward_type == "observer"))

    outcome = filters.get("outcome", "all")
    valid_outcomes = (
        "all",
        "dewarded",
        "expired",
        "allied_removed",
        "match_ended",
        "unresolved_removal",
    )
    if outcome not in valid_outcomes:
        raise BadRequest(f"outcome must be one of {', '.join(valid_outcomes)}")
    if outcome == "unresolved_removal":
        query = query.where(Ward.outcome.in_(("unknown", "replay_ended")))
    elif outcome != "all":
        query = query.where(Ward.outcome == outcome)

    return query


def apply_range_filters(query, filters: dict[str, Any]):
    ranges = (
        (
            "game minute",
            number_filter(filters, "minimum_game_minute", -1.5),
            number_filter(filters, "maximum_game_minute", 60),
        ),
        (
            "match duration",
            integer_filter(filters, "minimum_match_duration", 0),
            integer_filter(filters, "maximum_match_duration", 180),
        ),
        (
            "ward lifetime",
            integer_filter(filters, "minimum_ward_lifetime", 0),
            integer_filter(filters, "maximum_ward_lifetime", 600),
        ),
    )

    for name, minimum, maximum in ranges:
        minimum_allowed = -1.5 if name == "game minute" else 0
        if minimum < minimum_allowed or maximum < minimum:
            raise BadRequest(f"invalid {name} range")

    return query.where(
        Ward.time_placed >= ranges[0][1] * 60,
        Ward.time_placed <= ranges[0][2] * 60,
        Match.duration >= ranges[1][1] * 60,
        Match.duration <= ranges[1][2] * 60,
        Ward.duration >= ranges[2][1],
        Ward.duration <= ranges[2][2],
    )


def apply_vision_filters(query, filters: dict[str, Any]):
    ranges = (
        ("added vision", Ward.added_vision_seconds, "added_vision_seconds"),
        ("fresh sightings", Ward.fresh_sightings, "fresh_sightings"),
        ("scouting score", Ward.scouting_score, "scouting_score"),
        ("enemy hero vision", Ward.enemy_hero_vision_seconds, "enemy_hero_vision_seconds"),
        (
            "unique enemy hero vision",
            Ward.unique_enemy_hero_vision_seconds,
            "unique_enemy_hero_vision_seconds",
        ),
        ("heroes spotted", Ward.heroes_spotted, "heroes_spotted"),
        ("hero reveal events", Ward.hero_reveal_events, "hero_reveal_events"),
        (
            "unique hero reveal events",
            Ward.unique_hero_reveal_events,
            "unique_hero_reveal_events",
        ),
        ("scouting tracking", Ward.scouting_tracking_seconds, "scouting_tracking_seconds"),
        ("scouting discovery", Ward.scouting_discovery_seconds, "scouting_discovery_seconds"),
    )

    for label, column, field in ranges:
        minimum = optional_number_filter(filters, f"minimum_{field}")
        maximum = optional_number_filter(filters, f"maximum_{field}")

        if minimum is not None and minimum < 0:
            raise BadRequest(f"minimum {label} must be zero or greater")
        if maximum is not None and maximum < 0:
            raise BadRequest(f"maximum {label} must be zero or greater")
        if minimum is not None and maximum is not None and maximum < minimum:
            raise BadRequest(f"invalid {label} range")

        if minimum is not None:
            query = query.where(column >= minimum)
        if maximum is not None:
            query = query.where(column <= maximum)

    return query


def count_response(query, filters: dict[str, Any], ids: dict[str, list[int]]) -> dict[str, int] | None:
    count_only = filters.get("count_only", False)
    if not isinstance(count_only, bool):
        raise BadRequest("count_only must be a boolean")
    if not count_only:
        return None

    if not any(ids.values()):
        raise BadRequest("count_only queries must include at least one ID filter")

    count_query = select(func.count()).select_from(query.order_by(None).subquery())

    return {"count": db.session.execute(count_query).scalar_one()}


def paginated_response(query, filters: dict[str, Any]) -> dict[str, Any]:
    try:
        page_size = integer_filter(filters, "page_size", 2000)
        cursor_value = filters.get("cursor")
        cursor = int(cursor_value) if cursor_value is not None else None
    except (TypeError, ValueError) as exc:
        raise BadRequest("page_size and cursor must be integers") from exc

    if page_size < 1:
        raise BadRequest("page_size must be greater than zero")

    page_size = min(page_size, max_ward_page_size())
    if cursor is not None:
        query = query.where(Ward.id < cursor)

    rows = db.session.execute(query.order_by(Ward.id.desc()).limit(page_size + 1)).all()
    has_more = len(rows) > page_size
    rows = rows[:page_size]

    return {
        "data": [ward_response(row) for row in rows],
        "pagination": {
            "page_size": page_size,
            "has_more": has_more,
            "next_cursor": rows[-1].id if has_more and rows else None,
        },
    }


@bp.post("/wards/query")
def query_wards():
    filters = request.get_json(silent=True) or {}
    if not isinstance(filters, dict):
        raise BadRequest("request body must be a JSON object")

    query, owner_team_id, opponent_team_id, team_won = ward_query()
    ids = id_filters(filters)

    query = apply_id_filters(query, ids, owner_team_id, opponent_team_id)
    query = apply_category_filters(query, filters, team_won)
    query = apply_range_filters(query, filters)
    query = apply_vision_filters(query, filters)

    if response := count_response(query, filters, ids):
        return response

    return paginated_response(query, filters)


@bp.post("/wards/population")
def ward_population():
    filters = request.get_json(silent=True) or {}
    if not isinstance(filters, dict):
        raise BadRequest("request body must be a JSON object")

    ids = id_filters(filters)
    radiant = select(
        Match.id.label("match_id"),
        cast(true(), Boolean).label("is_radiant"),
        Match.radiant_team_id.label("team_id"),
        Match.dire_team_id.label("opponent_team_id"),
        Match.duration,
        Match.league_id,
        Match.radiant_win.label("team_won"),
    )
    dire = select(
        Match.id.label("match_id"),
        cast(false(), Boolean).label("is_radiant"),
        Match.dire_team_id.label("team_id"),
        Match.radiant_team_id.label("opponent_team_id"),
        Match.duration,
        Match.league_id,
        (~Match.radiant_win).label("team_won"),
    )
    population = union_all(radiant, dire).subquery()
    query = select(population)

    if ids["league_ids"]:
        query = query.where(population.c.league_id.in_(ids["league_ids"]))
    if ids["match_ids"]:
        query = query.where(population.c.match_id.in_(ids["match_ids"]))
    if ids["team_ids"]:
        query = query.where(population.c.team_id.in_(ids["team_ids"]))
    if ids["opponent_team_ids"]:
        query = query.where(population.c.opponent_team_id.in_(ids["opponent_team_ids"]))

    side = filters.get("side", "all")
    if side not in ("all", "radiant", "dire"):
        raise BadRequest("side must be all, radiant, or dire")
    if side != "all":
        query = query.where(population.c.is_radiant.is_(side == "radiant"))

    team_result = filters.get("team_result", "all")
    if team_result not in ("all", "won", "lost"):
        raise BadRequest("team_result must be all, won, or lost")
    if team_result != "all":
        query = query.where(population.c.team_won.is_(team_result == "won"))

    minimum_duration = integer_filter(filters, "minimum_match_duration", 0)
    maximum_duration = integer_filter(filters, "maximum_match_duration", 180)
    if minimum_duration < 0 or maximum_duration < minimum_duration:
        raise BadRequest("invalid match duration range")
    query = query.where(
        population.c.duration >= minimum_duration * 60,
        population.c.duration <= maximum_duration * 60,
    )
    minimum_game_minute = number_filter(filters, "minimum_game_minute", -1.5)
    if minimum_game_minute < -1.5:
        raise BadRequest("invalid game minute range")
    if minimum_game_minute > 0:
        query = query.where(population.c.duration >= minimum_game_minute * 60)

    for name, opposite in (("player_ids", False), ("opponent_player_ids", True)):
        if not ids[name]:
            continue
        participation = players_matches.alias(f"population_{name}")
        same_side = participation.c.is_radiant == population.c.is_radiant
        query = query.where(
            exists(
                select(literal(1)).where(
                    participation.c.match_id == population.c.match_id,
                    participation.c.player_id.in_(ids[name]),
                    ~same_side if opposite else same_side,
                )
            )
        )

    selected = query.subquery()
    row = db.session.execute(
        select(
            func.count().label("match_sides"),
            func.count(func.distinct(selected.c.match_id)).label("matches"),
        ).select_from(selected)
    ).one()

    quality_filters = bool(
        ids["destroyed_by_player_ids"]
        or filters.get("outcome", "all") != "all"
        or filters.get("minimum_ward_lifetime", 0) != 0
        or filters.get("maximum_ward_lifetime", 600) != 600
        or any(
            value is not None and any(word in key for word in ("scouting", "vision", "spotted", "reveal"))
            for key, value in filters.items()
        )
    )

    return {
        "matches": row.matches,
        "match_sides": row.match_sides,
        "selection_conditioned": team_result != "all" or quality_filters,
    }
