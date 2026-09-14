/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_founder_exit.h"

#include <errno.h>
#include <inttypes.h>
#include <stdio.h>

int toy_factory_garden_founder_exit_apply(struct picosystem_garden_world *world,
					  struct toy_factory_garden_founder_exit *result)
{
	if ((world == NULL) || (result == NULL) || world->auto_gardener_enabled ||
	    (world->logic_tick_count % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR != 0U)) {
		return -EINVAL;
	}
	/* Validate before looking through arrays, including valid no-op worlds. */
	struct picosystem_garden_seed_sites sites;
	const int valid = picosystem_garden_world_seed_sites(world, &sites);
	if (valid != 0) {
		return valid;
	}
	struct picosystem_garden_world candidate = *world;
	struct toy_factory_garden_founder_exit next = {
		.tick = world->logic_tick_count,
		.before_hash = picosystem_garden_world_hash(world),
	};
	for (uint8_t i = 0U; i < world->plant_count; ++i) {
		const struct picosystem_garden_plant *const p = &world->plants[i];
		if ((p->parent_lineage_id != 0U) || (p->flags & PICOSYSTEM_GARDEN_PLANT_DEAD)) {
			continue;
		}
		for (uint8_t other = 0U; other < world->plant_count; ++other) {
			if ((other != i) &&
			    !(world->plants[other].flags & PICOSYSTEM_GARDEN_PLANT_DEAD) &&
			    (world->plants[other].base_column == p->base_column)) {
				return -EINVAL;
			}
		}
		/* A one-column patch selects only this plant after the overlap check.
		 * Reuse death/resource/light behavior; never fabricate a corpse here.
		 */
		const int err = picosystem_garden_world_experimental_kill_patch(
			&candidate, p->base_column, p->base_column);
		if (err != 0) {
			return err;
		}
		next.killed_ids[next.count++] = p->lineage_id;
		next.energy = (uint16_t)(next.energy + p->stored_energy);
		next.water = (uint16_t)(next.water + p->stored_water);
		next.nodes = (uint16_t)(next.nodes + p->node_count);
	}
	next.after_hash = picosystem_garden_world_hash(&candidate);
	*world = candidate;
	*result = next;
	return 0;
}

int toy_factory_garden_founder_exit_print(const struct toy_factory_garden_founder_exit *result)
{
	if ((result == NULL) || (result->count > PICOSYSTEM_GARDEN_MAX_PLANTS)) {
		return -EINVAL;
	}
	printf("{\"rule\":\"%s\",\"tick\":%" PRIu32 ",\"before_hash\":\"%08" PRIx32
	       "\",\"after_hash\":\"%08" PRIx32 "\",\"energy\":%u,\"water\":%u,"
	       "\"nodes\":%u,\"killed\":[",
	       TOY_FACTORY_GARDEN_FOUNDER_EXIT_RULE, result->tick, result->before_hash,
	       result->after_hash, result->energy, result->water, result->nodes);
	for (uint8_t i = 0U; i < result->count; ++i) {
		printf("%s%" PRIu32, i ? "," : "", result->killed_ids[i]);
	}
	printf("]}");
	return ferror(stdout) ? -EIO : 0;
}
