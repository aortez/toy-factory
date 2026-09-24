/* SPDX-License-Identifier: Apache-2.0 */
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_plant_slots.h"

uint8_t picosystem_garden_plant_slots_limit(bool enabled, uint32_t tick)
{
	return enabled && tick > PICOSYSTEM_GARDEN_PLANT_SLOTS_AFTER ? 16U : 8U;
}

int picosystem_garden_plant_slots_parse(const char *name, bool *enabled)
{
	if ((name == NULL) || (enabled == NULL) || *enabled || (strcmp(name, "16") != 0)) {
		return -EINVAL;
	}
	*enabled = true;
	return 0;
}

int picosystem_garden_plant_slots_print(bool enabled, uint32_t tick)
{
	if (!enabled) {
		return 0;
	}
	return printf("\"plant_admission\":{\"rule\":\"%s\",\"after\":%u,\"limit\":%u},",
		      PICOSYSTEM_GARDEN_PLANT_SLOTS_RULE, PICOSYSTEM_GARDEN_PLANT_SLOTS_AFTER,
		      picosystem_garden_plant_slots_limit(enabled, tick)) < 0
		       ? -EIO
		       : 0;
}
