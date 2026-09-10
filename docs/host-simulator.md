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
hash, and framebuffer CRC-32. `--expect-hash` and `--expect-crc` turn those
values into assertions; `--output` writes RGB PPM and `--framebuffer` writes
the native RGB565 big-endian bytes. Run `make host-cli ARGS="--help"` for the
complete syntax.

The current Clockwork, directional Hourglass, neutral Hourglass, Marble
Machine, and Garden fixtures all match their hardware-established hashes and
framebuffer CRCs exactly.

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
