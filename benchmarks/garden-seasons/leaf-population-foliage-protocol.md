# Matched dawn light and leaf condition

Separate light exposure from leaf condition for original-placement shrub 19
and fewer-blocker shrub 17 in the [offline comparison](leaf-population-dawn.md).
Keep condition-only repair, weather seed `9a903368`, rainfed Search 1 population,
and all ecological rules unchanged. Run original/fewest placement crossed
with diagnostics off/on: four day-608 replays, not training or intervention.

Record exactly 256 ecology steps in `(152,153]` days for each focal plant.
Retain all active leaf positions, local light, condition before repair, chosen
repair node/action, sun phase/strength, fractional energy remainders, and the
six resource payment points. Use the existing read-only repair-decision route;
forward the original decision without modification. The frozen uptake observer
does not support this maintenance profile and must not be enabled by weakening
its guard.

The light field at that callback is the actual uptake field. Wear occurs before
uptake; repair and construction occur later. Verify the focal body's unchanged
leaf roster against the pre-step world, joining in body order across possible
global node compaction. Check every leaf's condition against the preceding
condition minus scheduled wear. Require stable node/leaf counts, one callback
per step, and no focal construction. Reject missing, duplicate, or inconsistent
records rather than approximating the moment of uptake.

Reconstruct each step's gross energy as
`(prior_remainder + sum((light // 64) * condition)) // 255`, including the
exact new remainder. Reconcile income and payment stages with the existing
maintenance normalizer, the day-152 ledger, and reproduction opening receipts.
Distinguish the sum of light bands from condition-weighted production. A
healthy-leaf ceiling holds recorded light fixed; it is not a counterfactual
world with healthier leaves, which would also change shading and later actions.

Use bounded session-owned storage (256 rows, at most 32 leaves per row), one
allocation, no allocation while stepping, no retained simulation pointers,
and latched failures. Test timing, wear, clamping, compaction, malformed traces,
allocation/output failure, reset, and state preservation. Keep frozen runtime
inputs unchanged and pin sources/binary/protocol during collection.

Run all host and preparation suites first. Use two workers, 180 seconds per
call, a 900-second collection budget, 24 MiB per-call evidence cap, and a fresh
output directory. Retain failures without silent replay retries. Require all
44 checkpoints, four final outputs, and existing diagnostics to match the
reproduction archive byte-for-byte, including pixels. That archive has SHA-256
`3258eda497056194975a308f3a8ab79bd8c980afa968cb694b8263033adb226e`.

Report the complete day's exposure and condition-weighted production, plus
the fixed dawn interval `(152.75,152.875]` ending at the focal opening. Preserve
the differences in body, age, position, neighbors, and bank availability; this
is not an isolated causal placement or repair experiment. Verify the packaged
evidence offline without executing archived code.
