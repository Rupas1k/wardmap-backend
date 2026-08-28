use std::cell::RefCell;
use std::collections::{BTreeSet, HashMap, HashSet};
use std::rc::Rc;

use source2_demo::prelude::*;
use source2_demo::proto::DotaCombatlogTypes;

mod grid;
use grid::VisionGrid;

use crate::observers::game_time::GameTime;
use crate::observers::players::Players;
use crate::VisionSample;

const RADIANT: i32 = 2;
const DIRE: i32 = 3;
const WATCHER_VISION_RANGE: i32 = 800;
const SAMPLE_INTERVAL_TICKS: i32 = 30;

#[derive(Default)]
struct WardVisionAccumulator {
    enemy_hero_seconds: f32,
    unique_enemy_hero_seconds: f32,
    heroes_spotted: HashSet<u64>,
    hero_reveal_events: u16,
    unique_hero_reveal_events: u16,
}

#[derive(Debug, Default)]
pub struct WardVisionMetrics {
    pub enemy_hero_seconds: f32,
    pub unique_enemy_hero_seconds: f32,
    pub heroes_spotted: u8,
    pub hero_reveal_events: u16,
    pub unique_hero_reveal_events: u16,
}

#[derive(Default)]
pub struct Vision {
    game_time: Rc<RefCell<GameTime>>,
    players: Rc<RefCell<Players>>,
    grid: VisionGrid,
    provider_handles: HashSet<u32>,
    next_sample_tick: Option<i32>,
    previous_sample_tick: Option<i32>,
    ward_metrics: HashMap<u32, WardVisionAccumulator>,
    smoked_heroes: HashSet<u64>,
    previously_visible: HashMap<u64, bool>,
    collect_samples: bool,
    pub samples: Vec<VisionSample>,
}

impl Vision {
    pub fn set_dependencies(&mut self, game_time: Rc<RefCell<GameTime>>, players: Rc<RefCell<Players>>) {
        self.game_time = game_time;
        self.players = players;
    }

    pub fn enable_samples(&mut self) {
        self.collect_samples = true;
    }

    pub fn ward_metrics(&self, handle: u32) -> WardVisionMetrics {
        let Some(metrics) = self.ward_metrics.get(&handle) else {
            return WardVisionMetrics::default();
        };

        WardVisionMetrics {
            enemy_hero_seconds: metrics.enemy_hero_seconds,
            unique_enemy_hero_seconds: metrics.unique_enemy_hero_seconds,
            heroes_spotted: metrics.heroes_spotted.len().try_into().unwrap_or(u8::MAX),
            hero_reveal_events: metrics.hero_reveal_events,
            unique_hero_reveal_events: metrics.unique_hero_reveal_events,
        }
    }

    fn sample(&mut self, ctx: &Context, tick: i32, start_time: f32) {
        let elapsed_seconds = self
            .previous_sample_tick
            .map(|previous_tick| (tick - previous_tick).max(0) as f32 / 30.0)
            .unwrap_or(0.0);
        self.previous_sample_tick = Some(tick);

        let is_day = self.is_day(ctx);
        let providers = self
            .provider_handles
            .iter()
            .filter_map(|handle| ctx.entities().get_by_handle(*handle as usize).ok())
            .filter_map(|entity| ActiveProvider::from_entity(entity, is_day))
            .collect::<Vec<_>>();
        let players = self.players.borrow();
        let time = (tick as f32 / 30.0 - start_time) as i32;

        for player in &players.players {
            let player = player.borrow();
            let Ok(hero) = ctx.entities().get_by_handle(player.handle) else {
                continue;
            };

            let is_alive = is_alive(hero);
            let position = entity_position(hero);
            let enemy_team = if player.team == RADIANT { DIRE } else { RADIANT };
            let mut provider_kinds = BTreeSet::new();
            let mut provider_count = 0_u16;
            let mut sole_provider = None;
            let mut ward_providers = Vec::new();
            let mut has_non_ward_provider = false;

            if is_alive && !self.smoked_heroes.contains(&player.id) {
                if let Some(target_position) = position {
                    for provider in providers.iter().filter(|provider| provider.team == enemy_team) {
                        if self.grid.can_see(provider.position, target_position, provider.range) {
                            sole_provider = if provider_count == 0 { Some(provider) } else { None };
                            provider_count = provider_count.saturating_add(1);
                            provider_kinds.insert(provider.kind.to_string());

                            if provider.kind == "observer_ward" {
                                ward_providers.push(provider.handle);
                                let metrics = self.ward_metrics.entry(provider.handle).or_default();
                                metrics.enemy_hero_seconds += elapsed_seconds;
                                metrics.heroes_spotted.insert(player.id);
                            } else {
                                has_non_ward_provider = true;
                            }
                        }
                    }

                    if let Some(provider) = sole_provider.filter(|provider| provider.kind == "observer_ward") {
                        self.ward_metrics
                            .entry(provider.handle)
                            .or_default()
                            .unique_enemy_hero_seconds += elapsed_seconds;
                    }
                }
            }

            let visible = provider_count > 0;
            let was_visible = self.previously_visible.insert(player.id, visible).unwrap_or(false);
            if visible && !was_visible && !has_non_ward_provider {
                for handle in &ward_providers {
                    let metrics = self.ward_metrics.entry(*handle).or_default();
                    metrics.hero_reveal_events = metrics.hero_reveal_events.saturating_add(1);
                }

                if ward_providers.len() == 1 && provider_count == 1 {
                    let metrics = self.ward_metrics.entry(ward_providers[0]).or_default();
                    metrics.unique_hero_reveal_events = metrics.unique_hero_reveal_events.saturating_add(1);
                }
            }

            if self.collect_samples {
                self.samples.push(VisionSample {
                    time,
                    target_player_steam_id: player.id,
                    target_is_radiant: player.team == RADIANT,
                    observing_is_radiant: enemy_team == RADIANT,
                    is_alive,
                    visible_by_enemy: provider_count > 0,
                    provider_count,
                    provider_kinds: provider_kinds.into_iter().collect(),
                });
            }
        }
    }

