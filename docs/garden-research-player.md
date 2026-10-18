# Garden research player

Watch the fixed wear controller or either learned repair policy under the exact
research conditions used in the [durability comparison](../benchmarks/garden-seasons/leaf-family-durability.md).
This is a separate host-only viewer: ordinary `make host-play` and PicoSystem
firmware keep their existing behavior.

## Launch

```sh
make host-play-research ARGS="--policy s1-g3-c4 --speed 256"
```

Use `initial` for the fixed wear control, `s1-g3-c4` for Search 1, or `s2-g3-c1`
for Search 2. Neither finalist is promoted as a replacement default.

The default condition is rainfed founder 1 on weather `58d7d6ca`. To watch a
different founder in the crowded plot:

```sh
make host-play-research \
  ARGS="--policy s2-g3-c1 --layout rainfed-crowded --founder 4 --seed 9a903368 --speed 256"
```

Rainfed has founders 1–3; rainfed-crowded has founders 1–5. The four panel seeds
are `58d7d6ca`, `9a903368`, `6b9c1a3e`, and `59818bc3`; the archived reference
seed `98a89374` is also accepted. Use eight lowercase hexadecimal digits without
`0x`. Changing a condition or policy requires a fresh launch, so a model is
never replaced midway through a family's life.

The Docker build prepares the frozen sources and models from the committed
evidence archive, then compiles the session adapter and pinned SDL3 viewer.
It does not need the old experiment build directories, install host development
dependencies, or execute saved binaries. The first build may download SDL.

## Controls and time

| Key | Action |
|---|---|
| Space or P | Pause or resume |
| N or period | Pause and advance one logic tick |
| D | Pause and advance one Garden day |
| R | Reset the same policy and conditions |
| Minus or plus | Select 1x, 16x, 256x, or maximum speed |
| M | Maximum speed |
| H | Toggle the selected family's overlay |
| S | Save a screenshot and complete state/history record |
| Escape | Quit |

A Garden day is 3,840 logic ticks: 64 seconds at 1x, or about a quarter-second
at 256x when the host keeps up. The header shows the requested speed and measured
effective speed. Presentation is capped near 30 frames per second; faster
playback can skip display frames but still executes every simulation tick.
Stepping is split into bounded work slices to keep keyboard handling responsive.
Playback pauses at day 1376; reset or quit from there.

Repeated N, period or D presses queue their steps, up to the run's stop tick;
holding a key does not auto-repeat. Pause/resume or reset cancels any queued
steps. A screenshot records the current completed tick, not queued future work.

The candidate policy belongs to one founder family and follows its descendants.
Other families retain the selective resident controller. The header's `live`
and `bank` counts refer only to the candidate family, not the whole garden.
A populated garden can therefore have an extinct candidate family. W2 growth,
seasonal rain and the fixed ecology remain unchanged. Gardener keys do nothing.

Press H to trace the selected family's living stems and roots in cyan, with
small squares at their bases. Pink diamonds mark that family's pending seeds,
including seeds whose parents have died. Dead plants are not highlighted.
The overlay follows lineage identity through reproduction and plant-slot reuse;
it does not identify family membership by location or appearance.

The overlay starts off. Add `--highlight-family` to start with it enabled:

```sh
make host-play-research ARGS="--policy s1-g3-c4 --speed 256 --highlight-family"
```

Highlighting does not advance the world or cancel queued steps. It changes only
the viewer display; saved captures retain the original pixels without overlays.

## Captures

`S` creates a fresh `shot-*` directory under `artifacts/garden-research-captures`:

- `frame.png`: the unmodified 240-by-240 garden image, without viewer text or overlays;
- `frame.raw`: its exact RGB565 big-endian bytes;
- `state.json`: the canonical state, model identity, conditions and full histories;
- `manifest.json`: the frozen runtime archive identity, policy name and frame CRC.

The manifest is published last. A folder without a complete manifest is a
failed/partial capture, not evidence of a completed save. Existing captures are
never overwritten. `--capture-dir DIR` chooses a different directory; its parent
must exist. Capture or simulation errors stop the viewer with an error message.

For automation, `--stop-tick COUNT` exits at that exact tick,
`--paused --frames 1` presents the initial world, and `--capture-on-exit` saves
the final image and state. Successful exit prints the same JSON record as the
headless research runner. Canonical state records identify a run; loading them
to resume playback is not implemented.

## Verification

```sh
make host-research-player-check
```

Checks cover ownership, independent sessions, reset and allocation failure,
latched audit errors, render-state preservation, actual SDL keyboard events,
queued tick/day presses and stop boundaries, speed-independent results, invalid
inputs, capture safety, and PNG-to-native pixel equality. Overlay checks cover
actual H events and displayed marker pixels, exact restoration after toggling
off, unchanged captures for all three policies, and a 64-day lineage replay with
descendants, dead plants, reused slots and posthumous seeds. Preparation tests reject
changed archives, models, sources, manifests, unsafe paths, symlinks and partial
output directories. The new C code
builds with strict warnings and undefined-behavior sanitization.

Nine longer checks also matched complete archived stdout and raw pixels:
three day-608 anchors, three day-1376 rainfed founder-1 runs on `58d7d6ca`, and
those three late runs with rendering after every Garden day. They completed in
257.3 seconds in a clean Git-tree export without historical artifacts or network
access. Results are retained in `artifacts/garden-research-parity-v1`.

To repeat that bounded check, use a fresh output directory:

```sh
docker compose run --rm -T host-player python3 -B sim/research_player/check_replay.py \
  --binary artifacts/garden-research-player-build-v1/research-replay \
  --out artifacts/garden-research-parity-v2
```

The implementation follows the [playback plan](garden-research-playback-plan.md).
Side-by-side worlds, backward seeking, browser playback,
new training and firmware deployment remain separate work.
