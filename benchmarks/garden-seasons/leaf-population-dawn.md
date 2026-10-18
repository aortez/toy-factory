# The successful shrub has healthier foliage despite fewer leaves

Original-placement shrub 19 has higher energy income than fewer-blocker shrub
17 on 96 of the 104 matched calendar days in `[128,232)`. Its mean condition
per leaf is higher at 95 day-end checkpoints. It has 24 leaves versus 26,
while both bodies remain at 32 nodes. Leaf quantity alone does not explain
the successful shrub's earlier reproductive readiness.

This extends the [step-budget finding](leaf-population-budget.md) without
running another simulation. The next useful measurement is each leaf's actual
light and condition during the focal dawn. Daily totals establish a persistent
difference, but cannot separate light exposure from leaf health at that moment.

## The focal day favors condition rather than leaf count

At day 152.875, original shrub 19 has 240 energy and buys a seed. Experimental
shrub 17 has 168 against the same 208 threshold. Their preceding calendar-day
boundary is day 152.000; it is not the dawn itself. On that boundary, the
original shrub's mean leaf condition is 52.7% of the maximum, versus 36.5% for
the experimental shrub. Both start with 252 energy and 508 water.

| Measurement over calendar day 152 | Original shrub 19 | Experimental shrub 17 |
|---|---:|---:|
| Nodes throughout the day | 32 | 32 |
| Leaves throughout the day | 24 | 26 |
| Mean leaf condition at day start, out of 255 | 134.46 | 93.12 |
| Gross energy income | 1,462 | 1,252 |
| Energy paid for upkeep | 256 | 256 |
| Leaf repairs | 15 | 9 |
| Energy paid for repairs | 135 | 81 |
| Energy paid for seeds | 48 | 0 |
| Energy at day end | 252 | 252 |

The successful plant spends more on repair, not less, and both fill storage
again by the end of the day. Some of those repairs occur after the focal
purchase, so the day's 15-versus-9 count cannot explain the purchase by itself.
The condition difference already exists at the start of the day and in the
neighboring days. A repair controller that preserves productive foliage is
a plausible lead, not a demonstrated intervention.

Across all 104 days, the original shrub earns 131,091 energy versus 117,771
(11.3% more), performs 991 repairs versus 852, and buys nine seeds versus zero.
It repairs more often on 63 days, less often on 29, and equally often on 12.
Neither plant grows further during this window. These are matched calendar
days, not matched ages: at the focal opening the plants are about 57.06 and
86.97 days old, in soil columns 0 and 7 respectively. They are different
generations with different neighbors and population histories.

## Dawn receipts also preserve different bank histories

The original garden already has two free seed slots before the experimental
garden has any. The records below show resources at each plant's actual visit,
not end-of-step state; occupancy is out of eight slots.

| Day | Original energy | Experimental energy | Original occupancy | Experimental occupancy |
|---|---:|---:|---:|---:|
| 152.84375 | 175 | 125 | 6 | 8 |
| 152.859375 | 200 | 139 | 6 | 8 |
| 152.875 | 240 | 168 | 6 | 7 |
| 152.890625 | 231 | 204 | 8 | 8 |

Both have sufficient water throughout. At day 152.875, the original passes
all checks while the experimental plant fails only energy. The later original
balance is after its earlier seed purchase and subsequent recovery; it is not
a no-purchase comparison. The experimental plant reaches 240 energy at day
152.90625, when the bank is already full.

These receipts are consistent with better resource recovery in the original
plant, but not a controlled race for identical openings. Its larger initial
bank opening also persists longer. More income would not by itself guarantee
long-term replacement; spacing and subsequent offspring survival still matter.

## Next measure light and condition at the same uptake step

Use a read-only trace over day 152 for these two plants, with a logging-off
repeat for each trajectory. Retain actual leaf positions, local light,
condition used for uptake, and the fractional energy remainder. Reconstruct
the measured income exactly before comparing its components.

The frozen kernel multiplies each active leaf's light band (`light / 64`,
integer division) by its condition, sums those contributions with the carried
remainder, then divides by 255. Comparing the light-band sum with the
condition-weighted sum can distinguish limited exposure from degraded leaves.
A healthy-leaf calculation would hold the recorded light field fixed; it is
not a simulated world with healthier foliage or changed shading.

This trace should answer whether shrub 17 misses the opening mainly because
its leaves receive less useful light, because those receiving light are worn,
or both. Keep repair, growth, placement, storage, and reproduction rules fixed.
No new reserve guard or controller training follows from the daily comparison
alone.

The [completed leaf-level comparison](leaf-population-foliage.md) now separates
these terms: during the focal dawn, light-weighted condition is nearly equal
but the original shrub has 1.84 times the usable light-band exposure. Across
the full day, exposure is nearly equal and condition weighting differs. The
time of income matters as well as its daily total.

## Reproducible offline comparison

The [analysis](../../sim/experiments/leaf_population/population_dawn.py)
authenticates the reproduction and budget archives, validates both trajectories
and their ancestry/resource traces, and joins the experimental step budgets.
It requires all 104 full days in order, sums resource flows rather than stocks,
normalizes condition by each plant's leaf count, and retains all matched daily
rows rather than selecting only the focal day. The complete day-152 budget also
matches the step ledger exactly.

The derived JSON (`leaf-population-dawn.json`, kept locally) contains nine input
digests and the full comparison. It is 332,108 bytes with SHA-256
`4fd7f8d23ac5358014ed845fb9c0c832f04c9c6b956a78f4deee945610d1c8ba`. To recompute
and verify it without native execution:

```sh
docker compose run --rm -T host-player python3 -B \
  sim/experiments/leaf_population/population_dawn.py --check \
  benchmarks/garden-seasons/leaf-population-dawn.json
```

Ten focused tests cover missing/duplicate/partial days, stock-versus-flow
aggregation, per-leaf normalization, continuity, lineage scope, missing dawn
receipts, different occupancy histories, and exact published results. The
published derivation is tested with subprocess execution forbidden. No runtime,
firmware, controller, or ecological default changes are included.
The final analysis suite passes all 136 tests in 56.03 seconds; whitespace
and local documentation links also pass.
