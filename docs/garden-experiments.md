# Matched Garden experiments

One command now collects rain-fed matches, lightweight timelines, a paired
comparison, and detailed replays of selected cases. This changes neither the
Garden ecology nor training fitness and requires no device. Firmware receives
no additional buffers or tracing work.

The [Garden A-life roadmap](garden-alife-roadmap.md) tracks environment
qualification, per-generation champion screenshots, training objectives, and
parallel search. Post-process a completed bundle with the separate
[visual-review gallery](garden-visual-review.md) to capture saved-model images
checked against these timelines. Per-generation integration now exists in the
bounded [persistence pilot](../benchmarks/garden-longevity/training-pilot.md);
the general legacy trainer still uses its existing final-model export.
The separate [seed-establishment audit](garden-establishment.md) follows seeds
to germination/expiry and compares their actual locations with other sites in
the same unchanged worlds.

For the controlled host-only scattering-width comparison, see
[the dispersal protocol and results](../benchmarks/garden-longevity/dispersal.md).
`--dispersal wide-v1` validates an explicitly compiled experimental evaluator;
it does not switch behavior at runtime. Normal builds and firmware stay narrow.
The [water-uptake protocol](../benchmarks/garden-longevity/water-headroom.md) uses
`--water-uptake headroom-v1` with a separately compiled host executable, retaining
narrow scattering. Combining both rules requires explicit opt-in in both CMake
(`TOY_FACTORY_GARDEN_COMBINED_EXPERIMENT=ON`, alongside both rule options) and
collection (`--combined-experiment`, alongside both identity flags). Incomplete
or implicit combinations are rejected. The [combined protocol](../benchmarks/garden-longevity/combined-ecology.md)
and `sim/garden_factorial.py` complete the matched four-condition comparison;
this does not promote either rule to normal host builds or firmware.
The [node-capacity control](../benchmarks/garden-longevity/node-capacity.md) adds
`TOY_FACTORY_GARDEN_LARGE_POOL=ON` only to that combined host build, with
`--node-capacity 512` during collection. Capacity is recorded and verified by
evaluators, inspectors, seed/node audits and screenshot replayers. Its comparison
uses `garden_ecology.py --change node-capacity` against combined **256**, not
against baseline ecology. Normal builds explicitly retain 256 nodes; firmware
rejects the experimental option.
The [leaf-maintenance experiment](../benchmarks/garden-longevity/leaf-maintenance.md)
adds a separate host-only `TOY_FACTORY_GARDEN_LEAF_MAINTENANCE=ON` build on top of
the combined rules. Its evaluator/inspector/replayer accept `--leaf-policy
none|all|selective`; normal tools reject that option. Use the dedicated
`sim/garden_leaf_experiment.py` collector, not the legacy ecology collector:
it checks the additional environment identity, maintenance/resource ledgers,
and native captures. Training is explicitly disabled in this experimental build.
Normal `make host-build` clears the option and retains the existing model format.
`sim/garden_ecology.py`
validates matched settings and compares the recorded conditions; it does not train.

## Run a batch

```sh
make host-experiment-garden GARDEN_EXPERIMENT_OUT=artifacts/baseline-01 \
    GARDEN_EXPERIMENT_ARGS="--candidate-model artifacts/garden-champion.tgm --cycles 8"
```

The default is eight world seeds, eight day/night cycles (30,720 logic ticks,
8 minutes 32 seconds), and the two rain-fed planting layouts. All policies
receive identical initial conditions and weather within each layout/seed.
They run in **separate worlds**, not competing against one another in one plot.
The candidate is compared to the hand-authored adaptive policy. The baseline
policy is also retained as a diagnostic reference. Without `--candidate-model`,
the candidate is the deliberately untrained neural reference, not an implicitly
discovered local champion.

Compare a new model against an old model under the same unchanged ecology:

```sh
make host-experiment-garden GARDEN_EXPERIMENT_OUT=artifacts/model-ab-01 \
    GARDEN_EXPERIMENT_ARGS="--candidate-model artifacts/new.tgm --control-model artifacts/old.tgm --cycles 24 --trials 8 --seed 0x12345678"
```

Supported bounds: `--trials 1-64`, `--cycles 1-26`, `--trace-pairs 1-6`,
`--jobs 1-4` (evaluation processes only), and a positive per-process `--timeout`
in seconds. Default trace-pair limit is five. Each selected pair produces both
policy traces; coincident selection reasons share a pair. Output directories
must be new, either under ignored `artifacts/` or outside the source tree.
An existing directory or timeline is never overwritten.

