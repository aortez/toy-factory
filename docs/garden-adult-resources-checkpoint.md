# Garden adult resources and renewal research checkpoint

This checkpoint answers the original adult-resource question and consolidates
the subsequent investigations into construction, resource access, seed-bank
access and landing competition. It is **host research tooling and evidence,
not a qualified ecology or controller**. No experimental rule is promoted to
ordinary host or PicoSystem behavior.

The review boundary is `feature/garden-adult-resources`, based on recruitment
checkpoint commit `3e44a23`. The [preceding guide](garden-recruitment-checkpoint.md)
describes `feature/garden-recruitment-recovery`; its validation counts and PR
scope are not this branch's. The [A-life roadmap](garden-alife-roadmap.md) and
[issue #30](https://github.com/aortez/toy-factory/issues/30) retain the larger
environment-qualification goal.

## What this checkpoint delivers

- Host observations of adult and seedling budgets, root uptake, shade, paid
  construction, ordered reproduction, seed fates and competing landing sites.
- Explicit host-only experiments for construction budgets, placement, visit
  order, resource protection, root allocation, uptake, wicking, wider late
  dispersal, controlled openings and paid replacement of owned seeds.
- Bounded collectors and offline auditors with source/model/run identities,
  transactional failure checks, observer-neutrality checks and exact repeats.
- Portable protocols, complete result summaries, selected detailed receipts,
  screenshots and regression tests, including unsuccessful interventions.

The original missing-accounting question is closed. The four selected older
plants died energy-short while retaining water, without late optional spending
to veto. Later investigations are included here as completed research, not as
evidence that the environment-qualification milestone has been achieved.

## Findings to read first

| Investigation | What the evidence establishes | Remaining limit |
| --- | --- | --- |
| [Adult resources](../benchmarks/garden-seasons/landing-adult-resources.md) | Income timing, upkeep and storage overflow explain the selected energy losses; spacing, cold and moisture delay replacements. | One diagnosed pair is not a general rescue. |
| [Construction cap](../benchmarks/garden-seasons/landing-growth.md) and [shoot reservation](../benchmarks/garden-seasons/landing-budget.md) | Limiting construction improves selected seasonal survival; reserving shoot space restores flower production. | Steady renewal remains stalled, and reservation loses seasonal renewal. |
| [Placement](../benchmarks/garden-seasons/landing-placement.md), [bank access](../benchmarks/garden-seasons/landing-bank-access.md) and [visit order](../benchmarks/garden-seasons/landing-order.md) | Reachable sites and access order affect who reproduces. Some old and posthumous seeds remain valuable. | Aggregate gains coexist with worse individual worlds and cohort losses. |
| [Resource protection](../benchmarks/garden-seasons/landing-population.md) and [root direction](../benchmarks/garden-seasons/landing-root-direction.md) | Selected rescues do not translate into a population-wide safe rule. | Only two of eight protection pairs pass the harm checks; all four root-direction pairs fail. |
| [Uptake cap](../benchmarks/garden-seasons/landing-uptake-limit.md) and [late dispersal](../benchmarks/garden-seasons/landing-late-dispersal.md) | Broader late dispersal increases established offspring in the examined uptake-capped worlds. | Only four of sixteen comparisons pass every harm check; ten worsen descendant energy shortfalls. |
| [Second opening](../benchmarks/garden-seasons/landing-second-opening.md) | Each selected world gains an established replacement; old and newly purchased seeds can fill openings. | None of the five first recruits produces a child. These histories share one model and weather seed. |
| [Paid seed replacement](../benchmarks/garden-seasons/landing-seed-replacement.md) | Four paid replacements let two first recruits buy seeds and accelerate one refill. | Neither recruit gains a child; every world still establishes one post-opening offspring from the same parent as its control. |

The [seasonal evidence index](../benchmarks/garden-seasons/README.md) links the
full sequence. The [research history](garden-research-history.md) preserves
intermediate findings and superseded next steps without presenting them as
the current plan. More births, full capacity and attractive screenshots do not
alone establish sustained reproduction or diversity.

## Ordinary behavior and research isolation

Ordinary host/device ecology remains **256 nodes, eight plants and eight seed
slots**. No model, scoring change, new mortality schedule, seed replacement,
larger pool or experimental resource policy becomes a default here.

The new policy callbacks, intervention fields and observers are host-only.
Disabled callbacks and zero intervention onsets retain the ordinary path.
New compiled ecology options default off, are reset explicitly by ordinary
host build wrappers, and reject firmware use. The late uptake/dispersal/wicking
family is isolated from incompatible earlier research configurations.

Research mutations must be explicitly requested and tagged in run identity.
Replacement records a distinct seed fate and charges the complete purchase
cost; forced deaths remain distinguishable from natural mortality. Observer
buffers belong to host callers. No trace buffer, collector or trainer is added
to firmware.

## Review order

1. Check shared-code isolation in [garden_world.c](../src/garden_world.c),
   [policy options](../src/garden_agent.h), [world APIs](../src/garden_world.h)
   and the host audit headers. Priorities are bounds, unchanged disabled-path
   RNG behavior, resource charges, seed ownership and callback failures.
2. Review [run transactions](../sim/garden_landing_run.c),
   [CLI validation](../sim/garden_landing_cli.c),
   [seed accounting](../sim/garden_landing_ledger.c) and
   [lifetime accounting](../sim/garden_lifetimes.c). Audit identities, onset
   boundaries, rollback, deaths versus removals and censored outcomes.
3. Review [host CMake options](../sim/CMakeLists.txt),
   [explicit ordinary defaults](../scripts/container/host-garden-defaults.sh)
   and [their regression checks](../scripts/tests/host-garden-defaults-test.py).
   Host availability is not evidence that an experiment runs by default.
4. Read the reports above before the raw data. Use the
   [tool guide](garden-landing-tools.md) for collector/verifier contracts.
   Inspect positive cases and regressions together, including cohort denominators.

## Validation and evidence preservation

The checkpoint validation commands are:

```sh
make check
make host-research-check
docker compose run --rm -T firmware bash scripts/container/host-late-dispersal-build.sh
docker compose run --rm -T firmware bash scripts/container/host-landing-seed-replacement-build.sh
make host-player-check
```

`make check` covers pinned formatting, standalone tests, ordinary host CTest
and the default firmware build. The representative research suite covers the
earlier option chain; the two dedicated scripts additionally check the isolated
late uptake/dispersal family, with and without wicking. None flashes the board or
starts a new research comparison. The player check uses SDL's off-screen driver.
CI now includes the isolated late-family checks alongside the ordinary,
representative research, player and alternate-display jobs. Local checks must
not be reported as a remote CI result.

### Local checkpoint results

- Ordinary host CTest: 216 of 217 passed on the full run. The remaining
  signal-replay boundary fixture was corrected; all eight of its cases pass,
  and `ctest --rerun-failed --output-on-failure` passes. The entire suite was
  not repeated after this test-only correction.
- Representative opt-in research configuration: all 149 CTests pass.
- Four isolated uptake/dispersal configurations: placement, uptake and wicking
  native checks pass in each. Turnover and replacement checks also pass in
  both late-dispersal builds, with and without wicking.
- Ordinary-default regression: all four Python tests pass, including cache
  reset for four valid configurations across both research families.
- SDL player build and off-screen smoke test pass.
- Pristine default firmware builds successfully: 223,004 bytes RAM and
  257,596 bytes application flash reported. This build was run separately
  because the initial `make check` stopped at the stale test. Existing
  devicetree unit-address and enabled-assertion warnings remain.
- Pinned formatting, standalone checks, shell syntax, CI YAML parsing and
  whitespace checks pass. All 467 local links in the seven reviewed Markdown
  files resolve; the archived chronology and roadmap acceptance gates are
  preserved. Markdown layout was inspected as source, not in a rendered preview.

Local logs are in ignored `artifacts/garden-adult-checkpoint-hLcyQr/`.
Alternate-display builds and remote CI were not rerun for this consolidation.
No device was flashed or measured, and no new research comparison was started.

Versioned protocols, portable results and images remain under
`benchmarks/garden-seasons/`. Large raw traces, captured binaries and source
archives remain under ignored `artifacts/`; they are not part of a clone.
Historical verification uses recorded capture identities, not a silently
rebuilt current executable. Strict collectors may require their historical
source context; do not relax their checks or rewrite evidence to make a
different source revision appear identical.

The only simulation-source edit during consolidation corrects the pinned
formatter's initializer layout in
`sim/garden_landing_root_allocation.h`; its values are unchanged. That still
changes source identity. Frozen protocols, collectors and results are retained
unchanged, and current builds are validated separately from historical captures.
The build-default regression also now clears cached configurations from both
research families, including wicking alone and combined late uptake/dispersal.
The full host suite exposed a stale signal-replay rejection fixture that still
used the earlier 288-day limit. It now tests one tick beyond the documented
320-day maximum, matching the existing CLI and ordinary replay boundary test.
This changes the test expectation, not the simulation or CLI limit.

## Stopping point and separately scoped follow up

The paid replacement comparison is complete and fails its required increase
in established offspring for the first recruits. Close this checkpoint by
reviewing and integrating the tooling and evidence; no additional experiment
is needed to make that negative result publishable.

A next investigation could examine **competition among already-pending seeds**:
their maturity, reachable landings and the capacity remaining after an opening
admits its first seedling. Discuss and bound that investigation before changing
placement, dormancy or the environmental opening schedule. New purchases alone
are not its success criterion; follow the recruited plants through reproduction
and check harms to other cohorts.

Broad training, a new fitness objective, ecological promotion, device deployment
and on-device evolution remain outside this checkpoint. Reliable multi-generation
renewal across varied conditions is still unproven, and no device performance
measurement is supplied by these host experiments.
