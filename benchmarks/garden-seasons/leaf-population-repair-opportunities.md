# Short light windows escape lower-leaf repair selection

The relocated shrub's 15 lower leaves receive 146 repair-controller visits
during the recorded day, but no repairs. Every visit chooses WAIT because
light is below the model's threshold. Nine leaves never reach that threshold;
six briefly reach it while another leaf is selected. All nine of this shrub's
actual repairs go to its upper canopy. The original shrub repairs nine lower
leaves over the same day.

This is an offline audit of the existing [foliage traces](leaf-population-foliage.md),
following the [canopy-source diagnosis](leaf-population-canopy.md). It exactly
reconstructs all 512 recorded decisions and evaluates 12,800 recorded leaf
snapshots. No new simulation, training, controller change, or firmware change
was performed.

## Useful light is not sufficient light for this repair model

The frozen kernel selects one mature leaf per plant per ecology step:

```text
selected ordinal = (ecology step + lineage ID) % mature leaf count
```

The controller chooses WAIT or RENEW for that leaf; it cannot nominate a
different one. Body order is stable throughout these traces even when global
node indices move during compaction.

For both recorded leaf counts, the archived `condition` model requests RENEW
exactly when **light is at least 145 and condition is at most 192**. Integer
quantization and WAIT on tied scores are included. In contrast, the first
usable light-energy band starts at 64. A worn leaf can therefore receive
usable light and still fail the repair gate.

Only two hidden units affect this model's output. Their inputs are condition,
light, mature leaf count, and the fixed renewal water cost; stored energy and
water do not affect its decision. The kernel still enforces payment after a
request: nine energy and five water. All 24 actual requests across both
shrubs were accepted. No selected visit lacked energy, but water is not in
these leaf traces, so unselected opportunities are not proven affordable.

## Lower leaves face two different limitations

The lower canopy is the same fixed grid region used in the spatial diagnosis:
rows 7–13, with rows 0–6 classed as upper.

| Full-day lower-canopy observation | Original shrub 19 | Relocated shrub 17 |
|---|---:|---:|
| Mature leaves | 17 | 15 |
| Selected visits | 179 | 146 |
| Selected visits with light at least 64 | 39 | 23 |
| Selected visits passing the light gate | 10 | 0 |
| Accepted repairs | 9 | 0 |
| Leaves never reaching the light gate | 8 | 9 |
| Leaves with joint-gate windows but no selection in them | 0 | 6 |

All 146 relocated lower-leaf visits pass the condition gate and fail only
the light gate. Eleven of those leaves remain at zero condition throughout
the day. Zero condition does not itself prohibit repair: the original shrub
successfully repairs an upper leaf from zero to 255 at tick 587445.

The six relocated lower leaves with qualifying windows are body ordinals
0, 1, 3, 5, 8, and 19. Each is selected every 26 ecology steps, while its
observed contiguous qualifying windows last only two to ten steps. For
example, ordinal 3 at cell `(7, 10)` is selected at tick 587130 with light
118. It passes both gates at ticks 587250–587385, then is next selected at
587520 with light 107. The controller never sees that leaf during its
ten-step qualifying window.

Across these six leaves there are 36 qualifying but unselected leaf-samples:
eight in the afternoon before the focal dawn, none during dawn, and 28 after
the seed-bank opening. These are repeated snapshot opportunities, **not 36
possible extra repairs**. A real repair changes subsequent condition,
resources, shading, and possibly later opportunities.

Chronology matters: this calendar day starts at noon. Neither shrub has any
leaf passing the light gate during the focal dawn interval
`(152.75, 152.875]`. The later missed windows cannot directly explain the
already-missed opening purchase. Earlier repair history remains unresolved.

## Next check persistence before changing selection or thresholds

This explains the absence of lower-leaf repairs on the recorded day, not why
those leaves originally wore out or whether renewing them would repay the
cost. The trajectories also differ in position, age, body, and neighbors.

There are 256 ecology steps per day. For a fixed 26-leaf body, the selector's
phase relative to daylight repeats after `26 / gcd(26, 256) = 13` days;
for 24 leaves it repeats after three. One day's missed windows therefore do
not establish a permanent timing lock. Weather, shading, condition, and leaf
counts can also change, so this is a selector cycle, not a periodic world.

The next bounded investigation should observe one full 13-day selection-phase
cycle in both unchanged trajectories, starting at day 152, and distinguish
persistent lack of brightness from short windows eventually caught by the
selector. Keep the model, payment rules, ecology, and defaults unchanged.
Only then choose a selection or decision intervention. No further replays
have been run as part of this audit.

## Reproduce and verify

```sh
docker compose run --rm -T host-player python3 -B \
  sim/experiments/leaf_population/population_repair_opportunities.py \
  --check benchmarks/garden-seasons/leaf-population-repair-opportunities.json
```

Verification authenticates and fully checks the foliage archive, derives the
exact model bytes, validates the selector and every recorded decision, and
reconciles leaf, height, period, and whole-plant counts. Archived programs are
never executed. Missing model inputs are ignored only after proving they
cannot affect the output.

The derived evidence (`leaf-population-repair-opportunities.json`, kept locally)
is 380,049 bytes with SHA-256
`cd020156bc2cc485e2d74e70c91a4078cc44e4870a79344c581feb1b1fb24bd8`. Its source
foliage archive has SHA-256
`7462461ae0057387c2e5d1cb68fb61ab5b6671f3601640ecd1cac32b51ce5cf2`; the derived
model has SHA-256
`5e474190b02fb0d5d66ca58b391cae8961062aefbbc6617bafa7cc4d1ad4c51a`.

All 180 analysis tests pass in 51.08 seconds, including 13 new tests covering
quantized thresholds and ties, irrelevant inputs, compaction-safe joins,
corrupted decisions and coverage, unpaid requests, final-step repairs,
chronological windows, selector cycles, and exact archived results without
native execution.
