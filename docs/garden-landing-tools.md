# Host landing-model replay and evaluation

The [experimental TGL2 network](garden-landing-inference.md) now has explicit
host file, replay, and matched-evaluation commands. This is tooling, **not a new
training score or evidence that the added observations improve plant fitness**.
The old trainer/player, firmware, and ordinary ecological defaults are unchanged.
The later [bounded training pilot](garden-landing-training.md) adds `mutate` and
`replay --ledger`, reusing the established renewal score in a separate experiment.
The [frozen validation panel](garden-landing-validation.md) adds explicit
`ablate IN.tgl NEW.tgl off|current` derivation without modifying any weights.
The [signal-content probe](garden-landing-signals.md) adds a separate
`probe-replay` command with explicit occupancy/resource interventions and a
probe-aware identity; ordinary replay and TGL2 files remain unchanged.
The [same-state observer](garden-landing-decisions.md) adds explicit `trace-replay`
with a separate trace file. Its alternative proposals never advance the world;
the normal replay JSON and GLR1 run identity remain unchanged.
The [reach observer](garden-landing-reach.md) adds `replay --ledger --reach-trace`
for parent-specific support and exact sequential site masks, without altering
the world, model or RNG. It can accompany the first-day recruitment trace.

## Start with an explicit model

```sh
# Docker builds all dependencies. artifacts/ is ignored by git.
make host-build
mkdir -p artifacts/landing-models

# A built-in reference with zero extra weights (a control, not a trained model).
make host-landing-garden \
  ARGS="reference artifacts/landing-models/reference.tgl --mode history"

# Or explicitly import a saved v1 model; its original bytes remain nested intact.
make host-landing-garden \
  ARGS="import artifacts/garden-champion.tgm artifacts/landing-models/champion.tgl --mode history"

make host-landing-garden ARGS="inspect artifacts/landing-models/reference.tgl"
```

Creation requires `--mode off|current|history`; `--omit-dead-only` is optional.
Loading never guesses the format or overrides a stored mask. Imports initialize
all 208 added weights to zero, so changing the mask alone cannot improve an
imported controller. `inspect` reports both CRCs, the fixed mask/flag, and the
number of nonzero added weights. CRCs detect corruption, not authenticity.

Model reads require exactly 1,448 valid bytes. New model and raw-image writes
refuse existing files, directories, and symlinks. An ordinary write/close failure
removes only the newly created partial output. These are exclusive-creation
operations, not crash-durable transactions; callers must own the destination
pathname while writing. Model-read failures preserve the caller's output.

## Replay one world

```sh
make host-landing-garden \
  ARGS="replay artifacts/landing-models/reference.tgl rainfed 0xa9c30c1f --ticks 122880 --climate seasonal --framebuffer artifacts/landing-frame.rgb565be"
```

Both `--ticks` and `--climate` are required; seed must be a nonzero u32.
Layouts are `rainfed` and `rainfed-crowded`; climates are `steady`, `winter`,
`drought`, and `seasonal`. Initial water is still part of scenario setup, but
there is no recurring irrigation or gardener assistance. Supported horizons are
0..983,040 logic ticks (256 Garden days). One Garden day is 3,840 logic ticks,
256 ecology steps, or 64 seconds at the device's nominal 60 Hz logic rate.

JSON records the model, climate, build-rule bits (wide=1, flower-origin=2),
ordinary world hash **and cache/model-aware run hash**, warmup, census, accumulated
post-step descendant-live logic ticks, and lifetime totals by species. Optional
capture is the same 240×240 RGB565 big-endian production render used by the old
replayer. It does not advance the simulation. The raster has one owner per
process; parallel batches use independent executable processes, not simultaneous
calls into the process-global renderer.

The landing-aware step now exposes the existing exact natural-death receipts.
The same lifetime ledger as the older evaluator retains birth/death history
after plant-slot compaction; totals must reconcile with the authoritative world
or the command fails. Both complete run and receipt output remain unchanged on
step failure. The 4,096-lineage host ledger fails explicitly on exhaustion,
never silently truncates a report. It is not part of device RAM.

Full-day survivors require a full day of potential follow-up; recent living and
dead offspring are reported separately. A historical durable parent and at least
one child each survived a day. That does not establish current renewal, and an
empty eligible cohort is not a zero-percent survival rate. Pending-seed ancestry,
closing-window fitness, and training selection are not added by this command.

## Compare saved models and capture PNGs

```sh
make host-evaluate-landing-garden \
  GARDEN_LANDING_OUT=artifacts/landing-comparison \
  GARDEN_LANDING_ARGS="--model control=artifacts/landing-models/reference.tgl --model candidate=artifacts/landing-models/champion.tgl --days 32 --climate steady --climate seasonal --seed 0xa9c30c1f --seed 0xed52188c --jobs 2"
```