The comparison is for models on the **same executable/ecology**. Replays use
the exact frozen executables, but this runner does not yet run cross-revision
ecology A/B comparisons or mix different policies within one world.

## What is retained

| Artifact | Purpose |
|---|---|
| `summary.md` | Paired outcomes, distributions, selected cases, and descriptive diagnostic observations |
| `comparisons.json` | Every paired seed, explicit candidate/control identities, raw metrics and cohort denominators |
| `cycles.json` | Reset and every day/night-cycle checkpoint from every trial |
| `reports/*.json` | Complete evaluator reports, including species/founder/lifetime partitions |
| `timelines/*.jsonl.gz` | One-second snapshots plus exact ecology-step birth/death and rain-transition events |
| `cases.json` | Deterministic selection reasons, replay commands, verified checkpoints, and trace hashes |
| `traces/*.jsonl.gz` | Every ecology step and every policy bid for selected trials |
| `traces/*.resources.json` | Checked resource accounting, lineage histories and first-cycle/night spending |
| `models/`, `bin/`, `tools/` | Frozen model bytes, native executables, runner and resource analyzer |
| `source.tar.gz`, `source.patch` | Current nonignored source files including untracked files, plus the tracked diff against HEAD |
| `manifest.json` | Completion marker, artifact/source hashes, Git identity, environment, seeds, roles and settings |

Timelines include sun/rain, deposited water and runoff, soil moisture, living
plants/descendants, occupied plant/node/seed capacity, live roots/active leaves,
resource stores/stress, cumulative births/deaths, and plant-time integrals.
New timelines also include seed creation/expiration counters and lifetime counts
at each full-cycle boundary. The latter record eligible offspring, full-cycle
survivors, and survivors with a full-cycle-surviving child. Older schema-1
timelines remain readable; renewal-window analysis requires these new fields.
They include tick zero and the exact final tick. Capture does not alter the
ordinary evaluator JSON or state hashes; tests compare capture on versus off.

The inspector and resource reconciler were promoted from investigation-only
files into `sim/garden_inspect.c` and `sim/garden_resources.py`. The old Python
analyzer entry point still delegates to the maintained implementation. Legacy
irrigation investigations remain supported by the inspector.

## Selection and interpretation

Selection uses a documented lexicographic ordering: population viability,
durable parents, full-cycle offspring survivors, then descendant plant-time.
This is an **inspection heuristic, not a changed training objective**. The
runner chooses the median paired outcome, largest actual improvement/regression,
earliest extinction on either side, and strongest candidate outcome, deduplicated
and limited by `--trace-pairs`. It does not invent an improvement when all results
tie or lose. A small limit may omit some categories.

Each selected policy is rerun from its original seed through the full horizon.
Every lightweight timeline hash must match the detailed replay, not merely the
final hash. The resource reconciler checks live-step accounting and committed
decisions against the recorded bids. The bundle is not complete if any check
fails. Trace files use deterministic gzip headers and a subsequent replay must
also reproduce the compressed trace hash.

The report describes observed first deaths and flags, and lineages that spent
energy on night growth with no night income during their first-cycle observation
window. These are starting points for controlled probes, **not causal findings**.
Selected traces are biased examples; aggregate statistics come from the whole
batch. Empty offspring cohorts have rate `null`, not zero. Recent births retain
the lifetime ledger's explicit follow-up exclusions. The two layouts share seeds
and should not be treated as independent replicates for significance claims.

Death clears energy/water and income telemetry in the current world code.
Terminal-step budgets remain explicitly unaccounted rather than interpreting
the clearing as resource consumption. Complete death-step tracing, graphical
timeline plots and interactive player replay of arbitrary models are follow-up
work. Exact headless model screenshots are available through the visual-review gallery.

## Replay a saved case

From the repository in the existing build container:

```sh
docker compose run --rm firmware python3 \
    artifacts/baseline-01/tools/garden_experiments.py \
    --replay artifacts/baseline-01 --case 01
```

This is read-only with respect to the bundle. It verifies the relevant saved
artifact hashes, runs the bundled native inspector/model into temporary storage,
and checks timeline hashes and trace identity. No PicoSystem connection is used.
The executables require the matching host architecture and runtime (use the
builder container); they are not portable firmware or browser binaries. Source
and build-cache snapshots support rebuilding but are not a substitute for the
exact executables when checking historical replay.

## Controlled nighttime-growth probe

To compare the same model with and without paid nighttime growth:

