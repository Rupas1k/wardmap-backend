# Ward impact score

## Purpose

Ward impact is an explainable raw score for what one observer ward contributed
during one match. It should answer:

> What useful information did this ward provide, and what happened while that
> information was available?

The score is not a prediction that a ward caused a kill or won the match. It is
an accounting system for observed information, timely warnings, associated
actions, and strategic coverage.

The product should use two names consistently:

- **Ward impact** for the score of an individual observer ward.
- **Fantasy points** for aggregations across a player, team, match, or series.

Sentries require a separate scoring model based on detection, protected area,
and dewards. They should not be forced into the observer formula.

## Design principles

1. **Reward information, not passive survival.** A safe ward that sees nothing
   should not beat a short-lived ward that exposes a smoke rotation.
2. **Preserve raw evidence.** Store reveal and outcome events so weights can be
   changed without reparsing demos.
3. **Show the breakdown.** Every score must be reproducible from visible
   components and published weights.
4. **Do not imply causality.** A fight following a reveal is an associated
   outcome unless stronger evidence supports attribution.
5. **Prevent duplicate credit.** Multiple allied providers may contribute, but
   the same information should not be awarded at full value repeatedly.
6. **Separate realized and structural value.** Enemy traffic measures what
   happened; useful map coverage measures what the ward was positioned to do.
7. **Avoid rewarding winning twice.** Team victory and gold advantage are
   context for comparisons, not major sources of points.
8. **Compare like with like.** Rating and percentile calculations should group
   by map version, side, game phase, and broad location.

## Score structure

Keep the raw score open-ended. A normal useful ward can land around 40–60
points, an exceptional ward around 80–100, and a genuinely match-defining ward
may exceed 100.

```text
ward impact =
    scouting value
  + warning value
  + smoke value
  + combat contribution
  + objective contribution
  + structural coverage
  + lifecycle adjustment
  - redundancy penalty
  - failure penalty
```

All components should be stored separately. The combined number is a view over
the components rather than the canonical data.

## 1. Scouting value

Scouting is the foundation and should normally contribute the largest share of
points.

### Total enemy hero-seconds

One visible enemy for one second contributes one hero-second. Visibility is
additive across heroes. This measures traffic through the ward's vision, but it
does not establish that the ward supplied new information.

Use diminishing returns so one stationary enemy cannot dominate the score:

```text
traffic points = 3.0 × sqrt(total enemy hero-seconds)
```

The exact coefficient should be calibrated from real distributions.

### Unique enemy hero-seconds

Time during which the ward is the only allied vision provider should be worth
substantially more than redundant visibility:

```text
unique points = 5.0 × sqrt(unique enemy hero-seconds)
shared points = 1.0 × sqrt(total seconds - unique seconds)
```

All allied providers must participate in the uniqueness calculation: heroes,
creeps, controlled units, towers, buildings, watchers, and other wards.

### Distinct heroes

Award a small diversity bonus for distinct real enemy heroes seen. Use a cap so
briefly touching five heroes is not more important than sustained useful
vision.

```text
distinct hero bonus = min(distinct heroes, 5) × 1.5
```

Illusions, clones, summons, and disconnected/replaced entities must not inflate
this count. Whether Meepo clones count as the same strategic hero should be
explicitly defined.

### First reveals

A first reveal occurs when the ward changes an enemy from not visible to
visible. It is more valuable than continuing to observe an already-known hero.

Possible bonuses:

- +2 for a new reveal after at least 5 seconds unseen.
- +4 after at least 15 seconds unseen.
- +6 when the enemy was last known in a different named region.

Use a cooldown per ward/enemy pair to prevent points from flickering at the
edge of vision.

## 2. Warning value

A reveal becomes actionable when it gives allies time to react to danger.
Measure warning events rather than guessing player intent.

Potential protected targets:

- Allied heroes.
- Towers, barracks, and the Ancient.
- Roshan and Tormentor areas.
- Wisdom, power, bounty, and water rune areas.
- Stacked camps or another explicitly valuable farming area.

