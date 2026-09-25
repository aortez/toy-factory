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

The [bounded-renewal training comparison](../benchmarks/garden-longevity/renewal-training.md)
adds an explicit Python objective adapter to the mixed pilot runner. Its default
remains persistence-v2; `garden_renewal_training.py` fixes two arms, v2 and the
previously tested individual-minimum bounded-renewal key. Both use the same
original model, initial mutation stream, eight training seeds and two schedules;
four fresh review seeds never select parents. The exact native tools/configuration
come from the verified coverage bundle, without rebuilding or changing ecology.

```sh
# New collection only after agreeing a fixed protocol and budget:
python3 -W error sim/garden_renewal_training.py --output artifacts/NEW-renewal-training
# Reanalyze the completed evidence, without executing native simulations:
python3 -W error sim/garden_renewal_training.py \
  --output artifacts/garden-renewal-training-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-training
```

The [frozen protocol](../benchmarks/garden-longevity/renewal-training-protocol.md)
allows three generations of three mutants per arm: 704 ledger trials including
full capture-disabled repeats, 128 frame replays and 36 mutations, exactly 868
native processes. Every generation, including unchanged champions, has all eight
review images at day 192. Both score views, individual periods, blocked omissions,
cohorts and diversity remain visible. Verification requires A to reproduce the
prior coverage search exactly, identical A/B first-generation inputs, independent
capture-disabled search agreement and all 64 framebuffers to repeat byte-for-byte.
`--verify --export NEW_PREFIX` exports summary/gallery/PNGs; `--verify
--check-export EXISTING_PREFIX` checks the published copies against the frozen
bundle. This is an experimental host pilot, not default fitness adoption, a
new final-test panel or a promoted controller. Do not rerun/extend it based on
review outcomes without discussing a separate protocol.

The [independent replication](../benchmarks/garden-longevity/renewal-replication.md)
uses `sim/garden_renewal_replication.py` with immutable custom study profiles:
separate training/review patch schedules, world seeds and per-search mutation
RNGs. The original mixed/coverage/A-B profiles preserve their settings and output.
The fixed replication runs two complete serial A/B replicas concurrently in
private directories, not a configurable parallel trainer. Each uses the exact
previous native binaries and original model; review schedules are absent from
training. All role-specific native validation, scoring, captures and reanalysis
use the declared schedules, without global configuration swapping.

```sh
# Only after agreeing the fixed replication protocol/budget:
python3 -W error sim/garden_renewal_replication.py --output artifacts/NEW-renewal-replication
# Saved-evidence verification, no native simulation execution:
python3 -W error sim/garden_renewal_replication.py \
  --output artifacts/garden-renewal-replication-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-replication
```

The fixed budget is 1,408 ledger trials, 256 image replays and 72 mutations,
including full capture-disabled repeats and all 128 independently repeated
day-192 screenshots. Original controls must agree across all four searches and
first-generation mutants within each matched pair. Report replicas separately:
their review worlds are shared, not independent environmental observations.
`--verify --export NEW_PREFIX` exports both contact sheets, all PNGs and portable
score/cohort diagnostics; `--verify --check-export EXISTING_PREFIX` validates
them. A failed collection retains partial evidence, with no automatic restart.
The negative replication result does not authorize more search or score tuning.

The [frozen-model transfer diagnostic](../benchmarks/garden-longevity/renewal-transfer.md)
uses `sim/garden_renewal_transfer.py` to complete the world-set × schedule-set
cross for the original and four fixed finalists. TT/RR native histories are
copied from the pinned replication; TR/RT are measured and independently
repeated. Native binaries and model bytes are reused, not rebuilt or trained.

```sh
# Only after agreeing the fixed transfer protocol/budget:
python3 -W error sim/garden_renewal_transfer.py --output artifacts/NEW-renewal-transfer
# Saved-evidence verification, no native simulation execution:
python3 -W error sim/garden_renewal_transfer.py \
  --output artifacts/garden-renewal-transfer-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-transfer
```

Exactly 300 native calls cover 120 new trials plus full repeats and thirty new
image pairs; ten existing image pairs are reused for a fixed forty-frame panel.
All five models use the same first canonical seed of each world set for captures.
Two private model jobs may run concurrently, with no shared simulation/RNG state.
The runner rejects changed model provenance, altered command identities/budget,
nonmatching native JSON repeats, reused scores or image pixels, and changed
source/input hashes. It validates all four cells under both score views and
retains every finalist/original and B/A comparison, cohort and diversity record.
Cross-cell diagnostics use exact per-condition rational means, not unequal raw
sums; seed omissions drop both affected cells' paired schedules. The eight/four
world panels and four schedule seeds support descriptive diagnostics only, not
weather attribution or fresh held-out qualification. `--verify --export NEW_PREFIX`
exports portable data and all forty PNGs; `--verify --check-export EXISTING_PREFIX`
checks metadata, image bytes and the regenerated contact sheet. No native runs
occur during reanalysis/export. A failed collection preserves partial evidence;
it does not authorize extra conditions, restarts, training or model selection.

The [8/16-world bounded-renewal comparison](../benchmarks/garden-longevity/renewal-coverage.md)
uses `sim/garden_renewal_coverage.py`. Both arms use the same existing renewal
selector; narrow controls are complete reused R1/R2 searches, not newly trained
v2 arms. Wide adds eight fixed training seeds, with identical mutation streams,
schedule sets, native binaries and candidate budget. Eight fresh review worlds
evaluate every generation but never select parents. The previously inspected
review schedule seeds remain unchanged.

```sh
# Only after agreeing the fixed coverage protocol/budget:
python3 -W error sim/garden_renewal_coverage.py --output artifacts/NEW-renewal-coverage
# Saved-evidence verification; no native simulation execution:
python3 -W error sim/garden_renewal_coverage.py \
  --output artifacts/garden-renewal-coverage-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-coverage
```

The exact new budget is 2,084 native calls: 1,280 wide training/repeat trials,
256 review trials, 512 frame replays and 36 mutations. Reused narrow evidence
adds 640 histories and 36 mutation records, with no new calls. All 256 review
frames are fixed by generation/world/schedule, including unchanged models.
Two independent replica jobs use private directories and serial native calls.
Verification checks the exact reused histories, shared mutation-prefix model
and original-world bytes, complete capture-disabled wide searches, command
identities/budget, native scores/endpoints, image repeats and regenerated sheets.
Own-training credit means use exact rational denominators; original/added world
subsets and both review score views remain separate. The candidate budget is
matched, not training evaluation compute. `--verify --export NEW_PREFIX` exports
both sheets, all PNGs and portable diagnostics; `--verify --check-export
EXISTING_PREFIX` checks them. No simulation/native/default changes, automatic reruns,
extra search or retrospective review selection follow from this comparison.

The [frozen-finalist return check](../benchmarks/garden-longevity/renewal-return.md)
uses `sim/garden_renewal_return.py` to evaluate both fixed W3 models on the old
transfer cross. Pinned transfer/coverage inputs supply native binaries, model
provenance and all original/N3 controls. No old protocol or runner defaults are
changed and no training/mutations occur.

```sh
# Only after agreeing the fixed return protocol/budget:
python3 -W error sim/garden_renewal_return.py --output artifacts/NEW-renewal-return
# Saved-evidence verification, without native simulation execution:
python3 -W error sim/garden_renewal_return.py \
  --output artifacts/garden-renewal-return-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-return
```

Exactly 224 new calls cover 96 trial/repeat pairs and sixteen image/repeat pairs.
Another 144 outcomes and 24 repeated images are copied from verified controls.
Both independent model jobs stay private. W's original-training subset must
also reproduce saved coverage bytes. Verify both source bundles, final model
identities, equal native binaries/configuration, exact commands/budget, complete
ledger repeats, native scores and all forty endpoint/image/PNG/sheet checks.
Preserve the two score views, every W/N and finalist/original comparison, both
schedules and blocked omissions. Saved coverage review is separate context,
not fresh evidence or pooled with old RR; unequal panels retain exact rational
means. `--verify --export NEW_PREFIX` and `--verify --check-export EXISTING_PREFIX`
export/check the summary and entire gallery without new native calls. Failed
collection preserves evidence without automatic retries, extra conditions,
training or promotion. Record limitations as well as aggregate gains.

The [offline cohort audit](../benchmarks/garden-longevity/renewal-cohorts.md)
uses `sim/garden_renewal_cohorts.py` on the pinned return bundle. It copies forty
old-RR histories and reconstructs all 160 period attributions without native
execution, training, models or new captures. Full original/N/W controls remain
visible alongside six score-selected explanatory labels.

```sh
# Only after agreeing the offline audit scope:
python3 -W error sim/garden_renewal_cohorts.py --output artifacts/NEW-renewal-cohorts
# Saved-evidence verification, without native simulation execution:
python3 -W error sim/garden_renewal_cohorts.py \
  --output artifacts/garden-renewal-cohorts-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-cohorts-summary.json
```

