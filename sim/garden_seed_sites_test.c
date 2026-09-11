/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_evaluation.h"

static void check_query(struct picosystem_garden_world *world)
{
	const struct picosystem_garden_world before = *world;
	struct picosystem_garden_seed_sites sites;
	assert(picosystem_garden_world_seed_sites(world, &sites) == 0);
	assert(memcmp(world, &before, sizeof(before)) == 0);
	for (uint8_t column = 0U; column < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++column) {
		assert((sites.blockers[column] & PICOSYSTEM_GARDEN_SEED_BLOCKED_DORMANT) == 0U);
		if (world->plant_count == 0U) {
			continue;
		}
		/* A controlled copy exercises the actual-seed API at each hypothetical site. */
		struct picosystem_garden_world copy = *world;
		copy.seed_count = 1U;
		copy.seeds[0] = (struct picosystem_garden_seed){
			.parent_lineage_id = world->plants[0].lineage_id,
			.generation = 1U,
			.column = column,
			.age_ecology_ticks = PICOSYSTEM_GARDEN_SEED_DORMANCY_TICKS,
		};
		uint8_t blockers;
		assert(picosystem_garden_world_seed_germination_blockers(&copy, 0U, &blockers) ==
		       0);
		assert(blockers == sites.blockers[column]);
		--copy.seeds[0].age_ecology_ticks;
		assert(picosystem_garden_world_seed_germination_blockers(&copy, 0U, &blockers) ==
		       0);
		assert(blockers ==
		       (sites.blockers[column] | PICOSYSTEM_GARDEN_SEED_BLOCKED_DORMANT));
	}
}

static void check_dispersal_support(struct picosystem_garden_world *world)
{
#if defined(TOY_FACTORY_GARDEN_WIDE_DISPERSAL)
	const int minimum = 3;
	const int maximum = 9;
#else
	const int minimum = 5;
	const int maximum = 7;
#endif
	for (int base = 0; base < 28; ++base) {
		for (int trait = -2; trait <= 2; ++trait) {
			world->plants[0].base_column = (uint8_t)base;
			world->plants[0].genome.dispersal = (int8_t)trait;
			uint32_t expected = 0U;
			for (int distance = minimum + trait; distance <= maximum + trait;
			     ++distance) {
				for (int direction = -1; direction <= 1; direction += 2) {
					int column = base + direction * distance;
					if ((column < 0) || (column > 27)) {
						column = base - direction * distance;
					}
					assert((column >= 0) && (column <= 27));
					expected |= UINT32_C(1) << column;
				}
			}
			const struct picosystem_garden_world before = *world;
			struct picosystem_garden_seed_sites sites;
			assert(picosystem_garden_world_seed_sites(world, &sites) == 0);
			assert(sites.dispersal_columns[0] == expected);
			assert(memcmp(world, &before, sizeof(before)) == 0);
		}
	}
}

int main(void)
{
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	check_query(&world);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 0U) ==
	       0);
	check_dispersal_support(&world);
	struct picosystem_garden_seed_sites sites;
	world.plants[0].base_column = 27U;
	world.plants[0].genome.dispersal = 2;
	world.plants[0].flags = PICOSYSTEM_GARDEN_PLANT_DEAD;
	world.plants[0].stress = PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD;
	assert(picosystem_garden_world_seed_sites(&world, &sites) == 0);
	assert(sites.dispersal_columns[0] == 0U);
	assert((sites.blockers[27] & PICOSYSTEM_GARDEN_SEED_BLOCKED_SPACING) != 0U);
	check_query(&world);

	/* Capacity boundaries use a controlled valid topology, not grown geometry. */
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 0U) ==
	       0);
	for (uint16_t count = 252U; count <= 256U; ++count) {
		for (uint16_t index = world.node_count; index < count; ++index) {
			world.nodes[index] = world.nodes[0];
			world.nodes[index].parent_index = 0U;
		}
		world.node_count = count;
		world.plants[0].node_count = count;
		assert(picosystem_garden_world_seed_sites(&world, &sites) == 0);
		for (uint8_t column = 0U; column < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++column) {
			assert(((sites.blockers[column] &
				 PICOSYSTEM_GARDEN_SEED_BLOCKED_NODE_CAPACITY) != 0U) ==
			       (count > 252U));
		}
		check_query(&world);
	}
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	for (uint8_t index = 0U; index < PICOSYSTEM_GARDEN_MAX_PLANTS; ++index) {
		assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER,
							  (uint8_t)(index * 3U)) == 0);
		assert(picosystem_garden_world_seed_sites(&world, &sites) == 0);
		assert(((sites.blockers[27] & PICOSYSTEM_GARDEN_SEED_BLOCKED_PLANT_CAPACITY) !=
			0U) == (index == 7U));
	}
	check_query(&world);

	assert(toy_factory_garden_evaluation_reset(&world, &toy_factory_garden_rainfed_scenarios[1],
						   0x6f47c12cU) == 0);
	for (uint32_t tick = 0U; tick < 12000U; ++tick) {
		if ((tick % 15U) == 0U) {
			check_query(&world);
		}
		assert(picosystem_garden_world_step(&world) == 0);
	}
	const struct picosystem_garden_seed_sites before = sites;
	assert(picosystem_garden_world_seed_sites(NULL, &sites) == -EINVAL);
	assert(picosystem_garden_world_seed_sites(&world, NULL) == -EINVAL);
	world.seed_count = PICOSYSTEM_GARDEN_MAX_SEEDS + 1U;
	assert(picosystem_garden_world_seed_sites(&world, &sites) == -EINVAL);
	assert(memcmp(&sites, &before, sizeof(sites)) == 0);
	puts("PASS: seed-site queries preserve state and reuse germination/dispersal rules");
	return 0;
}
