# Toy Factory

Toy Factory is an idle toy for the Pimoroni PicoSystem PIM559.

The current baseline exercises the complete board and a game-oriented graphics
path:

- boots a Zephyr 4.4.2 image from the RP2040 UF2 bootloader;
- exposes an interactive Zephyr shell and log console as `Toy Factory PicoSystem`
  over USB CDC ACM;
- reads all eight buttons;
- performs an RGB LED self-test and then mirrors the face buttons;
- owns one 240 x 240 RGB565 framebuffer and presents packed dirty regions over SPI;
- runs exact 120 Hz fixed-step game logic with Q16.16 positions;
- publishes compact state snapshots to an independent, lower-priority renderer;
- late-latches the newest snapshot and aligns partial display writes with the LCD's GP8
  tearing-effect signal;
- exposes acknowledged reset, pause, exact-step, injected-input, state-hash, and
  framebuffer-capture controls over USB;
- runs declarative deterministic device sequences with state/framebuffer assertions;
- plays a short, bounded piezo tone when B is pressed;
- averages and reports the GP26 battery-voltage ADC at startup and every 30 seconds;
- classifies the GP2 VBUS and active-low GP24 charger-status inputs;
- emits a 30-second log heartbeat and a faster visual heartbeat on the blue LED.

The LCD backlight is held off until the initial framebuffer is complete and has
been transferred, then enabled at 25%. The framebuffer consumes 115,200 bytes;
a separate 3,840-byte staging buffer packs partial rows for efficient driver
writes. The piezo starts silent and uses a conservative 25 us active pulse for
the tone test. GP2 remains an input so the board's automatic red charging
indicator continues to work. PIO and PIO/DMA display transports remain optional
benchmark variants; the default uses SPI0/PL022.

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
make build-pio-dma  # build the optional PIO/DMA display benchmark
make setup    # explicitly refresh the pinned west dependencies
make format   # format the application C source in the container
make check    # formatting, whitespace, and a clean build
make container-shell  # enter the build container (`make shell` also works)
make sim-pause  # pause at a tick boundary and print exact simulation state
make sim-reset  # restore canonical tick-zero state while paused
make sim-step STEPS=1  # advance a paused simulation by exact 1/120-second ticks
make sim-test  # run the default deterministic hardware sequence
make screenshot  # save the coherent presented framebuffer as a PNG
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

On Linux, if the verified `RPI-RP2` block device appears but the desktop does
not automount it, `make update` uses `udisksctl` as a fallback. It accepts only
a unique removable USB VFAT partition whose udev vendor/model and filesystem
identity match the RP2040 ROM bootloader; ambiguous devices are never mounted
or flashed automatically. Install the host's `udisks2` package or mount the
volume manually when `udisksctl` is unavailable.

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
show a dark checkerboard playfield, cyan border, white `SIM 120HZ TE DISPLAY`
heading, and a moving yellow sprite. The sprite advances on exact rational
120 Hz deadlines and each normal presentation covers only the union of its old
and new bounds. The D-pad steers its horizontal and vertical velocity. Press A
to queue a full-screen redraw for comparison and B to play a 440 Hz tone for
180 ms. A full transfer still occupies the panel for roughly 80 ms, but it runs
on the renderer thread: game logic and input sampling continue at 120 Hz and
newer snapshots coalesce while the renderer is busy.

The RGB LED shows red, green, and blue in sequence at startup, then blinks blue.
A/B/X illuminate red/green/blue respectively; Y illuminates all three channels.
While the battery is actively charging, the board's independent hardware path
also illuminates the red channel, so software-selected colors can mix with red.

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
`toy-factory:~$` prompt. Tab completion, command history, and asynchronous Zephyr
logs share the same terminal.

For a non-interactive snapshot, run:

```sh
make status
make game-stats
make game-redraw
make display-sync
make sim-pause
make sim-reset
make sim-input INPUT=right
make sim-step STEPS=1
make sim-state
make screenshot OUT=artifacts/screenshot.png
make sim-run
make sim-test
```

