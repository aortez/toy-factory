# Simple terminal shedding is too small a storage lever in this world

The [fixed read-only census](renewal-topology-protocol.md) resolves the missing
topology question. At the full 512-node control endpoint, **136 of 146 exhausted
leaf nodes support descendants**. Of the ten childless exhausted leaf nodes,
four carry flowers, four are growth tips, one is otherwise protected by a
previous-tip reference, and **only one** meets the conservative structural
criteria. That last node has been observed exhausted for just 600 logic ticks,
less than one 3,840-tick garden day.

This does not justify implementing simple terminal shedding as the next
capacity fix. Keep the negative result, close this bounded investigation and
consolidate the branch for review. More substantial living-body turnover or a
different structural representation requires a separate design discussion.

## Fixed checkpoints

Only the prior full-pool experiment's **control** was replayed: the existing
sixteen-slot admission trajectory, 512-node pool and eight-seed bank. The failed
non-allocating full-pool candidate was not enabled. Models, weather, routing,
existing export and all ecological rules remained identical.

| Logic tick | Occupied nodes | Exhausted leaves | Internal exhausted leaves | Eligible terminal nodes | Eligible and zero for a day |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 20 | 0 | 0 | 0 | 0 |
| 46095 | 278 | 42 | 42 | 0 | 0 |
| 69120 | 379 | 86 | 85 | 1 | 1 |
| 72960 | 414 | 70 | 69 | 1 | 1 |
| 80940 | 512 | 86 | 84 | 1 | 1 |
| 111000 | 512 | 166 | 155 | 1 | 1 |
| 184320 | 512 | 145 | 143 | 0 | 0 |
| 245760 | 512 | 146 | 136 | 1 | 0 |

Eligibility means a living zero-condition leaf-bearing, non-base, childless
shoot with no TIP, BRANCH_PENDING or FLOWER role and no previous-tip reference.
Children are independently recomputed from parent links, not inferred from
TIP flags. Spent flowers remain protected. Reasons can overlap; the portable
summary includes the exact combinations rather than adding incompatible totals.

The candidate at ticks 69120 through 111000 is the **same** leaf: lineage 7,
leaf ordinal 45, node 262 in those snapshots, at `(18,88)`, observed zero since
tick 50400. Repeated snapshots do not imply four available deletions. Its
hypothetical removal crosses one water-upkeep price step, but none for energy.
At the endpoint the candidate is lineage 39, leaf ordinal 19, node 497,
at `(72,101)`, zero since 245160. Removing it crosses neither upkeep step.

At every sampled full-pool checkpoint the conservative set frees **at most one
slot**; germination requires four. No removal was performed, so there are no
measured resource savings, rescued seedlings or changed lifetime outcomes.
Even structural eligibility would not prove that shedding beats later renewal.

These are eight predeclared snapshots of one historical world, not a census
of terminality at every tick or a general proof that all shedding is ineffective.
The earlier all-zero-leaf storage bound was optimistic because a leaf-bearing
node is also part of the plant's structural skeleton. Deleting its leaf role
alone would not release that node's slot; removing an internal node would need
different connectivity semantics. Neither is silently added to this trial.

## Reusable host diagnostic

`toy-factory-garden-inspect` now accepts repeated `--topology-at TICK` options
with `--ecology`: at most sixteen increasing, distinct ecology boundaries,
including zero, within the requested horizon. Each topology record follows its
corresponding world record. A checkpoint at an intervention tick deliberately
records each before/after world separately; do not collapse them by timestamp.

The record exports dense node indices, owner slots/lineages, parent links,
position, depth, progress, kind, overlapping flags, stored child counts, optional
leaf condition, and each owner's base/previous-tip references. A world hash
binds it to the adjacent census. Without the maintenance experiment, condition
is `null`, not a fabricated zero. The host exporter validates structural bounds
and links before output and propagates I/O failures without changing the world.

The offline analyzer reconciles all inventories and leaf ordinals against the
adjacent original census. Zero durations come from the complete 15-tick history,
including renewal, death and whole-owner compaction, not from the sparse output.
No topology arrays were added to the authoritative world or firmware.

## Verification and provenance

- Exactly **three native research calls**: capture off, capture on, capture-on
  repeat, each through tick 245760. The rebuilt off trace is byte-identical to
  the frozen historical control. Both topology-enabled traces repeat exactly.
- Removing only the eight new records reproduces **all 194,270 original trace
  records byte-for-byte**, including bids, events, configuration and world hashes.
- Parent links, ownership, unique bases, previous-tip references, recomputed
  children, aggregate roles and exact leaf-condition order agree at all eight
  checkpoints. Repeated analysis and separate Docker verification match.
- Strict warnings/UBSan, native bounds/state-preservation/I/O checks, **13
  focused Python cases**, **95/95 default CTests** and **100/100 experimental
  CTests** pass. The maintenance-only intervention test is skipped in the
  default configuration. C formatting and `git diff --check` pass.
- No shared `src/` C/header changes, firmware build/flash, controller training,
  new screenshots, ecological policy change, capacity increase, commit or push.
  The embedded-C safety review kept the diagnostic read-only and caller-bounded.

Local immutable bundle: `artifacts/garden-renewal-topology-v1`.
Manifest SHA-256:
`9ea83b5cc45d436b232bbb68fe73cec286cbfb5020a7a7732ba9684d4ef9e5c7`.
[Portable summary](renewal-topology-summary.json), SHA-256:
`c7b9a2a7df394334968e6bcc62a006d64b2fc7bc9407442468491b0a04099f3b`.
The bundle freezes sources, protocol, models, build configuration, executable,
raw traces and parent receipts. It remains local/ignored; the summary and notes
are intended for version control and are currently uncommitted.

```sh
docker compose run --rm -T --no-deps firmware python3 -W error \
  sim/garden_renewal_topology.py \
  --output artifacts/garden-renewal-topology-v1 \
  --check benchmarks/garden-longevity/renewal-topology-summary.json
```

At the recorded capture revision, this verifies without executing the simulator.
The later [merge cleanup](../../docs/garden-merge-checkpoint.md) includes a
whitespace-only inspector change; use the archived source for this strict
source-bound verifier. Neither the frozen bundle nor summary was changed.
Collection requires a fresh
output directory; `--finish` is analysis-only recovery of a completed capture.
Earlier strict source-bound verifiers belong to their recorded revisions; their
requirements and saved evidence have not been weakened for the new inspector.

## Merge checkpoint, not another automatic experiment

The agreed question is answered: **conservative terminal shedding does not
offer meaningful storage recovery at these checkpoints**. Do not broaden it into
subtree cutting, internal-stem contraction, flower disposal, root pruning or
relaxed protection rules to obtain a positive result. No shedding A/B is warranted
from this evidence.

Next prepare a coherent review checkpoint of the existing branch: distinguish
reusable production foundations from opt-in research rules, summarize accepted
and rejected findings, retain reproducible tests/evidence and explicitly list
remaining ecology-qualification work. A balanced ecosystem, parallel trainer
and device evolution are not prerequisites for merging that checkpoint.