For each first reveal, estimate the earliest subsequent time the enemy reaches
a protected target or relevant region. Award more for earlier warning, capped
to avoid excessive credit for distant incidental sightings:

```text
warning points = importance × clamp(warning seconds / 12, 0, 1) × 6
```

Record the evidence as a sequence:

```text
18:42 enemy revealed
18:49 allied carry begins retreat
18:54 enemy reaches the lane
warning time: 12 seconds
```

Retreat detection can later add confidence, but the first version only needs
the reveal and approach timing.

## 3. Smoke value

Smoke detection is one of the clearest high-impact vision events, but several
mechanics must be separated.

### Smoke rotation revealed by a ward

Track Smoke of Deceit activation and the smoked state for each enemy hero. A
ward receives smoke-reveal credit when:

1. The enemy was smoked shortly before entering the ward's vision.
2. The ward is a provider of the first allied visibility during that rotation.
3. The enemy was not already visible from another allied provider.

Record:

- Number of smoked heroes revealed.
- Whether this was unique ward vision.
- Time since smoke activation.
- Distance traveled while smoked.
- Warning time before contact with allies or an objective.
- Whether allies visibly disengaged or repositioned.
- Whether the smoke produced a kill despite the reveal.

Suggested initial value:

```text
smoke reveal = 8 base points
             + 2 per additional smoked hero
             + warning bonus up to 8
             + 4 if allies avoid contact for 15 seconds
```

Cap a single smoke sequence near 25 points.

### Smoke breaking near an enemy hero

A ward does not itself break Smoke of Deceit; proximity to an allied hero or
tower does. The score must distinguish:

- **Ward revealed smoked movement before the break.** Strong ward credit.
- **Smoke broke, then the ward supplied vision.** Smaller follow-up credit.
- **Smoke broke solely because of an allied hero/building and the ward added no
  unique vision.** No smoke-reveal bonus.

If demo fields do not expose the exact smoke state reliably, preserve a
lower-confidence inferred event rather than treating it as certain.

### Smoke protected by allied vision

An allied ward may protect a team's own smoke route by revealing enemies that
could intercept or break it. This is real value, but attribution is weaker.
Track it as a future contextual component rather than awarding it in version 1.

## 4. Combat contribution

Ward-assisted combat should reward information available during the setup and
fight, not every death occurring inside the vision circle.

### Fight detection

Define a team fight from replay evidence rather than a hard-coded kill window.
A practical detector can group damage, disable, death, buyback, and hero
proximity events when:

- At least two heroes from each team participate or are within the fight area.
- Combat activity continues with gaps shorter than a configurable timeout.
- The event has meaningful hero damage, a death, or an objective transition.

Store a fight envelope with start/end time, location, participants, deaths,
damage, disables, and outcome.

### Vision phases of a fight

Score ward contribution across three phases:

1. **Setup vision:** reveals an enemy participant within roughly 20 seconds
   before combat starts.
2. **Engagement vision:** keeps enemies visible during the opening engagement.
3. **Chase/retreat vision:** reveals escaping or pursuing enemies after the main
   exchange.

Possible component:

```text
fight vision points =
    4 × uniquely revealed participants before the fight
  + 0.15 × unique participant vision-seconds during the fight
  + 2 × enemy deaths while uniquely visible
```

Cap points per fight and split credit between wards when coverage overlaps.

### Attribution confidence

Label fight contributions instead of presenting them all equally:

- **Strong:** unique reveal before initiation or unique vision of a target when
  the first allied attack/disable occurs.
- **Moderate:** unique vision during meaningful damage or pursuit.
- **Weak:** shared vision during a nearby fight.

Only strong and moderate events should materially affect the raw score.

### Kill contribution

A ward-assisted kill needs more than spatial proximity. Candidate conditions:

- Target was visible through the ward at first allied attack or disable.
- Ward supplied unique vision during part of the chase.
- Target was first revealed shortly before initiation.
- Kill occurred within a bounded time after the last useful ward reveal.

