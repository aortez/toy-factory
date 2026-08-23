# PIM559 Hourglass capacity and granular profiling

These measurements were captured on one Pimoroni PicoSystem PIM559 on
2026-08-23. The recommended image uses the 62.5 MHz PL022/DMA full-frame path,
and the RP2040 runs at 125 MHz. Isolated timings cover only the authoritative
granular step; live timings include contention from core-1 rasterization and
display DMA but still report physics and snapshot publication separately.

## Capacity and memory

The fixed engine capacity is 512 grains. The normal Hourglass packs 320
two-pixel-radius grains at four-pixel spacing. Three Kconfig fragments preserve
controlled alternatives:

- [`sparse-96.conf`](sparse-96.conf): the original sparse comparison;
- [`dense-192.conf`](dense-192.conf): the previous normal population; and
- [`dense-384.conf`](dense-384.conf): the current stretch workload.

The game world and immutable render snapshot use scene-tagged unions, so rigid
and granular alternatives share storage:

- the rigid world is 22,636 bytes, the 512-particle granular world is 16,480
  bytes, and the complete tagged game world remains 22,704 bytes;
- the granular scratch grid contains 1,920 16-bit heads and 1,920 one-byte
  boundary masks, plus 512 16-bit particle links and a 512-entry occupied-cell
  list;
- the immutable snapshot is 1,128 bytes, with a 1,088-byte granular payload and
  an 820-byte rigid payload sharing the same slot;
- the recommended image uses 251,836 of 261,120 Zephyr RAM bytes, leaving 9,284
  bytes, while the conservative image uses 221,820 and leaves 39,300 bytes; and
- the recommended and conservative images use 236,080 and 230,352 bytes of
  flash respectively.

Scenario builders, immutable configuration, and inactive scenario code execute
directly from XIP flash. No overlay loader is needed. A controlled 384-grain
placement experiment before the final radial-correction change moved about
3,104 bytes of granular code into SRAM, reduced linker headroom to 6,180 bytes,
and made the isolated replay slower: 16.047 ms instead of 15.597 ms. The
granular loop therefore remains in flash. The much larger rigid solver retains
its independently measured SRAM placement in the recommended image.

## Measurement method

`picosystem profile granular [ticks]`, exposed as `make profile-granular`,
resets a private Hourglass and replays exact neutral ticks while the live game
is paused. Each step records 22 timer reads and attributes integration,
boundaries, grid construction, pair solving, passage tracking, unattributed
overhead, and total time. Fixed histograms retain p50/p95/p99 and exact maxima
without per-tick logging. Deterministic work totals expose rejection, contact,
correction, wall, and grid load.

The explicit profiler always collects work counters. Normal gameplay does not:
its hot loops contain no counter updates or work-pointer branches. The optional
[`live-work-counters.conf`](live-work-counters.conf) fragment restores live
counters for diagnostic runs at a measurable runtime cost.

## Scaling result

The original exact-math work established the 192-grain baseline. Subsequent
rows show the path used to reach the denser packings. All are 1,000-tick device
replays unless stated otherwise.

| Population and solver | Pair solve mean | Total mean | Maximum | 60 Hz violations |
| --- | ---: | ---: | ---: | ---: |
| 192, original implementation, 120 ticks | — | 22.267 ms | 31.025 ms | 120 / 120 |
| 192, optimized exact math | — | 13.688 ms | 14.394 ms | 0 / 1,000 |
| 320, bounded Newton length | 9.488 ms | 13.847 ms | — | 0 / 1,000 |
| **320, final shared radial correction** | **8.380 ms** | **12.568 ms** | **13.118 ms** | **0 / 1,000** |
| 384, bounded Newton length | 11.432 ms | 16.403 ms | — | 728 / 1,000 |
| 384, seven-projection length and two normal divides | 10.657 ms | 15.597 ms | — | 0 / 1,000 |
| 384, shared radial scale with runtime component divisors | 10.485 ms | 15.479 ms | 16.240 ms | 0 / 1,000 |
| **384, shared radial scale with constant component shifts** | **10.020 ms** | **15.037 ms** | **15.777 ms** | **0 / 1,000** |

The final 384-grain replay ended at deterministic granular hash `23b75eb0`.
Its stage means were 1.471 ms integration, 2.376 ms boundaries, 0.892 ms grid
construction, 10.020 ms pair solving, 0.175 ms passage tracking, and 0.102 ms
other work.

Its exact accumulated work explains where time remains:

