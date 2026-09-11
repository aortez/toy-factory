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
- a compact per-plant genome perturbs growth rate, root/shoot allocation,
  resource seeking, branching, stature, reserves, and seed dispersal without
  dynamic content or unstable random ordering.

Insects, disease, nutrients, persistence, and rigid-body stems remain outside
the current scope. Resource maintenance, stress, reproduction, death, and
decomposition are part of the authoritative simulation.

## Fixed-capacity state

[`garden_world.c`](../src/garden_world.c) has no Zephyr, renderer, allocation,
or wall-clock dependency. Its caller-owned state is 4,340 bytes and contains:

- eight plant records, including eight bytes of lifetime policy memory and 40
  bytes of derived decision telemetry each, and a shared pool of 256 ten-byte
  plant nodes;
- a dense eight-entry dormant-seed bank with compact genomes and lineage IDs;
- a 28 x 11 byte soil-moisture field covering eight-pixel cells;
- a derived 28 x 14 byte canopy-light field; the sun itself is derived from
  the ecology tick and consumes no persistent world storage;
- cursor, selected-tool, automatic-policy, deterministic-random, cadence,
  lifecycle state, and bounded cumulative diagnostic counters.

Every node refers only to an earlier parent. Stems and roots share the pool;
leaf, flower, active-tip, pending-branch, and pruning state are flags on a node.
Pool exhaustion stops further growth without reallocating or corrupting the
existing garden.

The authoritative loop remains 60 Hz. Node interpolation and cursor input run
at that cadence, while moisture, light collection, decomposition, and growth
advance every 15 ticks, producing a 4 Hz ecology update. Plants pay maintenance
every four ecology updates, or once per second. Cursor input moves immediately
on a new direction, then uses a deterministic delay and repeat rate while held.

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
branch. Leaves begin collecting energy and casting shade after a fixed visible
growth threshold; terminal tips flower after their species threshold.

Each plant also carries eight signed one-byte traits in the range -2 through
+2. Species parameters remain immutable templates in flash; the genome is only
a compact set of offsets around that template. Traits influence growth cadence,
shoot allocation, light and water seeking, branch spacing, shoot/root stature,
night reserves, and dispersal. The complete genome is included in the agent
observation, so a later learned policy can act on the same inherited state.

A mature flower may produce one seed after paying bounded energy and water
costs while retaining its strategy-adjusted reserve and enough resources for a
complete normal night. The flower is then marked as spent. Seeds disperse a
bounded horizontal distance, remain dormant for eight ecology ticks (two
seconds), and expire after 256 ecology ticks (64 seconds). A dormant seed
germinates only when its surface soil has sufficient moisture, the bottom
canopy row has sufficient light, plant spacing is valid, and fixed plant/node
capacity is available. Mutation is deterministic: three quarters of new seeds
change exactly one trait by one bounded step. Every plant has a monotonic
lineage ID, parent lineage, generation, and offspring count; cumulative seed,
germination, expiration, and mutation counters survive parent reclamation.

Each one-second maintenance event costs one energy unit per eight total nodes
and one water unit per eight shoot nodes, rounded up. A failed payment records
which resource was short and increments plant stress; a successful event heals
one stress point. Stress reaching eight kills a plant; without a recovery, that
takes eight seconds. The baseline growth policy keeps a forty-maintenance-period
reserve at minimum ambient light. The adaptive policy starts preserving that
reserve as daylight fades, allowing a healthy plant to cross the normal night
instead of spending its reserves on blind growth.

Dead tissue stops collecting resources and growing, changes to a brown palette,
then disappears from the tips inward over roughly 12--16 seconds. Once every
node is gone, an in-place stable compaction returns the whole plant and all of
its nodes to the fixed pools. A transient 256-byte old-to-new node map repairs
parent and plant references; there is no heap, free list, or persistent second
pool.

The player-facing controls are:

- D-pad: move the garden cursor;
- A: apply the selected seed, water, or prune tool;
- B: select the next tool;
- X: toggle the auto-gardener;
- short/long Y: reset or select the next scene, as in every playable scene.

Pruning pinches a nearby live shoot tip rather than deleting graph storage. Its
next segment turns outward, which redirects the visible form without requiring
a free list or invalidating child indexes.

## Agent boundary and adaptive policy

