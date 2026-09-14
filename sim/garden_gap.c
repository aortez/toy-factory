/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_gap.h"

#include <errno.h>
#include <inttypes.h>
#include <stdio.h>

#include "garden_light.h"

int toy_factory_garden_gap_apply(struct picosystem_garden_world *world,
				 struct toy_factory_garden_gap *result)
{
	if ((world == NULL) || (result == NULL) ||
	    (world->plant_count > PICOSYSTEM_GARDEN_MAX_PLANTS) ||
	    (world->logic_tick_count % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR != 0U)) {
		return -EINVAL;
	}
	const struct picosystem_garden_plant *target = NULL;
	for (uint8_t index = 0U; index < world->plant_count; ++index) {
		const struct picosystem_garden_plant *plant = &world->plants[index];
		if ((plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) ||
		    (plant->age_ecology_ticks < PICOSYSTEM_GARDEN_SUN_CYCLE_TICKS)) {
			continue;
		}
		if ((target == NULL) || (plant->node_count > target->node_count) ||
		    ((plant->node_count == target->node_count) &&
		     (plant->lineage_id < target->lineage_id))) {
			target = plant;
		}
	}
	if (target == NULL) {
		return -ENOENT;
	}
	struct toy_factory_garden_gap gap = {
		.tick = world->logic_tick_count,
		.lineage_id = target->lineage_id,
		.nodes = target->node_count,
		.column = target->base_column,
		.energy = target->stored_energy,
		.water = target->stored_water,
	};
	/* Validate/mutate before hashing potentially malformed input. */
	const struct picosystem_garden_world before = *world;
	const int err = picosystem_garden_world_experimental_clear(world, gap.lineage_id);
	if (err != 0) {
		return err;
	}
	gap.before_hash = picosystem_garden_world_hash(&before);
	gap.after_hash = picosystem_garden_world_hash(world);
	*result = gap;
	return 0;
}

int toy_factory_garden_gap_print(const struct toy_factory_garden_gap *gap)
{
	printf("{\"type\":\"gap\",\"protocol\":\"%s\",\"tick\":%" PRIu32 ",\"id\":%" PRIu32
	       ",\"column\":%u,\"nodes\":%u,\"energy\":%u,\"water\":%u,"
	       "\"before_hash\":\"%08" PRIx32 "\",\"after_hash\":\"%08" PRIx32 "\"}\n",
	       TOY_FACTORY_GARDEN_GAP_PROTOCOL, gap->tick, gap->lineage_id, gap->column, gap->nodes,
	       gap->energy, gap->water, gap->before_hash, gap->after_hash);
	return ferror(stdout) ? -EIO : 0;
}
