/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_disturbance.h"

static void test_death(void)
{
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	world.auto_gardener_enabled = false;
	for (uint8_t i = 0U; i < 3U; ++i) {
		assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER,
							  (uint8_t)(4U + i * 9U)) == 0);
	}
	world.plants[1].flags |= PICOSYSTEM_GARDEN_PLANT_ENERGY_SHORTAGE;
	world.seeds[0] = (struct picosystem_garden_seed){
		.parent_lineage_id = 2U, .generation = 1U, .column = 13U};
	world.seed_count = 1U;
	const struct picosystem_garden_world before = world;
	assert(picosystem_garden_world_experimental_kill_patch(&world, 12U, 14U) == 0);
	assert(world.plants[1].flags == PICOSYSTEM_GARDEN_PLANT_DEAD);
	assert(world.plants[1].stored_energy == 0U && world.plants[1].stored_water == 0U);
	assert(world.plants[1].stress == PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD);
	assert(world.node_count == before.node_count && world.plant_count == before.plant_count);
	assert(world.death_count == 1U && world.reclaimed_plant_count == 0U);
	assert(memcmp(&world.plants[0], &before.plants[0], sizeof(world.plants[0])) == 0);
	assert(memcmp(&world.plants[2], &before.plants[2], sizeof(world.plants[2])) == 0);
	assert(memcmp(world.seeds, before.seeds, sizeof(world.seeds)) == 0);
	assert(memcmp(world.moisture, before.moisture, sizeof(world.moisture)) == 0);
	assert(world.random_state == before.random_state);
	assert(memcmp(world.leaf_condition, before.leaf_condition, sizeof(world.leaf_condition)) ==
	       0);
	for (uint16_t i = 4U; i < 8U; ++i) {
		assert(world.nodes[i].growth_progress > 0U);
		assert(!(world.nodes[i].flags & PICOSYSTEM_GARDEN_NODE_TIP));
	}
	struct picosystem_garden_seed_sites sites;
	assert(picosystem_garden_world_seed_sites(&world, &sites) == 0);
	const struct picosystem_garden_world dead = world;
	assert(picosystem_garden_world_experimental_kill_patch(&world, 12U, 14U) == 0);
	assert(memcmp(&world, &dead, sizeof(world)) == 0);
	assert(picosystem_garden_world_experimental_kill_patch(&world, 0U, 1U) == 0);
	assert(memcmp(&world, &dead, sizeof(world)) == 0);
	for (uint32_t i = 0U; i < 1000U && world.reclaimed_plant_count == 0U; ++i) {
		assert(picosystem_garden_world_step_with_policy(
			       &world, picosystem_garden_agent_baseline_policy()) == 0);
	}
	assert(world.reclaimed_plant_count >= 1U);
	for (uint8_t i = 0U; i < world.plant_count; ++i) {
		assert(world.plants[i].lineage_id != 2U);
	}
	assert(picosystem_garden_world_seed_sites(&world, &sites) == 0);
	for (int failure = 0; failure < 4; ++failure) {
		world = before;
		if (failure == 0) {
			world.random_state = 0U;
		} else if (failure == 1) {
			world.node_count = PICOSYSTEM_GARDEN_MAX_NODES + 1U;
		}
		const struct picosystem_garden_world invalid = world;
		assert(picosystem_garden_world_experimental_kill_patch(
			       &world, failure == 2 ? 15U : 12U, failure == 3 ? 28U : 14U) ==
		       -EINVAL);
		assert(memcmp(&world, &invalid, sizeof(world)) == 0);
	}
	assert(picosystem_garden_world_experimental_kill_patch(NULL, 0U, 27U) == -EINVAL);
}

static void test_schedule(void)
{
	bool coverage[28] = {false};
	for (uint32_t seed = 1U; seed <= 1000U; ++seed) {
		uint32_t previous = 0U;
		for (uint32_t index = 0U; index < TOY_FACTORY_GARDEN_DISTURBANCE_MAX_EVENTS;
		     ++index) {
			struct toy_factory_garden_disturbance_event event;
			const int err = toy_factory_garden_disturbance_plan(seed, index, &event);
			if (err == -ENOENT) {
				break;
			}
			assert(err == 0 && event.tick <= TOY_FACTORY_GARDEN_DISTURBANCE_MAX_TICKS &&
			       event.tick % 15U == 0U);
			assert(index != 0U || event.tick == 61440U);
			assert(index == 0U || (event.tick - previous >= 15360U &&
					       event.tick - previous <= 30720U));
			assert(event.first_column <= event.last_column && event.last_column < 28U);
			assert(event.last_column - event.first_column <= 2);
			for (uint8_t column = event.first_column; column <= event.last_column;
			     ++column) {
				coverage[column] = true;
			}
			previous = event.tick;
		}
	}
	for (uint8_t column = 0U; column < 28U; ++column) {
		assert(coverage[column]);
	}
	struct toy_factory_garden_disturbance_event event = {0};
	const struct toy_factory_garden_disturbance_event empty = event;
	assert(toy_factory_garden_disturbance_plan(0U, 0U, &event) == -EINVAL);
	assert(toy_factory_garden_disturbance_plan(1U, UINT32_MAX, &event) == -ENOENT);
	assert(memcmp(&event, &empty, sizeof(event)) == 0);
	assert(toy_factory_garden_disturbance_plan(1U, 0U, &event) == 0);
	assert(event.tick == 61440U && event.first_column == 17U && event.last_column == 19U);
	struct toy_factory_garden_disturbance_event second;
	assert(toy_factory_garden_disturbance_plan(1U, 1U, &second) == 0);
	assert(second.tick == 80655U && second.first_column == 14U && second.last_column == 16U);
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, 4U) == 0);
	const struct picosystem_garden_world before = world;
	const struct toy_factory_garden_disturbance_event planned = event;
	assert(toy_factory_garden_disturbance_apply(&world, &event) == -EINVAL);
	assert(memcmp(&world, &before, sizeof(world)) == 0);
	assert(memcmp(&event, &planned, sizeof(event)) == 0);
	world.logic_tick_count = event.tick;
	world.ecology_tick_count = event.tick / 15U;
	assert(toy_factory_garden_disturbance_apply(&world, &event) == 0);
	assert(event.killed_count == 0U && event.before_hash == event.after_hash);
	event.killed_count = PICOSYSTEM_GARDEN_MAX_PLANTS + 1U;
	assert(toy_factory_garden_disturbance_print(&event) == -EINVAL);
}

int main(void)
{
	test_death();
	test_schedule();
	puts("Patch mortality/schedule tests passed");
	return 0;
}
