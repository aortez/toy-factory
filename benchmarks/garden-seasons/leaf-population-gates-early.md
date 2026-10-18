# Early repair differences change seed bank handoffs

The contrasting repair outcomes on weather seed `9a903368` depend on which
seeds replace the first shrubs, not simply on how long the founder survives.
Light-only and condition-only each return from a seed-only interval around
day 63. Both-restored instead leaves one seed blocked beside a surviving
flower until it expires on day 66.

The successful seeds were also blocked when purchased. They germinate only
just before their own expiry. A blanket ban on buying blocked seeds would
therefore remove these successful handoffs as well as some failures.

This offline diagnosis uses the existing [four-seed panel](leaf-population-gates-panel.md)
and [late-rescue comparison](leaf-population-gates-transfer.md). It examines
the first 64 days, follows the terminal seed through day 66, and uses the
recorded day-608 histories to distinguish eventual establishment from young
survivors. There are no new simulation calls or changes to policy or ecology.

## The successful replacements arrive after their parents die

On `9a903368`, all four founders die between days 62.625 and 62.8125. Their
first child, born at day 1.90625 in column 19, dies before age 32 in every arm.
The next handoffs differ:

| Arm | Important replacement | Purchase day | Germination day | Parent death day | Time left before seed expiry |
|---|---|---:|---:|---:|---:|
| Light | Founder child 15, column 19 | 31.09375 | 63.0625 | 62.625 | 0.03125 day |
| Condition | Grandchild 16, column 15 | 31.078125 | 63.015625 | 54.875 | 0.0625 day |
| Both | Founder seed, column 6 | 34 | Never | 62.75 | Expires at day 66 |

The two successful seeds have only 8 and 16 ecology-step intervals remaining
before expiry when they germinate. Each registers exactly one successful
germination check, with no living member of its family at that check. Both
children subsequently reach age 32 and support later descendants. At day 64,
however, they are still young: neither should already be counted as established.

The unchanged arm also has one young survivor at day 64, lineage 16, but it
dies at day 78.859375 before reaching age 32. Its birth does not involve a
seed-only return because the founder was still alive. Thus the number of
living plants at day 64 alone would not distinguish this eventual failure
from the two successes.

## The combined arm runs out of useful recruitment opportunities

Both-restored produces three children. The first dies with an energy-shortage
flag at day 30.65625. The next two die with water-shortage flags at days
55.03125 and 55.46875. Its founder then dies with an energy-shortage flag at
day 62.75, leaving only the seed bought on day 34.

That seed targets column 6. Flower founder 1 occupies column 4 throughout the
run. Their distance is two columns, below the frozen minimum spacing of three.
The seed's trace confirms the resulting persistent obstruction:

- All 8,191 germination checks include the spacing blocker; 519 have no other blocker.
- After the shrub family loses its last living plant, 832 checks remain; 275
  are blocked by spacing alone.
- During days `(64,66)`, all 511 checks occur with no living shrub, and none
  is blocked by plant or node capacity. Column 7 is a fully open hypothetical
  mature-seed site on 139 of these checks, while the actual seed stays at column 6.

The open-site histogram counts checks **per column**. Columns can be open
simultaneously, so their counts cannot be added to obtain a number of unique
opportunities. Nor do later open sites prove that a parent could have selected
them at purchase, or that a relocated seed would have established.

This is not merely a missing spacing filter. The frozen placement policy
already prefers clear reachable destinations, with a daylight tie-breaker.
When none is available, it retains a fallback destination. At the combined
arm's day-34 purchase, living plants block every normal destination reachable
from its origin at column 13, for every permitted dispersal trait. This follows
from the recorded lifetimes and the frozen placement geometry; it does not
require guessing the founder's unretained trait.

Conversely, the successful light and condition seeds are also spacing-blocked
at purchase. In the light arm, a ground-cover plant at column 21 blocks the
target at 19; that plant dies at day 62.84375. In the condition arm, the shrub
founder at column 13 blocks the target at 15 until its death. These destinations
eventually become usable before the seeds expire. The failed combined seed
waits beside a flower that never dies during the recorded run.

