# Seed establishment and spatial opportunities

2026-09-11. Follow-up to the [nighttime-growth probe](night-growth.md), tracked
in [issue #30](https://github.com/aortez/toy-factory/issues/30).

## Scope and method

Keep ecology, model weights, policies and weather unchanged. Replay the same
48 worlds (8 seeds × 2 rain-fed layouts × original neural / no-night-growth
probe / adaptive) for 24 day/night cycles. Inspect every ecology step, retaining
the preselected late window of cycles 16–24.

The census follows **6629 individual seeds**, reconciling creation, germination,
expiry and pending outcomes against seed ages, new plant ancestry and counters.
All **77459 saved evaluator checkpoints** match. No device flash or training
was performed. This adds a read-only diagnostic API and host tooling, not a
different simulated environment or a relocation policy.

For all 28 columns, the query reuses production germination checks for a
hypothetical mature seed. It also enumerates each living parent's possible
dispersal columns without advancing RNG. See the
[audit workflow and limitations](../../docs/garden-establishment.md).

```sh
make host-audit-garden \
    GARDEN_AUDIT_BUNDLE=artifacts/garden-night-growth-probe \
    GARDEN_AUDIT_OUT=artifacts/garden-establishment \
    GARDEN_AUDIT_ARGS="--late-cycles 8"
```

The frozen model remains CRC32 `dc5e849d`, file SHA256
`bd9f9c6ba7f5fd17309f917972da5f759c305c077798e1d4ba9a52701e2cd48b`.
Both neural roles use identical model bytes; the existing nighttime adapter
remains the only difference between their policies. Rain-v1, startup water,
capacities, seed lifetime and reset layout are unchanged. There is no gardener.

## Seed outcomes, with explicit follow-up

This table counts seeds born **after cycle 16 and through cycle 23**, giving
each one a full seed lifetime (one cycle) of potential follow-up by cycle 24.
It includes seeds that germinated earlier, not just those observed for a full
cycle. Recent seeds are kept in a separate cohort in the artifact.

| Policy | Eligible seeds | Germinated | Expired | Of expired: any site ever open | Of expired: reachable site ever open |
|---|---:|---:|---:|---:|---:|
| Original neural | 381 | 10 | 371 | 228 | 20 |
| Neural, no night growth | 746 | 6 | 740 | 305 | 17 |
| Adaptive | 855 | 5 | 850 | 350 | 8 |

"Ever open" means at a captured point during that seed's mature lifetime.
Anywhere-open allows any soil column; reachable-open restricts it to the
parent's dispersal support at creation. These are spatial upper bounds, not
tests that actually moved seeds or demonstrated surviving offspring.

For the no-night-growth policy, 305 expired seeds had an opening somewhere,
but only 17 had one within their parent's dispersal support. Thus 288 of those
305 could not use any observed opening even with perfect selection among the
current landing choices. Conversely, 435 of 740 expired seeds never saw any
open site anywhere in the recorded mature-lifetime snapshots. Dispersal cannot
be assumed to solve all failures.

These germination counts differ from the prior late-window **plant births**
(12/8/5). That report counted any germination happening during cycles 16–24;
this table selects seeds by creation time and potential follow-up, excluding
carry-in seeds and recent seeds. The two measurements answer different questions.

## A concrete blind spot in the dispersal rule

Rainfed seed `9c530b07`, no-night-growth policy (audit case 02), settles into
five living plants at columns 4, 10, 16, 21 and 26. Open sites appear at columns
0, 1, 7 and 13 during the late bright-day window, but none are reachable under
these parents' actual dispersal rules:

| Parent column | Possible landing columns |
|---:|---|
| 4 | 9, 10, 11 |
| 10 | 3, 4, 5, 15, 16, 17 |
| 16 | 9, 10, 11, 21, 22, 23 |
| 21 | 14, 15, 16, 26, 27 |
| 26 | 19, 20, 21 |

The rule chooses distance `5 + inherited dispersal trait + {0,1,2}`, in either
direction. Out-of-bounds results reflect around the parent. With the common
zero trait, a parent at column 4 cannot land in the open columns 0 or 1: all
three attempted leftward distances leave the plot and reflect rightward.
Likewise, interior gaps can require shorter distances than the narrow range
offers. The NN's growth actions do not directly choose a seed's landing column.

At tick **68760**, case 02 has open sites:

| Column | Surface moisture | Light | Blockers |
|---:|---:|---:|---|
| 0 | 14 | 168 | None |
| 1 | 14 | 168 | None |
| 7 | 12 | 126 | None |

The Garden hash is `c99bc64e`. Its bank contains seeds at columns 23, 21, 10,
5 and 27, not these openings. This is evidence of a real spatial blind spot,
not proof that teleporting a seed to an opening would sustain its descendants.

## Other constraints remain

Among **remaining mature-seed observations during late bright daylight**:

| Blocker present | Original neural | No night growth | Adaptive |
|---|---:|---:|---:|
| Insufficient local surface moisture | 96.1% | 96.7% | 96.2% |
| Spacing | 96.5% | 97.9% | 85.4% |
| Insufficient local light | 14.6% | 56.8% | 64.4% |
| Fewer than four free nodes | 0% | 29.0% | 26.3% |
| All eight plant slots occupied | 0% | 0% | 0% |

Denominators are 27138 / 54168 / 62397 repeated seed snapshots, respectively.
Blockers overlap; percentages do not sum to 100. Bright daylight requires sun
strength >=128, above the unshaded germination threshold of 80, so these light
failures are not explained merely by night. However, seeds that successfully
germinate are removed before observation: this is a survivor-biased picture of
the remaining bank, **not independent seed failure probabilities**.

Exact single-blocker failures are uncommon. For the no-night-growth policy,
only 1.26% of these observations fail on spacing alone and 0.88% on moisture
alone. Relaxing one requirement at the same location would often still leave
another requirement unmet. Broader landing support changes which locations
are tried; it is different from bypassing those requirements.

One additional water-accounting detail deserves a separate experiment: roots
remove water from soil even if the plant's storage is full. Storage then
saturates, discarding the excess. This is current behavior in
`absorb_water_and_light`, not a newly introduced rule. In the existing detailed
rainfed `9c530b07` traces over cycles 16–24:

| Policy | Water removed by roots | Storage overflow | Maintenance / growth / seed water debits |
|---|---:|---:|---|
| No night growth | 30778 | 24231 (78.7%) | 5120 / 130 / 960 |
| Original neural | 29964 | 25188 (84.1%) | 4096 / 0 / 768 |

These totals come from the resource reconciler on the previously frozen
`garden-night-growth-probe` cases 01/02; both have zero terminal/death steps in
this window. Changes in retained stores account for the remaining balance.
This is a quantified water sink, but whether it should represent ongoing
transpiration or be capped by demand is a design choice. It is not evidence
that changing uptake alone solves establishment, and no uptake change was made.

## Evidence and checks

The ignored local audit `artifacts/garden-establishment/` is about 29 MiB. It
contains raw compressed censuses, every seed's lifetime, cohort/histogram
summaries, per-column opportunity maps, frozen executables/models/scripts,
input references and a source snapshot. Manifest SHA256:
`5518f0c9c1f1100ab6b157308f984192dc46e7dd5fe35f64eb37c5b8845f33df`.
The numeric findings above are versioned here so the evidence does not depend
solely on those local files. Use new paths when repeating a collection.

To view the example through the production renderer:

```sh
make host-gallery-garden \
    GARDEN_GALLERY_BUNDLE=artifacts/garden-night-growth-probe \
    GARDEN_GALLERY_OUT=artifacts/garden-establishment-gallery \
    GARDEN_GALLERY_ARGS="--seed 9c530b07 --include-adaptive --checkpoint 68760"
```

The API tests check byte-for-byte state preservation, real-seed versus site
blockers, dormancy, edge reflection, dead parents, node/plant capacity boundaries,
and invalid inputs. Integration tests exercise seed identity, exact outcome
reconciliation, pending/follow-up cohorts, hash mismatches, missing observations,
frozen replay and refusing overwritten outputs. All 22 host tests pass in the
strict-warning/UBSan build.
Frozen census/reanalysis verification was repeated for cases 02, 18 and 34
(all three policies on `9c530b07`). The six corresponding gallery frames match
their evaluator states and reproduce exact framebuffer bytes.

## Recommended next controlled test

First test a **broader dispersal support** on the host, with exactly the same
model, seeds, rain, lifetime, capacities, spacing and germination thresholds.
Retain the old rule as control and compare late seed cohorts and full-cycle
offspring survival, not just more germination events. Decide the revised range
and boundary behavior before implementing it.
The concrete proposal is an attempted distance of **3–9 instead of 5–7**,
keeping the midpoint at 6, the inherited trait offset, and existing reflection.
This supplies shorter/longer choices without selecting only known-good sites.

Then consider a separate uptake/demand or transpiration experiment, not a
simultaneous water/dispersal change. Neither forced deaths nor globally easier
germination is justified by this audit alone. Environment qualification and
broad training remain pending.
