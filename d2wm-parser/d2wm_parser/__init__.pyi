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

def parse_replay(data: bytes) -> list[Output]: ...
