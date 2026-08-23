# PIM559 Hourglass capacity and granular profiling

These measurements were captured on one Pimoroni PicoSystem PIM559 on
2026-08-23. The recommended 62.5 MHz PL022/DMA full-frame image was used, and
the RP2040 ran at 125 MHz. Physics timings cover only the authoritative
granular step; core-1 rendering and display transfer continue independently.

## Capacity and placement

The game world and immutable render snapshot use scene-tagged unions, so rigid
and granular alternatives share storage:

- the rigid world is 22,636 bytes and the 192-particle granular world is 7,540
  bytes, but the game world pays only for the larger active alternative;
- the granular world includes 1,920 one-byte grid heads and 1,920 one-byte
  boundary masks for its 40 x 48 broad-phase grid;
- the immutable snapshot is 856 bytes, with an 820-byte rigid payload and a
  448-byte granular payload sharing the same slot;
- the recommended image uses 251,276 of 261,120 Zephyr RAM bytes, leaving 9,844
  bytes free, while the conservative image uses 221,276 bytes and leaves
  39,844; and
- the recommended and conservative images use 236,060 and 230,348 bytes of
  flash respectively.

Scenario builders, immutable configuration, and inactive scenario code remain
in XIP flash. No overlay loader is needed. An earlier placement A/B test showed
that copying the then-1,452-byte granular step into SRAM was consistently about
4.4% slower and consumed another 1,536 bytes:

| 192-grain placement before solver optimization | Mean | Maximum | 60 Hz violations | RAM |
| --- | ---: | ---: | ---: | ---: |
| XIP flash | 23.393 ms | about 32.5 ms | 120 / 120 | 251,180 B |
| SRAM | 24.433 ms | about 34.1 ms | 120 / 120 | 252,716 B |

The data-heavy granular loop therefore stays in flash. The much larger rigid
solver remains in SRAM in the recommended image: moving it to XIP recovered
20,952 bytes but increased an isolated grid step from 5.798 to 9.092 ms and a
live Clockwork step from 10.329 to 13.788 ms.

## Measurement method

The device command `picosystem profile granular [ticks]`, exposed as
`make profile-granular`, resets a private Hourglass world and replays exact
neutral ticks. The live simulation must be paused first. Each step records 22
timer reads and attributes integration, boundaries, grid construction, pair
solving, passage tracking, unattributed overhead, and total time. Fixed
histograms retain p50/p95/p99 and exact maxima without per-tick logging.
Deterministic work totals expose rejection, contact, correction, wall, and grid
load.

The explicit profiler always collects work counters. Normal gameplay does not:
its hot loops contain no counter updates or work-pointer branches. The optional
[`live-work-counters.conf`](live-work-counters.conf) fragment restores live
counters for controlled diagnostics at a measurable runtime cost.

The original exact-math work established this same-method history:

| Replay | Mean | Maximum | 60 Hz violations | Final hash |
| --- | ---: | ---: | ---: | --- |
| 192 grains, original baseline, 120 ticks | 22.267 ms | 31.025 ms | 120 / 120 | `5776bdd3` |
| 192 grains, exact-math solver, 120 ticks | 10.644 ms | 13.611 ms | 0 / 120 | `5776bdd3` |
| 192 grains, exact-math solver, 1,000 ticks | 13.688 ms | 14.394 ms | 0 / 1,000 | `fbf44016` |
| 96 grains, exact-math solver, 1,000 ticks | 5.849 ms | 6.236 ms | 0 / 1,000 | `782ba00d` |

## Broad-phase and boundary A/B

Three later 1,000-tick replays isolated grid and wall-filter changes. The
all-boundaries variants intentionally test every height-active wall for every
grain. The third variant uses the exact precomputed per-cell boundary masks:

| Counted replay | 8 px grid, all walls | 4 px grid, all walls | 4 px grid, masked walls |
| --- | ---: | ---: | ---: |
| Integrate | 0.727 ms | 0.726 ms | 0.729 ms |
| Boundaries | 5.694 ms | 5.597 ms | 2.396 ms |
| Grid build | 0.428 ms | 0.573 ms | 0.572 ms |
| Pair solve | 8.163 ms | 6.158 ms | 6.145 ms |
| Passage plus other | 0.144 ms | 0.141 ms | 0.142 ms |
| **Total** | **15.156 ms** | **13.196 ms** | **9.983 ms** |
| Maximum | 15.850 ms | 13.782 ms | 10.824 ms |

The corresponding exact work totals explain the timing:

