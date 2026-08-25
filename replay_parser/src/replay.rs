use anyhow::{anyhow, bail};
use hashbrown::HashMap;
use std::cell::RefCell;
use std::collections::VecDeque;
use std::rc::Rc;

use source2_demo::prelude::*;

use crate::observers::game_time::*;
use crate::observers::players::*;
use crate::observers::vision::*;
use crate::observers::wards::*;
use crate::output::{Output, VisionSample};

#[derive(Debug, Copy, Clone)]
struct WardEntry {
    hero_handle: usize,
    placed_tick: i32,
    is_radiant: bool,
    is_observer: bool,
}

#[derive(Default)]
struct App {
    game_time: Rc<RefCell<GameTime>>,
    players: Rc<RefCell<Players>>,
    vision: Rc<RefCell<Vision>>,

    handle_to_entry: HashMap<u32, WardEntry>,
    pending_entries: VecDeque<(Entity, i32, WardEvent)>,
    result: Vec<Output>,
}

#[observer]
impl App {
    #[on_tick_end]
    fn tick_end(&mut self, ctx: &Context) -> ObserverResult {
        let Ok(start_time) = self.game_time.borrow().start_time() else {
            return Ok(());
        };

        while let Some((ward, tick, event)) = self.pending_entries.pop_front() {
            let handle = ward.handle();
            let entry = self
                .handle_to_entry
                .get(&handle)
                .copied()
                .ok_or_else(|| anyhow!("Ward handle {handle} has no placement entry"))?;
            let duration = (((tick - entry.placed_tick) as f32) / 30.0).round() as i32;
            let time_placed = (entry.placed_tick as f32 / 30.0 - start_time).round() as i32;
            let hero_placed = ctx.entities().get_by_handle(entry.hero_handle)?.class().name();
            let vision_metrics = self.vision.borrow().ward_metrics(handle);
            let player_destroyed_steam_id = match &event {
                WardEvent::Killed(killer) => self
                    .players
                    .borrow()
                    .hero_to_player
                    .get(killer)
                    .map(|player| player.borrow().id),
                _ => None,
            };
            let npc_killed = match &event {
                WardEvent::Killed(killer) => Some(killer.to_string()),
                _ => None,
            };

            self.result.push(Output {
                time_placed,
                duration,
                is_obs: entry.is_observer,
                is_radiant: entry.is_radiant,
                event: event.to_string(),
                post_game: false,
                player_placed_steam_id: self
                    .players
                    .borrow()
                    .hero_to_player
                    .get(hero_placed)
                    .ok_or_else(|| anyhow!("Hero {hero_placed} has no player entry"))?
                    .borrow()
                    .id,
                player_destroyed_steam_id,
                npc_killed,
                x: property!(ward, "CBodyComponent.m_cellX"),
                y: property!(ward, "CBodyComponent.m_cellY"),
                z: property!(ward, "CBodyComponent.m_cellZ"),
                vec_x: property!(ward, "CBodyComponent.m_vecX"),
                vec_y: property!(ward, "CBodyComponent.m_vecY"),
                vec_z: property!(ward, "CBodyComponent.m_vecZ"),
                radiant_networth: property!(
                    ctx.entities().get_by_class_name("CDOTA_DataRadiant")?,
                    "m_vecDataTeam.0002.m_iNetWorth"
                ),
                dire_networth: property!(
                    ctx.entities().get_by_class_name("CDOTA_DataDire")?,
                    "m_vecDataTeam.0003.m_iNetWorth"
                ),
                enemy_hero_vision_seconds: vision_metrics.enemy_hero_seconds,
                unique_enemy_hero_vision_seconds: vision_metrics.unique_enemy_hero_seconds,
                heroes_spotted: vision_metrics.heroes_spotted,
                hero_reveal_events: vision_metrics.hero_reveal_events,
                unique_hero_reveal_events: vision_metrics.unique_hero_reveal_events,
            });
        }

        Ok(())
    }
}

impl WardsObserver for App {
    fn on_ward(&mut self, ctx: &Context, ward_class: WardClass, event: WardEvent, ward: &Entity) -> ObserverResult {
        match event {
            WardEvent::Placed => self.track_placement(ctx, ward_class, ward)?,
            WardEvent::Killed(killer) => self.queue_removal(ctx, ward, WardEvent::Killed(killer))?,
            WardEvent::Expired => self.queue_removal(ctx, ward, WardEvent::Expired)?,
        }

        Ok(())
    }
}

impl App {
    fn track_placement(&mut self, ctx: &Context, ward_class: WardClass, ward: &Entity) -> ObserverResult {
        let owner_handle: usize = property!(ward, "m_hOwnerEntity");
        let owner = ctx.entities().get_by_handle(owner_handle)?;
        let mut player_slot: usize = if let Some(slot) = try_property!(owner, "m_nPlayerID") {
            slot
        } else if let Some(slot) = try_property!(owner, "m_iPlayerID") {
            slot
        } else {
            bail!("Couldn't get player slot from ward entity")
        };

        player_slot >>= 1;

        let player = self
            .players
            .borrow()
            .players
            .get(player_slot)
            .cloned()
            .ok_or_else(|| anyhow!("Player slot {player_slot} is unavailable"))?;
        let player = player.borrow();

        self.handle_to_entry.insert(
            ward.handle(),
            WardEntry {
                hero_handle: player.handle,
                placed_tick: self.game_time.borrow().tick(ctx)?,
                is_radiant: player.team == 2,
                is_observer: ward_class == WardClass::Observer,
            },
        );

        Ok(())
    }

    fn queue_removal(&mut self, ctx: &Context, ward: &Entity, event: WardEvent) -> ObserverResult {
        self.pending_entries
            .push_back((ward.clone(), self.game_time.borrow().tick(ctx)?, event));

        Ok(())
    }
}

pub(crate) fn parse_replay(data: &[u8]) -> anyhow::Result<Vec<Output>> {
    let mut parser = Parser::new(data)?;

    let game_time = parser.register_observer::<GameTime>();
    let players = parser.register_observer::<Players>();
    let wards = parser.register_observer::<Wards>();
    let vision = parser.register_observer::<Vision>();
    let app = parser.register_observer::<App>();

    wards.borrow_mut().register_observer(app.clone());
    vision.borrow_mut().set_dependencies(game_time.clone(), players.clone());

    app.borrow_mut().game_time = game_time;
    app.borrow_mut().players = players;
    app.borrow_mut().vision = vision;

    parser.run_to_end()?;
    app.borrow_mut().tick_end(parser.context())?;

    let result = app.borrow().result.clone();

    Ok(result)
}

pub(crate) fn parse_vision(data: &[u8]) -> anyhow::Result<Vec<VisionSample>> {
    let mut parser = Parser::new(data)?;

    let game_time = parser.register_observer::<GameTime>();
    let players = parser.register_observer::<Players>();
    let vision = parser.register_observer::<Vision>();

    vision.borrow_mut().set_dependencies(game_time, players);
    vision.borrow_mut().enable_samples();

    parser.run_to_end()?;

    let samples = vision.borrow().samples.clone();

    Ok(samples)
}
