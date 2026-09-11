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
eight-trait genome, eight signed lifetime-memory values, selected-action counts,
root/shoot arbitration counts, and its latest accepted decision. The aggregate
Garden record retains equivalent counters across reclaimed plants. The default
policy leaves the memory values at zero; injected policies can use them without
forking the simulation implementation.
`--expect-hash` and `--expect-crc` turn the deterministic values into
assertions; `--output` writes RGB PPM and `--framebuffer` writes the native
RGB565 big-endian bytes. Run `make host-cli ARGS="--help"` for the complete
syntax.

The current Clockwork, directional Hourglass, neutral Hourglass, Marble
Machine, growing Garden, established Garden, unattended Garden lifecycle, and
Garden generation fixtures all match their committed hashes and framebuffer
CRCs exactly on the host. The generation fixture explicitly reaches two living
generation-1 offspring through the ordinary seed bank and germination path.

## Garden policy evaluation

Compare the baseline, adaptive, and fixed neural-reference policies over a
deterministic batch with:

```sh
make host-evaluate-garden
```

The default run gives all three policies the same eight derived seeds in each
of three scenarios: an unassisted three-plant plot, that plot with periodic
irrigation, and a periodically irrigated crowded five-plant plot. Irrigation
uses a fixed whole-plot pattern independent of current plants and seeds, so all
policies receive exactly the same external water while generational success
remains observable. Each trial advances 7,680 ticks, or two complete Garden
day/night cycles.

The command prints a compact comparison and writes the complete report to
`artifacts/garden-evaluation.json`. Raw results include state hashes,
living-plant-time and sampled resource integrals, final and peak population and
node counts, stress, deaths, reclamation, seeds, germination, mutation,
generation, recurrent-memory use, and decision telemetry. The evaluator also
tracks every observed lineage back to its initial founder and partitions
survival, descendant plant-time, established offspring, mortality, maximum
generation, and extinction by both founder and species.

The neural reference is deliberately untrained. It is a stable executable
fixture for the feature contract, recurrent inference, action head, and
context-sensitive candidate scorer—not a claimed improvement over the adaptive
policy. That distinction gives later search runs a fixed control and makes poor
weights visible in the same survival-first report as useful ones.

The report treats evaluation as ordered gates rather than one weighted score:

1. survival, including the first tick at which no living plant or banked seed
   remains;
2. reproduction that produces an established descendant, defined as an
   offspring old enough to have crossed a maintenance boundary while unstressed
   and carrying an active leaf;
3. descendant plant-time and generation depth, which distinguish a persistent
   lineage from a last-tick population spike; and
4. efficiency diagnostics such as resources, decisions, and growth choices.

Deaths are classified by the energy/water shortage flags present at death.
Seed-blocker counters sample seeds left in the bank after each ecology step.
Dormant samples are separated from mature blocked samples; moisture, light,
plant capacity, node capacity, and spacing reasons may overlap. Those are sample
counts, not unique seed counts. There is intentionally no composite fitness
score: future experiments can choose an objective without discarding the
underlying measurements. Trial count, duration, seed, and output path are
overridable:

```sh
make host-evaluate-garden GARDEN_EVAL_TRIALS=32 GARDEN_EVAL_TICKS=15360 \
  GARDEN_EVAL_SEED=0x12345678 GARDEN_EVAL_OUT=artifacts/garden-long.json
```

The simulation and experiment workspaces are fixed-capacity and do not call heap
allocation. Host-only lineage bookkeeping retains 4,096 lineage IDs and rejects
an experiment that exceeds that explicit bound. The maximum accepted 100,000-tick
batch is exercised as a long-run capacity check. The evaluator test executes the
same batch twice under UBSan, requires byte-equivalent JSON, validates global,
species, and founder accounting invariants, rejects invalid limits, and verifies
that matched policies receive identical trial seeds.

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