    fn is_day(&self, ctx: &Context) -> bool {
        let Ok(game_rules) = ctx.entities().get_by_class_name("CDOTAGamerulesProxy") else {
            return true;
        };

        if game_rules
            .get_property("m_pGameRules.m_bIsTemporaryDay")
            .is_ok_and(|x| x.bool())
        {
            return true;
        };

        if game_rules
            .get_property("m_pGameRules.m_bIsTemporaryNight")
            .is_ok_and(|x| x.bool())
        {
            return false;
        };

        if game_rules
            .get_property("m_pGameRules.m_bIsNightstalkerNight")
            .is_ok_and(|x| x.bool())
        {
            return false;
        };

        let Ok(FieldValue::Signed32(net_time)) = game_rules.get_property("m_pGameRules.m_iNetTimeOfDay") else {
            return false;
        };

        let daytime_start = try_property!(game_rules, f32, "m_pGameRules.m_flDaytimeStart").unwrap_or(0.25);
        let nighttime_start = try_property!(game_rules, f32, "m_pGameRules.m_flNighttimeStart").unwrap_or(0.75);
        let time_of_day = *net_time as f32 / u16::MAX as f32;

        time_of_day >= daytime_start && time_of_day < nighttime_start
    }
}

#[observer]
impl Vision {
    #[on_entity]
    fn on_entity(&mut self, event: EntityEvents, entity: &Entity) -> ObserverResult {
        if event == EntityEvents::Deleted {
            self.provider_handles.remove(&entity.handle());
            return Ok(());
        }

        if is_provider_candidate(entity) {
            self.provider_handles.insert(entity.handle());
        } else {
            self.provider_handles.remove(&entity.handle());
        }

        Ok(())
    }

    #[on_tick_end]
    fn on_tick_end(&mut self, ctx: &Context) -> ObserverResult {
        if !self.players.borrow().init {
            return Ok(());
        }

        let Ok(tick) = self.game_time.borrow().tick(ctx) else {
            return Ok(());
        };

        let Ok(start_time) = self.game_time.borrow().start_time() else {
            return Ok(());
        };

        if self.next_sample_tick.is_some_and(|next| tick < next) {
            return Ok(());
        }

        self.next_sample_tick = Some(tick + SAMPLE_INTERVAL_TICKS);
        self.sample(ctx, tick, start_time);

        Ok(())
    }

    #[on_combat_log]
    fn on_combat_log(&mut self, combat_log: &CombatLogEntry) -> ObserverResult {
        let event = combat_log.r#type();
        if event != DotaCombatlogTypes::DotaCombatlogModifierAdd && event != DotaCombatlogTypes::DotaCombatlogModifierRemove {
            return Ok(());
        }

        if combat_log.inflictor_name().ok() != Some("modifier_smoke_of_deceit") {
            return Ok(());
        }

        let Ok(target_name) = combat_log.target_name() else {
            return Ok(());
        };

        let Some(player) = self.players.borrow().hero_to_player.get(target_name).cloned() else {
            return Ok(());
        };

        let player_id = player.borrow().id;

        if event == DotaCombatlogTypes::DotaCombatlogModifierAdd {
            self.smoked_heroes.insert(player_id);
            self.previously_visible.insert(player_id, false);
        } else {
            self.smoked_heroes.remove(&player_id);
        }

        Ok(())
    }
}

