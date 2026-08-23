# PIM559 Hourglass capacity and granular profiling

These measurements were captured on one Pimoroni PicoSystem PIM559 on
2026-08-23. The recommended 62.5 MHz PL022/DMA full-frame image was used, and
the RP2040 ran at 125 MHz. Physics timings cover only the authoritative
granular step; core-1 rendering and display transfer continue independently.

## Capacity and placement

The game world and immutable render snapshot now use scene-tagged unions, so
rigid and granular alternatives share storage. This recovered 6,512 bytes from
the recommended image while increasing granular capacity from 128 to 192:

- the rigid world is 22,636 bytes and the 192-particle granular world is 4,180
  bytes, but the game world pays only for the larger active alternative;
- the immutable snapshot is 856 bytes, with an 820-byte rigid payload and a
  448-byte granular payload sharing the same slot;
- the recommended image uses 251,180 of 261,120 Zephyr RAM bytes, leaving 9,940
  bytes free; the conservative image uses 221,276 bytes and leaves 39,844;
- the recommended image uses 234,744 bytes of flash.

Scenario builders, immutable configuration, and inactive scenario code remain
in XIP flash. No overlay loader is needed. A placement A/B test also showed
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

## Stage profiler

The device command `picosystem profile granular [ticks]`, exposed as
`make profile-granular`, resets a private Hourglass world and replays exact
neutral ticks. The live simulation must be paused first. Each step records 22
timer reads and attributes integration, boundaries, grid construction, pair
solving, passage tracking, unattributed overhead, and total time. Fixed
histograms retain p50/p95/p99 and exact maxima without per-tick logging.
Deterministic work totals expose rejection, contact, correction, wall, and grid
load.

The instrumented, otherwise untouched 192-grain solver established this
same-method baseline. The final rows use the optimized exact solver:

| Replay | Mean | Maximum | 60 Hz violations | Final hash |
| --- | ---: | ---: | ---: | --- |
| 192 grains, baseline, 120 ticks | 22.267 ms | 31.025 ms | 120 / 120 | `5776bdd3` |
| 192 grains, optimized, 120 ticks | 10.644 ms | 13.611 ms | 0 / 120 | `5776bdd3` |
| 192 grains, optimized, 1,000 ticks | 13.688 ms | 14.394 ms | 0 / 1,000 | `fbf44016` |
| 96 grains, optimized, 1,000 ticks | 5.849 ms | 6.236 ms | 0 / 1,000 | `782ba00d` |

Three optimized 120-tick repetitions measured 10.641-10.645 ms mean and
13.470-13.611 ms maximum. All finished with 175 grains below the neck, 175
passages, and hash `5776bdd3`. The longer dense replay finished with all 192
grains below the neck and 2.273 ms of worst-case physics margin.

The stage breakdown shows where the improvement came from:

| 192 grains, 120 ticks | Baseline mean | Optimized mean |
| --- | ---: | ---: |
| Integrate | 0.856 ms | 0.785 ms |
| Boundaries | 5.925 ms | 3.564 ms |
| Grid build | 0.415 ms | 0.424 ms |
| Pair solve | 14.920 ms | 5.708 ms |
| Passage plus other | 0.151 ms | 0.160 ms |
| **Total** | **22.267 ms** | **10.644 ms** |

The final 120-tick replay considered 4,400,640 all-pairs possibilities. The
grid retained 416,649 candidates; exact axis and diagonal tests rejected
371,638 of those before the squared-distance test. The solver resolved 39,701
particle contacts. Boundary code considered 368,616 active planes and safely
rejected 169,071 with a coarse fixed-point bound before the exact dot product.

## Exact optimizations

The final state hash remained unchanged after every optimization:

- axis and conservative diagonal rejection precede the 64-bit distance test;
- axis-aligned walls bypass the generic dot product, while sloped walls use a
  proven coarse fractional-pixel rejection bound;
- contact length squared is calculated once and reused;
- the bounded sub-38-bit contact square root uses 32-bit base-four digits,
  avoiding RP2040 stack spills in the generic 64-bit loop;
- Q12 normals produce the same correction with bounded 32-bit products instead
  of two Q16 64-bit multiplies;
- the two normal components share one short, interrupt-safe use of the
  per-core RP2040 hardware divider; and
- only the granular step is compiled for speed (`-O3`); the rest of the image
  retains its size-oriented build.

Native tests exhaustively check every bounded perfect-square interval endpoint,
compare another 100,000 square roots with an independent reference, and retain
the existing long deterministic world replays. `make check`, both recommended
builds, the 192-grain device profiles, and the 192-grain hash/CRC device
sequences all pass.

The optimized 192-grain scene is now the normal build. `sparse-96.conf` retains
the former population for controlled A/B comparisons, while
`granular-sram.conf` moves the granular step into SRAM for placement experiments.
