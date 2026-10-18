# Repair from day zero: light-only leads, but timing matters

Restoring the light gate produces the strongest renewal on this four-seed
panel, including one family with qualifying children in every scoring window.
It is not a universal fix. Two shrub families still go extinct, and restoring
both gates performs worse overall than restoring either gate separately.
The earlier late-rescue result does not generalize uniformly to early growth.

All 32 [planned replays](leaf-population-gates-panel-protocol.md) completed in
190.037 seconds, without failures or retries. These are 16 distinct conditions
with logging-on/off repeats, not 32 independent samples. Each runs through
day 608. All 352 state/history/pixel captures pass validation, including exact
matched logging repeats and unchanged-arm comparisons with the original
population archive.

## Conditions

The four original rainfed weather seeds and fixed variants are unchanged.
Only shrub founder family 2 and its descendants receive the derived repair
controller, now from the first decision after tick zero. Flower and ground-cover
families retain Search 1. Growth, memory, costs, weather, spacing, capacity,
seed lifetime, and the renewal objective remain frozen. No training or model
promotion occurs.

The native `--gate-panel` command records activation tick zero in its `TGR1`
state and JSON identity. Existing day-208 commands and evidence remain intact.
Resource traces stop at day 256; complete ancestry and seed histories continue
through day 608.

## Results by seed

Each cell gives **renewal credits out of 12; living shrubs at day 608**.
Credits count qualifying children of non-founder parents, with both parent
and child surviving their own first 32 days. Births must fall in `(192,576]`,
and each of the six 64-day windows contributes at most two credits.

| Weather seed | Unchanged | Light restored | Condition restored | Both restored |
|---|---:|---:|---:|---:|
| `58d7d6ca` | 0; 0 | 8; 6 | 6; 4 | 4; 8 |
| `9a903368` | 0; 0 | 8; 4 | 4; 2 | 0; 0 |
| `6b9c1a3e` | 0; 0 | 0; 0 | 0; 0 | 0; 0 |
| `59818bc3` | 2; 0 | 0; 0 | 0; 0 | 0; 0 |

On `58d7d6ca`, all three changes preserve the family. Light-only produces
qualifying-child counts `[4,0,0,2,2,6]`, capped to eight credits. Both-restored
fills all eight plant slots with shrubs, but its counts are `[4,0,0,2,0,0]`:
four capped credits and no qualifying births in the final two windows. A full
garden is therefore not equivalent to ongoing replacement. Condition-only
retains one young child born on day 577, still short of age 32 at the endpoint;
it is neither an establishment success nor a death.

On `9a903368`, light-only produces counts `[2,1,1,2,1,1]`: successful renewal
in all six windows, eight credits, and four surviving descendants. The family
reaches generation 6, although that maximum includes historical plants, not
just endpoint survivors. The founder dies at day 62.625, so the result is not
merely prolonged founder survival. Condition-only also rescues this family,
with counts `[2,0,1,0,1,0]` and two living descendants, including generation 7.
Both-restored loses the family by day 66; all three of its offspring die
before age 32. The unchanged family goes extinct at day 78.859375.

On `6b9c1a3e`, no variant produces any shrub offspring. Light-only and
both-restored extend founder life from day 14.828125 to day 30.5625, but
all four families lose their last pending seeds at day 32.90625. Longer adult
survival alone does not solve recruitment here.

On `59818bc3`, every from-start arm loses the shrub family. Extinction occurs
at days 385.9375, 257.890625, 194, and 32.9375 for unchanged, light-only,
condition-only, and both-restored respectively. This is the same seed where
[restoring light after day 208](leaf-population-gates-transfer.md) preserved
descendants through day 608. Applying it throughout early growth changes that
outcome substantially. The trajectories diverge before the old switch, so
this comparison does not identify one local resource cost as the cause.

## Panel totals and competition

These totals describe four known conditions per variant. Logging repeats
are counted once. Offspring counts include all births through day 608, not
only births inside the scoring interval.

