use pyo3::prelude::*;

#[pyclass(get_all, skip_from_py_object)]
#[derive(Clone)]
pub struct Replay {
    pub metadata: ReplayMetadata,
    pub wards: Vec<Output>,
}

#[pyclass(get_all, skip_from_py_object)]
#[derive(Clone)]
pub struct ReplayMetadata {
    pub playback_time_seconds: Option<f32>,
    pub game_duration_seconds: Option<f32>,
    pub playback_ticks: Option<i32>,
    pub playback_frames: Option<i32>,
    pub match_id: Option<u64>,
    pub game_mode: Option<i32>,
    pub game_winner: Option<i32>,
    pub league_id: Option<u32>,
    pub radiant_team_id: Option<u32>,
    pub dire_team_id: Option<u32>,
    pub radiant_team_tag: Option<String>,
    pub dire_team_tag: Option<String>,
    pub end_time: Option<u32>,
    pub players: Vec<ReplayPlayer>,
}

#[pyclass(get_all, skip_from_py_object)]
#[derive(Clone)]
pub struct ReplayPlayer {
    pub steam_id: Option<u64>,
    pub name: Option<String>,
    pub hero_name: Option<String>,
    pub team: Option<i32>,
    pub is_fake_client: Option<bool>,
}

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
    pub scouting_tracking_seconds: Option<f64>,
    pub scouting_discovery_seconds: Option<f64>,
    pub scouting_score: Option<f64>,
    pub scouting_version: Option<i16>,
    pub scouting_tau_seconds: Option<f64>,
    pub scouting_complete: Option<bool>,
    pub measurement_json: Option<String>,
}

impl From<wardmap_parser::Output> for Output {
    fn from(value: wardmap_parser::Output) -> Self {
        Self {
            time_placed: value.time_placed,
            duration: value.duration,
            is_obs: value.is_obs,
            is_radiant: value.is_radiant,
            event: value.event,
            post_game: value.post_game,
            player_placed_steam_id: value.player_placed_steam_id,
            player_destroyed_steam_id: value.player_destroyed_steam_id,
            npc_killed: value.npc_killed,
            x: value.x,
            y: value.y,
            z: value.z,
            vec_x: value.vec_x,
            vec_y: value.vec_y,
            vec_z: value.vec_z,
            radiant_networth: value.radiant_networth,
            dire_networth: value.dire_networth,
            enemy_hero_vision_seconds: value.enemy_hero_vision_seconds,
            unique_enemy_hero_vision_seconds: value.unique_enemy_hero_vision_seconds,
            heroes_spotted: value.heroes_spotted,
            hero_reveal_events: value.hero_reveal_events,
            unique_hero_reveal_events: value.unique_hero_reveal_events,
            scouting_tracking_seconds: value.scouting_tracking_seconds,
            scouting_discovery_seconds: value.scouting_discovery_seconds,
            scouting_score: value.scouting_score,
            scouting_version: value.scouting_version,
            scouting_tau_seconds: value.scouting_tau_seconds,
            scouting_complete: value.scouting_complete,
            measurement_json: value.measurement_json,
        }
    }
}

impl From<wardmap_parser::Replay> for Replay {
    fn from(value: wardmap_parser::Replay) -> Self {
        Self {
            metadata: value.metadata.into(),
            wards: value.wards.into_iter().map(Output::from).collect(),
        }
    }
}

impl From<wardmap_parser::ReplayMetadata> for ReplayMetadata {
    fn from(value: wardmap_parser::ReplayMetadata) -> Self {
        Self {
            playback_time_seconds: value.playback_time_seconds,
            game_duration_seconds: value.game_duration_seconds,
            playback_ticks: value.playback_ticks,
            playback_frames: value.playback_frames,
            match_id: value.match_id,
            game_mode: value.game_mode,
            game_winner: value.game_winner,
            league_id: value.league_id,
            radiant_team_id: value.radiant_team_id,
            dire_team_id: value.dire_team_id,
            radiant_team_tag: value.radiant_team_tag,
            dire_team_tag: value.dire_team_tag,
            end_time: value.end_time,
            players: value.players.into_iter().map(ReplayPlayer::from).collect(),
        }
    }
}

impl From<wardmap_parser::ReplayPlayer> for ReplayPlayer {
    fn from(value: wardmap_parser::ReplayPlayer) -> Self {
        Self {
            steam_id: value.steam_id,
            name: value.name,
            hero_name: value.hero_name,
            team: value.team,
            is_fake_client: value.is_fake_client,
        }
    }
}
