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

class VisionSample:
    time: int
    target_player_steam_id: int
    target_is_radiant: bool
    observing_is_radiant: bool
    is_alive: bool
    visible_by_enemy: bool
    provider_count: int
    provider_kinds: list[str]

def parse_replay(data: bytes) -> list[Output]: ...
def parse_vision(data: bytes) -> list[VisionSample]: ...
