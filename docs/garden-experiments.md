# Matched Garden experiments

One command now collects rain-fed matches, lightweight timelines, a paired
comparison, and detailed replays of selected cases. This changes neither the
Garden ecology nor training fitness and requires no device. Firmware receives
no additional buffers or tracing work.

The [Garden A-life roadmap](garden-alife-roadmap.md) tracks environment
qualification, per-generation champion screenshots, training objectives, and
parallel search. Post-process a completed bundle with the separate
[visual-review gallery](garden-visual-review.md) to capture saved-model images
checked against these timelines. Per-generation trainer integration is still planned.
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
