/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_evaluation.h"
#include "garden_reproduction_audit.h"

static int wait_decide(const struct picosystem_garden_agent_observation *observation,
		       const struct picosystem_garden_agent_memory *memory,
		       struct picosystem_garden_agent_decision *decision, const void *context)
{
	(void)context;
	*decision = (struct picosystem_garden_agent_decision){
		.next_memory = *memory,
		.proposal = {.tip_index = observation->tip_index,
			     .action = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT},
	};
	return 0;
}

static const struct picosystem_garden_agent_policy wait_policy = {
	.decide = wait_decide,
	.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS,
};

static void ready(struct picosystem_garden_world *world, uint8_t plants)
{
	assert(picosystem_garden_world_reset(world, 123U) == 0);
	world->auto_gardener_enabled = false;
	for (uint8_t i = 0U; i < plants; ++i) {
		assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_FLOWER,
							  (uint8_t)(i * 10U)) == 0);
		world->plants[i].stored_energy = 145U;
		world->plants[i].stored_water = 65U;
		world->plants[i].genome.reserve_strategy = 0;
		world->plants[i].reproduction_cooldown = 0U;
	}
	for (uint16_t i = 0U; i < world->node_count; ++i) {
		world->nodes[i].kind = PICOSYSTEM_GARDEN_NODE_STEM;
		world->nodes[i].flags = (i % 4U) == 0U ? PICOSYSTEM_GARDEN_NODE_FLOWER : 0U;
		world->nodes[i].growth_progress = UINT8_MAX;
	}
	world->logic_tick_count = 899U;
	world->ecology_tick_count = 59U;
}

static void bank(struct picosystem_garden_world *world, uint8_t count)
{
	world->seed_count = count;
	for (uint8_t i = 0U; i < count; ++i) {
		world->seeds[i] = (struct picosystem_garden_seed){
			.parent_lineage_id = 1U,
			.generation = 1U,
			.column = 14U,
			.species_id = PICOSYSTEM_GARDEN_SPECIES_FLOWER,
		};
	}
}

static void same_step(struct picosystem_garden_world *world,
		      const struct picosystem_garden_agent_policy *policy,
		      struct picosystem_garden_reproduction_audit *audit)
{
	struct picosystem_garden_world plain = *world;
	assert(picosystem_garden_world_step_with_policy(&plain, policy) == 0);
	assert(picosystem_garden_world_step_reproduction_audit(world, policy, audit) == 0);
	assert(memcmp(world, &plain, sizeof(plain)) == 0);
	assert(audit->ecology_step == ((world->logic_tick_count % 15U) == 0U));
	assert(audit->count == (audit->ecology_step ? world->plant_count : 0U));
	for (uint8_t i = 0U; i < audit->count; ++i) {
		assert(audit->visits[i].produced == (audit->visits[i].blockers == 0U));
		assert(audit->visits[i].lineage == world->plants[i].lineage_id);
	}
}

