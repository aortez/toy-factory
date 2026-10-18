# Audit root reach and construction limits in the saved histories

Status: **FROZEN before analysis**. Follow the [soil audit](landing-soil-audit.md)
without changing the simulator or running new worlds.

## Fixed subjects and evidence

Use all four existing allocation cases and both arms. Keep the same matched
plants: daylight lineage 16 and dawn lineage 17, born at logic tick 590640.
Inspect their recorded decisions from birth through the shared-capacity
anchors, 626580 and 626520 respectively. Use the soil audit's anchor and 629760
endpoint grids for depth context. Fixed and rotating duplicates are not
independent replications.

Pin the preceding soil results at SHA-256
`bd5066879c513a2d4af58773014d70d39da931584b40eafbe4f6d27d07898a55`,
the allocation results at
`8877c4e6f7f951ec06c546c5fc6f3e0ea0175a250b70e21596e734cd8fa63d76`,
and the original allocation manifest at
`b2aab73b6ed9fadf1e28d1dd32e28911202661ca0ff593cc3c1a3641f4195972`.
Reuse the pinned common-window resource histories and the archived native
source, recording hashes for every additional source and raw trace consumed.
Preserve both repeat receipts and all selected observations in portable output.

## Reachability before affordability

Read the exact archived root steps, seedling positions, cell dimensions,
species and genome depth limits, tip termination, collision rule, resource
costs and body budget. Distinguish root depth in segments from soil depth in
eight-pixel rows. Establish an optimistic geometric envelope from each initial
root and each recorded tip, respecting bounds and the recorded maximum depth
but ignoring future collisions. An unreachable cell under that upper bound
cannot be made reachable merely by choosing another direction. A reachable
cell under that bound is not yet a legal executable path.

Reconstruct actual root extensions and terminations from the saved stand,
direction and resource observations. Require complete identity, clock, root
count and candidate agreement. Retain every selected root bid, including
waits, rejected bids and unchanged choices. Compare the resulting geometry
with the later uptake footprint, or report any evidence gap rather than
silently inventing a body.

Count soil stock beyond the actual roots, beyond the selected plants' maximum
geometric reach, and beyond the most permissive species/genome root envelope.
Keep row-wide stock separate from actual endpoint accessibility. Water in a
later grid is not proof that it was present when an earlier root could grow.

For recorded opportunities that can geometrically reach a deeper wet row,
report the minimum extra nodes and construction costs alongside actual stores,
node allowance, reserved shoot completion and recorded spending gates.
Separate immediate affordability from a multi-step schedule: unchanged future
income, collisions, maintenance, competition and policy choices cannot be
assumed. If geometry alone excludes the deeper reservoir, report that bound
and do not manufacture an affordability or survival counterfactual.

## Validation and limits

Add synthetic tests for segment-to-cell boundaries, maximum-depth termination,
world bounds, minimum path costs and malformed or changed evidence. Require
deterministic exports, portable reanalysis and optional raw-trace verification
without native execution. Preserve prior artifacts and do not overwrite an
existing output.

This is a saved-history feasibility audit, not a deeper-root intervention or a
test of upward wicking. Do not change root limits, body allowances, soil flow,
reserves, controller weights or defaults. Propose any subsequent experiment
separately, based on the remaining uncertainty.
