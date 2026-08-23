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

## Current Hourglass validation

The recommended 62.5 MHz PL022/DMA image runs a deterministic 192-grain
Hourglass at an exact 60 Hz simulation cadence and presents complete frames at
about 30 fps. Its isolated 1,000-tick replay averaged 13.688 ms, peaked at
14.394 ms, and recorded no 60 Hz violations. A first live 832-tick window under
concurrent rendering averaged 14.984 ms in physics and exposed occasional
deadline overruns, so reducing live contention remains the next optimization
target.

The image uses 251,180 bytes of the 255 KiB Zephyr RAM region and 234,744 bytes
of flash, leaving 9,940 bytes of linker RAM plus the separately reserved 8 KiB
core-1 mailbox/stack area. The conservative image uses 221,276 bytes of Zephyr
RAM and 229,128 bytes of flash. The immutable render snapshot is 856 bytes.
The tagged game-world and snapshot unions permit the normal 192-grain scene
without allocating inactive scene payloads. Full results are in the
[Hourglass report](../benchmarks/hourglass/README.md).

Exact USB-controlled replay reproduced tick 360 at hash `010f9b49` and
framebuffer CRC-32 `d199c13c` after a directional/flip sequence. A 600-tick
neutral drain reached hash `9d12ec5e` and CRC-32 `09f0b159`. Rendering the same
paused scene on each core produced matching CRC-32 `fb1db43e` and restored the
original framebuffer. Physical D-pad gravity tilt, X flip, Y reset, A redraw,
and B tone behavior were also exercised on the PIM559.

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

## Decoupled 60 Hz simulation and presentation

Zephyr and every device driver run on core 0. Its priority-0 main thread owns
input and all authoritative simulation state; the USB shell runs at priority 1.
The conservative image uses a preemptible priority-2 damage renderer. The fast
PL022/DMA image instead uses a short priority -1 coordinator and a bare-metal
core-1 raster worker. Core 1 receives immutable snapshots through reserved SRAM,
signals completion through the SIO FIFO mailbox interrupt, and never calls
Zephyr or a driver. Once two or more simulation deadlines are due, the main
loop reserves a one-millisecond recovery window so the shell can still accept
diagnostics or a bootloader request. An isolated late tick may catch up and
reach its ordinary scheduler sleep without the added delay. The scheduler
represents 60 Hz as rational kernel-tick deadlines rather than rounding it to
an integer millisecond period. With the configured 10 kHz kernel tick, the
deadline spacing repeats 166, 167, and 167 ticks, totaling exactly 500 ticks for
three updates and 10,000 ticks for 60 updates. A native host test checks this
pattern, catch-up boundaries, validation, and the constant-time due-count result
against an iterative reference.

Simulation uses Q16.16 positions and publishes an 856-byte immutable snapshot
of up to 12 circle, oriented-box, or capsule bodies, eight physical static
segments, 16 render-only guide segments, two ropes with up to 12 particles
each, eight render records each for distance and revolute joints, and one
canonical box sensor at a deterministic 30 Hz real-time cadence. Physics remains
at 60 Hz; pause, reset, redraw, and exact-step controls force a current snapshot.
Two slots and a short spin-lock-protected copy prevent the renderer from
observing partially updated state. A saturated semaphore is only a wake-up
hint: if two or more simulation states arrive during a panel period, the
renderer deliberately coalesces the older ones. The main thread never waits for
TE, framebuffer work, core 1, or SPI, and neither renderer mode reads live
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