Do not award a full kill bonus merely because the death coordinate lies inside
the ward radius. Award no kill points when allied natural vision already made
the ward irrelevant.

## 5. Objective contribution

Objectives produce understandable strategic value and should be scored through
explicit windows.

Candidate objectives:

- Roshan and Aegis-related events.
- Tormentor.
- Towers, barracks, and Ancient.
- Wisdom and power runes.
- Twin Gate approaches when strategically relevant.

An objective contribution can include:

- Establishing vision before an allied attempt.
- Revealing an enemy approach or contest.
- Revealing that an enemy started an objective.
- Maintaining unique vision during an engagement.
- Covering a retreat after the objective.
- Surviving an enemy deward sweep during the setup window.

Suggested windows should depend on the objective. Roshan may use 45 seconds
before through 20 seconds after; a power rune may use 15 seconds on either side.

Avoid awarding points for merely being geometrically near an objective. Require
either useful traversable coverage, enemy traffic, or an actual objective event.

## 6. Structural coverage

Realized traffic is partly luck. Structural coverage recognizes a ward that is
positioned to provide useful information even when no enemy happens to pass it
in that match.

Measure:

- Visible traversable GridNav cells.
- Unique cells not covered by another allied observer.
- Ramps, entrances, junctions, and chokepoints covered.
- Named objective approaches covered.
- Common movement lanes learned from aggregate hero trajectories.
- Coverage of enemy-accessible territory rather than unreachable cliffs.

Structural coverage should remain a modest component, around 10–15% of a
typical score. Otherwise theoretical map geometry will outweigh actual match
impact.

Static path importance must be versioned by map version. A future learned
traffic model should be trained without leaking the evaluated match into its
own baseline.

## 7. Lifecycle adjustment

Lifetime is context, not a direct measure of quality.

Reward utilization:

```text
utilization = useful information seconds / effective lifetime
```

Effective lifetime ends at the earliest of natural expiry, destruction, match
end, or reliable owner denial/removal. A short ward with high utilization can
outscore a long inactive ward.

Small adjustments may include:

- +1 to +3 for surviving a relevant enemy detection sweep.
- 0 adjustment for natural expiry by itself.
- −2 to −8 for an early deward before producing value.
- Little or no deward penalty after the ward already generated high impact.

The deward penalty should decay as realized impact rises:

```text
early deward penalty = base penalty × exp(-impact before deward / 12)
```

This avoids teaching users that safe wards are always better than aggressive
high-value wards.

## 8. Redundancy

Redundancy is not automatically bad: overlapping vision can maintain coverage
after a deward or protect an objective from different angles. Penalize only
information that is genuinely duplicated without a clear resilience benefit.

Track separately:

- Hero-seconds shared with other observers.
- Hero-seconds already supplied by allied non-ward providers.
- Traversable cells shared with observers.
- Time overlap between nearby observers.
- Whether one ward survives after the other is destroyed.

The strongest approach is to give full points to unique information and reduced
points to shared information rather than applying a large global penalty.

## 9. Failure and negative events

Negative points should be rare, bounded, and explainable:

- Ward immediately dewarded without useful vision.
- Ward placed inside known enemy true sight, if reconstructable.
- Ward replaces an allied observer while wasting substantial remaining
  lifetime, if the game permits and the event is reliable.
- Ward reveals no enemies, covers little useful terrain, and substantially
  overlaps another observer for most of its life.

Do not penalize:

- A ward sacrificed after revealing a smoke.
- A ward destroyed during a successful objective setup.
- A ward with no enemy traffic but meaningful structural coverage.
- The planter for losing the match.

## Proposed scoring versions

### Version 0: current parser data

Use only measurements already available or nearly available:

```text
impact_v0 =
    5.0 × sqrt(unique enemy hero-seconds)
  + 1.0 × sqrt(shared enemy hero-seconds)
  + 1.5 × distinct heroes spotted
  + lifecycle adjustment
```

