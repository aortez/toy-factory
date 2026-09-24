# Saved-trace reproduction-access audit

Follow the [reserve-handoff result](renewal-dawn-reserve.md) without running
another world or changing ecology. The question is why the rescued shrub makes
one seed despite living through day 64, and how its opportunity compares with
existing adults and the two controls.

## Fixed inputs and scope

- Parent: `artifacts/garden-renewal-dawn-reserve-v1`, manifest
  `ee74ce6b80ff164c5f2358fbcc9829832fac6debebc032086e78b2c52a39f06b`.
- Portable parent: `renewal-dawn-reserve-summary.json`, SHA-256
  `2cbf7bb6b4568bce1f022d8ff28d330e473b3ca46ebd031e2a44688ceadb3163`.
- Use all three arms, every recorded parent, and every ecology step through
  tick 245,760/day 64. Focus on lineage 12 without equating later newborn IDs
  across arms.
- Summaries: whole run; first-noon-and-later (tick >= 69,120); fixed closing
  interval (184,320 < tick <= 245,760). Preserve dead/absent denominators.
- Zero new experimental native calls, training calls, model changes, screenshots
  or device work. Existing images remain the visual evidence.

## Reconstruction and limits

Review the frozen C stage order. Reproduction runs after seed removals,
germination, maintenance, growth and leaf renewal; it only appends seeds, in
current plant-array order. Verify appended-seed order against purchase counters,
16-step cooldown resets, resource debits and the seed ledger.

Infer bank occupancy immediately before reproduction as final bank size minus
this step's verified purchases, then add verified earlier purchases to obtain
occupancy at each plant's turn. Check the start count independently from prior
occupancy minus expiries/germinations. This does not reconstruct the order of
individual germination attempts or light/water conditions within that loop.

Reconstruct each living plant's pre-seed energy/water by undoing only its actual
seed debit. Evaluate unchanged daylight, stress, generation, cooldown, cadence
and body/trait-based retained-resource thresholds. Flower counts include
immature nodes: use a conservative prior-step mature-flower witness and actual
native seed-expense receipts, otherwise label maturity unknown. Do not silently
count a newly flagged flower as mature.

Report overlapping resource/eligibility failures separately from disjoint
opportunity outcomes. Distinguish bank full at loop entry, slots filled by
earlier parents, ordinary dark-guard refusal, verified purchase, and unresolved
flower maturity. A bank-full observation is not a missed viable purchase unless
all independently observable prerequisites are satisfied.

Retain focal maintenance-step evidence and per-parent/window totals, first/last
opportunities, seed-purchase phase/parent patterns, slot-release/refill evidence,
and the target's seed lifetime/spacing witnesses. Compare whole-population and
closing outcomes to the unchanged parent report. No counterfactual offspring,
probabilities or benefits of reordering are inferred from these records.

## Validation and stopping

Verify immutable parent inventory, existing analysis-source hashes, native
source identity, repeated traces and portable equivalence. Re-run the original
saved-data analysis, never its captured binaries. Reconcile every live budget
and every seed purchase; repeat the new analysis exactly and independently
check its portable summary in Docker.

Add synthetic tests for resource thresholds, cooldown decrement/reset, cadence,
daylight/stress, daily spent-flower reset, maturity ambiguity, bank releases,
ordered fills, denied spending, malformed evidence and input preservation.
Register the new Python test without changing native code.

Write the report, update issue #30 and roadmap, then stop uncommitted. Any bank
size, purchase order, retention, reproduction-policy or training change needs
a separately discussed experiment.
