# PicoSystem Zephyr playground

An experimental, out-of-tree Zephyr port for the Pimoroni PicoSystem PIM559.
The build runs entirely in Docker; the host needs only Git, Docker, and the
Docker Compose plugin.

The first milestone intentionally exercises only low-risk hardware:

- boots a Zephyr 4.4.2 image from the RP2040 UF2 bootloader;
- exposes the Zephyr log console over USB CDC ACM;
- reads all eight buttons;
- performs an RGB LED self-test and then mirrors the face buttons;
- initializes the LCD over SPI and draws an asymmetric orientation target;
- emits a five-second heartbeat over USB and on the blue LED.

The LCD backlight is held off until the test frame is complete, then enabled at
25%. Audio, battery ADC, charger status, and DMA/PIO display transfers are
documented but not enabled yet.

## Build

```sh
make build
```

On the first build, Docker creates a pinned, RP2040-focused image containing
only the ARM toolchain and `west` clones Zephyr plus the two RP2040 dependencies
into a named Docker volume. Later builds reuse both. The flashable output is:

```text
build/zephyr/zephyr.uf2
```

Useful commands:

```sh
make setup    # explicitly refresh the pinned west dependencies
make format   # format the application C source in the container
make check    # formatting, whitespace, and a clean build
make shell    # enter the build container
```

The Ubuntu base, SDK archives, Python dependencies, and Zephyr release are
pinned. SDK downloads are checked against their upstream SHA-256 hashes.
Changing `west.yml` automatically causes the next build to refresh the
dependency volume.

## Flash

1. Turn the PicoSystem off.
2. Hold **X** while turning it on.
3. Release X when the `RPI-RP2` mass-storage volume appears.
4. Copy `build/zephyr/zephyr.uf2` to that volume.

On Linux or macOS, the checked flash helper validates the UF2 volume before it
copies anything:

```sh
make flash UF2_MOUNT=/media/$USER/RPI-RP2
# macOS commonly uses: UF2_MOUNT=/Volumes/RPI-RP2
```

The PicoSystem reboots automatically when the copy completes. Its LCD should
show red/green/blue/white corner blocks and a yellow arrow pointing toward the
top at low brightness. The RGB LED should show red, green, and blue in sequence,
then blink blue. A/B/X illuminate red/green/blue respectively; Y illuminates all
three channels.

The ROM bootloader is independent of the application, so a faulty Zephyr image
can normally be replaced by repeating the hold-X procedure.

## USB log console

After the application boots, the same USB cable presents a CDC ACM serial
device. On Linux it will usually be `/dev/ttyACM0`:

```sh
make monitor PORT=/dev/ttyACM0
```

The monitor also runs inside Docker. Press `Ctrl+]` to exit its terminal.
The port disconnects briefly each time the PicoSystem resets and may return
with a different number.

Expected messages include button press/release events and a periodic line like:

```text
<inf> picosystem_playground: alive: uptime=10000 ms, buttons=0x00, display=109393 us
```

## Repository layout

```text
boards/pimoroni/picosystem/  Out-of-tree PIM559 Zephyr board definition
docker/                      Pinned Zephyr build image
docs/                        Hardware notes and staged bring-up plan
scripts/container/           Dependency, build, and validation automation
src/                         Firmware application
compose.yaml                 Isolated workspace and persistent dependencies
west.yml                     Pinned Zephyr/module manifest
```

See [the hardware map](docs/hardware.md) before adding peripherals and
[the bring-up roadmap](docs/roadmap.md) for the next milestones.

## Current validation boundary

`make check` verifies configuration, device tree, compilation, linking, and UF2
generation. USB CDC, all eight buttons, the RGB heartbeat, hold-X recovery, and
the asymmetric display target at 20 MHz and 25% backlight have been checked on
one PIM559. Its bounded eight-row renderer measured 109393 us for a full frame.
Backlight startup behavior and flash-size behavior still require physical
confirmation. Record those results in the roadmap rather than treating a
successful cross-build as hardware validation.
