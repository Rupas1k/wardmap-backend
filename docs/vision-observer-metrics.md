# Vision observer metrics

## Initial metrics

The first implementation records two explainable values for every observer
ward. Sentry wards do not contribute to either value.

### Enemy hero vision-seconds

Enemy hero vision-seconds measure how long enemy heroes are visible through a
ward's terrain-aware vision. Time is additive across heroes:

- One enemy visible for ten seconds contributes 10 hero-seconds.
- Three enemies visible for ten seconds contribute 30 hero-seconds.
- Two enemies visible for 2.5 seconds contribute 5 hero-seconds.

The parser samples vision once per second. Every observer capable of seeing an
enemy receives the full interval, even when another allied source also sees the
same enemy. This makes the metric a direct measurement of a ward's coverage,
not a claim that the ward was solely responsible for the information.

### Heroes spotted

Heroes spotted is the number of distinct enemy players visible through the
ward at least once during its lifetime. Repeated sightings of the same player
do not increase the count.

### Unique enemy hero vision-seconds

Unique enemy hero vision-seconds count time during which an enemy was visible
through this ward and no other allied provider. Allied heroes, creeps,
buildings, controlled units, watchers, and other observer wards all participate
in this attribution. A ward receives the interval only when it is the sole
provider revealing that enemy.

This metric should be displayed beside total enemy hero vision-seconds so users
can distinguish broad coverage from genuinely additional information.

## Next metrics, in priority order

### 1. First reveals and warning time

Record when a ward changes an enemy from unseen to seen, then measure the time
until that enemy reaches an allied hero, building, or objective area. This
captures whether the ward provided actionable warning rather than only passive
visibility.

### 2. Important movement revealed

Detect enemy crossings through map entrances and movement between named
regions. Count rotations, flanks, and retreat paths revealed by the ward while
retaining the underlying events so classifications can be revised later.

### 3. Objective vision contribution

Measure enemy sightings and vision coverage around Roshan, Tormentor, runes,
gates, and towers during relevant time windows. Report the objective and timing
instead of hiding them inside a single score.

### 4. Vision-assisted outcomes

Connect ward sightings with subsequent kills, deaths, smoke breaks, and fights.
Use explicit time windows and describe these as associated outcomes rather than
claiming that the ward caused them.

## Interpretation rules

- Keep every component visible; do not start with a combined efficiency score.
- Treat zero as a measured result and `null` as a replay that has not been
  processed by the vision observer.
- Compare wards within the same map version, side, and approximate game phase.
- Preserve raw reveal events if storage permits so improved attribution can be
  recomputed without reparsing the replay.