```sh
make host-experiment-garden GARDEN_EXPERIMENT_OUT=artifacts/night-growth-01 \
    GARDEN_EXPERIMENT_ARGS="--candidate-model artifacts/garden-champion.tgm --control-model artifacts/garden-champion.tgm --candidate-probe no-night-growth-v1 --cycles 24 --trials 8 --seed 0x6d617463 --split exploratory"

docker compose run --rm firmware python3 sim/garden_renewal.py \
    --bundle artifacts/night-growth-01 --late-cycles 8 \
    --output artifacts/night-growth-01-renewal.json

make host-gallery-garden GARDEN_GALLERY_BUNDLE=artifacts/night-growth-01 \
    GARDEN_GALLERY_OUT=artifacts/night-growth-01-gallery \
    GARDEN_GALLERY_ARGS="--include-adaptive --checkpoint 480 --checkpoint 1920 --checkpoint 2880 --checkpoint 92160"
```

`no-night-growth-v1` is a shared **host-only policy adapter**, not a firmware
ecology rule or retrained model. At sun phases 128–255 it converts `EXTEND` and
`FINISH_TIP` to `WAIT`. Both original actions spend growth resources. Tip
identity, priority, arbitration, and proposed recurrent memory stay unchanged;
ordinary automatic maintenance, maturation, and seed production continue.
Daytime decisions and existing waits pass through unchanged. The distinct
`neural-no-night-growth` policy name and `candidate_probe` metadata prevent
confusion with the unmodified model.

The evaluator, inspector and screenshot replayer use the same adapter. The
inspector additionally records each original neural action and the sun phase;
the resource analyzer checks the veto and records suppressed bids. These are
tip bids, not necessarily committed actions. Legacy per-lineage overrides
cannot be combined with this probe. Neither model weights nor fitness change.

Both evaluator jobs retain baseline/adaptive controls; the collector requires
their final reports to match. For 8 seeds × 2 layouts the two jobs perform 96
trials, representing 48 relevant unique three-way outcomes (probe, unchanged
neural, adaptive). The renewal report requires identical candidate/control model
bytes and uses all three policies, without counting duplicated controls twice.

Renewal analysis distinguishes late births from newly **qualified** lifetime
survivors/parents. Qualification can lag birth by a full cycle; these deltas are
not survival rates for a late-born cohort. Resource/capacity fractions are
time-weighted estimates from at-most-one-second samples, not per-tick traces.
An empty live population with seeds is potential viability, not proof those
seeds will germinate. Frozen detailed traces retain the existing explicit gap
for death-step resource telemetry.

## Provenance and seed separation

The host-only [recurring patch-death collector](../benchmarks/garden-longevity/patch-disturbance.md)
uses `sim/garden_disturbance.py` for 64-day paired controls and fixed environmental
schedules. It freezes ordinary pre-event world/seed censuses and separate immediate
post-event boundaries, reconciling natural deaths, environmental losses, seed
production and window-censored offspring lifetimes. It does not run training or
change firmware; see the report for the exact build flags and reproduction commands.

The [192-day longevity/diversity collector](../benchmarks/garden-longevity/disturbance-longevity.md)
in `sim/garden_diversity.py` reuses frozen controls, adds four fixed fresh schedules,
and verifies independent replays/native frames. The host-maintenance-only inspector
flag `--population` emits birth/death/event boundaries and daily worlds without
the expensive bid/seed-site streams. Tests verify equality with full snapshots
and lifetime accounting. It is not an exhaustive per-ecology resource budget or
seed-identity ledger; bank-species/family disappearance is observed daily. Use
the detailed modes when sub-day exposures or exact seed outcomes are required.

For actual water transfers, the host-only [water-budget audit](../benchmarks/garden-longevity/water-balance.md)
uses caller-owned inventories around the production step's stages, validates
every ecology step and reconciles daily soil/plant/seed accounts. It does not
add world fields, change hashes, implement a second water solver or enable an
observer in firmware. `sim/garden_water_budget.py` freezes and checks replays
against the prior long-run panel; it retains depth profiles and root-access
measurements alongside the balance. See the report for grouped-stage and
seed-endowment interpretation limits.

The [bottom-drainage A/B](../benchmarks/garden-longevity/bottom-drainage.md) adds
an explicit host-only `TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE=ON` build, requiring
the existing maintenance experiment. It removes at most one unit per bottom
soil cell every 16 ecology steps, identifies `bottom-drain-v1` in metadata and
hashes, and adds no authoritative world state. Default/device ecology stays
unchanged. `sim/garden_drainage.py` pairs every prior 192-day case with exact
off-baseline replay and independent on water/population/frame checks. Drainage
is measured separately from evaporation. Empty-world shortage fractions remain
undefined; never treat them as zero. See the report for reproduction, frozen
bundles, adverse survival outcomes and the proposed policy diagnostic.

