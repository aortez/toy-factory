# Purchase time trace protocol

Observe why the four repair variants choose different seed destinations in the
early handoff of rainfed weather seed `9a903368`. This is a read-only diagnostic,
not a placement-policy experiment or training run. Ecology, growth and repair
models, family routing, and firmware defaults remain unchanged.

## Fixed comparison

Run Search 1 with each existing family-2 repair variant (`none`, `light`,
`condition`, `both`), activated at tick zero, through day 608. Run each once
with diagnostics off and once with diagnostics on: eight native calls, two
workers, at most 180 seconds per call and 900 seconds for collection. Retain
failed attempts; do not replace or retry them silently. Limit evidence to
24 MiB per call. Use a fresh output directory.

Record every species' paid seed-placement decision in the half-open interval
`[30, 35)` days (logic ticks 115200 through 134399). This includes the preceding
births and the purchases on days 31 and 34 without selecting records after
seeing their outcomes. Cap the trace at 256 purchases; exhaustion fails the
run. Capture the supplied draw and reachable columns, blocked-choice mask,
ordinary and final choice, spacing-clear and legal columns, current site
blockers, and the stored plant roster with current age, energy, water, stress,
species, lineage, and node count. Include retained dead plants because they
still block spacing. No future death times or additional RNG draws enter the
observer or any decision.

## Instrumentation and checks

Keep the authenticated runtime preparation byte-for-byte intact. A separate
build-directory adapter changes only the placement callback binding in a copy
of the frozen host runner. It forwards the original callback exactly once and
borrows a session-owned trace through the existing synchronous growth observer.
No global observer, policy change, or per-step allocation is permitted. Observer
failure propagates and prevents publication of successful session outputs.

Before collection, run the existing seven session/viewer/analysis suites and ten
preparation checks, including focused observer boundary, capacity, failure,
reset, and parity tests. Pin the native binary, protocol, adapter recipe, and
sources. During collection these inputs are frozen.

Compare all eleven existing checkpoints (days 0, 32, 192, 208, 220, 222, 224,
256, 384, 512, 608), complete history, canonical state, and raw framebuffer
bytes with the matching original from-start panel, as well as logging off/on.
Resource traces through day 256 must also match the panel exactly.

Baseline archive: `leaf-population-gates-panel-results.json.gz`, SHA-256
`2c1e0260aad599c631073d3f796bc2529e97632e1ff6110bd2f2998aff4900fd`.

## Analysis

For each focal-family purchase, distinguish a free reachable alternative from
an all-blocked fallback, identify the current spacing blockers, and compare
their contemporaneous age and resources. Join later seed outcomes only in
offline analysis. An association with later clearance is not evidence that a
plant could predict death accurately. Do not infer that blocked purchases
should be prohibited: the previous successful handoffs also began blocked.
