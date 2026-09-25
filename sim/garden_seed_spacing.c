/* SPDX-License-Identifier: Apache-2.0 */
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_seed_spacing.h"

uint8_t picosystem_garden_seed_spacing_minimum(bool enabled, uint32_t tick)
{
	return enabled && tick > PICOSYSTEM_GARDEN_SEED_SPACING_AFTER ? 2U : 3U;
}

int picosystem_garden_seed_spacing_parse(const char *name, bool *enabled)
{
	if ((name == NULL) || (enabled == NULL) || *enabled || (strcmp(name, "2") != 0)) {
		return -EINVAL;
	}
	*enabled = true;
	return 0;
}

int picosystem_garden_seed_spacing_print(bool enabled, uint32_t tick)
{
	if (!enabled) {
		return 0;
	}
	return printf("\"seed_spacing\":{\"rule\":\"%s\",\"after\":%u,\"minimum\":%u},",
		      PICOSYSTEM_GARDEN_SEED_SPACING_RULE, PICOSYSTEM_GARDEN_SEED_SPACING_AFTER,
		      picosystem_garden_seed_spacing_minimum(enabled, tick)) < 0
		       ? -EIO
		       : 0;
}
