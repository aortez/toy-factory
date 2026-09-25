/* SPDX-License-Identifier: Apache-2.0 */
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_world.h"

uint8_t picosystem_garden_seed_order_start(uint32_t tick, uint8_t plant_count)
{
	const uint32_t period =
		PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR * PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR;
	if ((tick <= PICOSYSTEM_GARDEN_SEED_ORDER_AFTER) || ((tick % period) != 0U) ||
	    (plant_count == 0U)) {
		return 0U;
	}
	return (uint8_t)(((tick - PICOSYSTEM_GARDEN_SEED_ORDER_AFTER) / period) % plant_count);
}

int picosystem_garden_seed_order_parse(const char *name, bool *enabled)
{
	if ((name == NULL) || (enabled == NULL) || *enabled || (strcmp(name, "rotating") != 0)) {
		return -EINVAL;
	}
	*enabled = true;
	return 0;
}

int picosystem_garden_seed_order_print(bool enabled, uint32_t tick, uint8_t plant_count)
{
	if (!enabled) {
		return 0;
	}
	if (plant_count > PICOSYSTEM_GARDEN_MAX_PLANTS) {
		return -EINVAL;
	}
	return printf("\"seed_order\":{\"rule\":\"%s\",\"after\":%u,\"start\":%u},",
		      PICOSYSTEM_GARDEN_SEED_ORDER_RULE, PICOSYSTEM_GARDEN_SEED_ORDER_AFTER,
		      picosystem_garden_seed_order_start(tick, plant_count)) < 0
		       ? -EIO
		       : 0;
}
