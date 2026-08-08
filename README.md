# PicoSystem Zephyr playground

An experimental, out-of-tree Zephyr port for the Pimoroni PicoSystem PIM559.
The build runs entirely in Docker; the host needs only Git, Docker, and the
Docker Compose plugin.

The first milestone intentionally exercises only low-risk hardware:

- boots a Zephyr 4.4.2 image from the RP2040 UF2 bootloader;
- exposes an interactive Zephyr shell and log console over USB CDC ACM;
- reads all eight buttons;
- performs an RGB LED self-test and then mirrors the face buttons;
- initializes the LCD over SPI and draws an asymmetric target with a movable marker;
- plays a short, bounded piezo tone when B is pressed;
- averages and reports the GP26 battery-voltage ADC at startup and every 30 seconds;
- classifies the GP2 VBUS and active-low GP24 charger-status inputs;
- emits a 30-second log heartbeat and a faster visual heartbeat on the blue LED.

The LCD backlight is held off until the test frame is complete, then enabled at
25%. The piezo starts silent and uses a conservative 25 us active pulse for the
tone test. GP2 remains an input so the board's automatic red charging indicator
continues to work. DMA/PIO display transfers are documented but not enabled yet.

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
make          # show all available targets (`make help` also works)
make build    # build the firmware
make setup    # explicitly refresh the pinned west dependencies
make format   # format the application C source in the container
make check    # formatting, whitespace, and a clean build
make container-shell  # enter the build container (`make shell` also works)
```

The Ubuntu base, SDK archives, Python dependencies, and Zephyr release are
pinned. SDK downloads are checked against their upstream SHA-256 hashes.
Changing `west.yml` automatically causes the next build to refresh the
dependency volume.

## Flash

On Linux or macOS, `make update` handles the normal development cycle. It
builds the firmware, asks the running application to reboot into the RP2040 ROM
bootloader, waits for the `RPI-RP2` volume, validates it, and copies the UF2:

```sh
make update
```

If the PicoSystem is already in update mode, the command skips the reboot and
flashes it directly. If serial-port or mount detection is ambiguous, select the
device explicitly with `PORT=/dev/ttyACM0` or
`UF2_MOUNT=/path/to/RPI-RP2`. The existing `make flash` target is an alias for
the same workflow. Close `make console` before updating because only one
process can own the serial port.

To enter update mode without building or flashing, run:

```sh
make bootloader
```

The physical gesture remains the recovery path for a blank or broken image:

1. Turn the PicoSystem off.
2. Hold **X** while turning it on.
3. Release X when the `RPI-RP2` mass-storage volume appears.
4. Run `make update` again.

The PicoSystem reboots automatically when the copy completes. Its LCD should
show red/green/blue/white corner blocks and a yellow arrow pointing toward the
top at low brightness. The RGB LED should show red, green, and blue in sequence,
then blink blue. A/B/X illuminate red/green/blue respectively; Y illuminates all
three channels. While the battery is actively charging, the board's independent
hardware path also illuminates the red channel, so software-selected colors can
mix with red.

A white-bordered magenta marker starts in the center. The D-pad moves it in
8-pixel steps and repeats while held. Each move redraws only the marker's old
and new bounds. Press A to force a full-screen redraw for comparison. Press B
to play a 440 Hz tone for 180 ms; the green RGB channel remains tied to B as
before.

The ROM bootloader is independent of the application, so software-controlled
entry cannot remove the hold-X recovery path.

## USB diagnostic shell and log console

After the application boots, the same USB cable presents a CDC ACM serial
device. `make console` detects exactly one Zephyr CDC ACM device and opens the
interactive shell and log stream:

```sh
make console
```

The console runs inside Docker. Press `Ctrl+]` to exit its terminal. If more
than one matching port exists, select one with
`make console PORT=/dev/ttyACM0`. `make monitor` remains as a compatibility
alias. The port disconnects briefly each time the PicoSystem resets and may
return with a different number. Press Enter after connecting to reveal the
`picosystem:~$` prompt. Tab completion, command history, and asynchronous Zephyr
logs share the same terminal.

For a non-interactive snapshot, run:

```sh
make status
```

`status` briefly owns the same serial port as `console`, sends `picosystem
status`, prints the response, and exits. Close the console before using it.

The application adds these commands:

```text
picosystem status
picosystem buttons
picosystem led auto|off|red|green|blue|white
picosystem tone <frequency_hz> <duration_ms>
picosystem display stats
picosystem reboot bootloader
```

`picosystem status` returns current uptime and software LED mode alongside one
coherent hardware snapshot containing buttons, USB/charger state, the most
recent battery sample and its age, display timing, and sprite position.
`buttons` is a compact live-input view.
The LED override takes effect in the main hardware loop; `auto` restores the
button colors and blue heartbeat. The independent hardware red charge indicator
is not disabled by `led off`. Tone requests are constrained to 100-4000 Hz and
1-1000 ms and are queued for the main loop rather than driving PWM from the
shell thread. Enter `picosystem -h` for command help.
`reboot bootloader` stores a one-shot boot-mode marker in reserved SRAM and
performs a cold reset; Zephyr consumes and clears the marker before entering
the RP2040 ROM USB bootloader.

Expected messages include button press/release events and a periodic line like:

```text
<inf> picosystem_display_test: Partial #1: 24x32 at (108,100), 2130 us, 704 KiB/s
<inf> picosystem_playground: battery: 3988 mV (raw mean 1650)
<inf> picosystem_playground: power: usb-charging (usb=present, charge=active)
<inf> picosystem_playground: alive: uptime=10000 ms, buttons=0x00, power=usb-charging, full=116593 us, partial=2130 us/24x32 (#1)
```

After moving the marker, the log also reports the dirty rectangle and measured
transfer rate. Pressing B logs the start of the tone and confirms when the
delayed shutoff has returned the PWM output to silence. Battery readings are
averaged over 16 raw samples. They are diagnostic voltage measurements, not a
charge-percentage estimate. Power status is reported as `battery`,
`usb-powered`, or `usb-charging`; an unexpected active charger signal without
VBUS is retained as a separate diagnostic state. Each active charger sample
holds `usb-charging` for one second so sampled status pulses do not flood the
log. A resulting input combination must remain unchanged for 250 ms before it
replaces the reported state. Routine battery/heartbeat logging now occurs every
30 seconds; use `picosystem status` for an immediate snapshot.

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
one PIM559. Its bounded eight-row renderer measured 109393 us for the static
target and about 116 ms with the movable marker. Cardinal partial updates took
1.83-2.13 ms; diagonal updates took 2.29-2.60 ms without visible corruption.
A cold power-on also showed no visible bright/white backlight flash before the
completed target appeared. The 440 Hz piezo tone, silent startup/idle state,
and rapid retrigger behavior have also been checked on the same unit. Flash-size
behavior still requires physical confirmation. Eight USB-powered battery reports
over 35 seconds measured 4196-4201 mV with raw means of 1736-1738 and no ADC
errors. This confirms plausible, repeatable telemetry, not absolute calibration
against an external meter. GP2/GP24 power-state sampling and the independent
red charge indicator have also been checked. The unit continued running in the
`battery` state after USB was removed, reported charge activity after USB was
restored, and later remained `usb-powered` for a 130-second capture at
4206-4208 mV while the charge-complete LED behavior was blue-heartbeat only.
The diagnostic shell has also been checked through the physical USB connection:
help, status, display statistics, bounded tone parsing/playback, every software
LED override with `auto` recovery, and a held-X snapshot (`0x40 X`) behaved as
documented. A three-command input burst produced no RX overrun, and startup plus
30-second heartbeat logs were preserved without dropped-message reports.
