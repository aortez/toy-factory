/* SPDX-License-Identifier: Apache-2.0 */
#ifndef PICOSYSTEM_GARDEN_SEED_ORDER_H_
#define PICOSYSTEM_GARDEN_SEED_ORDER_H_

#include <stdbool.h>
#include <stdint.h>

#if defined(__ZEPHYR__) || !defined(TOY_FACTORY_GARDEN_SEED_ORDER) ||                              \
	!defined(TOY_FACTORY_GARDEN_DAWN_FINISH)
#error "Seed order is a host-only reserve-handoff experiment"
#endif

#define PICOSYSTEM_GARDEN_SEED_ORDER_RULE  "maintenance-seed-rotation-v1"
#define PICOSYSTEM_GARDEN_SEED_ORDER_AFTER 69120U

/* Stateless visit offset, not a plant-array permutation. Zero outside the
 * maintenance window and for an empty population. No random state is consumed.
 */
uint8_t picosystem_garden_seed_order_start(uint32_t tick, uint8_t plant_count);
int picosystem_garden_seed_order_parse(const char *name, bool *enabled);
/* JSON fragment including trailing comma. Disabled support emits nothing. */
int picosystem_garden_seed_order_print(bool enabled, uint32_t tick, uint8_t plant_count);

#endif
