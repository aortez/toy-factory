/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_topology.h"

static void unchanged_output(const struct picosystem_garden_world *world, bool valid)
{
	const struct picosystem_garden_world before = *world;
	FILE *output = tmpfile();
	assert(output != NULL);
	assert(toy_factory_garden_topology_print(world, output) == (valid ? 0 : -EINVAL));
	assert(memcmp(world, &before, sizeof(before)) == 0);
	assert(fflush(output) == 0);
	assert(valid ? ftell(output) > 0 : ftell(output) == 0);
	assert(fclose(output) == 0);
}

int main(void)
{
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	unchanged_output(&world, true);
	assert(toy_factory_garden_topology_print(&world, NULL) == -EINVAL);
	FILE *output = tmpfile();
	assert(output != NULL);
	assert(toy_factory_garden_topology_print(NULL, output) == -EINVAL);
	assert(ftell(output) == 0);
	assert(fclose(output) == 0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_SHRUB, 4U) ==
	       0);
	unchanged_output(&world, true);
	const struct picosystem_garden_world seedling = world;
	world.node_count = PICOSYSTEM_GARDEN_MAX_NODES + 1U;
	unchanged_output(&world, false);
	world = seedling;
	world.plant_count = PICOSYSTEM_GARDEN_MAX_PLANTS + 1U;
	unchanged_output(&world, false);
	world = seedling;
	world.nodes[1].parent_index = 1U;
	unchanged_output(&world, false);
	world = seedling;
	world.nodes[1].parent_index = PICOSYSTEM_GARDEN_NODE_NONE;
	--world.nodes[0].child_count;
	unchanged_output(&world, false);
	world = seedling;
	world.nodes[1].plant_index = world.plant_count;
	unchanged_output(&world, false);
	world = seedling;
	++world.nodes[0].child_count;
	unchanged_output(&world, false);
	world = seedling;
	world.nodes[1].kind = PICOSYSTEM_GARDEN_NODE_KIND_COUNT;
	unchanged_output(&world, false);
	world = seedling;
	world.nodes[1].flags = 128U;
	unchanged_output(&world, false);
	world = seedling;
	++world.plants[0].node_count;
	unchanged_output(&world, false);
	world = seedling;
	world.plants[0].base_node_index = 1U;
	unchanged_output(&world, false);
	world = seedling;
	world.plants[0].last_shoot_tip_index = world.node_count;
	unchanged_output(&world, false);
	world = seedling;
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 20U) ==
	       0);
	const struct picosystem_garden_world pair = world;
	world.nodes[5].parent_index = 0U;
	unchanged_output(&world, false);
	world = pair;
	world.plants[0].last_root_tip_index = world.plants[1].base_node_index;
	unchanged_output(&world, false);
	world = seedling;
	for (uint16_t i = 0U; i < PICOSYSTEM_GARDEN_MAX_NODES; ++i) {
		world.nodes[i] = seedling.nodes[1];
		world.nodes[i].parent_index =
			i == 0U ? PICOSYSTEM_GARDEN_NODE_NONE : (uint16_t)(i - 1U);
		world.nodes[i].child_count = (i + 1U < PICOSYSTEM_GARDEN_MAX_NODES) ? 1U : 0U;
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
		world.leaf_condition[i] = 0U;
#endif
	}
	world.node_count = PICOSYSTEM_GARDEN_MAX_NODES;
	world.plants[0].node_count = PICOSYSTEM_GARDEN_MAX_NODES;
	unchanged_output(&world, true);
	output = fopen("/dev/full", "w");
	assert(output != NULL);
	assert(setvbuf(output, NULL, _IONBF, 0) == 0);
	const struct picosystem_garden_world before = world;
	assert(toy_factory_garden_topology_print(&world, output) == -EIO);
	assert(memcmp(&world, &before, sizeof(world)) == 0);
	(void)fclose(output);
	puts("Read-only topology bounds, link/count checks and I/O failure tests passed");
	return 0;
}
