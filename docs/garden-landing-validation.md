# Frozen landing-controller validation

This host-only development experiment tests the pilot's nine final
**training-selected** controllers on four additional world/weather seeds.
It does not retrain, select replacements, change ecology or flash the device.
The [fixed protocol](../benchmarks/garden-seasons/landing-validation-protocol.md)
defines 19 variants, 16 conditions, 192-day horizons and 76 review frames.
The [completed report](../benchmarks/garden-seasons/landing-validation.md) records
robust current-only endpoint survival, mixed same-weight input benefits and
persistent renewal gaps. Its retained models, ledgers and gallery receipts are
portable repository evidence; the ignored local bundle additionally contains
the frozen executable and raw framebuffers.

```sh
make host-validate-landing-garden \
  GARDEN_LANDING_VALIDATE_OUT=artifacts/garden-landing-validation-v1
```

The pinned pilot models and selection summary are in the repository, so a
fresh clone has the inputs. Output must be a new directory; research ecology
flags are rejected. `GARDEN_LANDING_VALIDATE_ARGS="--jobs 2"` controls independent
world workers only. The entire panel is repeated with one worker and no capture;
models, ledgers and scores must match exactly. No extra training is automatic.

## Explicit input ablation

```sh
make host-landing-garden ARGS="ablate history.tgl current.tgl current"
make host-landing-garden ARGS="ablate current.tgl off.tgl off"
```

Allowed changes: history to current/off, current to off. Identity operations,
input re-enabling, malformed files and existing destinations are rejected.
The source is untouched. Only the stored mode byte and outer CRC change; all
legacy bytes and extension weights remain identical. Loading/replay never
silently overrides a model. The independent byte oracle in the collector checks
every derived model against its archived source.

`panel/results.json` retains complete per-world lineage/seed histories, the
existing renewal score, and paired comparisons by condition, seed, climate and
layout. Within-controller ablations are distinct from between-training-arm
comparisons. Aggregate lexicographic keys are not scalar scores. Inspect
zero-credit windows and world-level results, not only populated screenshots.

`panel/gallery.json` maps every image to its model and outcome. Contact sheets
under `panel/gallery/` have days 16/192 as columns, ordinary/crowded layout as
successive rows, and original input mode followed by reduced modes (history,
current, off where applicable). All use the first fixed seed, seasonal climate.
Day-192 captures must match independent headless results. Failure images stay.

## Reproduce a trusted local bundle

```sh
docker compose run --rm -T firmware python3 \
  artifacts/garden-landing-validation-v1/sim/garden_landing_validation.py \
  --verify artifacts/garden-landing-validation-v1
```

Verification executes the frozen binary, rederives all models, repeats all 304
worlds and 76 frames, rescores their ledgers and compares saved files byte for
byte. The manifest hashes the binary, source snapshot, tools, options, protocol,
inputs and output; `FAILED.txt` rejects interrupted/invalid collection. Do not
edit sources or rebuild during collection. A snapshot records source identity,
not proof of a reproducible build.

An ablation loss establishes input dependence under zeroing, not necessarily
useful interpretation of changing environmental information: activation
distributions also change. Four seeds are a bounded development check, not
statistical certification or an untouched final test set. Discuss results
before expanding the search or changing the experiment.