Fresh/carry-in credit separates cohort count, window/age timing and natural/patch
losses. Confirmation and purchase cohorts retain their own periods/follow-up;
species and founder families stay distinct. Exact minimum-switch witnesses
prevent comparing different periods as though they were the same one. Daily
censuses and species loss/recovery events are ledger reconstructions, not native
screenshots; pending seeds distinguish temporary living absence from extinction.
Verify copied hashes, original scores/cohorts, repeated audit output and portable
JSON. `--verify --export NEW_FILE.json` writes that summary. No native binaries
are copied or invoked. Accounting does not identify physical causes of natural
deaths or seed expiry, and the result does not authorize new diagnostic replays,
training, score changes or model promotion.

The [eight-day startup diagnostic](../benchmarks/garden-longevity/renewal-startup.md)
uses `sim/garden_renewal_startup.py` with original and R2 N/W on fixed world
`0d983a80`. The return/stall bundles supply hash-pinned models, inspector, replayer,
native source and matching build configuration; no native rebuild is performed.

```sh
# Only after agreeing the fixed startup protocol/budget:
python3 -W error sim/garden_renewal_startup.py --output artifacts/NEW-renewal-startup
# Offline verification and portable summary/native-sheet check:
python3 -W error sim/garden_renewal_startup.py \
  --output artifacts/garden-renewal-startup-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-startup
```

The collector makes exactly six full ecology traces and 24 frame replays,
including all repeats. Live resource/leaf/tip accounting, actual committed bids,
all births/deaths and old startup hashes must reconcile. Terminal income is
cleared by the engine and remains explicitly unaccounted; later saved deaths
are censored at the short horizon. Only identical reset founders, not descendant
IDs, are paired across models. Fixed images are days 0.25, 0.75, 2 and 8. The
first scheduled patch is later, at day 16; no new ecology or policy is tested.

`--verify --export NEW_PREFIX` writes the portable JSON and native contact sheet.
Capture outputs are sealed before analysis. If analysis fails after a complete
capture, `--finish-captured` can finish that output **offline** after validating
the sealed inputs/results and saving a separate revised analysis source snapshot;
it never silently reruns simulation calls or overwrites completed results.
The first bundle used that path to correct an expectation of a world-level policy
name: this inspector carries its night-veto identity in bid records instead.
Its original error/source and capture bytes remain recorded. Native timing was
unavailable after that initial exception and is explicitly null, not estimated.

### Reciprocal founder-controller diagnostic

The [reciprocal swap](../benchmarks/garden-longevity/renewal-swap.md) uses a small
host-only adapter in the inspector and native replayer. Both accept
`--focal-model MODEL --focal-founder ID` together, only with
`neural-no-night-growth`. The founder must exist alive at reset; routing follows
its stable lineage ID through compaction, and all descendants retain the
background model. No new neural observations or firmware code are introduced.
Other growth overrides, bootstrap, gap and founder-exit interventions cannot
be combined with it. Shared leaf policy and arbitration must match.

`sim/garden_renewal_swap.py` fixes two saved models, one founder/world and four
eight-day cases. It seals forty native calls (including all repeats) before
analysis, verifies every selected controller CRC, and requires the two
self-routing controls to match every old trace record and saved frame after
removing only declared routing metadata. Resource/leaf/tip audits are reused
from the startup diagnostic. No trainer or mutation executable is called.

The matching separate build is `artifacts/build-host-renewal-swap`, configured
with RelWithDebInfo, `CMAKE_C_FLAGS_RELWITHDEBINFO=-O2 -g`, UBSan, wide dispersal,
headroom uptake, combined experiment, large pool and leaf maintenance enabled;
player, profiling, bottom drainage, large seed bank and seed reserve are off.
Build this through the existing Docker service, not new host dependencies.
The collector rejects any mismatch with the pinned baseline build settings.

```sh
# Only after agreeing the fixed protocol and building the matching tools:
docker compose run --rm firmware python3 -W error sim/garden_renewal_swap.py \
  --build artifacts/build-host-renewal-swap --output artifacts/NEW-renewal-swap
# Offline verification and portable summary/native sheet check; no native calls:
python3 -W error sim/garden_renewal_swap.py \
  --output artifacts/garden-renewal-swap-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-swap
```

`--verify --export NEW_PREFIX` writes the portable JSON and contact sheet. Failed
collections are retained and never automatically rerun or overwritten. This
case-specific swap is not a general mixed-population trainer or controller
inheritance scheme. Any neighbor effect includes ordinary ecological feedback
and shared-world arbitration; it does not by itself identify shading or prove
cooperation.

### Single-neighbor follow-up

The [one-neighbor diagnostic](../benchmarks/garden-longevity/renewal-neighbors.md)
keeps observed shrub 2 on N and switches founders 1, 3, 4 or 5 individually to W.
`sim/garden_renewal_neighbors.py` copies the hash-pinned prior executables/models
and reuses their existing founder router: no native rebuild is needed. All new
descendants remain N. N/N and N/W are copied references, not reruns; the latter
also controls descendants with W and is not a factorial all-four-founder endpoint.

```sh
# Only after agreeing the fixed protocol; forty new native calls, no training:
docker compose run --rm firmware python3 -W error sim/garden_renewal_neighbors.py \
  --output artifacts/NEW-renewal-neighbors
# Offline reanalysis and portable data/native image check:
python3 -W error sim/garden_renewal_neighbors.py \
  --output artifacts/garden-renewal-neighbors-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-neighbors
```

The collector retains focal seed-purchase events and compares resource/body
differences and physical tip winners against N/N. It separately identifies equal
recorded bid multisets with differing tied winners, excluding only global tip
indices and declared routing CRC. Changed inputs, priorities or candidate data
cannot be hidden to make an event look order-only. These records do not expose
all neural inputs/private-memory proposals; they are not a tie-policy intervention.
Shared resource/leaf/tip reconciliation, capture sealing, exact repeats, native
source hash equality, copied-reference identity and framebuffer checks remain
mandatory. The six-column sheet includes four new cases and two references.
`--verify --export NEW_PREFIX` writes portable data and the native sheet without
rerunning simulations. Failed output is retained, never silently overwritten.

### Fourth-seed counterfactual

The [scoped seed-veto diagnostic](../benchmarks/garden-longevity/renewal-seed-veto.md)
uses the same far-right-flower swap. A separate host build with
`TOY_FACTORY_GARDEN_FOCAL_SEED_VETO=ON` suppresses founder 2's fourth and subsequent
otherwise-eligible purchases only during logic ticks `[2880, 4800)`. It uses
existing dawn-reset spent-flower flags, not a new world-state counter. Other
parents/descendants/days and normal eligibility checks are unaffected directly;
ordinary downstream seed-bank and ecological feedback remains enabled.

The option requires undrained 512-node leaf-maintenance ecology with the ordinary
eight-seed bank and no sunset-reserve gate. It is rejected for firmware and OFF
by default; `make host-build` explicitly clears it. This is a diagnostic build,
not a qualified player/training environment. Census and replay output identify
`founder-2-second-day-three-seeds-v1`.

`sim/garden_renewal_seed_veto.py` takes `--control-build` and `--veto-build`, defaulting
to `artifacts/build-host-renewal-seed-{control,veto}`. Both use the pinned prior
ecology configuration and assertion-enabled `RelWithDebInfo` / `-O2 -g`, with
UBSan, differing only in that new option. The frozen bundle retains both CMake
caches and build command graphs. Its twenty-call panel captures two eight-day
cases twice, plus repeated frames at ticks 4,800, 6,720, 7,680 and 30,720.

```sh
# New collection only after agreeing its fixed protocol and building both tools:
docker compose run --rm firmware python3 -W error sim/garden_renewal_seed_veto.py \
  --output artifacts/NEW-renewal-seed-veto
# Offline verification; does not execute either native tool:
python3 -W error sim/garden_renewal_seed_veto.py \
  --output artifacts/garden-renewal-seed-veto-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-seed-veto
```

The verifier requires the complete OFF trace to reproduce the pinned prior trace,
and ON to match until the exact fourth purchase, ignoring only declared veto
metadata. It checks the initial 48-energy/24-water debit difference, three versus
four purchases, model routing, ordinary resource/decision accounting and every
native frame/repeat. `--verify --export NEW_PREFIX` exports portable JSON and the
contact sheet. A failed bundle is retained without automatic reruns or overwrites.

### Offline seed-forecast audit

The [saved-purchase audit](../benchmarks/garden-longevity/renewal-seed-forecast.md)
reuses the existing sunset-reserve reference at two already observed purchases.
It never launches native worlds. `sim/garden_renewal_seed_forecast.py` pins the
prior seed-veto manifest, verifies its entire capture and the relevant frozen
source hashes, and repeats the calculation exactly.

