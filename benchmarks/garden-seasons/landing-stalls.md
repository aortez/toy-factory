# Water refusal streak diagnosis

The saved water-guard traces show **short, repeated delays in root growth, not
permanent locks while a funded wetter-root proposal remains available**. The
680 missed-root decisions form 174 consecutive streaks affecting 77 late-born
children. Their outcomes are mixed: 38 survive their first day and 39 die.
This supports a bounded test of affordability-aware arbitration, not automatic
adoption or a claim that forcing roots would rescue the failures.

This is an offline diagnosis of the [completed water-reserve comparison](landing-water.md).
No new experimental trajectories, policy changes, training or device work were
performed. Its failed acceptance gates and unchanged scores still stand.

## Definitions and scope

The input is the complete portable water-comparison archive, pinned by SHA-256.
Both arms retain the same twelve worlds and frozen controllers. Analyze every
late child born in (62,190]: 127 controls and 135 guarded children, with complete
first-day resource follow-up. Descendant IDs are scoped to their world and arm;
no child is matched across divergent trajectories.

An opportunity conflict means the original selected proposal fails the water
reserve forecast while at least one losing root proposal has a locally available
wetter destination and passes that forecast. In the guarded arm this is an
actual WAIT. In the control arm the original action executes: it is a hypothetical
refusal condition, not a recorded wait.

A streak contains maximal consecutive conflicts **15 logic ticks apart**.
An absent winner, a step without the opportunity, death or the guard boundary
breaks a streak. Missing observations are not treated as policy WAIT or as proof
that no root is available. First-day growth follow-up includes age 257, when
the guard is already off; winner receipts cover only ages 1 through 256.

Streak length is a sample count. Its first-to-last span is `(samples - 1) × 15`
logic ticks, not `samples × 15`. A Garden day is 3,840 logic ticks. Root-delay
summaries include only observed later root growth and explicitly retain the
children without such growth separately.

## How long the delays last

The 174 guarded opportunity streaks have a median of **two decisions** and a
maximum of **25**. Sixty-six are single decisions. The longest first-to-last
span is 360 logic ticks: 0.09375 Garden days, or six seconds at the ordinary
60 Hz logic cadence. This is not a device timing measurement.

The broader set of all guarded WAITs includes periods with no funded wetter-root
alternative. Those 1,282 WAITs form 244 streaks, with a maximum of 47 decisions.
Do not confuse that broader duration with the narrower missed-root opportunity.

| Immediately after an opportunity streak | Streaks |
|---|---:|
| Root extension | 66 |
| Shoot extension | 70 |
| Continued guarded WAIT without a funded wetter-root bid | 38 |

Every observed opportunity streak has a next-step winner before guard expiry;
none ends through death, missing observation or censoring in this panel. The
38 continued WAITs show that a streak can end because the local opportunity is
no longer recorded, rather than because growth resumes. The audit does not
identify which losing tip or destination persisted between decisions.

Roots are observed later in first-day follow-up after 136 of the 174 streaks.
These are repeated events within children, not 174 independent trials.

## Which seedlings experience them

First conflicts occur at ages 6 through 28 ecology ticks, with median age 15.
Of the 77 affected children, **73 have not yet extended their starting roots**.
Starting two-root bodies account for 621 of the 680 conflicting decisions.
Stored water at these decisions is 6–12 units: the forecast permits some root
proposal, even though it refuses the higher-priority proposal.

For all 37 affected children that later record a water-maintenance shortage,
the first conflict precedes that shortage; the other 40 record no first-day
water shortage. Likewise, conflicts precede the first energy shortage in all
18 affected children with one. This is an early allocation decision, not merely
a reaction to an already-recorded maintenance failure.

| Affected children | First-day survivors | Water-only deaths | Energy-only deaths | Combined deaths |
|---|---:|---:|---:|---:|
| Steady, 5 children | 0 | 4 | 1 | 0 |
| Seasonal, 72 children | 38 | 20 | 13 | 1 |
| All, 77 children | 38 | 24 | 14 | 1 |

