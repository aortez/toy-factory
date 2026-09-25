/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_agent.h"
#include "garden_leaf.h"
#include "garden_seed_audit.h"

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

static void fixture(struct picosystem_garden_world *world)
{
	assert(picosystem_garden_world_reset(world, 123U) == 0);
	assert(!world->plant_slots_sixteen);
	world->auto_gardener_enabled = false;
	world->wet_germination_enabled = true;
	for (uint8_t i = 0U; i < 8U; ++i) {
		assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_FLOWER,
							  (uint8_t)(i * 3U)) == 0);
	}
	memset(world->moisture, UINT8_MAX, sizeof(world->moisture));
	world->seed_count = 1U;
	world->seeds[0] = (struct picosystem_garden_seed){
		.genome = world->plants[0].genome,
		.parent_lineage_id = 1U,
		.generation = 1U,
		.column = 27U,
		.age_ecology_ticks = 7U,
		.species_id = PICOSYSTEM_GARDEN_SPECIES_FLOWER,
	};
	world->logic_tick_count = 69119U;
	world->ecology_tick_count = 4607U;
}

static uint8_t blockers(const struct picosystem_garden_world *world)
{
	uint8_t result = UINT8_MAX;
	assert(picosystem_garden_world_seed_germination_blockers(world, 0U, &result) == 0);
	return result;
}

static void test_boundary(void)
{
	struct picosystem_garden_world control, candidate;
	fixture(&control);
	candidate = control;
	candidate.plant_slots_sixteen = true;
	assert(picosystem_garden_world_hash(&control) == picosystem_garden_world_hash(&candidate));
	for (uint32_t t = 69120U; t < 69135U; ++t) {
		assert(picosystem_garden_world_step_with_policy(&control, &wait_policy) == 0);
		assert(picosystem_garden_world_step_with_policy(&candidate, &wait_policy) == 0);
		struct picosystem_garden_world plain = candidate;
		plain.plant_slots_sixteen = false;
		assert(memcmp(&control, &plain, sizeof(control)) == 0);
		assert(control.logic_tick_count == t && control.plant_count == 8U);
		if (t == 69120U) {
			assert(blockers(&candidate) ==
			       PICOSYSTEM_GARDEN_SEED_BLOCKED_PLANT_CAPACITY);
			const struct picosystem_garden_world before = candidate;
			assert(picosystem_garden_world_plant_seed(&candidate,
								  PICOSYSTEM_GARDEN_SPECIES_FLOWER,
								  27U) == -ENOSPC);
			assert(memcmp(&candidate, &before, sizeof(candidate)) == 0);
		}
	}
	struct picosystem_garden_seed_audit a, b;
	assert(picosystem_garden_world_step_seed_audit(&control, &wait_policy, &a) == 0);
	assert(picosystem_garden_world_step_seed_audit(&candidate, &wait_policy, &b) == 0);
	assert(control.plant_count == 8U && control.seed_count == 1U);
	assert(candidate.plant_count == 9U && candidate.seed_count == 0U);
	assert(a.attempts[0].blockers == PICOSYSTEM_GARDEN_SEED_BLOCKED_PLANT_CAPACITY);
	assert(b.attempts[0].outcome == PICOSYSTEM_GARDEN_SEED_GERMINATED);
	assert(b.stages[PICOSYSTEM_GARDEN_SEED_AFTER_CHECKS].nodes ==
	       b.stages[PICOSYSTEM_GARDEN_SEED_BEFORE_CHECKS].nodes + 4U);
	assert(picosystem_garden_world_reset(&candidate, 123U) == 0);
	assert(!candidate.plant_slots_sixteen);
	fixture(&candidate);
	candidate.plant_slots_sixteen = true;
	candidate.logic_tick_count = 69121U;
	assert(picosystem_garden_world_plant_seed(&candidate, PICOSYSTEM_GARDEN_SPECIES_FLOWER,
						  27U) == 0);
}

