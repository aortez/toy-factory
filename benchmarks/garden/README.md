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

## Damage reconstruction prototype

The next host prototype adds no retained pixel buffer. It compares the
last-presented and current immutable Garden snapshots, creates a bounded 8 x 8
semantic damage mask, coalesces adjacent tiles into regions, and redraws only
those regions into the existing framebuffer. The planner's own state is about
124 bytes; device integration must separately place the last-presented Garden
history without recreating the earlier renderer-stack squeeze. Every
reconstructed frame is then compared byte for byte with a fresh full render.
The profiler proves 60 frames at each checkpoint and cadence: 540 exact
reconstructions per invocation. A separate UBSan test covers interactive
watering, planting, tool changes, auto-gardener state, cursor motion, and
growth.

A 64-repetition Release run after adding conservative node culling produced:

| Checkpoint | Rate | Plan median | Partial raster median / p95 | Mean tiles | Mean regions | Mean transfer pixels | Mean raster writes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Initial | 30 Hz | 381 ns | 1,413 / 5,711 ns | 6 | 2 | 406 | 1,082 |
| Initial | 10 Hz | 450 ns | 1,593 / 7,023 ns | 7 | 3 | 494 | 1,310 |
| Initial | 4 Hz | 531 ns | 3,647 / 7,084 ns | 11 | 4 | 728 | 1,895 |
| Growing | 30 Hz | 571 ns | 2,285 / 21,501 ns | 7 | 3 | 459 | 1,353 |
| Growing | 10 Hz | 722 ns | 4,579 / 23,735 ns | 12 | 7 | 814 | 2,468 |
| Growing | 4 Hz | 892 ns | 19,387 / 27,131 ns | 23 | 15 | 1,491 | 4,542 |
| Mature | 30 Hz | 762 ns | 1,673 / 12,173 ns | 1 | 1 | 124 | 408 |
| Mature | 10 Hz | 801 ns | 3,096 / 15,279 ns | 5 | 3 | 334 | 1,084 |
| Mature | 4 Hz | 851 ns | 11,202 / 17,794 ns | 10 | 7 | 698 | 2,237 |

At the intended 10 Hz Garden presentation rate, the mature plan covers a mean
334 of 57,600 display pixels (0.58%) and causes about 168 times fewer logical
raster writes than the full renderer. Planning itself has an 801 ns median on
this host. The growing 4 Hz case is an important counterexample: processing 15
small regions has a 19.4 us median, slower than that checkpoint's 7.3 us full
render. Firmware integration therefore needs a measured adaptive threshold
that chooses partial or full presentation from region shape and count.

These are host-relative measurements and exclude LCD transport. The current
PicoSystem firmware still renders and transfers full frames; the prototype
first establishes correctness and exposes the work counts needed to choose a
hardware policy.