The [focused policy/resource diagnostic](../benchmarks/garden-longevity/drainage-policy.md)
uses `sim/garden_policy_diagnostic.py` to compare the frozen neural controller
with existing `adaptive-no-night-growth` in the same environments. The inspector
and replayer accept MODEL `-` for that reference; it uses no neural model file.
Inspector rows explicitly identify the new growth policy, and old collectors
reject it unless requested. Full focal traces retain individual bids and live-step
resource budgets while keeping erased terminal income unaccounted. The 40-run
panel, exact old-neural replay checks and all native final frames are described
in the report. No training or controller tuning is performed by this collector.

Its explicit `--reference reserve` mode now compares the same frozen NN with
host-only `neural-reserve-growth`, a fixed `energy-reserve-v1` forecast gate after
the existing night veto. Both compared policies take the same model file;
MODEL `-` still belongs only to the adaptive reference. The wrapper preserves
tip priorities, arbitration and proposed memory, with no new world fields or
neural ABI. Rejected paid growth becomes WAIT. Inspector metadata identifies the
policy and detailed bids expose independently checked forecast inputs/terms.
Unit and smoke tests cover boundaries, malformed forecasts, unchanged inputs,
identity and full/sparse/native agreement. See the
[40-run report and screenshots](../benchmarks/garden-longevity/reserve-growth.md):
the former failure survives, but fewer births and stagnant controls remain
important qualifications. No rule was retuned during collection; no new default,
training run or device deployment was made.

The collector also accepts `--panel full`, validating all eighty original
seed/layout/schedule cases from a 256- or 512-node drainage baseline and running
both policies under both drainage settings (320 runs per capacity). The default
focused scope is unchanged. Full mode preserves every final native frame and
one five-row sheet per seed/layout; its top-level sheet is only the fixed
`9c530b07` review world in both layouts. Metadata identifies panel/capacity, and
replays verify layout/seed/tick/capacity as well as policy/model/hash identity.
The [640-run report](../benchmarks/garden-longevity/reserve-panel.md) includes the
results, regressions, reproducible review helper and exported aggregate/paired
JSON. Full mode does not collect a new per-step resource ledger for every case
and does not train, tune, select defaults or qualify previously examined seeds
as unseen-world evidence.

The [crowded recruitment diagnostic](../benchmarks/garden-longevity/recruitment-sites.md)
uses `sim/garden_recruitment.py` to replay eight explicitly selected adverse and
better-performing cases with the prior frozen binaries. Full world and seed-site
censuses reconcile every ecology step, both patch boundaries, prior population
hashes, resource/seed/lineage accounts and independent native replays. No native
code changes are needed. World-resource analysis only accepts the reserve policy
when explicitly requested; compact site rows are hash-bound to those checked
worlds. Whole/closing bright/twilight/night counts expose overlapping blockers,
mature-seed supply and observational spatial relaxations. Post-step masks cannot
identify the exact conditions of earlier germination attempts. The report and
read-only review helper preserve denominators, censoring, paired native images,
and a separately labeled vacancy close-up; no training or retuning is performed.
For decision-point evidence, `sim/garden_seed_attempts.py` and the host-only
`toy-factory-garden-seed-attempts` executable now observe the exact sequential seed
loop using a caller-owned `garden_seed_audit.h` buffer. The same production step
records expiry/check outcomes and allocation stages; it does not implement a
second solver or add world state. A FROM_TICK prefix runs normally before
observation, preserving histories. The [report](../benchmarks/garden-longevity/seed-attempts.md)
documents the eight-case closing window, real before/after site distinction,
strict ancestry/resource reconciliation, frozen replay/frame equality and
read-only review/export command. Hypothetical open columns are not probabilities
or automatic seed relocation; no ecology or training change follows implicitly.

The subsequent approved [8/16-seed host A/B](../benchmarks/garden-longevity/seed-bank.md)
adds `TOY_FACTORY_GARDEN_LARGE_SEED_BANK=ON`, restricted to the undrained 512-node
maintenance build. It changes only ungerminated seed capacity; ordinary/device
builds remain at eight. `sim/garden_seed_bank.py` freezes four matched pairs,
full world/site/seed-attempt ledgers and native frames at days 64/128/192. New
outputs explicitly declare `seed_capacity:16`; shared analyzers default to eight
and reject mixed identities unless sixteen is explicitly requested. The frozen
eight-seed side and common pre-divergence histories must still match. Results
are mixed and remain exploratory, not a training or firmware promotion.

