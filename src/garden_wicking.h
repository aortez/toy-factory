/* SPDX-License-Identifier: Apache-2.0 */
#ifndef PICOSYSTEM_GARDEN_WICKING_H_
#define PICOSYSTEM_GARDEN_WICKING_H_

#if defined(__ZEPHYR__)
#error "Soil wicking is an unqualified host-only experiment"
#endif

#include <stddef.h>
#include <stdint.h>

#define PICOSYSTEM_GARDEN_WICKING_VERSION    1U
#define PICOSYSTEM_GARDEN_WICKING_AFTER_TICK UINT32_C(626580)
#define PICOSYSTEM_GARDEN_WICKING_PERIOD     60U

/* One unit per eligible upward edge, top to bottom. Returns transferred units
 * (not new water), or -EINVAL without mutation for invalid storage. No RNG,
 * allocation or persistent state. Call after lateral flow, before evaporation.
 */
int picosystem_garden_wicking_step(uint8_t *moisture, size_t count, uint32_t logic_tick);

#endif