```sh
python3 -W error sim/garden_renewal_seed_forecast.py \
  --check benchmarks/garden-longevity/renewal-seed-forecast-summary.json
# Optional fresh export; no overwrite or writes inside the frozen input bundle:
python3 -W error sim/garden_renewal_seed_forecast.py --output artifacts/NEW-forecast.json
```

The ledger reconstructs actual pre-seed energy without double-counting current
income/upkeep, separates predicted income from paid/required maintenance and
other costs, and stops accounting on cleared death steps. Nominal night and dawn
recovery remain separate windows. A fixed-body storage bound counts payments in
the observed sub-64-light interval; it is not a claim that deceased plants paid
later upkeep. No-purchase traces are contextual observations, not independent
gate-enabled rollouts. The analysis does not change or promote a forecast or gate.

### Phase-aware saved-purchase forecast

The [fixed phase-aware audit](../benchmarks/garden-longevity/renewal-phase-forecast.md)
uses all 112 purchases from those same two traces. One predeclared predictor scales
the current income by future/current integer sunlight tier, holds the body fixed,
assumes no further optional spending and adequate water, and follows energy/stress
through the next dawn to noon. It is an offline diagnostic, not a runtime gate.
Zero-light anchors are unsupported rather than assigned an invented rate.

```sh
python3 -W error sim/garden_renewal_phase_forecast.py \
  --check benchmarks/garden-longevity/renewal-phase-forecast-summary.json
# Fresh export only; does not launch native tools or overwrite old evidence:
python3 -W error sim/garden_renewal_phase_forecast.py --output artifacts/NEW-phase-forecast.json
```

The auditor pins and re-verifies the earlier audit and original capture. Every
purchase retains its projected/actual endpoints, signed/absolute errors, exact
worst-error samples, first assumption break, budget and death/censoring status.
Aggregate results separate all observed live samples from the prefix strictly
before later spending/body changes/water shortage. Follow-up windows overlap;
death-labelled purchases and actual case-specific parent deaths are counted
separately. Projected death is absorbing, while potential income after that point
is explicitly diagnostic rather than credited. No terminal income is inferred
from cleared native telemetry, and right-censored follow-ups are not survivors.

### Exact guaranteed-dark spending budget

The [dark-budget audit](../benchmarks/garden-longevity/renewal-dark-budget.md)
reuses the same traces without extrapolating daylight income. It inventories
every accepted expense, reconstructs growth/renewal-before-seed stage ordering,
and projects only when the immediately following steps have guaranteed zero
energy income. A separate panel checks every living plant at every phase-117
evening census. The first possibly productive step is excluded.

```sh
python3 -W error sim/garden_renewal_dark_budget.py \
  --check benchmarks/garden-longevity/renewal-dark-budget-summary.json
# Fresh portable export only; no native tools, overwrite or firmware changes:
python3 -W error sim/garden_renewal_dark_budget.py --output artifacts/NEW-dark-budget.json
```

The pure budget retains existing stress, recovery on full payment and death at
eight. It allows transient shortages and assumes sufficient water and no further
optional spending or energy-upkeep changes. The report keeps each expense's
pre/post arithmetic separate from actual end-of-step follow-up; it cannot prove
that refusing the expense rescues the plant. Daylight anchors without an immediate
zero-income horizon are out-of-scope, never implicit approvals. Comparisons check
exact agreement before later expenses, changed upkeep or water shortage, and
retain explicit death/censoring status. Neither newborn expenses nor coincident
growth/renewal-plus-seed steps are dropped from the full inventory. No new native
calls or runtime gate are part of this tool.

### Host-only exact dark spending guard

The [fixed native comparison](../benchmarks/garden-longevity/renewal-dark-guard.md)
adds `TOY_FACTORY_GARDEN_DARK_GUARD=ON` only to an explicit undrained 512-node
leaf-maintenance build, with the ordinary eight-seed bank and no seed-reserve
gate or focal quota. It is OFF by default and forbidden in firmware. Default
host build, player and profile scripts explicitly clear it. The rule checks
eligible growth/finish, renewal and seed expenses in native order, projecting
only through the immediately following guaranteed-zero-income interval. It
allows survivable shortages and leaves unsupported daylight decisions unchanged.

`sim/garden_renewal_dark_guard.py` freezes the agreed two-arm, twenty-call panel.
Its default build directories are
`artifacts/build-host-renewal-dark-{control,guard}-docker`, using the existing
Docker compiler, `RelWithDebInfo` / `-O2 -g`, assertions and UBSan. The complete
CMake caches/build graphs are retained in the bundle. All ecology options match
the prior seed-veto **control**, with only the new guard option differing.
The earlier focal veto is not active in either arm.

```sh
# After building both binaries and agreeing a fresh fixed capture:
python3 -W error sim/garden_renewal_dark_guard.py \
  --output artifacts/NEW-renewal-dark-guard
# Offline verification/export check: no native calls or new training:
python3 -W error sim/garden_renewal_dark_guard.py \
  --output artifacts/garden-renewal-dark-guard-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-dark-guard
```

The inspector retains bounded candidate events with pre/post body, stores,
forecast, expense kind and decision. Diagnostics do not enter the authoritative
hash. Every native forecast is checked against the independent dark-budget
reference. Rejected winning bids remain in the raw trace, but are removed from
an explicit derived stream after their non-commitment has been checked, allowing
the existing live resource/leaf/tip reconciler to audit actual actions. The tool
also checks the complete frozen control, exact first divergence, all repeats
and native framebuffer/census agreement. Failed bundles are retained without
automatic reruns or overwrites; `--verify --export NEW_PREFIX` creates the
portable summary and contact sheet. Survival and reproduction outcomes remain
separate, with no automatic fitness or firmware promotion.

### Frozen longer dark-guard panel

The [64-day follow-up](../benchmarks/garden-longevity/renewal-dark-panel.md) copies
those exact binaries/models into a separate fixed four-world comparison, paired
with and without the existing patch schedule. It does not rebuild or change C.
`sim/garden_renewal_dark_panel.py` captures 16 trajectories twice, with repeated
frames at days 8/32/64: exactly 128 experimental native calls. The
[protocol](../benchmarks/garden-longevity/renewal-dark-panel-protocol.md) fixes the
review seeds, focal routing, late window and measures before collection.

```sh
# Only after agreeing a fresh capture; existing evidence cannot be overwritten:
python3 -W error sim/garden_renewal_dark_panel.py \
  --output artifacts/NEW-renewal-dark-panel
# Offline verification/export check: no native calls or training:
python3 -W error sim/garden_renewal_dark_panel.py \
  --output artifacts/garden-renewal-dark-panel-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-dark-panel
```

The raw trace keeps ordinary pre-patch, event and post-patch records. Offline
accounting validates each boundary, charges patch losses separately, and carries
the post-event state forward without counting the same guard decisions twice.
Independent resource/tip/lifetime checks agree. Derived accounting traces omit
only rejected, uncommitted growth bids; no census or leaf proposal is rewritten.
Natural terminal-step income remains explicitly unreconstructed.

Daily populations, complete lineages, eligible/recent offspring cohorts, durable
parents, descendant seed production and tipless/capacity exposure are retained.
Events use `(start, stop]`; exposure integrates post-event states on `[start, stop)`.
Both conditions must reproduce the old selected world's full eight-day history
and match one another through the ordinary day-16 step before patch mortality.
`--verify --export NEW_PREFIX` creates the portable JSON, both fixed contact
sheets and all 48 native PNGs; the export is itself checked against the bundle.
Repeated capture/analysis proves reproducibility, not independent generalization
or permission to promote the rule. Failed captures remain intact without reruns.

### Residual guarded-death audit

The [mortality audit](../benchmarks/garden-longevity/renewal-dark-failures.md)
consumes only that frozen panel. It preserves all sixteen trajectories and
checks every living phase-117 state plus newborns inside a dark interval, not
only states belonging to later deaths. Follow-up separates exact survival/death,
changed assumptions and patch/trace censoring. Natural deaths are classified
inside/after the latest covered window or before any anchor, with explicit
energy/water flags and unreconstructed terminal budgets.

```sh
python3 -W error sim/garden_renewal_dark_failures.py \
  --check benchmarks/garden-longevity/renewal-dark-failures-summary.json
# Fresh portable export only; no native simulations or overwrite:
python3 -W error sim/garden_renewal_dark_failures.py \
  --output artifacts/NEW-renewal-dark-failures.json
```