`sim/garden_turnover.py` and the [turnover report](../benchmarks/garden-longevity/turnover.md)
provide a read-only follow-up using those frozen artifacts. They separate
1/2/4/8/16-day follow-up and censoring, parent/child qualification timing,
natural versus patch mortality, and per-parent final-day/sunset budgets.
No executable is run and no new world is generated. The review helper verifies
the saved input/output hashes and can reanalyze the traces independently.

The subsequent [seed-reserve A/B](../benchmarks/garden-longevity/seed-reserve.md)
uses `TOY_FACTORY_GARDEN_SEED_RESERVE=ON` only in the undrained 512-node maintenance
build, under either seed-bank capacity. It adds no world state and labels native
outputs `seed_reserve_rule: sunset-seed-reserve-v1`; shared maintenance/world
analyzers reject the new identity unless explicitly opted in.
`sim/garden_seed_reserve.py` freezes the matched eight off/on pairs,
lifetime/resource audits and three native frame
checkpoints. First-difference checks include freed-slot reassignment and a valid
unchanged history; every actual gate-on purchase must satisfy an independent
forecast audit. The report distinguishes native execution from strictly checked
reuse after correcting the audit. Defaults/device builds and training stay unchanged.

`sim/garden_seedling_water.py` is a read-only follow-up of that frozen panel.
It checks every world row and reconstructs first-day water budgets for all
offspring born during days (160,192], including survivors and adverse cases.
Root-cell aliasing, actual new soil access, action deltas, patch deaths and
horizon censoring are explicit; terminal-step incomes are not invented.
The [report](../benchmarks/garden-longevity/seedling-water.md) and compact export
record the surface-only/shoot-spending failure and its exceptions. Run
`benchmarks/garden-longevity/review-seedling-water.py` to verify input/output
hashes, or add `--reanalyze` to recompute all first-day histories. This does not
change native rules or execute a new simulation.

The subsequent [wet-root bootstrap experiment](../benchmarks/garden-longevity/root-bootstrap.md)
adds a host-only policy wrapper and `--root-bootstrap-after TICK` to the inspector
and native replayer. It requires the undrained 512-node maintenance configuration,
a recurring patch schedule and either neural no-night-growth or reserve-growth.
It cannot combine with old lineage overrides, gap export or seed-site census.
World/frame records carry `root_bootstrap_rule: wet-root-bootstrap-v1` and the
activation tick; shared maintenance/competition/water analyzers require explicit
matching opt-in. No world fields or model ABI change. `sim/garden_root_bids.py`
verifies unchanged observational replays; `sim/garden_root_bootstrap.py` freezes
the paired late-activation protocol, controls, bids, budgets and native frames.
See the report for limitations, required builds and verification commands.

The [allocation challenge](garden-allocation-challenge.md) then freezes selected
pre-birth worlds and forks native continuations for a single seedling. It accepts
a saved candidate model with the existing ABI, retains fixed neighbors' policies
and weather, and reports survival/resource/productivity vectors rather than
fitness. Six explicit development cases retain both beneficial and adverse root
investment, the three rooted-water failures and a previously successful control.
The executable exists only in the explicit seed-reserve host build. No training,
device/default or neural contract changes follow from collecting this challenge.
See the linked guide for Docker builds, collection and standalone verification.

`sim/garden_allocation_objectives.py` performs the subsequent **offline objective
dry-run**, not a trainer modification. It computes three predeclared objective
variants, fixed bonus-weight sensitivities, exact tie rankings and leave-one-case-
out means from the frozen allocation challenge. Common exogenous patch deadlines,
delayed seed confirmation, resource shortages and censored follow-up are explicit.
The [report](../benchmarks/garden-longevity/allocation-objectives.md) distinguishes
real traces from synthetic arithmetic fixtures and a post-ranking shortage
severity diagnostic. `--verify` reanalyzes the frozen inputs; `--export NEW_PATH`
also includes that separately labeled diagnostic. No resulting score is wired
into `garden_train.c`, and no previously inspected seed is relabeled held-out.

`sim/garden_allocation_survival.py` adds the subsequent
[survival-confirmed rescore](../benchmarks/garden-longevity/allocation-survival.md):
the same cap/weights/windows, replacing zero-shortage confirmation with observed
additional-day parent survival. It verifies the original objective bundle before
appending revised scores, native resource diagnostics and exact break-even lost
survival time. `--output NEW_DIRECTORY`, `--verify DIRECTORY`, and optional
`--export NEW_PATH` preserve earlier artifacts. This remains an allocation
diagnostic, not a descendant-based fitness or a training experiment.

