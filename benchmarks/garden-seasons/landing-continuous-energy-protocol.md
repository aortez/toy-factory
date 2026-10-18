# Continuous energy protection comparison protocol

Test whether removing the one-day cutoff from both existing energy checks
rescues the remaining second-night failure without harming the four surviving
checks. This selected diagnostic panel is not training or fresh qualification.

## Fixed comparison

The control is the candidate from the afternoon comparison. Both arms buy the
same root at birth tick T, then apply the unchanged energy forecast and stored
energy condition for afternoon maintenance increases. Control protection covers
ecology ages 2 through 256. Candidate protection starts at age 2 and continues
for that named living offspring through death or the day-256 endpoint. It does
not transfer to descendants or other plants. The first-day water guard, prices,
maintenance timing, priorities, destinations, memory and random draws do not
change. No future-world access or resource grants are permitted.

| Order | Lineage | Birth tick T | Column | Current role |
| --- | ---: | ---: | ---: | --- |
| fixed | 45 | 859860 | 25 | retain survivor |
| fixed | 46 | 905595 | 3 | retain survivor |
| rotating | 48 | 899130 | 27 | retain earlier rescue |
| rotating | 49 | 906570 | 12 | second-night failure |
| rotating | 50 | 906720 | 27 | retain latest rescue |

Use the same model, seasonal rainfed-crowded world, seed 940cfdc4, resource
limits and independent paired worlds as before. Pin afternoon portable results
SHA-256 `dea464eae46233bcc2f253ae657a7b4a05e8b2d3c51a8b484f23e04c40602afc`
and raw manifest `9ec0e6c08a0bf19971e89a6ffbaaef8fe97a5675c20d4d0ade390e3f3e219e82`.
Retain its pinned earlier inputs and model SHA-256
`f2dc989380339614dc512f64f11f2bf03f7079c465c4c9bd18895044ec3e1567`.

Scope uses configured lineage, living nonfounder status and birth-consistent
32-bit plant age. The observation age saturates at uint16 maximum as usual;
that does not expire continuous protection. Elapsed time must remain
ecology-aligned. No mutable
fired flag or new world state. Existing modes and hashes stay unchanged.
Use an explicit opt-in CLI flag requiring both checks and a distinct GLU1 run
identity. The existing afternoon trace schema already records each check's
active status and forecast independently; reuse it without changing its fields.

## Budget and evidence requirements

Exactly forty native experiment calls: five cases, two arms, four calls each.
Capture post-root T, first-day T+3840, full trace to 983040 and its exact repeat.
Stand and resource traces cover T−15 through 983040. Unit and integration tests
are separate. No parameter tuning, new panel selection or extra experiment
calls after inspecting results. Preserve failures and adverse results.

Freeze protocol, inputs, source, executable and build configuration in a fresh
no-clobber bundle before collection. Do not edit source during collection.
Controls must reproduce all previous candidate checkpoints, pixels and full
traces exactly. Pair prefixes must match after normalizing identity; repeats
must match JSON, pixels and both traces. Keep the original formulas unchanged.

Independently check scope, arithmetic and combined arbitration for every bid,
including nonfocal plants. Retain the focal plant's complete resource, body,
reproduction and bid history through death or endpoint in portable evidence.
Recompute energy and water budgets, shortages and guard counts. Attribute a
first changed choice only after checking matching prior physical observations
and pre-action bids, ignoring the scope annotations that necessarily differ.
Check both energy guards together against the day-one-cutoff rule on the same
candidate-state proposals; do not treat later diverged proposals as a paired
causal comparison.

Report all five pairs, survival with endpoint censoring, seed production,
confirmed descendants, other plants' survival and reproduction, seed-bank
effects, closing-window credit and screenshots. Compare diverged descendants by
parent, birth and site rather than numeric ID alone. Survival without seeds is
not renewal. Save raw verification, portable corruption tests and a concise
report. No firmware/default-policy, commit, push or PR changes in this step.
