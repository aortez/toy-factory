# Garden profiling

Garden profiling separates deterministic work from machine-dependent time. Run:

```sh
make host-profile-garden GARDEN_PROFILE_REPETITIONS=64
```

The command writes the complete JSON result to
`artifacts/garden-host-profile.json`. CI runs a one-repetition smoke test to
verify its schema, all checkpoint hashes and framebuffer CRCs, and basic timing
and work-count invariants. It deliberately does not gate on host timing.

## Initial host baseline

The first 64-repetition Release run used the pinned Ubuntu builder with GCC
13.3.0 on an AMD Ryzen 7 9800X3D. Back-to-back monotonic clock reads had a 20 ns
median. These medians are reference values for local A/B comparisons, not
RP2040 performance claims:

| Checkpoint | Ordinary step | Ecology step | Snapshot | Full raster |
| --- | ---: | ---: | ---: | ---: |
| Initial, 12 nodes | 40 ns | 591 ns | 50 ns | 3,837 ns |
| Growing, 147 nodes | 150 ns | 1,513 ns | 240 ns | 7,254 ns |
| Mature, 256 nodes | 221 ns | 1,663 ns | 391 ns | 14,107 ns |

The mature full renderer performs 182,138 logical framebuffer pixel writes for
a 57,600-pixel image, plus 2,167 rectangle fills, 257 lines, and 207 circles.
The clear routine writes packed pixel pairs, but the counter reports the two
logical pixels represented by each store. The pixel-write count is only six
percent above the initial scene's 172,113 writes, while the primitive-call count
and host raster time grow much more sharply. This distinguishes redundant
background writes from mature-plant drawing overhead.

## Presentation deltas

The same run compared sixty consecutive frames at three candidate Garden
presentation rates. The authoritative simulation remained at 60 Hz throughout:

| Checkpoint | Presentation | Mean changed pixels | Median / p95 changed pixels | Mean changed 8 x 8 tiles | Zero-change frames |
| --- | ---: | ---: | ---: | ---: | ---: |
| Initial | 30 Hz | 52 | 3 / 254 | 3 | 21 / 60 |
| Initial | 10 Hz | 100 | 6 / 502 | 4 | 15 / 60 |
| Initial | 4 Hz | 106 | 24 / 503 | 4 | 4 / 60 |
| Growing | 30 Hz | 162 | 10 / 983 | 4 | 8 / 60 |
| Growing | 10 Hz | 407 | 97 / 1,165 | 9 | 1 / 60 |
| Growing | 4 Hz | 856 | 802 / 1,280 | 17 | 0 / 60 |
| Mature | 30 Hz | 94 | 9 / 419 | 1 | 29 / 60 |
| Mature | 10 Hz | 268 | 73 / 799 | 5 | 6 / 60 |
| Mature | 4 Hz | 602 | 553 / 954 | 10 | 0 / 60 |

Even at 10 Hz, the mature Garden changes a mean of only 268 pixels across five
8 x 8 tiles while the current path rasterizes and transfers the entire screen.
The wide bounding boxes reported in the JSON are caused by spatially separated
changes, including the header, so a single bounding rectangle would often be a
poor damage representation. Multiple compact regions or tiles deserve
evaluation before adding a large previous-snapshot allocation.

The authoritative PIM559 baseline remains 0.218 ms mean / 3.103 ms maximum for
Garden model work, 12.7-13.0 ms for a mature raster, and 18.387 ms for the
full-frame DMA transfer. Those device figures, rather than host nanoseconds,
decide whether an optimization earns its RAM and complexity cost.
