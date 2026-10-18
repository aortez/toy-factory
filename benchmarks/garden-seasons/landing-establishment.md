# First day resource allocation under ordinary dispersal

The saved first-day traces point toward a **water-allocation experiment**, not
more starting resources or wider dispersal. Of 43 late-born seedlings dying
from water shortage alone, 42 never extend their two starting roots. Their
growth spending goes almost entirely into shoots. This is an observed failure
pattern, not proof that forcing roots or restricting growth would rescue them.

This read-only diagnosis uses the same twelve ordinary-range worlds and frozen
neural controllers as the [recruitment trace](landing-recruitment-trace.md).
There are 127 births in (62,190] Garden days: 13 in steady climates and 114 in
seasonal climates. Every child has a full day of possible follow-up. All 55
survivors and 72 failures remain included. These retrospectively selected cases
are not 127 independent environmental replicates or a fresh evaluation panel.
No new experimental simulations or training, scoring change, firmware change
or deployment; native regression tests are separate validation runs.

## Root expansion precedes the outcome difference

At age one-eighth of a day, **all 127 seedlings are still alive**, so this
comparison does not drop early deaths or give survivors more observation time:

| Body at one-eighth day | Children | Survive their first day | Die within their first day |
|---|---:|---:|---:|
| More than the two starting roots | 55 | 47 | 8 |
| Still two roots | 72 | 8 | 64 |

Early roots are neither sufficient nor necessary: eight early expanders die,
and eight later expanders survive. By the first-day endpoint, all 55 survivors
have expanded roots; 62 of 72 failures never do. At the quarter-day landmark,
27 children have already died and are explicitly retained as not living,
rather than omitted from the comparison.

Inherited traits, sites, season, neighbors, and neural decisions can all affect
both root expansion and survival. The traces show actual root additions, not
whether a useful root destination was available or which losing bid the
controller could have selected. Successful root growth is not a free resource
or an oracle for finding wet soil.

## Water spending and acquisition

The 43 water-only deaths have **2,815 water units** available across their
observed first days: 1,032 from birth endowments and 1,783 from uptake. They
spend 2,070 on growth (73.5%) and 745 on upkeep, with no water overflow or
discarded water. The growth expense separates into:

| Observed transaction | Purchases | Water spent |
|---|---:|---:|
| Added shoot node | 410 | 2,050 |
| Added root node | 1 | 5 |
| Paid growth without a new node | 3 | 15 |

The last category includes possible tip finishing or failed extensions; the
resource trace cannot distinguish them and does not label them wasted work.
These plants still discard 9,094 energy units at death, so an energy grant
does not address their immediate terminal shortage.

In 34 of these 43 deaths, a growth purchase reduces water below one upkeep
payment for the post-growth body before the first observed water shortage.
This is only a same-step exposure: future uptake is not assumed. Five eventual
survivors also cross this threshold before a water shortage. A crossing cannot
be treated as a prediction of death or an individually proven rescue.

The surviving cohort spends much more water on growth in total (9,595 units),
but acquires 72,338 units. Its longer observation time and different bodies
preclude a simple spending-rate comparison. The question is allocation that
funds subsequent acquisition, not whether growth should stop altogether.

## Energy failures are a separate timing problem

All 22 energy-only deaths and all seven combined energy/water deaths occur
during the dark part of the daily cycle. Energy-only failures had received
4,273 energy units in total; 1,168 overflowed storage, 3,368 funded growth and
1,145 funded upkeep, together with 1,408 initial energy units. Daytime income
does not guarantee enough retained energy for the later body and night.

Only four energy-related failures cross the one-payment energy threshold
before their first energy shortage. A short water reserve and a full-night
energy forecast therefore ask different questions. Do not combine their
interventions in the next test. The reconstructed unattenuated sun is an upper
bound; it cannot identify local shade or actual seasonal leaf illumination.

## Proposed next experiment

Use **one host-only water reserve probe** on these same twelve ordinary-range
cases, with frozen weights and the unchanged rolling-renewal objective. Reuse
the existing seedling water component instead of searching for a new threshold:
at offspring ages 1..256 ecology ticks, allow a paid growth action only when
its water cost leaves four upkeep payments for its resulting shoot count.
An available root extension into a wetter cell containing at least its water
cost retains one payment instead. The wetter-cell exception is an opportunity,
not credited future water. Equality permits the purchase.

Keep the existing priority/ranking and normal winner-only memory semantics;
denied proposals become WAIT. No forced root action, added water, energy guard,
different dispersal, training or reproduction restriction. Release the guard
after the first day. This may stall a high-priority shoot without making a root
win; that possibility is a reason to test, not silently alter arbitration.

Compare unguarded/guarded worlds through day 192. Retain each climate's score
and first-day survivors, require an improvement in at least one climate's score
or qualifying renewal confirmations, and allow no earlier/new empty world.
Track water failures, root allocation, seed production and contrary cases too.
Different later lineages are not individually matched rescues. Repeat captures
and preserve every paired endpoint image as in the range screen. Freeze an exact
protocol before implementing or collecting that experiment.

This recommendation is **not implemented**. Earlier reserve successes used
different controllers and experimental ecology; they justify reusing a tested
probe, not assuming that these neural controllers will benefit. The long-term
goal remains learned resource management and sustained reproduction, not a
permanent hand-authored growth rule.

## Reproduction and evidence

[Portable results](landing-establishment-results.json.gz) retain every selected
child, growth debit, shortage event, same-age snapshot, grouped budget and
unchanged history score. The analyzer checks all 271 original children's
budgets before extracting the late cohort. Maintenance demand is independently
reconstructed from pre-growth nodes/roots and the four-step payment cadence;
stress and death receipts must agree. Post-death leaf reset is excluded from
the last-living morphology. No refund or fixed-body counterfactual is presented
as an actual simulation.

```sh
make host-audit-landing-establishment
# Choose a fresh file for each export; no overwrite is permitted.
make host-audit-landing-establishment \
  GARDEN_LANDING_ESTABLISHMENT_OUT=artifacts/my-establishment.json.gz
docker compose run --rm -T firmware python3 -W error \
  sim/garden_landing_establishment.py --verify \
  benchmarks/garden-seasons/landing-establishment-results.json.gz
```

The input archive is pinned by SHA-256
`2e4a8b9bada29ae847e0f77d22e020cab9b117765455ff6e11fbd52088b44561`.
The portable result SHA-256 is
`0c3d3fc87c0cefd3d4d756485cd3b863af50b583d7ddd1d2ddaedeaf43cd720d`.
The eight new tests cover complete recomputation, unchanged scores, contrary
outcomes, upkeep boundaries, cadence, corrupt receipts, censoring, source
preservation, input identity and no-clobber. No device performance claim.
All **146 ordinary host CTests pass** in a fresh RelWithDebInfo/UBSan build;
the log is `artifacts/garden-landing-establishment-host-tests.log`. The Make
target also regenerates the compressed evidence byte-for-byte, and a separate
verification invocation reproduces the analysis. No new wide build is needed
for this ordinary-input offline diagnosis.
