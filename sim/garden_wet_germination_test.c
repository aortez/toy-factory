/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_agent.h"
#include "garden_seed_audit.h"
#include "garden_wet_germination.h"

static void ready(struct picosystem_garden_world *world)
{
	assert(picosystem_garden_world_reset(world, 123U) == 0);
	assert(!world->wet_germination_enabled);
	world->auto_gardener_enabled = false;
	assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 0U) ==
	       0);
	memset(world->moisture, 20, sizeof(world->moisture));
	memset(world->light, 24, sizeof(world->light));
	world->seed_count = 1U;
	world->seeds[0] =
		(struct picosystem_garden_seed){.parent_lineage_id = 1U,
						.generation = 1U,
						.column = 14U,
						.species_id = PICOSYSTEM_GARDEN_SPECIES_SHRUB,
						.age_ecology_ticks = 8U};
}

static uint8_t blockers(const struct picosystem_garden_world *world)
{
	uint8_t result = UINT8_MAX;
	assert(picosystem_garden_world_seed_germination_blockers(world, 0U, &result) == 0);
	return result;
}

static int wait_decision(const struct picosystem_garden_agent_observation *observation,
			 const struct picosystem_garden_agent_memory *memory,
			 struct picosystem_garden_agent_decision *decision, const void *context)
{
	(void)context;
	*decision = (struct picosystem_garden_agent_decision){
		.proposal = {.tip_index = observation->tip_index,
			     .action = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT},
		.next_memory = *memory};
	return 0;
}