`sim/garden_descendants.py` then joins the saved crowded-recruitment and exact
seed-attempt bundles to distinguish purchases, germination, day-surviving
children and observed further-generation establishment. The
[report](../benchmarks/garden-longevity/descendant-outcomes.md) defines the
creation-time cohort and full-potential follow-up subset, retains parent and
descendant fate separately, and reports policy-dependent opportunity without
turning it into a reward adjustment. Collection/review performs full offline
reanalysis of the old traces; it does not execute native simulations or train.
Use `--output NEW_DIRECTORY`, `--verify DIRECTORY`, and optional
`--export NEW_PATH`. The primary seed-creation cohort is reconciled with, not
silently substituted for, the previous offspring-birth cohort.

`sim/garden_lineage_fitness.py` adds the subsequent
[candidate fitness test](../benchmarks/garden-longevity/lineage-fitness.md).
It scores terminal descendant presence, established renewing parents, first-day
confirmations and established descendant occupancy in that order. Collection
first reproduces the complete frozen descendant analysis, then exports exact
per-world, paired, aggregate and leave-one-condition-out keys plus synthetic
counterexamples. Seed-only endpoints have no comparable key and block a suite
ranking. Use `--output NEW_DIRECTORY`, `--verify DIRECTORY`, and optional
`--export NEW_PATH`; run `python3 -W error sim/test_garden_lineage_fitness.py`
for the portable score semantics. This is an offline reference function, not
trainer integration. Its confirmation-time cohort differs explicitly from the
preceding seed-creation audit. The report records short-lived-offspring and
endpoint tradeoffs that must be settled before adoption.

`sim/garden_lineage_persistence.py` implements the next
[persistence v2 candidate](../benchmarks/garden-longevity/lineage-persistence.md).
Newly established children of established non-founder parents contribute their
observed live ticks, ahead of parent/establishment counts. All worlds have a
fixed two-day terminal follow-up; pending new-generation seeds at its deadline
remain explicitly unconfirmed, and missing follow-up blocks ranking. The main
window moves to days 158–190 within the existing 192-day histories, with matched
v1 controls and cutoff projection preventing future-event leakage. The collector
first reproduces the original v1 bundle in full. Use `--output NEW_DIRECTORY`,
`--verify DIRECTORY`, and optional `--export NEW_PATH`; run
`python3 -W error sim/test_garden_lineage_persistence.py` for portable tests.
This remains the independent offline reference. The subsequent opt-in
`sim/garden_training_pilot.py` uses the same frozen rule for a seven-model search,
without changing the legacy trainer's fitness or removing its maintenance guard.
Its [protocol, build commands and results](../benchmarks/garden-longevity/training-pilot.md)
document the fixed 512-node/bank-8 environment, 158–190 scoring window and day-192
follow-up. Each native trial exports complete bounded lifetime/seed ledgers,
checked independently against Python; the runner archives candidate/RNG identities,
repeats the search, and captures generation 0/1/2 on separate review seeds.
All 18 frames match scored checkpoints and independent re-renders. Use
`--output NEW_DIRECTORY` to collect or `--output DIRECTORY --verify` to verify
without simulation; `benchmarks/garden-longevity/review-training-pilot.py --export
NEW_PREFIX` produces portable JSON, a browsable gallery and native PNGs. The
frozen input recruitment bundle is required for collection; missing/changed
inputs fail closed. A complete manifest is written only after every score and
required image succeeds. No resume, parallel worker pool or live viewer yet.
The pilot's development winner loses the aggregate review comparison. Keep it
as evidence for broader paired evaluation, not a qualified or deployed controller.

`sim/garden_pilot_validation.py` now provides that fixed
[paired follow-up](../benchmarks/garden-longevity/pilot-validation.md), reusing the
pilot's exact native executables and two model files. Eight new world seeds ×
two existing schedules × two controllers produce 32 trials with unchanged clocks
and scoring. The host explanation layer attributes renewal to individual
confirmation times and observed lifetimes, follows the closing seed-purchase
cohort, and reports per-schedule/overall/leave-one-world-seed-out comparisons.
Every trial has an independent final replay; eight outcome-selected images
provide paired visual examples, not representative samples. Use `--output
NEW_ARTIFACT_DIRECTORY` to collect or `--output DIRECTORY --verify` to reanalyze
without simulations. `benchmarks/garden-longevity/review-pilot-validation.py
--export NEW_PREFIX` writes portable scores/cohorts, a labeled gallery and PNGs.
The old pilot's fresh-1 defaults are unchanged; shared Python validation/replay
helpers accept an explicit patch identity for this follow-up. The small aggregate
win is seed-sensitive and has more one-species endpoints; no further training,
diversity reward or model promotion follows automatically.

