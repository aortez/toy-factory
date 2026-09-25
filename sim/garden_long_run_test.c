/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "garden_agent.h"
#include "garden_death_audit.h"
#include "garden_evaluation.h"

static int wait_decide(const struct picosystem_garden_agent_observation *observation,
		       const struct picosystem_garden_agent_memory *memory,
		       struct picosystem_garden_agent_decision *decision, const void *context)
{
	(void)context;
	*decision = (struct picosystem_garden_agent_decision){
		.proposal = {.tip_index = observation->tip_index,
			     .action = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT},
		.next_memory = *memory,
	};
	return 0;
}

static const struct picosystem_garden_agent_policy wait_policy = {.decide = wait_decide};

static void setup(struct picosystem_garden_world *world, uint8_t plants)
{
	assert(picosystem_garden_world_reset(world, 123U) == 0);
	for (uint8_t index = 0U; index < plants; ++index) {
		assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_FLOWER,
							  (uint8_t)(index * 3U)) == 0);
	}
	memset(world->moisture, 0, sizeof(world->moisture));
	world->logic_tick_count = 59U;
	world->ecology_tick_count = 3U;
}

static void identical_step(struct picosystem_garden_world *world,
			   struct picosystem_garden_death_audit *audit)
{
	struct picosystem_garden_world control = *world;
	assert(picosystem_garden_world_step_with_policy(&control, &wait_policy) == 0);
	assert(picosystem_garden_world_step_death_audit(world, &wait_policy, audit) == 0);
	assert(memcmp(world, &control, sizeof(control)) == 0);
	assert(picosystem_garden_world_hash(world) == picosystem_garden_world_hash(&control));
}

static void test_age(void)
{
	struct picosystem_garden_world world;
	setup(&world, 1U);
	world.plants[0].age_ecology_ticks = UINT16_MAX - 1U;
	for (uint32_t expected = UINT16_MAX; expected <= UINT16_MAX + 2U; ++expected) {
		world.logic_tick_count = 59U;
		world.ecology_tick_count = 3U;
		world.plants[0].stored_energy = 100U;
		world.plants[0].stored_water = 100U;
		assert(picosystem_garden_world_step_with_policy(&world, &wait_policy) == 0);
		assert(world.plants[0].age_ecology_ticks == expected);
		struct picosystem_garden_agent_observation observation;
		assert(picosystem_garden_agent_observe_tip(&world, 0U, 1U, 0U, &observation) == 0);
		assert(observation.age_ecology_ticks == UINT16_MAX);
		assert(picosystem_garden_agent_observation_is_valid(&observation));
	}
	world.plants[0].age_ecology_ticks = UINT32_MAX - 1U;
	for (uint32_t tick = 0U; tick < 30U; ++tick) {
		assert(picosystem_garden_world_step_with_policy(&world, &wait_policy) == 0);
	}
	assert(world.plants[0].age_ecology_ticks == UINT32_MAX);
	world.plants[0].age_ecology_ticks = 1U;
	const uint32_t young_hash = picosystem_garden_world_hash(&world);
	world.plants[0].age_ecology_ticks += UINT32_C(65536);
	const uint32_t old_hash = picosystem_garden_world_hash(&world);
	assert(young_hash != old_hash);
	world.plants[0].age_ecology_ticks += UINT32_C(65536);
	assert(picosystem_garden_world_hash(&world) != old_hash);
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 0U) ==
	       0);
	assert(world.plants[0].age_ecology_ticks == 0U);
}

static void test_death_resources(void)
{
	for (uint8_t shortages = 1U; shortages <= 3U; ++shortages) {
		struct picosystem_garden_world world;
		setup(&world, 1U);
		world.plants[0].stress = 7U;
		world.plants[0].stored_energy = (shortages & 1U) != 0U ? 0U : 256U;
		world.plants[0].stored_water = (shortages & 2U) != 0U ? 0U : 510U;
		if ((shortages & 2U) == 0U) {
			memset(world.moisture, 10, sizeof(world.moisture));
		}
		for (uint16_t index = 0U; index < world.node_count; ++index) {
			world.nodes[index].flags &= (uint8_t)~PICOSYSTEM_GARDEN_NODE_LEAF;
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
			world.leaf_condition[index] = 0U;
#endif
			if (((shortages & 1U) == 0U) &&
			    (world.nodes[index].kind == PICOSYSTEM_GARDEN_NODE_STEM)) {
				world.nodes[index].flags |= PICOSYSTEM_GARDEN_NODE_LEAF;
				world.nodes[index].growth_progress = UINT8_MAX;
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
				world.leaf_condition[index] = UINT8_MAX;
#endif
			}
		}
		struct picosystem_garden_death_audit audit;
		identical_step(&world, &audit);
		assert(audit.ecology_step && audit.count == 1U);
		const struct picosystem_garden_death_event *const event = &audit.events[0];
		assert(event->lineage_id == world.plants[0].lineage_id);
		assert(event->flags == (uint8_t)(1U | ((uint32_t)shortages << 1U)));
		assert(event->stress_before == 7U);
		assert(event->energy.upkeep_due == 1U && event->water.upkeep_due == 1U);
		assert(event->energy.upkeep_paid == ((shortages & 1U) ? 0U : 1U));
		assert(event->water.upkeep_paid == ((shortages & 2U) ? 0U : 1U));
		assert(event->energy.discarded == ((shortages & 1U) ? 0U : 255U));
		assert(event->water.discarded == ((shortages & 2U) ? 0U : 511U));
		assert(event->energy.before + event->energy.income ==
		       event->energy.overflow + event->energy.upkeep_paid +
			       event->energy.discarded);
		assert(event->water.before + event->water.income ==
		       event->water.overflow + event->water.upkeep_paid + event->water.discarded);
		if ((shortages & 1U) == 0U) {
			assert(event->energy.income > 0U && event->energy.overflow > 0U);
		}
		if ((shortages & 2U) == 0U) {
#if defined(TOY_FACTORY_GARDEN_WATER_HEADROOM)
			assert(event->water.income == 2U && event->water.overflow == 0U);
#else
			assert(event->water.income == 6U && event->water.overflow == 4U);
#endif
		}
		assert(world.plants[0].stored_energy == 0U && world.plants[0].stored_water == 0U);
		assert(world.plants[0].last_energy_income == 0U &&
		       world.plants[0].last_water_income == 0U);
		const uint32_t dead_age = world.plants[0].age_ecology_ticks;
		for (uint8_t tick = 0U; tick < 15U; ++tick) {
			identical_step(&world, &audit);
			assert(audit.count == 0U);
		}
		assert(world.plants[0].age_ecology_ticks == dead_age);
	}
}

