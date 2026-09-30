# Paired live/fixed-input training

This host-only experiment trains the same current-only network with either live
added readings or fixed raw-zero readings. Both preserve source/body gating,
legacy inputs, model size, mutable weights and the original renewal objective.
Raw zero becomes -128 after encoding: unlike neutral masking, the control
retains learnable extra-input offsets. Redundant fixed columns still change
effective optimization difficulty; equal budgets do not erase that limitation.

The [fixed protocol](../benchmarks/garden-seasons/landing-controls-protocol.md)
defines all profiles, seeds, budgets, comparison gates and stopping rules.
No C, inference, model-ABI, ecology, player or device change is needed; this
runner composes the existing explicit host probe and native mutation commands.
The [experiment report](../benchmarks/garden-seasons/landing-controls.md) retains
the full comparisons, model files and all generation galleries.

```sh
make host-train-landing-controls \
  GARDEN_LANDING_CONTROLS_OUT=artifacts/garden-landing-controls-v1
```

Inputs are the pinned, retained original pilot models, histories and summary
under `benchmarks/garden-seasons`. A fresh clone does not need an ignored model
artifact. `GARDEN_LANDING_CONTROLS_ARGS="--jobs 4"` controls independent world
workers (1–8). Budgets, conditions and fixed values are intentionally not knobs.
Use a fresh output directory and ordinary ecology with all research flags off.
For an optimized isolated build, invoke `sim/garden_landing_controls.py` directly
with `--build`, `--inputs` and `--out` paths inside the builder container.

There are 42 candidate evaluations, 72 per-generation review results and 128
final/initial evaluation results: 368 scored worlds total (168 training worlds).
All searches finish before the new evaluation seeds run. Only training picks a
winner; review and evaluation cannot change the parent or budget. The live arm
must reproduce the earlier current-only models and biological trajectories.
Generation zero must behave identically across profiles. GSP1 diagnostic hashes
remain profile-specific and are not treated as ordinary GLR1 identities.

Each generation, including zero, retains four seasonal review frames: both
layouts at days 16 and 192. Six contact sheets contain all 72 frames, including
failures and unchanged champions. Every capture matches its headless replay.
The model needs its recorded profile for replay: a fixed-trained TGL2 file
alone does not silently install an override in an ordinary host/device run.

Collection freezes sources, binary, protocol and inputs, then repeats everything
with one worker and captures disabled. Do not edit the repository or rebuild
during collection. Partial or failed output is not resumable evidence. A source
snapshot alone is not proof the binary was built from those sources.

To independently execute and verify a trusted local frozen bundle, including
all model mutations, results, raw frames, PNGs and contact sheets:

```sh
docker compose run --rm -T firmware python3 \
  artifacts/garden-landing-controls-v1/sim/garden_landing_controls.py \
  --verify artifacts/garden-landing-controls-v1
```

This is one small paired training experiment. Stop at the fixed budget and
discuss its evidence; do not adopt a controller, tune constants or automatically
expand training. The newly inspected evaluation seeds become development data.