`status` briefly owns the same serial port as `console`, sends `picosystem
status`, prints the response, and exits. Close the console before using it.
`game-stats` reports detailed simulation/renderer metrics, `game-redraw` queues
the same asynchronous full redraw as the A button, and `display-sync` reports
the panel refresh signal and bounded-wait counters. The `sim-*` targets provide
acknowledged remote simulation control and deterministic sequence testing.
`screenshot` validates and converts a coherent RGB565 transfer into a PNG
beneath the checkout. Captures briefly own the same framebuffer mutex as the
renderer, so pausing first is recommended when an exact stepped frame is
required.

The application adds these commands:

```text
picosystem status
picosystem buttons
picosystem led auto|off|red|green|blue|white
picosystem tone <frequency_hz> <duration_ms>
picosystem display stats
picosystem display sync [on|off]
picosystem display checksum
picosystem display capture
picosystem game stats
picosystem game redraw
picosystem game pause
picosystem game reset
picosystem game step [count]
picosystem game input physical|none|up|down|left|right|up-left|up-right|down-left|down-right
picosystem game state
picosystem game run
picosystem reboot bootloader
```

`picosystem status` returns current uptime and software LED mode alongside one
coherent hardware snapshot containing buttons, USB/charger state, the most
recent battery sample and its age, framebuffer/presentation timing, game-loop
rate and skipped ticks, snapshot age, simulation/displayed sprite state, and
both application-thread stack high-water marks.
`buttons` is a compact live-input view.
`display sync` reports GP8 edge timing, refresh frequency, blanking-pulse width,
qualification state, wait latency, and fallback counts. Passing `off` bypasses
TE waits without disabling measurement; `on` restores automatic synchronization.
Only partial presents wait for TE because a full frame cannot fit within one
panel refresh interval. `game stats` exposes scheduler backlog and budget
counters, published/coalesced snapshots, renderer health, state age at the SPI
write, full-redraw count, and both stack high-water marks. `game redraw` only
posts a coalesced request; the shell never touches the framebuffer or display.
`game pause` is acknowledged only after the priority-0 simulation owner reaches
a tick boundary. `game reset` is accepted only while paused; it restores the
canonical tick-zero position and velocity, selects neutral remote input, and
publishes a full-redraw snapshot without rewinding renderer sequence numbers.
While paused, `game step` executes 1-120 exact fixed-duration updates without
advancing wall-clock scheduling. `game run` starts a fresh rational deadline
sequence and performance-measurement epoch, so time and exact steps spent paused
never become catch-up debt or distort subsequent real-time rate reporting.
`game input` selects either physical buttons or a persistent injected direction;
`none` is a neutral remote input and `physical` restores the D-pad. In the
current demo, neutral means “do not change velocity,” rather than “stop.” Every
control response includes the exact tick, Q16.16 state, input source,
published/presented snapshot sequence, and a deterministic hash that excludes
clocks and performance counters.

`display checksum` reports the CRC-32 of one fully presented framebuffer.
`display capture` waits for the current published snapshot to be presented,
then streams the complete 240 x 240 RGB565 big-endian framebuffer in numbered
base64 chunks with a final CRC-32. The host rejects missing, reordered, corrupt,
or truncated chunks before writing a PNG. The capture represents the software
framebuffer sent to the display. The PIM559 display bus is write-only, so it
cannot prove that a faulty SPI transfer or physical LCD produced the same pixels.
The LED override takes effect in the main hardware loop; `auto` restores the
button colors and blue heartbeat. The independent hardware red charge indicator
is not disabled by `led off`. Tone requests are constrained to 100-4000 Hz and
1-1000 ms and are queued for the main loop rather than driving PWM from the
shell thread. Enter `picosystem -h` for command help.
`reboot bootloader` stores a one-shot boot-mode marker in reserved SRAM and
performs a cold reset; Zephyr consumes and clears the marker before entering
the RP2040 ROM USB bootloader.

### Deterministic device sequences

`make sim-test` runs
[`scripts/sequences/deterministic-smoke.json`](scripts/sequences/deterministic-smoke.json)
against the firmware currently flashed on the board; run `make update` first
after firmware changes. A sequence contains bounded directional-input segments
and optional final assertions:

```json
{
  "name": "deterministic-smoke",
  "steps": [
    {"input": "right", "ticks": 30},
    {"input": "up", "ticks": 15}
  ],
  "expect": {
    "hash": "e60b17ef",
    "framebuffer_crc32": "3e08ecbb"
  }
}
```