/* Controlled valid topology tests storage independently of the spacing ceiling. */
static void populate_storage(struct picosystem_garden_world *world, uint8_t count)
{
	assert(count > 0U && count <= PICOSYSTEM_GARDEN_MAX_PLANTS);
	assert(picosystem_garden_world_reset(world, 123U) == 0);
	world->auto_gardener_enabled = false;
	world->plant_slots_sixteen = true;
	world->wet_germination_enabled = true;
	world->logic_tick_count = 69134U;
	world->ecology_tick_count = 4608U;
	assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 0U) ==
	       0);
	for (uint8_t i = 1U; i < count; ++i) {
		world->plants[i] = world->plants[0];
		world->plants[i].lineage_id = (uint32_t)i + 1U;
		world->plants[i].base_node_index = (uint16_t)(4U * i);
		for (uint16_t n = 0U; n < 4U; ++n) {
			const uint16_t index = (uint16_t)(4U * i + n);
			world->nodes[index] = world->nodes[n];
			world->nodes[index].plant_index = i;
			if (n != 0U) {
				world->nodes[index].parent_index = (uint16_t)(4U * i);
			}
			world->leaf_condition[index] = world->leaf_condition[n];
		}
	}
	world->plant_count = count;
	world->lineage_sequence = count;
	world->node_count = (uint16_t)(4U * count);
	memset(world->moisture, UINT8_MAX, sizeof(world->moisture));
	world->seed_count = 2U;
	world->seeds[0] = (struct picosystem_garden_seed){
		.genome = world->plants[0].genome,
		.parent_lineage_id = 1U,
		.generation = 1U,
		.column = 20U,
		.age_ecology_ticks = 8U,
		.species_id = PICOSYSTEM_GARDEN_SPECIES_FLOWER,
	};
	world->seeds[1] = world->seeds[0];
	world->seeds[1].column = 27U;
}

static void test_bounds(void)
{
	struct picosystem_garden_world world;
	populate_storage(&world, 16U);
	assert(blockers(&world) == PICOSYSTEM_GARDEN_SEED_BLOCKED_PLANT_CAPACITY);
	const struct picosystem_garden_world full = world;
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 27U) ==
	       -ENOSPC);
	assert(memcmp(&world, &full, sizeof(world)) == 0);
	world.plant_count = 17U;
	uint8_t result = 91U;
	assert(picosystem_garden_world_seed_germination_blockers(&world, 0U, &result) == -EINVAL);
	assert(result == 91U);
	world = full;
	world.plant_slots_sixteen = false;
	assert(picosystem_garden_world_step_with_policy(&world, &wait_policy) == -EINVAL);
	populate_storage(&world, 15U);
	assert(blockers(&world) == 0U);
	struct picosystem_garden_seed_audit audit;
	assert(picosystem_garden_world_step_seed_audit(&world, &wait_policy, &audit) == 0);
	assert(world.plant_count == 16U && world.seed_count == 1U);
	assert(audit.attempts[0].outcome == PICOSYSTEM_GARDEN_SEED_GERMINATED);
	assert(audit.attempts[1].blockers == PICOSYSTEM_GARDEN_SEED_BLOCKED_PLANT_CAPACITY);
	assert(!world.dark_guard.overflow && !world.night_capacity.overflow);
	for (uint16_t count = 508U; count <= 509U; ++count) {
		populate_storage(&world, 1U);
		for (uint16_t i = 4U; i < count; ++i) {
			world.nodes[i] = world.nodes[0];
			world.nodes[i].parent_index = 0U;
		}
		world.node_count = count;
		world.plants[0].node_count = count;
		assert(blockers(&world) ==
		       (count == 508U ? 0U : PICOSYSTEM_GARDEN_SEED_BLOCKED_NODE_CAPACITY));
		const struct picosystem_garden_world before = world;
		assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER,
							  27U) == (count == 508U ? 0 : -ENOSPC));
		if (count == 508U) {
			assert(world.node_count == 512U);
		} else {
			assert(memcmp(&world, &before, sizeof(world)) == 0);
		}
	}
	populate_storage(&world, 1U);
	world.seed_count = 9U;
	assert(picosystem_garden_world_step_with_policy(&world, &wait_policy) == -EINVAL);
}

