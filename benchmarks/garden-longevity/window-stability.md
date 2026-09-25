# Late-window sensitivity: the rankings change with cohort timing

The broad-trained final controller beats the original in the first three of five
declared late windows, then loses in the last two. Its small primary advantage
over the narrow-trained final also changes sign. These are unchanged controllers
and trajectories: the measurement window, including its own fixed follow-up,
is the only difference. **The original primary result remains unchanged.**

[Frozen protocol](window-stability-protocol.md) ·
[All 160 scores, cohorts and exact contribution changes](window-stability-summary.json)

## Scope and safeguards

Four frozen controllers × four existing review seeds × two disturbance schedules
× five equal 32-day windows. Each window has its own two-day terminal deadline.
This is an offline projection of the 32 complete histories already saved by the
[coverage experiment](training-coverage.md): **zero new native simulations,
training runs or screenshots**. The review seeds have already been inspected;
they are not a fresh test set. Generation 1 duplicates the original and is omitted.

Full original records and counters are validated before projection. Future births,
deaths, seed purchases and seed outcomes are hidden at each deadline, and counters
are recounted. Every score matches independent direct timestamp arithmetic; all
32 full primary evaluations match the saved coverage evaluations exactly.

## All declared windows

Each cell below is the percentage change in renewing-child live ticks relative
to the named baseline. These ticks sum eligible plant occupancy, not elapsed
CPU time. All 160 projected endpoints retain established descendants, so their
terminal tiers tie; renewal is the first component deciding the aggregate rank.
Intervals exclude their start and include their end.

| Main days | G2 / original | Broad final / original | Narrow final / original | Broad / narrow | Broad / G2 |
|---|---:|---:|---:|---:|---:|
| (126,158] | +2.68% | +35.32% | +17.38% | +15.28% | +31.78% |
| (134,166] | +11.08% | +6.60% | +3.19% | +3.30% | −4.04% |
| (142,174] | +17.76% | +20.48% | +5.38% | +14.33% | +2.30% |
| (150,182] | −6.32% | −25.19% | −18.41% | −8.30% | −20.14% |
| **(158,190] primary** | **−4.20%** | **−8.22%** | **−9.08%** | **+0.95%** | **−4.19%** |

Controller CRCs: original `dc5e849d`, broad G2 `556a5dd2`, broad final `c7c1b31e`,
narrow final `449c35fe`. Every controller-window aggregate begins with `[1,8]`.
The portable JSON retains the complete keys, not just these percentages.

Broad-final comparisons in more detail; there are no paired ties:

| Main days | Wins / losses vs original | Fresh-1 / fresh-2 direction vs original | Wins / losses vs narrow | Blocked seed omissions preserving broad/narrow direction |
|---|---:|---|---:|---:|
| (126,158] | 5 / 3 | − / + | 4 / 4 | 4 / 4 |
| (134,166] | 6 / 2 | − / + | 5 / 3 | 4 / 4 |
| (142,174] | 6 / 2 | + / + | 6 / 2 | 4 / 4 |
| (150,182] | 3 / 5 | − / + | 3 / 5 | 3 / 4 |
| (158,190] primary | 3 / 5 | − / + | 2 / 6 | 2 / 4 |

For broad versus original, all four blocked seed omissions retain the aggregate
direction **within every window**, despite the change of direction across time.
Thus simply removing one review seed does not eliminate this temporal contrast.
Each omission removes both schedules for that seed. Full paired, schedule and
omission results for all five comparisons are included in the portable JSON.

## Why the largest reversal happens

The recent-renewal component counts offspring that reach full-cycle confirmation
inside the main window and have an established non-founder parent. Offspring
confirmed before the window are no longer in that cohort, even when still alive;
their live time remains in the lower-priority general descendant component.

Moving from (142,174] to (150,182] changes the broad-minus-original renewal margin
from **+317,820** to **−418,500** ticks, a **−736,320** change. The exact accounting is:

| Change in paired margin | Renewal ticks |
|---|---:|
| Offspring leaving the eligible confirmation cohort | −596,130 |
| Offspring newly entering that cohort | +59,520 |
| Changed credited live time for offspring retained in both cohorts | −199,710 |
| **Total** | **−736,320** |

Fifteen children leave the broad controller's eligible cohort, removing 1,167,180
previously credited ticks. Eight leave the original's cohort, removing 571,050.
This cohort-membership difference is the largest term in the reversal. Child IDs
are compared only within the same controller and world; the margin subtracts
the resulting totals, not purported matches between different controllers.

This is the intended recent-renewal rule, not a scoring bug. It does show how
strongly the result can depend on when successful offspring enter that cohort.
The retained term compares real additional occupancy in the two trajectories;
it does not mean an individual retained child's credited live time became negative.
Births, deaths and environmental phase also change. Lifetime records do not
identify light/water causes, and earlier wins do not erase later weak renewal.

The primary cohort still shows a substantive contrast: broad has 34 credited
children versus the original's 29, but loses 867,210 available ticks after deaths
versus 438,120, leaving **1,470,900 versus 1,602,570** credited live ticks.
More qualifying offspring alone does not imply more sustained occupancy.

## Interpretation and next discussion

We should not call the broad final generally better, pick its favorable window,
or replace the primary result after looking at these alternatives. Adjacent
windows share 24 of 32 days and all come from the same trajectories; these are
not five independent experimental replicates or a new combined fitness score.

The useful next design question is how evaluation should require **sustained
renewal across time**, while distinguishing genuine population failure from
cohort-boundary effects. Discuss a predeclared multi-window evaluation and its
failure rules before changing training or choosing an aggregation formula.
This check does not choose weights, introduce a new objective, promote a model,
or change ecology, firmware or device state. The original final-test set remains
unused. No longer-than-192-day runs were added.

Only the previous [day-192 gallery](training-coverage-gallery.md) is available;
it does not show the earlier endpoints and no such images are implied here.

## Verification and reproduction

The analysis plus deterministic second pass took **3.46 seconds**, excluding
input/baseline verification and source copying. The frozen local bundle has 40
artifact files (14.78 MiB) and manifest SHA-256:
`da3f3eade4b9ee2bb15f7e60f7f72025db6461f3a555a6dcf786917bc6f1759e`.
Its complete scores and child-level transitions are exported with the source
bundle fingerprint; verbose nested v1 score detail is omitted only from the
portable copy. The raw histories/source snapshot remain in ignored local artifacts.

The new 11 unit tests cover all 18 existing arithmetic fixtures, original-score
identity, future-event exclusion, counters, confirmation/death boundaries,
seed-only follow-up, fixed panels, non-mutation and contribution reconciliation.
Six relevant pure-Python CTests pass in the Docker build; this check did not
rerun native simulation regression tests. Reverification recomputes all 160
scores, checks all frozen artifact/input hashes, and reconciles every adjacent
contribution and the original primary result.

```sh
# Requires the frozen local coverage bundle; creates a fresh analysis directory.
python3 -W error sim/garden_window_stability.py \
  --output artifacts/NEW-window-stability

# Recheck the existing evidence without starting any native simulations.
python3 -W error sim/garden_window_stability.py \
  --output artifacts/garden-window-stability-v1 --verify
python3 -W error benchmarks/garden-longevity/review-window-stability.py \
  --check-export benchmarks/garden-longevity/window-stability-summary.json

# Export to a new path; existing exports are never overwritten.
python3 -W error benchmarks/garden-longevity/review-window-stability.py \
  --export artifacts/NEW-window-summary.json
```