The subsequent [mixed-condition pilot](../benchmarks/garden-longevity/mixed-training.md)
uses `sim/garden_mixed_training.py --output NEW_ARTIFACT_DIRECTORY`: three
generations, ten models, four development seeds × two schedules, and a separate
four-seed review panel. Settings are frozen in the linked protocol; this is not a
general trainer CLI. It reuses the original pilot's exact binaries/model, saves
all generation champions, and repeats the full search without review/capture.
Use `--output DIRECTORY --verify` for full saved-artifact/score verification.
`benchmarks/garden-longevity/review-mixed-training.py --export NEW_PREFIX` exports
all candidate scores, paired/omission diagnostics, lifetime attribution and 32
native late snapshots. Its optional `--extinction-check NEW_ARTIFACT_DIRECTORY`
independently replays rejected terminal-extinction cases after collection; it
does not train or replace review worlds. The complete pilot passes 147 CTests,
but development improvement fails to transfer to review. Fitness/ecology stay
unchanged; discuss broader training-world coverage before more search depth.

The same runner now supports the fixed `--study coverage` profile, documented in
the [training-coverage comparison](../benchmarks/garden-longevity/training-coverage.md).
It doubles development seeds to eight while retaining the first four, declares
four fresh review seeds, and independently evaluates the frozen narrow champion
on those review worlds. Collection also requires the previous mixed-pilot bundle
(override its location with `--narrow-pilot`). The original `mixed` profile remains
the default; `--verify` reads the study from the saved bundle rule and rejects a
study override. Immutable profile metadata, exact panel checks and a shared
runner/exporter preserve old behavior without globally replacing its constants.
The coverage bundle contains 360 scored/repeated trials and 40 native late images;
the fifth gallery column is the historical narrow reference, not another new
generation. Pass `--bundle artifacts/garden-training-coverage-v1` to the shared
reporter. Its small matched review gain is not robust, and neither final model
beats the original. No new default or device deployment follows.

The [window sensitivity check](../benchmarks/garden-longevity/window-stability.md)
uses only saved coverage-pilot review histories. Run
`python3 -W error sim/garden_window_stability.py --output artifacts/NEW-window-check`
to validate/copy those inputs and evaluate the five fixed 32-day windows with
individually bounded two-day follow-up. No native executables run. The default
input is `artifacts/garden-training-coverage-v1`; `--coverage` can locate that
same fingerprinted bundle elsewhere. Use `--verify` with an existing output to
recompute scores and check artifact hashes. The reporter
`benchmarks/garden-longevity/review-window-stability.py --export NEW_JSON`
exports every per-world score, cohort and exact adjacent-window contribution;
`--check-export EXISTING_JSON` verifies the portable copy. Neither operation
overwrites the frozen evidence or changes the original primary score.
Earlier endpoints exclude future births/deaths/seed outcomes; source counters
are validated before projection. All 160 keys must match direct arithmetic.
This is a sensitivity report, not native world reconstruction, new screenshots,
new independent review samples, or a replacement multi-window training objective.

The subsequent [sustained-renewal candidate](../benchmarks/garden-longevity/sustained-renewal.md)
is also offline and separate from training fitness. Run
`python3 -W error sim/garden_sustained_renewal.py --output artifacts/NEW-sustained-check`
to verify/copy the same coverage input and evaluate four fixed non-overlapping
periods. Candidate credit follows each qualifying child's first 32 days after
confirmation, including bounded carry-in from earlier periods. An independent
sampled oracle and period additivity checks are required. Existing v2 primary
scores are preserved, and old-credit/new-credit single-/multi-period comparisons
are reported explicitly. `--verify` rechecks the bundle; add `--export NEW_JSON`
for a fresh portable copy or `--check-export EXISTING_JSON` to compare it.
The proposed survival-first, pooled-weakest-period ordering is not adopted:
its saved comparisons expose individual renewal gaps hidden by pooling. No native
trial, image capture, alternate aggregation sweep or model selection is performed.

The [individual-minimum follow-up](../benchmarks/garden-longevity/individual-renewal.md)
reuses the sustained-renewal bundle's exact 128 score cases and changes only
aggregation: each world's minimum is taken before summing worlds. Run
`python3 -W error sim/garden_individual_renewal.py --output artifacts/NEW-individual-check`.
The default source is `artifacts/garden-sustained-renewal-v1` (`--baseline` can
relocate that same fingerprinted bundle). It is fully verified before its
manifest/results are copied. `--verify` checks frozen aggregation inputs and
recomputes old/new keys and paired/partition identities; add `--export NEW_JSON`
or `--check-export EXISTING_JSON` for portable evidence. Credit and old primary
scores are unchanged. A complementary-slump challenge loses its pooled benefit,
but strong worlds can still compensate for a zero-minimum world; no hard gate or
training integration is introduced by this diagnostic.

