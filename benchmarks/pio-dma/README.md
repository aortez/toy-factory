# RP2040 PIO/DMA display benchmark

For the newer multi-coverage and multi-frequency hardware matrix, see the
[dense-display throughput report](../display-throughput/README.md).

This benchmark replaces the PicoSystem's hardware SPI0/PL022 display transport
with Zephyr's `raspberrypi,pico-spi-pio` driver on PIO0. The DMA variant adds
two RP2040 DMA channels using Zephyr's existing PIO SPI DMA support. The default
board definition is unchanged.

Use the isolated build directories through these targets:

```sh
make build-pio
make build-pio-dma
make check-pio-dma
make update-pio
make update-pio-dma
make update          # restore the default PL022 image
```

## PIM559 results

These transport measurements predate the application-owned GP8 tearing-effect
synchronization layer. TE waiting occurs before the timed display call, so the
relative transfer results remain applicable; current images are larger because
they also include signal measurement, bounded waiting, and shell diagnostics.

All variants used the same application, 20 MHz configured display frequency,
240 x 240 RGB565 framebuffer, and 18 x 18 animated dirty region. Full frames
are one contiguous 115,200-byte display write; partial regions continue to use
the bounded eight-row staging buffer. Times cover the synchronous Zephyr
display call. Each image was built cleanly, flashed through the software
bootloader path, and queried over USB CDC on the same PIM559.

| Transport | Flash | RAM | Full present | Typical 18 x 18 present | Main stack high-water |
| --- | ---: | ---: | ---: | ---: | ---: |
| SPI0/PL022 | 115,852 B | 142,620 B | 77,692-77,711 us | 821-839 us | 892 / 2048 B |
| PIO polling | 119,832 B | 142,692 B | 106,429 us | 1,553 us | 1016 / 2048 B |
| PIO plus DMA | 123,324 B | 143,204 B | 47,303-47,351 us | 1,913-1,940 us | 1132 / 2048 B |

All three variants sustained the fixed 62.5 fps update rate with zero skipped
ticks during their steady-state sample. The PIO/DMA image also retained zero
skips while serving twelve back-to-back USB status commands; its worst complete
dirty render during that run was 5,903 us.

Replacing thirty staged writes with one contiguous write reduced full-frame
time from 89,900 to 77,692-77,711 us on PL022, from 130,627 to 106,429 us with
PIO polling, and from 82,297-82,345 to 47,303-47,351 us with PIO/DMA. The
PIO/DMA result is within about 2.8% of the 46,080 us payload wire-time floor at
20 MHz and is about 39% faster than the new PL022 path.

PIO/DMA still makes the normal dirty transfer about 2.3 times slower, adds
7,472 bytes of flash and 584 bytes of RAM, and raises measured main-stack use
by 240 bytes. DMA setup overhead dominates the ST7789's short command/window
transactions. Zephyr's public SPI operation also waits synchronously for DMA
completion, so even the near-wire-speed full update blocks the caller for about
47 ms.

The dirty-first demo therefore retains SPI0/PL022 as its default. A workload
dominated by large contiguous updates should reconsider PIO/DMA, ideally with
a transfer-size threshold or an asynchronous display worker.