Every guarded death retains lifetime resource totals and a fixed two-day
lookback, with exact accepted expense stages, body changes, stress/light
checkpoints and actual income after possible dawn. Storage-cap/minimum-energy
calculations hold the observed body/stress fixed; they are not policy proposals
or proven veto rescues. Denials retain individual events and same-case lifetime
outcomes, with repeated attempts distinguished from distinct plants.
The tool re-verifies parent evidence, requires unchanged native sources, records
analysis-source hashes and repeats its analysis. It never modifies the frozen
bundle or calls native executables. The complete portable JSON includes all
anchors; shared cycles and pre-patch histories are not independent replicates.

### Two fixed one-shot purchase counterfactuals

The [purchase-veto protocol](../benchmarks/garden-longevity/renewal-purchase-veto-protocol.md)
uses one saved adverse world, a byte-identical rebuilt guarded control and two
independent interventions. `TOY_FACTORY_GARDEN_PURCHASE_VETO=ON` requires the
ordinary host dark-guard build; it is OFF in all default host build scripts and
forbidden in firmware. Inspect/replay accept `--purchase-veto extension|finish`.
The fixed lineage/tick/tip/action/resources must match exactly; a wrong, absent
or duplicate receipt fails. Normal later retries are intentionally permitted.
The hook cannot change the ordinary guard's forecasts or denial counters.

```sh
# After building the opt-in host target, use a fresh output for collection:
python3 -W error sim/garden_renewal_purchase_veto.py \
  --build artifacts/build-host-purchase-veto-docker \
  --output artifacts/NEW-renewal-purchase-veto

# No native calls during verification or portable-export checks:
python3 -W error sim/garden_renewal_purchase_veto.py \
  --output artifacts/garden-renewal-purchase-veto-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-purchase-veto
```

The 24-call budget includes full repeated 64-day traces and repeated native
frames at days 19/32/64 for all three arms. Results reconcile control/prefixes,
forced versus ordinary denials, resources, tips, leaf/stress budgets, patch
boundaries and all lineage/cohort outcomes. Full target histories stay in the
frozen bundle; the compact portable export retains selected receipts plus
complete whole-world/lineage results and records the exporter fingerprint.
See the [report](../benchmarks/garden-longevity/renewal-purchase-veto.md) for both
the extension rescue and adverse species/exposure effects. This does not
qualify a general rule or change the training objective.

### Retry-aware FINISH handoff

The [follow-up protocol](../benchmarks/garden-longevity/renewal-finish-retry-protocol.md)
adds `--purchase-veto finish-retry` to the same opt-in host build. It refuses
exactly the two known lineage-22 FINISH receipts at 69,885 and 69,900, then
leaves the ordinary guard in charge from 69,915 onward. The second refusal
must follow the first and match its expected resources/tip/action; missing,
wrong or repeated receipts fail. Private state is not advanced and alternative
bids are not selected. The diagnostic does not extend the guard's horizon.

```sh
# After building the opt-in host target, collect only into a fresh directory:
python3 -W error sim/garden_renewal_finish_retry.py \
  --build artifacts/build-host-finish-retry-docker \
  --output artifacts/NEW-renewal-finish-retry

# No native calls during verification or portable-export checks:
python3 -W error sim/garden_renewal_finish_retry.py \
  --output artifacts/garden-renewal-finish-retry-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-finish-retry
```

The fixed 24 calls cover control, one-shot FINISH and retry-aware FINISH through
64 days, with full repeated traces and repeated days-19/32/64 framebuffers.
Both rebuilt references must match the previous bundle byte-for-byte. Two
separate raw-prefix comparisons isolate each intervention, followed by exact
handoff, accounting, lineage/cohort and frame checks. Forced refusals retain
ordinary guard-allowed metadata but are not counted as paid purchases. See the
[report](../benchmarks/garden-longevity/renewal-finish-retry.md) for the durable
target rescue and adverse whole-garden mortality/species results.

### Saved-trace recruitment and first-night audit

The [recruitment protocol](../benchmarks/garden-longevity/renewal-recruitment-protocol.md)
reuses the frozen control/retry pair without native execution. It reconstructs
seed identity from parent/creation tick, ordered bank removal/append semantics,
fixed dormancy/expiry, newborn ancestry and per-step purchase/expiry counters.
Conflicting transitions fail; post-step blocker observations are not claimed
to be pre-germination decision conditions. Every seed and offspring remains in
the portable output, with full-day censoring and separate founder/pre/post
intervention mortality. Natural terminal budgets remain unknown.

```sh
python3 -W error sim/garden_renewal_recruitment.py \
  --check benchmarks/garden-longevity/renewal-recruitment-summary.json

# Fresh output only; no overwrite or new experimental native runs:
python3 -W error sim/garden_renewal_recruitment.py \
  --output artifacts/NEW-renewal-recruitment.json
```

The tool re-verifies the entire parent, unchanged native source, repeated
analysis, input hashes and analysis-source fingerprints. See the
[report](../benchmarks/garden-longevity/renewal-recruitment.md) for the split
between more births, first-night energy failures and shrub-site occupancy.

### Full-night body-capacity shadow audit

The [capacity protocol](../benchmarks/garden-longevity/renewal-night-capacity-protocol.md)
asks a narrower question than survival prediction: could this fixed body survive
the entire guaranteed-zero-income interval starting at full energy and zero
stress? The canonical phase-117 anchor includes 37 upkeep payments; at most
seven can go unpaid. The exact reference and an independent closed-form check
agree across all 512 legal body sizes. This does not use estimated morning
income, current reserves, or future observed outcomes to classify a proposal.

```sh
python3 -W error sim/garden_renewal_night_capacity.py \
  --check benchmarks/garden-longevity/renewal-night-capacity-summary.json

# Fresh output only; both saved bundles remain read-only:
python3 -W error sim/garden_renewal_night_capacity.py \
  --output artifacts/NEW-renewal-night-capacity.json
```

Both commands fully verify the frozen 16-trajectory panel and retry bundle,
then repeat the new analysis and check source/input fingerprints. The retry
case is supplemental, not a seventeenth independent world. Paid node-adding
extensions share a denominator; already-denied selected proposals and their
retries are separate. FINISH and blocked extensions are excluded. The portable
result retains all lineages, flagged and unflagged deaths, endpoint/patch
censoring, and first-full-night follow-up. No guard is enforced and no new
experimental native replay, screenshot, training run or firmware change occurs.

### Full-night growth-guard A/B

The [enforcement protocol](../benchmarks/garden-longevity/renewal-capacity-guard-protocol.md)
is a separate fixed four-world comparison, not an extension of the FINISH
veto. Build both arms with the ordinary dark guard, selective leaf maintenance,
512 nodes, wide dispersal and water headroom; leave purchase vetoes, drainage,
large seed bank, seed reserve and focal seed veto OFF. Use GCC's
`RelWithDebInfo`, `-O2 -g`, and UBSan in both builds. Only the treatment sets
`TOY_FACTORY_GARDEN_NIGHT_CAPACITY=ON`; it requires the ordinary guard and is
forbidden in Zephyr or alongside purchase vetoes. All ordinary host build
scripts explicitly reset the new option OFF.

```sh
# Fresh output; builds and the frozen panel must already exist.
docker compose run --rm firmware python3 -W error sim/garden_renewal_capacity_guard.py \
  --control-build artifacts/build-host-capacity-control-docker \
  --capacity-build artifacts/build-host-capacity-guard-docker \
  --output artifacts/NEW-renewal-capacity-guard

# Saved evidence verification; does not run the native binaries again.
docker compose run --rm firmware python3 -W error sim/garden_renewal_capacity_guard.py \
  --output artifacts/garden-renewal-capacity-guard-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-capacity-guard
```

Collection makes exactly 64 native calls, repeats complete traces and all
day-12/40/64 images, and stops on reference drift. The rebuilt control must
reproduce the prior panel guard byte-for-byte. Treatment prefixes isolate the
three declared first crossings; the fourth world's behavior must never change.
Separate capacity receipts identify ordinary-allowed node additions that are
subsequently refused. The accounting adapter validates those receipts before
removing uncommitted bids, without changing ordinary-guard denial counters or
inventing a payment. Source/build/input hashes and repeated analysis are frozen.

The [results](../benchmarks/garden-longevity/renewal-capacity-guard.md) retain
all refusals and target actions, natural/patch outcomes, full-night follow-up,
whole/closing cohorts and exposure, species sets, and 24 native screenshots.
Use `--verify --export PREFIX` for a fresh portable JSON/PNG export and
`--verify --check-export PREFIX` to recheck it. No training, device deployment
or default promotion is part of this diagnostic.

### Rescued-parent seed audit

The [saved-trace protocol](../benchmarks/garden-longevity/renewal-rescued-seeds-protocol.md)
follows the two rescued parents in both capacity-comparison arms. It reconstructs
every seed in all four traces, then reports the target seeds' destinations,
expiry/censoring, per-column masks and whole/since-refusal/closing exposure.
The original ordered seed ledger remains unchanged; no native binaries run.

