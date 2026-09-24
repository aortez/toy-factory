/* SPDX-License-Identifier: Apache-2.0 */
#ifndef PICOSYSTEM_GARDEN_FULL_POOL_H_
#define PICOSYSTEM_GARDEN_FULL_POOL_H_

#include <stdbool.h>
#include <stdint.h>

#if defined(__ZEPHYR__) || !defined(TOY_FACTORY_GARDEN_FULL_POOL) ||                               \
	!defined(TOY_FACTORY_GARDEN_PLANT_SLOTS)
#error "Full-pool actions require the explicit host-only plant-slot experiment"
#endif

#define PICOSYSTEM_GARDEN_FULL_POOL_RULE   "post-noon-nonallocating-actions-v1"
#define PICOSYSTEM_GARDEN_FULL_POOL_AFTER  69120U
#define PICOSYSTEM_GARDEN_FULL_POOL_EVENTS 16U

struct picosystem_garden_full_pool_event {
	uint32_t lineage;
	uint16_t node;
	uint8_t action;
	bool allocates;
};

/* Host diagnostics/configuration, not authoritative state. One winner per plant. */
struct picosystem_garden_full_pool_audit {
	uint32_t evaluated[3];
	uint32_t denied;
	struct picosystem_garden_full_pool_event events[PICOSYSTEM_GARDEN_FULL_POOL_EVENTS];
	uint8_t count;
	bool enabled;
	bool overflow;
};

bool picosystem_garden_full_pool_active(bool enabled, uint32_t tick);
int picosystem_garden_full_pool_parse(const char *name, bool *enabled);
int picosystem_garden_full_pool_check(struct picosystem_garden_full_pool_audit *audit,
				      uint32_t lineage, uint16_t node, uint8_t action,
				      bool allocates);
/* JSON fragment with trailing comma; disabled control emits nothing. */
int picosystem_garden_full_pool_print(const struct picosystem_garden_full_pool_audit *audit,
				      uint32_t tick);

#endif
