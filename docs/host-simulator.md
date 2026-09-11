# Host simulator

The host simulator runs Toy Factory's production deterministic model and
software renderer without a PicoSystem. It is both a fast regression harness
and an interactive scene-development tool; it is not an RP2040 emulator.

## Exact shared boundary

The native targets compile the same C sources used by the firmware:

- `game_world.c`, the rigid/granular/Garden worlds, and flash-resident scene
  builders own authoritative state and exact 60 Hz updates;
- `game_snapshot.c` creates the same fixed-size immutable render snapshot;
- `scene_renderer.c` draws that snapshot through the same primitives;
- `graphics_raster.c` owns the same 240 x 240 RGB565 big-endian framebuffer.

Zephyr threads, GPIO, USB, the LCD driver, DMA, tearing-effect synchronization,
and RP2040 core 1 remain outside this boundary. Native runs can therefore prove
model and intended-pixel equivalence, but device builds and measurements remain
authoritative for memory use, deadlines, display throughput, and concurrency.
The raster buffer is process-global and intentionally single-threaded.

## Deterministic command-line runner

Build and replay every committed device sequence under UBSan:

```sh
make host-check
```

Replay one sequence and save its final framebuffer as a PNG:

```sh
make host-run \
  SEQUENCE=scripts/sequences/garden-smoke.json \
  HOST_OUT=artifacts/host-garden.png
```

Run commands directly from left to right:

```sh
make host-cli ARGS="--scene hourglass --step right 60 \
  --step none 120 --action primary --step left 60"
```

The runner emits one JSON object containing scene, tick, authoritative-state
hash, and framebuffer CRC-32. Garden results also include current living/dead
plant and node totals, dormant seeds, cumulative lifecycle/reproduction
counters, maximum generation, and a record for every current lineage. Each
lineage record exposes its ID, parent, generation, offspring count, species,
and eight-trait genome.
`--expect-hash` and `--expect-crc` turn the deterministic values into
assertions; `--output` writes RGB PPM and `--framebuffer` writes the native
RGB565 big-endian bytes. Run `make host-cli ARGS="--help"` for the complete
syntax.

The current Clockwork, directional Hourglass, neutral Hourglass, Marble
Machine, growing Garden, established Garden, unattended Garden lifecycle, and
Garden generation fixtures all match their committed hashes and framebuffer
CRCs exactly on the host. The generation fixture explicitly reaches two living
generation-1 offspring through the ordinary seed bank and germination path.

## Garden profiling

Run the optimized Garden profiler with:

```sh
make host-profile-garden
```

It reconstructs three exact checkpoints: the initial three seedlings, the
mixed manual/automatic garden at tick 930, and an established garden at tick
3,771 after a complete death/reclamation cycle. For each checkpoint it reports
ordinary and 4 Hz ecology-step timing, snapshot and full-raster timing, state
and lifecycle counts, memory size, raster primitive calls, and logical
framebuffer pixel writes. It also advances sixty consecutive presentation
intervals at 30, 10, and 4 Hz and counts changed pixels, changed 8 x 8 tiles,
and the enclosing bounding-box area. For every one of those frames it builds
semantic Garden damage from the last-presented and current snapshots, patches
a retained framebuffer through the production clipped renderer, and requires
the result to match a canonical full render byte for byte. The report includes
damage tiles, coalesced regions, transfer coverage, partial-raster writes, and
planner/raster timing.

The Release build and repetition count are isolated from the sanitizer build.
Override the sample count and output path when needed:

```sh
make host-profile-garden GARDEN_PROFILE_REPETITIONS=64 \
  GARDEN_PROFILE_OUT=artifacts/garden-profile-64.json
```

Timing results depend on the host, container load, compiler, and CPU frequency,
so CI validates the schema and deterministic checkpoints but never imposes a
timing threshold. Work counts and framebuffer deltas are deterministic. Use
PicoSystem profiles for final RP2040 cycle, transfer, stack, and RAM decisions.

## Interactive SDL3 player

On Linux, launch a scene with:

```sh
make host-play ARGS="--scene garden"
```

The first invocation builds SDL 3.4.10 from a checksum-pinned release archive
inside the separate host-player container. The statically linked executable is
then run on the host, so no compiler, headers, or SDL development package is
installed there. Rebuilds reuse Docker and CMake artifacts. Verify the frontend
without opening a desktop window with `make host-player-check`.

The player uses a rational nanosecond accumulator for exact-average 60 Hz game
ticks. Presentation occurs after state changes and is independent of that fixed
step. A bounded eight-tick catch-up limit discards excess wall-clock backlog
rather than allowing an overloaded desktop process to spiral indefinitely.
Pause and single-step avoid wall-clock scheduling entirely.

Controls:

| Host key | PicoSystem behavior |
| --- | --- |
| Arrow keys | D-pad / scene input |
| A | Use the selected Garden tool |
| B | Cycle the selected Garden tool |
| X | Primary scene action; toggle the auto-gardener in Garden |
| Y or R | Reset the current scene |
| Tab | Select the next playable scene |
| 1, 2, 3, 4 | Clockwork, Hourglass, Marble Machine, Garden |
| Space or P | Pause or resume real-time simulation |
| N or `.` | Advance one exact tick while paused |
| Escape | Quit |

The title bar reports the scene, exact tick, run state, and current state hash.
On exit the player prints the final state hash and framebuffer CRC as JSON.

## Browser path

The portable simulator core deliberately has no SDL dependency. A future
Emscripten frontend can provide an HTML canvas and browser input around the
same caller-owned simulator API. That frontend should preserve the fixed-step
accumulator and use the same raw framebuffer rather than introducing another
model or renderer.
