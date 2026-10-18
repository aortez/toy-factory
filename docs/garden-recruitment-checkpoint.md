# Garden recruitment and landing aware control checkpoint

This branch follows the seasons and persistent-seed implementation in PR #33.
It delivers host tooling and reproducible evidence about seed placement,
establishment and renewal. **It does not deliver a qualified controller or
promote any experimental ecology or policy to firmware defaults.**

This is the review boundary for `feature/garden-recruitment-recovery`.
The broader [A-life roadmap](garden-alife-roadmap.md) and
[issue #30](https://github.com/aortez/toy-factory/issues/30) remain open.
The [earlier foundation checkpoint](garden-merge-checkpoint.md) describes
PR #31, not this branch's validation results.

The subsequent [adult resources and renewal checkpoint](garden-adult-resources-checkpoint.md)
now records that follow-up's scope and findings. It does not expand this
historical recruitment checkpoint or retroactively change its conclusions.

## Included work

- Exact host observations of seed production, germination blockers, first-day
  resource transfers, ancestry, reproduction and established-descendant gaps.
- Landing-neighborhood observations with causal terrain history, separate
  host-only TGL2 encoding, integer inference, model files and replay tools.
- Bounded deterministic training comparisons, input ablations, same-state
  decision traces, separate review panels and repeatable screenshot galleries.
- Explicit host-only experiments for dispersal, seedling reserves, seed-bank
  capacity, producing-flower origin and water-eligible arbitration.
- Portable reports, compressed histories, model records, screenshots and tests
  preserving both improvements and regressions. No new experiment is required
  merely to finish this PR.

Ordinary host/device ecology remains 256 nodes, eight plants and eight seed
slots. The playable policy, gardener controls and old model/training paths
remain separate from these experimental landing-model commands. New research
build switches default off; the eligibility callback and landing observers
are host-only. No trained champion, new reserve rule, wider dispersal or
larger bank is selected for the device by this checkpoint.

## Review order

1. **Shared-code isolation:** changes in [garden_world.c](../src/garden_world.c),
   [garden_world.h](../src/garden_world.h), [garden_agent.h](../src/garden_agent.h)
   and the host-only audit headers. Check ordinary-path parity, bounded
   capacities, callback ownership, failures and rollback.
2. **Landing-model contract:** [observations](garden-landing-observation.md),
   [encoding](garden-landing-encoding.md), [inference](garden-landing-inference.md)
   and [replay tools](garden-landing-tools.md). Versioned experiments must not
   masquerade as ordinary model evaluations or alter frozen inputs.
3. **Experiments and tests:** [training](garden-landing-training.md),
   [validation](garden-landing-validation.md),
   [arbitration](garden-landing-arbitration.md), [host CMake](../sim/CMakeLists.txt)
   and [ordinary build defaults](../scripts/container/host-garden-defaults.sh).
4. **Conclusions before raw data:** the
   [seasonal evidence index](../benchmarks/garden-seasons/README.md), especially
   the [multi-seed training results](../benchmarks/garden-seasons/landing-multiseed.md),
   [arbitration screen](../benchmarks/garden-seasons/landing-arbitration.md) and
   [turnover diagnosis](../benchmarks/garden-seasons/landing-turnover.md).

## Conclusions and remaining limits

Landing-aware training and several isolated mechanics improve selected measures,
but do not establish robust continuing reproduction across the declared panels.
Persistent adults, first-day survivors and sustained descendant renewal are
different outcomes. Improving one can worsen another.

The latest arbitration screen removes a measured bid-selection blockage but
fails retention. Its saved-history audit separates a seed-supplied generation
gap from persistent blocked landing sites and first-day energy/water failures.
The adult resource history needed to explain the generation gap is not recorded
in those traces. The next investigation should measure that history and
concurrent seed blockers before choosing another intervention.

That follow-up is outside this PR. So are broad training, a changed fitness
objective, new ecology defaults, controller deployment and on-device evolution.
Merging useful tooling and negative evidence does not close environmental
qualification or demonstrate long-term diversity.

## Validation and evidence handling

```sh
make check                 # formatting, standalone tests, ordinary host suite, default firmware
make host-research-check   # representative opt-in research configuration and tests
```

CI additionally checks the host player and alternate display firmware builds.
The PR description records which commands were run for this checkpoint; older
reports' test counts describe their own source revisions. Building firmware
does not imply it was flashed or that device performance was measured.

Reviewable evidence lives in `benchmarks/garden-seasons/`; full frozen binaries,
source snapshots and raw experiment bundles remain under ignored `artifacts/`.
Portable evidence tests run without those historical bundles. Historical
verifiers must use their recorded source/binary context, not silently rebuild
or overwrite prior evidence. Generated JSON is marked for collapsed GitHub
diff presentation; neither those files nor negative outcomes are removed.

Merge preparation also separates the old seasonal recruitment output variable
from `GARDEN_LANDING_RECRUITMENT_OUT` for the newer trace target, with a dry-run
regression test for both defaults and independent overrides.
The standalone Garden/game-world test scripts now link the host landing-observer
source, matching the CMake test build; the full check exposed those missing links.
