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

The renderer waits for a fresh rising edge only after four periods qualify
between 15 and 18.5 ms. Each wait is capped at 20 ms, stale signals are bypassed,
and each display path begins from a bounded wait. Damage rendering late-latches
after the edge; the fast full-frame path rasterizes first and starts its one DMA
write at the next edge. A conservative 20 MHz full transfer still spans several
panel periods even though its start is synchronized.
In the final stress run, GP8 measured 59.626 Hz over more than 8,000 periods,
with a 16,771 us mean period, no GPIO read errors, and no TE timeout. Runtime
`sync off` and `sync on` also switched cleanly between unconstrained snapshot
consumption and TE-driven presentation without rebooting.

## Decoupled 120 Hz simulation and presentation

Zephyr and every device driver run on core 0. Its priority-0 main thread owns
input and all authoritative simulation state; the USB shell runs at priority 1.
The conservative image uses a preemptible priority-2 damage renderer. The fast
PL022/DMA image instead uses a short priority -1 coordinator and a bare-metal
core-1 raster worker. Core 1 receives immutable snapshots through reserved SRAM,
signals completion through the SIO FIFO mailbox interrupt, and never calls
Zephyr or a driver. When simulation has already missed its next deadline, the
main loop reserves a one-millisecond recovery window so the shell can still
accept diagnostics or a bootloader request. The scheduler
represents 120 Hz as rational kernel-tick deadlines rather than rounding it to
an integer millisecond period. With the configured 10 kHz kernel tick, the
deadline spacing repeats 83, 83, and 84 ticks, totaling exactly 250 ticks for
three updates and 10,000 ticks for 120 updates. A native host test checks this
pattern, catch-up boundaries, validation, and the constant-time due-count result
against an iterative reference.

Simulation uses Q16.16 positions and publishes a 504-byte immutable snapshot of
up to 12 circle or oriented-box bodies, eight static segments, and eight
distance-joint render records on every update. Two slots and a short
spin-lock-protected copy prevent the
renderer from observing partially updated state. A saturated semaphore is only
a wake-up hint: if two or more simulation states arrive during a panel period,
the renderer deliberately coalesces the older ones. The main thread never waits
for TE, framebuffer work, core 1, or SPI, and neither renderer mode reads live
simulation state.

The six-body collision lab held 120.0 Hz simulation and 59.3 fps presentation
over a clean 20-second physical run, with backlog one and zero skipped or
over-budget updates. Routine sampled physics updates took 1.9-2.1 ms; the
observed maximum was 6.269 ms. Main and renderer stack high-water marks were
1,392/2,048 and 1,340/2,048 bytes. Splitting coalesced motion into separate old
and new footprints reduced the observed worst dirty-render wall time from
77.591 ms to 33.808 ms, including the TE wait; a routine 21 x 22 region took
1.125 ms.

The subsequent mixed rigid-body lab adds three oriented boxes, angular state,
SAT/clipping narrow phase, and angular impulse response while retaining three
circles. Its fixed-capacity world is 13,936 bytes and its two render snapshots
are 400 bytes each. Each dynamic box basis is cached once per contact pass, and
each static-segment normal is derived once when the scene is built. A clean
4,136-tick window held 120.0 Hz with backlog one, zero skipped ticks, zero
over-budget updates, a 4.580 ms current update, and a 5.449 ms observed maximum.
TE-driven presentation was 57.8 fps. Main and renderer stack high-water marks
were 2,448/4,096 and 1,988/3,072 bytes.

The uniform-grid lab expands the physical demo to four circles and four boxes
while retaining capacity for 12 bodies. Its 14,968-byte physics world includes
a 1,024-byte, 16 x 16 scratch grid. The PIM559 reproduced the native reset,
right-30, and right-30/up-15 hashes (`b20aaf3a`, `cb18185d`, and `7272656f`) and
the tick-45 framebuffer CRC-32 `11bbf436`. A reset 3,692-tick window ran at
119.9 Hz with zero skipped ticks and one isolated over-budget update; the
sampled update was 5.724 ms and the observed maximum was 19.848 ms. The sampled
step retained 15 of 76 possible pairs, occupied 91 of 256 cells, and used no
brute-force fallback. TE-driven presentation was 53.9 fps. Main and renderer
stack high-water marks were 2,600/4,096 and 1,988/3,072 bytes.

The distance-joint lab adds eight fixed-capacity joint slots and canonically
constrains one circle to a world pivot. Its physics world is 15,520 bytes, its
two render snapshots are 504 bytes each, and the complete image uses 193,012
bytes of RAM. Native and RP2040 reset/right-30/right-30-up-15 hashes are
`695073bd`, `ba22ef24`, and `4e8d1ac6`; the tick-45 framebuffer CRC-32 is
`bc0cfa77`. A clean opening window ran 2,934 ticks at 119.9 Hz with zero skipped
ticks and two over-budget updates; presentation averaged 48.9 fps. The isolated
2,000-tick device profile measured 2.173 ms mean and 6.816 ms maximum for the
grid path, with no 8.333 ms budget violations. The brute-force path averaged
2.382 ms, and both paths ended in exactly matching state. Main and renderer
stack high-water marks were 2,752/4,096 and 2,676/3,584 bytes.