int main(void)
{
	struct picosystem_garden_world world;
	struct picosystem_garden_reproduction_audit audit;
	memset(&audit, 0x5a, sizeof(audit));
	const struct picosystem_garden_reproduction_audit sentinel = audit;
	ready(&world, 1U);
	const struct picosystem_garden_world before = world;
	assert(picosystem_garden_world_step_reproduction_audit(NULL, &wait_policy, &audit) ==
	       -EINVAL);
	assert(picosystem_garden_world_step_reproduction_audit(&world, NULL, &audit) == -EINVAL);
	assert(picosystem_garden_world_step_reproduction_audit(&world, &wait_policy, NULL) ==
	       -EINVAL);
	assert(memcmp(&audit, &sentinel, sizeof(audit)) == 0);
	assert(memcmp(&world, &before, sizeof(world)) == 0);
	world.auto_gardener_enabled = true;
	assert(picosystem_garden_world_step_reproduction_audit(&world, &wait_policy, &audit) ==
	       -EINVAL);
	assert(memcmp(&audit, &sentinel, sizeof(audit)) == 0);
	world = before;
	world.node_count = PICOSYSTEM_GARDEN_MAX_NODES + 1U;
	assert(picosystem_garden_world_step_reproduction_audit(&world, &wait_policy, &audit) ==
	       -EINVAL);
	assert(memcmp(&audit, &sentinel, sizeof(audit)) == 0);

	ready(&world, 1U);
	same_step(&world, &wait_policy, &audit);
	assert(audit.visits[0].produced && audit.visits[0].energy_required == 144 &&
	       audit.visits[0].water_required == 64 && audit.visits[0].energy == 144U &&
	       audit.visits[0].water == 64U && audit.visits[0].ready_flowers == 1U);
	assert(world.plants[0].stored_energy == 96U && world.plants[0].stored_water == 40U);
	for (unsigned int resource = 0U; resource < 2U; ++resource) {
		ready(&world, 1U);
		if (resource == 0U) {
			--world.plants[0].stored_energy;
		} else {
			--world.plants[0].stored_water;
		}
		same_step(&world, &wait_policy, &audit);
		assert(audit.visits[0].blockers ==
		       (resource == 0U ? PICOSYSTEM_GARDEN_REPRODUCTION_ENERGY
				       : PICOSYSTEM_GARDEN_REPRODUCTION_WATER));
	}
	for (uint8_t cooldown = 1U; cooldown <= 2U; ++cooldown) {
		ready(&world, 1U);
		world.plants[0].reproduction_cooldown = cooldown;
		same_step(&world, &wait_policy, &audit);
		assert(audit.visits[0].cooldown == cooldown - 1U);
		assert(audit.visits[0].blockers ==
		       (cooldown == 1U ? 0U : PICOSYSTEM_GARDEN_REPRODUCTION_COOLDOWN));
	}
	ready(&world, 2U);
	bank(&world, PICOSYSTEM_GARDEN_MAX_SEEDS - 1U);
	same_step(&world, &wait_policy, &audit);
	assert(audit.visits[0].produced &&
	       audit.visits[0].seed_count == PICOSYSTEM_GARDEN_MAX_SEEDS - 1U);
	assert(audit.visits[1].blockers == PICOSYSTEM_GARDEN_REPRODUCTION_BANK &&
	       audit.visits[1].seed_count == PICOSYSTEM_GARDEN_MAX_SEEDS);
	ready(&world, 1U);
	world.nodes[0].growth_progress = 0U;
	same_step(&world, &wait_policy, &audit);
	assert(audit.visits[0].blockers == PICOSYSTEM_GARDEN_REPRODUCTION_FLOWER &&
	       audit.visits[0].immature_flowers == 1U && audit.visits[0].ready_flowers == 0U);
	for (uint8_t progress = 73U; progress <= 74U; ++progress) {
		ready(&world, 1U);
		world.nodes[0].growth_progress = progress;
		same_step(&world, &wait_policy, &audit);
		assert(world.nodes[0].growth_progress == progress + 22U);
		assert(audit.visits[0].produced == (progress == 74U));
	}
	ready(&world, 1U);
	world.nodes[0].flags |= PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED;
	same_step(&world, &wait_policy, &audit);
	assert(audit.visits[0].blockers == PICOSYSTEM_GARDEN_REPRODUCTION_FLOWER &&
	       audit.visits[0].spent_flowers == 1U);
	ready(&world, 1U);
	world.nodes[0].flags |= PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED;
	world.logic_tick_count = 2879U;
	world.ecology_tick_count = 191U;
	same_step(&world, &wait_policy, &audit);
	assert(audit.visits[0].ready_flowers == 1U && audit.visits[0].spent_flowers == 0U);
	assert((audit.visits[0].blockers & PICOSYSTEM_GARDEN_REPRODUCTION_FLOWER) == 0U);
	ready(&world, 1U);
	world.logic_tick_count = 914U;
	world.ecology_tick_count = 60U;
	same_step(&world, &wait_policy, &audit);
	assert(audit.visits[0].blockers == PICOSYSTEM_GARDEN_REPRODUCTION_CADENCE);
	ready(&world, 1U);
	world.logic_tick_count = 959U;
	world.ecology_tick_count = 63U;
	same_step(&world, &wait_policy, &audit);
	assert(audit.visits[0].blockers == PICOSYSTEM_GARDEN_REPRODUCTION_LIGHT);
	ready(&world, 1U);
	world.plants[0].stress = 2U;
	same_step(&world, &wait_policy, &audit);
	assert(audit.visits[0].stress == 1U &&
	       audit.visits[0].blockers == PICOSYSTEM_GARDEN_REPRODUCTION_STRESS);
	ready(&world, 1U);
	world.plants[0].generation = UINT16_MAX;
	world.plants[0].parent_lineage_id = 1U;
	world.maximum_generation = UINT16_MAX;
	same_step(&world, &wait_policy, &audit);
	assert(audit.visits[0].blockers == PICOSYSTEM_GARDEN_REPRODUCTION_GENERATION);
	ready(&world, 1U);
	world.plants[0].flags |= PICOSYSTEM_GARDEN_PLANT_DEAD;
	world.plants[0].stress = PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD;
	same_step(&world, &wait_policy, &audit);
	assert(audit.visits[0].blockers & PICOSYSTEM_GARDEN_REPRODUCTION_DEAD);

	const struct picosystem_garden_reproduction_audit zero = {0};
	for (uint8_t controller = 0U; controller < 2U; ++controller) {
		assert(toy_factory_garden_evaluation_reset(
			       &world, &toy_factory_garden_rainfed_scenarios[1], 0xed52188cU) == 0);
		assert(picosystem_garden_world_set_climate(
			       &world, PICOSYSTEM_GARDEN_CLIMATE_SEASONAL) == 0);
		const struct picosystem_garden_agent_policy *const policy =
			controller == 0U ? picosystem_garden_agent_baseline_policy()
					 : picosystem_garden_agent_adaptive_policy();
		for (uint32_t tick = 1U; tick <= 18U * 3840U; ++tick) {
			same_step(&world, policy, &audit);
			if (!audit.ecology_step) {
				assert(memcmp(&audit, &zero, sizeof(audit)) == 0);
			}
		}
	}
	printf("Production audit boundaries and full-world noninterference passed (%zu bytes)\n",
	       sizeof(audit));
	return 0;
}
