/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_founder_exit.h"
#include "garden_agent.h"

static struct picosystem_garden_world fixture(void)
{
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	world.auto_gardener_enabled = false;
	for (uint8_t i = 0U; i < 3U; ++i) {
		assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER,
							  (uint8_t)(3U + i * 10U)) == 0);
	}
	world.plants[1].parent_lineage_id = 1U;
	world.plants[1].generation = 1U;
	world.maximum_generation = 1U;
	world.seeds[0] = (struct picosystem_garden_seed){
		.parent_lineage_id = 1U, .generation = 1U, .column = 8U};
	world.seed_count = 1U;
	return world;
}

static void selection_and_preservation(void)
{
	struct picosystem_garden_world world = fixture();
	const struct picosystem_garden_world before = world;
	struct picosystem_garden_world expected = world;
	assert(picosystem_garden_world_experimental_kill_patch(&expected, 3U, 3U) == 0);
	assert(picosystem_garden_world_experimental_kill_patch(&expected, 23U, 23U) == 0);
	struct toy_factory_garden_founder_exit result;
	assert(toy_factory_garden_founder_exit_apply(&world, &result) == 0);
	assert(memcmp(&world, &expected, sizeof(world)) == 0);
	assert(result.count == 2U && result.killed_ids[0] == 1U && result.killed_ids[1] == 3U);
	assert(result.energy == 256U && result.water == 64U && result.nodes == 8U);
	assert(result.before_hash == picosystem_garden_world_hash(&before));
	assert(result.after_hash == picosystem_garden_world_hash(&world));
	assert(memcmp(&world.plants[1], &before.plants[1], sizeof(world.plants[1])) == 0);
	assert(memcmp(world.seeds, before.seeds, sizeof(world.seeds)) == 0);
	assert(memcmp(world.moisture, before.moisture, sizeof(world.moisture)) == 0);
	assert(world.random_state == before.random_state &&
	       world.weather_seed == before.weather_seed);
	assert(world.plant_count == before.plant_count && world.node_count == before.node_count);
	assert(world.death_count == 2U && world.reclaimed_plant_count == 0U);
	for (uint8_t i = 0U; i < world.plant_count; ++i) {
		assert(world.plants[i].random_state == before.plants[i].random_state);
	}
	struct picosystem_garden_seed_sites sites;
	assert(picosystem_garden_world_seed_sites(&world, &sites) == 0);
	assert(sites.blockers[3] & PICOSYSTEM_GARDEN_SEED_BLOCKED_SPACING);
	const struct picosystem_garden_world dead = world;
	assert(toy_factory_garden_founder_exit_apply(&world, &result) == 0);
	assert(result.count == 0U && result.before_hash == result.after_hash);
	assert(memcmp(&world, &dead, sizeof(world)) == 0);
	for (unsigned int i = 0U; i < 2000U && world.reclaimed_plant_count < 2U; ++i) {
		assert(picosystem_garden_world_step_with_policy(
			       &world, picosystem_garden_agent_baseline_policy()) == 0);
	}
	assert(world.reclaimed_plant_count >= 2U);
	/* Parent-zero identity, not a persistent array index, controls selection. */
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 3U) ==
	       0);
	while (world.logic_tick_count % 15U != 0U) {
		assert(picosystem_garden_world_step_with_policy(
			       &world, picosystem_garden_agent_baseline_policy()) == 0);
	}
	const uint32_t added = world.lineage_sequence;
	assert(toy_factory_garden_founder_exit_apply(&world, &result) == 0);
	assert(result.count == 1U && result.killed_ids[0] == added);
}

static void invalid_is_atomic(void)
{
	for (unsigned int failure = 0U; failure < 5U; ++failure) {
		struct picosystem_garden_world world = fixture();
		if (failure == 0U) {
			world.auto_gardener_enabled = true;
		} else if (failure == 1U) {
			world.logic_tick_count = 1U;
		} else if (failure == 2U) {
			world.random_state = 0U;
		} else if (failure == 3U) {
			world.plant_count = PICOSYSTEM_GARDEN_MAX_PLANTS + 1U;
		} else {
			world.plants[1].base_column = world.plants[2].base_column;
		}
		const struct picosystem_garden_world before = world;
		struct toy_factory_garden_founder_exit result = {.tick = 7U};
		const struct toy_factory_garden_founder_exit old = result;
		assert(toy_factory_garden_founder_exit_apply(&world, &result) != 0);
		assert(memcmp(&world, &before, sizeof(world)) == 0);
		assert(memcmp(&result, &old, sizeof(result)) == 0);
	}
	struct picosystem_garden_world world = fixture();
	struct toy_factory_garden_founder_exit result;
	assert(toy_factory_garden_founder_exit_apply(NULL, &result) == -EINVAL);
	assert(toy_factory_garden_founder_exit_apply(&world, NULL) == -EINVAL);
	assert(picosystem_garden_world_reset(&world, 4U) == 0);
	world.auto_gardener_enabled = false;
	assert(toy_factory_garden_founder_exit_apply(&world, &result) == 0 && result.count == 0U);
}

int main(void)
{
	selection_and_preservation();
	invalid_is_atomic();
	puts("Founder death, no-op, preservation, reclamation and atomicity checks passed");
	return 0;
}