The following physical measurements describe the preceding single-sprite
snapshot and remain the scheduling/display baseline for the new collision lab.
On hardware, normal presentation remained about 59.6 fps while the simulation
advanced at 120 Hz. Snapshot state was typically 2.8-6.4 ms old at the start of
the SPI write, with a 10.0 ms observed dirty-update maximum. The maximum
simulation update was 1,149 us of the 8,333 us budget; maximum scheduler backlog
was one, with zero skipped and zero over-budget ticks. Sixteen back-to-back USB
status sessions left those counters unchanged. Main and renderer stack
high-water marks were 1,184/2,048 and 628/2,048 bytes respectively.

Asynchronous full redraws measured 81,906-82,094 us. During those intervals the main
thread continued to simulate and publish; the renderer coalesced superseded
snapshots, then resumed TE-driven dirty presentation with the latest state.
Scheduler backlog and skipped-tick counters remained unchanged. The A button
and `picosystem game redraw` both post this same coalesced request rather than
calling graphics code from their requesting context. The A-button path was
visually confirmed without tearing. The sprite jumps forward when the transfer
finishes because roughly ten pixels of 120 Hz simulation occurred during the
roughly 82 ms in which the renderer is occupied; those obsolete intermediate
snapshots were intentionally not replayed. The collision lab preserves that
coalescing contract but presents several merged body regions per panel period.

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

The earlier single-threaded framebuffer baseline established the buffer sizes
and dirty-region geometry: 115200 bytes for one 240 x 240 RGB565 framebuffer
and 3840 bytes for an eight-row transfer buffer. Its initial bounded full
transfer took 89840 us (1252 KiB/s), while routine 18 x 18 dirty transfers took
about 820-833 us. After 3518 fixed updates it sustained 62.5 fps with zero
skipped ticks, including twelve back-to-back USB status requests. The animated
sprite, D-pad steering, and synchronous full redraws were visually confirmed
without corruption. Those 62.5 Hz and blocking-redraw figures are historical;
the current 120 Hz decoupled loop above replaces that scheduling path.

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

The later dense-update matrix measures deterministic full-width bands,
scattered tiles, and contiguous frames at several configured clocks. Stock
PIO/DMA reaches 95.2% payload efficiency at its 31.25 MHz program limit and
presents a full frame in 30.972 ms. PL022/DMA at 62.5 MHz is faster for the same
contiguous frame at 18.361 ms, but repeated DMA/window setup makes 100 tiles
take 102.914 ms. Polling PL022 barely improves when configured above 20 MHz.
These results favor a size- and shape-aware transport policy; the current
dirty-first image remains on polling PL022. Full distributions and reproduction
commands are in [the dense-display report](../benchmarks/display-throughput/README.md).
The current schema-2 profiler also includes a synthetic full-frame raster load
with 64 moving circle/box bodies and 112 links, and reports remaining mean time
inside conservative 30 Hz and 60 Hz processing budgets. With 62.5 MHz
PL022/DMA, optimized 32-bit triangle edges, and a one-write frame transfer, that
scene draws in 13.346 ms and presents in 18.328 ms: 31.57 fps unpaced with
1.659 ms of mean 30 Hz processing headroom. Every-second-TE pacing measures
29.805 fps on the approximately 59.6 Hz panel.

The subsequent dual-core image rasterizes that workload on bare-metal core 1,
then presents the completed framebuffer with one 62.5 MHz PL022/DMA write from
core 0. A 4,896-frame physical run sustained 29.8 fps while the authoritative
simulation completed 18,494 ticks at 120.0 Hz with zero skipped ticks. Core-1
raster time was 9.667 ms (9.935 ms observed maximum), transfer time was
19.242 ms, and core-1 stack use was 376/4,096 bytes. The run recorded 244
updates over the 8.333 ms physics budget and a 28.890 ms maximum, but the
deadline scheduler recovered every tick. Paused live-scene and dense-frame
checks produced byte-identical core-0/core-1 results and restored the original
framebuffer after each comparison.

Because the fast coordinator runs at priority -1, it leaves a one-millisecond
handoff window after every frame and uses nonblocking framebuffer acquisition.
This prevents continuous presentation from starving the lower-priority USB
shell and prevents mutex priority inheritance from promoting a long capture
above simulation. With that policy, a clean 4,365-tick run held 119.9 Hz and
29.8 fps with zero skipped ticks. A paused capture completed in 7.1 seconds.
A live capture held the coherent framebuffer for about 99 seconds and therefore
froze presentation, but all 16,240 simulation ticks completed at 120.0 Hz with
zero skips. Pause before capture for deterministic automation and practical
latency.

On a cold power-on, the backlight remained visually dark until the completed
frame appeared; no bright or white startup flash was observed.
