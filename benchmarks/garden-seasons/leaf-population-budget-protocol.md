# Resource budgets around missed reproduction openings

Determine what pays down shrub 17's resources around its eight open-bank
reproduction failures in the [ordered access comparison](leaf-population-reproduction.md).
Separate immediate repair expense from accumulated upkeep, growth, income,
and capped storage. Do not alter any decision or ecological rule.

## Fixed trace and comparison

Use two day-608 replays of weather seed `9a903368`, rainfed Search 1 population,
condition-only repair and fewer-blocker placement: diagnostics off/on. Keep
the usual eleven checkpoints, resource trace, early purchase trace, and
ordered reproduction trace. Add only the budget trace when diagnostics are on.

The eight focal logic ticks are 587040, 621660, 709920, 733500, 733560, 744540,
764520, and 867420. They are exactly shrub 17's visits that see space but fail
a resource check in the prior trace, not new fitted intervention times.
For each tick t, record ecology steps in `(t-3840,t+960]`: one Garden day
before and a quarter day after. Deduplicate overlaps. This gives 2,244
step records, bounded by 2,560, for lineage 17 only. Times select observation,
never policy behavior.

Retain both resource ledgers and their six ordered payment points, separating
leaf renewal from construction. Include leaf condition, fractional energy
remainders, stress, node counts, and maintenance timing. On reproduction
cadence ticks, join the actual pre-purchase eligibility mask, bank occupancy,
and required resource thresholds. Enforce exact step coverage, conservation,
stage consistency, and agreement with the previous opening receipts.

Use two workers, 180 seconds per call, a 900-second collection budget, and
24 MiB per-call output limit. Require a fresh directory and retain failures;
do not silently repeat simulations. Freeze the protocol, sources, and binary
during collection. Baseline archive `leaf-population-reproduction-results.json.gz`
has SHA-256 `3258eda497056194975a308f3a8ab79bd8c980afa968cb694b8263033adb226e`.

## Validation and interpretation

Keep the authenticated runtime intact and reuse its pure maintenance-budget
normalizer. Storage belongs to the host session, is allocated once, and never
grows while stepping. Errors latch and prevent publication. Test window
boundaries, overlaps, missing or duplicated steps, absent lineages, malformed
visits, allocation/output failures, reset, and state preservation.

Run the host suites and preparation tests before collection. Require both
replays, all 22 checkpoints, and all existing diagnostics to match the prior
archive byte-for-byte. Verify the new archive without native execution.

Report the opening-step deficit, repair expense at that step, preceding-day
income and expenses, and recovery during the following quarter day. Adding
back a same-step repair debit is only a payment-point calculation. Adding
earlier debits is not a no-repair trajectory: storage caps, later income,
leaf condition, decisions, and competitors can all change. Do not claim that
a reserve guard improves reproduction without a separate intervention trial.
