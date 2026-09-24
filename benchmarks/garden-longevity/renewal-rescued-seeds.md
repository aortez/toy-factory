# Rescued adults, but no open sites for their seeds

Of the **43 seeds produced by the two rescued plants, 40 expire and three
remain pending at day 64; none germinates**. All **10,171 observed mature-seed
checks** have an already-present, living neighbor within the spacing exclusion
distance. Adult survival and seed production improved for these parents, but
their observed seeds never had a spacing opportunity.

This is an offline audit of the existing
[full-night growth-guard comparison](renewal-capacity-guard.md), not a new
experiment or an independent validation panel. The
[fixed protocol](renewal-rescued-seeds-protocol.md) was
[posted before aggregation](https://github.com/aortez/toy-factory/issues/30#issuecomment-5755504086).
No native simulation, model, firmware, ecology or controller behavior changed.

## Outcomes and destinations

Control retains the ordinary dark-spending guard. Treatment also has the
full-night capacity guard. Each pair ends at tick 245,760 / day 64.

| World / parent | Arm | Seeds | Germinated | Expired | Pending | Mature snapshots |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `0d983a80`, no patches, shrub 7 | Control | 1 | 0 | 1 | 0 | 248 |
| Same parent | Capacity guard | 15 | 0 | 14 | 1 | 3,485 |
| `58e36558`, patches, ground-cover 12 | Control | 0 | 0 | 0 | 0 | 0 |
| Same parent | Capacity guard | 28 | 0 | 26 | 2 | 6,686 |

Every treatment purchase occurs after that parent's first capacity refusal.
Thus whole-lifetime and since-refusal seed exposure agree. The closing
day-48–64 window contains 5,462 mature observations, all spacing-blocked,
including exposure from a seed purchased before that window. There are 24
new target purchases during the closing window: four shrub, twenty ground-cover.

The three pending seeds are right-censored, **not counted as failed**:

| Parent | Creation tick | Landing column | Endpoint age, ecology steps | Mature observations |
| --- | ---: | ---: | ---: | ---: |
| Shrub 7 | 245,460 | 5 | 20 | 13 |
| Ground-cover 12 | 242,100 | 2 | 244 | 237 |
| Ground-cover 12 | 245,640 | 0 | 8 | 1 |

Dormancy lasts eight ecology steps. At age 256, expiry precedes the next
germination check. Each of the forty expired treatment seeds therefore has
248 mature observations: **40 × 248 + 13 + 237 + 1 = 10,171**.

### Shrub 7: its entire dispersal range is occupied

The parent is at column 0 with dispersal trait zero. The unchanged wide
dispersal rule reflects out-of-bounds placements; its possible destinations
are exactly **columns 3–9**. This is support geometry, not a probability
distribution or reconstruction of random draws.

| Actual destinations, column × seed count | Living spacing occupant | Mature observations |
| --- | --- | ---: |
| 3 × 3, 4 × 1, 5 × 4 | Founder flower 1, column 3 | 1,749 |
| 6 × 3, 7 × 2, 9 × 2 | Founder shrub 2, column 8 | 1,736 |

Both founders remain alive throughout the run. Their exclusion ranges cover
columns 1–5 and 6–10, respectively: **all seven possible destinations are
blocked**, including the unchosen column 8. Producing more seeds within this
unchanged geometry cannot bypass those occupants while they remain there.
Plant capacity is never full in these target seeds' mature snapshots. The
control's lone seed lands at column 7 and also expires beside founder 2.

### Ground-cover 12: all chosen sites are occupied too

This parent is at column 7, also with dispersal trait zero. Possible
destinations are **0–4 and 10–16**; the observed placements all satisfy that
native support. Unlike the shrub result, this audit does not establish that
every unchosen destination was unavailable throughout the run.

| Actual destinations, column × seed count | Living spacing occupant | Mature observations |
| --- | --- | ---: |
| 3 × 4, 4 × 2 | Founder flower 1, column 3 | 1,488 |
| 2 × 1 | Founder flower 1 and descendant flower 8, columns 3 and 0 | 237 |
| 0 × 1 | Descendant flower 8, column 0 | 1 |
| 10 × 1 | Descendant ground-cover 16, column 10 | 248 |
| 13 × 1, 14 × 4, 15 × 7 | Founder ground-cover 3, column 13 | 2,976 |
| 16 × 7 | Founder shrub 4, column 18 | 1,736 |

These rows partition the seed observations; two witnesses at column 2 are
not two germination opportunities. Plant 16 dies later, at tick 240,015,
but this target seed has already expired at 234,600. None of the observed
spacing vetoes depends on unreclaimed dead plants or either rescued parent
blocking its own seed. IDs are within-run identities, not matched later
newborns across arms or different worlds.

## What the blockers do and do not prove

The embedded-C contract review establishes a stronger spacing result than
the raw post-step masks alone. Decomposition/reclamation occurs before the
seed-check loop. An occupant still present afterward and **born before this
step** necessarily existed throughout that loop. At a column distance less
than three, it was a spacing veto when the mature seed was checked. The audit
excludes same-step newborns from this inference, and handles patch samples
separately from ordinary ecology steps.

All 10,171 treatment observations have such a stable witness. All witnesses
are alive; 9,922 observations include a founder. There are no observations
explained only by a later newborn, and none with an empty blocker mask. This
is a **code-order inference**, not a newly instrumented decision-stage receipt.

Other logged gates overlap:

| Post-step blocker | Shrub seeds / 3,485 | Ground-cover seeds / 6,686 | Combined / 10,171 |
| --- | ---: | ---: | ---: |
| Spacing | 3,485 | 6,686 | 10,171 |
| Insufficient light | 3,075 | 5,937 | 9,012 |
| Insufficient moisture | 1,800 | 1,819 | 3,619 |
| Eight occupied plant slots | 0 | 5,811 | 5,811 |
| Node capacity | 0 | 0 | 0 |

Of the 5,811 full-plant snapshots, **5,806 contain eight pre-existing plants**,
which proves the slot cap was full during the checks. Five include a same-step
newborn, so that stronger claim is withheld for them. All five still have an
independent stable spacing witness.

There are 265 snapshots with spacing as the only recorded blocker (166 shrub,
99 ground-cover). But later growth, light recomputation and earlier seedling
water consumption prevent interpreting post-step light/moisture as exact
decision-stage readings. Removing a neighbor also changes shade, water and
capacity. Neither these counts nor the spacing proof predicts successful
germination or subsequent survival under a changed world.

## Verification and portable evidence

- Reconstructed **all 2,060 seeds** in the four traces, not just the selected
  43: **37 germinate, 1,991 expire, 32 remain pending**. All ordered bank
  transitions, creation/expiry counters, child ancestry and per-parent totals
  reconcile. The four traces contain **500,004 mature seed snapshots**.
- Reused the existing seed-ledger implementation without altering its historic
  outputs. Seed identities/ages come from creation ticks, ordering and counters,
  not invented logged IDs. Patch samples never age a seed twice.
- Re-verified all eight parent cases and their 24 repeated native frames,
  source/build/model/artifact hashes, exact controls and accounting. Each new
  analysis runs twice and must agree; the portable export is checked separately.
- Fourteen new synthetic tests cover empty controls, expiry/censoring,
  duplicate ordering, window boundaries, dead versus same-step newborn
  occupants, overlapping masks, dispersal reflection and invalid/truncated
  evidence. The ten existing seed-ledger tests and **all 77 default host
  CTests pass** with the Docker build. Regression fixtures are separate from
  the **zero new experimental native calls** in this audit.
- The [portable JSON](renewal-rescued-seeds-summary.json) retains complete
  four-trace seed histories, lifetimes and whole/closing context, plus detailed
  per-target seed/site/window/witness evidence and source fingerprints.
  Use case-specific witness IDs; aggregate ID counters combine separate worlds
  and do not identify a shared individual. Existing
  [fixed native images](renewal-capacity-guard.md#fixed-native-screenshots) remain
  the visual context; no new frames were generated or selected.

The unchanged parent manifest is
`f8e7237a0db166e15fe802c12e78b5a0f76b539fd853888d7fbc2efdc7a33d2f`.
The new portable JSON is 3,139,706 bytes, SHA-256
`5dbf08356e6968cb33e52f835c2f775bdbc7e77b27712d13a37b79612378a913`.
The raw parent bundle remains local at
`artifacts/garden-renewal-capacity-guard-v1`; it is required for full rechecking:

```sh
docker compose run --rm firmware python3 -W error sim/garden_renewal_rescued_seeds.py \
  --check benchmarks/garden-longevity/renewal-rescued-seeds-summary.json
```

## Next proposal

Test **recruitment after a controlled opening**, starting with the simpler
unpatched shrub world. Before running anything, specify one blocking founder
and removal tick, retain an untouched control, and follow all subsequent
seed destinations, germination gates, competing parents and first-day survival.
Keep the capacity guard, model, seed lifetime and spacing/dispersal rules fixed.
This would be a host-only diagnostic disturbance, not gardener assistance
during training.

This would ask whether an available gap enables a rescued parent's descendants
to establish, and where establishment fails if not. It would not isolate
spacing from the light/water/plant-slot changes caused by removal, and it would
not qualify a natural turnover schedule or guarantee species coexistence.
Do not relax spacing, add more seeds, impose adult lifetimes, retrain, or promote
the survival guards on this evidence alone. The growth-retry and 237/240
night-entry reserve problems remain separate. Discuss the bounded gap test
before implementing it; this audit ends without a commit or push.
