/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "garden_agent.h"

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

static const struct picosystem_garden_agent_policy policy = {
	.decide = wait_decide,
	.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS,
};

static uint8_t fixture(struct picosystem_garden_world *world, bool compacted, uint8_t spent)
{
	assert(picosystem_garden_world_reset(world, 123U) == 0);
	world->auto_gardener_enabled = false;
	if (!compacted) {
		assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_FLOWER,
							  0U) == 0);
	}
	assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_SHRUB, 8U) == 0);
	const uint8_t index = (uint8_t)(world->plant_count - 1U);
	struct picosystem_garden_plant *const plant = &world->plants[index];
	/* The same founder in either its original slot or the compacted slot zero. */
	plant->lineage_id = 2U;
	world->lineage_sequence = 2U;
	for (uint8_t i = 0U; i < 4U; ++i) {
		world->nodes[world->node_count] = world->nodes[plant->base_node_index];
		world->nodes[world->node_count].parent_index = plant->base_node_index;
		++world->node_count;
		++plant->node_count;
	}
	for (uint16_t i = 0U; i < world->node_count; ++i) {
		world->nodes[i].flags = 0U;
		world->nodes[i].growth_progress = UINT8_MAX;
		world->leaf_condition[i] = 0U;
	}
	for (uint16_t i = 0U; i < 4U; ++i) {
		world->nodes[world->node_count - 4U + i].flags =
			PICOSYSTEM_GARDEN_NODE_FLOWER |
			(i < spent ? PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED : 0U);
	}
	plant->stored_energy = 256U;
	plant->stored_water = 512U;
	return index;
}

static void purchase(struct picosystem_garden_world *world, uint8_t index, uint32_t tick,
		     bool allowed)
{
	assert((tick % 60U) == 0U);
	world->logic_tick_count = tick - 1U;
	world->ecology_tick_count = tick / 15U - 1U;
	const uint32_t random = world->plants[index].random_state;
	const uint32_t created = world->seed_creation_count;
	const uint16_t energy = world->plants[index].stored_energy;
	assert(picosystem_garden_world_step_with_policy(world, &policy) == 0);
	assert(world->seed_creation_count == created + (allowed ? 1U : 0U));
	assert(world->plants[index].stored_energy == energy - 1U - (allowed ? 48U : 0U));
	assert(world->plants[index].stored_water == 511U - (allowed ? 24U : 0U));
	assert(world->plants[index].reproduction_cooldown == (allowed ? 16U : 0U));
	assert((world->plants[index].random_state != random) == allowed);
}

int main(void)
{
	bool veto_enabled = false;
#if defined(TOY_FACTORY_GARDEN_FOCAL_SEED_VETO)
	veto_enabled = true;
#endif
	struct picosystem_garden_world world;
	for (uint8_t compacted = 0U; compacted < 2U; ++compacted) {
		for (uint8_t spent = 0U; spent < 4U; ++spent) {
			const uint8_t index = fixture(&world, compacted != 0U, spent);
			const uint16_t flower = (uint16_t)(world.node_count - 4U + spent);
			const bool allowed = !veto_enabled || (spent < 3U);
			purchase(&world, index, 4620U, allowed);
			assert(((world.nodes[flower].flags &
				 PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED) != 0U) == allowed);
			if (!allowed) {
				/* A later eligible retry must not sneak the fourth seed through. */
				world.plants[index].stored_water = 512U;
				purchase(&world, index, 4680U, false);
			}
		}
	}
	for (uint8_t descendant = 0U; descendant < 2U; ++descendant) {
		const uint8_t index = fixture(&world, true, 3U);
		world.plants[index].lineage_id = 3U;
		world.lineage_sequence = 3U;
		if (descendant != 0U) {
			world.plants[index].parent_lineage_id = 2U;
			world.plants[index].generation = 1U;
			world.maximum_generation = 1U;
		}
		purchase(&world, index, 4620U, true);
	}
	/* Before, within, and after the fixed daylight interval. At either endpoint
	 * ordinary low-light checks still prevent purchases, and dawn clears flags.
	 */
	const uint32_t ticks[] = {900U, 2880U, 3180U, 4740U, 4800U, 8460U};
	for (size_t i = 0U; i < sizeof(ticks) / sizeof(ticks[0]); ++i) {
		const uint8_t index = fixture(&world, true, 3U);
		const uint32_t tick = ticks[i];
		const bool ordinary = (tick != 2880U) && (tick != 4800U);
		const bool limited = veto_enabled && (tick >= 2880U) && (tick < 4800U);
		purchase(&world, index, tick, ordinary && !limited);
		if (tick == 2880U) {
			for (uint16_t n = 0U; n < world.node_count; ++n) {
				assert((world.nodes[n].flags &
					PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED) == 0U);
			}
		}
	}
	/* A veto must not replace ordinary affordability/maturity/cooldown checks. */
	for (uint8_t reason = 0U; reason < 3U; ++reason) {
		const uint8_t index = fixture(&world, true, 2U);
		world.logic_tick_count = 4619U;
		world.ecology_tick_count = 307U;
		if (reason == 0U) {
			world.plants[index].stored_energy = 1U;
		} else if (reason == 1U) {
			world.plants[index].reproduction_cooldown = 2U;
		} else {
			world.nodes[world.node_count - 1U].growth_progress = 0U;
			world.nodes[world.node_count - 2U].growth_progress = 0U;
		}
		const uint32_t random = world.plants[index].random_state;
		assert(picosystem_garden_world_step_with_policy(&world, &policy) == 0);
		assert(world.seed_creation_count == 0U &&
		       world.plants[index].random_state == random);
	}
	puts("Focal seed veto production path, retries, identity, timing and debit isolation "
	     "passed");
	return 0;
}
