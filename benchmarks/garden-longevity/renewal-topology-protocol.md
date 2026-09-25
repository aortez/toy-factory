# Read-only topology census before considering shedding

Freeze before native outcome capture. This resolves the missing structural
information in the shedding audit; it does not implement a removal policy.

## Fixed evidence and execution

- Parent: `artifacts/garden-renewal-full-pool-v1`, manifest SHA-256
  `c35c3ab8ec8479312e6bf2b14a9a78867a536b72693a5ce492cc6d64bd03a97a`.
- Shedding audit SHA-256:
  `59f1d44ff4b9870b8911337b3fc552ad2f254cde404e9475a418e3e6eb58cdc0`.
- Replay only the parent's **control**: sixteen-slot admission, 512 nodes,
  eight seeds, unchanged models, routing, weather and prior interventions.
  Do not enable its unsuccessful non-allocating full-pool action candidate.
- Horizon 245760; checkpoints **0, 46095, 69120, 72960, 80940, 111000,
  184320, 245760**. These cover initialization, the existing export, admission
  boundary, existing image, first full pool, peak exhausted-leaf full pool,
  closing-window boundary and endpoint. They are selected from prior evidence.
- Exactly **three** research native calls: rebuilt observer-off control,
  observer-on control, identical observer-on repeat. No new images or training.
  Regression tests are separate. No new scenario, seed or horizon search.
- Observer-off raw output must match the historical control byte-for-byte.
  Removing only the new topology records from observer-on output must reproduce
  that entire output, not just its final hash. Topology records repeat exactly.
- Freeze protocol, source, binaries, build configuration, model and output
  receipts. Analysis-only recovery must not recapture observations.

## Read-only interface and audit

Add an opt-in host inspector output at bounded explicit ecology checkpoints.
Keep it out of the shared world, controller inputs, simulation and firmware.
Export each occupied node's index, owner, parent, position, kind, flags,
growth progress, depth, stored child count and optional leaf condition, plus
each owner's lineage, flags, base and previous-tip indices. Include a physical
world hash. Keep original records unchanged when disabled or enabled.

Recompute children from parent links independently of stored child counts.
Check parent-before-child, ownership, bases, previous-tip references, aggregate
inventories and exact leaf-condition order against the adjacent world record.
Identify leaves by `(lineage, leaf ordinal)` in these append-only living bodies;
global indices can change on whole-owner compaction. Use the existing complete
canonical census for observed zero duration, not spacing between snapshots.

Count overlapping rejection reasons for living zero-condition leaves: base,
root, internal node, TIP, BRANCH_PENDING, FLOWER (including spent flowers),
and previous-tip reference. A conservative structural candidate must be a
non-base childless shoot without any of those roles/references. Report both
all such candidates and the subset continuously observed zero for a day.
The one-day threshold is diagnostic, not a deletion rule. Inspect positive
condition terminal leaves separately, without calling them waste.

Compute per-owner, quantized instantaneous upkeep price differences and
four-node seedling headroom for the conservative set. These are hypothetical
storage/price bounds, not actual savings, births or ecological improvements.
Report zero eligible nodes honestly. Do not relax eligibility after results,
recursively trim parents, remove roots/flowers, or infer benefit from capacity.

## Validation and stop

Strict compiler warnings and UBSan; malformed bounds/parents/ownership/counts,
empty/full worlds, null arguments and output failures; bytewise world preservation.
CLI tests cover bounded checkpoint parsing, duplicate/out-of-order ticks,
alignment/range, same-tick intervention records, disabled output and capture
neutrality. Offline tests cover overlapping flags, internal exhausted leaves,
previous-tip references, persistence, compaction identities and quantization.
Run default and experimental regression suites; independently verify export.

Update report, roadmap and issue #30. Decide whether a bounded shedding trial
is justified, but do not change ecology, models, capacities, device defaults,
or firmware. Stop uncommitted/unpushed with explicit remaining design choices.
