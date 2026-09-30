/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_reach.h"

#include <assert.h>
#include <errno.h>
#include <string.h>

int main(void)
{
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, 3U) == 0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 0U) ==
	       0);
	world.logic_tick_count = 15U;
	world.plants[0].genome.dispersal = -2;
	world.seed_count = 1U;
	world.seeds[0] = (struct picosystem_garden_seed){
		.genome = world.plants[0].genome,
		.parent_lineage_id = world.plants[0].lineage_id,
		.generation = 1U,
		.column = 3U,
		.species_id = PICOSYSTEM_GARDEN_SPECIES_FLOWER,
	};
	/* The mutated seed would have different reach; it did not place itself. */
	world.seeds[0].genome.dispersal = 2;
	const struct picosystem_garden_world before = world;
	struct picosystem_garden_seed_audit seeds = {.ecology_step = true};
	FILE *stream = tmpfile();
	assert(stream != NULL);
	assert(toy_factory_garden_reach_print(stream, &world, &seeds) == 0);
	assert(memcmp(&world, &before, sizeof(world)) == 0);
	rewind(stream);
	char row[1024];
	assert(fgets(row, sizeof(row), stream) != NULL);
	assert(strstr(row, "\"origin\":0,\"dispersal\":-2,\"choices\":[3,3,4,4,5,5]") != NULL);
	assert(fclose(stream) == 0);
	stream = tmpfile();
	assert(stream != NULL);
	assert(toy_factory_garden_reach_print(NULL, &world, &seeds) == -EINVAL);
	assert(toy_factory_garden_reach_print(stream, NULL, &seeds) == -EINVAL);
	assert(toy_factory_garden_reach_print(stream, &world, NULL) == -EINVAL);
	seeds.ecology_step = false;
	assert(toy_factory_garden_reach_print(stream, &world, &seeds) == -EINVAL);
	seeds.ecology_step = true;
	seeds.count = PICOSYSTEM_GARDEN_MAX_SEEDS + 1U;
	assert(toy_factory_garden_reach_print(stream, &world, &seeds) == -EINVAL);
	seeds.count = 0U;
	world.seeds[0].column = 9U;
	assert(toy_factory_garden_reach_print(stream, &world, &seeds) == -EFAULT);
	world.seeds[0].column = 3U;
	world.lineage_sequence = 2U;
	world.seeds[0].parent_lineage_id = 2U;
	assert(toy_factory_garden_reach_print(stream, &world, &seeds) == -EFAULT);
	assert(ftell(stream) == 0L);
	assert(fclose(stream) == 0);
	return 0;
}
