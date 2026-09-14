# Seedling water: shoot spending before root access

The approved read-only follow-up to [seed reserve](seed-reserve.md) finds a
recurring establishment failure: seedlings spend their water on shoots before
extending roots beyond their shared surface cell. **41 of 44 first-day deaths
involving water shortage have no root extension.** This includes all seven
remaining water deaths in the targeted sixteen-bank reserve run and the large
b61837dc baseline-policy regressions. It is not evidence that all water deaths
have the same cause, or that more rain is the right fix.

No ecology, policy, model, firmware or training changed. This audit reads saved
native traces; it does not simulate alternative outcomes.

## The targeted seven

`c7f54e18.reserve.16.on`, offspring born during days (160,192]. All seven are
shrubs. Their two starter roots remain in **one surface soil cell** throughout
life. They collect some water initially, but make only shoot extensions and no
root extension, tip finish, leaf renewal or seed purchase. None experiences rain
between birth and its last live sample. These are observed dry intervals, not
an assertion that the weather never rains.

Water accounting through the last live sample, excluding cleared terminal steps:

| Lineage | Death age (days) | Initial water | Absorbed | Shoot spending | Paid upkeep | Final live water | Final live energy |
|---|---:|---:|---:|---:|---:|---:|---:|
| 65 | 0.2070 | 24 | 17 | 35 | 6 | 0 | 256 |
| 68 | 0.2617 | 24 | 29 | 40 | 13 | 0 | 210 |
| 69 | 0.2383 | 24 | 14 | 30 | 8 | 0 | 139 |
| 75 | 0.2578 | 24 | 34 | 45 | 13 | 0 | 252 |
| 76 | 0.2188 | 24 | 30 | 45 | 9 | 0 | 256 |
| 77 | 0.2227 | 24 | 26 | 40 | 10 | 0 | 254 |
| 79 | 0.2578 | 24 | 37 | 50 | 11 | 0 | 53 |

For example, lineage 75 balances exactly: **24 + 34 − 45 − 13 = 0**. It commits
nine shoot extensions, never a root, and still has 252 energy just before death.
Its post-germination surface cell initially holds ten water, then is empty in
64 of its 66 live snapshots. A zero post-step cell does not mean uptake was zero;
the recorded income accounts for absorbed water separately.

In the same run, all **eight first-day survivors** extend into the next soil row
24–36 ecology steps after birth (0.094–0.141 days). They have already made 7–9
shoot extensions by their first root investment, but still have 8–60 water
immediately before buying it. None falls below the water price for growth during
its observed first day. Their first-day water income is 495–842, compared with
14–37 over the shorter lives of the seven failures; unequal observation lengths
mean these totals are not comparable uptake rates.

Birth moisture alone is not a viability test: survivor 78 starts with zero
post-germination water in its root cell, subsequently receives rain and grows
deeper roots. Failed seedlings start with 2–10. Survivor 71 starts with 15.
Genomes, birth timing, light, neighbors and subsequent weather differ; these
are descriptive comparisons, not matched-plant interventions.

The eighth natural death, lineage 66, remains an **energy** failure. It finishes
its last live step with 34 water. A water intervention would not directly fix
that separate underfunded-night problem.

## What the native rules actually do

The embedded-C conventions skill guided a read-only review of resource/state
ordering in `garden_world.c`; no C/header edits were made in this follow-up.

- Germination requires at least 12 water in the surface cell and debits those
  12 units. The offspring starts with 24 stored water. This checks present
  conditions, not whether water will remain accessible until the next rain.
- Both starter roots end in the same 8×8 soil cell. They can each absorb water,
  but they draw from one reservoir, not two independent reservoirs.
- Roots have no maturation gate on uptake. Newborns miss their birth-step uptake
  because germination runs later, not because roots are too immature to drink.
- Growth can run on the birth step. A shrub extension costs five water, whether
  root or shoot. The ordinary affordability gate stops asking for growth
  decisions when stored water is below that price. Root investment must occur
  before that point, or await sufficient new uptake.
- Upkeep drains existing stores and increments stress if payment fails. Death
  clears both stores **and** income telemetry, so terminal zeros are not a
  reconstructed debit or proof of energy starvation.
- Water transport moves downward and diffuses sideways. Water somewhere else
  in the soil does not automatically become accessible to a surface-only root.

This is consistent with the [earlier surface-water trap](resources.md), where
actual root bids lost to shoots despite wet available candidates. A targeted
root-first override helped that old watered case. We have **not** yet inspected
the losing bids or tested that override in these rainfed maintenance worlds;
the old result is supporting context, not a new causal result here.

## Entire closing birth cohort, including adverse pairs

199 offspring across all sixteen saved worlds, followed from birth through the
first day, earlier death or horizon: 130 survive beyond one day, 43 die from
water alone, one from both shortages, 21 from energy alone, two from fixed
patches and two remain horizon-censored. A death exactly at age one day is not
a survivor. Pairs with identical histories are still shown, not independent
replications; this is a repeatedly inspected exploratory panel.

Here “water death” includes the one mixed-shortage death. Arrows mean seed gate
off → on, not eight → sixteen seeds. Counts are not exposure-adjusted hazards.