Growth decisions cross a versioned, fixed-capacity observation/decision
boundary. A 104-byte observation describes one active tip, its parent-relative
orientation, the plant's energy, water, age, morphology totals, stress,
maintenance costs and phase, recent resource income, plant status, and up to
five canonical growth candidates. Each candidate reports its endpoint, local
light or moisture, bounded clearance, and nearby own/foreign tissue. The
observation also reports sun phase, strength, and signed ray slope. A 12-byte
proposal selects an action, supplies a priority for later arbitration, and
ranks the candidate indexes without receiving mutable world access. A complete
20-byte decision pairs that proposal with the plant's next eight-byte signed
memory vector.

The world owns that lifetime memory and passes its current value immutably to a
caller-supplied pure callback. It validates the callback's proposal before
transactionally committing its next memory, private random stream, and tip
cursor; rejected or failed decisions commit none of those fields. Memory is
not heritable: a germinated offspring starts with zero memory while receiving
its parent-derived genome. Nonzero memory participates in the authoritative
state hash and is exposed by the host lineage diagnostics.

The original hand-authored policy remains available as an explicit A/B oracle.
It carries memory through unchanged and uses the original phased root/shoot and
round-robin tip selection. Normal Garden updates use the adaptive policy. Its
eight memory channels smooth energy pressure, water pressure, stress, recent
energy income, recent water income, and local crowding while tracking lifetime
root/shoot allocation and consecutive choices. Those signals, current
morphology, inherited shoot bias, shortages, and candidate quality determine a
bounded integer priority. A three-leaf establishment bias strongly favors shoot
growth until a seedling can collect useful light.

Adaptive plants use all-tip arbitration: every active root and shoot tip bids
against the same immutable memory and deterministic random nonce. The world
scans from a stable rotating origin, resolves equal priorities by that order,
and commits only the winning decision's memory, random advance, and tip cursor.
Terminal and physically blocked tips bid to finish, and low-light proposals may
wait to protect maintenance reserves. Any callback error or invalid proposal
rejects the whole plant decision without leaking private state. The world
remains the sole authority for resource costs and graph mutation, so this same
path can later host a quantized learned policy without creating a second
simulation.

Every accepted selected decision increments saturating per-plant and cumulative
telemetry: extend/wait/finish, root/shoot arbitration wins, root/shoot extend
choices, and the most recent tip, action, and priority. Invalid callback output
does not leak into either telemetry or policy state. Per-plant counters disappear
when that plant is reclaimed, while the world aggregate survives reclamation.
These diagnostics are deliberately excluded from the authoritative hash, so
observability does not redefine simulation identity.

A fixed-capacity host evaluator runs the original baseline and normal adaptive
policies against identical seeds in unassisted, irrigated, and crowded plots.
It reports survival as the first gate, established reproduction as the second,
then descendant plant-time, generation depth, resources, memory, and decision
measurements rather than imposing one fitness function. Persistent lineage IDs
let the host partition those results by species and initial founder even after
dead plants and their nodes have been compacted out of the live world. Death
causes and sampled seed-germination blockers expose why a candidate failed, not
just its final population.
`make host-evaluate-garden` prints the comparison and stores the full trial report in
`artifacts/garden-evaluation.json`; see the [host simulator guide](host-simulator.md)
for its exact experiment contract.

## Auto-gardener

The auto-gardener is an ordinary deterministic policy, not a privileged state
editor. It chooses a target, visibly moves the same cursor, selects an ordinary
tool, and calls the same planting, watering, or pruning operation exposed to
manual control. Fixed priority and rotating scan origins make ties reproducible.
It establishes a five-plant mixture, waters low-resource plants, and
occasionally pinches a mature tip in deep shade. Below that population target,
it waters a viable dormant seed before buying another seedling, allowing
natural offspring to claim reclaimed space.

This gives the idle toy an autonomous mode and supplies a long-running workload
for capacity, determinism, and rendering tests.

## Presentation and validation

The renderer receives a 1,622-byte garden payload inside the existing
scene-tagged snapshot union. Each rendered node is five bytes: position,
backward parent distance, growth progress, and packed style. Each dormant seed
uses two bytes for its screen column and packed species/dormancy style. The
complete immutable snapshot is 1,664 bytes. Soil moisture is copied directly;
the 392-byte derived light field and authoritative genomes are not duplicated.
A small sun marker makes the cycle visible. Garden uses the established 30 Hz
full-frame path while ecology and input remain authoritative at 60 Hz.