Run another file with:

```sh
make sim-test SEQUENCE=path/to/sequence.json
```

The runner holds one exclusive USB connection, pauses and canonically resets
the simulation, applies each input, and checks the exact returned tick after
every request. Segments longer than 120 ticks are automatically divided into
bounded firmware requests. The complete file is limited to 256 segments and
100,000 ticks; physical input is deliberately unavailable inside deterministic
sequences. Hash and framebuffer assertions are independently optional while a
new baseline is being authored, but committed regression sequences should use
both.

On success, the runner restores physical input and resumes real-time scheduling.
On failure, it first saves a coherent diagnostic image to
`artifacts/sequence-failure.png`, then performs the same cleanup and returns a
nonzero status. Override that path with
`FAIL_SCREENSHOT=artifacts/another-name.png`. Close `make console` before running
a sequence because the test owns the serial port for its entire duration.

Expected messages include button press/release events and a periodic line like:

```text
<inf> picosystem_graphics: Framebuffer ready: 115200 bytes plus 3840-byte transfer buffer, SPI 20000000 Hz
<inf> toy_factory: battery: 3850 mV (raw mean 1593)
<inf> toy_factory: power: usb-charging (usb=present, charge=active)
<inf> toy_factory: alive: uptime=30000 ms, buttons=0x00, power=usb-charging, ticks=3465, frame=1721, present=820 us/18x18, skipped=0, stacks=1184/2048+628/2048 bytes
```

