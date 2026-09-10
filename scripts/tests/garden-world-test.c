/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "garden_agent.h"
#include "garden_world.h"

static void test_reset_and_validation(void)
{
	assert(picosystem_garden_world_reset(NULL, 1U) == -EINVAL);
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, 0U) == 0);
	assert(world.random_state != 0U);
	assert(world.plant_count == 0U);
	assert(world.node_count == 0U);
	assert(world.cursor_column == PICOSYSTEM_GARDEN_GRID_COLUMNS / 2U);
	assert(world.cursor_row == PICOSYSTEM_GARDEN_CANOPY_ROWS);
	assert(world.light[0] == UINT8_MAX);
	assert(picosystem_garden_world_hash(&world) != 0U);
	assert(picosystem_garden_species_name(PICOSYSTEM_GARDEN_SPECIES_SHRUB) != NULL);
	assert(strcmp(picosystem_garden_species_name(PICOSYSTEM_GARDEN_SPECIES_COUNT), "unknown") ==
	       0);
	assert(strcmp(picosystem_garden_tool_name(PICOSYSTEM_GARDEN_TOOL_WATER), "water") == 0);
}

static void test_seed_spacing_capacity_and_access(void)
{
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, UINT32_C(0x12345678)) == 0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_COUNT, 2U) ==
	       -ERANGE);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER,
						  PICOSYSTEM_GARDEN_GRID_COLUMNS) == -ERANGE);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 2U) ==
	       0);
	assert(world.plant_count == 1U);
	assert(world.node_count == 4U);
	const struct picosystem_garden_world unchanged = world;
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_SHRUB, 4U) ==
	       -EEXIST);
	assert(memcmp(&world, &unchanged, sizeof(world)) == 0);
	assert(picosystem_garden_world_node_at(&world, 3U) != NULL);
	assert(picosystem_garden_world_node_at(&world, 4U) == NULL);
	assert(picosystem_garden_world_plant_at(&world, 0U) != NULL);
	assert(picosystem_garden_world_plant_at(&world, 1U) == NULL);

	for (uint8_t index = 1U; index < PICOSYSTEM_GARDEN_MAX_PLANTS; ++index) {
		assert(picosystem_garden_world_plant_seed(
			       &world,
			       (enum picosystem_garden_species_id)(index %
								   PICOSYSTEM_GARDEN_SPECIES_COUNT),
			       (uint8_t)(2U + (index * 3U))) == 0);
	}
	assert(world.plant_count == PICOSYSTEM_GARDEN_MAX_PLANTS);
	const struct picosystem_garden_world full = world;
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 27U) ==
	       -ENOSPC);
	assert(memcmp(&world, &full, sizeof(world)) == 0);
}

static void test_water_flow_and_light_competition(void)
{
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, 9U) == 0);
	assert(picosystem_garden_world_water(&world, 10U, 120U) == 0);
	const uint16_t initial_total = world.moisture_total;
	assert(initial_total > 0U);
	assert(picosystem_garden_world_water(&world, 10U, 0U) == -ERANGE);
	assert(picosystem_garden_world_water(&world, PICOSYSTEM_GARDEN_GRID_COLUMNS, 1U) ==
	       -ERANGE);
	for (uint32_t tick = 0U; tick < 180U; ++tick) {
		assert(picosystem_garden_world_step(&world) == 0);
	}
	assert(world.ecology_tick_count == 12U);
	assert(world.moisture[PICOSYSTEM_GARDEN_GRID_COLUMNS + 10U] > 0U);
	assert(world.moisture_total < initial_total);
}