int main(void)
{
	struct picosystem_garden_world world;
	ready(&world);
	const struct picosystem_garden_world before = world;
	const uint32_t old_hash = picosystem_garden_world_hash(&world);
	assert(blockers(&world) == PICOSYSTEM_GARDEN_SEED_BLOCKED_LIGHT);
	assert(picosystem_garden_world_enable_wet_germination(&world) == 0);
	assert(picosystem_garden_world_hash(&world) != old_hash);
	assert(blockers(&world) == 0U);
	struct picosystem_garden_world expected = before;
	expected.wet_germination_enabled = true;
	assert(memcmp(&world, &expected, sizeof(world)) == 0);
	assert(picosystem_garden_world_enable_wet_germination(&world) == -EINVAL);
	assert(memcmp(&world, &expected, sizeof(world)) == 0);
	assert(picosystem_garden_world_enable_wet_germination(NULL) == -EINVAL);
	for (unsigned int defect = 0U; defect < 3U; ++defect) {
		world = before;
		if (defect == 0U) {
			world.auto_gardener_enabled = true;
		} else if (defect == 1U) {
			world.logic_tick_count = 1U;
		} else {
			world.seed_count = PICOSYSTEM_GARDEN_MAX_SEEDS + 1U;
		}
		const struct picosystem_garden_world invalid = world;
		assert(picosystem_garden_world_enable_wet_germination(&world) == -EINVAL);
		assert(memcmp(&world, &invalid, sizeof(world)) == 0);
	}
	for (uint16_t light = 0U; light <= UINT8_MAX; ++light) {
		world = before;
		memset(world.light, (int)light, sizeof(world.light));
		assert(blockers(&world) ==
		       (light < 80U ? PICOSYSTEM_GARDEN_SEED_BLOCKED_LIGHT : 0U));
		assert(picosystem_garden_world_enable_wet_germination(&world) == 0);
		assert(blockers(&world) == 0U);
	}
	for (uint8_t wet = 0U; wet < 2U; ++wet) {
		world = before;
		if (wet != 0U) {
			assert(picosystem_garden_world_enable_wet_germination(&world) == 0);
		}
		const uint8_t light_mask = wet ? 0U : PICOSYSTEM_GARDEN_SEED_BLOCKED_LIGHT;
		world.moisture[14] = 11U;
		assert(blockers(&world) == (light_mask | PICOSYSTEM_GARDEN_SEED_BLOCKED_MOISTURE));
		world.moisture[14] = 12U;
		assert(blockers(&world) == light_mask);
		world.seeds[0].age_ecology_ticks = 7U;
		assert(blockers(&world) == (light_mask | PICOSYSTEM_GARDEN_SEED_BLOCKED_DORMANT));
		world.seeds[0].age_ecology_ticks = 8U;
		world.seeds[0].column = 2U;
		assert(blockers(&world) == (light_mask | PICOSYSTEM_GARDEN_SEED_BLOCKED_SPACING));
		world.seeds[0].column = 3U;
		assert(blockers(&world) == light_mask);
		for (uint8_t i = 1U; i < PICOSYSTEM_GARDEN_DEFAULT_PLANTS; ++i) {
			assert(picosystem_garden_world_plant_seed(&world,
								  PICOSYSTEM_GARDEN_SPECIES_FLOWER,
								  (uint8_t)(i * 3U)) == 0);
		}
		world.seeds[0].column = 27U;
		assert(blockers(&world) ==
		       (light_mask | PICOSYSTEM_GARDEN_SEED_BLOCKED_PLANT_CAPACITY));
		world = before;
		world.wet_germination_enabled = wet != 0U;
		for (uint16_t i = world.node_count; i < PICOSYSTEM_GARDEN_MAX_NODES - 3U; ++i) {
			world.nodes[i] = world.nodes[0];
			world.nodes[i].parent_index = 0U;
		}
		world.node_count = PICOSYSTEM_GARDEN_MAX_NODES - 4U;
		world.plants[0].node_count = world.node_count;
		assert(blockers(&world) == light_mask);
		++world.node_count;
		++world.plants[0].node_count;
		assert(blockers(&world) ==
		       (light_mask | PICOSYSTEM_GARDEN_SEED_BLOCKED_NODE_CAPACITY));
	}
	const struct picosystem_garden_agent_policy policy = {
		.decide = wait_decision,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS};
	for (uint8_t wet = 0U; wet < 2U; ++wet) {
		ready(&world);
		if (wet) {
			assert(picosystem_garden_world_enable_wet_germination(&world) == 0);
		}
		memset(world.moisture, UINT8_MAX, sizeof(world.moisture));
		world.logic_tick_count = 959U;
		world.ecology_tick_count = 63U;
		world.seed_count = 3U;
		world.seeds[1] = world.seeds[0];
		world.seeds[1].age_ecology_ticks = PICOSYSTEM_GARDEN_SEED_LIFETIME_TICKS - 1U;
		world.seeds[2] = world.seeds[0];
		struct picosystem_garden_world plain = world;
		struct picosystem_garden_seed_audit audit;
		assert(picosystem_garden_world_step_with_policy(&plain, &policy) == 0);
		assert(picosystem_garden_world_step_seed_audit(&world, &policy, &audit) == 0);
		assert(memcmp(&world, &plain, sizeof(world)) == 0);
		assert(audit.attempts[0].light == 24U);
		assert(audit.attempts[1].outcome == PICOSYSTEM_GARDEN_SEED_EXPIRED);
		assert(world.germination_count == wet);
		if (wet) {
			assert(audit.attempts[0].outcome == PICOSYSTEM_GARDEN_SEED_GERMINATED);
			assert(audit.attempts[2].blockers ==
			       PICOSYSTEM_GARDEN_SEED_BLOCKED_SPACING);
			assert(audit.attempts[2].moisture + 12U == audit.attempts[0].moisture);
			assert(world.plants[1].stored_energy == 64U &&
			       world.plants[1].stored_water == 24U);
			assert(world.plants[1].node_count == 4U);
		} else {
			assert(audit.attempts[0].blockers == PICOSYSTEM_GARDEN_SEED_BLOCKED_LIGHT);
		}
	}
	ready(&world);
	printf("Wet germination: isolated flag/hash, gates, dark birth, reserves, expiry and "
	       "observer neutrality passed\n");
	return 0;
}
