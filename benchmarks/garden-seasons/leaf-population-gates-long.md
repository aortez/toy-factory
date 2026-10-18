# Restoring both repair gates enables later shrub generations

The day-608 follow-up separates surviving from reproducing. Restoring only the
light gate keeps the founder alive and eventually produces one established
direct child. Restoring both gates produces six new shrubs, including two
qualifying later-generation offspring under the unchanged renewal objective.
That stronger shrub family coincides with loss of the ground-cover family;
it is not a general improvement for every species.

All eight [planned runs](leaf-population-gates-long-protocol.md) completed in
42.569 seconds. Every earlier checkpoint and resource trace matches the
[day-256 experiment](leaf-population-gates.md) byte for byte. Logging-on/off
pairs match complete state, histories, and native pixels through day 608.

## Survival and recruitment are different outcomes

The seed remains `58d7d6ca`, with the rainfed layout and Search 1 throughout
the garden until day 208. Only shrub family 2 receives a derived repair model
after that point. Competitors, growth policy, ecological rules, and costs stay
unchanged. Each variant continues throughout the follow-up.

| Outcome through day 608 | Unchanged | Light restored | Condition restored | Both restored |
|---|---:|---:|---:|---:|
| Founder alive | No | Yes | No | Yes |
| Living shrub-family members | 0 | 2 | 0 | 6 |
| New shrubs born after day 208 | 0 | 1 | 0 | 6 |
| New shrubs reaching age 32 | 0 | 1 | 0 | 3 |
| New shrubs still too young to classify | 0 | 0 | 0 | 2 |
| Qualifying renewal children | 0 | 0 | 0 | 2 |
| Renewal score out of 12 credits | 0 | 0 | 0 | 2 |

Unchanged and condition-only families remain extinct from day 225.1875.
The two surviving founders are still alive at the endpoint; their lifetimes
are censored there. The combined arm's six new births comprise three established
offspring, one death before age 32, and two young survivors. One established
offspring later dies, leaving four new offspring alive alongside the founder
and the child already present at the switch.

Light-only produces its new child at day 558.94921875. That child reaches
age 32, but its parent is the original founder: it does not qualify as a
later-generation renewal. Simply counting births would obscure this distinction.

## A late chain of descendants

With both gates restored, new recruitment begins at day 479.125, more than
271 days after the switch. The first new child is lineage 20, descended directly
from founder 2. The successful chain then reaches four generations beyond
the founder:

`2 → 20 → 24 → 28 → 29`

| Lineage | Parent | Generation after founder | Birth day | Outcome through day 608 |
|---|---:|---:|---:|---|
| 20 | 2 | 1 | 479.125 | Established and alive |
| 24 | 20 | 2 | 527.03125 | Established; dies at 568.0625 |
| 27 | 20 | 2 | 559.109375 | Dies at 567.78125, before establishment |
| 28 | 24 | 3 | 559.81640625 | Established and alive |
| 29 | 28 | 4 | 577.0625 | Alive, but younger than 32 days |
| 30 | 20 | 2 | 591.140625 | Alive, but younger than 32 days |

Lineages 24 and 28 earn the two renewal credits. Both are children of
non-founder parents, and both parent and child survive their own first 32
days. Both births occur in the last scoring window, `(512,576]`; the other
five windows have no qualifying births. The normalized renewal score is
therefore `2/12 = 1/6`, not sustained renewal across all six windows.

The scoring interval remains `(192,576]` with follow-up through day 608.
Its first 16 days precede the intervention; neither credited shrub birth comes
from that shared prefix. The existing occupancy tie-breaker remains unchanged
and is not substituted for renewal. The old child, lineage 14, survives in
the combined arm but is not the parent of this new chain.

## Competition changes which families persist

At day 608 the living flower/shrub/ground-cover counts are:

| Arm | Flowers | Shrubs | Ground cover |
|---|---:|---:|---:|
| Unchanged | 4 | 0 | 4 |
| Light restored | 2 | 2 | 4 |
| Condition restored | 3 | 0 | 5 |
| Both restored | 2 | 6 | 0 |

Every endpoint still contains eight living plants. Light-only retains all
three founder families; both-restored gives the shrub family stronger renewal
but loses ground cover. In that arm, the last ground-cover plant dies at day
526.703125 with an energy-shortage flag. Its final seed expires at day
545.03125, completing extinction.

The first new shrub appears shortly after ground-cover deaths near day 479.
This timing is consistent with new recruitment opportunities as competitors
die. The retained history establishes that sequence, but does not identify the
exact late-stage germination blockers or isolate shading from other feedback:
detailed resource and seed-blocker logging deliberately ends at day 256.

## What this establishes and what comes next

In this known failure case, fixing repair gates can improve survival and also
enable later generations without changing growth, weather, seed lifetime,
spacing, or the training objective. Condition-only failed, yet adding it to
light restoration changes the longer trajectory substantially. The short
survival endpoint did not capture that distinction.

This remains one selected weather seed and one family intervention, not a
generalization result. An offline check of the authenticated original population
evidence (`leaf-population-results.json.gz`, kept locally) identifies which
existing seeds could receive the same scheduled intervention:

| Rainfed weather seed | Living shrub lineages at day 208 | Pending shrub seeds |
|---|---|---:|
| `58d7d6ca` | 2 and 14 | 2 |
| `9a903368` | None | 0 |
| `6b9c1a3e` | None | 0 |
| `59818bc3` | 7 and 18 | 0 |

The next useful comparison is the same four arms on `59818bc3`, retaining
family renewal and competitor extinctions as separate outcomes. Its original
founder is already dead, so the intervention would act on descendants.
Applying a day-208 change to the two already-extinct families cannot test
whether a repair change would have rescued them earlier. Those cases require
a separately specified earlier-start experiment. No new simulations were
needed for this eligibility check. Do not promote either variant or alter the
objective on the strength of this one case.

The subsequent [second-seed comparison](leaf-population-gates-transfer.md)
now reports that repeat. This archive remains the original first-seed evidence.

## Evidence and verification

The 619 KiB archive (`leaf-population-gates-long-results.json.gz`, kept locally)
retains eight process receipts, 88 state/pixel captures, four resource traces
through day 256, source and protocol snapshots, derived models, binary digest,
and preflight results. There were no failed collection calls or retries. The
earlier archive is retained unchanged.

The original short gate command still stops at day 256. The new `--gate-long`
command explicitly extends at that checkpoint, freezes its bounded trace,
and stops at day 608. No canonical state or model bytes change at extension.
Complete ancestry and seed outcomes continue to be recorded. Tests cover
boundary rejection, repeated extension, failure latching, reset, frozen trace,
allocation bounds, output preservation, and age-32 censoring.

All seven replay/viewer preflight suites passed in 100.49 seconds, along with
ten preparation tests, using strict compiler warnings and UBSan. Published
evidence tests additionally check offline archive round-trip, tamper rejection,
outcome accounting, the unchanged arm against the original population
archive at day 608, and day-208 intervention eligibility in that archive.
All 57 population analysis tests pass. Archive verification never executes
archived source.

```sh
python3 -B sim/experiments/leaf_population/population_gates_long.py unpack \
  benchmarks/garden-seasons/leaf-population-gates-long-results.json.gz \
  artifacts/garden-population-gates-long-review-v1
python3 -B sim/experiments/leaf_population/population_gates_long.py verify \
  artifacts/garden-population-gates-long-review-v1
```

Use a fresh directory. Archive SHA256:
`d4be171527f53f92f5efff8cf2948227eb1910c2848c71670b60ec5dba0e639a`.

The work remains host-only. Firmware and original policies are unchanged.
