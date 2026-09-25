# Seedling budgets: startup without income, then a dawn-recovery gap

The six post-gap recruits separate into **two deaths before one day, two deaths
after about 2.6 days, and two day-64 survivors**. The early failures have no
recorded photosynthetic income. The later failures survive the guaranteed-dark
interval but die at its first dawn maintenance payment. More startup energy is
not yet justified as a general fix.

This follows the [frozen offline protocol](renewal-seedling-budget-protocol.md)
and [wet-germination A/B](renewal-wet-germination.md). No worlds were rerun and
no simulation rules, controllers or device firmware changed. The existing
[native screenshots](renewal-wet-germination.md#fixed-native-screenshots) remain
the visual context.

## Scope and accounting

All post-gap recruits are included: required-light child 10 and optional-light
children 10–14. IDs are arm-local. Their bodies, genomes, birth phases and
neighbors differ; equal IDs, columns or node counts are not matched individuals.
Each detailed history covers birth through three age-based days (11,520 ticks),
or death if earlier. Focal live steps through day 64 are also rechecked, with
later lineage/seed outcomes separate from the three-day budgets.

Energy and water telescope from the unchanged **64/24 initial allocation**:
income, capped overflow, paid maintenance, growth/FINISH, renewal and seeds.
Maintenance charges the previous body before growth. Unmet demand raises
stress but is not a cash debit. Persistent shortage flags between maintenance
ticks are not extra payments. Death clears stores and income: the **four
terminal-step budgets remain unknown**, not invented from those zeros.

## Startup: two seedlings never earn recorded income

| Recruit | First positive income, age in ecology steps | First-day result | Later result |
| --- | ---: | --- | --- |
| Required / 10 | 1 | Survives brief stress | Alive at day 64 |
| Optional / 10 | None in 174 live steps | Dies at age 0.680 days | No seeds |
| Optional / 11 | None in 157 live steps | Dies at age 0.613 days | No seeds |
| Optional / 12 | 183 | Recovers from stress 5 | Dies at age 2.578 days |
| Optional / 13 | 161 | No shortage | Dies at age 2.555 days |
| Optional / 14 | 168 | Recovers from stress 6 | Alive at day 64 |

There are 256 ecology steps per day. First-income ages exclude the birth step,
which occurs after uptake; no-income claims exclude the cleared terminal step.

- Optional 10: **64 initial + 0 income − 28 growth − 36 upkeep = 0**.
  Four seven-energy extensions leave eight nodes and five active leaves.
  Last-live water is **183**, with no water-shortage event.
- Optional 11: **64 initial + 0 income − 32 growth − 32 upkeep = 0**.
  Four extensions likewise leave eight nodes and five active leaves.
  Last-live water is **281**, with no water-shortage event.

Both survive their first globally dark interval. Child 10 has stress 3 at its
end, then no income for another 17 live steps before death. Child 11 has stress
zero and three energy there, then no income for another 41 live steps.

The no-night-growth wrapper restarts growth at phase **0**, while global light
cannot pay even one integer photosynthetic tier until phase **11**. Child 11
spends its 32 growth energy at phases **0, 3, 6 and 9**. These purchases pass
the current guard because they permit survival to phase 10, not because local
light will pay afterward.

After global light first becomes potentially productive, children 12, 13 and
14 wait another **36, 20 and 24 steps**, respectively, for actual income.
Children 12 and 14 recover from early shortages once it arrives. Early stress
therefore does not reliably identify eventual failures.

The traces establish actual income, leaf activity/condition and spending, not
which leaf is shaded by which neighbor. Global sunlight is not local leaf
productivity. Conversely, forbidding growth until positive income could prevent
a shaded seedling from growing into light; that policy has not been tested.
Observed growth expense is not automatically wasted energy.

## Larger plants: darkness survived, dawn payment failed

The two later deaths have **61 and 60 nodes**, eight-energy upkeep, and **512
water** in their last live states. Neither exceeds the full-night body cap.
Their last completed nights, alongside the survivors' third-night boundaries:

| Recruit | Dark-entry energy / nodes | Spending during darkness | Energy / stress at phase 10 | Phase-11 income | Phase-12 maintenance |
| --- | --- | --- | --- | ---: | --- |
| Optional / 12 | 251 / 61 | 8 energy, one FINISH | 0 / 7 | 2 | Eighth shortage; dies |
| Optional / 13 | 245 / 60 | None | 0 / 7 | 2 | Eighth shortage; dies |
| Required / 10 | 252 / 61 | None | 0 / 6 | 3 | Pays 7 of 8; stress reaches 7, remains alive |
| Optional / 14 | 256 / 61 | 14 energy, two actions; reaches 62 nodes | 0 / 7 | 6 | Another 6 arrives; pays 8, stress falls to 6 |

The dead plants' phase-12 income/payment is **not reconstructed**. Their native
energy-shortage flags and stress transition 7 → 8 establish the failure. The
prior live sample records two energy; do not assume another two arrived on the
terminal step.

Required child 10 tolerates one more shortage, pays at phase 16 and recovers.
Optional child 14 pays immediately and reaches stress zero at tick 91,740.
Thus similar-sized bodies need not die, and the surviving 64-node endpoint does
not justify a lower permanent size cap.

Child 13's final expense-free dark forecast matches **exactly**, including
stress 7 at the boundary, then it dies two ecology steps later. Survival until
the first *possible* income is a narrower claim than survival through dawn.

### A specific expense worth testing

Child 12 enters its last dark interval at **66,075** with 251 energy and 61
nodes. At **66,090 / phase 118** it pays **8 energy** for FINISH, leaving 243.
No other optional expense occurs that night. The guard predicts both states
alive at its boundary; the structural guard does not apply to a no-new-node
FINISH. It reaches phase 10 with stress 7, then dies at **68,340 / phase 12**.

Keeping those eight units preserves an additional paid maintenance opportunity
in the fixed-body, zero-income ledger. That is a concrete mechanism, **not a
demonstrated rescue**: deferral changes later policy opportunities and possibly
the trajectory. Retries must be handled explicitly.

Child 13 instead makes its last extension at phase 116, leaving 240 energy;
phase 117 income raises it to 245, then it spends nothing during darkness. A
child-12 FINISH deferral is not a claimed solution for this separate history or
the two startup failures.

## Complete costs and guard evidence

These ledgers end at each last live state within the fixed three-day window.
Shorter fatal lifetimes are not efficiency advantages. Each row satisfies
initial 64 + income − all listed debits = last energy.

| Recruit | Income | Overflow | Growth/FINISH | Renewal | Upkeep paid | Last energy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Required / 10 | 3,664 | 1,811 | 536 | 9 | 1,143 | 229 |
| Optional / 10 | 0 | 0 | 28 | 0 | 36 | 0 |
| Optional / 11 | 0 | 0 | 32 | 0 | 32 | 0 |
| Optional / 12 | 2,059 | 936 | 536 | 0 | 649 | 2 |
| Optional / 13 | 2,357 | 1,152 | 568 | 0 | 699 | 2 |
| Optional / 14 | 4,132 | 2,461 | 553 | 18 | 918 | 246 |

Water also reconciles step-by-step. There are no water shortages or seed
purchases in these windows. Required 10 and optional 14 each make one seed
later in the saved 64-day run; both seeds expire.

The windows contain **292 paid growth/FINISH stages, three renewals, 34 ordinary
guard refusals and 90 structural-capacity refusals**. All capacity refusals
belong to optional 14. Native refusal receipts are not charged as spending or
counted as proof of a saved life.

Of 15 dark windows, **three clean windows match exactly**, eleven have later
spending/upkeep changes that break the frozen-body assumptions, and one is
right-censored at the three-day cutoff. All 698 valid-prefix steps agree.
All four natural deaths occur after the guaranteed-dark horizon, not within it.

## Verification and reproduction

```sh
docker compose run --rm firmware python3 -W error sim/garden_renewal_seedling_budget.py \
  --output artifacts/NEW-seedling-budget.json

docker compose run --rm firmware python3 -W error sim/garden_renewal_seedling_budget.py \
  --check benchmarks/garden-longevity/renewal-seedling-budget-summary.json
```

The [portable evidence](renewal-seedling-budget-summary.json) retains all **3,187
focal steps (3,183 live, four terminal)**, resource/action ledgers, native
refusals, stress episodes, body changes, checkpoints, dark windows and day-64
outcomes. All **25,156 focal live steps through day 64** are rechecked. Analysis
repeats exactly and independently verifies under Docker/Python 3.12.

Twelve synthetic tests cover scope, day boundaries, old-body upkeep, unpaid
demand, terminal omissions, missing/duplicate steps, resource/stress corruption,
partial/censored nights, persistent flags, recovery and receipt ownership.
All **81 default / 80 experimental CTests pass**. Native sources are unchanged;
there are zero new experimental native calls or frames.

- Parent manifest:
  `645ea3d984e064d56263238955188b3efd5eee9b9bc9de5a4c96d4e8f4349cef`.
- Parent portable SHA-256:
  `50f90c2d2cdf349f0595c22c201992a056336f426de04075d3573f131a502eb1`.
- This portable SHA-256:
  `da2a89751ebc77727ec77c339149ba961ab161281f18bd2c76ea70cef40725e6`.

The export records 147 native-source and 144 analysis/protocol/build-description
fingerprints. Parent traces, models, images and accounting verify without
altering the frozen bundle.

## Next proposal — not implemented

Run one isolated host-only, retry-aware deferral of **child 12's final FINISH**
from 66,090 through its first dawn maintenance at 68,340, then release it to the
unchanged policy. Compare the exact control and follow survival and later
reproduction through day 64. Freeze scope and matching prefixes before capture.

This tests the dawn-margin mechanism before designing a general spending
policy. It does not increase free reserves or claim to repair child 13, shaded
establishment, spacing or sustainable renewal. No counterfactual was executed.
Work remains uncommitted; no training, promotion or deployment occurred.