static struct picosystem_garden_agent_observation
baseline_observation(enum picosystem_garden_node_kind kind)
{
	struct picosystem_garden_agent_observation observation = {
		.tip_index = 7U,
		.version = PICOSYSTEM_GARDEN_AGENT_OBSERVATION_VERSION,
		.plant_index = 0U,
		.species_id = PICOSYSTEM_GARDEN_SPECIES_FLOWER,
		.tissue_kind = (uint8_t)kind,
		.depth = 2U,
		.tip_x = 32U,
		.base_x = 32U,
		.maximum_depth = 10U,
		.candidate_count = (kind == PICOSYSTEM_GARDEN_NODE_STEM) ? 5U : 3U,
	};
	for (uint8_t index = 0U; index < observation.candidate_count; ++index) {
		observation.candidates[index].flags = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS |
						      PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE;
	}
	return observation;
}

static void test_agent_observation_and_baseline_policy(void)
{
	struct picosystem_garden_world world;
	struct picosystem_garden_agent_observation observation;
	const struct picosystem_garden_agent_observation empty_observation = {0};
	assert(picosystem_garden_agent_observe_tip(NULL, 0U, 0U, 0U, &observation) == -EINVAL);
	assert(memcmp(&observation, &empty_observation, sizeof(observation)) == 0);
	assert(picosystem_garden_world_reset(&world, UINT32_C(0x12345678)) == 0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 10U) ==
	       0);
	assert(picosystem_garden_agent_observe_tip(&world, 0U, 1U, UINT32_C(0x89abcdef), NULL) ==
	       -EINVAL);
	assert(picosystem_garden_agent_observe_tip(&world, 1U, 1U, 0U, &observation) == -ERANGE);
	assert(picosystem_garden_agent_observe_tip(&world, 0U, 4U, 0U, &observation) == -ERANGE);
	assert(picosystem_garden_agent_observe_tip(&world, 0U, 0U, 0U, &observation) == -ENOENT);
	assert(memcmp(&observation, &empty_observation, sizeof(observation)) == 0);

	assert(picosystem_garden_agent_observe_tip(&world, 0U, 1U, UINT32_C(0x89abcdef),
						   &observation) == 0);
	assert(observation.version == PICOSYSTEM_GARDEN_AGENT_OBSERVATION_VERSION);
	assert(observation.decision_nonce == UINT32_C(0x89abcdef));
	assert(observation.tip_index == 1U);
	assert(observation.tissue_kind == PICOSYSTEM_GARDEN_NODE_STEM);
	assert(observation.parent_delta_x == 0);
	assert(observation.parent_delta_y == -6);
	assert(observation.plant_node_count == 4U);
	assert(observation.shoot_node_count == 2U);
	assert(observation.root_node_count == 2U);
	assert(observation.leaf_node_count == 1U);
	assert(observation.active_tip_count == 3U);
	assert(observation.candidate_count == 5U);
	assert(observation.candidates[0].delta_x == -5);
	assert(observation.candidates[0].delta_y == -5);
	assert(observation.candidates[2].delta_x == 0);
	assert(observation.candidates[2].delta_y == -7);
	assert(observation.candidates[4].delta_x == 5);
	assert(observation.candidates[4].delta_y == -5);
	assert(observation.tip_light == UINT8_MAX);
	assert(observation.tip_moisture == 0U);
	assert(observation.candidates[2].light == UINT8_MAX);
	assert((observation.candidates[2].flags & PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE) !=
	       0U);

	assert(picosystem_garden_agent_observe_tip(&world, 0U, 2U, 1U, &observation) == 0);
	assert(observation.tissue_kind == PICOSYSTEM_GARDEN_NODE_ROOT);
	assert(observation.parent_delta_x == -3);
	assert(observation.parent_delta_y == 5);
	assert(observation.candidate_count == 3U);
	assert(observation.tip_light == 0U);
	assert(observation.tip_moisture == 0U);
	assert(observation.candidates[1].delta_x == 0);
	assert(observation.candidates[1].delta_y == 6);
	assert(observation.candidates[1].moisture == 0U);

	struct picosystem_garden_world crowded;
	assert(picosystem_garden_world_reset(&crowded, 7U) == 0);
	assert(picosystem_garden_world_plant_seed(&crowded, PICOSYSTEM_GARDEN_SPECIES_FLOWER,
						  10U) == 0);
	assert(picosystem_garden_world_plant_seed(&crowded, PICOSYSTEM_GARDEN_SPECIES_SHRUB, 14U) ==
	       0);
	crowded.nodes[5].x = crowded.nodes[1].x;
	crowded.nodes[5].y = (uint8_t)(crowded.nodes[1].y - 7U);
	assert(picosystem_garden_agent_observe_tip(&crowded, 0U, 1U, 0U, &observation) == 0);
	assert(observation.candidates[2].clearance_squared == 0U);
	assert((observation.candidates[2].flags & PICOSYSTEM_GARDEN_AGENT_CANDIDATE_FOREIGN_NEAR) !=
	       0U);
	assert((observation.candidates[2].flags & PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE) ==
	       0U);

	assert(picosystem_garden_world_reset(&crowded, 8U) == 0);
	assert(picosystem_garden_world_plant_seed(&crowded, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 0U) ==
	       0);
	assert(picosystem_garden_agent_observe_tip(&crowded, 0U, 1U, 0U, &observation) == 0);
	assert(observation.candidates[0].flags == 0U);

	struct picosystem_garden_agent_proposal proposal;
	assert(picosystem_garden_agent_baseline_propose(&observation, NULL) == -EINVAL);
	assert(picosystem_garden_agent_baseline_propose(NULL, &proposal) == -EINVAL);
	assert(proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT);
	assert(proposal.candidate_order[0] == PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE);

	observation = baseline_observation(PICOSYSTEM_GARDEN_NODE_STEM);
	for (uint8_t index = 0U; index < observation.candidate_count; ++index) {
		observation.candidates[index].light = (uint8_t)((index + 1U) * 8U);
	}
	assert(picosystem_garden_agent_baseline_propose(&observation, &proposal) == 0);
	assert(proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND);
	assert(proposal.priority == 5);
	const uint8_t expected_shoot_order[] = {4U, 0U, 1U, 2U, 3U};
	assert(memcmp(proposal.candidate_order, expected_shoot_order,
		      sizeof(expected_shoot_order)) == 0);

	observation.tip_flags = PICOSYSTEM_GARDEN_NODE_BRANCH_PENDING;
	observation.tip_x = (uint8_t)(observation.base_x + 1U);
	assert(picosystem_garden_agent_baseline_propose(&observation, &proposal) == 0);
	assert(proposal.candidate_order[0] == 0U);
	observation.depth = observation.maximum_depth;
	assert(picosystem_garden_agent_baseline_propose(&observation, &proposal) == 0);
	assert(proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP);
	assert(proposal.candidate_count == 0U);

	observation = baseline_observation(PICOSYSTEM_GARDEN_NODE_ROOT);
	observation.candidates[0].moisture = 10U;
	observation.candidates[1].moisture = 20U;
	observation.candidates[2].moisture = 20U;
	assert(picosystem_garden_agent_baseline_propose(&observation, &proposal) == 0);
	assert(proposal.priority == 20);
	const uint8_t expected_root_order[] = {2U, 0U, 1U};
	assert(memcmp(proposal.candidate_order, expected_root_order, sizeof(expected_root_order)) ==
	       0);

	observation.candidates[0].flags = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE;
	assert(picosystem_garden_agent_baseline_propose(&observation, &proposal) == -ERANGE);
	assert(proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT);
	observation.candidates[0].flags = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS |
					  PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE |
					  PICOSYSTEM_GARDEN_AGENT_CANDIDATE_OWN_NEAR;
	assert(picosystem_garden_agent_baseline_propose(&observation, &proposal) == -ERANGE);
	assert(proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT);
}