The preceding multi-link lab adds eight fixed-capacity revolute-joint slots and
uses four of them for one world pin plus three body-to-body hinges. Its physics
world is 16,076 bytes, its two render snapshots are 600 bytes each, and the
recommended full-frame image uses 205,300 bytes of Zephyr RAM. The PIM559
reproduced the native reset hash `2eee9251`; its coherent reset framebuffer is
CRC-32 `c965155f`, and the exact right-30/up-15 device sequence reaches hash
`7e462383` and framebuffer CRC-32 `4ddc9697`. An isolated 1,000-tick device
profile averaged 3.539 ms for the grid and 3.793 ms for the reference, with no
8.333 ms budget violations and exact state agreement. A live 14,416-tick window
held 120.0 Hz simulation with one isolated skipped tick amid USB profiling and
status activity, while full-frame presentation averaged 29.8 fps. The expanded
snapshot drove renderer stack use to 3,204 of 3,584 bytes during bring-up, so
the configured renderer stack is now 4,096 bytes.

The adaptive-convergence fast image uses 181,284 bytes of flash. It performs
one revolute position pass and adds alternating passes only while an anchor is
more than one pixel apart, with a four-pass hard limit. Isolated 4-, 6-, and
8-link fixtures averaged 1.569, 2.315, and 3.897 ms respectively, with no
8.333 ms budget violations and exact grid/reference agreement. Their average
pass counts were 1.000, 1.172, and 2.552, and maximum anchor errors were 0.495,
1.118, and 1.158 pixels. The 8-link maximum was 5.188 ms.

The preceding motor-and-limit lab expands each revolute slot with a bounded motor
row, creation-relative angular range, and per-step limit state. Its physics
world is 16,364 bytes, its profiling workspace is 23,984 bytes, and the
recommended full-frame image uses 206,404 bytes of Zephyr RAM plus 184,216
bytes of flash. The canonical root hinge targets 1/96 radian per tick with at
most 1/8 angular impulse per tick; the final hinge is limited to plus or minus
one radian. The PIM559 reproduced reset/right-30/right-30-up-15 hashes
`13420a19`, `c65f5731`, and `66e3ab10`, plus framebuffer CRC-32 `0633575c` at
tick 45. Its isolated 1,000-tick grid profile averaged 4.136 ms, reached a 5.760
ms p95 and 7.001 ms maximum, and recorded no 8.333 ms budget violations. The
brute-force reference averaged 4.418 ms; both modes ended at `a554f3c3` with
exact state agreement. Maximum hinge-anchor separation was 0.947 pixels and
maximum angular-limit violation was 0.0175 radian. A 20,055-tick live window
held 119.9 Hz with seven skipped ticks while full-frame presentation remained
at 29.8 fps. Concurrent rendering and USB activity produced 5,143 updates over
8.333 ms and a 25.008 ms maximum; faster intervening updates recovered most
deadlines.

The preceding powered Machine Lab adds eight fixed-capacity prismatic slots and
uses one for a motorized world rail with creation-relative travel limits. Its
20,020-byte physics world uses compact per-body velocity revisions to cache
unchanged contact and prismatic rows; the serialized profiling workspace is
28,672 bytes. The recommended image uses 216,260 bytes of Zephyr RAM and
192,148 bytes of flash, leaving about 44 KiB in the 255 KiB region in addition
to the separately reserved 8 KiB core-1 area.

The PIM559 reproduced reset/right-30/right-30-up-15 hashes `58ed1623`,
`c79a2439`, and `107b9aa0`, plus framebuffer CRC-32 `410a58ac` at tick 45. Its
isolated 1,000-tick grid profile averaged 3.535 ms, reached a 4.992 ms p95 and
6.379 ms maximum, and recorded no 8.333 ms budget violations. The brute-force
reference averaged 3.662 ms; both modes ended at `4ed9cc6f` with exact state
agreement. A concurrent 3,798-tick window held 119.2 Hz while full-frame
presentation averaged 29.8 fps. It recorded eight skipped ticks, a five-tick
worst backlog, and mean/maximum physics time of 5.788/9.786 ms. A settled
sampled tick skipped 16 of 42 scheduled contact visits. Main, render, and core-1
stack high-water marks were 3,648/4,096, 3,588/4,096, and 344/4,096 bytes.