This version is deliberately narrow and should be labeled **Scouting impact**.
It can be validated before combat attribution is introduced.

### Version 1: reveal and map context

Add:

- First reveals.
- Warning time.
- Smoke rotation reveals.
- Traversable and strategic coverage.
- Objective approach events.
- Better redundancy attribution.

### Version 2: combat and objective outcomes

Add confidence-weighted:

- Fight setup, engagement, and chase contribution.
- Kill and save associations.
- Objective start, contest, and completion contribution.
- Allied reaction evidence.

Version every formula. Store `impact_version` with derived scores and never
compare values produced by different versions without recalculation.

## Normalization and ratings

Raw impact describes what happened. It should not be silently normalized.
Expose a separate **Ward rating** or percentile based on comparable wards:

```text
reference cohort =
  map version
  + side
  + observer ward
  + game phase
  + broad map region
  + optional gold-state band
```

Useful derived values:

- Raw ward impact.
- Expected impact for the cohort.
- Impact above expected.
- Cohort percentile.
- Confidence/sample size.

Gold advantage should primarily select a cohort. Directly adding points for
placing while behind would reward context rather than contribution.

## Aggregating fantasy points

Player and team reports should include both volume and efficiency:

- Total impact.
- Impact per observer.
- Impact per 10 minutes.
- Impact above expected.
- Percentage of observers above the cohort median.
- Smoke reveals and fight contributions.
- Number of observers placed.

For a fantasy competition, a possible player total is:

```text
fantasy points =
    total ward impact
  + 0.5 × total impact above expected
  + capped consistency bonus
```

Never publish player totals without the observer count and matches played.

## Data to preserve

Prefer replay-derived event tables over adding dozens of irreversible aggregate
columns. Candidate records include:

### Reveal event

- Match, ward, enemy player, start, end.
- Total and unique duration.
- Providers present.
- Previous visibility and previous known region.
- Smoke state and invisibility state.
- Ward age at reveal.

### Warning event

- Reveal event.
- Protected target/region.
- Time and distance to contact.
- Inferred allied reaction and confidence.

### Fight event

- Start/end, region, participants, deaths, damage, disables, outcome.
- Setup, engagement, and chase intervals.

### Ward-fight contribution

- Ward and fight.
- Revealed participants.
- Unique vision-seconds.
- First-attack/disable visibility.
- Attribution confidence.

### Objective event and contribution

- Objective type and event timestamps.
- Team, outcome, approach/contest regions.
- Ward contribution and confidence.

Derived ward components can then be recalculated quickly without reading the
demo again.

## Validation strategy

Before exposing fantasy rankings:

1. Sample wards across low, medium, and high scores.
2. Render their vision/event timelines for human review.
3. Ask experienced players or analysts to rank the same wards without seeing
   the score.
4. Investigate disagreements by component rather than tuning the final number
   blindly.
5. Check for systematic bias by side, role, game length, winning state, region,
   and number of wards placed.
6. Confirm that score increases correspond to evidence users can understand.

Useful safeguards:

- Component caps per event.
- Diminishing returns for repeated sightings.
- Confidence labels for inferred smoke/fight attribution.
- Minimum sample sizes for leaderboards.
- Distribution monitoring after every formula change.

## Open questions

- How reliably does the demo expose smoke activation, modifier removal, and the
  exact reason smoke ends?
- Should naturally visible high-ground enemies count when the ward is only one
  of several providers?
- How should invisibility, True Sight, and reveal mechanics interact with
  observer credit?
- Can allied reactions be inferred robustly from movement changes?
- How should shared credit be divided between two complementary wards?
- What objective windows best match professional play?
- Should learned route importance be global, patch-specific, or league-specific?
- How should score confidence fall when provider or entity state is incomplete?

## Recommended next step

Implement and validate `impact_v0` from the existing total vision-seconds,
unique vision-seconds, heroes spotted, lifetime, and deward timing. At the same
time, preserve individual reveal intervals in the parser so first reveals,
smoke sequences, warning time, and fight attribution can be added without
another full redesign.