Choose a **fresh** output directory. The collector retains:

- Frozen executable and models; settings, model metadata, CMake cache, source
  snapshot/hashes, and SHA-256 artifact inventory.
- Every requested case, including failed/empty ecologies; JSON outcomes and
  raw frames plus PNGs at fixed checkpoints. Each capture is independently
  replayed from tick zero and must match state, outcomes, and raw pixels exactly.
- A short comparison report and a per-climate first-seed contact sheet. Other
  seeds' frames are retained too. No best-looking run is selected.

Defaults: both layouts, seasonal climate, seed `0xa9c30c1f`, 32 days, checkpoints
1/16/32, two workers. Repeat `--model LABEL=PATH` (up to four), `--seed` (up to
eight), `--scenario`, `--climate`, and `--checkpoint-day` to choose a panel.
The final day is always included; at most six checkpoints. Names are bounded,
unique labels. These are **development** worlds, not a held-out test set.

Only ordinary ecology and the isolated wide/flower-origin builds are accepted.
For a deliberately built experimental directory, invoke
`python3 sim/garden_landing_evaluate.py --build PATH ...` inside the builder;
the friendly Make targets rebuild ordinary defaults. Never rebuild a frozen
older experiment directory. Keep source/build/model inputs fixed during a run.
Collection detects changed inputs, marks a started failed bundle `FAILED.txt`,
and publishes a complete manifest only after success. It never overwrites an
older bundle or silently resumes partial results.

The source snapshot describes files observed during collection; it is not an
attestation that an arbitrary supplied executable was built from those files.
Build immediately before collecting, then freeze inputs. Exact replay is tied
to the retained binary/model hashes and a compatible host runtime (the builder
container), not a promise of bit-identical rebuilds on every toolchain.

Recheck a **trusted local** bundle without rebuilding or changing its settings:

```sh
docker compose run --rm -T firmware python3 \
  artifacts/landing-comparison/sim/garden_landing_evaluate.py \
  --verify artifacts/landing-comparison
```

Verification checks recorded artifact hashes before executing the saved binary
and regenerates every saved state/frame. SHA-256 inventories detect accidental
edits, not malicious replacement of a bundle and its manifest.

## Gate before training

Tests cover explicit import/format separation, strict CLI bounds, no-clobber
and short-write failures, rollback, old/new lifetime agreement, zero-extra
world/pixel equivalence across all climates, nonzero saved-model influence,
independent repeats, PNG pixels, frozen-bundle verification and tamper rejection.

Next define a bounded, equal-budget host-training comparison of off/current/
history inputs under **identical mechanics**, with frozen seeds and untouched
validation conditions. This tooling supplies replayable model artifacts and
diagnostics; it does not yet train extended networks or add portable world saves.

## Verified checkpoint

All **130 ordinary / 124 representative older-research CTests pass**, plus the
four focused native/file/CLI/reference tests in a wide + flower-origin build.
The CLI tests compare 96 zero-extra captures against the old replayer (three
masks × two layouts × four climates × four checkpoints); world fingerprints,
census and raw pixels match, and capture-free replays have identical outcomes.
Saved nonzero weights influence the authoritative run. Audited and unaudited
landing steps retain byte-identical worlds/caches and the same death receipts
as the old path over three 32-day cases; failure rollback is covered.

The retained local workflow check uses a previously saved v1 controller
(`01b9d94a` payload CRC, SHA-256
`fab9b6d97de88a970d63bb8af8fc336d076bb3d0ae6867b307290209abf85cf2`),
imported separately with off/current/history masks and zero added weights.
Two weather seeds (`a9c30c1f`, `ed52188c`), two layouts and steady/seasonal
climates give **24 runs to day 32**, with **72 captures** at days 1/16/32.
Every capture repeats and the completed frozen bundle verifies independently.
All three masks have identical world fingerprints, census, lifetime outcomes
and pixels in each matched case, as expected for zero-extra imports.

The images also retain the old controller's failures: all four crowded
conditions end with no living plants or seeds, while ordinary rainfed endpoints
have two or three living plants. This small development panel is a workflow
check, not a fresh training result or an ecological promotion gate.

Local outputs are `artifacts/garden-landing-tools-panel/report.md` and its
`gallery/` subdirectory. Regression logs are
`artifacts/garden-landing-tools-{default,research,flower}.log`. Regenerate a
fresh panel with the commands above; no device flash was needed.

The changed `garden_world.c` also compiles with the recorded Zephyr firmware
flags, writing a separate object without changing the existing firmware build.
An additional ad-hoc `-Wextra -Werror` ARM check encounters the pre-existing
enum/type-limits warning in `picosystem_garden_world_set_climate`; that is not
part of the recorded build's warning configuration. This check is not a full
firmware rebuild, stack measurement, or hardware test.
