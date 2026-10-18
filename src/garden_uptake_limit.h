/* SPDX-License-Identifier: Apache-2.0 */
#ifndef PICOSYSTEM_GARDEN_UPTAKE_LIMIT_H_
#define PICOSYSTEM_GARDEN_UPTAKE_LIMIT_H_

#if defined(__ZEPHYR__)
#error "Late uptake limiting is an unqualified host-only experiment"
#endif

#include <stdint.h>

#define PICOSYSTEM_GARDEN_UPTAKE_LIMIT_VERSION    1U
#define PICOSYSTEM_GARDEN_UPTAKE_LIMIT_AFTER_TICK UINT32_C(626580)
#define PICOSYSTEM_GARDEN_UPTAKE_LIMIT_CAPACITY   512U

/* Limit before soil debit, using storage after the preceding root. The caller
 * validates world storage. Do not reserve capacity for later upkeep or growth.
 */
static inline uint8_t picosystem_garden_uptake_limit(uint8_t available, uint16_t stored,
						     uint32_t logic_tick)
{
	if (logic_tick <= PICOSYSTEM_GARDEN_UPTAKE_LIMIT_AFTER_TICK) {
		return available;
	}
	if (stored >= PICOSYSTEM_GARDEN_UPTAKE_LIMIT_CAPACITY) {
		return 0U;
	}
	const uint16_t space = (uint16_t)(PICOSYSTEM_GARDEN_UPTAKE_LIMIT_CAPACITY - stored);
	return (available < space) ? available : (uint8_t)space;
}

#endif