| World / growth / bank | Births | First-day water deaths | Water deaths with no root extension | Survive beyond one day |
|---|---:|---:|---:|---:|
| b61837dc / baseline / 8 | 17 → 22 | 1 → 8 | 1 → 8 | 13 → 6 |
| b61837dc / baseline / 16 | 8 → 16 | 0 → 8 | 0 → 8 | 4 → 8 |
| b61837dc / reserve / 8 | 11 → 12 | 3 → 4 | 2 → 3 | 5 → 6 |
| b61837dc / reserve / 16 | 7 → 13 | 1 → 4 | 1 → 3 | 6 → 9 |
| c7f54e18 / baseline / 8 | 3 → 7 | 0 → 0 | 0 → 0 | 3 → 6 |
| c7f54e18 / baseline / 16 | 5 → 6 | 0 → 0 | 0 → 0 | 4 → 5 |
| c7f54e18 / reserve / 8 | 9 → 9 | 2 → 2 | 2 → 2 | 7 → 7 |
| c7f54e18 / reserve / 16 | 38 → 16 | 4 → 7 | 4 → 7 | 33 → 8 |

One offspring in each b61837dc/reserve/8 arm is horizon-censored; its fate is
not assumed. The two first-day patch deaths occur in b61837dc/reserve/8/off
and c7f54e18/reserve/16/off. The export keeps every lineage and resource budget.

Three counterexamples grow roots and still die thirsty:

- b61837dc/reserve/8/off lineage 68: two root extensions, death at 0.254 days.
- b61837dc/reserve/8/on lineage 67: five root extensions, death at 0.332 days.
- b61837dc/reserve/16/on lineage 70: three root extensions, death at 0.301 days.

They end with roots in deeper but dry cells. Conversely, five of the 130
one-day survivors never extend a root in that day. “Has a deeper root” is neither
necessary nor sufficient for survival under all conditions. Six closing adult
water deaths are retained separately, not attributed to seedling establishment.

No overlap with an earlier **post-step living** plant's roots is observed for
any of the 44 water-failing seedlings. This is only a snapshot proxy: it excludes
plants that died during the step and includes roots added after uptake. It
cannot measure uptake-order competition, prior depletion or competition through
neighboring cells. Likewise, post-step moisture is not a map of pre-uptake or
pre-decision water availability. Do not claim other plants stole no water.

## Next experiment to discuss

Test **early productive root investment**, keeping rain, storage and resource
prices fixed. First replay representative failing and successful cases with
the existing bid/candidate telemetry, verifying unchanged world hashes. Confirm
whether affordable roots can actually reach wetter cells and whether they lose
to shoots, wait, are energy-vetoed or are geometrically blocked.

Then predeclare one bounded host-only policy probe that favors an affordable
root extension into wetter soil before shoot spending exhausts the reserve.
Retain successful cases, the three rooted failures and both adverse bank pairs;
check nighttime energy and longer offspring survival, not just fewer immediate
water deaths. The existing lineage override intentionally rejects recurring
patch combinations, so supporting such a probe needs an explicit tested change,
not silently mixing unsupported flags. No new policy or probe is implemented here.

The eventual learning objective is to discover useful resource allocation, not
to permanently hand-code a gardener. If a bounded probe works, it establishes a
learnable opportunity under these mechanics; it is not automatically the policy
we should ship or train against.

## Reproduce, inspect and verify

```sh
python3 sim/garden_seedling_water.py --output artifacts/garden-seedling-water-new
python3 benchmarks/garden-longevity/review-seedling-water.py
# Optional: recompute every first-day ledger/history from the original traces.
python3 benchmarks/garden-longevity/review-seedling-water.py --reanalyze
```

The default input is the complete `artifacts/garden-seed-reserve-v3` bundle.
Fresh outputs refuse overwrite and cannot be placed inside that frozen input.
The audit checks all 786,448 ecology rows for cadence/identity and reconciles
**39,658 first-day live budgets**. It preserves fixed-patch boundaries, censoring,
terminal clearing, exact action deltas and actual deeper-root geometry separately
from charged extension attempts. Full-world budgets were checked by the earlier
seed-reserve audit; this follow-up does not claim to rerun all of those ledgers.

All **36 default host CTests pass**, including six new offline unit cases.
Cases exercise aliased root cells, uptake-order snapshot selection, newborn
ordering, stale last-action telemetry, charged failed extensions, water gating,
terminal clearing, corrupted/truncated traces, age-boundary survival, patch
follow-up and censoring. The reviewer verified all 35 output artifacts and 48
frozen inputs; no native simulation, new render or device experiment was needed.
The optional full reanalysis command is provided, not claimed as a second run.

- Result bundle: `artifacts/garden-seedling-water`.
- Result manifest SHA-256: `7f6912ebcd219803dad246ba42ea78567d50674cc4e66b5970f2d07e957d67ee`.
- Input manifest SHA-256: `a4696431b029146d12f241161a7eb53a36b85d71a2efb1351df63ba30a429654`.
- 375 source fingerprints and source archive; all native C/header hashes match
  the prior experiment. Docs/review/export were added after that snapshot.
- [Compact per-seedling export](seedling-water-summary.json); full plant snapshots
  and per-step histories remain in the local bundle.

Default ecology, the device's eight-seed configuration and frozen model remain
unchanged. No commit, push, training or firmware deployment accompanies this audit.
