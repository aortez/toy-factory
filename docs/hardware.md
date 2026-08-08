# PIM559 hardware map

This table is the working contract for the Zephyr board port. It is derived
from Pimoroni's [PicoSystem schematic](https://cdn.shopify.com/s/files/1/0174/1800/files/picosystem_schematic.pdf?v=1633439554)
and [native hardware implementation](https://github.com/pimoroni/picosystem/blob/main/libraries/hardware.cpp).

| GPIO | Function | First-use milestone |
|---:|---|---|
| GP0 | Internal debug UART TX | Optional debugger work |
| GP1 | Internal debug UART RX | Optional debugger work |
| GP2 | Charge indicator LED | Power/charger support |
| GP4 | LCD reset | Display |
| GP5 | LCD chip select | Display |
| GP6 | LCD SPI0 clock | Display |
| GP7 | LCD SPI0 MOSI | Display |
| GP8 | LCD tearing-effect/vsync input | Optimized display |
| GP9 | LCD data/command | Display |
| GP11 | Piezo audio PWM | Audio |
| GP12 | LCD backlight PWM | Display |
| GP13 | RGB LED green | GPIO bring-up |
| GP14 | RGB LED red | GPIO bring-up |
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
buttons, RGB LED, SPI display, and PWM backlight. The display test uses RGB565
at 20 MHz and deliberately does not use the tearing-effect signal. Before
enabling settings, a filesystem, or unusually large images, audit the factory
firmware's flash/data layout and define explicit storage partitions. A
peripheral should be added to the device tree only when its driver milestone
begins, keeping early failures easy to isolate.

On the tested PIM559, sending the 115200-byte orientation frame in bounded
eight-row chunks took 109393 us (1028 KiB/s). The earlier one-row baseline took
194685 us (577 KiB/s), so batching reduced latency by about 44%. These figures
measure the complete Zephyr display call path, including panel-window and driver
overhead; they are not raw SPI wire-speed measurements.
