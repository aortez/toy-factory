# Garden visual review

Inspect a fixed panel of the exact worlds already measured in a completed
[matched experiment bundle](garden-experiments.md), using the production renderer:

```sh
make host-gallery-garden \
    GARDEN_GALLERY_BUNDLE=artifacts/garden-matches-baseline \
    GARDEN_GALLERY_OUT=artifacts/garden-visual-baseline
```

Open `artifacts/garden-visual-baseline/index.md`. It links a contact sheet,
native 240 x 240 PNGs, per-frame population/weather metadata, and final
offspring-survival/reproduction metrics. The table below the contact sheet
identifies its rows; individual labeled images appear further down. Empty and
failed worlds are retained, not discarded for presentation.

## Panel and timing

The default panel is the **first recorded world seed**, both rain-fed layouts,
and the experiment's candidate/control policies. It is not ranked by outcomes.
Its three default checkpoints are:

- tick 480: eight seconds of growth in daylight;
- tick 2880: first dawn after the first night, at 48 seconds;
- final tick: late-run state, e.g. 92160 after 24 cycles (25 minutes 36 seconds).

Reset starts at noon: sun phase is `(64 + tick / 15) % 256`, using integer
division. One cycle takes 3840 authoritative ticks / 64 seconds. Short-run
default ticks are clamped to the horizon and deduplicated.

Choose a panel before examining its images, for example:

```sh
make host-gallery-garden \
    GARDEN_GALLERY_BUNDLE=artifacts/garden-matches-baseline \
    GARDEN_GALLERY_OUT=artifacts/garden-visual-custom \
    GARDEN_GALLERY_ARGS="--seed 6f47c12c --checkpoint 480 --checkpoint 1920 --checkpoint 2880 --checkpoint 92160"
```

Seeds are exact eight-hex-digit **world** seeds in that bundle, not new batch
seeds. Repeat `--seed` up to four times and `--checkpoint` up to six times.
Every requested checkpoint must exist in every selected evaluator timeline.
Use `--include-adaptive` to add an adaptive row beside each candidate/control
pair, useful for a neural-model A/B probe. The default panel has 12 images;
the largest supported panel has 96, or 144 with this third policy. The output
directory must be new. The source experiment is never modified.

Manual review informs model selection; a gallery is not untouched test evidence.
Test-labeled bundles are rejected by this development workflow. For future
training galleries, declare review seeds distinct from training and final test
seeds. Current baseline images reuse already investigated validation conditions,
not a newly reserved review split.

## Exact replay boundary

`toy-factory-garden-replay` loads a canonical model, resets through
`garden_evaluation`, and runs the same policy and seed to the requested tick.
It never substitutes the playable Garden's default policy or uses a gardener.
A host-only adapter copies the Garden into a tagged game-world wrapper for the
production snapshot builder and rasterizer. The process-global framebuffer has
one renderer owner. Rendering does not advance authoritative state.

The reported hash is the **Garden evaluator hash**, not the larger playable
game-world hash. Raw files are RGB565 big-endian, exactly 115200 bytes; CRC is
checked before conversion with the existing PNG writer. The standalone interface:

```sh
make host-build
docker compose run --rm firmware build-host/toy-factory-garden-replay \
    artifacts/garden-lifetimes/champion.tgm rainfed neural-candidate 0x6f47c12c \
    --ticks 2880 --framebuffer artifacts/garden-frame.rgb565be
```

The parent directory must exist and the frame file must be new. Omit
`--framebuffer` for identical headless evaluation without rasterization. Use
model `-` for `baseline`, `adaptive`, or `neural-reference`; a non-dash model is
accepted for `neural-candidate` or the explicitly labeled host-only
`neural-no-night-growth` probe. Both rain-fed layouts and any tick from
0 through 100000 are supported. The gallery's timeline constraints are stricter
than this standalone interface.

## Retained evidence and verification

- `index.md`, `contact-sheet.png`, and native PNG/raw-frame pairs;
- `frames.json`: reference timeline rows, final evaluator metrics, replay
  results, identities, and contact-sheet ordering;
- `bin/garden-replay`, `models/`, `tools/`: frozen replay inputs and tools;
- `input-manifest.json`: source experiment provenance and hashes;
- `source.tar.gz`, `source.patch`: current render/replay sources, including
  dirty/untracked files, separate from original evaluator provenance;
- `manifest.json`: completion marker and retained-artifact hashes.

Each captured hash and population/weather field must match the recorded
timeline. External model CRCs must match the frozen model identity. Renderer
changes are permitted without changing ecology: render provenance and pixels
are recorded separately from the original experiment. Source changes during
capture fail collection. Partial outputs retain `failure.json`, without a
completed manifest.

Recheck all captures using the frozen executable and models:

```sh
docker compose run --rm firmware python3 \
    artifacts/garden-visual-baseline/tools/garden_gallery.py \
    --verify artifacts/garden-visual-baseline
```

Verification checks artifact hashes, then reproduces exact result records and
raw framebuffer bytes. It does not modify the gallery. Frozen native binaries
need a compatible host architecture/runtime; use the builder container.
`--timeout` controls the positive per-capture timeout (default 120 seconds).

Tests compare capture on/off across all supported policies and both layouts,
zero/non-ecology/dawn ticks, repeated pixels, model validation, exclusive output,
evaluator hashes, PNG-decoded pixels, contact-sheet placement, and frozen
verification/failure cases.

## Scope

This is the saved-model replay/gallery bridge, **not automatic per-generation
trainer capture**. The trainer still exports only the final champion.
Persisting every generation's model and scheduling its screenshots remain in
[issue #30](https://github.com/aortez/toy-factory/issues/30) and the
[Garden A-life roadmap](garden-alife-roadmap.md). A live player for arbitrary
saved evaluation models is optional later work. Ecology, fitness, firmware RAM,
and device rendering are unchanged by this host-only feature.
