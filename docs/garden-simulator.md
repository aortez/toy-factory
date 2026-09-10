# Garden Simulator design

[GitHub issue #4](https://github.com/aortez/toy-factory/issues/4) is the living
milestone tracker. This document records the implementation contract that must
remain synchronized with the native and device tests.

![A mature Garden running on the PicoSystem](images/garden.png)

## Scope

Garden is a deterministic side-view pocket terrarium. Its variety comes from
two coupled resources and three parameterized growth forms rather than a large
collection of unrelated subsystems:

- water enters a coarse soil field, travels downward, diffuses sideways,
  evaporates, and is absorbed by roots;
- a deterministic moving sun casts light through the canopy along slanted
  integer rays, so established plants shade later growth and daylight varies
  over time;
- flower, shrub, and ground-cover species vary their cadence, costs, branching,
  height, root reach, leaf density, shade, and horizontal tendency;
- per-plant deterministic traits add lean and vigor without dynamic content or
  unstable random ordering.

Insects, disease, nutrients, reproduction, persistence, and rigid-body stems
remain outside the initial scope.

## Fixed-capacity state

[`garden_world.c`](../src/garden_world.c) has no Zephyr, renderer, allocation,
or wall-clock dependency. Its caller-owned state is 3,496 bytes and contains:

- eight plant records and a shared pool of 256 ten-byte plant nodes;
- a 28 x 11 byte soil-moisture field covering eight-pixel cells;
- a derived 28 x 14 byte canopy-light field; the sun itself is derived from
  the ecology tick and consumes no persistent world storage;
- cursor, selected-tool, automatic-policy, deterministic-random, cadence, and
  bounded diagnostic counters.

Every node refers only to an earlier parent. Stems and roots share the pool;
leaf, flower, active-tip, pending-branch, and pruning state are flags on a node.
Pool exhaustion stops further growth without reallocating or corrupting the
existing garden.

The authoritative loop remains 60 Hz. Node interpolation and cursor input run
at that cadence, while moisture, light collection, and growth advance every 15
ticks, producing a 4 Hz ecology update. Cursor input moves immediately on a new
direction, then uses a deterministic delay and repeat rate while held.

The 256-ecology-tick sun cycle lasts 64 seconds. Reset begins at noon; the sun
moves toward sunset, remains at minimum ambient strength overnight, then moves
from sunrise back to noon. Its signed Q4 ray slope ranges from -0.75 to +0.75
canopy cells per row. Each target cell traces toward the source and accumulates
the opacity of leaves it crosses, clamping at a nonzero ambient floor. This is
bounded integer work with no trigonometry or allocation.

## Growth and tools

A new seed creates one soil-line base, one shoot tip, and two root tips. Roots
choose among bounded downward steps using nearby moisture. Shoots choose among
five upward steps using canopy light, species tendency, stored lean, and a
stable per-plant random stream. Selected depths schedule at most one secondary
branch. Leaves collect energy and cast shade; terminal tips flower after their
species threshold.

The player-facing controls are:

- D-pad: move the garden cursor;
- A: apply the selected seed, water, or prune tool;
- B: select the next tool;
- X: toggle the auto-gardener;
- short/long Y: reset or select the next scene, as in every playable scene.

Pruning pinches a nearby live shoot tip rather than deleting graph storage. Its
next segment turns outward, which redirects the visible form without requiring
a free list or invalidating child indexes.

## Agent boundary

Growth decisions now cross a versioned, fixed-capacity observation/proposal
boundary. An 88-byte observation describes one active tip, its parent-relative
orientation, the plant's energy, water, age, and morphology totals, and up to
five canonical growth candidates. Each candidate reports its endpoint, local
light or moisture, bounded clearance, and nearby own/foreign tissue. Three
bytes that previously served as alignment padding now report sun phase,
strength, and signed ray slope. A 12-byte proposal selects an action, supplies
a priority for later arbitration, and ranks the candidate indexes without
receiving mutable world access.

The original hand-authored policy is the first consumer of this interface. The
world still chooses the alternating root/shoot opportunity, validates the
proposal, pays resource costs, and performs every mutation. The same boundary
now exposes directional light without increasing its 88-byte size. This
establishes a testable baseline before adding plant-level recurrent state,
multiple-tip bidding, or a quantized learned policy.

## Auto-gardener

The auto-gardener is an ordinary deterministic policy, not a privileged state
editor. It chooses a target, visibly moves the same cursor, selects an ordinary
tool, and calls the same planting, watering, or pruning operation exposed to
manual control. Fixed priority and rotating scan origins make ties reproducible.
It establishes a five-plant mixture, waters low-resource plants, and
occasionally pinches a mature tip in deep shade.

This gives the idle toy an autonomous mode and supplies a long-running workload
for capacity, determinism, and rendering tests.

## Presentation and validation

The renderer receives a 1,604-byte garden payload inside the existing
scene-tagged snapshot union. Each rendered node is five bytes: position,
backward parent distance, growth progress, and packed style. The complete
immutable snapshot remains 1,640 bytes because the sun phase, strength, and
slope occupy former tail padding. Soil moisture is copied directly; the
392-byte derived light field is not duplicated. A small sun marker makes the
cycle visible. Garden uses the established 30 Hz full-frame path while ecology
and input remain authoritative at 60 Hz.

The host prototype now treats that framebuffer as a pixel cache. A bounded
semantic planner compares the last-presented and current Garden snapshots,
marks conservative 8 x 8 damage tiles for visible moisture bands, cursor and
automation state, header text, and old/new plant geometry, then coalesces equal
horizontal runs across rows. The planner itself needs only a 30-row bit mask
plus iterator state; it does not allocate a second framebuffer. Firmware
integration will also need a last-presented Garden history, whose placement
must be chosen against the renderer's measured stack and shared-memory budget.
Across initial, growing, and mature checkpoints at 30, 10, and 4 Hz, 540
reconstructed frames match full renders exactly. Firmware still uses
full-frame presentation until device measurements establish an adaptive
partial/full cutoff.

The strict-warning/UBSan native suites currently cover invalid inputs, spacing,
plant and node capacity, downward water travel, evaporation, cursor repeat,
tool cycling, pruning, distinct species growth, exact paired replays, and a
five-minute automatic soak. The mixed device-sequence fixture waters the plot,
plants another flower, enables automation, and advances 930 exact ticks to host
hash `de69461d` and framebuffer CRC-32 `7cf1bee7`. Continuing the same state to
the mature tick-3,771 checkpoint produces 225 nodes, hash `f5df2b20`, and
CRC-32 `0008203d`. Host-side full and damage-region rasterization agrees exactly
across every tested sun phase, and the PIM559 reproduces both revised hashes and
framebuffer checksums exactly.

In a 32-repetition optimized host profile, median ecology steps ranged from
1.944 to 6.312 microseconds across the three checkpoints, and the slowest
observed step was 9.608 microseconds. On the PIM559, an ensuing 5,698-tick
real-time window with 236 nodes maintained 60.0 Hz with no skipped or
over-budget updates. Complete updates averaged 0.686 ms and peaked at 5.923 ms;
world/model work averaged 0.305 ms and peaked at 5.154 ms.

The first Garden-capable image booted on the PIM559, but its Hourglass startup
run reached 4,956/5,120 bytes on the renderer stack. Adding the larger snapshot
had expanded both current and previous snapshots, and inlining reserved the
dirty-region scratch on full-frame calls too. The renderer now stores only an
836-byte rigid-scene damage history and isolates the 1,040-byte dirty-region
call frame. The compiler reports a 2,552-byte renderer entry frame, down from
4,344 bytes, with no increase in static RAM or configured stack size. The
game-demo translation unit emits stack-usage reports and fails compilation if
an individual frame exceeds 3,072 bytes. On the PIM559, main, renderer, and
core-1 stack high-water marks reached 4,256/5,120, 3,164/5,120, and 360/4,096
bytes respectively.

In the preceding vertical-light build, a full 256-node, 2,467-tick device
window maintained 60.0 Hz simulation and 29.6 fps presentation without skipped
or over-budget updates. Complete updates averaged 0.616 ms and peaked at 3.623
ms. Mature-scene rasterization took 12.7-13.0 ms and the final DMA transfer took
18.387 ms, so full-screen presentation—not ecology—is the limiting path. With the shared
clipped Garden renderer, the fast image uses 255,172 bytes of Zephyr RAM and
253,812 bytes of flash, leaving 5,948 bytes of linked RAM plus the separately
reserved 8 KiB core-1 area.

Physical playtesting confirmed that manual planting, watering, pruning, tool
selection, reset, and the visible auto-gardener behave smoothly on the PIM559.
The directional-light revision also passed both exact device replays and a
coherent framebuffer capture on the PIM559.

Pruning uses a 32-bit squared distance: opposite corners can exceed 65,535
square pixels. A native regression verifies that a distant tip cannot appear
nearby through 16-bit wraparound and that a rejected prune preserves state.

## Prototype boundary

The first version deliberately favors bounded behavior over a finished-game
progression. The shared node pool never reclaims storage, so reaching 256 nodes
ends further growth until reset. Branches use a small set of integer steps,
nearby leaves can merge into dense circular clusters, and soil moisture is a
visibly coarse field. Tool identity is communicated primarily by cursor color,
with no plant inspection or resource overlay. These are presentation and
progression follow-ups rather than determinism or performance failures. The
host profiler now reconstructs initial, growing, and mature Gardens and measures
model, snapshot, raster, primitive-work, framebuffer-delta, and exact semantic
damage behavior without requiring the PicoSystem.
