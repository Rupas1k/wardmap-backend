use anyhow::{Context as _, Result};
use source2_demo::prelude::*;
use std::collections::{BTreeMap, BTreeSet};
use std::env;
use std::fs;

#[derive(Default)]
struct VisionInspector {
    candidates: BTreeMap<CandidateKey, Candidate>,
}

#[derive(Clone, Debug, Eq, Ord, PartialEq, PartialOrd)]
struct CandidateKey {
    class_name: String,
    entity_name: String,
    team: i32,
    day_range: i32,
    night_range: i32,
}

#[derive(Default)]
struct Candidate {
    handles: BTreeSet<u32>,
    life_states: BTreeSet<String>,
    health: BTreeSet<String>,
    owner_handles: BTreeSet<String>,
    player_ids: BTreeSet<String>,
    unit_states: BTreeSet<String>,
}

fn property_debug(entity: &Entity, name: &str) -> String {
    entity
        .get_property(name)
        .map(|value| format!("{value:?}"))
        .unwrap_or_else(|_| "-".to_string())
}

fn remember_sample(samples: &mut BTreeSet<String>, value: String) {
    if samples.len() < 8 || samples.contains(&value) {
        samples.insert(value);
    }
}

fn entity_name(ctx: &Context, entity: &Entity) -> String {
    let index = try_property!(entity, i32, "m_pEntity.m_nameStringTableIndex")
        .map(|value| value as usize)
        .or_else(|| try_property!(entity, u32, "m_pEntity.m_nameStringTableIndex").map(|value| value as usize));
    let Some(index) = index else {
        return "-".to_string();
    };

    ctx.string_tables()
        .get_by_name("EntityNames")
        .ok()
        .and_then(|table| table.get_row(index).ok())
        .map(|row| row.key().to_string())
        .unwrap_or_else(|| format!("index:{index}"))
}

#[observer]
impl VisionInspector {
    #[on_entity]
    fn on_entity(&mut self, ctx: &Context, event: EntityEvents, entity: &Entity) -> ObserverResult {
        if event == EntityEvents::Deleted {
            return Ok(());
        }

        let Some(team) = try_property!(entity, i32, "m_iTeamNum") else {
            return Ok(());
        };
        let Some(day_range) = try_property!(entity, i32, "m_iDayTimeVisionRange") else {
            return Ok(());
        };
        let Some(night_range) = try_property!(entity, i32, "m_iNightTimeVisionRange") else {
            return Ok(());
        };

        if team != 2 && team != 3 && day_range == 0 && night_range == 0 {
            return Ok(());
        }

        let key = CandidateKey {
            class_name: entity.class().name().to_string(),
            entity_name: entity_name(ctx, entity),
            team,
            day_range,
            night_range,
        };
        let candidate = self.candidates.entry(key).or_default();

        candidate.handles.insert(entity.handle());
        remember_sample(&mut candidate.life_states, property_debug(entity, "m_lifeState"));
        remember_sample(&mut candidate.health, property_debug(entity, "m_iHealth"));
        remember_sample(&mut candidate.owner_handles, property_debug(entity, "m_hOwnerEntity"));
        remember_sample(&mut candidate.player_ids, property_debug(entity, "m_iPlayerID"));
        remember_sample(&mut candidate.unit_states, property_debug(entity, "m_nUnitState64"));

        Ok(())
    }

    #[on_stop]
    fn on_stop(&mut self) -> ObserverResult {
        println!("class\tname\tteam\tday\tnight\tentities\tlife_state\thealth\towner\tplayer_id\tunit_state");

        for (key, candidate) in &self.candidates {
            println!(
                "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}",
                key.class_name,
                key.entity_name,
                key.team,
                key.day_range,
                key.night_range,
                candidate.handles.len(),
                candidate.life_states.iter().cloned().collect::<Vec<_>>().join(","),
                candidate.health.iter().cloned().collect::<Vec<_>>().join(","),
                candidate.owner_handles.iter().cloned().collect::<Vec<_>>().join(","),
                candidate.player_ids.iter().cloned().collect::<Vec<_>>().join(","),
                candidate.unit_states.iter().cloned().collect::<Vec<_>>().join(","),
            );
        }

        Ok(())
    }
}

fn main() -> Result<()> {
    let path = env::args().nth(1).context("usage: inspect_vision <replay.dem>")?;
    let data = fs::read(&path).with_context(|| format!("unable to read {path}"))?;
    let mut parser = Parser::new(&data)?;

    parser.register_observer::<VisionInspector>();
    parser.run_to_end()?;

    Ok(())
}
