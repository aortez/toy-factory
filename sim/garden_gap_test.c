/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_gap.h"
#include "garden_agent.h"

static void setup(struct picosystem_garden_world *world)
{
	assert(picosystem_garden_world_reset(world, 123U) == 0);
	for (uint8_t i = 0U; i < 3U; ++i) {
		assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_FLOWER,
							  (uint8_t)(4U + i * 9U)) == 0);
		world->plants[i].age_ecology_ticks = 256U;
		world->plants[i].last_shoot_tip_index = (uint16_t)(i * 4U + 1U);
		world->plants[i].last_root_tip_index = (uint16_t)(i * 4U + 3U);
		world->plants[i].agent_memory.hidden[0] = (int8_t)i;
		world->leaf_condition[i * 4U + 1U] = (uint8_t)(100U + i);
	}
	world->auto_gardener_enabled = false;
	world->seeds[0] = (struct picosystem_garden_seed){
		.parent_lineage_id = 1U,
		.generation = 1U,
		.column = 4U,
		.age_ecology_ticks = 10U,
	};
	world->seed_count = 1U;
	world->seed_creation_count = 1U;
	assert(picosystem_garden_world_water(world, 4U, 99U) == 0);
}

static void test_remap(void)
{
	for (uint8_t target = 0U; target < 3U; ++target) {
		struct picosystem_garden_world world;
		setup(&world);
		const struct picosystem_garden_world before = world;
		struct picosystem_garden_world expected = before;
		const uint32_t identity = world.plants[target].lineage_id;
		assert(picosystem_garden_world_experimental_clear(&world, identity) == 0);
		for (uint8_t i = target; i < 2U; ++i) {
			expected.plants[i] = before.plants[i + 1U];
			expected.plants[i].base_node_index =
				(uint16_t)(expected.plants[i].base_node_index - 4U);
			expected.plants[i].last_shoot_tip_index =
				(uint16_t)(expected.plants[i].last_shoot_tip_index - 4U);
			expected.plants[i].last_root_tip_index =
				(uint16_t)(expected.plants[i].last_root_tip_index - 4U);
		}
		memset(&expected.plants[2], 0, sizeof(expected.plants[2]));
		for (uint16_t i = (uint16_t)(target * 4U); i < 8U; ++i) {
			expected.nodes[i] = before.nodes[i + 4U];
			--expected.nodes[i].plant_index;
			if (expected.nodes[i].parent_index != PICOSYSTEM_GARDEN_NODE_NONE) {
				expected.nodes[i].parent_index =
					(uint16_t)(expected.nodes[i].parent_index - 4U);
			}
			expected.leaf_condition[i] = before.leaf_condition[i + 4U];
		}
		memset(&expected.nodes[8], 0, 4U * sizeof(expected.nodes[0]));
		memset(&expected.leaf_condition[8], 0, 4U);
		expected.node_count = 8U;
		expected.plant_count = 2U;
		/* Only the derived light field may change in addition to explicit compaction. */
		memcpy(expected.light, world.light, sizeof(world.light));
		assert(memcmp(&world, &expected, sizeof(world)) == 0);
		assert(picosystem_garden_world_experimental_clear(&world, identity) == -ENOENT);
		assert(memcmp(&world, &expected, sizeof(world)) == 0);
		assert(picosystem_garden_world_step_with_policy(
			       &world, picosystem_garden_agent_baseline_policy()) == 0);
	}
}

