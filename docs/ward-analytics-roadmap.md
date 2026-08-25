# Ward Analytics Product Roadmap

## Product direction

The product should evolve from answering only:

> Where are wards placed?

to answering:

> What vision did a team establish, why did it establish it, how predictable was it, and what happened afterward?

A heatmap is useful for exploration, but coaches, analysts, teams, and serious
players need information that leads to decisions. The core product should
therefore connect ward location with time, lifecycle, game state, objectives,
opponent behavior, and measurable outcomes.

## Product principles

- Keep raw observations separate from inferred intent.
- Prefer explainable metrics over opaque scores.
- Always condition comparisons on game time, side, patch/map version, and game
  state where possible.
- Preserve historical map assets rather than moving old data onto a new map.
- Describe correlations as correlations. A ward near an objective does not prove
  that it caused the objective outcome.
- Make the basic public map useful and shareable; reserve workflow, private data,
  advanced comparison, exports, and expensive computation for paid plans.

## 1. Vision timeline

Build a match timeline with a draggable time control. At the selected moment,
the map should display:

- Active observer wards.
- Active sentries.
- Team and player that placed each ward.
- Placement time and remaining lifetime.
- Destroyed or expired wards.
- Placement and destruction events near the selected time.
- Approximate observer vision and sentry true-sight coverage.

This should answer questions such as:

- What vision existed before Roshan?
- Was a farming area actually protected?
- Did a team enter an area without vision?
- Were multiple wards covering the same space?
- How long did a team control a region?

### Initial implementation

The current ward records already contain placement time, duration, type,
position, team, and destruction state. These are sufficient for a basic ward
lifecycle timeline.

The first coverage rendering may use nominal circles. It must be labeled as an
approximation because terrain, elevation, trees, time of day, and other game
mechanics affect actual vision.

## 2. Location intelligence

Every ward-location cluster should have a detail panel with metrics such as:

```text
Radiant triangle cliff
────────────────────────────
Placements:             184
Average placement:    18:42
Destroyed:              63%
Median survival:       2:14
Expired naturally:      31%
Most common player:    Player X
Common sentry zone:    South edge
Radiant usage:           72%
Dire usage:              28%
```

### Survival metrics

Measure more than whether a ward was destroyed:

- Time until destruction.
- Probability of surviving 30 seconds.
- Probability of surviving two minutes.
- Probability of expiring naturally.
- Median and percentile survival time.
- Survival by team, opponent, tournament, side, and map version.

A ward destroyed after ten seconds and a ward destroyed after five minutes
should not be treated as equivalent outcomes.

### Deward-risk map

Show locations according to their historical risk:

- Green: frequently survives.
- Yellow: moderate risk.
- Red: frequently found quickly.

Filters should include:

- Match phase.
- Radiant or Dire.
- Observer or sentry.
- Team and opponent.
- Player.
- League or tournament.
- Patch and map asset version.
- Net-worth state.
- Recent-match window.

### Placement timing

For every location, show when it is normally used:

- Before the horn.
- Laning phase.
- First night.
- 10–15 minutes.
- 15–25 minutes.
- Late game.
- Before and after objective windows.

The same position can serve a different purpose depending on when it is used.

## 3. Opponent scouting and predictability

Create a report for a selected team or player containing:

- Most frequently used observer and sentry locations.
- First-ward tendencies.
- First-night tendencies.
- Radiant-versus-Dire differences.
- Locations repeated across consecutive matches.
- Favorite locations by match phase.
- Common sentry zones around observer locations.
- Player responsible for each category of ward.
- Time taken to replace destroyed wards.
- Changes against specific opponents.
- Changes between recent and older matches.

### Predictability score

A predictability score can summarize the concentration and repetition of ward
placements:

```text
Team A observer predictability: 74/100

62% of its 10–20 minute observer wards fall into five clusters.
Three locations were repeated in at least four of the last six games.
```

The calculation must be visible to users. It should be based on factors such as:

- Share of placements contained in the top location clusters.
- Repetition across consecutive games.
- Diversity of locations after controlling for side and match phase.
- Similarity between recent matches.

The score measures predictability, not overall team or player quality.

## 4. Sentry effectiveness

Sentries require different analysis from observers. Useful measurements include:

- Whether a sentry revealed an observer that was subsequently destroyed.
- Time between sentry placement and enemy ward destruction.
- Number of enemy observers covered.
- Sentry placement with no known enemy ward nearby.
- Observer-and-sentry pairing.
- Coverage already provided by another sentry.
- Defensive versus offensive placement.
- Dewards per sentry.
- Time for which a strategically important area was protected by true sight.