The animation deliberately avoids per-frame logging; use `picosystem display
stats` or `picosystem game stats` for current buffer sizes, full and dirty
presentation timing, simulation and presentation rates, skipped ticks, render
time, snapshot age, sprite state, and stack usage.
Pressing B logs the start of the tone and confirms when the delayed shutoff has
returned the PWM output to silence. Battery readings are averaged over 16 raw
samples. They are diagnostic voltage measurements, not a charge-percentage
estimate. Power status is reported as `battery`,
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
scripts/sequences/           Declarative deterministic device tests
src/                         Firmware application
compose.yaml                 Isolated workspace and persistent dependencies
west.yml                     Pinned Zephyr/module manifest
```

See [the hardware map](docs/hardware.md) before adding peripherals and
[the bring-up roadmap](docs/roadmap.md) for the next milestones. The measured
[PIO/DMA comparison](benchmarks/pio-dma/README.md) shows the tradeoff between
the default hardware SPI0/PL022 dirty-update path and faster PIO/DMA full frames.

## Game-loop architecture

The authoritative fixed-point state, canonical reset, one-tick update, collision
response, input validation, and stable field-by-field hash live in
[`src/game_world.c`](src/game_world.c). That module has no Zephyr, scheduler,
renderer, USB, or wall-clock dependency. The firmware and native test suite
compile the same C source, so host replay tests exercise the implementation that
runs on the RP2040 rather than a second simulation model.

The RP2040 build currently uses one core, so this is priority-based decoupling
rather than parallel CPU execution. The priority-0 main thread owns all
authoritative game state, samples input, and asks the platform-neutral world to
advance one fixed 120 Hz tick. It publishes a 24-byte immutable render snapshot
into one of two slots under a short spin lock. A saturated semaphore wakes the
priority-1 renderer, which coalesces obsolete snapshots instead of making
simulation wait.

For normal dirty updates, the renderer waits for a qualified TE rising edge,
then late-latches the newest snapshot and immediately draws/presents it. This
keeps presentation synchronized to the roughly 59.63 Hz panel while logic runs
twice as fast. Slow or deliberately full redraws may reduce presentation rate,
but they do not change simulation time. This ownership boundary is intended to
remain stable as the demo grows into heavier physics: simulation can later
publish a richer read-only snapshot without giving rendering access to live
world state.

Remote game-control requests cross a bounded message queue and are completed by
that same simulation-owning main thread. Canonical reset rewinds only
authoritative state; renderer publication numbers remain monotonic. The host
sequence runner keeps one CDC ACM connection open, but every mutation still
crosses the acknowledged queue. Framebuffer readers never mutate graphics
state: they wait for a presented sequence and share a mutex with the renderer
while visiting the existing framebuffer in small chunks. No second 115,200-byte
framebuffer is allocated.

## Current validation boundary

`make check` verifies configuration, device tree, compilation, linking, and UF2
generation and also runs native game-world replay/boundary, deadline-scheduler,
serial-shell, framebuffer protocol, RGB565 conversion, PNG-structure, and
deterministic-sequence tests. The game-world test uses the undefined-behavior
sanitizer and treats the board-confirmed reset/right-30/up-15 hashes as native
goldens. The default remote-debug image uses 147,108 bytes of RAM (54.62%) and
130,092 bytes of flash. This includes the 115,200-byte framebuffer, 3,840-byte
transfer buffer, two 24-byte render snapshots, and a 1,024-byte shell TX ring.
Full frames bypass the staging buffer with one contiguous display write.

GitHub Actions runs `make check` and builds the PIO and PIO/DMA variants for
every pull request and push to `main`. Tests that need a connected PicoSystem
remain part of the physical smoke-test boundary rather than hosted CI.

On the tested PIM559, the exact 120 Hz scheduler ran with a maximum observed
backlog of one, zero skipped ticks, and zero over-budget updates. The worst
simulation update during the run was 1,149 us of its 8,333 us budget. Normal
TE-driven presentation settled at about 59.6 fps with dirty state typically
2.8-6.4 ms old and a 10.0 ms observed maximum at the start of its SPI write.
Sixteen back-to-back USB status sessions did not change those scheduler
counters. Renderer-owned full redraws took 80,321-82,094 us; snapshots coalesced
while they ran, and simulation still reported no backlog growth or skipped tick.
Main- and render-thread stack high-water marks were 1,312 and 628 bytes of their
respective 2,048-byte stacks.

GP8 measured 59.626 Hz over the same stress run, with a 16,771 us mean period,
roughly 1.15 ms active-high blanking pulse, no GPIO read errors, and no TE wait
timeouts. Runtime sync-off made the renderer consume snapshots near the 120 Hz
publication rate; sync-on immediately restored TE-driven presentation without
rebooting or disrupting simulation. USB CDC, all eight buttons, the RGB heartbeat,
hold-X recovery, and the earlier asymmetric display target at 20 MHz and 25%
backlight have been checked on one PIM559. Its bounded eight-row renderer
measured 109393 us for the static target and about 116 ms with the movable
marker. Cardinal partial updates took 1.83-2.13 ms; diagonal updates took
2.29-2.60 ms without visible corruption. The framebuffer animation, D-pad
steering, and earlier synchronous full-redraw path were visually confirmed
without corruption. The current asynchronous A-button full-redraw path was also
visually confirmed without tearing. Its expected position jump reflects
coalesced intermediate snapshots while the renderer is occupied, rather than a
simulation pause.
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

The remote-debug controls have also been exercised against the physical board.
A paused state remained bit-for-bit stable at tick 11,252; injected-right steps
advanced it to ticks 11,253 and 11,263 exactly, with a new deterministic hash at
each result. The renderer subsequently acknowledged snapshot 11,264, and its
framebuffer CRC-32 was `74db97a8`. Invalid stepping while running now produces
a nonzero host-tool exit instead of a false-positive automation result.

Canonical reset was also rejected while running and repeatedly produced tick 0,
neutral remote input, and hash `482ffd98` while paused. Three consecutive runs
of the committed right-30/up-15 sequence each reached tick 45, hash `e60b17ef`,
and framebuffer CRC-32 `3e08ecbb`. The intentional mismatch path returned
nonzero, captured the expected 240 x 240 frame before cleanup, and restored
physical input plus real-time scheduling. Rebased post-test metrics returned to
120.0 Hz simulation and approximately 59.5 fps instead of counting exact manual
steps against wall time.

CRC-validated PNG captures complete in roughly 8.0-8.6 seconds after increasing
the interrupt-driven USB shell TX ring from 8 to 1,024 bytes. Captures were
visually inspected and matched the on-device header, border, checkerboard,
sprite, and colors. During a running capture, logic advanced from tick 3,440 to
4,554; the subsequent metrics still reported 120.0 Hz, zero skipped ticks, zero
over-budget updates, and a fully caught-up presented snapshot. Capture outputs
and newly created artifact directories retain the invoking host user's ownership.