| Outcome | Unchanged | Light restored | Condition restored | Both restored |
|---|---:|---:|---:|---:|
| Capped renewal credits, out of 48 | 2 | 16 | 10 | 4 |
| Living shrub families, out of 4 | 0 | 2 | 2 | 1 |
| Dormant seed-only shrub families | 0 | 0 | 0 | 0 |
| Original shrub founders still alive | 0 | 1 | 0 | 1 |
| Shrub offspring born | 14 | 50 | 47 | 21 |
| Offspring reaching age 32 | 7 | 35 | 22 | 13 |
| Offspring dying before or at age 32 | 7 | 15 | 24 | 8 |
| Young offspring still alive | 0 | 0 | 1 | 0 |
| Flower family extinctions | 0 | 0 | 1 | 2 |
| Ground-cover family extinctions | 2 | 2 | 1 | 1 |

The gains redistribute competitive outcomes. On `58d7d6ca`, light-only loses
ground cover, condition-only loses flowers, and both-restored loses both.
On `9a903368`, condition-only retains all three families, whereas light-only
retains flowers and shrubs but loses ground cover. Equal aggregate loss counts
can also conceal different seeds: light-only loses ground cover on the first
two seeds, while unchanged loses it on `9a903368` and `59818bc3`.

The existing established-descendant occupancy tie-breaker is retained in the
per-family evidence. These descriptive survival and competition counts do
not replace or modify the scoring rule.

## What this supports next

Light-only is the best of these four fixed alternatives on this panel, but it
is not ready for promotion. All seeds were previously examined, only one
layout is included, and two families still fail. Even the six-window success
is evidence through day 608, not proof of indefinite replacement.

The next useful step is an offline early-life comparison on `9a903368`: why
do light-only and condition-only each preserve descendants, while combining
them loses every shrub? The existing traces cover that entire failure. Compare
the first 64 days of repairs, resource budgets, offspring survival, and seed
blockers before proposing a context-sensitive controller or another training
run. Keep the contrasting from-start versus late-rescue result on `59818bc3`
as a second check. No additional native calls are needed for that diagnosis.

The subsequent [early-life diagnosis](leaf-population-gates-early.md) finds
near-expiry seed-bank handoffs in the successful arms and a persistently
spacing-blocked terminal seed in the combined arm. Founder repair expenditure
alone does not rank like family survival, and forbidding blocked purchases
would also discard the successful handoffs.

## Evidence and verification

The 2.14 MiB archive (`leaf-population-gates-panel-results.json.gz`, kept
locally) contains 32 receipts, 352 state/pixel captures, 16 resource traces,
exact model bytes, source and prospective-protocol snapshots, the binary digest,
and preflight results. The uncompressed collection occupies about 58 MiB. Two
workers, 180 seconds per call, a 900-second collection budget, and a 24 MiB
per-call output cap were respected.

Every arm matches the original archive's initial state and pixels after
explicit intervention-envelope validation. Unchanged arms also match at
days 32, 192, and 608, and their retained histories match all checkpoint
prefixes. Logging-on/off outputs match at every capture; resource and leaf
conservation, seed coverage, complete history, and scoring reconcile.

All seven preflight suites passed in 94.78 seconds, alongside ten preparation
tests. Native checks include strict warnings, UBSan, both activation boundaries,
descendant routing, allocation failure, reset, latched errors, and output
preservation. Published-evidence tests additionally verify offline byte-exact
round trips, recipe separation, scoring caps, young-offspring censoring,
and tamper detection. Those tests were added after collection; the archived
source snapshot and results are preserved. All 71 population analysis tests
pass in 33.68 seconds.

```sh
python3 -B sim/experiments/leaf_population/population_gates_panel.py unpack \
  benchmarks/garden-seasons/leaf-population-gates-panel-results.json.gz \
  artifacts/garden-population-gates-panel-review-v1
python3 -B sim/experiments/leaf_population/population_gates_panel.py verify \
  artifacts/garden-population-gates-panel-review-v1
```

Use a fresh output directory. Verification does not execute archived code.
Archive SHA256:
`2c1e0260aad599c631073d3f796bc2529e97632e1ff6110bd2f2998aff4900fd`.
Firmware, policy defaults, and ecological rules remain unchanged.