The preceding sensor/contact-event image adds eight fixed-capacity axis-aligned
box sensors, exact circle/box overlap tests, persistent pair masks, and a
258-record lifecycle-event buffer. Each event is six bytes and is pair-level
even when a physical manifold has two points. The sensor mask fits in existing
grid-cell padding, so the 16 x 16 scratch grid remains 1,024 bytes. The physics
world is 21,804 bytes, the complete game world is 21,812 bytes, each immutable
render snapshot is 744 bytes, and the serialized profile workspace is 31,208
bytes. The conservative image uses 214,908 bytes of Zephyr RAM and 193,336
bytes of flash.

The recommended image places its 16,480-byte inlined physics step in SRAM to
avoid XIP contention with the core-1 raster worker. It uses 238,532 bytes of the
255 KiB Zephyr region and 198,560 bytes of flash, retaining 22,588 bytes of
linker RAM headroom plus the separately reserved 8 KiB core-1 area. Main,
render, shell-profile, and core-1 stack high-water marks were 3,632/4,096,
3,668/4,096, 3,856/5,120, and 336/4,096 bytes.

The PIM559 reproduced reset/right-30/right-30-up-15 hashes `765185a2`,
`4a1dd4fa`, and `2a43f4e8`, plus framebuffer CRC-32 `dd67545b` at tick 45. Its
schema-version-7 isolated 1,000-tick grid profile averaged 2.723 ms, reached a
3.584 ms p95 and 4.722 ms maximum, and recorded no 8.333 ms budget violations.
The brute-force reference averaged 2.998 ms; both modes ended at `1d58dedd`
with exact state agreement. Grid filtering retained 8.017 of 70 possible pairs
and 0.685 of seven body/sensor tests per tick. Both modes produced 182 begin,
523 stay, and 182 end events. A clean 4,978-tick concurrent window held 120.0
Hz with zero skipped ticks while full-frame presentation averaged 29.8 fps.
Mean complete-update/physics/snapshot time was 5.046/4.356/0.689 ms; four
updates exceeded 8.333 ms and the worst backlog was three ticks. A paused scene
check produced identical core-0/core-1 pixels in 9.728 ms and restored the
framebuffer exactly.

The preceding sleeping image adds an authoritative sleep mask, per-body quiet
counters, deterministic contact/joint-island wake propagation, and sleep work
counters. Its physics world is 21,864 bytes, complete game world is 21,872
bytes, render snapshot remains 744 bytes, and serialized profile workspace is
31,304 bytes. The conservative image uses 215,276 bytes of Zephyr RAM and
196,328 bytes of flash. The recommended 62.5 MHz PL022/DMA image places its
16,576-byte inlined physics step in SRAM and uses 239,220 bytes of the 255 KiB
Zephyr region plus 201,876 bytes of flash, retaining 21,900 bytes of linker RAM
headroom in addition to the separately reserved 8 KiB core-1 area.

The PIM559 reproduced reset/right-30/right-30-up-15 hashes `765185a2`,
`4a1dd4fa`, and `2a43f4e8`, plus framebuffer CRC-32 `dd67545b` at tick 45. Its
schema-version-8 isolated 1,000-tick moving profile averaged 2.792 ms for the
grid and 3.117 ms for the brute-force reference, with no 8.333 ms budget
violations and exact final state agreement at `46020daa`. The 2,000-tick
neutral profile recorded one sleep and one wake transition, one sleeping body
for 664 sampled body-ticks, and 663 sleeping contacts skipped by both modes.
Grid/reference state agreed exactly at `ea65ce22`; means were 3.456 and 3.787
ms. The deterministic sleep sequence reached tick 1,228 at `5e0274dc` and
framebuffer CRC-32 `b78934e6`, visibly rendering the sleeping body blue/white.

The preceding spring-and-conveyor image extends distance joints with an optional
bounded soft row and static segments with signed start-to-end surface speed. Its
physics world is 22,112 bytes, complete game world is 22,120 bytes, render
snapshot is 752 bytes, and serialized profile workspace is 31,776 bytes. The
conservative image uses 216,228 bytes of Zephyr RAM and 199,968 bytes of flash.
The recommended 62.5 MHz PL022/DMA image uses 240,988 bytes of the 255 KiB
Zephyr region and 205,308 bytes of flash, retaining 20,132 bytes of linker RAM
headroom plus the separately reserved 8 KiB core-1 area.

