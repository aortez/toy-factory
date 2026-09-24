/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
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

static void fixture(struct picosystem_garden_world *world, uint8_t seed_count)
{
	assert(picosystem_garden_world_reset(world, 123U) == 0);
	assert(!world->seed_order_rotating);
	world->auto_gardener_enabled = false;
	for (uint8_t i = 0U; i < 3U; ++i) {
		assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_FLOWER,
							  (uint8_t)(i * 8U)) == 0);
		world->plants[i].stored_energy = 256U;
		world->plants[i].stored_water = 512U;
		world->plants[i].reproduction_cooldown = 0U;
	}
	for (uint16_t i = 0U; i < world->node_count; ++i) {
		world->nodes[i].flags = PICOSYSTEM_GARDEN_NODE_FLOWER;
		world->nodes[i].growth_progress = UINT8_MAX;
		world->leaf_condition[i] = 0U;
	}
	for (uint8_t i = 0U; i < seed_count; ++i) {
		world->seeds[i] = (struct picosystem_garden_seed){
			.genome = world->plants[0].genome,
			.parent_lineage_id = world->plants[0].lineage_id,
			.generation = 1U,
			.column = 27U,
			.species_id = PICOSYSTEM_GARDEN_SPECIES_FLOWER,
		};
	}
	world->seed_count = seed_count;
}

static void step_at(struct picosystem_garden_world *world, uint32_t tick)
{
	world->logic_tick_count = tick - 1U;
	world->ecology_tick_count = tick / 15U - 1U;
	const struct picosystem_garden_agent_policy policy = {
		.decide = wait_decide,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS,
	};
	assert(picosystem_garden_world_step_with_policy(world, &policy) == 0);
}

int main(void)
{
	bool enabled = false;
	assert(picosystem_garden_seed_order_parse(NULL, &enabled) == -EINVAL);
	assert(picosystem_garden_seed_order_parse("bad", &enabled) == -EINVAL && !enabled);
	assert(picosystem_garden_seed_order_parse("rotating", NULL) == -EINVAL);
	assert(picosystem_garden_seed_order_parse("rotating", &enabled) == 0 && enabled);
	assert(picosystem_garden_seed_order_parse("rotating", &enabled) == -EINVAL && enabled);
	for (uint8_t count = 0U; count <= PICOSYSTEM_GARDEN_MAX_PLANTS; ++count) {
		assert(picosystem_garden_seed_order_start(0U, count) == 0U);
		assert(picosystem_garden_seed_order_start(69120U, count) == 0U);
		assert(picosystem_garden_seed_order_start(69135U, count) == 0U);
		for (uint32_t turn = 1U; turn <= 32U; ++turn) {
			const uint8_t start =
				picosystem_garden_seed_order_start(69120U + turn * 60U, count);
			assert(start == (count == 0U ? 0U : turn % count));
			uint16_t seen = 0U;
			for (uint8_t visit = 0U; visit < count; ++visit) {
				const uint8_t index = (uint8_t)((start + visit) % count);
				assert((seen & (1U << index)) == 0U);
				seen |= (uint16_t)(1U << index);
			}
			assert(seen == (1U << count) - 1U);
		}
	}
	struct picosystem_garden_world fixed, rotated;
	fixture(&fixed, 7U);
	rotated = fixed;
	rotated.seed_order_rotating = true;
	assert(picosystem_garden_world_hash(&fixed) == picosystem_garden_world_hash(&rotated));
	step_at(&fixed, 69120U);
	step_at(&rotated, 69120U);
	rotated.seed_order_rotating = false;
	assert(memcmp(&fixed, &rotated, sizeof(fixed)) == 0);
	for (uint8_t slots = 1U; slots <= 2U; ++slots) {
		fixture(&fixed, (uint8_t)(8U - slots));
		rotated = fixed;
		rotated.seed_order_rotating = true;
		step_at(&fixed, 69180U);
		step_at(&rotated, 69180U);
		assert(fixed.seed_creation_count == slots && rotated.seed_creation_count == slots);
		for (uint8_t i = 0U; i < slots; ++i) {
			assert(fixed.seeds[8U - slots + i].parent_lineage_id ==
			       fixed.plants[i].lineage_id);
			assert(rotated.seeds[8U - slots + i].parent_lineage_id ==
			       rotated.plants[i + 1U].lineage_id);
		}
		for (uint8_t i = 0U; i < 3U; ++i) {
			const struct picosystem_garden_plant *const p = &rotated.plants[i];
			const bool bought = (i > 0U) && (i <= slots);
			assert(p->lineage_id == fixed.plants[i].lineage_id);
			assert(p->last_energy_income == 0U);
			assert(p->stored_energy ==
			       256U - (p->node_count + 7U) / 8U - (bought ? 48U : 0U));
			assert(p->reproduction_cooldown == (bought ? 16U : 0U));
			assert(p->stored_water == fixed.plants[i].stored_water +
							  (i < slots ? 24U : 0U) -
							  (bought ? 24U : 0U));
		}
	}
	fixture(&rotated, 8U);
	rotated.seed_order_rotating = true;
	for (uint8_t i = 0U; i < 3U; ++i) {
		rotated.plants[i].reproduction_cooldown = 2U;
	}
	step_at(&rotated, 69180U);
	assert(rotated.seed_creation_count == 0U);
	for (uint8_t i = 0U; i < 3U; ++i) {
		assert(rotated.plants[i].reproduction_cooldown == 1U);
	}
	for (uint8_t reason = 0U; reason < 3U; ++reason) {
		fixture(&rotated, 7U);
		rotated.seed_order_rotating = true;
		if (reason == 0U) {
			rotated.plants[1].stored_energy = 1U;
		} else if (reason == 1U) {
			rotated.plants[1].reproduction_cooldown = 2U;
		} else {
			for (uint16_t i = 0U; i < rotated.node_count; ++i) {
				if (rotated.nodes[i].plant_index == 1U) {
					rotated.nodes[i].flags = 0U;
				}
			}
		}
		step_at(&rotated, 69180U);
		assert(rotated.seed_creation_count == 1U);
		assert(rotated.seeds[7].parent_lineage_id == rotated.plants[2].lineage_id);
	}
	assert(picosystem_garden_world_reset(&rotated, 123U) == 0);
	assert(!rotated.seed_order_rotating);
	puts("Seed-order boundaries, real purchases, gates, cooldowns and reset passed");
	return 0;
}
