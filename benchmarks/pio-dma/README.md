# RP2040 PIO/DMA display benchmark

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

All variants used the same application, 20 MHz configured display frequency,
240 x 240 RGB565 framebuffer, and 18 x 18 animated dirty region. Times cover
the synchronous Zephyr display call. Each image was built cleanly, flashed
through the software bootloader path, and queried over USB CDC on the same
PIM559.

| Transport | Flash | RAM | Full present | Typical 18 x 18 present | Main stack high-water |
| --- | ---: | ---: | ---: | ---: | ---: |
| SPI0/PL022 | 115,644 B | 142,620 B | 89,900 us | 818 us | 892 / 2048 B |
| PIO polling | 119,624 B | 142,692 B | 130,627 us | 1,615 us | 1016 / 2048 B |
| PIO plus DMA | 123,116 B | 143,204 B | 82,297-82,345 us | 1,915-2,060 us | 1132 / 2048 B |

All three variants sustained the fixed 62.5 fps update rate with zero skipped
ticks during their steady-state sample. The PIO/DMA image also retained zero
skips while serving twelve back-to-back USB status commands; its worst complete
dirty render during that run was 5,903 us.

PIO/DMA improved the infrequent full-frame transfer by about 8.4%, but made the
normal dirty transfer 2.3-2.5 times slower, added 7,472 bytes of flash and 584
bytes of RAM, and raised measured main-stack use by 240 bytes. The Zephyr driver
uses DMA for the ST7789's short command/window transactions as well as pixel
payloads, so setup overhead dominates small updates. Its public SPI operation
also waits synchronously for DMA completion, meaning it does not remove the
visible full-redraw stall.

The default therefore remains SPI0/PL022. PIO/DMA may be worth revisiting with
a transfer-size threshold, an asynchronous display worker, or a renderer that
primarily sends large contiguous regions.
