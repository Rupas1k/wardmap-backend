class Output:
    time_placed: int
    duration: int
    is_obs: bool
    is_radiant: bool
    event: str
    post_game: bool
    player_placed_steam_id: int
    player_destroyed_steam_id: int | None
    npc_killed: str | None
    x: int
    y: int
    z: int
    vec_x: float
    vec_y: float
    vec_z: float
    radiant_networth: int
    dire_networth: int
    enemy_hero_vision_seconds: float
    unique_enemy_hero_vision_seconds: float
    heroes_spotted: int
    hero_reveal_events: int
    unique_hero_reveal_events: int
    scouting_tracking_seconds: float | None
    scouting_discovery_seconds: float | None
    scouting_score: float | None
    scouting_version: int | None
    scouting_tau_seconds: float | None
    scouting_complete: bool | None

class VisionSample:
    time: int
    game_time_seconds: float
    target_player_steam_id: int
    target_is_radiant: bool
    observing_is_radiant: bool
    is_alive: bool
    visible_by_enemy: bool
    provider_count: int
    provider_kinds: list[str]
    ward_provider_handles: list[int]
    has_non_ward_provider: bool
    visibility_known: bool

def parse_replay(data: bytes) -> Replay: ...
def parse_vision(data: bytes) -> list[VisionSample]: ...

class Replay:
    metadata: ReplayMetadata
    wards: list[Output]

class ReplayMetadata:
    playback_time_seconds: float | None
    game_duration_seconds: float | None
    playback_ticks: int | None
    playback_frames: int | None
    match_id: int | None
    game_mode: int | None
    game_winner: int | None
    league_id: int | None
    radiant_team_id: int | None
    dire_team_id: int | None
    radiant_team_tag: str | None
    dire_team_tag: str | None
    end_time: int | None
    players: list[ReplayPlayer]

class ReplayPlayer:
    steam_id: int | None
    name: str | None
    hero_name: str | None
    team: int | None
    is_fake_client: bool | None
