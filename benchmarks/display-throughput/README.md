# PIM559 dense-display throughput

This benchmark measures the complete framebuffer-to-ST7789 presentation path
for dense scenes. It separates the cost of transferred pixels from the cost of
splitting those pixels across display windows.

The tracked reports were captured on one Pimoroni PicoSystem PIM559 on
2026-08-17. Every case uses two warm-up frames and 16 measured frames. The game
is paused, a canonical full scene is established, each destructive workload is
run with TE synchronization, and the same canonical scene is redrawn and
CRC-verified before the simulation resumes.

## Workloads

- `band-*` draws one centered, full-width strip. The application submits one
  region, but the current 3,840-byte staging path splits it into 3-30 display
  writes.
- `tiles-*` draws deterministic scattered 24 x 24 tiles and submits each tile
  separately. The 100% case therefore performs 100 display writes.
- `full-100` clears the framebuffer and sends its contiguous 115,200 bytes in
  one display write.

Reported `present` time includes the synchronous Zephyr display call, panel
window commands, buffer packing, SPI setup, DMA setup where applicable, and
payload transfer. `draw` and the preceding TE wait are timed separately. The
configured-bus efficiency compares measured presentation with the payload-only
wire-time floor at the requested SPI clock; it does not claim the controller
sustained that clock continuously.

Framebuffer CRCs validate the software data and restoration path, not pixels
read back from the write-only LCD. The 62.5 MHz image therefore remains a
benchmark variant pending explicit visual stress validation.

## Results

| Transport | Configured clock | Full present | Full draw + present | Full unpaced rate | Full bus efficiency | 50% band present | 50% tiles present |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| PL022 polling | 20 MHz | 80.875 ms | 84.490 ms | 11.84 fps | 57.0% | 47.142 ms | 51.554 ms |
| PL022 polling | 62.5 MHz | 76.782 ms | 80.131 ms | 12.48 fps | 19.2% | 44.701 ms | 49.083 ms |
| PIO/DMA | 20 MHz | 47.568 ms | 50.951 ms | 19.63 fps | 96.9% | 44.572 ms | 84.934 ms |
| PIO/DMA | 31.25 MHz | 30.972 ms | 34.332 ms | 29.13 fps | 95.2% | 36.334 ms | 76.436 ms |
| PL022/DMA | 20 MHz | 70.974 ms | 74.318 ms | 13.46 fps | 64.9% | 51.205 ms | 77.655 ms |
| PL022/DMA | 62.5 MHz | 18.361 ms | 21.759 ms | 45.96 fps | 80.3% | 24.615 ms | 51.702 ms |

The full JSON reports preserve mean, minimum, p50, p95, p99, and maximum timing
for draw, TE wait, present, and total:

- [PL022 polling at 20 MHz](pim559-pl022-20mhz-2026-08-17.json)
- [PL022 polling at 62.5 MHz](pim559-pl022-62_5mhz-2026-08-17.json)
- [PIO/DMA at 20 MHz](pim559-pio-dma-20mhz-2026-08-17.json)
- [PIO/DMA at 31.25 MHz](pim559-pio-dma-31_25mhz-2026-08-17.json)
- [PL022/DMA at 20 MHz](pim559-pl022-dma-20mhz-2026-08-17.json)
- [PL022/DMA at 62.5 MHz](pim559-pl022-dma-62_5mhz-2026-08-17.json)

## Findings

PL022 polling is CPU/feed limited around 1.5 MB/s. Raising its configured clock
from 20 to 62.5 MHz barely changes measured throughput. It remains the best of
the tested stock paths for many tiny regions, which is why it stays the default
for the current dirty-first demo.

PIO/DMA keeps a single contiguous payload close to the configured wire limit,
but Zephyr's four-cycle full-duplex PIO program limits a 125 MHz RP2040 to a
31.25 MHz SPI clock. Its best complete clear-and-present result is therefore
34.332 ms. Repeated DMA setup is expensive: 100 tiles at the same pixel count
take 152.486 ms instead of the contiguous frame's 30.972 ms.

PL022/DMA is the fastest dense path at 62.5 MHz. Its 18.361 ms full present is
already 1.6 ms longer than the measured panel period before any drawing occurs,
and the solid-frame draw adds another 3.398 ms. It also performs poorly on
small transfers because the generic Zephyr driver creates paired TX/RX DMA
transactions for every command and payload.

The evidence points to a size- and shape-aware renderer rather than one global
transport choice:

1. Add a direct one-write fast path for contiguous full-width strips instead of
   copying and submitting every eight rows.
2. Merge aggressively and switch to a full frame when window setup costs more
   than the extra pixels.
3. Prototype a PL022 path that polls short command/dirty transfers but uses DMA
   for a large payload without rebuilding the firmware.
4. Reduce solid-fill and dense-raster cost. At an ideal 62.5 MHz payload rate,
   a 60 Hz sequential full-frame pipeline leaves only about 2.0 ms for all
   drawing and non-payload overhead.
5. If dense 60 Hz remains a requirement, consider a bounded scanline/band
   producer-consumer that overlaps rasterization and DMA. The roughly 72 KiB
   remaining RAM cannot hold a second 115,200-byte framebuffer.

The benchmark also exposed a correctness issue outside its throughput results:
the framebuffer produced by ordinary partial rendering did not always match a
canonical full redraw of the same snapshot. The current renderer rejects
objects that do not intersect a dirty region, but intersecting primitives are
not strictly clipped to that region and can modify software pixels that are not
sent to the LCD. The profiler avoids contaminating its measurements by
canonicalizing before and after every run; clip containment should be fixed
before framebuffer capture is treated as a literal LCD reconstruction.

## Reproduce

Close any interactive console, then build, flash, and profile one variant:

```sh
make update-render-profile \
  DISPLAY_TRANSPORT=pl022-dma DISPLAY_HZ=62500000
make render-profile \
  RENDER_PROFILE_SAMPLES=16 \
  RENDER_PROFILE_OUT=artifacts/render-profile.json
make update  # restore the default 20 MHz PL022 image
```

Accepted transports are `default`, `pio`, `pio-dma`, and `pl022-dma`. Accepted
configured frequencies are 20, 31.25, 41.666667, and 62.5 MHz. The stock PIO
driver rejects values above 31.25 MHz, and the build wrapper enforces that
limit before producing an unusable image.