The 58 unexposed guarded children include 22 survivors and 36 deaths. These
groups differ in state, opportunity, climate and subsequent competition; their
survival fractions are **not** a causal comparison of waiting versus acting.
The steady subgroup is especially small. All five affected steady children die,
but the lone surviving steady child never experiences this conflict.

Of the 77 affected children, **59 grow a root afterward**. The median delay from
first conflict to the next root is nine ecology intervals (135 logic ticks),
conditional on observing that root. Delays range from one to 71 intervals.
Four of those children had already expanded roots before their first conflict.
The other 18 never expand their starting roots during first-day follow-up, and
all die. Root acquisition still does not guarantee success: among the 59 with
later roots, 38 survive, seven die water-only and fourteen die energy-only.

For a concrete adverse example, multi /33's seasonal child 36 has the longest
25-decision opportunity streak. It waits once more without a funded wetter-root
bid, grows a root two steps after the streak ends, and still dies water-only
within its first day. A contrary example in the same world, child 37, has a
17-decision streak, grows a root on the next step and survives. These are
explicit duration-selected illustrations; every child remains in the data.

## What the unguarded control adds

The same forecast conflict occurs 99 times among 68 control children, forming
98 streaks: 97 single decisions and one two-decision streak. **None is a WAIT**;
the original selected paid action executes. The next step has no winner receipt
in 87 cases, shoot growth in nine and root growth in two. Missing winner receipts
do not identify the reason the policy was not queried or establish root access.

This contrasts observed arbitration paths, not individually matched rescue
opportunities. The populations diverged earlier, and the controls have different
cohort sizes and states. Existing resource accounts and every four-window score
recompute unchanged.

## Proposed next comparison

Test **eligibility-aware arbitration** as one separate host-only intervention:
exclude growth proposals that fail the same water check, then select the
highest-priority remaining proposal using the existing tie order. Preserve
genuine neural WAIT proposals, and retain winner-only memory advancement. If
all proposals are refused, define an explicit WAIT fallback. Do not implement
exclusion by a priority sentinel that could collide with a valid neural priority.

This does not add a root bonus or force a particular root; the network still
ranks eligible actions. Keep the reserve thresholds, age window, models,
ordinary ecology and objective unchanged. Compare against the current guard,
while retaining the archived ordinary controls, and require the same climate
retention gates. Energy timing remains a separate question. This proposal has
not been implemented or tested by the present diagnosis.

The current receipts do not retain every losing proposal's identity, priority,
memory or complete destination state. They establish a local opportunity but
cannot reconstruct the exact alternative winner or its future uptake, energy
cost, competition or survival. The report therefore does not attribute the
seasonal terminal regression or all steady losses to arbitration alone.

The subsequent [arbitration comparison](landing-arbitration.md) now tests this
proposal separately. It does not change the measurements in this offline
diagnosis or convert its observed opportunities into individually proven rescues.

## Reproduction and checks

```sh
make host-audit-landing-stalls GARDEN_LANDING_STALLS_OUT=artifacts/my-streak-audit.json.gz
docker compose run --rm -T firmware python3 sim/garden_landing_stalls.py \
  --verify artifacts/my-streak-audit.json.gz
```

The collector is an offline analyzer: it accepts only the pinned input and
requires a fresh output file. The [portable diagnosis](landing-stalls-results.json.gz)
contains all 262 late-child records, maximal streaks, observed continuations,
first-day outcomes, resource totals and unchanged scores/comparisons. All figures
regenerate exactly, including byte-identical compressed output.

Eight new tests cover gaps, ordering, duplicates, missing winners, actual WAIT
versus absent observation, death, guard release, first-day censor boundaries,
corrupt receipts, unchanged budgets/scores, contrary outcomes and CLI no-clobber.
The analysis test rejects any attempted native invocation. This step changes
only analysis, tests, build/test wiring and documentation, not simulation code.

Input SHA-256:
`9f93b8047cfa6468bb7053d06f11b10dbe459e02fb36d37f1616c1ba56200e9c`.
Portable diagnosis SHA-256:
`3dbd85795869ea117a07b932ab6a40e9fe7d63e94a4322e6277e05b21b3309ba`.
