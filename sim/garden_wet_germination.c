/* SPDX-License-Identifier: Apache-2.0 */
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>

#include "garden_wet_germination.h"

int toy_factory_garden_wet_germination_activate(struct picosystem_garden_world *world)
{
	const uint32_t before = picosystem_garden_world_hash(world);
	const int err = picosystem_garden_world_enable_wet_germination(world);
	if (err != 0) {
		return err;
	}
	printf("{\"type\":\"germination-rule\",\"rule\":\"%s\",\"tick\":%" PRIu32
	       ",\"before_hash\":\"%08" PRIx32 "\",\"after_hash\":\"%08" PRIx32 "\"}\n",
	       PICOSYSTEM_GARDEN_WET_GERMINATION_NAME, world->logic_tick_count, before,
	       picosystem_garden_world_hash(world));
	return ferror(stdout) ? -EIO : 0;
}