static void test_selection_and_failures(void)
{
	struct picosystem_garden_world world;
	setup(&world);
	struct toy_factory_garden_gap result = {0};
	const uint32_t before_hash = picosystem_garden_world_hash(&world);
	const uint16_t exported_energy = world.plants[0].stored_energy;
	const uint16_t exported_water = world.plants[0].stored_water;
	assert(toy_factory_garden_gap_apply(&world, &result) == 0);
	assert(result.lineage_id == 1U && result.nodes == 4U && result.column == 4U);
	assert(!result.named);
	assert(result.before_hash == before_hash);
	assert(result.after_hash == picosystem_garden_world_hash(&world));
	assert(result.energy == exported_energy && result.water == exported_water);
	assert(world.death_count == 0U && world.reclaimed_plant_count == 0U);

	setup(&world);
	world.plants[0].age_ecology_ticks = 255U;
	assert(toy_factory_garden_gap_apply(&world, &result) == 0);
	assert(result.lineage_id == 2U);
	setup(&world);
	/* A valid extra root makes plant 3 the largest, with no lineage/RNG changes. */
	world.nodes[12] = world.nodes[11];
	world.nodes[12].parent_index = 11U;
	world.nodes[12].flags = 0U;
	world.nodes[11].child_count = 1U;
	++world.plants[2].node_count;
	++world.node_count;
	assert(toy_factory_garden_gap_apply(&world, &result) == 0);
	assert(result.lineage_id == 3U && result.nodes == 5U);

	for (int failure = 0; failure < 5; ++failure) {
		setup(&world);
		if (failure == 0) {
			for (uint8_t i = 0U; i < world.plant_count; ++i) {
				world.plants[i].age_ecology_ticks = 255U;
			}
		} else if (failure == 1) {
			++world.logic_tick_count;
		} else if (failure == 2) {
			world.node_count = PICOSYSTEM_GARDEN_MAX_NODES + 1U;
		} else if (failure == 3) {
			++world.plants[0].node_count;
		} else {
			world.random_state = 0U;
		}
		const struct picosystem_garden_world before = world;
		const struct toy_factory_garden_gap old_result = result;
		assert(toy_factory_garden_gap_apply(&world, &result) < 0);
		assert(memcmp(&world, &before, sizeof(world)) == 0);
		assert(memcmp(&result, &old_result, sizeof(result)) == 0);
	}
	assert(toy_factory_garden_gap_apply(NULL, &result) == -EINVAL);
	assert(picosystem_garden_world_experimental_clear(NULL, 1U) == -EINVAL);
	setup(&world);
	const struct picosystem_garden_world before = world;
	assert(toy_factory_garden_gap_apply(&world, NULL) == -EINVAL);
	assert(picosystem_garden_world_experimental_clear(&world, 0U) == -EINVAL);
	assert(memcmp(&world, &before, sizeof(world)) == 0);
	world.plants[0].flags = PICOSYSTEM_GARDEN_PLANT_DEAD;
	world.plants[0].stress = PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD;
	const struct picosystem_garden_world dead = world;
	assert(picosystem_garden_world_experimental_clear(&world, 1U) == -EINVAL);
	assert(memcmp(&world, &dead, sizeof(world)) == 0);
	world = before;
	for (uint32_t identity = 1U; identity <= 3U; ++identity) {
		assert(picosystem_garden_world_experimental_clear(&world, identity) == 0);
	}
	assert(world.plant_count == 0U && world.node_count == 0U);
	for (size_t i = 0U; i < sizeof(world.light); ++i) {
		assert(world.light[i] == UINT8_MAX);
	}
	assert(picosystem_garden_world_step_with_policy(
		       &world, picosystem_garden_agent_baseline_policy()) == 0);
}

static void test_named_selection_and_failures(void)
{
	for (uint32_t identity = 1U; identity <= 3U; ++identity) {
		struct picosystem_garden_world world;
		setup(&world);
		const struct picosystem_garden_world before = world;
		struct picosystem_garden_world expected = world;
		struct toy_factory_garden_gap result = {0};
		assert(picosystem_garden_world_experimental_clear(&expected, identity) == 0);
		assert(toy_factory_garden_gap_apply_named(&world, identity, &result) == 0);
		assert(result.named && result.lineage_id == identity && result.nodes == 4U);
		assert(result.before_hash == picosystem_garden_world_hash(&before));
		assert(result.after_hash == picosystem_garden_world_hash(&expected));
		assert(memcmp(&world, &expected, sizeof(world)) == 0);
		assert(toy_factory_garden_gap_apply_named(&world, identity, &result) == -ENOENT);
		assert(memcmp(&world, &expected, sizeof(world)) == 0);
	}
	for (int failure = 0; failure < 9; ++failure) {
		struct picosystem_garden_world world;
		setup(&world);
		uint32_t identity = 2U;
		if (failure == 0) {
			identity = 0U;
		} else if (failure == 1) {
			identity = UINT32_MAX;
		} else if (failure == 2) {
			world.plants[1].age_ecology_ticks = 255U;
		} else if (failure == 3) {
			world.plants[1].flags |= PICOSYSTEM_GARDEN_PLANT_DEAD;
		} else if (failure == 4) {
			++world.logic_tick_count;
		} else if (failure == 5) {
			world.node_count = PICOSYSTEM_GARDEN_MAX_NODES + 1U;
		} else if (failure == 6) {
			++world.plants[1].node_count;
		} else if (failure == 7) {
			world.random_state = 0U;
		} else {
			world.plant_count = PICOSYSTEM_GARDEN_MAX_PLANTS + 1U;
		}
		const struct picosystem_garden_world before = world;
		struct toy_factory_garden_gap result = {.lineage_id = 42U, .named = true};
		const struct toy_factory_garden_gap old_result = result;
		assert(toy_factory_garden_gap_apply_named(&world, identity, &result) < 0);
		assert(memcmp(&world, &before, sizeof(world)) == 0);
		assert(memcmp(&result, &old_result, sizeof(result)) == 0);
	}
	struct picosystem_garden_world world;
	setup(&world);
	const struct picosystem_garden_world before = world;
	struct toy_factory_garden_gap result = {0};
	assert(toy_factory_garden_gap_apply_named(NULL, 1U, &result) == -EINVAL);
	assert(toy_factory_garden_gap_apply_named(&world, 1U, NULL) == -EINVAL);
	assert(memcmp(&world, &before, sizeof(world)) == 0);
	assert(toy_factory_garden_gap_print(NULL) == -EINVAL);
}

int main(void)
{
	test_remap();
	test_selection_and_failures();
	test_named_selection_and_failures();
	puts("Gap selection/export tests passed");
	return 0;
}