Example summary:

```text
Sentry effectiveness
────────────────────────────
Sentries placed:          31
Led to a deward:          12
Successful within 20 s:    9
No enemy ward detected:   15
Coverage overlap:          4
```

Do not initially label every sentry that finds no observer as "wasted." It may
have protected a smoke, objective, farming area, or route even without producing
a deward. Use neutral labels such as "no detected enemy ward."

## 5. Observer–sentry interaction

Detect relationships based on distance and time:

- A sentry placed near an allied observer.
- A sentry placed shortly before an enemy observer is destroyed.
- An observer placed shortly after an area is cleared.
- Repeated sentry sweeps through the same region.
- An observer placed just outside frequently used sentry coverage.

A valuable visualization would overlay:

```text
Common observer locations
              +
Opponent sentry coverage probability
```

This can identify alternative ward positions that provide similar information
while avoiding the opponent's most predictable sentry zones.

## 6. Game-state context

Ward placement must be interpreted using the state of the match. The application
already stores Radiant and Dire net worth at placement, so it can classify a ward
from the placing team's perspective as:

- Far ahead.
- Slightly ahead.
- Approximately even.
- Slightly behind.
- Far behind.

Example report:

```text
When ahead:
  48% of wards are in enemy territory.

When behind:
  71% of wards are near the base or defensive jungle entrances.
```

Thresholds should be time-aware or percentage-based. A 3,000-gold advantage at
ten minutes is not equivalent to the same advantage at 50 minutes.

### Avoid misleading location win rates

Raw win rate by ward location is likely to confuse cause and effect. A deep ward
may correlate with winning because teams that are already ahead can safely place
it. Any outcome comparison should control for at least:

- Net-worth difference at placement.
- Match time.
- Side.
- Patch and map version.
- Remaining towers and barracks, when available.
- Opponent strength or tournament level, when practical.

## 7. Named regions and territory control

Divide every supported map version into stable, meaningful regions, for example:

- Radiant safe-lane jungle.
- Dire safe-lane jungle.
- Radiant triangle.
- Dire triangle.
- River and rune areas.
- Roshan pits and approaches.
- Tormentor areas.
- Twin gates.
- Base approaches.
- Lanes.

Calculate over time:

- Important territory under observer coverage.
- Offensive versus defensive vision share.
- Contested regions.
- Time without vision around objectives.
- Speed at which control moves after a tower falls.
- Region transitions before and after fights or objectives.

Named regions make reports easier to interpret and discuss than raw coordinates
or anonymous cluster identifiers.

## 8. Objective vision

Extend replay parsing to connect vision with:

- Roshan attempts and kills.
- Tormentor attempts.
- Tower pushes and tower destruction.
- High-ground attempts.
- Smoke movements.
- Team fights and pickoffs.
- Rune timings.

Useful measurements include:

- Vision established 30–120 seconds before an objective.
- Enemy vision cleared before an objective.
- Objective approach paths covered.
- Remaining ward lifetime when an objective begins.
- Wards placed after winning a fight.
- Vision lost immediately before a failed objective.
- Time between establishing vision and beginning the objective.

The UI should show the sequence rather than only aggregate counts:

```text
22:14 enemy observer destroyed
22:31 allied observer placed on approach
22:48 team enters Roshan area
23:07 Roshan attempt begins
23:42 Roshan killed
```

These events establish useful context but do not by themselves prove causality.

## 9. Ward impact

The long-term differentiating feature should estimate what an observer actually
accomplished. Candidate signals include:

- Enemy hero-seconds visible.
- Number of unique enemy heroes revealed.
- Important movement paths revealed.
- Warning time before an enemy rotation.
- Kills occurring while a target was visible.
- Objective attempts detected.
- Unique vision not supplied by another observer.
- Ward survival duration.
- Redundant overlap with allied vision.

An explainable score might combine these signals:

```text
Impact: 82

+ Spotted four enemy heroes
+ Provided 11 seconds of warning before a rotation
+ Covered the Roshan approach
− Overlapped another observer for 74 seconds
```

The score must expose its components and weights. It should never appear as an
unexplained AI judgment.

### Additional data required

Accurate impact analysis will require replay parsing beyond ward events:

- Periodic hero positions.
- Team visibility state, if available.
- Deaths and combat events.
- Smoke activation and breaking.
- Objective events.
- Towers and other vision sources.
- Relevant tree destruction or map-state changes.
- Day/night transitions.

This is significantly more expensive than the earlier roadmap items and should
follow validation of the simpler scouting product.

## 10. Player tendencies and benchmarking

For individual players, show:

- Wards placed per match.
- Observer/sentry distribution.
- Median placement time.
- Median ward survival.
- Dewards attributable to sentries.
- Preferred regions.
- Offensive/defensive balance.
- Behavior while ahead and behind.
- Location diversity and predictability.
- Differences by hero.
- Differences between position 4 and position 5, when role data is available.

Compare players against an appropriate cohort instead of using only a global
leaderboard:

```text
Player X versus professional position-5 baseline

Ward survival:       +18%
Location diversity:  −12%
Early vision:        +24%
Objective coverage:   +6%
```

Benchmarks should be filtered by patch, role, tournament level, and side where
sample size permits.

## 11. Contextual recommendations

Once the historical dataset is sufficiently large, generate evidence-based
suggestions:

```text
Against Team A, this location is dewarded within 90 seconds in 68% of
recent matches.

Two nearby alternatives historically provide similar objective coverage with
lower deward rates and lie outside Team A's most common sentry clusters.
```

Recommendations should include:

- Evidence and sample size.
- Filters used to select historical matches.
- Alternative locations.
- Coverage tradeoffs.
- Historical deward risk.
- Confidence or uncertainty.

The wording must remain probabilistic. Historical behavior cannot guarantee what
an opponent will do in the next match.

## 12. Core scouting report

The first cohesive product should be a page titled:

> How this opponent controls vision

Inputs:

- League or tournament.
- Team or player.
- Opponent, optionally.
- Side.
- Match phase.
- Recent-match window.
- Patch/map version.

Output:

- Preferred observer and sentry locations.
- Placement timing.
- Ward survival and deward risk.
- Sentry coverage.
- Repetition and predictability.
- Differences by side and game state.
- Downloadable and shareable report.

This packages the existing data into a specific coaching workflow and is a
strong candidate for the first paid feature.

## Data and schema direction

### Keep map versions immutable

Assets should remain versioned:

```text
static/img/tiles/2/...
static/data/elevations/2
static/img/tiles/3/...
static/data/elevations/3
```

Do not overwrite an old version when the Dota map changes.

### Move map version to the match level

The current map asset version belongs to a league. This assumes every match in a
league uses the same map. A league can span a major map update, so the robust
design is to assign `map_asset_version` to each match.

Ward queries and cluster compilation should group by map asset version. Results
from different geometries should not be combined into one spatial layer unless
an explicit coordinate transformation exists.

### Preserve raw facts

Store raw replay-derived events separately from derived analytics. Derived
clusters, scores, region assignments, and reports should be reproducible when an
algorithm changes.

Candidate future concepts include:

- Objective events.
- Ward lifecycle events.
- Periodic hero-position samples.
- Map regions associated with a map asset version.
- Derived ward-to-sentry attribution.
- Derived ward impact components.

## Delivery phases

### Phase 1: use current data

1. Ward lifecycle timeline.
2. Location-cluster detail cards.
3. Survival and time-to-deward maps.
4. Placement timing distributions.
5. Team/player predictability reports.
6. Basic sentry-to-deward attribution.
7. Net-worth-context filters.

### Phase 2: add structured map and objective context

1. Versioned named map regions.
2. Territory-control summaries.
3. Objective and tower replay events.
4. Objective-vision timelines.
5. Better sentry-effectiveness classification.
6. Exportable scouting reports.

### Phase 3: reconstruct vision impact

1. Parse hero movement and visibility-related events.
2. Calculate terrain-aware coverage where feasible.
3. Measure unique enemy visibility and warning time.
4. Add explainable ward-impact scoring.
5. Generate contextual placement alternatives.

## Recommended implementation order

The recommended overall priority is:

1. Vision timeline.
2. Cluster detail cards.
3. Survival and time-to-deward analysis.
4. Team/player predictability.
5. Sentry-to-deward attribution.
6. Named map regions and territory control.
7. Objective events and objective-vision reports.
8. Hero movement and actual vision-impact analysis.
9. Contextual ward recommendations.

The first five items mostly use data already stored by the application. Objective
analysis requires additional replay events. Actual vision reconstruction is the
hardest step because it depends on movement, terrain, elevation, trees,
day/night state, and other sources of vision.

## Success criteria

The roadmap should be validated with coaches and analysts rather than only page
traffic. Useful signals include:

- Time saved when preparing for an opponent.
- Number of reports created and shared.
- Repeat use before matches or tournaments.
- Saved filters and revisited analyses.
- Percentage of suggestions that users mark as useful.
- Willingness to pay for private data, exports, and automated reports.

The central product hypothesis is:

> A coach or analyst will pay for a reliable report that turns many replay files
> into an understandable account of an opponent's vision habits.