The host prototype now treats that framebuffer as a pixel cache. A bounded
semantic planner compares the last-presented and current Garden snapshots,
marks conservative 8 x 8 damage tiles for visible moisture bands, cursor and
automation state, header text, and old/new plant geometry, then coalesces equal
horizontal runs across rows. The planner itself needs only a 30-row bit mask
plus iterator state; it does not allocate a second framebuffer. Firmware
integration will also need a last-presented Garden history, whose placement
must be chosen against the renderer's measured stack and shared-memory budget.
Across initial, growing, and established checkpoints at 30, 10, and 4 Hz, 540
reconstructed frames match full renders exactly. Firmware still uses
full-frame presentation until device measurements establish an adaptive
partial/full cutoff.

The strict-warning/UBSan native suites currently cover invalid inputs, spacing,
plant and node capacity, downward water travel, evaporation, cursor repeat,
tool cycling, pruning, distinct species growth, exact paired replays, healthy
night survival, reversible resource stress, dry death, graph compaction, twelve
death/replant cycles without leakage, reproduction costs, single-trait bounded
mutation, seed dormancy/expiry, germination, parent-child lineage, exact seed
damage rendering, recurrent-memory carry/reset/hash behavior, pressure-sensitive
adaptive choices, memory bounds, shared-input all-tip bidding, winner-only
commit, injected-policy determinism and rejection, and a five-minute automatic
soak. The mixed sequence fixture waters the plot, plants another flower,
enables automation, and advances 930 exact ticks to five plants, 137 nodes,
four blooms, and one dormant seed at hash `dc82ca95` and framebuffer CRC-32
`c96704e4`. Continuing the same state to tick 3,771 reaches five healthy plants,
189 nodes, 15 blooms, and five dormant seeds at hash `3da95d0b` and CRC-32
`37bcf2aa`.

A separate unaided lifecycle fixture reaches tick 4,530 with two living plants,
one visibly decomposing plant, two cumulative deaths, and one reclaimed 25-node
plant at hash `43930afa` and CRC-32 `5c1d934a`. The generation fixture applies
the same pressure before enabling automation, then continues through tick 8,430
with six living plants, seven produced seeds, one germination, three expirations,
six mutations, and one living generation-one offspring. It reaches hash
`cf48b126` and CRC-32 `c836f83a`. UBSan host runs reproduce all four checkpoints
exactly. The PIM559 also reproduced the short mixed fixture and complete
generation fixture's final hashes and framebuffer CRCs exactly.

In a 32-repetition optimized host profile, median ecology steps ranged from
6.201 to 8.446 microseconds across the three checkpoints, and the slowest
observed step was 18.285 microseconds. The established checkpoint's 8.446
microsecond median is about 16% above the preceding phased-policy baseline. On
the PIM559 after the generation replay, a 412-tick live window maintained 60.0
Hz with no skipped or over-budget updates. Complete updates averaged 0.890 ms
and peaked at 10.851 ms; world/model work averaged 0.452 ms and peaked at 10.268
ms. Full-frame presentation held 29.3 fps; the last/maximum core-1 raster times
were 11.742/12.055 ms and the last display transfer took 18.372 ms.

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
18.387 ms, so full-screen presentation—not ecology—is the limiting path. With
the shared clipped Garden renderer, the fast adaptive-policy image uses 255,612
bytes of Zephyr RAM and 261,588 bytes of flash, leaving 5,508 bytes of linked
RAM plus the separately reserved 8 KiB core-1 area.

Physical playtesting confirmed that manual planting, watering, pruning, tool
selection, reset, and the visible auto-gardener behave smoothly on the PIM559.
The directional-light revision also passed both exact device replays and a
coherent framebuffer capture on the PIM559.

Pruning uses a 32-bit squared distance: opposite corners can exceed 65,535
square pixels. A native regression verifies that a distant tip cannot appear
nearby through 16-bit wraparound and that a rejected prune preserves state.

## Prototype boundary

The current version deliberately favors bounded behavior over a finished-game
progression. Whole-plant reclamation recovers the shared pool, but individual
pruning still redirects growth instead of freeing arbitrary subtrees. Branches
use a small set of integer steps, nearby leaves can merge into dense circular
clusters, and soil moisture is a visibly coarse field. Tool identity is
communicated primarily by cursor color, with no plant inspection or resource
overlay. Nutrients, richer inspection channels, and a quantized learned policy
remain future simulation layers. The host profiler reconstructs
initial, growing, and established Gardens and measures model, snapshot, raster,
primitive-work, framebuffer-delta, and exact semantic damage behavior without
requiring the PicoSystem.
