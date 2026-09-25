# Phase-aware forecast: better sunsets, not yet a survival policy

The fixed phase-aware predictor reduces sunset-energy error, and reproduces the
two previously diagnosed late-purchase deaths. It is **not ready to govern
reproduction**: later optional spending breaks its assumptions in 103 of 112
purchase windows, and even unchanged-body/no-spending prefixes can have large
morning income errors. No runtime rule was changed.

[Fixed protocol](renewal-phase-forecast-protocol.md) ·
[Every purchase and verified metrics](renewal-phase-forecast-summary.json) ·
[Previous forecast audit](renewal-seed-forecast.md)

## Predictor and coverage

Use the same two eight-day control/veto traces, with **52 / 60 purchases**.
They share eight pre-intervention purchase records. Repeated parents, overlapping
horizons and the common world/prefix mean these are not 112 independent trials.
All outcomes are reused, not fresh held-out validation.

The sole candidate was specified before evaluation. At purchase time it scales
current income by the future/current **integer unshaded light tier**:

```text
Q(phase) = floor(sun_strength(phase) / 64)
predicted_income = floor(current_income * Q(future_phase) / Q(current_phase))
```

Sun strength follows the existing C formula exactly, checked against every saved
census. There is no fitted safety factor, history window or future trace input.
The body remains fixed; no further optional spending is assumed. Energy is capped
before maintenance. The forecast continues through the next dawn to the following
noon, tracking unpaid upkeep, stress recovery and an absorbing predicted death
at stress eight. Stress is **energy-only, conditional on adequate water**.

Two phase-120 purchases have zero current light tier, making that normalization
undefined. They remain in the report as **unsupported**, not guessed zero-income
forecasts. Thus 110 purchases have projections. Nine purchase windows end before
the next-noon horizon and remain explicitly right-censored, not survivors.

## Sunset estimates improve in both traces

Errors below compare the two estimates at the **same living sunset checkpoints**.
Two unsupported anchors and nine sunsets beyond the saved trace are excluded
from this paired comparison, but retained in the purchase records.

| Paired sunset cohort | Count | Existing estimate mean absolute error | Phase-aware mean absolute error |
|---|---:|---:|---:|
| All available, control | 46 | 37.02 | 24.54 |
| All available, veto | 55 | 21.67 | 8.16 |
| All available, combined | 101 | 28.66 | 15.62 |
| Assumptions still hold at sunset, combined | 27 | 16.70 | 3.30 |

For the 27 assumption-valid sunsets, worst error falls from **37 to 14**. For all
101, worst error is still **81** (previously 89). Every sunset error in this
panel is nonnegative: both estimates are optimistic, not conservative bounds.
The combined improvement is descriptive, not an independent-sample significance
claim or qualification of the two-world garden environment.

At the two earlier tick-4,620 purchases:

| Case | Existing sunset estimate | Phase-aware | Actual | Predicted / actual death tick |
|---|---:|---:|---:|---|
| Control shrub 2 | 224 | 188 | 187 | 6,840 / 6,840 |
| Veto-case ground-cover 3 | 209 | 183 | 183 | 6,600 / 6,600 |

Those are useful checks, but already known failure examples, not novel validation.

## Later spending makes long-range survival predictions unreliable

Across all 112 actual purchase-follow-up windows:

- **103** contain later optional spending: another seed, growth/finishing or renewal.
- **27** have body/active-leaf changes; these overlap the spending group.
- **Zero** have an observed water shortage in their recorded follow-up.
- There are **22 death-labelled purchase windows**, representing **six
  case-specific parent-death events**, not 22 distinct deaths.

Among supported projections with known outcomes, the predictor catches **two
death windows**, misses **18**, and predicts survival in **81** windows where the
parent does survive to the horizon. It predicts no false deaths in this sample.
All 18 missed death windows have a recorded assumption break before death; that
does **not** prove later spending alone accounts for every prediction error.

Restricting to fully observed, assumption-valid supported outcomes leaves only
the **two known deaths and no surviving control windows**. Five further supported,
unbroken windows are right-censored. This subset cannot establish a reliable
survival classifier. In particular, a forecast made at one seed purchase cannot
be treated as permission for subsequent expenses.

## Global sunlight does not predict plant-specific morning income well enough

