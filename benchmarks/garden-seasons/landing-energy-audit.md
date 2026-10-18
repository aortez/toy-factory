# Maintenance increases: forecast error and the cost of caution

The saved histories support testing a **more cautious afternoon maintenance
increase**, not removing all future-income credit. Two failed seedlings really
do overestimate income after buying their ninth node. But six successful morning
maintenance increases also depend on future income: a stores-only rule would
reject all six at their observed decision states.

This is an offline audit of the [root-energy comparison](landing-root-energy.md),
not a new policy test. No simulations, training, screenshots, firmware changes
or default changes were made. The [protocol](landing-energy-audit-protocol.md)
was written before extracting the audit, with the previous experiment's two
known failures already disclosed. The selected cases are diagnostic evidence,
not an independent validation panel or an estimate of general success rates.

## Scope and counting

All five cases and both arms are retained. The control already buys one early
root; the candidate makes the same purchase and adds the existing first-day
energy eligibility test. Decisions are selected from `birth <= tick < birth+3840`;
saved second-day follow-up supplies later sunset/dawn endpoints when needed.
The energy guard turns off at age 257, so the audit does not silently extend it.

The two successful fixed-order cases have identical captured focal histories in
both arms once observational energy-gate annotations are removed. They are
retained in the results but counted once in the deduplicated columns below.
Different histories still share worlds and prefixes; they are not independent
replicates.

| Saved observations | All arm histories | Deduplicated histories |
| --- | ---: | ---: |
| Focal histories | 10 | 8 |
| Executed paid daylight actions | 194 | 134 |
| Maintenance increases | 21 | 15 |
| Otherwise budget/water-eligible increase opportunities | 175 | 169 |
| Opportunities rejected by an active energy guard | 154 | 154 |

The fifteen deduplicated increases comprise eight 8→9, four 16→17 and three
24→25 transitions. An opportunity is one ecology decision, not one tip bid.
The 154 refusals include 38 before noon, 24 from noon to sunset and 92 at night;
these are repeated decisions in the same histories, not 154 saved seedlings.
All fifteen increase events reach the next sunset in the saved data; nine reach
the following dawn and six die beforehand. The checker also handles missing
follow-up as censored and death on the endpoint as death.

## The two clean forecast failures

Maintenance rounds up in blocks of eight nodes. A ninth node doubles each
maintenance payment from one energy to two, and the nominal night requirement
from 32 to 64. The existing forecast credits half the current income multiplied
by remaining daylight steps (excluding the already received current step and
sunset). It is a fixed-body estimate; it does not model future growth choices.

| Candidate case | Purchase phase | Energy after purchase | Forecast future income | Actual future income | Daylight upkeep | Predicted sunset | Actual sunset | Night requirement |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Rotating 49 | 94 | 35 | 49 | 26 | 18 | 66 | 43 | 64 |
| Rotating 50 | 110 | 49 | 25 | 6 | 10 | 64 | 45 | 64 |

Noon is phase 64 and sunset is phase 128. Neither plant pays for further growth
or reproduction before sunset; neither overflows storage or misses a daylight
energy maintenance payment in that interval. Thus their 23- and 19-energy
prediction errors are entirely income overestimates, not later spending.
Both forecasts permit the purchase; both plants subsequently die before dawn.

The accounting is exact:

```
case 49: 35 + 26 - 18 = 43 at sunset, versus 64 required
case 50: 49 +  6 - 10 = 45 at sunset, versus 64 required
```

This audit isolates the error in total future income. It does not isolate how
much came from declining sunlight, changing shade or per-leaf integer income.
Those processes exist in the source, but the saved aggregate receipts do not
separate them. Nor does refusing these purchases prove that either plant would
survive: changed actions can alter subsequent growth, memory and competition.

## Why not eliminate future-income credit?

For each observed increase, the audit also computes a same-state stores-only
margin: post-purchase energy minus fixed-body maintenance through sunset and
the following night. Negative means existing stores cannot fund the purchase
and that interval without any future income. This is an arithmetic comparison,
not an executed alternative policy.

| Deduplicated increase events | Before noon | Noon/afternoon |
| --- | ---: | ---: |
| Executed increases | 6 | 9 |
| In histories that establish for a full first day | 6 | 3 |
| Those successful events rejected by stores-only arithmetic | 6 | 0 |
| Actual next dawn reached | 6 | 3 |

All six successful morning increases have negative stores-only margins:
fixed 45 at nine nodes (−42); fixed 46 at nine, seventeen and twenty-five
(−81, −106, −10); rescued rotating 48 at nine and seventeen (−88, −77).
The three successful afternoon increases are already funded from stored energy:
fixed 45 at seventeen/twenty-five (+50/+73) and rotating 48 at twenty-five (+31).

