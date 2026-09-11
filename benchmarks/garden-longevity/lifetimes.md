# Offspring lifetime investigation

The [renewable-flower correction](renewal.md) restarted reproduction, but births
and 1.25-second establishment do not establish a durable lineage. This pass adds
host-only measurements without changing ecology, policies, fitness, or weights.
Checkpoint `bb2f228` contains the pre-instrumentation implementation.

The comparison reuses frozen neural model CRC-32 `dc5e849d`, file SHA-256
`bd9f9c6ba7f5fd17309f917972da5f759c305c077798e1d4ba9a52701e2cd48b`,
and all 32 held-out seeds derived from `0x686f6c64`. There are three policies,
three layouts, and five horizons (2/4/8/16/24 cycles). Horizons are prefixes of
the same trajectories, not independent replicate worlds. Rates below pool births
across the 32 trials; siblings and successive generations are not independent
statistical samples.

## Definition

One full cycle is 3,840 logic ticks or 64 simulated seconds after birth. The plant
must be alive on that boundary; death exactly at it fails. Later death does not
erase credit. Use exact observed birth ticks: a newborn's ecology age counter
already reads 1 during its birth step.

For the survival denominator, include only births at least one cycle before the
cutoff. Separately report newer births still alive and newer births already dead.
Those recent deaths are known failures but do not enter a denominator that omits
their same-age living peers. Thus:

```text
eligible offspring = cycle survivors + deaths before/on the cycle boundary
all births = eligible offspring + recent living births + recent dead births
```

A **durable parent** is an offspring that survived a cycle and produced at least
one child that also survived a cycle. Count each parent once, even with multiple
qualifying children or after the parent has died and its world slot was reclaimed.
This is an observed count, not a reproductive success rate: young parents have
less time to qualify. The raw report also counts parents without requiring their
own cycle survival, and counts founder parents separately.

## Results at 24 cycles (25 minutes 36 seconds)

| Layout | Policy | Cycle survivors / eligible offspring | Rate | Recent living / dead | Durable parents | Trials with a durable parent |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Irrigated | Baseline | 258 / 415 | 62.2% | 2 / 3 | 130 | 31 / 32 |
| Irrigated | Adaptive | 185 / 292 | 63.4% | 2 / 1 | 58 | 21 / 32 |
| Irrigated | Neural candidate | 20 / 699 | 2.9% | 2 / 22 | 7 | 5 / 32 |
| Crowded | Baseline | 163 / 499 | 32.7% | 2 / 8 | 62 | 23 / 32 |
| Crowded | Adaptive | 114 / 247 | 46.2% | 0 / 6 | 35 | 15 / 32 |
| Crowded | Neural candidate | 2 / 1,386 | 0.1% | 1 / 61 | 0 | 0 / 32 |

All watered trials retain living plants. All unassisted trials are extinct by
cycle 2 and have no births, so their offspring survival rate is not applicable.

The crowded neural plot's 1,448 births and 1,448 short-term establishments mask
poor durability. Its final 67 living plants are **64 original flower founders**
and only three flower offspring (two cycle survivors plus one recent birth).
No shrub offspring were born; all 25 ground-cover offspring died before a cycle.
Across the irrigated neural trials, 17 flower and three ground-cover offspring
survived a cycle, and no shrub offspring were born. All 32 original flower
founders remain alive there too.

The seven durable neural parents in the irrigated layout are concentrated in
five world seeds: `cef5afdf` (2), `d751dbc0` (1), `8e2c8189` (2), `29219de7` (1),
and `8288e3e1` (1). These are useful inspection cases, not grounds for selecting
new weights against the held-out set.

## When offspring die

These mortality counts include every observed offspring death, even births too
recent for the complete-follow-up cohort above. Causes are flags at death, not
causal attribution to a particular earlier growth decision.

