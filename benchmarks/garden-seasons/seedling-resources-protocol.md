# Fixed seedling resource replay

Diagnostic follow-up to the [offspring outcome audit](offspring-outcomes.md).
Use the frozen confirmation histories, uncompressed SHA-256
`2e6a1eb37d7eee860120f762c05f4c1b5e5f045b52cc942e229005aefaec6d7f`.
This is selected-case explanation, not fresh-seed confirmation or an intervention.
Do not change ecology, policy, weather, capacity, model or device firmware.

## Selection before inspecting new detailed traces

Only combined-climate offspring born strictly after day 112 and with a full
day of possible follow-up by day 128 qualify. Order worlds by the confirmation's
declared seed order, then rainfed/rainfed-crowded, then baseline/adaptive; within
a world order by birth tick and lineage ID.

Select the first wide-arm example of each:

1. Death on/before its full-day boundary, energy-only terminal shortage, without
   active drought or seasonally dim light at death.
2. The corresponding water-only failure category.
3. An offspring surviving a complete day.

For each, include the identical narrow world (same seed/layout/policy). In that
world select the eligible late offspring of the same species with the nearest
birth tick, breaking ties by earlier birth then ID. If none exists, record that
absence; do not move to another world or invent a matching plant. Numeric IDs
are not matched across rules. Merge duplicate world jobs and focal plants.
Surviving controls supply context, not proof that a failure could be rescued.

## Trace and accounting

Use the existing inspector's `--death-audit` mode, which includes every ecology
step and decision bids, through day 128. All C/header/shared collector sources
and both inspector/replayer binaries must match the confirmation. Only the
scattering flag differs across builds; retain start/end dependency hashes.

For every selected plant, inspect birth through the earlier of death or its
full-day boundary. Check contiguous samples, identity, all live resource-budget
equations and decision winners. Reuse the maintained budget reconciler and
terminal receipt validator; do not infer cleared death-step income. Account for
starting grants, uptake, overflow, maintenance paid/unpaid, growth, seed spending
and terminal discard. Record post-step root-cell moisture, body size, active
leaves, actual uptake, global sun and growth proposals, plus first shortage and
phase transitions. Plant state/action histories—not terminal flags alone—must
support the interpretation.

Root moisture is post-uptake, not a pre-uptake supply measurement. Global sun and
candidate light are not per-leaf light maps. Zero energy income with active
leaves is observed non-productivity, not by itself proof of its geometric cause.
No assumed veto/rescue or hypothetical future income is a measured intervention.

Match all 129 daily states and complete birth/death histories with the frozen
input. Repeat each selected world's native trace byte-for-byte. Capture both
rules at each wide focal plant's birth and analysis endpoint; match rendered
state hashes and framebuffer CRCs with the trace. Do not select nicer images
afterward. Keep portable focal histories, numeric summaries, selection and
image checksums; full compressed traces remain in ignored artifacts.

Stop on a replay/accounting mismatch. Record limitations and useful/non-useful
findings without expanding the panel or retuning any rule. Discuss any next
counterfactual or additional instrumentation before implementing it.
