# Bring-up roadmap

Each milestone should leave a flashable, observable image. A cross-build is not
enough to mark hardware-dependent acceptance items complete.

## 0. Reproducible foundation

- [x] Initialize the Git repository on `main`.
- [x] Pin the Zephyr release and required west modules.
- [x] Pin a multi-architecture Zephyr build container by digest.
- [x] Keep dependency checkouts in a Docker volume and artifacts in the repo.
- [x] Add format, validation, flash, monitor, and interactive-shell commands.

## 1. USB and GPIO proof of life

- [x] Define the PIM559 RP2040, 16 MiB flash, USB, buttons, and RGB LED.
- [x] Cross-build a UF2 image.
- [x] Confirm the blue RGB heartbeat on physical hardware.
- [ ] Confirm the red/green/blue startup sequence on physical hardware.
- [x] Confirm USB CDC enumeration and periodic log output.
- [x] Confirm all eight button mappings and active-low behavior.
- [x] Confirm hold-X UF2 recovery after flashing Zephyr.

## 2. Conventional display path

- [x] Add SPI0 pin control, LCD reset, chip select, D/C, and backlight PWM.
- [x] Add an initial Zephyr ST7789V/MIPI-DBI device-tree node.
- [x] Add a bounded RGB565 color-bar test.
- [x] Confirm full-frame geometry, RGB color order, and 25% PWM backlight.
- [x] Add an asymmetric corner/arrow orientation target.
- [x] Confirm target orientation and 20 MHz SPI transfer timing on hardware.
- [x] Measure full-frame throughput with a bounded eight-row buffer.
- [x] Add a bounded interactive dirty-rectangle test.
- [x] Measure partial-update throughput.
- [x] Confirm that backlight-off is the safe startup state.

## 3. Remaining board peripherals

- [x] Add PWM piezo support and a short B-button tone test.
- [x] Confirm the tone and silent startup/idle state on physical hardware.
- [x] Add battery ADC sampling, divider conversion, and sanity limits.
- [x] Confirm plausible and repeatable battery readings on physical hardware.
- [x] Add VBUS/charger-status sampling while preserving the automatic red indicator.
- [x] Confirm USB-powered/charging states and indicator behavior on physical hardware.
- [ ] Audit the factory flash/data layout before adding persistent storage.
- [x] Add a USB shell that reports board state without flooding logs.
- [x] Confirm status, buttons, LED overrides, and queued tones through the physical shell.

## 4. Game-oriented graphics

- [x] Select one full 240 x 240 RGB565 framebuffer with packed partial transfers.
- [x] Add clipped pixel, rectangle, monochrome-sprite, and compact text primitives.
- [x] Separate fixed-step game updates from dirty-region presentation.
- [x] Confirm the bouncing/steerable framebuffer demo on physical hardware.
- [x] Measure RAM, stack high-water marks, frame time, and USB logging impact.
- [x] Add and benchmark a contiguous one-transfer full-frame path.
- [x] Evaluate a preassembled PIO/DMA transfer path; retain PL022 for dirty updates.
- [x] Use the LCD tearing-effect signal for synchronized presentation.
- [x] Run authoritative simulation on exact rational 120 Hz deadlines.
- [x] Hand immutable snapshots to a lower-priority, TE-driven renderer.
- [x] Confirm that full redraws and repeated USB queries do not skip simulation ticks.
- [x] Visually confirm the asynchronous A-button full-redraw path on hardware.
- [ ] Evaluate 120 x 120 pixel-doubled rendering.

## 5. Automation and maintenance

- [x] Add hosted CI for native checks and reproducible firmware builds.
- [ ] Archive UF2 and size reports for tagged builds.
- [x] Add a native unit test for the hardware-independent fixed-rate scheduler.
- [x] Extract and natively test deterministic hardware-independent game-world logic.
- [ ] Define a small physical smoke-test checklist for releases.
- [ ] Decide whether the board port should be proposed upstream to Zephyr.

## 6. Deterministic physics

- [x] Define numeric, ownership, memory, timing, overload, and validation contracts.
- [x] Add a fixed-point circle/static-segment collision lab with native tests.
- [x] Confirm deterministic state and framebuffer goldens on physical hardware.
- [ ] Add angular bodies, oriented boxes, and stable contact manifolds.
- [ ] Add a deterministic broad phase proven against brute-force candidate sets.
- [ ] Add joints, motors, conveyors, springs, sensors, and sleeping.
- [ ] Add a bounded rope or soft-body subsystem.
- [ ] Evaluate granular materials and approximate force fields.