| Work over 1,000 ticks | 8 px grid, all walls | 4 px grid, all walls | 4 px grid, masked walls |
| --- | ---: | ---: | ---: |
| Possible pairs | 36,672,000 | 36,672,000 | 36,672,000 |
| Grid candidates | 4,926,312 | 1,551,177 | 1,551,177 |
| Axis rejections | 4,065,203 | 710,923 | 710,923 |
| Diagonal rejections | 36,552 | 47,511 | 47,511 |
| Exact distance tests | 824,557 | 792,743 | 792,743 |
| Particle contacts | 767,030 | 728,693 | 728,693 |
| Boundary tests | 3,071,974 | 3,071,962 | 236,275 |
| Coarse boundary rejections | 1,478,310 | 1,472,511 | 25,076 |
| Boundary contacts | 90,104 | 90,104 | 90,104 |
| Maximum cell occupancy | 9 | 4 | 4 |

Matching the four-pixel grain diameter with a four-pixel cell reduced pair
candidates by 68.5%. The neighbor traversal remains complete for all possible
contacts. Conservative cell masks then reduced exact/coarse boundary visits by
92.3% while retaining identical state (`02c43e89`) to the 4 px all-walls
reference. Grid size changes deterministic pair visitation order, so its state
differs from the earlier 8 px result (`fbf44016`) even though both are valid
bounded solvers.

The final compact counted replay averaged 10.180 ms, peaked at 10.811 ms, and
had no 60 Hz violations over 1,000 ticks. It finished at `02c43e89`. Its
counter-bearing wrapper is deliberately separate from the smaller production
wrapper, so that absolute number is diagnostic rather than production-loop
overhead.

## Live production result

Warm live windows measured the production path while core 1 rasterized and
transferred full frames:

| Live 192-grain variant | Simulation | Physics mean | Physics max | Skipped | Over budget | Raster mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 8 px grid, all walls, generic circle | 59.3 Hz | 15.728 ms | 24.164 ms | 14 | 335 | 9.876 ms |
| 4 px grid, all walls, generic circle | 60.0 Hz | 14.230 ms | 24.103 ms | 0 | 4 | 9.873 ms |
| 4 px grid, masked walls, generic circle | 60.0 Hz | 10.927 ms | 13.124 ms | 0 | 0 | 9.813 ms |
| 4 px grid, masked walls, radius-2 circle | 60.0 Hz | 10.955 ms | 14.278 ms | 0 | 0 | 8.998 ms |
| **Final compact production path** | **60.0 Hz** | **10.465 ms** | **13.492 ms** | **0** | **0** | **9.030 ms** |

The table's controlled final window leaves about 6.2 ms of mean physics
headroom in each 16.667 ms simulation tick. A subsequent 23,601-tick acceptance
window confirmed 60.0 Hz with zero skipped or over-budget updates: physics
averaged 10.860 ms and peaked at 14.573 ms, while complete updates averaged
11.036 ms and peaked at 14.587 ms. Core-1 rasterization averaged 9.050 ms,
full-frame transfer took 18.471 ms, and presentation held 29.8 fps. The longer
run therefore retained about 5.8 ms of mean and 2.1 ms of worst-observed physics
headroom.

The radius-two drawing specialization emits the generic midpoint circle's
exact final five spans directly instead of performing eight writes with three
overlaps. An isolated core-1 verification render fell from 11.227 to 9.654 ms,
with identical pixels and CRC-32 `33aa52af`. The compact production/profile
split then removed 6,656 bytes of duplicated flash code and improved live
physics by another 0.490 ms compared with the first fully inlined version.

## Exact optimizations and validation

The complete dense solver now combines:

- axis and conservative diagonal rejection before the 64-bit distance test;
- axis-aligned wall handling and a proven coarse fractional-pixel bound for
  sloped walls;
- one reused contact-length square and a bounded 32-bit base-four square root;
- Q12 normals with bounded 32-bit correction products;
- one short, interrupt-safe use of the per-core RP2040 hardware divider for
  both normal components;
- a diameter-sized spatial grid with complete neighboring-cell traversal;
- conservative precomputed boundary masks, with edge cells deliberately
  testing every wall because out-of-grid positions fold into those cells; and
- compact counted and counter-free wrappers sharing the same contact math.

Only the granular step is compiled for speed (`-O3`); the rest of the image
retains its size-oriented build.

Native tests compare the masked solver with an all-boundaries profiled
reference on every one of 3,000 ticks, including containment and exact state
hashes. They also exhaustively check every bounded perfect-square interval
endpoint, compare another 100,000 square roots with an independent reference,
and retain the long deterministic world replays.

`make check`, the pristine recommended build, and both device sequences pass.
The 600-tick neutral replay reaches hash `f9de5870` and framebuffer CRC-32
`ef323e84`; the directional/flip replay reaches tick 360 at `20b82113` and
`cecc86d5`. `sparse-96.conf` retains the former grain population for A/B
comparisons, while `granular-sram.conf` retains the placement experiment.
