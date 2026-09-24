/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_agent.h"
#include "garden_seed_audit.h"

static const uint8_t columns[] = {0U, 4U, 8U, 13U, 18U, 23U, 27U};

static void fixture(struct picosystem_garden_world *world)
{
	assert(picosystem_garden_world_reset(world, 123U) == 0);
	assert(!world->seed_spacing_two);
	world->auto_gardener_enabled = false;
	world->wet_germination_enabled = true;
	for (uint8_t i = 0U; i < sizeof(columns); ++i) {
		assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_FLOWER,
							  columns[i]) == 0);
	}
	memset(world->moisture, UINT8_MAX, sizeof(world->moisture));
	memset(world->light, UINT8_MAX, sizeof(world->light));
	world->seed_count = 2U;
	world->seeds[0] = (struct picosystem_garden_seed){
		.genome = world->plants[0].genome,
		.parent_lineage_id = 1U,
		.generation = 1U,
		.column = 2U,
		.age_ecology_ticks = 8U,
		.species_id = PICOSYSTEM_GARDEN_SPECIES_FLOWER,
	};
	world->seeds[1] = world->seeds[0];
}

static uint8_t blockers(const struct picosystem_garden_world *world)
{
	uint8_t mask = UINT8_MAX;
	assert(picosystem_garden_world_seed_germination_blockers(world, 0U, &mask) == 0);
	return mask;
}

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

