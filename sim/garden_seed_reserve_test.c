/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_agent.h"
#if defined(TOY_FACTORY_GARDEN_SEED_RESERVE)
#include "garden_seed_reserve.h"
#endif

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

static void production_step(uint16_t count)
{
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	world.auto_gardener_enabled = false;
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 0U) ==
	       0);
	for (uint16_t i = world.node_count; i < count; ++i) {
		world.nodes[i] = world.nodes[0];
		world.nodes[i].parent_index = 0U;
	}
	world.node_count = count;
	world.plants[0].node_count = count;
	for (uint16_t i = 0U; i < count; ++i) {
		world.nodes[i].flags = 0U;
		world.leaf_condition[i] = 0U;
		world.nodes[i].growth_progress = UINT8_MAX;
	}
	world.nodes[0].flags = PICOSYSTEM_GARDEN_NODE_FLOWER;
	world.plants[0].stored_energy = 256U;
	world.plants[0].stored_water = 512U;
	world.plants[0].reproduction_cooldown = 0U;
	world.logic_tick_count = 899U;
	world.ecology_tick_count = 59U; /* Next step has phase 124 and upkeep. */
	const uint32_t random = world.plants[0].random_state;
	const struct picosystem_garden_agent_policy policy = {
		.decide = wait_decide,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS,
	};
	assert(picosystem_garden_world_step_with_policy(&world, &policy) == 0);
	bool allowed = true;
#if defined(TOY_FACTORY_GARDEN_SEED_RESERVE)
	allowed = count == 4U;
#endif
	assert(world.seed_creation_count == (allowed ? 1U : 0U));
	assert(world.seed_count == world.seed_creation_count);
	assert(world.plants[0].last_energy_income == 0U);
	assert(world.plants[0].stored_energy == 256U - (count + 7U) / 8U - (allowed ? 48U : 0U));
	assert(world.plants[0].reproduction_cooldown == (allowed ? 16U : 0U));
	assert(((world.nodes[0].flags & PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED) != 0U) == allowed);
	assert((world.plants[0].random_state != random) == allowed);
}

int main(void)
{
#if defined(TOY_FACTORY_GARDEN_SEED_RESERVE)
	struct picosystem_garden_seed_reserve_forecast f;
	/* At phase 124, one sunset payment plus 31 night payments remain. */
	assert(picosystem_garden_seed_reserve_forecast(240U, 0U, 48U, 124U, &f) == 0);
	assert(f.allowed && f.after_seed == 192 && f.projected_sunset == 186 &&
	       f.night_upkeep == 186U);
	assert(picosystem_garden_seed_reserve_forecast(239U, 0U, 48U, 124U, &f) == 0 && !f.allowed);
	assert(picosystem_garden_seed_reserve_forecast(240U, 0U, 49U, 124U, &f) == 0 && !f.allowed);
	/* Actual cap-before-upkeep ordering: even abundant income cannot exceed 248 at sunset. */
	assert(picosystem_garden_seed_reserve_forecast(248U, 255U, 64U, 124U, &f) == 0);
	assert(f.allowed && f.projected_sunset == 248 && f.night_upkeep == 248U);
	assert(picosystem_garden_seed_reserve_forecast(248U, 255U, 65U, 124U, &f) == 0 &&
	       !f.allowed);
	assert(picosystem_garden_seed_reserve_forecast(248U, 30U, 64U, 124U, &f) == 0 &&
	       !f.allowed);
	assert(picosystem_garden_seed_reserve_forecast(248U, 36U, 64U, 124U, &f) == 0 &&
	       !f.allowed);
	assert(picosystem_garden_seed_reserve_forecast(248U, 38U, 64U, 124U, &f) == 0 && f.allowed);
	/* Early purchases can refill; the same purchase near sunset cannot. */
	assert(picosystem_garden_seed_reserve_forecast(248U, 8U, 64U, 64U, &f) == 0 && f.allowed);
	assert(picosystem_garden_seed_reserve_forecast(248U, 8U, 64U, 124U, &f) == 0 && !f.allowed);
	assert(picosystem_garden_seed_reserve_forecast(248U, 255U, 64U, 127U, &f) == 0 &&
	       !f.allowed);
	for (uint16_t p = 128U; p < 256U; ++p) {
		assert(picosystem_garden_seed_reserve_forecast(256U, 255U, 4U, (uint8_t)p, &f) ==
			       0 &&
		       !f.allowed);
	}
	assert(picosystem_garden_seed_reserve_forecast(256U, 255U, 4U, 0U, &f) == 0 && !f.allowed);
	assert(picosystem_garden_seed_reserve_forecast(48U, 255U, 4U, 64U, &f) == 0 && !f.allowed);
	assert(picosystem_garden_seed_reserve_forecast(0U, 0U, 512U, 1U, &f) == 0 && !f.allowed);
	const struct picosystem_garden_seed_reserve_forecast before = f;
	assert(picosystem_garden_seed_reserve_forecast(257U, 0U, 4U, 64U, &f) == -EINVAL);
	assert(picosystem_garden_seed_reserve_forecast(256U, 0U, 0U, 64U, &f) == -EINVAL);
	assert(picosystem_garden_seed_reserve_forecast(256U, 0U, 513U, 64U, &f) == -EINVAL);
	assert(picosystem_garden_seed_reserve_forecast(256U, 0U, 4U, 64U, NULL) == -EINVAL);
	assert(memcmp(&before, &f, sizeof(f)) == 0);
#endif
	production_step(4U);
	production_step(64U);
	puts("Seed reserve forecast and real production-step boundaries passed");
	return 0;
}