static void water_all_plants(struct picosystem_garden_world *world)
{
	for (uint8_t index = 0U; index < world->plant_count; ++index) {
		assert(picosystem_garden_world_water(world, world->plants[index].base_column,
						     96U) == 0);
	}
}

static void test_growth_variety_and_determinism(void)
{
	struct picosystem_garden_world left;
	struct picosystem_garden_world right;
	assert(picosystem_garden_world_reset(&left, UINT32_C(0xabcdef01)) == 0);
	assert(picosystem_garden_world_reset(&right, UINT32_C(0xabcdef01)) == 0);
	for (uint8_t species = 0U; species < PICOSYSTEM_GARDEN_SPECIES_COUNT; ++species) {
		const uint8_t column = (uint8_t)(4U + (species * 8U));
		assert(picosystem_garden_world_plant_seed(
			       &left, (enum picosystem_garden_species_id)species, column) == 0);
		assert(picosystem_garden_world_plant_seed(
			       &right, (enum picosystem_garden_species_id)species, column) == 0);
	}
	for (uint32_t tick = 0U; tick < 3600U; ++tick) {
		if ((tick % 240U) == 0U) {
			water_all_plants(&left);
			water_all_plants(&right);
		}
		assert(picosystem_garden_world_step(&left) == 0);
		assert(picosystem_garden_world_step(&right) == 0);
		assert(picosystem_garden_world_hash(&left) == picosystem_garden_world_hash(&right));
	}
	assert(left.node_count > 40U);
	assert(left.bloom_count > 0U);
	assert(left.plants[PICOSYSTEM_GARDEN_SPECIES_FLOWER].node_count !=
	       left.plants[PICOSYSTEM_GARDEN_SPECIES_SHRUB].node_count);
	assert(left.plants[PICOSYSTEM_GARDEN_SPECIES_SHRUB].node_count !=
	       left.plants[PICOSYSTEM_GARDEN_SPECIES_GROUND_COVER].node_count);
	printf("garden manual hash=%08x plants=%u nodes=%u blooms=%u water=%u\n",
	       picosystem_garden_world_hash(&left), left.plant_count, left.node_count,
	       (unsigned int)left.bloom_count, left.moisture_total);
}