The morning histories demonstrate why a conservative forecast is not the same
thing as refusing every purchase that needs future sunlight. They do not prove
that an alternative controller could not wait and grow later. Conversely, the
three funded afternoon observations do not establish that a stricter afternoon
rule is harmless outside this selected panel.
One successful increase is at phase 63, just one ecology step before noon;
future qualification must check boundary-related growth delays as well.

## Separate forecasting from later behavior

Every paid event carries a reconciled sunset budget and, when available, the
next night's observed transfers. The error decomposition is:

```
predicted sunset - actual sunset
  = predicted income - actual income
  + actual paid upkeep - predicted fixed-body upkeep
  + later growth + reproduction + overflow + death discard
  - forecast energy-cap adjustment
```

For example, successful fixed 45's ninth-node forecast is 256 and actual sunset
energy is 243. Calling that a thirteen-unit income overestimate would be wrong:
the income term is −374, while later maintenance adds 26, later growth costs 200,
overflow removes 189 and the forecast cap subtracts 28. These sum to +13.
The plant then reaches dawn with 115 energy.

After later growth, nominal night cost at the earlier decision need not equal
the actual body's later night cost. Likewise, a negative maintenance-error term
can mean maintenance went unpaid, not that the plant became cheaper. The report
retains shortage ticks and actual night outcomes rather than treating a predicted
reserve or sunset balance as a survival guarantee. A `clean_interval` has no
later paid growth, reproduction, overflow, discard or energy shortage before an
observed living sunset; only the two candidate failures meet that definition
among the maintenance increases.

## Proposed comparison after this audit

Keep the existing first-day energy guard as control. Test one additional
eligibility condition only when a paid allocation would increase maintenance
**at/after noon**: require current post-purchase stores to cover remaining
daylight and night upkeep, without speculative future-income credit. Keep
morning decisions, within-band growth, priorities, destinations, ordinary
prices, memory commits and the first-day scope unchanged.

The rationale is to avoid doubling an ongoing cost late in the day against
income that has not arrived. Noon is the existing clock boundary, not a fitted
cutoff chosen between the two failed purchases. This is still a hypothesis
informed by these outcomes; use the same five cases as diagnostic/harm checks,
with exact repeats and follow-through to day 256. Inspect both focal outcomes
and effects on other plants, seed production and recruitment. Preserve failures
instead of adjusting the cutoff or margin during the comparison. Broader/fresh
validation would be required before promotion.

In the recorded states this condition refuses both clean failures and permits
all three successful afternoon increases. That describes the existing decisions,
not predicted counterfactual trajectories. It must still earn its keep in replays.
The previously rescued plant has produced no seeds: autonomous renewal remains
the larger unsolved goal.

Follow-up: this proposal has since been tested in the
[afternoon maintenance comparison](landing-afternoon.md). The audit's observations
and pinned results above remain unchanged.

## Reproduce and verify

`make host-audit-landing-energy` runs only Python against the pinned portable
input; it does not build or run a simulator. Set a fresh
`GARDEN_LANDING_ENERGY_AUDIT_OUT=artifacts/new-energy-audit` for another export.

```sh
docker compose run --rm -T firmware python3 sim/garden_landing_energy_audit.py \
  --verify benchmarks/garden-seasons/landing-energy-audit-results.json.gz
docker compose run --rm -T firmware python3 -W error sim/test_garden_landing_energy_audit.py
```

The [portable results](landing-energy-audit-results.json.gz) retain every selected
paid event, threshold opportunity, duplicate identity, summary and provenance
hash. Verification recomputes the full analysis from the pinned input, rather
than checking only these headline numbers. Bundle verification additionally
checks all three artifact hashes and the archived source files against their
recorded hashes. Exports refuse existing destinations and source-tree output.

Input SHA-256:
`dca98970b1efbd6552df4796c280fcb0883bc959f226d569531353a760abe778`.
The output includes its protocol hash and an exact source snapshot; it neither
rewrites the prior capture nor runs a simulator to fill gaps.

Portable results SHA-256:
`7943e9edb3b2e4c1f8f30925d46bbce1a7d5a5ca8ed7f70ee228f2694fd4e14b`.
Protocol SHA-256:
`a2789c4ceb948b6547fe45f3d211edcdc6c0bd982d74f4746e4a92d84f4696a5`.
Raw bundle: `artifacts/garden-landing-energy-audit-v1`, manifest SHA-256
`65b489ac5b0b36313637d914e43895314c2c801a3d54a4f03ebb7cfbb3f22de7`.
A second export before any source edits produced byte-identical portable results
in `artifacts/garden-landing-energy-audit-v1-repeat`.

Validation: all sixteen focused Python tests pass with warnings treated as errors,
including the registered `garden-landing-energy-audit` CTest. Coverage includes
selection/ties, per-decision opportunities, duplicate accounting, income/spending/
overflow decomposition, same-tick reproduction, death/censor endpoints, no-clobber
exports, source archives and corrupt portable evidence. Raw-bundle and portable
verification both pass. The full native suite was not rerun for this offline-only
step; no C source or controller changed.