## Repair expenditure alone does not explain the ranking

These founder budgets cover birth through each founder's death, all before
day 64. Values are in simulation resource units, and shortage counts are
steps where upkeep could not be fully paid.

| Founder measure | Unchanged | Light | Condition | Both |
|---|---:|---:|---:|---:|
| Repairs | 313 | 295 | 356 | 384 |
| Repair energy | 2817 | 2655 | 3204 | 3456 |
| Energy income | 51664 | 45984 | 49209 | 51045 |
| Energy discarded at storage cap | 32481 | 27024 | 29701 | 31283 |
| Energy-shortage steps | 13 | 17 | 15 | 12 |
| Water-shortage steps | 0 | 0 | 0 | 0 |

Both-restored spends more on repair but has fewer founder shortage steps than
either successful arm, and its founder dies at almost the same time. Light-only
has lower income and more shortage steps than unchanged while sustaining the
family. Aggregate repair spending therefore does not by itself explain which
family survives. Large overflow totals also do not rule out shortages at
particular times. These are different trajectories, not a controlled comparison
holding body geometry, neighbors, and observations fixed.

## The second seed separates founder benefit from offspring benefit

On `59818bc3`, the initial child is lineage 7, born at day 1.921875 in column
19 in every arm. Restoring light extends the founder's life but loses this
child much earlier:

| Measure | Unchanged | Light | Condition | Both |
|---|---:|---:|---:|---:|
| Founder death day | 14.765625 | 62.75 | 14.734375 | 30.796875 |
| First child death day | 318.671875 | 14.78125 | 190.796875 | 14.8125 |
| Child leaves at day 12 | 13 | 14 | 13 | 14 |
| Child energy income through day 12 | 7742 | 7110 | 7949 | 7227 |

The child's recorded bodies and resource histories differ even though the
growth controller is unchanged. The trace does not isolate whether the decisive
difference comes from its own repair choices, its changed growth, or its
neighbors. It does establish that improving the founder's survival is not
equivalent to preserving its family.

All four late-rescue reference runs reproduce the unchanged early history
and resource trace through day 64. They keep the original long-lived child 7
through the early period; applying light or both changes after day 208 then
retains shrubs through day 608. Applying those changes from day zero instead
leads to extinction in this seed. The distinction is a changed early trajectory,
not a different weather seed or objective.

## Purchase time follow up

The [purchase-time trace](leaf-population-purchases.md) now completes this
diagnostic with eight exact-parity replays. Its full roster also shows a
second, earlier-clearing blocker at the condition arm's selected column 15.

It records reachable destinations, current blockers, the selected fallback,
and occupant age and resources before the seed purchase debit. Future
lifetimes remain diagnostic labels, never policy inputs. The next proposed
comparison changes only the all-blocked placement fallback under the existing
costs and scoring rule; it does not prohibit blocked purchases.

## Reproducible evidence

The derived JSON (`leaf-population-gates-early.json`, kept locally) retains
eight from-start cases, four late references, 36 authenticated input-file
digests, individual plant resource windows, early seed fates, and overlapping
blocker histograms. Early population summaries are censored at day 64; lifetime
and establishment outcomes through day 608 are explicitly labeled separately.
Both source archives and the authenticated frozen runtime remain unchanged.

```sh
python3 -B sim/experiments/leaf_population/population_gates_early.py --check \
  benchmarks/garden-seasons/leaf-population-gates-early.json
```

The [diagnostic](../../sim/experiments/leaf_population/population_gates_early.py)
authenticates archive digests, checks model and activation identity, reconciles
the trace endpoint with full history, and verifies resource conservation and
coverage. It executes no archived source or simulator. Eight new tests cover
exact derivation, stock versus flux accounting, overlapping histogram counts,
archive rejection, near-expiry handoffs, censoring, spatial obstructions, and
the second-case comparison. All 79 analysis tests pass in 41.01 seconds.