static void test_cursor_tools_and_pruning(void)
{
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, 5U) == 0);
	assert(picosystem_garden_world_move_cursor(&world, -2, 0) == -ERANGE);
	for (uint8_t step = 0U; step < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++step) {
		assert(picosystem_garden_world_move_cursor(&world, -1, 0) == 0);
	}
	assert(world.cursor_column == 0U);
	assert(picosystem_garden_world_use_tool(&world) == 0);
	assert(world.manual_action_count == 1U);
	for (uint8_t tool = 0U; tool < PICOSYSTEM_GARDEN_TOOL_COUNT; ++tool) {
		assert(picosystem_garden_world_cycle_tool(&world) == 0);
	}
	assert(world.selected_tool == PICOSYSTEM_GARDEN_TOOL_FLOWER_SEED);

	const uint8_t start_column = world.cursor_column;
	assert(picosystem_garden_world_step_input(&world, 1, 0) == 0);
	assert(world.cursor_column == (uint8_t)(start_column + 1U));
	for (uint8_t tick = 0U; tick < PICOSYSTEM_GARDEN_CURSOR_REPEAT_DELAY_TICKS; ++tick) {
		assert(picosystem_garden_world_step_input(&world, 1, 0) == 0);
		assert(world.cursor_column == (uint8_t)(start_column + 1U));
	}
	assert(picosystem_garden_world_step_input(&world, 1, 0) == 0);
	assert(world.cursor_column == (uint8_t)(start_column + 2U));
	assert(picosystem_garden_world_step_input(&world, 2, 0) == -ERANGE);
	assert(picosystem_garden_world_step_input(&world, 0, 0) == 0);

	for (uint32_t tick = 0U; tick < 360U; ++tick) {
		if ((tick % 180U) == 0U) {
			assert(picosystem_garden_world_water(&world, 0U, 96U) == 0);
		}
		assert(picosystem_garden_world_step(&world) == 0);
	}
	uint16_t tip = PICOSYSTEM_GARDEN_NODE_NONE;
	for (uint16_t index = 0U; index < world.node_count; ++index) {
		if ((world.nodes[index].kind == PICOSYSTEM_GARDEN_NODE_STEM) &&
		    ((world.nodes[index].flags & PICOSYSTEM_GARDEN_NODE_TIP) != 0U)) {
			tip = index;
			break;
		}
	}
	assert(tip != PICOSYSTEM_GARDEN_NODE_NONE);
	const uint8_t column = (uint8_t)((world.nodes[tip].x - PICOSYSTEM_GARDEN_ORIGIN_X_PIXELS) /
					 PICOSYSTEM_GARDEN_CELL_PIXELS);
	const uint8_t row = (uint8_t)((world.nodes[tip].y - PICOSYSTEM_GARDEN_CANOPY_TOP_PIXELS) /
				      PICOSYSTEM_GARDEN_CELL_PIXELS);
	assert(picosystem_garden_world_prune(&world, column, row) == 0);
	assert((world.nodes[tip].flags & PICOSYSTEM_GARDEN_NODE_PRUNED) != 0U);
}