struct ActiveProvider<'a> {
    handle: u32,
    team: i32,
    range: i32,
    position: [f32; 3],
    kind: &'a str,
}

impl<'a> ActiveProvider<'a> {
    fn from_entity(entity: &'a Entity, is_day: bool) -> Option<Self> {
        if !is_alive(entity) {
            return None;
        }

        let team = try_property!(entity, i32, "m_iTeamNum")?;
        if team != RADIANT && team != DIRE {
            return None;
        }

        let class_name = entity.class().name();
        let range = if class_name == "CDOTA_BaseNPC_Watch_Tower" {
            // Captured watchers change to team 2/3 in the entity stream, but
            // their networked day/night fields remain zero in current demos.
            WATCHER_VISION_RANGE
        } else if is_day {
            try_property!(entity, i32, "m_iDayTimeVisionRange")?
        } else {
            try_property!(entity, i32, "m_iNightTimeVisionRange")?
        };

        if range <= 0 {
            return None;
        }

        Some(Self {
            handle: entity.handle(),
            team,
            range,
            position: entity_position(entity)?,
            kind: provider_kind(class_name),
        })
    }
}

fn is_provider_candidate(entity: &Entity) -> bool {
    let team = try_property!(entity, i32, "m_iTeamNum");
    if team != Some(RADIANT) && team != Some(DIRE) {
        return false;
    }

    if entity.class().name() == "CDOTA_BaseNPC_Watch_Tower" {
        return true;
    }

    let day_range = try_property!(entity, i32, "m_iDayTimeVisionRange").unwrap_or(0);
    let night_range = try_property!(entity, i32, "m_iNightTimeVisionRange").unwrap_or(0);

    day_range > 0 || night_range > 0
}

fn is_alive(entity: &Entity) -> bool {
    try_property!(entity, i32, "m_lifeState").is_none_or(|state| state == 0)
        && try_property!(entity, i32, "m_iHealth").is_none_or(|health| health > 0)
}

fn entity_position(entity: &Entity) -> Option<[f32; 3]> {
    let cell_x = try_property!(entity, u16, "CBodyComponent.m_cellX")?;
    let cell_y = try_property!(entity, u16, "CBodyComponent.m_cellY")?;
    let cell_z = try_property!(entity, u16, "CBodyComponent.m_cellZ")?;
    let offset_x = try_property!(entity, f32, "CBodyComponent.m_vecX")?;
    let offset_y = try_property!(entity, f32, "CBodyComponent.m_vecY")?;
    let offset_z = try_property!(entity, f32, "CBodyComponent.m_vecZ")?;

    Some([
        cell_x as f32 * 128.0 + offset_x,
        cell_y as f32 * 128.0 + offset_y,
        cell_z as f32 * 128.0 + offset_z,
    ])
}

fn provider_kind(class_name: &str) -> &'static str {
    if class_name.starts_with("CDOTA_Unit_Hero_") {
        "hero"
    } else if matches!(class_name, "CDOTA_BaseNPC_Creep_Lane" | "CDOTA_BaseNPC_Creep_Siege") {
        "lane_creep"
    } else if class_name == "CDOTA_BaseNPC_Creep_Neutral" {
        "controlled_neutral"
    } else if class_name == "CDOTA_NPC_Observer_Ward" {
        "observer_ward"
    } else if class_name == "CDOTA_BaseNPC_Tower" {
        "tower"
    } else if class_name == "CDOTA_BaseNPC_Watch_Tower" {
        "watcher"
    } else if class_name == "CDOTA_Unit_Courier" {
        "courier"
    } else if class_name == "CDOTA_Unit_Roshans_Banner" {
        "roshan_banner"
    } else if matches!(
        class_name,
        "CDOTA_BaseNPC_Barracks"
            | "CDOTA_BaseNPC_Effigy_Statue"
            | "CDOTA_BaseNPC_Filler"
            | "CDOTA_BaseNPC_Fort"
            | "CDOTA_NPC_BaseBlocker"
            | "CDOTA_Unit_Fountain"
    ) {
        "building"
    } else {
        "controlled_unit"
    }
}
