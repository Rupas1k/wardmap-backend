use std::collections::{HashMap, HashSet};

use serde::Serialize;

pub const SCOUTING_VERSION: i16 = 1;
pub const DISCOVERY_TAU_SECONDS: f64 = 10.0;
pub const SAMPLE_INTERVAL_TICKS: i32 = 6;
pub const MEASUREMENT_VERSION: u16 = 2;
pub const FRESH_SIGHTING_THRESHOLD_SECONDS: f64 = 5.0;
const MAX_INTERVAL_SECONDS: f64 = SAMPLE_INTERVAL_TICKS as f64 / 30.0 + 1e-6;

#[derive(Debug, Default, Clone)]
pub struct WardVisionMetrics {
    pub enemy_hero_seconds: f64,
    pub unique_enemy_hero_seconds: f64,
    pub heroes_spotted: u8,
    pub hero_reveal_events: u16,
    pub unique_hero_reveal_events: u16,
    pub scouting_tracking_seconds: f64,
    pub scouting_discovery_seconds: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct SightingEvidence {
    pub time: f64,
    pub target_player: String,
    pub hidden_seconds: f64,
    pub observer_handles: Vec<u32>,
    pub credit: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct VisionInterval {
    pub start: f64,
    pub end: f64,
    pub target_player: String,
    pub observer_handles: Vec<u32>,
    pub non_ward: bool,
    pub added_seconds: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct WardMeasurement {
    pub intervals: Vec<VisionInterval>,
    pub sightings: Vec<SightingEvidence>,
    pub version: u16,
    pub model: &'static str,
    pub estimated: bool,
    pub added_vision_seconds: f64,
    pub fresh_sightings: f64,
    pub fresh_sighting_threshold_seconds: f64,
    pub eligible_target_seconds: f64,
    pub known_target_seconds: f64,
    pub missing_target_seconds: f64,
    pub coverage: Option<f64>,
    pub model_limitations: [&'static str; 4],
}

impl WardVisionMetrics {
    pub fn scouting_score(&self) -> f64 {
        self.scouting_tracking_seconds + self.scouting_discovery_seconds
    }
}

#[derive(Default)]
struct WardAccumulator {
    intervals: Vec<VisionInterval>,
    last_interval: HashMap<u64, usize>,
    sightings: Vec<SightingEvidence>,
    metrics: WardVisionMetrics,
    heroes: HashSet<u64>,
    fresh_sightings: f64,
    eligible_target_seconds: f64,
    known_target_seconds: f64,
}

#[derive(Default, Clone)]
pub struct Sight {
    pub wards: Vec<u32>,
    pub non_ward: bool,
}

impl Sight {
    fn visible(&self) -> bool {
        self.non_ward || !self.wards.is_empty()
    }
}

#[derive(Clone)]
pub enum Observation {
    Alive(Sight),
    Dead,
    Unknown,
}

#[derive(Clone)]
pub struct PlayerObservation {
    pub id: u64,
    pub team: i32,
    pub state: Observation,
}

struct TargetState {
    sight: Sight,
    unseen_since: Option<f64>,
}

#[derive(Default)]
pub struct VisionMetrics {
    previous_time: Option<f64>,
    targets: HashMap<u64, TargetState>,
    wards: HashMap<u32, WardAccumulator>,
    previous_known: HashSet<u64>,
    previous_active: Vec<(u32, i32)>,
}

impl VisionMetrics {
    pub fn ward(&self, handle: u32) -> WardVisionMetrics {
        self.wards.get(&handle).map(|ward| ward.metrics.clone()).unwrap_or_default()
    }

    pub fn measurement(&self, handle: u32) -> WardMeasurement {
        let ward = self.wards.get(&handle);
        let eligible = ward.map_or(0.0, |ward| ward.eligible_target_seconds);
        let known = ward.map_or(0.0, |ward| ward.known_target_seconds);

        WardMeasurement {
            intervals: ward.map_or_else(Vec::new, |ward| ward.intervals.clone()),
            sightings: ward.map_or_else(Vec::new, |ward| ward.sightings.clone()),
            version: MEASUREMENT_VERSION,
            model: "geometry-v2",
            estimated: true,
            added_vision_seconds: ward.map_or(0.0, |ward| ward.metrics.scouting_tracking_seconds),
            fresh_sightings: ward.map_or(0.0, |ward| ward.fresh_sightings),
            fresh_sighting_threshold_seconds: FRESH_SIGHTING_THRESHOLD_SECONDS,
            eligible_target_seconds: eligible,
            known_target_seconds: known,
            missing_target_seconds: (eligible - known).max(0.0),
            coverage: (eligible > 0.0).then_some((known / eligible).clamp(0.0, 1.0)),
            model_limitations: [
                "static map and tree geometry",
                "spell and flying vision are incomplete",
                "local invisibility other than Smoke of Deceit is unsupported",
                "Meepo and Arc Warden target bodies are unsupported and counted as unknown",
            ],
        }
    }

    pub fn sample(&mut self, time: f64, observations: Vec<PlayerObservation>, active_wards: &[(u32, i32)]) {
        let elapsed = self.previous_time.map(|previous| time - previous);
        self.previous_time = Some(time);

        let elapsed = match elapsed {
            Some(elapsed) if (0.0..=MAX_INTERVAL_SECONDS).contains(&elapsed) => elapsed,
            _ => {
                self.targets.clear();
                self.previous_known.clear();
                0.0
            }
        };
        let mut previous = std::mem::take(&mut self.targets);
        let previous_known = std::mem::take(&mut self.previous_known);
        let previous_active = std::mem::replace(&mut self.previous_active, active_wards.to_vec());

        for observation in observations {
            let player = observation.id;
            let team = observation.team;
            let state = observation.state;
            let old = previous.remove(&player);

            if elapsed > 0.0 {
                for (handle, _) in previous_active.iter().filter(|(_, ward_team)| *ward_team != team) {
                    let ward = self.wards.entry(*handle).or_default();
                    ward.eligible_target_seconds += elapsed;
                    if previous_known.contains(&player) && !matches!(state, Observation::Unknown) {
                        ward.known_target_seconds += elapsed;
                    }
                }
            }
            if matches!(state, Observation::Unknown) {
                continue;
            }
            self.previous_known.insert(player);

            if let Some(old) = &old {
                self.integrate(&old.sight, elapsed, time, player);
            }

            let Observation::Alive(mut sight) = state else {
                continue;
            };
            sight.wards.sort_unstable();
            sight.wards.dedup();

            let visible = sight.visible();
            for handle in &sight.wards {
                let ward = self.wards.entry(*handle).or_default();
                ward.heroes.insert(player);
                ward.metrics.heroes_spotted = ward.heroes.len().try_into().unwrap_or(u8::MAX);
            }

            if visible && !sight.non_ward {
                if let Some(since) = old.as_ref().and_then(|old| old.unseen_since) {
                    let hidden_seconds = time - since;
                    let discovery = discovery_bonus(hidden_seconds) / sight.wards.len() as f64;
                    for handle in &sight.wards {
                        let ward = self.wards.entry(*handle).or_default();
                        if hidden_seconds >= FRESH_SIGHTING_THRESHOLD_SECONDS {
                            ward.fresh_sightings += 1.0 / sight.wards.len() as f64;
                            ward.sightings.push(SightingEvidence {
                                time,
                                target_player: player.to_string(),
                                hidden_seconds,
                                observer_handles: sight.wards.clone(),
                                credit: 1.0 / sight.wards.len() as f64,
                            });
                        }
                        let metrics = &mut ward.metrics;
                        metrics.scouting_discovery_seconds += discovery;
                        metrics.hero_reveal_events = metrics.hero_reveal_events.saturating_add(1);
                        if sight.wards.len() == 1 {
                            metrics.unique_hero_reveal_events = metrics.unique_hero_reveal_events.saturating_add(1);
                        }
                    }
                }
            }

            let unseen_since = if visible {
                None
            } else {
                Some(old.and_then(|old| old.unseen_since).unwrap_or(time))
            };
            self.targets.insert(player, TargetState { sight, unseen_since });
        }
    }

    fn integrate(&mut self, sight: &Sight, elapsed: f64, time: f64, player: u64) {
        for handle in &sight.wards {
            let ward = self.wards.entry(*handle).or_default();
            let added = if sight.non_ward {
                0.0
            } else {
                elapsed / sight.wards.len() as f64
            };
            if elapsed > 0.0 {
                let previous = ward.last_interval.get(&player).copied();
                let merge = previous.is_some_and(|index| {
                    let interval = &ward.intervals[index];
                    (interval.end - (time - elapsed)).abs() < 1e-6
                        && interval.observer_handles == sight.wards
                        && interval.non_ward == sight.non_ward
                });
                if merge {
                    let interval = &mut ward.intervals[previous.unwrap()];
                    interval.end = time;
                    interval.added_seconds += added;
                } else {
                    ward.last_interval.insert(player, ward.intervals.len());
                    ward.intervals.push(VisionInterval {
                        start: time - elapsed,
                        end: time,
                        target_player: player.to_string(),
                        observer_handles: sight.wards.clone(),
                        non_ward: sight.non_ward,
                        added_seconds: added,
                    });
                }
            }
            let metrics = &mut ward.metrics;
            metrics.enemy_hero_seconds += elapsed;
            if !sight.non_ward {
                metrics.scouting_tracking_seconds += elapsed / sight.wards.len() as f64;
                if sight.wards.len() == 1 {
                    metrics.unique_enemy_hero_seconds += elapsed;
                }
            }
        }
    }
}

fn discovery_bonus(unseen_seconds: f64) -> f64 {
    -DISCOVERY_TAU_SECONDS * (-unseen_seconds.max(0.0) / DISCOVERY_TAU_SECONDS).exp_m1()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn player(state: Observation) -> PlayerObservation {
        PlayerObservation { id: 7, team: 3, state }
    }

    #[test]
    fn added_vision_is_split_between_observer_wards() {
        let mut metrics = VisionMetrics::default();
        let wards = [(10, 2), (11, 2)];
        let sight = || {
            Observation::Alive(Sight {
                wards: vec![10, 11],
                non_ward: false,
            })
        };

        metrics.sample(0.0, vec![player(sight())], &wards);
        metrics.sample(0.2, vec![player(sight())], &wards);

        assert!((metrics.measurement(10).added_vision_seconds - 0.1).abs() < 1e-9);
        assert!((metrics.measurement(11).added_vision_seconds - 0.1).abs() < 1e-9);
        let measurement = metrics.measurement(10);
        assert_eq!(measurement.intervals.len(), 1);
        assert_eq!(measurement.intervals[0].observer_handles, vec![10, 11]);
        assert!((measurement.intervals[0].added_seconds - measurement.added_vision_seconds).abs() < 1e-9);
    }

    #[test]
    fn new_ward_does_not_inherit_previous_interval_coverage() {
        let mut metrics = VisionMetrics::default();
        metrics.sample(0.0, vec![player(Observation::Dead)], &[]);
        metrics.sample(0.2, vec![player(Observation::Dead)], &[(10, 2)]);
        assert_eq!(metrics.measurement(10).known_target_seconds, 0.0);
        metrics.sample(0.4, vec![player(Observation::Dead)], &[(10, 2)]);
        assert!((metrics.measurement(10).known_target_seconds - 0.2).abs() < 1e-9);
    }

    #[test]
    fn recovery_from_unknown_does_not_backfill_coverage() {
        let mut metrics = VisionMetrics::default();
        metrics.sample(0.0, vec![player(Observation::Unknown)], &[(10, 2)]);
        metrics.sample(0.2, vec![player(Observation::Dead)], &[(10, 2)]);
        assert_eq!(metrics.measurement(10).known_target_seconds, 0.0);
    }

    #[test]
    fn gap_cannot_create_a_fresh_sighting() {
        let mut metrics = VisionMetrics::default();
        metrics.sample(0.0, vec![player(Observation::Alive(Sight::default()))], &[(10, 2)]);
        metrics.sample(
            6.0,
            vec![player(Observation::Alive(Sight {
                wards: vec![10],
                non_ward: false,
            }))],
            &[(10, 2)],
        );
        assert_eq!(metrics.measurement(10).fresh_sightings, 0.0);
        assert_eq!(metrics.measurement(10).known_target_seconds, 0.0);
    }

    #[test]
    fn unknown_target_time_reduces_coverage_without_becoming_zero_impact() {
        let mut metrics = VisionMetrics::default();
        let wards = [(10, 2)];

        metrics.sample(0.0, vec![player(Observation::Unknown)], &wards);
        metrics.sample(0.2, vec![player(Observation::Unknown)], &wards);

        let measurement = metrics.measurement(10);
        assert!((measurement.eligible_target_seconds - 0.2).abs() < 1e-9);
        assert_eq!(measurement.known_target_seconds, 0.0);
        assert_eq!(measurement.coverage, Some(0.0));
    }

    #[test]
    fn fresh_sighting_requires_five_known_hidden_seconds_and_splits_credit() {
        let mut metrics = VisionMetrics::default();
        let wards = [(10, 2), (11, 2)];
        let hidden = || Observation::Alive(Sight::default());

        metrics.sample(0.0, vec![player(hidden())], &wards);
        for sample in 1..=25 {
            metrics.sample(sample as f64 * 0.2, vec![player(hidden())], &wards);
        }
        metrics.sample(
            5.2,
            vec![player(Observation::Alive(Sight {
                wards: vec![10, 11],
                non_ward: false,
            }))],
            &wards,
        );

        assert_eq!(metrics.measurement(10).fresh_sightings, 0.5);
        assert_eq!(metrics.measurement(11).fresh_sightings, 0.5);
        let measurement = metrics.measurement(10);
        assert_eq!(measurement.sightings.len(), 1);
        assert_eq!(measurement.sightings[0].target_player, "7");
        assert_eq!(measurement.sightings[0].credit, measurement.fresh_sightings);
    }
}