static void test_auto_gardener_long_soak(void)
{
	struct picosystem_garden_world left;
	struct picosystem_garden_world right;
	assert(picosystem_garden_world_reset(&left, UINT32_C(0x10203040)) == 0);
	assert(picosystem_garden_world_reset(&right, UINT32_C(0x10203040)) == 0);
	assert(picosystem_garden_world_set_auto_gardener(&left, true) == 0);
	assert(picosystem_garden_world_set_auto_gardener(&right, true) == 0);
	for (uint32_t tick = 0U; tick < 18000U; ++tick) {
		assert(picosystem_garden_world_step(&left) == 0);
		assert(picosystem_garden_world_step(&right) == 0);
		if ((tick % 120U) == 0U) {
			assert(picosystem_garden_world_hash(&left) ==
			       picosystem_garden_world_hash(&right));
		}
	}
	assert(left.plant_count >= 5U);
	assert(left.node_count <= PICOSYSTEM_GARDEN_MAX_NODES);
	assert(left.auto_action_count > 20U);
	assert(left.auto_decision_count > left.auto_action_count);
	assert(left.bloom_count > 0U);
	assert(left.moisture_total > 0U);
	assert(picosystem_garden_world_hash(&left) == picosystem_garden_world_hash(&right));
	printf("garden auto hash=%08x plants=%u nodes=%u blooms=%u actions=%u decisions=%u "
	       "water=%u\n",
	       picosystem_garden_world_hash(&left), left.plant_count, left.node_count,
	       (unsigned int)left.bloom_count, (unsigned int)left.auto_action_count,
	       (unsigned int)left.auto_decision_count, left.moisture_total);
}

static void test_pruning_rejects_distant_tip(void)
{
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, 5U) == 0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 1U) ==
	       0);
	/* This in-bounds tip is 65,540 squared pixels from the bottom-right cursor.
	 * A 16-bit distance would wrap to four and incorrectly accept the prune.
	 */
	world.nodes[1].x = 22U;
	world.nodes[1].y = 76U;
	const struct picosystem_garden_world unchanged = world;
	assert(picosystem_garden_world_prune(&world, 27U, 24U) == -ENOENT);
	assert(memcmp(&world, &unchanged, sizeof(world)) == 0);
}

int main(void)
{
	test_reset_and_validation();
	test_seed_spacing_capacity_and_access();
	test_water_flow_and_light_competition();
	test_agent_observation_and_baseline_policy();
	test_growth_variety_and_determinism();
	test_cursor_tools_and_pruning();
	test_pruning_rejects_distant_tip();
	test_auto_gardener_long_soak();
	return 0;
}