int main(void)
{
	bool enabled = false;
	assert(picosystem_garden_seed_spacing_parse(NULL, &enabled) == -EINVAL);
	assert(picosystem_garden_seed_spacing_parse("2", NULL) == -EINVAL);
	assert(picosystem_garden_seed_spacing_parse("3", &enabled) == -EINVAL && !enabled);
	assert(picosystem_garden_seed_spacing_parse("2", &enabled) == 0 && enabled);
	assert(picosystem_garden_seed_spacing_parse("2", &enabled) == -EINVAL && enabled);
	assert(picosystem_garden_seed_spacing_minimum(false, UINT32_MAX) == 3U);
	assert(picosystem_garden_seed_spacing_minimum(true, 0U) == 3U);
	assert(picosystem_garden_seed_spacing_minimum(true, 69120U) == 3U);
	assert(picosystem_garden_seed_spacing_minimum(true, 69121U) == 2U);
	struct picosystem_garden_world fixed, relaxed;
	fixture(&fixed);
	relaxed = fixed;
	relaxed.seed_spacing_two = true;
	assert(picosystem_garden_world_hash(&fixed) == picosystem_garden_world_hash(&relaxed));
	fixed.logic_tick_count = relaxed.logic_tick_count = 69120U;
	assert(blockers(&fixed) == PICOSYSTEM_GARDEN_SEED_BLOCKED_SPACING);
	assert(blockers(&relaxed) == PICOSYSTEM_GARDEN_SEED_BLOCKED_SPACING);
	relaxed.logic_tick_count = 69135U;
	struct picosystem_garden_seed_sites sites;
	assert(picosystem_garden_world_seed_sites(&relaxed, &sites) == 0);
	uint8_t open = 0U;
	for (uint8_t column = 0U; column < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++column) {
		bool available = true;
		for (uint8_t i = 0U; i < sizeof(columns); ++i) {
			const int distance = (int)column - columns[i];
			available = available && ((distance <= -2) || (distance >= 2));
		}
		assert((sites.blockers[column] == 0U) == available);
		if (available) {
			++open;
		}
	}
	assert(open == 9U && blockers(&relaxed) == 0U);
	relaxed.moisture[2] = 11U;
	assert(blockers(&relaxed) == PICOSYSTEM_GARDEN_SEED_BLOCKED_MOISTURE);
	relaxed.moisture[2] = 12U;
	relaxed.seeds[0].age_ecology_ticks = 7U;
	assert(blockers(&relaxed) == PICOSYSTEM_GARDEN_SEED_BLOCKED_DORMANT);
	relaxed.seeds[0].age_ecology_ticks = 8U;
	relaxed.wet_germination_enabled = false;
	relaxed.light[(PICOSYSTEM_GARDEN_CANOPY_ROWS - 1U) * PICOSYSTEM_GARDEN_GRID_COLUMNS + 2U] =
		79U;
	assert(blockers(&relaxed) == PICOSYSTEM_GARDEN_SEED_BLOCKED_LIGHT);
	relaxed = fixed;
	relaxed.logic_tick_count = 69135U;
	relaxed.seed_spacing_two = true;
	relaxed.plants[0].flags = PICOSYSTEM_GARDEN_PLANT_DEAD;
	relaxed.plants[0].stress = PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD;
	relaxed.seeds[0].column = 1U;
	assert(blockers(&relaxed) == PICOSYSTEM_GARDEN_SEED_BLOCKED_SPACING);
	relaxed.seeds[0].column = 2U;
	assert(blockers(&relaxed) == 0U);
	const struct picosystem_garden_world before = relaxed;
	assert(picosystem_garden_world_plant_seed(&relaxed, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 1U) ==
	       -EEXIST);
	assert(memcmp(&before, &relaxed, sizeof(before)) == 0);
	assert(picosystem_garden_world_plant_seed(&relaxed, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 2U) ==
	       0);
	assert((blockers(&relaxed) & PICOSYSTEM_GARDEN_SEED_BLOCKED_PLANT_CAPACITY) != 0U);
	relaxed = fixed;
	relaxed.seed_spacing_two = true;
	relaxed.logic_tick_count = 69135U;
	for (uint16_t i = relaxed.node_count; i < PICOSYSTEM_GARDEN_MAX_NODES - 3U; ++i) {
		relaxed.nodes[i] = relaxed.nodes[0];
		relaxed.nodes[i].parent_index = 0U;
		++relaxed.plants[0].node_count;
	}
	relaxed.node_count = PICOSYSTEM_GARDEN_MAX_NODES - 3U;
	assert(blockers(&relaxed) == PICOSYSTEM_GARDEN_SEED_BLOCKED_NODE_CAPACITY);
	const struct picosystem_garden_agent_policy policy = {
		.decide = wait_decide,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS,
	};
	for (uint8_t treatment = 0U; treatment < 2U; ++treatment) {
		fixture(&relaxed);
		relaxed.seed_spacing_two = treatment != 0U;
		relaxed.logic_tick_count = 69119U;
		relaxed.ecology_tick_count = 4607U;
		assert(picosystem_garden_world_step_with_policy(&relaxed, &policy) == 0);
		assert(relaxed.germination_count == 0U);
		for (uint8_t i = 0U; i < 14U; ++i) {
			assert(picosystem_garden_world_step_with_policy(&relaxed, &policy) == 0);
		}
		struct picosystem_garden_seed_audit audit;
		struct picosystem_garden_world plain = relaxed;
		assert(picosystem_garden_world_step_with_policy(&plain, &policy) == 0);
		assert(picosystem_garden_world_step_seed_audit(&relaxed, &policy, &audit) == 0);
		assert(memcmp(&plain, &relaxed, sizeof(plain)) == 0);
		assert(relaxed.germination_count == treatment);
		if (treatment) {
			assert(audit.attempts[0].outcome == PICOSYSTEM_GARDEN_SEED_GERMINATED);
			assert(audit.attempts[1].moisture + 12U == audit.attempts[0].moisture);
			assert(audit.attempts[1].blockers ==
			       (PICOSYSTEM_GARDEN_SEED_BLOCKED_SPACING |
				PICOSYSTEM_GARDEN_SEED_BLOCKED_PLANT_CAPACITY));
			assert(relaxed.plants[7].node_count == 4U);
			assert(relaxed.plants[7].stored_energy == 64U &&
			       relaxed.plants[7].stored_water == 24U);
		} else {
			assert(audit.attempts[0].blockers ==
			       PICOSYSTEM_GARDEN_SEED_BLOCKED_SPACING);
		}
	}
	assert(picosystem_garden_world_reset(&relaxed, 123U) == 0 && !relaxed.seed_spacing_two);
	puts("Spacing boundary, creation, sequential germination, resource gates, capacity and "
	     "reset passed");
	return 0;
}