static void test_diagnostic_bounds(void)
{
	struct picosystem_garden_world world;
	populate_storage(&world, 16U);
	for (uint8_t i = 0U; i < 16U; ++i) {
		const uint16_t leaf = (uint16_t)(4U * i + 1U);
		world.nodes[leaf].growth_progress = UINT8_MAX;
		world.plants[i].stored_energy = 256U;
		world.plants[i].stored_water = 512U;
		/* Exercise every diagnostic entry, including indexes beyond the old 24. */
		for (uint8_t repeat = 0U; repeat < 3U; ++repeat) {
			world.leaf_condition[leaf] = 0U;
			assert(picosystem_garden_leaf_renew(&world, i, leaf) == 0);
		}
	}
	assert(world.dark_guard.count == 48U && !world.dark_guard.overflow);
	world.leaf_condition[1] = 0U;
	const uint32_t hash = picosystem_garden_world_hash(&world);
	assert(picosystem_garden_leaf_renew(&world, 0U, 1U) == -EAGAIN);
	assert(world.dark_guard.overflow && picosystem_garden_world_hash(&world) == hash);
	const struct picosystem_garden_dark_event expense = {
		.kind = PICOSYSTEM_GARDEN_EXPENSE_GROWTH,
		.nodes_before = 4U,
		.nodes_after = 5U,
	};
	for (uint8_t i = 0U; i < 16U; ++i) {
		assert(picosystem_garden_night_check(&world.night_capacity, &expense,
						     (uint8_t)(2U * i)) == 0);
	}
	assert(world.night_capacity.count == 16U && !world.night_capacity.overflow);
	assert(picosystem_garden_night_check(&world.night_capacity, &expense, 32U) == -EOVERFLOW);
	assert(world.night_capacity.overflow);
}

int main(void)
{
	_Static_assert(PICOSYSTEM_GARDEN_MAX_NODES == 512U && PICOSYSTEM_GARDEN_MAX_SEEDS == 8U,
		       "Only plant admission changes");
	_Static_assert(PICOSYSTEM_GARDEN_DARK_EVENTS == 48U &&
			       PICOSYSTEM_GARDEN_NIGHT_EVENTS == 16U,
		       "Diagnostics must hold the expanded population");
	bool enabled = false;
	assert(picosystem_garden_plant_slots_parse(NULL, &enabled) == -EINVAL);
	assert(picosystem_garden_plant_slots_parse("16", NULL) == -EINVAL);
	assert(picosystem_garden_plant_slots_parse("8", &enabled) == -EINVAL && !enabled);
	assert(picosystem_garden_plant_slots_parse("16", &enabled) == 0 && enabled);
	assert(picosystem_garden_plant_slots_parse("16", &enabled) == -EINVAL && enabled);
	assert(picosystem_garden_plant_slots_limit(false, UINT32_MAX) == 8U);
	assert(picosystem_garden_plant_slots_limit(true, 0U) == 8U);
	assert(picosystem_garden_plant_slots_limit(true, 69120U) == 8U);
	assert(picosystem_garden_plant_slots_limit(true, 69121U) == 16U);
	test_boundary();
	test_bounds();
	test_diagnostic_bounds();
	printf("Plant slots bounds passed; world=%zu plant=%zu dark=%zu night=%zu bytes\n",
	       sizeof(struct picosystem_garden_world), sizeof(struct picosystem_garden_plant),
	       sizeof(struct picosystem_garden_dark_audit),
	       sizeof(struct picosystem_garden_night_audit));
	return 0;
}