```sh
# Fresh analysis output, outside the frozen parent bundle.
docker compose run --rm firmware python3 -W error sim/garden_renewal_rescued_seeds.py \
  --output artifacts/NEW-renewal-rescued-seeds.json

# Full saved-input verification and exact repeated portable comparison.
docker compose run --rm firmware python3 -W error sim/garden_renewal_rescued_seeds.py \
  --check benchmarks/garden-longevity/renewal-rescued-seeds-summary.json
```

Both commands require the local `artifacts/garden-renewal-capacity-guard-v1`
bundle and its portable export. They pin both hashes, re-verify all eight
parent cases and fixed frames, analyze the four selected traces twice and
reject changed source/input evidence. No new experimental native calls,
screenshots, training or device deployment are part of this audit.

The [results](../benchmarks/garden-longevity/renewal-rescued-seeds.md) distinguish
post-step masks from stable spacing witnesses: an occupant born before the
step, present afterward and within the exclusion distance existed throughout
the seed-check loop. Same-step newborns are excluded; dead unreclaimed plants
would still count. An absent witness does not prove a free site. Light and
moisture remain post-step readings, overlapping observations are not independent
attempts, and pending seeds are censored rather than failed. Per-case IDs and
source fingerprints accompany the complete portable seed histories.

### Controlled named-gap recruitment comparison

The [fixed protocol](../benchmarks/garden-longevity/renewal-controlled-gap-protocol.md)
uses the unpatched `0d983a80` capacity-guard world, with one host-only export of
founder flower 1 after tick 46,080. The existing `--gap-at TICK` retains its
largest-adult behavior; adding **`--gap-lineage ID`** selects exactly that living,
at-least-one-day-old lineage. There is no fallback target. Missing/invalid IDs,
young/dead plants, duplicate options, non-ecology boundaries and incompatible
disturbance/override combinations fail. The named operation supports existing
focal-founder routing, which uses stable IDs rather than compacted plant slots.

Build both arms from one host configuration with the same flags as the capacity
guard treatment above, including `TOY_FACTORY_GARDEN_NIGHT_CAPACITY=ON`, the
ordinary dark guard, `RelWithDebInfo` / `-O2 -g`, and UBSan. Keep all production
simulation files, models, spacing, seed lifetime, dispersal and water rules
unchanged. The normal host/device build defaults are not promoted.

```sh
# Fresh output; frozen capacity bundle and experimental build must exist.
docker compose run --rm firmware python3 -W error sim/garden_renewal_controlled_gap.py \
  --build artifacts/build-host-controlled-gap-docker \
  --output artifacts/NEW-renewal-controlled-gap

# Re-verify saved captures and their portable export; no new native calls.
docker compose run --rm firmware python3 -W error sim/garden_renewal_controlled_gap.py \
  --output artifacts/garden-renewal-controlled-gap-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-controlled-gap
```

Collection makes exactly 24 calls: repeated world/bid and aged-seed/site traces
for both arms, plus repeated frames at days 12, 13, 16 and 64. The control must
match the prior trace before treatment capture. Both pre-export prefixes and
immediate export triples are checked, followed by guard/resource accounting,
ordered seed reconstruction cross-checked against explicit native ages, and
offspring follow-up with endpoint censoring. Use `--verify --export PREFIX` for
a fresh portable JSON/PNG export.

The [results](../benchmarks/garden-longevity/renewal-controlled-gap.md) distinguish
export from natural death, pending seeds from failures, the rescued parent's
offspring from competing families, and post-step site masks from actual
decision-stage gates. Post-export exposure uses the after-state without aging
the seed bank twice. The old patch-only species-event output is not reused for
this export; post-export daily population samples provide that context. No
training, permanent turnover rule, device deployment or automatic commit is
part of the comparison.

### Exact germination checks after the named gap

The [fixed trace protocol](../benchmarks/garden-longevity/renewal-germination-trace-protocol.md)
reuses the controlled-gap trajectories and native seed-loop observer. The host
`toy-factory-garden-seed-attempts` CLI retains its original positional arguments:

```text
MODEL RAINFED_SCENARIO POLICY WORLD_SEED SCHEDULE_OR_ZERO FROM_TICK END_TICK
```

It also accepts paired `--focal-model MODEL --focal-founder ID` and paired
`--gap-at TICK --gap-lineage ID`. This original diagnostic placed the named
export strictly **before** `FROM_TICK`, so its origin already includes the
intervention. The subsequent wet-germination extension below also supports
in-window exports with explicit boundary snapshots; those are not extra ecology
steps. Exports must be ecology boundaries no later than `END_TICK`. There is no
largest-adult fallback. Focal routing requires `neural-no-night-growth`; neither
focal routing nor an export can be combined with a recurring disturbance schedule.
Malformed, duplicate, unpaired, missing/invalid lineage and boundary requests fail.
Without these flags the previous trace/header behavior is unchanged.

The runner fixes the origin/end at 49,545/57,360 and makes exactly four native
calls, control and gap each repeated. It compares every checkpoint to both saved
world and site traces and uses the existing sequential audit validator for all
seeds, not just the three declared focal seeds. Expiry visits are not resource
checks; a post-germination site's new spacing mask is not a failed check.

Use the same Docker experimental configuration as the controlled gap, including
both guards and UBSan. No production build defaults or models change.

```sh
# Fresh output; the frozen controlled-gap bundle must exist.
docker compose run --rm firmware python3 -W error sim/garden_renewal_germination_trace.py \
  --build artifacts/build-host-germination-trace-docker \
  --output artifacts/NEW-renewal-germination-trace

# Verify saved receipts and portable data without new native calls.
docker compose run --rm firmware python3 -W error sim/garden_renewal_germination_trace.py \
  --output artifacts/garden-renewal-germination-trace-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-germination-trace-summary.json
```

`--verify --export FILE.json` writes a fresh portable export. The
[results](../benchmarks/garden-longevity/renewal-germination-trace.md) retain all
520 focal visits, actual gate histograms, raw light/water, sampled resource
windows, post-step differences, whole-bank accounting and source/input/build
provenance. The prior genuine screenshots remain the visual context. This trace
does not implement the proposed germination-light experiment or deploy firmware.

### Post-gap wet-germination A/B

The [fixed protocol](../benchmarks/garden-longevity/renewal-wet-germination-protocol.md)
compares the identical named-gap world with/without the immediate light gate,
activated only after the day-12 export. Both arms share one experimental binary.
Configure the prior night-capacity build with
`-DTOY_FACTORY_GARDEN_WET_GERMINATION=ON`; all other cache options must match.
It requires `TOY_FACTORY_GARDEN_NIGHT_CAPACITY=ON` and its existing prerequisite
chain. Firmware compilation is rejected. Normal host/player/profile build
scripts explicitly set the option OFF, including when reusing a CMake cache.

In this build, `inspect`, `replay` and `seed-attempts` accept
`--wet-germination-after TICK`, which must match an explicit
`--gap-at TICK --gap-lineage ID`. It cannot be supplied alone or combined with a
recurring disturbance. Omitting it retains the previous rule and hash/output
identity. The authoritative world flag starts false, enables once at an ecology
boundary with the gardener off, and changes only seed eligibility's LIGHT gate.
Raw light, photosynthesis and initial seedling resources do not change.

World/site and seed-attempt traces explicitly bracket the named export and
`germination-rule` activation with same-tick snapshots. In-window seed boundaries
have empty stage/site/attempt arrays, not a second step or second seed aging.
For events before the trace origin, the event is emitted but no out-of-window
snapshot is inserted. Active records carry `germination_rule: wet-germination-v1`;
the seed validator must explicitly select optional-light checking after auditing
that boundary. Its default interpretation remains light-required.

```sh
# Fresh output; both frozen parent bundles and the opt-in build must exist.
docker compose run --rm firmware python3 -W error sim/garden_renewal_wet_germination.py \
  --build artifacts/build-host-wet-germination-docker \
  --output artifacts/NEW-renewal-wet-germination

# Verify saved native data, outcomes and images without new native calls.
docker compose run --rm firmware python3 -W error sim/garden_renewal_wet_germination.py \
  --output artifacts/garden-renewal-wet-germination-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-wet-germination
```

`--verify --export PREFIX` creates a fresh `PREFIX-summary.json`,
`PREFIX-frames/` and `PREFIX.png`. The runner enforces 28 fixed calls, exact
control/repeat/prefix parity, activation isolation, complete ordered seed checks,
all first-day recruit outcomes, guard/resource/lineage accounting, occupancy,
and the four predeclared frame checkpoints. The
[result](../benchmarks/garden-longevity/renewal-wet-germination.md) is more
germination with four additional energy deaths, not sustained renewal. No
automatic promotion, parameter sweep, training or deployment follows.

### Saved-trace post-gap seedling budgets