static void test_compaction_and_multiple_deaths(void)
{
	struct picosystem_garden_world world;
	setup(&world, 3U);
	world.plants[0].stored_energy = 0U;
	world.plants[0].stress = 7U;
	struct picosystem_garden_death_audit audit;
	identical_step(&world, &audit);
	assert(audit.count == 1U);
	for (uint16_t index = 0U; index < world.node_count; ++index) {
		if (world.nodes[index].plant_index == 0U) {
			world.nodes[index].growth_progress = 0U;
		}
	}
	const uint32_t second = world.plants[1].lineage_id;
	const uint32_t third = world.plants[2].lineage_id;
	for (uint8_t index = 1U; index < world.plant_count; ++index) {
		world.plants[index].stress = 7U;
		world.plants[index].stored_energy = 0U;
		world.plants[index].stored_water = 0U;
	}
	world.logic_tick_count = 119U;
	world.ecology_tick_count = 7U;
	identical_step(&world, &audit);
	assert(world.plant_count == 2U && world.reclaimed_plant_count == 1U);
	assert(audit.count == 2U);
	assert(audit.events[0].lineage_id == second && audit.events[1].lineage_id == third);
}

static void test_unsaturated_income(void)
{
	struct picosystem_garden_world world;
	setup(&world, 1U);
	const struct picosystem_garden_node root = world.nodes[2];
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	memset(world.leaf_condition, 0, sizeof(world.leaf_condition));
#endif
	world.node_count = 101U;
	world.plants[0].node_count = world.node_count;
	world.plants[0].stress = 7U;
	world.plants[0].stored_energy = 0U;
	world.plants[0].stored_water = 0U;
	world.nodes[0].child_count = 100U;
	for (uint16_t index = 1U; index < world.node_count; ++index) {
		world.nodes[index] = root;
		world.nodes[index].parent_index = 0U;
		world.nodes[index].depth = 1U;
		world.nodes[index].child_count = 0U;
		world.nodes[index].x = (uint8_t)(PICOSYSTEM_GARDEN_ORIGIN_X_PIXELS +
						 (index % PICOSYSTEM_GARDEN_GRID_COLUMNS) * 8U);
		world.nodes[index].y = (uint8_t)(PICOSYSTEM_GARDEN_SOIL_TOP_PIXELS +
						 (index / PICOSYSTEM_GARDEN_GRID_COLUMNS) * 8U);
	}
	memset(world.moisture, 10, sizeof(world.moisture));
	struct picosystem_garden_death_audit audit;
	identical_step(&world, &audit);
	assert(audit.count == 1U);
	assert(audit.events[0].water.income == 300U);
	assert(audit.events[0].water.upkeep_paid == 1U);
	assert(audit.events[0].water.discarded == 299U);
}

static void test_empty_and_invalid(void)
{
	struct picosystem_garden_world world;
	setup(&world, 1U);
	world.plants[0].stress = 7U;
	struct picosystem_garden_death_audit audit;
	memset(&audit, 0xa5, sizeof(audit));
	identical_step(&world, &audit);
	assert(world.plants[0].stress == 6U && audit.count == 0U);
	identical_step(&world, &audit);
	const struct picosystem_garden_death_audit empty = {0};
	assert(memcmp(&audit, &empty, sizeof(audit)) == 0);
	assert(picosystem_garden_world_step_death_audit(&world, NULL, &audit) == -EINVAL);
	assert(memcmp(&audit, &empty, sizeof(audit)) == 0);
	assert(picosystem_garden_world_step_death_audit(&world, &wait_policy, NULL) == -EINVAL);
	assert(picosystem_garden_world_set_auto_gardener(&world, true) == 0);
	const struct picosystem_garden_world unchanged = world;
	assert(picosystem_garden_world_step_death_audit(&world, &wait_policy, &audit) == -EINVAL);
	assert(memcmp(&world, &unchanged, sizeof(world)) == 0);
}

int main(void)
{
	test_age();
	test_death_resources();
	test_compaction_and_multiple_deaths();
	test_unsaturated_income();
	test_empty_and_invalid();
	printf("Long-run age and death accounting passed; world=%zu plant=%zu observation=%zu "
	       "bytes\n",
	       sizeof(struct picosystem_garden_world), sizeof(struct picosystem_garden_plant),
	       sizeof(struct picosystem_garden_agent_observation));
	return 0;
}
