# Dark budgets are exact within their scope; growth also spends survival reserves

The guaranteed-zero-income calculation matches every assumption-valid saved
energy/stress sample exactly. It distinguishes fatal exhaustion from shortages
that leave a plant alive when light could return. Nine accepted expense records
turn the local no-further-spending budget from alive to dead: **seven growth
actions and two seed purchases**. This is not solely a reproduction problem.
No runtime rule, native simulation, training or firmware was changed.

[Fixed protocol](renewal-dark-budget-protocol.md) ·
[Portable records and metrics](renewal-dark-budget-summary.json) ·
[Previous phase forecast](renewal-phase-forecast.md)

## What the check does—and does not know

The existing light quantization guarantees **zero energy income** while global
sun strength is below 64. Start after current-step uptake/maintenance, project
fixed-body upkeep and existing stress through those steps, and stop **before**
light could next pay anything. No forecast of morning shade, leaf condition or
income is required. The longest interval follows phase 117, covers phases
118..255,0..10, and contains 37 maintenance payments. At phase 116 the next step
can still earn energy: that anchor is explicitly out of scope.

Full payments decrease stress; an unpaid amount increases it; eight is fatal.
Exactly zero energy after a full payment is not a shortage. Later growth, renewal
or seed expenses are not silently assumed funded. Future water must suffice;
water shortage invalidates the energy-only prediction. Living through the dark
interval is **not a guarantee of recovery after it**.

Native expense ordering is retained: growth **or** renewal, then reproduction.
The audit reconstructs pre/post stores for each expense and uses the candidate's
new body for future upkeep. Current maintenance already charged the old body.
FINISH can cost energy without adding a node. Intermediate expense projections
are kept separate from observed end-of-step trajectories.

## Coverage and exact agreement

The complete inventory has **1,532 expenses in 1,525 spending steps**: 1,250
growth/finish, 170 renewals and 112 seeds. It includes 23 newborn spending steps
and seven steps with two expenses. Only 170 spending steps have an immediately
following zero-income interval; the other 1,355 remain in the report as
out-of-scope, not approved. The covered expenses are 168 growth and two seeds;
none is a renewal, a newborn's first action, or a coincident-expense step.

The separate evening panel includes every living plant at all eight phase-117
censuses: 33 control / 35 veto anchors. Both traces reuse the same world and
share a prefix: 268 spending anchors per trace (36 covered) and five evening
anchors. Subsequent anchors, repeated plants, overlapping windows and these
shared events are **not independent experiments**.

| Panel | Covered anchors | Complete, assumptions held | Exact deaths | Exact alive at boundary | Later assumption break |
|---|---:|---:|---:|---:|---:|
| Spending, control | 86 | 15 | 8 | 7 | 71 |
| Spending, veto | 84 | 14 | 5 | 9 | 70 |
| Evening, control | 33 | 17 | 1 | 16 | 16 |
| Evening, veto | 35 | 20 | 1 | 19 | 15 |

Every complete, assumption-valid outcome and death tick matches. Energy and
stress errors are both **zero** across 3,748 spending-window and 5,519
evening-window valid-prefix live samples (overlapping windows). All covered
windows are fully followed or end at observed death; none is right-censored.

Among the 37 complete clean evening intervals, 20 pay all upkeep, **15 incur
shortages but remain alive**, and two die. The 29 clean spending windows contain
13 deaths, nine shortage-but-alive outcomes, one all-paid outcome and six
early-morning intervals with no remaining maintenance. Those six are not
whole-night survival tests.

The check does not predict later decisions: 140 spending windows have further
expenses, 69 change energy upkeep and four encounter water shortage. The evening
counts are 31, 19 and one respectively; these categories overlap. Across all
windows, including broken ones, energy error reaches 82 and stress error seven.
That is why a one-time evening approval cannot license later expenses. There are
14 distinct case-specific deaths inside covered spending windows and 16 inside
evening windows, not one independent death per expense record.

