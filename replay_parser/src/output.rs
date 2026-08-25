use pyo3::prelude::*;

#[pyclass(get_all, set_all, skip_from_py_object)]
#[derive(Clone)]
pub struct Output {
    pub time_placed: i32,
    pub duration: i32,
    pub is_obs: bool,
    pub is_radiant: bool,
    pub event: String,
    pub post_game: bool,
    pub player_placed_steam_id: u64,
    pub player_destroyed_steam_id: Option<u64>,
    pub npc_killed: Option<String>,
    pub x: u16,
    pub y: u16,
    pub z: u16,
    pub vec_x: f32,
    pub vec_y: f32,
    pub vec_z: f32,
    pub radiant_networth: i32,
    pub dire_networth: i32,
    pub enemy_hero_vision_seconds: f32,
    pub unique_enemy_hero_vision_seconds: f32,
    pub heroes_spotted: u8,
    pub hero_reveal_events: u16,
    pub unique_hero_reveal_events: u16,
}

#[pyclass(get_all, skip_from_py_object)]
#[derive(Clone)]
pub struct VisionSample {
    pub time: i32,
    pub target_player_steam_id: u64,
    pub target_is_radiant: bool,
    pub observing_is_radiant: bool,
    pub is_alive: bool,
    pub visible_by_enemy: bool,
    pub provider_count: u16,
    pub provider_kinds: Vec<String>,
}