| Neural layout | Offspring deaths | Energy | Water | Mean age among deaths | Maximum age among deaths |
| --- | ---: | ---: | ---: | ---: | ---: |
| Irrigated | 701 | 648 | 53 | 39.32 s | 60.75 s |
| Crowded | 1,445 | 923 | 522 | 29.62 s | 47.75 s |

There are no combined/other offspring deaths in these neural batches. Every
observed neural offspring death occurs before 64 seconds; the few that cross
that boundary remain alive through the final cutoff. Means are conditional on
death, not mean lifespan estimates for the entire population.

Two distinct failure patterns are visible:

- Crowded: all 522 water-shortage deaths occur before 16 seconds of age, around
  late afternoon/sunset (sun bins 96–127 and 128–159). Of 923 energy-shortage
  deaths, 903 occur in the final two night bins (192–255), and eight at dawn.
- Irrigated: 50 of 53 water-shortage deaths occur before 16 seconds. Of 648
  energy-shortage deaths, 595 occur in those final two night bins and 36 at dawn.

This points to early water acquisition and overnight energy balance as separate
investigation targets. Histograms alone cannot distinguish root reach, local
competition, shading, body upkeep, growth expenditure, or seed expenditure.
Trace representative newborn resource budgets before changing those mechanics.
The subsequent [resource-budget traces and targeted probes](resources.md) do so
without changing the ordinary policy or ecology.

## Implications for training

At the two-cycle checkpoint, **none of the offspring in any of these held-out
policy/layout batches yet has a complete cycle of potential follow-up**. The
current two-cycle training horizon and short establishment gate cannot reveal
this particular long-term distinction in those worlds. The new measurements
remain diagnostics only; this patch does not silently replace the objective.

At eight cycles, irrigated neural offspring have 5 / 248 cycle survivors and one
durable parent; crowded neural offspring have 2 / 387 and no durable parents.
Longer runs already separate these behaviors well before cycle 24. Next, inspect
the two resource-failure patterns, then discuss a longer training horizon and
survival/descendant objectives. Preserve a fresh validation seed set when actually
selecting weights, and do not substitute a high birth count for durable turnover.

## Reproduce and validate

Keep the saved renewal model/training report (retraining with changed ecology
would not reproduce the frozen candidate), then choose a fresh output directory:

```sh
make host-build
docker compose run --rm firmware python3 benchmarks/garden-longevity/run.py \
  --model artifacts/garden-longevity-renewal-validated/champion.tgm \
  --training artifacts/garden-longevity-renewal-validated/training.json \
  --output artifacts/garden-lifetimes \
  --trials 32 --seed 0x686f6c64 --jobs 3
docker compose run --rm firmware python3 sim/summarize_garden_experiment.py \
  artifacts/garden-lifetimes/cycles-24.json
```

Raw schema-4 reports include lifetime totals per policy and per-trial species and
founder partitions, age/cause and sun-phase/cause matrices, and metric metadata.
Artifacts stay ignored; the runner records source/binary/model provenance and
refuses to overwrite a prior run. This sweep took about 114 seconds with three
host processes under UBSan; it is not a device performance measurement.

All original JSON fields, including state hashes, counters, resources, groups,
and policy telemetry, match the saved schema-3 renewal reports exactly across
all 1,440 outcomes. Comparison removes only `lifetimes`, `lifetime_followup`, and
the top-level `schema_version`; all five horizons match. Every new lifetime
partition and mortality histogram also passes accounting validation on those
1,440 outcomes.

`make host-check` passes all 14 tests after a pristine build. Lifetime unit tests
cover exact birth/death/cutoff boundaries, recent deaths, posthumous parent credit,
duplicate/rejected events without mutation, capacity exhaustion, each age and
sun-phase bucket boundary, and 64-bit age sums. Integration tests verify repeatable
JSON, species/founder/trial partitions, legacy death-cause agreement, null empty
age bounds, and the historical summary format. No firmware sources, memory
layout, world hash version, or trained weights changed; no device was flashed.