The PIM559 reproduced reset/right-30/right-30-up-15 hashes `a91c46a3`,
`f3643510`, and `3db7c5b5`. The coherently presented tick-45 framebuffer is
CRC-32 `c8ba210d`. The neutral sleep sequence reached tick 1,723 at `51bb08c0` with one
sleeping body and framebuffer CRC-32 `0a848efb`.

Its schema-version-9 isolated 1,000-tick moving profile averaged 2.718 ms for
the grid and 3.060 ms for the brute-force reference, with 4.660/4.872 ms maxima
and no 8.333 ms budget violations. Both modes ended at `728d8683` with exact
state agreement. The grid retained 7.043 of 70 possible pairs per tick; each
mode recorded 1,000 spring joint-ticks, 7,000 spring visits, ten conveyor
contact-ticks, and 70 conveyor visits. The separate 2,000-tick neutral profile
averaged 3.630/3.989 ms, recorded one sleep transition, 398 sleeping body-ticks,
794 skipped sleeping contacts, and 710 conveyor contact-ticks, and agreed at
`3d88bb5f` with zero budget violations.

An initial 1,497-tick concurrent window held 119.9 Hz simulation with no
skipped ticks and a three-tick worst backlog while full-frame presentation ran
at 29.6 fps. Mean/maximum complete update time was 5.484/10.905 ms; physics was
4.742/10.002 ms. Core-1 rasterization was 10.264 ms and the latest contiguous
full-frame transfer was 19.084 ms. Main, render, shell-profile, and core-1 stack
high-water marks were 3,712/4,096, 3,692/4,096, 3,896/5,120, and 344/4,096
bytes. A paused live-scene check produced identical core-0/core-1 pixels in
9.809 ms and restored the framebuffer exactly. A CRC-validated 240 x 240 PNG
capture completed in 8.2 seconds.

The reciprocal-rope implementation makes body endpoint pins two-way and gives
unpinned particles a one-pixel collision radius against external circles,
boxes, capsules, and static segments. It uses six alternating length passes and
three interleaved collision passes. Equal-and-opposite position and
radial-velocity response includes the endpoint body's translation and rotation;
reciprocal body/body pins also join the deterministic sleep graph. There is no
self-collision or rope/rope collision in this bounded milestone.

Its physics world is 22,636 bytes, each render snapshot is 856 bytes, and the
serialized profile workspace is 33,304 bytes. The current conservative
Clockwork image uses 221,124 bytes of Zephyr RAM and 218,252 bytes of flash. The
recommended 62.5 MHz PL022/DMA image uses 250,620 bytes of the 255 KiB Zephyr
region and 223,976 bytes of flash, retaining 10,500 bytes of linker RAM headroom
plus the separately reserved 8 KiB core-1 area. Both images route compiler integer
division through the RP2040 hardware divider using interrupt-safe Pico SDK
wrappers.

The 60 Hz PIM559 Clockwork build reproduced reset and right-15/up-8 hashes
`13d7f3d0` and `e7a7ba97`. The coherently presented tick-23 framebuffer is
CRC-32 `4efbf582`; the neutral sequence reached tick 259 at `3f94eab2` with
framebuffer CRC-32 `73e6b4d7`.

A clean 3,744-tick device window sustained 60.0 Hz simulation and 29.8 fps
presentation with zero skipped or over-budget updates. Physics averaged 9.719
ms and peaked at 13.000 ms; complete updates averaged 10.243 ms and peaked at
13.644 ms. Core-1 rasterization was 10.913 ms with an 11.437 ms observed
maximum, and the 62.5 MHz PL022/DMA full-frame transfer took 19.284 ms.

