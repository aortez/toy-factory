# PIM559 hardware map

This table is the working contract for the Zephyr board port. It is derived
from Pimoroni's [PicoSystem schematic](https://cdn.shopify.com/s/files/1/0174/1800/files/picosystem_schematic.pdf?v=1633439554)
and [native hardware implementation](https://github.com/pimoroni/picosystem/blob/main/libraries/hardware.cpp).

| GPIO | Function | First-use milestone |
|---:|---|---|
| GP0 | Internal debug UART TX | Optional debugger work |
| GP1 | Internal debug UART RX | Optional debugger work |
| GP2 | USB VBUS detect, active high; gates automatic red charge indicator | Power/charger support |
| GP4 | LCD reset | Display |
| GP5 | LCD chip select | Display |
| GP6 | LCD SPI0 clock | Display |
| GP7 | LCD SPI0 MOSI | Display |
| GP8 | LCD tearing-effect/vsync input | Optimized display |
| GP9 | LCD data/command | Display |
| GP11 | Piezo audio PWM | Audio |
| GP12 | LCD backlight PWM | Display |
| GP13 | RGB LED green | GPIO bring-up |
| GP14 | RGB LED red; shared with hardware charge-status path | GPIO bring-up |
| GP15 | RGB LED blue | GPIO bring-up |
| GP16 | Y button, active low | GPIO bring-up |
| GP17 | X button, active low | GPIO bring-up / UF2 entry |
| GP18 | A button, active low | GPIO bring-up |
| GP19 | B button, active low | GPIO bring-up |
| GP20 | Down button, active low | GPIO bring-up |
| GP21 | Right button, active low | GPIO bring-up |
| GP22 | Left button, active low | GPIO bring-up |
| GP23 | Up button, active low | GPIO bring-up |
| GP24 | Charger status input | Power/charger support |
| GP26 / ADC0 | Battery voltage through a 3:1 divider | Power/charger support |

Other board-level resources:

- RP2040 with 264 KiB SRAM;
- Winbond W25Q128 16 MiB QSPI flash;
- 240 x 240 ST7789-family LCD;
- USB-C connected to the RP2040 USB device controller;
- SWDIO/SWCLK and UART pads inside the enclosure;
- LiPo battery, charging circuit, power switch, and piezo transducer;
- no Wi-Fi, Bluetooth, or other radio.

The board target currently declares the physical flash size, USB device,
buttons, RGB LED, SPI display, PWM backlight, PWM piezo, and battery ADC. The
graphics baseline uses one 115,200-byte RGB565 framebuffer and a packed
3,840-byte transfer buffer at 20 MHz. GP8 is now an interrupt-driven input for
bounded tearing-effect synchronization. Before enabling settings, a filesystem,
or unusually large images, audit the factory firmware's flash/data layout and
define explicit storage partitions. A peripheral should be added to the device
tree only when its driver milestone begins, keeping early failures easy to
isolate.

## USB power and charging status

GP2 is not a dedicated LED output. The schematic connects VBUS to
`VBUS_DETECT` through a 10 kOhm/10 kOhm divider, producing about 2.5 V while USB
power is present and pulling the net low when it is absent. That same net drives
the gate of the MOSFET that allows the charger's `CHARGE_STAT` signal to sink
current through the RGB LED's red channel. The result is an automatic red light
while VBUS is present and the charger asserts its active-low status output.
Firmware can still drive the red channel independently through GP14.

Pimoroni's native runtime calls GP2 `CHARGE_LED` and deliberately drives it low,
which suppresses the automatic indicator and gives software exclusive RGB
control. The Zephyr bring-up instead configures GP2 as an active-high input so it
can report VBUS and leaves the hardware indicator enabled. GP2 must not be
changed to an output casually because it is electrically connected to the VBUS
divider.

GP24 reads `CHARGE_STAT` as active low with an internal pull-up. The charger
asserts it during preconditioning, fast-charge, and constant-voltage charging;
an inactive level means charging is complete, shut down, or otherwise not
active. Combining the two inputs produces `battery`, `usb-powered`, and
`usb-charging` states. `charge-active-without-usb` is retained as a diagnostic
state for a transition or an electrical/configuration fault rather than being
silently mapped to battery operation. The tested, nearly full unit produced
brief raw charge-status assertions when sampled every 20 ms, while the hardware
red indicator remained visibly active. Each sampled assertion therefore holds
the reported charging state for one second, and a different combined state must
then persist for 250 ms before firmware reports it. This qualification is for
telemetry stability; it does not alter either pin or the hardware LED path.

Physical validation exercised all three normal classifications. Removing USB
produced `battery` without resetting the running application. Restoring USB
produced `usb-charging` while the automatic red channel was visible. After the
nearly full cell finished charging, a 130-second serial capture remained stable
at `usb-powered` with 4206-4208 mV readings and a blue-only heartbeat; no red
charge indication or impossible charge-without-USB state appeared.

Battery sense uses a 1.5 MOhm upper leg and 750 kOhm lower leg, plus a 100 nF
filter capacitor, so GP26/ADC0 sees one third of VBAT. The Zephyr test takes 16
back-to-back 12-bit samples, averages the raw codes, converts using the declared
3.3 V ADC reference, and applies the divider values from device tree. Results
outside 2.5-4.3 V are flagged but still reported. This is diagnostic telemetry,
not a calibrated fuel gauge or charge-percentage model. On the tested,
USB-powered PIM559, eight reports over 35 seconds measured 4196-4201 mV with raw
means of 1736-1738 and no ADC errors. The 5 mV spread confirms repeatability and
a plausible nearly-full LiPo reading, but no external meter was used to establish
absolute accuracy.

Pimoroni's native implementation drives the GP11 piezo with active-high PWM and
uses a short positive pulse to limit transducer deflection, with 100 us as its
maximum-volume pulse. The initial Zephyr test is intentionally quieter: B plays
440 Hz for 180 ms using a 25 us pulse. A delayed system-work item silences the
channel independently of the display loop, and initialization explicitly sets
the pulse width to zero. On the tested PIM559, startup and idle remained silent,
the tone was clearly audible, and rapid presses safely extended playback only
until 180 ms after the final press.

## LCD tearing-effect synchronization

The Zephyr ST7789V driver does not enable the panel's tearing-effect output, and
the generic MIPI DBI SPI synchronization path waits indefinitely for a missing
pulse. The application therefore sends the standard `TEON` command in
vertical-blank mode after display initialization, then captures both edges of
the active-high GP8 signal. Timing accumulation is bounded inside the GPIO
callback and copied under a spin lock for shell readers.

Across hardware runs on the tested PIM559, GP8 measured about 59.64-59.67 Hz. A
4,859-period stress sample had a 16,762 us mean period, 16,604-16,891 us range,
and no GPIO read errors. The high blanking pulse averaged 1,151 us; the low
active-scan interval averaged 15,610 us. `picosystem display sync` exposes these
measurements and supports runtime `on` and `off` controls.

Partial presentations wait for a fresh rising edge only after four periods
qualify between 15 and 18.5 ms. Each wait is capped at 20 ms, stale signals are
bypassed, and full-frame writes remain unsynchronized because their roughly
77.7 ms transfer cannot fit in a panel refresh interval. In a synchronized
4,581-present run, including twelve back-to-back USB status commands, the
firmware recorded no timeout and no skipped logic tick. Presentation settled at
the panel's roughly 59.65 Hz while the fixed game logic remained at 62.5 Hz.
Routine 18 x 18 and catch-up 20 x 20 writes took about 0.80-0.95 ms; USB traffic
occasionally extended the synchronous SPI call to 1.52-1.62 ms. Main-thread
stack high-water was 988 of 2048 bytes.

On the tested PIM559, sending the 115200-byte orientation frame in bounded
eight-row chunks took 109393 us (1028 KiB/s). The earlier one-row baseline took
194685 us (577 KiB/s), so batching reduced latency by about 44%. These figures
measure the complete Zephyr display call path, including panel-window and driver
overhead; they are not raw SPI wire-speed measurements.

With the interactive marker overlay, repeated full redraws took 116137-116895
us. Cardinal 32 x 24 or 24 x 32 dirty rectangles took 1832-2130 us (704-818
KiB/s), while diagonal 32 x 32 rectangles took 2285-2602 us (768-875 KiB/s).
More than 300 held-key updates, diagonal moves, and edge clamps completed
without a display-write error or visible corruption.

The game-oriented framebuffer baseline uses 115200 bytes for one 240 x 240
RGB565 framebuffer and 3840 bytes for an eight-row transfer buffer. Its initial
bounded full transfer took 89840 us (1252 KiB/s), while routine 18 x 18 dirty
transfers took about 820-833 us. After 3518 fixed updates it sustained 62.5 fps
with zero skipped ticks, including twelve back-to-back USB status requests. The worst
complete dirty render observed in that run was 3340 us, and main-thread stack
high-water was 892 of 2048 bytes. The animated sprite, D-pad steering, and
repeated full redraws were visually confirmed without corruption. A forced full
redraw remains synchronous, so its diagnostic A-button path visibly hitches and
can intentionally accumulate skipped game ticks.

Full frames now bypass the staging buffer and send the wire-ready framebuffer
with one display write. This reduced PL022 full-frame time to 77,692-77,711 us
without changing the roughly 0.82 ms dirty path. Zephyr's preassembled RP2040
PIO SPI and PIO/DMA paths were measured again at the same configured 20 MHz.
PIO polling took 106,429 us; PIO/DMA took 47,303-47,351 us, close to the
46,080 us payload wire-time floor. PIO/DMA still increased the routine 18 x 18
transfer to 1.91-1.94 ms and consumed more flash, RAM, and stack. The dirty-first
demo therefore retains hardware SPI0/PL022 as its default, while large-update
workloads should reconsider PIO/DMA. The direct full-frame output was visually
confirmed on the physical PIM559. Full results and reproduction targets are in
[the benchmark report](../benchmarks/pio-dma/README.md).

On a cold power-on, the backlight remained visually dark until the completed
frame appeared; no bright or white startup flash was observed.