The [offline protocol](../benchmarks/garden-longevity/renewal-seedling-budget-protocol.md)
selects every post-gap recruit in the frozen wet-germination pair, not just
failures: required child 10 and optional children 10–14. The analyzer verifies
the parent bundle and portable data, then checks focal resource/stress/leaf
histories through day 64. Detailed comparisons stop at three age-based days or
death, whichever comes first.

```sh
docker compose run --rm firmware python3 -W error sim/garden_renewal_seedling_budget.py \
  --output artifacts/NEW-seedling-budget.json

docker compose run --rm firmware python3 -W error sim/garden_renewal_seedling_budget.py \
  --check benchmarks/garden-longevity/renewal-seedling-budget-summary.json
```

No native binaries execute during this analysis. The export includes complete
focal steps, both resource ledgers, old-body upkeep demand versus paid cost,
paid stages, native refusals, per-day totals, stress/recovery episodes and
exact-dark forecasts with assumption breaks and censoring. Cleared terminal
income/payments are not reconstructed. Actual dawn income is kept distinct from
globally possible income. The [result](../benchmarks/garden-longevity/renewal-seedling-budget.md)
separates zero-income startup deaths from larger plants that survive the dark
forecast horizon but fail the following dawn payment. No counterfactual or
general spending change is included.

### One FINISH deferred through dawn

The [fixed protocol](../benchmarks/garden-longevity/renewal-dawn-finish-protocol.md)
adds only `TOY_FACTORY_GARDEN_DAWN_FINISH=ON` to the wet-germination build.
It requires that host-only experiment and is off in normal container builders;
the header rejects firmware use. Inspector/replayer accept `--dawn-finish defer`
only with the fixed named-gap/wet/focal-founder/maintenance setup. Omitting the
option preserves old output and hashes. Diagnostics are world-owned, reset to
zero and excluded from the world hash, like the existing purchase-veto audit.

The new hook runs after ordinary dark and structural guard approval, before
private policy state or an expense commits. The first receipt must exactly
match lineage 12's FINISH at 66,090. Retries must identify the same root position
and depth; node-array compaction may change its index. The window includes
68,340, and 68,355 releases to normal policy. Invalid/missing target receipts
abort rather than selecting another transaction. This is not a runtime-general
spending controller.

```sh
docker compose run --rm firmware python3 -W error sim/garden_renewal_dawn_finish.py \
  --build artifacts/build-host-dawn-finish-docker \
  --output artifacts/NEW-dawn-finish

docker compose run --rm firmware python3 -W error sim/garden_renewal_dawn_finish.py \
  --output artifacts/garden-renewal-dawn-finish-v1-analysis-v2 --verify \
  --check-export benchmarks/garden-longevity/renewal-dawn-finish
```

Exactly 24 calls capture each arm's world/bid and aged-seed/site streams twice
plus four fixed native frames twice. The collector freezes dirty sources,
inputs and binaries, checks control against the old capture before treatment,
and reconciles all costs and lifetimes. `--finish` is analysis-only recovery of
a completed capture, with analysis-source fingerprints; it verifies existing
derived censuses before reusing them and never reruns native observations.
An analysis-only tooling revision preserves the original sealed bundle while
producing byte-identical results in the documented `analysis-v2` directory.
Native capture failures retain partial evidence and a
`capture-failure.json`; no sealed manifest is produced. Verification never
executes captured binaries. No separate seed-attempt-order trace is added here.
The [result](../benchmarks/garden-longevity/renewal-dawn-finish.md) is a one-second
death delay, not a lasting rescue; normal payment after release exhausts stores
just before upkeep. A reserve-aware handoff remains a proposal, not an adoption.

### Reserve-aware handoff of the same FINISH

The [three-arm protocol](../benchmarks/garden-longevity/renewal-dawn-reserve-protocol.md)
extends the existing host-only diagnostic with `--dawn-finish reserve`. Its
old deferral is identical through tick 68,340. From 68,355 until 69,120 exclusive,
the selected FINISH commits only if current energy covers cost eight plus one
eight-energy upkeep bill. Equality permits. A successful handoff records its
pre-spend tick, node and energy; the ordinary transaction still commits and pays.
Without a handoff, the check stops at noon anyway. Other plants, actions,
ordinary guard precedence, physics and firmware are unchanged.

```sh
# Use the same CMake options/compiler flags as the dawn-FINISH experiment.
docker compose run --rm --no-deps firmware python3 -W error sim/garden_renewal_dawn_reserve.py \
  --build artifacts/build-host-dawn-reserve-docker \
  --output artifacts/NEW-dawn-reserve

docker compose run --rm --no-deps firmware python3 -W error sim/garden_renewal_dawn_reserve.py \
  --output artifacts/garden-renewal-dawn-reserve-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-dawn-reserve
```

The runner freezes 36 calls: both historical arms first, then reserve. Every
trace and all four old frame metadata/pixel pairs must match their saved copies
before the new arm starts. It reuses the existing resource/lineage/site analysis
with an explicit receipt-check callback, adds independent threshold/handoff
checks and verifies both common prefixes. All frames and streams repeat.
`--finish` remains analysis-only; original captures are never replaced.
Verify with the matching analysis-source version recorded in each bundle;
historical source fingerprints are not relaxed to accept later tooling.

The [result](../benchmarks/garden-longevity/renewal-dawn-reserve.md) is a day-64
individual rescue but no offspring from that individual, fewer subsequent
births, and unchanged late stagnation. Both old outputs remain exact. The rule
remains selected-case, host-only and off by default; it is not a permanent
energy grant or a promoted dawn policy.

### Saved-trace reproduction access

The [read-only protocol](../benchmarks/garden-longevity/renewal-reproduction-access-protocol.md)
follows the reserve rescue without running another experimental world. It
reconstructs seed-bank occupancy at reproduction entry and each plant's turn
from verified removals and ordered appends. It undoes only actual seed fees to
recover pre-purchase stores, then checks the existing prerequisites. Previous
flowers and native expense receipts witness maturity; newly flagged flowers
without either witness stay unknown. Disjoint opportunity categories are
separate from overlapping resource failures. The final ordinary guard remains
unknown for bank-blocked turns; no counterfactual purchases are manufactured.

```sh
docker compose run --rm --no-deps firmware python3 -W error \
  sim/garden_renewal_reproduction_access.py \
  --check benchmarks/garden-longevity/renewal-reproduction-access-summary.json

# Fresh output, outside the frozen parent bundle:
docker compose run --rm --no-deps firmware python3 -W error \
  sim/garden_renewal_reproduction_access.py \
  --output artifacts/NEW-reproduction-access.json
```

The runner verifies every historical dependency by its recorded hash, permits
additional audit modules without accepting changes to old dependencies, checks
native source identity, reruns the original offline analysis and reconciles
all budgets/purchases. It repeats the new audit and never invokes a captured
experimental binary. Check portable output independently in Docker. Avoid
creating exports or editing files while provenance-sensitive CTests run.

The [result](../benchmarks/garden-longevity/renewal-reproduction-access.md) finds
259 otherwise-eligible closing target checks, all bank-blocked: 189 full at
entry, 70 filled by earlier parents. Eight seeds per day expire and are replaced,
but none germinate in the closing interval. A rotating purchase-order A/B is
the next proposal, not an implemented rule; retain resource/safety gates and
measure spending, survival and establishment as well as allocation.

### Post-noon rotating seed order

The [fixed two-arm protocol](../benchmarks/garden-longevity/renewal-seed-order-protocol.md)
adds `TOY_FACTORY_GARDEN_SEED_ORDER=ON` to the unchanged reserve-handoff host
build. It requires `TOY_FACTORY_GARDEN_DAWN_FINISH`; normal build scripts force
it off and the header rejects firmware. Use the same compiler/settings as the
parent, including RelWithDebInfo `-O2 -g` without `-DNDEBUG`.

Inspection/replay accept `--seed-order rotating` only with the existing
`--dawn-finish reserve` configuration. Omission preserves fixed order and emits
no new metadata. After tick 69,120, maintenance visits start at
`((tick-69120)/60)%plant_count` and wrap; zero/one-plant and off-cadence cases
are bounded. Every slot is visited once, with unchanged cooldown and expense
logic. The actual array is never reordered. The per-world opt-in resets off;
explicit JSON records its rule, endpoint and calculated start separately from
the physical state hash.

```sh
# Fresh independent output; exactly 16 experimental native calls.
docker compose run --rm --no-deps firmware python3 -W error \
  sim/garden_renewal_seed_order.py --build artifacts/build-host-seed-order-docker \
  --output artifacts/NEW-seed-order

docker compose run --rm --no-deps firmware python3 -W error \
  sim/garden_renewal_seed_order.py --output artifacts/garden-renewal-seed-order-v1 \
  --verify --check-export benchmarks/garden-longevity/renewal-seed-order
```