| Work over 1,000 ticks | Total | Maximum in one tick |
| --- | ---: | ---: |
| Possible unordered pairs | 147,072,000 | 147,072 |
| Grid candidates | 3,645,798 | 3,910 |
| Axis rejections | 1,763,709 | 2,736 |
| Diagonal rejections | 105,924 | 343 |
| Squared-distance tests | 1,776,165 | 1,998 |
| Particle contacts | 1,692,077 | 1,923 |
| Position corrections | 1,819,107 | 2,050 |
| Boundary tests | 326,834 | 502 |
| Boundary contacts | 127,030 | 168 |
| Occupied grid cells | 601,440 | 768 across both passes |
| Maximum cell occupancy | — | 7 |

The grid retained only 2.48% of the brute-force possible pairs. More than 46%
of those candidates were true contacts in the compacted material, so further
broad-phase rejection alone cannot remove most of the remaining pair cost.

## Live 384-grain stretch result

After an isolated profile, a fresh 2,013-update live window ran with core 1
rasterizing and DMA transferring full frames. It skipped no simulation ticks,
never exceeded backlog one, and averaged 15.267 ms of physics plus 0.250 ms of
snapshot work. Physics peaked at 17.869 ms and complete updates at 18.343 ms;
105 updates (5.2%) exceeded the 16.667 ms budget, with the scheduler recovering
on the following update. Core-1 rasterization was about 10.45 ms.

This demonstrates that 384 grains are playable at the exact 60 Hz scheduler
rate, but it leaves little capacity for additional gameplay. The normal build
therefore stays at 320 grains, preserving the 384 packing as an explicit
stress test rather than silently reducing solver quality or simulation rate.

A subsequent 12,837-tick live 320-grain acceptance window held 60.0 Hz with
zero skipped ticks, one over-budget update, and backlog two. Physics averaged
12.799 ms and peaked at 16.453 ms; complete updates averaged 13.042 ms and
peaked at 16.904 ms. That retains about 3.9 ms of mean physics headroom for
gameplay work.

## Final implementation

The dense solver now combines:

- 16-bit grid links and counters beyond particle index 255, with fixed capacity
  for 512 grains;
- sparse head clearing through a bounded occupied-cell list;
- cell-centric pair traversal that handles in-cell pairs and one canonical half
  of neighboring cells exactly once, alternating order on the second pass;
- axis and conservative diagonal rejection before the exact 64-bit
  squared-distance contact test;
- conservative precomputed per-cell boundary masks and a direct set-bit walk;
- the maximum of seven fixed-point unit-vector projections for contact length,
  producing an inscribed-polygon estimate within 0.28% of Euclidean length;
- one shared radial correction quotient from the interrupt-safe per-core RP2040
  hardware divider; and
- compile-time 8,192/4,096 component scales whose signed divisions lower to
  shifts in the ARMv6-M machine code.

The conservative length can slightly over-separate a contact, but it never
misses a contact because the preceding squared-distance test remains exact.
The shared correction is rounded outward; its extra component correction is at
most 1/8,192 of contact length for the normal radius-two grains. Compile-time
range assertions cover every projection, dividend, and signed product.

Rejected A/B variants remain useful constraints on future work. A fully
quantized face normal was faster in isolation but could leave a grain outside a
corner; adding a generic containment restart erased the gain. One solver pass
failed deep/angular separation and long-run containment. Copying the complete
granular step to SRAM increased both RAM use and execution time. Those options
were removed rather than leaving unproven switches in production code.

## Validation

Native tests exercise the default 320-grain and explicit 384-grain six-thousand
tick drains with undefined-behavior sanitization. They compare the masked
solver with an all-boundaries reference for every one of 3,000 ticks, including
field equality and authoritative hashes. Additional coverage includes exact
capacity rejection at 512, a contact involving particle index 256, coincident
and deep/angular overlaps, and exhaustive axes, a dense bounded grid, and
100,000 randomized comparisons of the polygon length with an independent
integer-square-root reference.

The recommended and conservative firmware images link successfully with 9,284
and 39,300 bytes of Zephyr RAM headroom. Device acceptance includes the
isolated profile above, live scheduler metrics, physical tilt/flip/reset play,
and the repository's exact USB-controlled state/framebuffer sequences.
The normal directional/flip sequence reaches tick 360 at state hash `a0919f8b`
and framebuffer CRC-32 `41e4cdd1`; its 600-tick neutral replay reaches
`82da7b6c` and `3e3e0901`.