The [renewal-stall case study](../benchmarks/garden-longevity/renewal-stalls.md)
uses a fixed selected panel of two zero-credit broad worlds plus matched original
controls. `python3 -W error sim/garden_renewal_stalls.py --output artifacts/NEW-stalls`
copies verified coverage histories/models/replayer and the matching existing
inspector, then runs the declared 40-process diagnostic budget. Four daily/event
censuses match original ledgers; 16 frames (days 62,78,94,110) each repeat exactly
and match census hashes; four day-192 anchors match saved endpoints. Parent seed
funnels use their own finite follow-up, and sampled blockers are not treated as
time-weighted seed-fate causes. `--verify` reanalyzes saved evidence without native
execution, `--verify --export NEW_PREFIX` emits a portable gallery/summary, and
`--verify --check-export EXISTING_PREFIX` checks those copies. This is not a new
unbiased test panel, scoring gate, intervention, or training run.

The [recruitment-recovery diagnostic](../benchmarks/garden-longevity/recruitment-recovery.md)
extends those same four histories with the existing every-step world/site and
sequential seed-attempt observers. Run `python3 -W error
sim/garden_recruitment_recovery.py --output artifacts/NEW-recovery` for the fixed
12-process budget: census through day 126 and exact attempts in (62,126]. It
pins the prior bundle, matching binaries/configuration and original ledgers;
matches all observer hashes, original census records and seed/birth outcomes;
and distinguishes death, corpse reclamation, hypothetical usable sites, actual
seed placement and first-day survival. All event intervals, including no-hits,
remain visible. `--verify` reanalyzes without native execution, `--verify --export
NEW_JSON_PATH` creates a portable copy, and `--verify --check-export JSON_PATH`
checks it. Event ownership is temporal, not proof of a causal patch effect;
neither an opportunity-normalized fitness nor new ecology is introduced.

The [founder-independence challenge](../benchmarks/garden-longevity/founder-independence.md)
adds optional host-only `--founder-exit TICK` to the persistence trial and replay
tools. It kills only living parent-zero plants through ordinary death, retains
corpses/soil/seeds/survivors/RNGs, and records killed IDs and before/after hashes.
Replay requires an existing disturbance schedule; gap/root-bootstrap combinations
are rejected. Absent the option, native output stays unchanged.
`python3 -W error sim/garden_founder_independence.py --output artifacts/NEW-founders`
uses the fixed 32-pair, day-64 exit / day-128 outcome / day-130 follow-up protocol
and separate optimized `artifacts/founder-independence-build`. It makes 144 native
calls, including frozen-original controls and 24 independently repeated images.
Every pair remains in analysis, including no-ops. Founder-bank carry-in is
separate from new descendant seed purchases, and further generations require
real confirmed parent-child links. `--verify`, `--verify --export NEW_PREFIX` and
`--verify --check-export EXISTING_PREFIX` validate frozen evidence and portable
summary/gallery/PNG copies. This is not a new ecology or training objective.

Use `--split exploratory` (default), `validation`, or `test` to record the purpose.
For validation/test with external models, pass their saved training reports:

```sh
make host-experiment-garden GARDEN_EXPERIMENT_OUT=artifacts/validation-01 \
    GARDEN_EXPERIMENT_ARGS="--candidate-model artifacts/garden-champion.tgm --training-report artifacts/garden-training.json --split validation --seed 0x686f6c64 --cycles 24"
```

`--training-report` can repeat for multiple models. Declared training seeds must
not overlap the trial seeds, and validation/test requires a matching training
model CRC for each external model. Those reports are frozen too. This verifies
the declared history, not unknown manual tuning or whether somebody previously
looked at a test seed. Keep the final test batch reserved until model selection
is over.

The source archive includes the actual dirty/untracked source state, not just a
Git commit hash. If source changes during collection, the runner marks the bundle
failed; finish edits before launching an experiment. A failed run retains its
partial artifacts plus `failure.json`, without a completed manifest. Raw temporary
traces are compressed sequentially to avoid keeping every detailed trace in RAM.
Replays verify all lightweight checkpoints; ordinary batch runs pay only for the
small timeline records, and full bid/plant logs are collected for selected cases.