The auditor also scores the prefix strictly **before** each first spending,
body-change or water-shortage break. Across 6,549 overlapping live prefix samples,
mean absolute energy error is about **6.92**, but the worst overestimate is **148**.
Each record includes the exact worst sample, so an average cannot hide this tail.

For example, `veto.1.26580` has no recorded assumption break until a renewal at
30,705. At **30,315**, still before that renewal and with unchanged body counts,
the predictor says **256 energy** and the actual parent has **108**. Its sunset
and dawn errors were only four. Another example, `veto.7.27060`, reaches a
114-energy overestimate before its next purchase.

Thus the known zero-light cutoff is useful, but a single income-to-global-light
ratio does not follow the next morning's effective light capture. The parent's
body counts can stay fixed while its neighbors and illumination change. Moving
shade, ray angle and leaf condition are not modeled here; their individual causal
contributions have not been isolated. No coefficient was adjusted after observing
these errors.

## The two unsupported anchors are important, not disposable

Both occur after usable sunlight has already disappeared, while the reproduction
eligibility check still considers it daylight:

| Purchase | Post-purchase energy / upkeep | Actual death | Earliest possible next light income |
|---|---|---:|---:|
| Control ground-cover 3, tick 12,360 | 200 / 8 | 14,340 | 14,565 |
| Control ground-cover 8, tick 23,880 | 201 / 7 | 26,040 | 26,085 |

Neither has later optional spending, body changes or water shortage before death.
The existing reserve gate rejects both at these observed states. The new ratio
predictor abstains because it cannot normalize a zero-light observation. A
separate **guaranteed-zero-income interval calculation** would not need that
normalization; no such fallback was added during this fixed test.

These remain observational follow-ups, not demonstrations that a gate-enabled
rollout would reach the same states or that a veto would improve the whole world.

## Verification and reproduction

Added `sim/garden_renewal_phase_forecast.py`, its tests and CTest registration.
The embedded-C review conventions guided explicit step ordering, resource-cap
handling, terminal censoring and recovery checks; no C source or header changed.
The auditor:

- Verifies all 112 purchase debits/cooldowns/flowers/seed appends, and all census
  sun strengths. Reconciles 24,242 actual live-step budgets and stress transitions
  **across overlapping windows**, not that many unique ecology steps.
- Preserves terminal death time/cause without inventing cleared income or debits.
  Predicted death is absorbing; diagnostic potential income is not credited later.
- Pins the prior audit and full frozen bundle; checks native/reference source
  identity, exact repeated analysis and the portable export. No old forecast or
  saved trace was modified.
- Passes **53 focused Python tests**, including 21 new phase/wrapping, cap/order,
  no-future-input, recovery, unsupported-anchor, assumption-break and censoring
  tests. Full offline verification also passes with subprocess execution disabled.
- Performs **zero new native simulation/replay calls**, training runs, mutations
  or deployments. No native build/test execution is newly claimed. Whitespace
  checks pass; work remains uncommitted and unpushed.

```sh
python3 -W error sim/garden_renewal_phase_forecast.py \
  --check benchmarks/garden-longevity/renewal-phase-forecast-summary.json
PYTHONPATH=sim python3 -W error -m unittest \
  test_garden_renewal_phase_forecast test_garden_renewal_seed_forecast \
  test_garden_seed_reserve test_garden_renewal_startup
```

`--output NEW.json` exports without overwriting an existing file or writing inside
the frozen bundle. Its original manifest remains
`dd44e765e15d4be5ed0c5c99273699718358ac8e5790af838162121620bcb5ae`.
The previous portable audit is pinned by SHA-256
`0a239e0921521c06bbb71c4b60fb73f8baab55402630bf1b36d462e20fa623fa`.

## Next proposal

First test an **exact guaranteed-dark-interval budget check** offline. It should
handle zero-light anchors without guessing morning income, distinguish tolerable
stress from death before productive light can possibly return, and retain
body/water/spending assumptions. Audit it across the saved spending decisions,
not just the two unsupported purchases.

Keep the full morning ratio predictor as a diagnostic, not a safety gate. Any
future spending guard needs to be reconsidered at each relevant expense;
improving the distant sunset estimate does not reserve money against later
spending. A richer shade-aware predictor, a risk threshold or a live gate test
is a separate proposal—not silently part of this investigation.
