# Passive root tracing during late drying

Status: **FROZEN before capture**. This follows the
[seed spending audit](landing-seed-spending-audit.md), not a new policy test.

## Question and fixed panel

Explain the two matched plants' later water-income losses using actual root
locations, cell moisture, traversal order and storage overflow. Retain the four
allocation cases in their original order: fixed daylight, fixed dawn, rotating
daylight, rotating dawn. Each has allocation control and candidate arms.
Targets are daylight lineage 16 and dawn lineage 17, both born at 590640.

Observe every ecology sample from **626520 through 629760 inclusive**: 217
samples per world, all roots and leaves, all soil cells, and all shade sources.
Also retain the full adult records from 626505 through 629760 to check root
coverage before growth. Do not select only favorable roots or consumers.

Use exactly **16 full native replays**, two identical observed calls for each
of eight arms. Run to 983040, as before. The existing observer-off allocation
captures are the neutrality controls; no additional full runs, searches,
training, new weather seeds, policy variants or firmware flashes are planned.
Short existing observer unit tests are separate from this full-run budget.

## Frozen execution

Reuse the archived allocation executable, not a rebuild. Its SHA-256 is
`d8aff498a26245936959222e4beadad935bc3484a20cd7fd0e897e26e6e34639`.
The original allocation manifest is
`b2aab73b6ed9fadf1e28d1dd32e28911202661ca0ff593cc3c1a3641f4195972`.
Copy its executable, CMake cache, capture metadata and source archive into the
new bundle, keeping that native provenance separate from the current Python
capture tool's source snapshot. Retain the original model and exact arguments,
adding only `--uptake-trace uptake.jsonl --uptake-window 626520:629760`.

Pin the original allocation results, common-window resource audit and seed
spending audit by SHA-256. Keep model, environmental processes, gardener-off,
limits, allocation arm, reproduction order and all existing guards unchanged.
Use a fresh no-clobber output directory and retain failed captures. A failure
does not authorize replacement runs or tuning of this panel.

Require both repeats' entire result objects, complete ordinary stand/adult/
direction trace hashes and final raw framebuffer hashes to match the archived
observer-off worlds. Require uptake traces to match between repeats as well.
Retain both calls and verify all trace framing, not just the observed window.

## Accounting and interpretation

Independently reconstruct every observed root transfer and soil grid, every
leaf income and light field, root visit coverage and each plant's recorded
uptake and overflow. Reconcile the target's adult rows with its previously
saved complete resource history.

Report full-window and post-anchor target water attribution. The shared
post-uptake anchors are 626580 for daylight and 626520 for dawn: exclude that
anchor's already-completed uptake when reconciling income. The previous audit
shows that all later income occurs inside this window. Require the observed
income and overflow sums to reproduce those saved terminal budgets exactly.

Preserve per-cell target contributions and all plants' cell consumption.
Compare endpoint footprints and per-cell water differences between arms.
For each cell check opening water plus the net changes between one step's
post-uptake grid and the next step's pre-uptake grid, minus actual root
consumption, equals closing water. Retain signed between-step net changes;
do not mislabel them as rainfall, evaporation or any single process.

Distinguish water already absent before uptake from depletion by earlier roots
in the same step. Already-dry cells do not prove natural drought: earlier
competition could have depleted them before this window. Hypothetically
removing earlier consumers is only a frozen-step bound, not a replayed rescue.
Different footprints and prior world histories also prevent unqualified causal
claims. The two order settings may share selected histories; do not count those
duplicates as independent demonstrations. No population policy is promoted.