The fixed arm must exactly reproduce the old reserve traces and both selected
frame pairs before rotating starts. Original censuses keep their plant order;
only read-only views for seed-ledger/access verification use the independently
calculated traversal. All fees, receipts, lifetimes, maturity uncertainties and
guard precedence are still checked. No new policy is inferred by the analyzer.
`--finish` recovers analysis without rerunning captured binaries.

The [result](../benchmarks/garden-longevity/renewal-seed-order.md) improves target
access, 1 → 42 seeds with no survival penalty in this selected world, but no
offspring. Post-noon planting columns are all spacing-blocked. Discuss
establishment/competition next; neither larger banks nor purchase counts alone
qualify the training environment. The precise schedule is not a universal
fairness guarantee, especially when cadence and population count alias.

### Post-noon two-column seedling spacing

The [fixed protocol](../benchmarks/garden-longevity/renewal-seed-spacing-protocol.md)
adds `TOY_FACTORY_GARDEN_SEED_SPACING=ON` to the same seed-order host build.
It requires seed-order support, rejects firmware, and is explicitly disabled
by normal host build scripts. Inspection/replay accept `--seed-spacing 2`
only alongside `--seed-order rotating` and its reserve-handoff prerequisites.
Both blocker queries and seedling creation retain distance three through tick
69,120 inclusive, then use distance two. Other gates, fees and capacities do
not change. The per-world flag resets off and is separately recorded as
`seed_spacing` metadata, not hidden in the physical hash or agent inputs.

```sh
# Fresh output: exactly 20 experimental native calls, including repeat frames.
docker compose run --rm --no-deps firmware python3 -W error \
  sim/garden_renewal_seed_spacing.py --build artifacts/build-host-seed-spacing-docker \
  --output artifacts/NEW-seed-spacing

docker compose run --rm --no-deps firmware python3 -W error \
  sim/garden_renewal_seed_spacing.py --output artifacts/garden-renewal-seed-spacing-v1 \
  --verify --check-export benchmarks/garden-longevity/renewal-seed-spacing
```

The control must reproduce the old rotating traces and frame pairs exactly
before candidate capture. Spatial/seed audit helpers accept an explicit minimum
with historical default three. Birth/root storage order remains authoritative;
only seed-purchase checks use the reproduction traversal. Historical seed
comparison canonicalizes first/last spacing-witness sets, not bank order or
physical arrays. `--finish` reanalyzes saved captures without running native
binaries. Six predetermined framebuffers accompany the portable report.

The [result](../benchmarks/garden-longevity/renewal-seed-spacing.md) admits 19 new
seedlings and six full-day survivors, but also produces substantial mortality
and loses the flower. Eight plant slots are the main sampled allocation limit;
direct shared-root-cell uptake contention is not observed. Audit seedling
energy/light and adult losses next; do not promote the rule from this one
selected-world result.

### Saved establishment-light audit

The [read-only follow-up](../benchmarks/garden-longevity/renewal-establishment-light.md)
reconciles all 19 new seedlings and matched flower-5 observations from the spacing
bundle. It reconstructs photosynthesis numerator from gross income/remainders,
checks pre-uptake wear and sampled mature-leaf counts, and joins paid growth to
winning bids without treating refused offers as spending. A sampled dark leaf
alone is not a whole-canopy measurement. Cleared death-step budgets remain unknown.

```sh
docker compose run --rm --no-deps firmware python3 -W error \
  sim/garden_renewal_establishment_light.py \
  --check benchmarks/garden-longevity/renewal-establishment-light-summary.json
```

Use `--output` only for a fresh audit destination outside the parent bundle.
The runner checks every frozen parent artifact, repeats parent/new analysis,
and permits no historical source change except the exact shared CMake test
registration. Added audit modules have their own fingerprints. The old spacing
runner's strict current-source verification predates those added modules; use
this chained verifier for the current checkout, not a weakened parent manifest.
No new experiment, training or screenshot is run. Do not infer that dim-light
growth should always be refused: five successful first-day recruits also
exhausted startup reserves before reaching useful light.

### Post-noon fractional canopy transmission

The [fixed protocol](../benchmarks/garden-longevity/renewal-canopy-transmission-protocol.md)
adds `TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION=ON` to the same spacing build.
It requires seed-spacing support, rejects firmware, and is explicitly disabled
by normal host build scripts. Inspection/replay accept
`--canopy-transmission fractional` only with `--seed-spacing 2` and its existing
prerequisites. Both arms use additive shade through tick 69,120; the candidate
uses fractional attenuation starting at ecology tick 69,135. Per-world state
resets off and is recorded as `canopy_transmission` metadata, not agent input
or part of the physical hash.

For each existing target-to-sky ray, start `beam = sun_strength - 24`, then
apply `(beam * (255 - shade) + 127) // 255` per cell and return `24 + beam`.
There is no coefficient search. Shade aggregation, sun geometry, leaf condition,
photosynthesis, fees and capacities stay fixed; ambient/night light earns no
energy. Native fixtures and an independent integer reference cover all 256
sun phases and 392 light cells.

```sh
# Fresh output only: 20 experimental native calls, including repeated frames.
docker compose run --rm --no-deps firmware python3 -W error \
  sim/garden_renewal_canopy_transmission.py \
  --build artifacts/build-host-canopy-transmission-docker \
  --output artifacts/NEW-canopy-transmission

# Read-only verification at the capture revision; see the newer audit below
# for the current checkout's additional Python/CMake registration.
docker compose run --rm --no-deps firmware python3 -W error \
  sim/garden_renewal_canopy_transmission.py \
  --output artifacts/garden-renewal-canopy-transmission-v1 \
  --verify --check-export benchmarks/garden-longevity/renewal-canopy-transmission
```

The rebuilt additive arm must exactly reproduce the frozen two-column traces
and frame pairs before candidate capture. The current verifier also binds the
parent evidence, source/build/model receipts, repeated analysis and portable
images. This chained verifier covers the optics capture revision: earlier strict
audit commands predate the added native optics sources. `--finish` supports
analysis-only recovery without replacing observations; none was needed here.

The [result](../benchmarks/garden-longevity/renewal-canopy-transmission.md) preserves
the flower and two new seedlings, but fewer births and 99.0% sampled plant-slot
occupancy leave no further-generation establishment. Both renewal gates fail;
do not promote the rule or resume training on this result. The next proposed
audit separates allocation-only germination blocking from overlapping spacing
and moisture gates using these saved traces. All work remains host-only/off by
default and uncommitted.

### Saved allocation-only germination audit

The [read-only follow-up](../benchmarks/garden-longevity/renewal-allocation-blockers.md)
checks both canopy arms, every seed lifetime and all saved site checkpoints.
It separates dormant seeds, mature retained-seed observations, distinct seeds,
purchase-window cohorts and hypothetical columns. Post-step mask `8` is promoted
to allocation-only rejection evidence only when the reviewed native stage order
supports it: no births on that step, eight non-newborn occupants, sufficient
surface moisture/node room and no spacing or wet-rule light gate. Birth-step
queries remain post-step evidence; removed seeds receive no invented observation.

```sh
docker compose run --rm --no-deps firmware python3 -W error \
  sim/garden_renewal_allocation_blockers.py \
  --check benchmarks/garden-longevity/renewal-allocation-blockers-summary.json
```

Use this verifier with its recorded source version. It checks the complete immutable
canopy bundle, parent reanalysis, historical source hashes, unchanged native
sources and six images, allowing only the exact shared registration of this
new Python test. It repeats the new analysis; `--output` requires a fresh path
outside the frozen parent. No native research executable is invoked.

The candidate has 53 distinct seeds with confirmed allocation-only observations,
including seven from new shrub 13; 52 expire. Only four of 5,542 confirmed
observations involve dead occupancy. The result supports discussing an isolated
eight-versus-sixteen plant-slot host diagnostic, not predicting successful
counterfactual seedlings or promoting capacity. Seedling survival, further
renewal, adult retention and displaced node/resource pressure must be evaluated
in that future test. This audit changes no capacity, ecology, model or firmware.

### Fixed eight-versus-sixteen plant admission experiment

The [protocol and results](../benchmarks/garden-longevity/renewal-plant-slots.md)
use the fractional-canopy arm as the historical eight-slot control. Compile
`TOY_FACTORY_GARDEN_PLANT_SLOTS=ON` only with that full opt-in dependency chain;
`--plant-slots 16` in inspector/replayer then raises effective admission after
tick 69,120. Compiled storage supports 16 in both arms, while an absent flag
retains eight throughout. Candidate metadata is `plant_admission`; the existing
replay `plant_slots` field remains the occupied-record count. Normal build
scripts disable the option and firmware rejects it. Node/seed capacities and
all other rules remain unchanged.

