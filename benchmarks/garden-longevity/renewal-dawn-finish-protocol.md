# One seedling's FINISH through dawn — frozen host counterfactual

Follow the [seedling budget audit](renewal-seedling-budget.md). Compare the
unchanged optional-light world with one narrowly targeted, retry-aware deferral.
This is a mechanism test, not a general spending rule or a training change.

## Fixed inputs and intervention

- Parent: `artifacts/garden-renewal-wet-germination-v1`, manifest SHA-256
  `645ea3d984e064d56263238955188b3efd5eee9b9bc9de5a4c96d4e8f4349cef`.
- Budget audit: `renewal-seedling-budget-summary.json`, SHA-256
  `da2a89751ebc77727ec77c339149ba961ab161281f18bd2c76ea70cef40725e6`.
- Same world `0d983a80`, N model `01b9d94a`, W model `c9ea07fd` only on
  reset founder 5; rainfed-crowded, no-night-growth, selective maintenance,
  eight plant/seed slots, 512 nodes, wide dispersal and water headroom.
- Keep ordinary dark spending and full-night capacity guards. Export founder 1
  at tick 46,080, then activate wet-germination-v1 exactly as in the parent.
- Two arms: `control` and `defer`. In defer, refuse only lineage 12's winning
  last-tip FINISH at tick **66,090**, and that tip's otherwise-allowed FINISH
  retries through **68,340 inclusive**. Release at 68,355 regardless of outcome.
- First receipt must match: root tip 378, coordinates (47,193), depth/max-depth
  9, 61 nodes before/after, 251 energy, 512 water, zero stress, cost 8/5,
  ordinary guard allowed with both forecasts supported and nonfatal.
  Retries identify the same lineage/root position/depth; array compaction may
  change the index. Unexpected selected non-WAIT actions on that lineage in the
  window abort rather than silently broadening the intervention.
- Reject before private memory, RNG, phase, cooldown, tip flags, telemetry or
  stores commit. Do not change the ordinary guard's decision. Its denials take
  precedence; do not count them as additional experimental refusals. No energy
  grants, free FINISH, new reserves, leaf changes, or repeated future-night rule.

## Collection and checks

Build isolated host support, disabled at runtime for control and absent from
ordinary builds/firmware. Preserve historical control output byte-for-byte.
Freeze dirty sources, protocol, binaries, build configuration and input hashes
before capture; run control first and stop if it differs from the saved parent.

Budget: **24 native calls**: each arm's full 0..245,760 ecology/bid and seed-site
traces twice, plus four frame replays twice per arm. Fixed frame ticks are
66,075 (before), 68,340 (dawn maintenance), 69,120 (later daylight), and 245,760
(day 64). Zero training or device calls. No outcome-selected reruns or windows.
Frames show the actual renderer, not a reconstructed illustration.

Audit the full common prefix and exact first transaction difference; verify each
refusal against its winning bid, guard receipt, counter and unchanged resources
and tip. Reconcile every ordinary live resource/stress step with both guard and
experimental refusals excluded from paid actions. Reconcile actual seed-bank
lifetimes/births with native aged-seed/site snapshots. This test does not add a
separate sequential seed-attempt capture; do not infer attempt order from sites.

Follow lineage 12's complete life, including dawn income/stress recovery, first
later paid FINISH, later death or survival, seed production and descendants.
Also report whole-population births/deaths, seed outcomes, day-64 composition
and the fixed day-48..64 closing window. IDs are arm-local after divergence.
Terminal death clears resource telemetry: do not invent terminal income or a
terminal budget. Distinguish dawn rescue, later survival, and enduring renewal.

## Stopping

Require exact repeated traces/pixels and repeated analysis, native transaction
and boundary tests, host regressions, portable evidence and manual frame review.
If an analysis defect needs correction, resume only analysis of the frozen
capture, recording its source fingerprint; never rerun or replace observations.
Update the report, roadmap and issue #30, then discuss the next proposal.
Leave work uncommitted; no push, flashing, promotion, retraining, broader guard
change, extra reserves, or automatically selected follow-up experiment.
