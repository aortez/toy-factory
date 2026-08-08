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
- [ ] Add charger status and charge indicator behavior.
- [ ] Audit the factory flash/data layout before adding persistent storage.
- [ ] Add a shell command that reports board state without flooding logs.

## 4. Game-oriented graphics

- [ ] Decide between a full 240 x 240 RGB565 framebuffer and partial buffers.
- [ ] Measure RAM, stack high-water marks, frame time, and USB logging impact.
- [ ] Evaluate a preassembled PIO/DMA transfer path.
- [ ] Use the LCD tearing-effect signal for synchronized presentation.
- [ ] Evaluate 120 x 120 pixel-doubled rendering.

## 5. Automation and maintenance

- [ ] Add hosted CI after selecting the repository host.
- [ ] Archive UF2 and size reports for tagged builds.
- [ ] Add native unit tests for hardware-independent game/application logic.
- [ ] Define a small physical smoke-test checklist for releases.
- [ ] Decide whether the board port should be proposed upstream to Zephyr.
