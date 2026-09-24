# Remaining dark-guard deaths: coverage limits, not forecast arithmetic

The guard's exact-dark arithmetic holds. The remaining deaths expose decisions
outside its scope: **35 guarded plants already enter the dark interval with a
fatal energy budget; 15 more die just after it ends; four die from water shortage**.
These are case-specific observations across eight guarded trajectories, not
54 independent plants: patch/no-patch versions share early histories.

This is an offline follow-up to the [64-day panel](renewal-dark-panel.md), using
the [predeclared protocol](renewal-dark-failures-protocol.md), recorded in
[issue 30 before analysis](https://github.com/aortez/toy-factory/issues/30#issuecomment-5747045282).
All sixteen saved trajectories remain in the comparison. No new experimental
native calls, model search, rule changes, C edits, device deployment, commit or
push. The [portable audit](renewal-dark-failures-summary.json) retains every dark
anchor, death classification and denial, plus every guarded death's two-day
spending/body history. Existing [native images](renewal-dark-panel-gallery.md)
remain the visual reference; no additional screenshots were selected.

## Where the guarded deaths occur

| Observed failure | No patches | Existing patch schedule | Total case occurrences |
|---|---:|---:|---:|
| Fatal energy budget already present at dark entry | 14 | 21 | 35 |
| Energy death after the dark window | 5 | 10 | 15 |
| Water death | 2 | 2 | 4 |
| All natural deaths | 21 | 33 | 54 |

All **35** first-category deaths match the forecast's exact time, with no later
optional spending, changed energy-upkeep tier or water shortage before death.
The guard cannot refund earlier purchases or shrink a body already built.

For **31/35**, the minimum energy needed at entry would fit within the 256-unit
store, but actual reserves are below it. This is a necessary budget condition,
not proof those plants could collect the missing energy in their environment.
For the remaining **four**, even a full store cannot sustain the observed body
through that interval. They have 68, 70 or 83 nodes; the 83-node plant occurs in
both conditions' shared prefix. All 35 enter at stress zero, so inherited stress
is not the explanation for these deficits.

The last accepted expense before those entries is growth/FINISH in **23** cases
and a seed purchase in **12**. All occur before guard coverage: **27 at phase
116**, three at 115, three at 112 and two at 89. The 12 seed purchases are all at
116. These are historical last purchases, not proven individually sufficient
causes: some plants were already too under-reserved before that final expense.
The two-day histories retain earlier spending rather than assigning every
deficit to the last debit.

Lookback totals start from the saved **post-step** state and count later live
steps. A receipt at that start tick is retained as history but is already paid
in the starting stores, so it is not debited twice. Lifetime totals also include
a newborn's first-step expenses against its initial 64 energy / 24 water.

### Surviving the dark window is not the same as recovering

The remaining **15 energy deaths** occur at phases **12 or 16**, one or five
ecology steps after phase 11, when sunlight first *could* yield energy. At the
end of the preceding dark interval, every one has zero energy and stress six
or seven. Known live-step energy income after possible light returns is only
0–15 units before death. Income on the terminal step is cleared and remains
unknown; it is not counted as zero.

Fourteen of these cases make no optional purchase after that boundary. The
exception buys an eight-energy growth action. Some also changed their body or
spent resources within the earlier interval; those break the single entry
forecast's assumptions and are explicitly marked, not counted as clean forecast
tests. Nonetheless, their observed deaths all fall outside the guard's horizon.
Possible sunlight is not a guarantee of enough actual income to pay upkeep and
recover stress.

Two water deaths occur after a successfully survived dark window; two occur
before any dark anchor was observed. An energy-only spending check does not
claim to protect these plants.

## The regressing world, `abf7af73`

Before the first patch on day 16, both conditions reproduce the same history:
control has 13 natural deaths and guard has 12. After that, the unpatched arms
have none, as does the patched control. The patched guard has **five additional
energy deaths**—one older shrub and four young flowers. That produces the
previous panel's full-run natural-death comparison **13 → 17**.

| Guarded plant | Body at dark entry | Entry energy / minimum to survive dark | Death tick | Observed failure |
|---|---:|---:|---:|---|
| Shrub 18 | 58 nodes | 252 / 240 | 68,400 | Survives dark, then fails after possible dawn income |
| Flower 21 | 33 nodes | 143 / 150 | 68,220 | Under-reserved at entry |
| Flower 22 | 21 nodes | 82 / 90 | 72,000 | Under-reserved at entry |
| Flower 23 | 19 nodes | 45 / 90 | 71,280 | Under-reserved at entry |
| Flower 25 | 36 nodes | 105 / 150 | 75,480 | Under-reserved at entry |

All minima retain the actual body and stress, with adequate water and no further
spending; they are not whole-day reserve recommendations. Plant IDs here belong
only to this guarded trajectory, not matched control individuals.

Two particularly useful receipts:

- **Flower 21, tick 66,060 / phase 116:** an extension costs nine energy and five
  water, changing **32 → 33 nodes** and **151 → 142 energy**. That crosses an
  upkeep tier from four to five per maintenance payment. It gains one energy on
  the next step, entering the dark interval with 143 versus a required 150.
  Both decision-time guard forecasts were explicitly unsupported: the next step
  could still earn income. With the earlier 32-node body, the corresponding
  fixed-dark minimum is 120, not 150.
- **Flower 22, tick 69,885 / phase 115:** a paid FINISH costs nine energy and five
  water, taking **92 → 83 energy** with the body unchanged at 21 nodes. Later
  income/upkeep leave 82 at dark entry, below the 90 minimum. FINISH is a real
  resource purchase even though it does not add tissue.

Flowers 23 and 25 are negative comparisons: even before their last expense,
their stores were below their eventual bodies' dark minima. Simply refunding
that one receipt is not enough under the fixed-body arithmetic. Native
counterfactual replays are still required to claim an actual rescue—or discover
that altered competition moves the failure to a neighbor.

## What the denials mean

All **184 already-fatal denials** belong to **18 case-specific plants** that do
die naturally before the corresponding dark boundary. These include repeated
attempts and shared pre-patch histories. They are not 184 deaths. The other
**213 denials**, whose proposed expense would newly cross the local fatal
boundary, are all followed by observed survival through that boundary.

This is consistent with the guard's intended narrow behavior. It does not prove
213 counterfactual rescues, indefinite survival or better generational turnover.
Conversely, a correct forecast presented after a plant is already doomed under
its assumptions is not a preventive policy.

## Population-wide checks, including survivors

The audit samples every living phase-117 state and newborns first observed
inside a covered interval. It does not select only death-associated anchors.

| Window outcome | No-patch control | No-patch guard | Patch control | Patch guard |
|---|---:|---:|---:|---:|
| Exact survival under unchanged assumptions | 1,880 | 1,819 | 1,812 | 1,825 |
| Exact energy-death timing | 7 | 14 | 7 | 21 |
| Assumptions changed | 70 | 39 | 93 | 69 |
| Interrupted by patch death | 0 | 0 | 16 | 17 |
| Total anchors | 1,957 | 1,872 | 1,928 | 1,932 |

Across **7,689 anchors**, all **1,100,869 valid-prefix live comparisons** have
exact energy/stress agreement. There are 1,138,270 checked dark live transitions
overall. Changed assumptions include accepted expenses, upkeep-tier changes and
maintenance water shortages; simultaneous causes can overlap. Patch deaths
stop biological follow-up and are never labeled starvation. No trace-censored
window happens to occur at this panel's endpoint, but the auditor tests and
supports that case. The patch counts here include only deaths interrupting a
sampled dark window, not all environmental deaths in the full trajectories.

The ordinary controls still have 96 natural deaths versus 54 guarded. Their
dark windows more often change after the anchor; low clean-death counts there
do not mean lower mortality. Neither survivors, repeated cycles within one plant,
nor duplicate patch/no-patch histories are independent statistical samples.

## Verification and scope

- All **71 default host CTests pass**, including **14 new mortality-audit tests**.
  Tests cover exact deaths/survival, daylight exclusion, newborn/dusk selection,
  optional spending/upkeep changes, water failures, patch/trace censoring,
  corrupt prefixes, impossible storage budgets and a post-horizon death.
  Regression fixtures are separate from the zero-new-capture experiment.
- The entire original panel re-verifies: raw repeats, forecasts, resource/tip
  accounting, lifetime/cohort outputs, screenshots and input fingerprints.
  The new audit independently rechecks ordinary live budgets and carries actual
  post-patch state forward. Natural terminal budgets stay unreconstructed; the
  patch step's known ordinary budget is checked globally, while forecast
  follow-up conservatively stops before that patch step.
- Full audit analysis repeats exactly. Current C/header fingerprints match the
  frozen panel, and the audit records analysis-source hashes. It neither edits
  that bundle nor launches native tools. Portable export is regenerated from
  the same evidence, not manually transcribed.

Parent manifest:
`d62a870fea9ecfede3a32cebe1465097c0391f53a0cf781358574fc2db2e4ae8`.
Audit JSON SHA-256:
`059da1ad064de38241a5c61af8cb773a5463b1a7665edea6d75e72a9c4b961eb`.

```sh
python3 -W error sim/garden_renewal_dark_failures.py \
  --check benchmarks/garden-longevity/renewal-dark-failures-summary.json
```

## Next proposal

Discuss two small **one-shot expense-veto counterfactuals** in the saved adverse
world: flower 21's extension at 66,060 and flower 22's FINISH at 69,885. Keep
ordinary matched controls, prove identical state up to each intervention, and
follow both the target and whole-world reproduction/mortality afterward. These
test the two concrete budget-crossing mechanisms before designing a broader
daylight rule. Do not infer that moving coverage earlier by one phase fixes earlier
deficits, overlarge bodies, water failures or the separate dawn-recovery problem.

The rule remains host-only, OFF by default and unqualified as a general renewal
improvement. No veto replay or further guard modification has been implemented
by this audit; training and promotion remain on hold.
