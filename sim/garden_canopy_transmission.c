/* SPDX-License-Identifier: Apache-2.0 */
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_canopy_transmission.h"

bool picosystem_garden_canopy_transmission_active(bool enabled, uint32_t tick)
{
	return enabled && (tick > PICOSYSTEM_GARDEN_CANOPY_TRANSMISSION_AFTER);
}

int picosystem_garden_canopy_transmission_parse(const char *name, bool *enabled)
{
	if ((name == NULL) || (enabled == NULL) || *enabled || (strcmp(name, "fractional") != 0)) {
		return -EINVAL;
	}
	*enabled = true;
	return 0;
}

int picosystem_garden_canopy_transmission_print(bool enabled, uint32_t tick)
{
	if (!enabled) {
		return 0;
	}
	return printf("\"canopy_transmission\":{\"rule\":\"%s\",\"after\":%u,\"active\":%s},",
		      PICOSYSTEM_GARDEN_CANOPY_TRANSMISSION_RULE,
		      PICOSYSTEM_GARDEN_CANOPY_TRANSMISSION_AFTER,
		      picosystem_garden_canopy_transmission_active(enabled, tick) ? "true"
										  : "false") < 0
		       ? -EIO
		       : 0;
}