Its schema-version-13 isolated 1,000-tick moving profile averaged 5.566 ms for
the grid and 6.044 ms for the brute-force reference, with 8.488/9.002 ms
maxima, no 16.667 ms budget violations, and exact final agreement at
`2ff3a57b`. The rope stage averaged 1.619/1.613 ms. The separate neutral
profile averaged 6.000/6.447 ms and agreed exactly at `9d3ad372`, again without
violations. Relative to the preceding 120 Hz grid profile, scheduled physics
CPU fell from 590 to 334 ms per real second.

A concurrent window advanced 5,723 measured ticks at 60.0 Hz while full-frame
presentation held 29.8 fps. Backlog was one, with zero skipped ticks and zero
over-budget updates; mean/maximum physics time was 7.463/13.399 ms and complete
updates averaged 7.944 ms with a 14.918 ms maximum. Main, render, and
shell-profile stack high-water marks were 4,016/5,120, 4,044/5,120, and
4,184/5,120 bytes.

For comparison, the preceding schema-version-12 120 Hz moving profile averaged
4.920/5.313 ms with 6.935/7.470 ms maxima and agreed at `1600fb06`. Its neutral
profile averaged 5.590/5.887 ms and agreed at `34a04b59`; an earlier concurrent
window held 120.0 Hz and 29.6 fps with one skipped tick.

The preceding one-way capsule-and-rope image added exact capsule interactions
against all body shapes, static segments, and box sensors, plus two fixed rope
slots with up to 12 Verlet particles each. The canonical scene uses one rotating
capsule and one eight-particle rope pinned between its local endpoint and a
fixed world anchor. The rope follows body motion kinematically, runs six
alternating position passes, and does not yet feed impulses back into rigid
bodies or collide its particles.

Its physics world is 22,584 bytes, each render snapshot is 856 bytes, and the
serialized profile workspace is 33,232 bytes. The conservative image uses
220,140 bytes of Zephyr RAM and 209,628 bytes of flash. The recommended 62.5
MHz PL022/DMA image uses 246,684 bytes of the 255 KiB Zephyr region and 214,960
bytes of flash, retaining 14,436 bytes of linker RAM headroom plus the
separately reserved 8 KiB core-1 area. Measured main, render, shell-profile, and
core-1 stack high-water marks are 3,928/4,608, 4,036/5,120, 4,160/5,120, and
360/4,096 bytes.

The PIM559 reproduced reset/right-30/right-30-up-15 hashes `63a73949`,
`a1734ba1`, and `63bfd54f`. The coherently presented tick-45 framebuffer is
CRC-32 `5111bc8b`; the neutral sleep sequence reached tick 1,723 at `cfd92dca`
with framebuffer CRC-32 `5c0542c9`.

Its schema-version-10 isolated 2,000-tick moving profile averaged 4.502 ms for
the grid and 5.100 ms for the brute-force reference, with 6.749/7.458 ms
maxima, no 8.333 ms budget violations, and exact final agreement at
`91744aeb`. The rope stage averaged 1.157/1.154 ms, visited 42 constraints per
tick, and held maximum segment error to 0.534 pixel. The separate 2,000-tick
neutral profile averaged 5.346/5.949 ms and agreed exactly at `7d4ae8ca`; the
production grid had no deadline violations, while the diagnostic reference
path had 18. A clean concurrent window advanced 4,233 ticks at 118.9 Hz with
35 skipped ticks while full-frame presentation held 29.7 fps.

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
the current 60 Hz decoupled loop above replaces that scheduling path.

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

The heavier powered Machine Lab exceeded the earlier 120-second live-capture
deadline and needed about one additional minute of held-DTR draining to finish
the pending output. The host capture timeout is now 240 seconds. This is a
bounded diagnostic fallback, not a gameplay workload; pause before capture so
the shell has the full core-0 idle budget and the selected frame remains exact.

On a cold power-on, the backlight remained visually dark until the completed
frame appeared; no bright or white startup flash was observed.
