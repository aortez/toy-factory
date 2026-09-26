/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_seed_audit.h"
#include "garden_evaluation.h"
#include "garden_leaf_policies.h"

static void ready(struct picosystem_garden_world *world)
{
	assert(picosystem_garden_world_reset(world, 123U) == 0);
	world->auto_gardener_enabled = false;
	assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 0U) ==
	       0);
	memset(world->moisture, UINT8_MAX, sizeof(world->moisture));
	world->logic_tick_count = 14U;
	world->seed_count = PICOSYSTEM_GARDEN_MAX_SEEDS;
	for (uint8_t i = 0U; i < world->seed_count; ++i) {
		world->seeds[i] = (struct picosystem_garden_seed){
			.parent_lineage_id = 1U,
			.generation = 1U,
			.column = 14U,
			.species_id = PICOSYSTEM_GARDEN_SPECIES_FLOWER,
			.age_ecology_ticks = 7U,
		};
	}
}

static void same_step(struct picosystem_garden_world *world,
		      const struct picosystem_garden_agent_policy *policy,
		      struct picosystem_garden_seed_audit *audit)
{
	struct picosystem_garden_world plain = *world;
	assert(picosystem_garden_world_step_with_policy(&plain, policy) == 0);
	assert(picosystem_garden_world_step_seed_audit(world, policy, audit) == 0);
	assert(memcmp(world, &plain, sizeof(plain)) == 0);
}

int main(void)
{
	struct picosystem_garden_world world;
	struct picosystem_garden_agent_policy policy = *picosystem_garden_agent_adaptive_policy();
	policy.leaf_policy = toy_factory_garden_leaf_policy("selective");
	struct picosystem_garden_seed_audit audit;
	memset(&audit, 0x5a, sizeof(audit));
	const struct picosystem_garden_seed_audit sentinel = audit;
	ready(&world);
	const struct picosystem_garden_world before = world;
	assert(picosystem_garden_world_step_seed_audit(NULL, &policy, &audit) == -EINVAL);
	assert(picosystem_garden_world_step_seed_audit(&world, NULL, &audit) == -EINVAL);
	assert(picosystem_garden_world_step_seed_audit(&world, &policy, NULL) == -EINVAL);
	assert(memcmp(&audit, &sentinel, sizeof(audit)) == 0);
	assert(memcmp(&world, &before, sizeof(world)) == 0);
	world.auto_gardener_enabled = true;
	assert(picosystem_garden_world_step_seed_audit(&world, &policy, &audit) == -EINVAL);
	assert(memcmp(&audit, &sentinel, sizeof(audit)) == 0);
	world = before;
	world.seed_count = PICOSYSTEM_GARDEN_MAX_SEEDS + 1U;
	assert(picosystem_garden_world_step_seed_audit(&world, &policy, &audit) == -EINVAL);
	assert(memcmp(&audit, &sentinel, sizeof(audit)) == 0);

	ready(&world);
	world.seeds[0].age_ecology_ticks = PICOSYSTEM_GARDEN_SEED_LIFETIME_TICKS - 1U;
	world.seeds[1].age_ecology_ticks = 6U;
	same_step(&world, &policy, &audit);
	assert(audit.ecology_step && audit.count == PICOSYSTEM_GARDEN_MAX_SEEDS);
	assert(audit.attempts[0].outcome == PICOSYSTEM_GARDEN_SEED_EXPIRED);
	assert(audit.attempts[0].age == PICOSYSTEM_GARDEN_SEED_LIFETIME_TICKS &&
	       audit.attempts[0].child == 0U);
	for (uint8_t c = 0U; c < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++c) {
		assert(audit.attempts[0].sites[c] == 0U);
	}
	assert(audit.attempts[1].outcome == PICOSYSTEM_GARDEN_SEED_WAIT);
	assert(audit.attempts[1].blockers == PICOSYSTEM_GARDEN_SEED_BLOCKED_DORMANT);
	assert(audit.attempts[2].outcome == PICOSYSTEM_GARDEN_SEED_GERMINATED);
	assert(audit.attempts[2].child == 2U && audit.attempts[2].blockers == 0U);
	assert(audit.sites_before[14] == 0U);
	for (uint8_t i = 3U; i < audit.count; ++i) {
		assert(audit.attempts[i].outcome == PICOSYSTEM_GARDEN_SEED_WAIT);
		assert(audit.attempts[i].blockers == PICOSYSTEM_GARDEN_SEED_BLOCKED_SPACING);
		assert(audit.attempts[i].sites[14] == PICOSYSTEM_GARDEN_SEED_BLOCKED_SPACING);
		assert(audit.attempts[i].child == 0U);
	}
	assert(audit.stages[PICOSYSTEM_GARDEN_SEED_AFTER_CHECKS].nodes ==
	       audit.stages[PICOSYSTEM_GARDEN_SEED_BEFORE_CHECKS].nodes + 4U);
	assert(audit.stages[PICOSYSTEM_GARDEN_SEED_AFTER_CHECKS].seeds ==
	       PICOSYSTEM_GARDEN_MAX_SEEDS - 2U);

	ready(&world);
	for (uint16_t i = world.node_count; i < PICOSYSTEM_GARDEN_MAX_NODES - 4U; ++i) {
		world.nodes[i] = world.nodes[0];
		world.nodes[i].parent_index = 0U;
	}
	world.node_count = PICOSYSTEM_GARDEN_MAX_NODES - 4U;
	world.plants[0].node_count = world.node_count;
	world.seeds[1].column = 20U;
	same_step(&world, &policy, &audit);
	assert(audit.attempts[0].outcome == PICOSYSTEM_GARDEN_SEED_GERMINATED);
	assert(audit.attempts[1].outcome == PICOSYSTEM_GARDEN_SEED_WAIT);
	assert(audit.attempts[1].blockers & PICOSYSTEM_GARDEN_SEED_BLOCKED_NODE_CAPACITY);
	assert(audit.attempts[1].nodes == PICOSYSTEM_GARDEN_MAX_NODES);

	ready(&world);
	for (uint8_t i = 1U; i < PICOSYSTEM_GARDEN_DEFAULT_PLANTS; ++i) {
		assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER,
							  (uint8_t)(i * 3U)) == 0);
	}
	world.seeds[0].column = 27U;
	same_step(&world, &policy, &audit);
	assert(audit.attempts[0].blockers & PICOSYSTEM_GARDEN_SEED_BLOCKED_PLANT_CAPACITY);

	ready(&world);
	memset(world.moisture, 0, sizeof(world.moisture));
	world.logic_tick_count = 959U;
	world.ecology_tick_count = 63U;
	same_step(&world, &policy, &audit);
	assert((audit.attempts[0].blockers & 6U) == 6U);
	assert(audit.attempts[0].moisture < 12U && audit.attempts[0].light < 80U);

	assert(toy_factory_garden_evaluation_reset(&world, &toy_factory_garden_rainfed_scenarios[1],
						   0xb61837dcU) == 0);
	const struct picosystem_garden_seed_audit zero = {0};
	for (uint32_t tick = 1U; tick <= 18U * 3840U; ++tick) {
		same_step(&world, &policy, &audit);
		assert(audit.ecology_step == ((tick % 15U) == 0U));
		if (!audit.ecology_step) {
			assert(memcmp(&audit, &zero, sizeof(audit)) == 0);
		}
	}
	printf("Seed audit state/sequence/boundary checks passed; caller storage=%zu bytes\n",
	       sizeof(audit));
	return 0;
}