## Concrete shortages versus fatal exhaustion

These four anchors share tick 4,635, immediately after the last potentially
productive step. Next possible income is tick 6,885; prediction ends at 6,870.
All four trajectories satisfy the assumptions throughout the interval.

| Trace / plant | Starting energy | Upkeep | Exact dark-interval result |
|---|---:|---:|---|
| Control shrub 2 | 208 | 7 | Dies at 6,840 |
| Veto shrub 2 | 256 | 7 | Alive, energy 0, stress 1 |
| Control ground-cover 3 | 255 | 8 | Alive, energy 0, stress 6 |
| Veto ground-cover 3 | 207 | 8 | Dies at 6,600 |

Forbidding all shortages would incorrectly reject the two surviving states.
Other clean evening survivors reach stress seven. The earlier phase-116
purchases themselves remain out of this exact check's scope; observing the next
step must not be represented as decision-time knowledge.

## Which expenses cross the fatal boundary?

Nine covered expense records change the local budget from alive at the boundary
to dead before it. The two repeated rows below count once for **each** trace.

| Trace / plant / tick | Expense | Nodes before → after | Predicted death after expense | Observed death | Further assumption break? |
|---|---|---:|---:|---:|---|
| Both / flower 5 / 945 | Growth, 9 energy | 33 → 34 | 3,000 | 3,000 | No |
| Both / shrub 4 / 4,635 | Growth, 8 energy | 56 → 57 | 6,840 | 6,660 | More growth |
| Control / ground-cover 3 / 12,360 | Seed, 48 energy | 59 → 59 | 14,340 | 14,340 | No |
| Control / ground-cover 8 / 23,880 | Seed, 48 energy | 56 → 56 | 26,040 | 26,040 | No |
| Veto / shrub 9 / 16,260 | Growth, 7 energy | 8 → 9 | 17,640 | 17,460 | More growth |
| Veto / shrub 11 / 23,925 | Growth, 8 energy | 8 → 9 | 25,140 | 24,900 | More growth |
| Veto / shrub 14 / 27,720 | Growth, 8 energy | 16 → 17 | 29,640 | 28,920 | More growth and water shortage |

The two seed purchases were unsupported zero-light anchors in the phase-aware
forecast. Here they have exact post-purchase death predictions, without a
guessed income rate. Five growth records cross an upkeep tier (including the
two shrub-4 records): their cost is both immediate spending and higher recurring
maintenance. Flower 5's same-tier expense is enough on its own to cross the
local boundary.

Another **31** expense records begin with an already-fatal fixed-body budget;
130 remain alive on both sides of the expense. These are local arithmetic
comparisons, **not proven rescues by veto**. Refusing an expense can change later
actions, seed competition and RNG use. A native paired intervention is required
to measure that feedback.

## Verification and next proposal

All **16,153 live census transitions** reconcile energy, water and stress. The
auditor re-verifies the pinned prior audit, native sources and all 72 frozen
artifacts, repeats analysis exactly and exports the portable report. Terminal
income/debits are never invented from cleared telemetry. **34 new / 87 focused
Python tests** pass, including all 256 phase boundaries, an independent
closed-form payment oracle, stage ordering, newborns, future-input isolation,
water exclusions, terminal events and censoring. Verification also passes with
subprocess launch functions blocked. Zero new native calls.

Next discuss a small **host-only, off-by-default spending-guard experiment**
covering growth, renewal and seeds during this exact interval. Recheck the
candidate's post-expense energy/upkeep at each decision; defer expenses whose
energy-only budget already predicts death before possible income returns. Keep
affordable transient shortages, leave earlier daylight decisions unchanged, and
record already-fatal states separately. Compare ordinary and guarded native runs
before claiming improved survival or renewal. This is a proposed diagnostic,
not yet a general reproduction policy, model promotion or firmware change.