```sh
docker compose run --rm -T firmware python3 -W error \
  sim/garden_renewal_plant_slots.py \
  --output artifacts/garden-renewal-plant-slots-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-plant-slots
```

This is the verifier at the plant-slot experiment's recorded source version.
For the node-pressure audit checkout, use its wrapper below; for the later
full-pool checkout use the full-pool verifier. These verification modes never
invoke the simulator. The
bundle preserves all 20 calls, raw repeats, six native images, sources, binaries,
models and unchanged parent observations. Historical analysis tools retain
their stricter source requirements; do not weaken them to accept newer rules.
The new analysis generalizes admission bounds using validated metadata, with
eight as the historical default; the standalone node-audit package includes
that helper. All historical control-derived results still reconcile exactly.

New full-day survivors rise 2 → 17 and new full-day parents with a full-day child
0 → 6, but incumbent deaths rise 1 → 6 and founder families fall 3 → 2. Maximum
generation reaches four; final population is 11 with all 512 nodes occupied.
The node pool stays full for the final 4.05 days and contains no dead tissue at
the endpoint. This fails the predeclared retention gates; no default promotion
or training follows. 90/94 default/experimental tests and independent Docker
verification pass. Next discuss an offline allocation/competition audit before
choosing a new mechanism or increasing memory.

### Saved node pressure and incumbent-death audit

The [read-only audit](../benchmarks/garden-longevity/renewal-node-pressure.md)
uses the frozen plant-slot bundle without new native research calls. It
reconstructs reclamation, four-node births and ordered per-plant allocations,
checks fullness at the actual growth stage, and matches all six incumbent
pre-death windows to their control histories. Cleared terminal budgets remain
unknown; full-pool exposure is not an unobserved rejected EXTEND request.

```sh
docker compose run --rm -T --no-deps firmware python3 -W error \
  sim/garden_renewal_node_pressure.py \
  --check benchmarks/garden-longevity/renewal-node-pressure-summary.json
```

Use this wrapper with its recorded source version. It validates the parent
manifest, portable summary,
historical analysis and native hashes, allowing only its exact new CMake test
registration. It reanalyzes the parent, repeats the new audit and checks output
identity; `--output` requires a fresh destination outside the parent bundle.
The historical verifier's stricter source checks remain intact.

The endpoint pool is entirely living tissue. The capacity check skips the
growth policy before it can choose WAIT or non-allocating FINISH, while leaf
renewal still succeeds. Four incumbent fatal episodes begin with water
shortage, two with energy shortage; five dead incumbents were already tipless
at the split. No capacity increase, forced turnover, rainfall change or adult
rescue is implied. Next proposal: a separate bounded non-allocating-action A/B.

### Fixed non-allocating actions at full node capacity

The [protocol and results](../benchmarks/garden-longevity/renewal-full-pool.md)
reuse the previous sixteen-slot candidate as the new control. Build the full
opt-in dependency chain with `TOY_FACTORY_GARDEN_FULL_POOL=ON`, then pass
`--full-pool nonallocating` to inspector/replayer alongside `--plant-slots 16`
and its required flags. An absent new flag retains the saved behavior exactly.
The new rule becomes active after tick 69,120; capacity remains 512 nodes.

Resource eligibility, cooldown and leaf-renewal precedence are unchanged. At
full entry, the normal winner is evaluated: an allocating EXTEND is rejected
before expense or private-state commit, while non-allocating actions retain
existing guards. No fallback to another bid or forced FINISH is introduced.
`full_pool` metadata distinguishes selection, allocation refusal and later
guard/commit outcomes. Diagnostics are per-world, bounded and overflow-checked,
reset off and excluded from the physical hash. Firmware rejects the option;
ordinary build scripts explicitly disable it.

```sh
docker compose run --rm -T --no-deps firmware python3 -W error \
  sim/garden_renewal_full_pool.py \
  --output artifacts/garden-renewal-full-pool-v1 --verify \
  --check-export benchmarks/garden-longevity/renewal-full-pool
```

At the full-pool capture revision, this verifier binds the archived parent/node audit, unchanged
historical control, limited native changes, build/model/source/protocol receipts,
all repeats, six frames and exact derived outcomes. It invokes no simulator.
`--finish` is analysis-only recovery for an already captured, unsealed bundle;
it cannot recapture observations. The allocation-refusal pre-accounting hook
removes only independently verified uncommitted bids from legacy expense
analysis, preserving raw evidence and all authoritative/leaf records.

The fixed run commits 6,224 full-pool WAITs and refuses 6,060 allocating winners,
but selects no FINISH or exhausted EXTEND. New full-day survivors fall 17 → 16;
durable new parents and incumbent deaths stay at six each. The mechanism and
survivor gates fail. Two recent generation-five seedlings remain censored.
286,700 live budgets, 1,036 seed lifetimes, repeated/independent analysis and
92/97 default/experimental CTests pass; 57 terminal budgets remain unknown.
Keep the change host-only/off by default. Discuss structural shedding and its
measurement/safety requirements before adding a pruning action, not more RAM,
forced FINISH or a training run. No device build/flash, commit or push.

### Saved shedding-feasibility audit

The [read-only audit](../benchmarks/garden-longevity/renewal-shedding-audit.md)
uses both full-pool histories without invoking the native research executables.
It tracks `(lineage, leaf ordinal)` across append-only growth and stable
whole-plant compaction, checking wear/renewal position-by-position. Zero spells
end separately at renewal, owner death or endpoint censoring. A one-day-zero
subset is diagnostic, not a new rule. `active_leaves` denotes maturity, not
condition; neither zero condition nor a growth-tip flag establishes terminality.

```sh
docker compose run --rm -T --no-deps firmware python3 -W error \
  sim/garden_renewal_shedding_audit.py \
  --check benchmarks/garden-longevity/renewal-shedding-audit-summary.json
```

Use this wrapper at the recorded audit revision. It verifies the full immutable
parent, historical derived outcomes/images and unchanged native sources,
permitting only this audit's exact CMake test registration. New analysis repeats
and the portable output verifies independently in Docker. Historical verifiers
remain strict; `--output` requires a fresh path outside the parent. There is no
capture/collection mode. The prior manual export is matched to its pre-export
canonical census, not incorrectly assigned to the next observation of absence.

The control endpoint has 146 zero-condition living leaf nodes, 110 continuously
zero for a day. Candidate counts are 56/46. Safe terminal removability is unknown;
hundreds of full-day zero spells subsequently renew. The node/upkeep calculations
are optimistic same-census bounds with a safe lower bound of zero, not simulated
deletions, guaranteed births or paid savings. 8,738,097 leaf-ordinal transitions,
6,780 renewals, 14 focused cases and 93/98 default/experimental CTests pass.

The next proposed step is a host-only topology census that preserves physical
hashes and reports node roles/parent links before any shedding implementation.
Stable compaction must preserve parent-before-child order, parallel leaf state,
per-owner counts and all base/previous-tip references. Recompute child counts;
do not mistake spent flowers for garbage or automatically reparent internal
stems. No native source, ecology, model, default or device changes in this audit.

### Read-only topology census: terminal shedding is not the storage fix

The [fixed follow-up](../benchmarks/garden-longevity/renewal-topology.md) adds
`--topology-at TICK` to the host inspector with `--ecology`. At most sixteen
increasing distinct ecology checkpoints are allowed, including zero. Records
follow their matching world census, including separate same-tick intervention
stages. Exported links, roles, conditions and plant references are host-only;
the world and controller observations do not gain persistent diagnostic storage.

The fixed runner replays only the historical sixteen-slot control, once with
capture off and twice with it on. It samples eight predeclared checkpoints and
requires byte-for-byte equality of all 194,270 pre-existing output records.
The independent analyzer reconstructs child counts, checks owner/reference and
leaf-order invariants, and uses the complete census for zero-condition duration.

The command below belongs to the recorded capture revision. The subsequent
[merge cleanup](garden-merge-checkpoint.md) formats the inspector without changing
behavior; the verifier intentionally requires its archived source, not that newer
file. The frozen bundle and portable evidence remain unchanged.

```sh
docker compose run --rm -T --no-deps firmware python3 -W error \
  sim/garden_renewal_topology.py \
  --output artifacts/garden-renewal-topology-v1 \
  --check benchmarks/garden-longevity/renewal-topology-summary.json
```

The endpoint has 146 exhausted leaf nodes, but 136 are internal supports. Only
one terminal node passes the conservative criteria; it has not remained zero
for a day. Every sampled full checkpoint has at most one eligible node, below
four-node germination headroom. No actual shedding or savings are claimed.
The three captures, independent verification and 95/100 default/experimental
CTests pass. The bounded investigation closes negatively; consolidate for review
rather than automatically broadening into structural surgery. The previous
strict verifiers remain tied to their frozen source revisions. No firmware,
default, model, training, capacity, commit or push change.

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
