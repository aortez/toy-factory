# Garden A-life foundation and research checkpoint

This is the review boundary for `green-garden`, based on `2258de2` / PR #29.
The goal is to merge useful simulation/training foundations and a reproducible
research record, **not to declare the ecology balanced or a controller qualified**.
[Issue #30](https://github.com/aortez/toy-factory/issues/30) remains open for the
larger [A-life roadmap](garden-alife-roadmap.md).

## What this change delivers

- Resource maintenance, reversible stress, death/decomposition and stable node
  reclamation; inherited plant traits, dormant seeds and renewable reproduction.
- Deterministic rain-fed conditions without a gardener in scored evaluations.
- Pure observation/action interfaces, eight-byte recurrent policy memory,
  plant-level arbitration, an adaptive reference and integer neural inference.
- Host policy evaluation, serial evolutionary search, CRC-protected model files,
  model reload/replay, and screenshot galleries for bounded training pilots.
- Per-plant resource, seed, lifetime, lineage and storage diagnostics, including
  the new read-only topology census. Failure cases and negative experiments
  remain part of the evidence.

## What runs where

| Layer | Included behavior | Explicit boundary |
| --- | --- | --- |
| Firmware and normal host scenes | 256 nodes, eight plants, eight seeds; lifecycle, heredity, seeded rain, adaptive growth policy, existing rendering/input | Does **not** automatically run a trained neural champion or learn on-device |
| General host tools | Evaluation, serial search, model serialization, replay, diagnostics and galleries | Training and capture do not become firmware dependencies; per-generation capture is in dedicated pilots, not every trainer |
| Opt-in host research | Wider dispersal/uptake, larger pools, leaf wear/renewal, drainage, spending guards, experimental germination/spacing/light/admission and full-pool handling | All 19 `TOY_FACTORY_GARDEN_*` options default OFF; enabling one is not promotion to production |
| Evidence | Protocols, summaries, reports and selected images under `benchmarks/garden-longevity/` | Full raw bundles and source snapshots under ignored `artifacts/` are local, not included in a fresh clone |

The playable gardener remains available. Training conditions deliberately disable
it. A UI prune hint is not storage reclamation; **no terminal shedding policy**
was added. Plant-trait inheritance is not neural-weight inheritance.

## Review order

1. **Authoritative behavior and memory:** [world](../src/garden_world.c),
   [world layout](../src/garden_world.h), [policy boundary](../src/garden_agent.h),
   [agent implementation](../src/garden_agent.c),
   [neural ABI](../src/garden_agent_neural.h),
   [inference](../src/garden_agent_neural.c) and
   [codec](../src/garden_agent_neural_codec.c).
   Compare against [the simulation contract](garden-simulator.md).
2. **Device integration:** [scene setup](../src/game_world.c),
   [snapshots](../src/game_snapshot.c), [renderer](../src/scene_renderer.c),
   [diagnostics](../src/diagnostic_shell.c) and [firmware sources](../CMakeLists.txt).
3. **Reusable host workflows:** [evaluator](../sim/garden_evaluation.c),
   [trainer](../sim/garden_train.c), [model files](../sim/garden_model_file.c),
   [experiment runner](../sim/garden_experiments.py),
   [gallery](../sim/garden_gallery.py), [inspector](../sim/garden_inspect.c),
   [topology export](../sim/garden_topology.c) and their focused tests.
4. **Research isolation and tests:** [host CMake](../sim/CMakeLists.txt),
   `TOY_FACTORY_GARDEN_*` guards in shared sources/headers,
   [ordinary build defaults](../scripts/container/host-garden-defaults.sh),
   [research CI build](../scripts/container/host-research-check.sh) and
   [CI](../.github/workflows/ci.yml).
5. **Conclusions, then detail:** use the findings below before the chronological
   [investigation index](../benchmarks/garden-longevity/README.md). Generated
   `*-summary.json` evidence is marked `linguist-generated` for diff review;
   it is retained unchanged, not excluded from the repository or correctness checks.

This is a targeted merge-preparation review, not a claim that every historical
research script or opt-in combination has received an independent full audit.

## Findings to retain

| Question | Conclusion | Representative evidence |
| --- | --- | --- |
| Does a surviving/full garden prove success? | No. Founders can persist while durable descendant renewal stalls. | [Lifetimes](../benchmarks/garden-longevity/lifetimes.md), [founder independence](../benchmarks/garden-longevity/founder-independence.md) |
| Is there a settled training objective? | No. Initial bounded-renewal improvements did not reproduce consistently; coverage/transfer show tradeoffs. | [Replication](../benchmarks/garden-longevity/renewal-replication.md), [coverage](../benchmarks/garden-longevity/renewal-coverage.md) |
| Can spending discipline help? | Yes in selected cases, but adult survival, descendant renewal and species retention can move in opposite directions. No universal guard was accepted. | [Dark panel](../benchmarks/garden-longevity/renewal-dark-panel.md), [purchase interventions](../benchmarks/garden-longevity/renewal-purchase-veto.md) |
| Will larger admission limits solve turnover? | More descendants establish, but living structural storage fills and diversity tradeoffs remain. | [Plant slots](../benchmarks/garden-longevity/renewal-plant-slots.md), [node pressure](../benchmarks/garden-longevity/renewal-node-pressure.md) |
| Can full-pool actions or simple leaf shedding recover useful space? | Neither justified promotion. Exhausted leaf-bearing nodes mostly remain structural supports; only zero or one conservative shedding candidate appeared at each sampled checkpoint. | [Full pool](../benchmarks/garden-longevity/renewal-full-pool.md), [topology](../benchmarks/garden-longevity/renewal-topology.md) |

Preserve the difference between a causal intervention, an observational bound,
a selected example, and an independent replication. Do not combine whichever
rules looked individually promising into an untested production ecology.

## Merge-preparation cleanup

- Fixed the two files rejected by the container's clang-format 18. The C changes
  are whitespace only; no simulation rule or ABI changed in this cleanup.
- Centralized all 19 research resets for normal simulator, player and profiler
  builds. Previously the latter two could retain older experimental options in
  reused CMake caches. New tests compare against the complete CMake option list,
  execute all three wrappers with a recording CMake stub, and reset a real
  experimental cache. Two existing guards now check the shared defaults.
- Added `make host-research-check` and a CI step for the expanded 512-node,
  sixteen-slot dependency chain with UBSan. It uses a separate build directory
  and runs regressions, not a new experiment or training campaign. It does not
  cover every mutually incompatible research configuration.
- Added this review guide and generated-evidence diff metadata. No experiment
  evidence was deleted, rewritten, squashed or moved to an external service.

## Validation boundary

Run from the repository root; host dependencies stay inside Docker:

```sh
make check                 # formatting, native tests, 95 default CTests, default UF2
make host-research-check   # 100 research-configuration CTests; separate cache
make host-player-check     # SDL off-screen smoke test
make host-profile-build    # ordinary optimized profiler, all research flags OFF
```

Merge-preparation results:

- `make check` passed, including formatting, standalone/native tests, all 95
  default host CTests and a pristine default firmware build.
- A separate source-only copy of the working tree (tracked and untracked source,
  but no ignored build caches or experiment bundles) passed all 95 default CTests,
  all three build-default regression tests and all 100 research CTests. The research
  build used the same script as `make host-research-check` and the new CI step.
- `make host-player-check` passed its SDL off-screen smoke test;
  `make host-profile-build` passed. All 19 research flags are OFF in each ordinary
  simulator/player/profiler cache.
- The default firmware links with 222,996 bytes in the 255 KiB main RAM region
  (85.40%), plus the separately reserved 8 KiB Core 1 region. This is static linker
  accounting, not a runtime stack/high-water measurement.

These results are also recorded in issue #30. CI on GitHub has not run this
unpushed checkpoint. These checks do not require the private/local historical
experiment bundles. They do not establish device timing, power behavior, USB
stability or unattended ecological viability; no firmware was flashed here.

### Historical evidence is source-bound

An archived experiment's verifier checks its exact source revision, not just
simulation semantics. Even a formatting-only inspector change invalidates that
source check. Run historical verification with the source recorded in its
bundle; do not weaken the verifier, replace a saved result or silently recapture.
The latest topology archive and portable summary are unchanged by this cleanup.
Individual reports describe their frozen inputs and reproduction commands.

The benchmark directory is roughly 275 MiB in this working tree, primarily
generated JSON. This checkpoint retains that evidence; `linguist-generated`
improves review presentation but does not reduce clone/storage size. A future
compression or publication strategy should preserve hashes/provenance and be a
separate explicit decision, not deletion during cleanup.

## Still open after this merge

- Sustainable descendant reproduction and useful policy tradeoffs across a
  qualified range of weather, light and crowding conditions.
- A validated fitness objective with declared training/review/final-test roles;
  complete terminal resource accounting where death clears live telemetry.
- Living plant age is still a 16-bit counter: fix/test its wrap before interpreting
  runs reaching 65,536 ecology steps (256 garden days). Historical longer panels
  stop at 192 days; this checkpoint does not silently change their ecology.
- Broader structural turnover needs a separate design discussion. Do not infer
  permission for internal-stem contraction, root pruning, new buffers or quotas.
- General trainer capture integration, deterministic parallel search, optional
  foreground replay, qualified frozen-model deployment and later on-device
  controller evolution remain separate roadmap milestones.

Completion for this checkpoint means clear scope, retained evidence, passing
build/test checks and reviewable commits. It does **not** mean closing issue #30.
User review/commit and push are the next handoff; no remote PR is created until
the branch is published.
