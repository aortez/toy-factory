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
#include "garden_light.h"
#include "garden_world.h"

static uint16_t test_light_index(uint8_t column, uint8_t row)
{
	return (uint16_t)(((uint16_t)row * PICOSYSTEM_GARDEN_GRID_COLUMNS) + column);
}

static void test_seeded_rain_schedule(void)
{
	bool differs = false;
	for (uint32_t window = 0U; window < 256U; ++window) {
		uint32_t wet_ticks = 0U;
		uint32_t transitions = 0U;
		uint8_t previous = 0U;
		for (uint32_t phase = 0U; phase < PICOSYSTEM_GARDEN_RAIN_WINDOW_TICKS; ++phase) {
			const uint32_t tick = window * PICOSYSTEM_GARDEN_RAIN_WINDOW_TICKS + phase;
			const uint8_t rain = picosystem_garden_rain_at(123U, tick);
			assert(picosystem_garden_rain_at(0U, tick) == 0U);
			assert(rain == picosystem_garden_rain_at(123U, tick));
			assert((rain == 0U) ||
			       ((rain >= 2U) && (rain <= PICOSYSTEM_GARDEN_RAIN_MAX_RATE)));
			if ((phase < 8U) || (phase >= 120U)) {
				assert(rain == 0U);
			}
			wet_ticks += (rain != 0U) ? 1U : 0U;
			transitions += ((rain != 0U) != (previous != 0U)) ? 1U : 0U;
			differs |= rain != picosystem_garden_rain_at(124U, tick);
			previous = rain;
		}
		assert((wet_ticks >= 16U) && (wet_ticks <= 32U));
		assert(transitions == 2U);
	}
	assert(differs);
	assert(picosystem_garden_rain_at(UINT32_MAX, UINT32_MAX) == 0U);
}

static void test_rain_deposition_and_independence(void)
{
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_set_weather(NULL, 1U) == -EINVAL);
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	const uint32_t dry_hash = picosystem_garden_world_hash(&world);
	assert(picosystem_garden_world_set_weather(&world, 123U) == 0);
	assert(picosystem_garden_world_hash(&world) != dry_hash);
	assert(world.random_state == 123U);
	assert(picosystem_garden_world_set_weather(&world, 0U) == 0);
	assert(picosystem_garden_world_hash(&world) == dry_hash);
	assert(picosystem_garden_world_set_weather(&world, 123U) == 0);
	struct picosystem_garden_world crowded = world;
	assert(picosystem_garden_world_plant_seed(&crowded, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 4U) ==
	       0);
	assert(crowded.random_state != world.random_state);
	uint32_t offered = 0U;
	uint32_t evaporated = 0U;
	for (uint32_t tick = 1U; tick <= 7680U; ++tick) {
		const uint32_t before = world.rain_deposited;
		assert(picosystem_garden_world_step(&world) == 0);
		assert(picosystem_garden_world_step(&crowded) == 0);
		if ((tick % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) == 0U) {
			offered += (uint32_t)picosystem_garden_rain_at(123U,
								       world.ecology_tick_count) *
				   PICOSYSTEM_GARDEN_GRID_COLUMNS;
			if ((world.ecology_tick_count % 4U) == 0U) {
				/* Identical columns in an empty plot; rain never reaches
				 * saturation. */
				evaporated = offered - world.moisture_total;
			}
		} else {
			assert(world.rain_deposited == before);
		}
		assert(world.rain_deposited + world.rain_runoff == offered);
		assert(crowded.rain_deposited + crowded.rain_runoff == offered);
		assert(world.rain_runoff == 0U);
		assert(world.moisture_total + evaporated == offered);
		assert(world.auto_action_count == 0U);
		assert(world.manual_action_count == 0U);
	}
	assert(offered > 0U);
	assert(evaporated > 0U);
	assert(world.random_state == 123U);
	assert(world.moisture[PICOSYSTEM_GARDEN_GRID_COLUMNS] > 0U);

	/* At rain onset, deposit only at the surface; overflow is measured, not wrapped. */
	uint32_t wet_tick = 1U;
	while (picosystem_garden_rain_at(123U, wet_tick) == 0U) {
		++wet_tick;
	}
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	assert(picosystem_garden_world_set_weather(&world, 123U) == 0);
	world.ecology_tick_count = wet_tick - 1U;
	world.logic_tick_count = (wet_tick * PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) - 1U;
	const struct picosystem_garden_world empty = world;
	memset(world.moisture, UINT8_MAX, sizeof(world.moisture));
	world.moisture[0] = UINT8_MAX - 1U;
	assert(picosystem_garden_world_step(&world) == 0);
	assert(world.rain_deposited == 1U);
	assert(world.rain_runoff == (uint32_t)picosystem_garden_rain_at(123U, wet_tick) *
						    PICOSYSTEM_GARDEN_GRID_COLUMNS -
					    1U);
	struct picosystem_garden_world diagnostics = world;
	diagnostics.rain_deposited = UINT32_MAX;
	diagnostics.rain_runoff = UINT32_MAX;
	assert(picosystem_garden_world_hash(&world) == picosystem_garden_world_hash(&diagnostics));
	assert(picosystem_garden_world_step(&diagnostics) == 0);
	for (uint32_t tick = 0U; tick < PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR; ++tick) {
		assert(picosystem_garden_world_step(&diagnostics) == 0);
	}
	assert(diagnostics.rain_deposited == UINT32_MAX);
	assert(diagnostics.rain_runoff == UINT32_MAX);
	world = empty;
	assert(picosystem_garden_world_step(&world) == 0);
	const uint8_t rate = picosystem_garden_rain_at(123U, wet_tick);
	const uint8_t downward = (uint8_t)(rate / 4U);
	const uint8_t evaporation = ((wet_tick % 4U) == 0U) ? 1U : 0U;
	for (uint8_t column = 0U; column < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++column) {
		assert(world.moisture[column] == (uint8_t)(rate - downward - evaporation));
		assert(world.moisture[PICOSYSTEM_GARDEN_GRID_COLUMNS + column] == downward);
	}
	for (uint16_t index = 2U * PICOSYSTEM_GARDEN_GRID_COLUMNS;
	     index < PICOSYSTEM_GARDEN_SOIL_CELL_COUNT; ++index) {
		assert(world.moisture[index] == 0U);
	}
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	assert(world.weather_seed == 0U);
	assert(world.rain_deposited == 0U);
	assert(world.rain_runoff == 0U);
}

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
	const uint32_t initial_hash = picosystem_garden_world_hash(&world);
	assert(initial_hash != 0U);
	struct picosystem_garden_world diagnostics_only = world;
	diagnostics_only.agent_telemetry.decision_count = 1U;
	diagnostics_only.agent_telemetry.extend_count = 1U;
	diagnostics_only.agent_telemetry.shoot_decision_count = 1U;
	diagnostics_only.agent_telemetry.shoot_extend_count = 1U;
	diagnostics_only.agent_telemetry.last_action = PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND;
	assert(picosystem_garden_world_hash(&diagnostics_only) == initial_hash);
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
	const uint32_t planted_hash = picosystem_garden_world_hash(&world);
	struct picosystem_garden_world plant_diagnostics_only = world;
	plant_diagnostics_only.plants[0].agent_telemetry.decision_count = 1U;
	plant_diagnostics_only.plants[0].agent_telemetry.wait_count = 1U;
	plant_diagnostics_only.plants[0].agent_telemetry.last_action =
		PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT;
	assert(picosystem_garden_world_hash(&plant_diagnostics_only) == planted_hash);
	const struct picosystem_garden_world unchanged = world;
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_SHRUB, 4U) ==
	       -EEXIST);
	assert(memcmp(&world, &unchanged, sizeof(world)) == 0);
	assert(picosystem_garden_world_node_at(&world, 3U) != NULL);
	assert(picosystem_garden_world_node_at(&world, 4U) == NULL);
	assert(picosystem_garden_world_plant_at(&world, 0U) != NULL);
	assert(picosystem_garden_world_plant_at(&world, 1U) == NULL);
	assert(picosystem_garden_world_seed_at(&world, 0U) == NULL);

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

static void test_directional_light_solver(void)
{
	const struct picosystem_garden_sun noon = picosystem_garden_sun_at(0U);
	assert(noon.phase == PICOSYSTEM_GARDEN_SUN_NOON_PHASE);
	assert(noon.strength == UINT8_MAX);
	assert(noon.ray_step_x_q4 == 0);

	const struct picosystem_garden_sun sunset = picosystem_garden_sun_at(64U);
	assert(sunset.phase == PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE);
	assert(sunset.strength == PICOSYSTEM_GARDEN_LIGHT_MINIMUM);
	assert(sunset.ray_step_x_q4 == -PICOSYSTEM_GARDEN_SUN_MAX_RAY_STEP_X_Q4);
	const struct picosystem_garden_sun midnight = picosystem_garden_sun_at(128U);
	assert(midnight.phase == 192U);
	assert(midnight.strength == PICOSYSTEM_GARDEN_LIGHT_MINIMUM);
	assert(midnight.ray_step_x_q4 == 0);
	const struct picosystem_garden_sun sunrise = picosystem_garden_sun_at(192U);
	assert(sunrise.phase == 0U);
	assert(sunrise.strength == PICOSYSTEM_GARDEN_LIGHT_MINIMUM);
	assert(sunrise.ray_step_x_q4 == PICOSYSTEM_GARDEN_SUN_MAX_RAY_STEP_X_Q4);
	const struct picosystem_garden_sun morning = picosystem_garden_sun_at(224U);
	assert(morning.phase == 32U);
	assert(morning.strength == 140U);
	assert(morning.ray_step_x_q4 == 6);
	const struct picosystem_garden_sun repeated_noon = picosystem_garden_sun_at(256U);
	assert(repeated_noon.phase == noon.phase);
	assert(repeated_noon.strength == noon.strength);
	assert(repeated_noon.ray_step_x_q4 == noon.ray_step_x_q4);

	uint8_t shade[PICOSYSTEM_GARDEN_LIGHT_CELL_COUNT] = {0};
	uint8_t light[PICOSYSTEM_GARDEN_LIGHT_CELL_COUNT] = {0};
	assert(picosystem_garden_light_solve(NULL, &noon, light) == -EINVAL);
	assert(picosystem_garden_light_solve(shade, NULL, light) == -EINVAL);
	assert(picosystem_garden_light_solve(shade, &noon, NULL) == -EINVAL);
	assert(picosystem_garden_light_solve(light, &noon, light) == -EINVAL);
	struct picosystem_garden_sun invalid = noon;
	invalid.ray_step_x_q4 = PICOSYSTEM_GARDEN_SUN_MAX_RAY_STEP_X_Q4 + 1;
	assert(picosystem_garden_light_solve(shade, &invalid, light) == -ERANGE);
	invalid = noon;
	invalid.strength = PICOSYSTEM_GARDEN_LIGHT_MINIMUM - 1U;
	assert(picosystem_garden_light_solve(shade, &invalid, light) == -ERANGE);

	assert(picosystem_garden_light_solve(shade, &noon, light) == 0);
	for (uint16_t index = 0U; index < PICOSYSTEM_GARDEN_LIGHT_CELL_COUNT; ++index) {
		assert(light[index] == UINT8_MAX);
	}

	shade[test_light_index(5U, 1U)] = 100U;
	assert(picosystem_garden_light_solve(shade, &noon, light) == 0);
	assert(light[test_light_index(5U, 1U)] == UINT8_MAX);
	assert(light[test_light_index(5U, 2U)] == 155U);
	assert(light[test_light_index(5U, 3U)] == 155U);

	struct picosystem_garden_sun angled = noon;
	angled.ray_step_x_q4 = PICOSYSTEM_GARDEN_SUN_MAX_RAY_STEP_X_Q4;
	assert(picosystem_garden_light_solve(shade, &angled, light) == 0);
	assert(light[test_light_index(6U, 2U)] == 155U);
	assert(light[test_light_index(7U, 3U)] == 155U);
	assert(light[test_light_index(5U, 3U)] == UINT8_MAX);
	angled.ray_step_x_q4 = -PICOSYSTEM_GARDEN_SUN_MAX_RAY_STEP_X_Q4;
	assert(picosystem_garden_light_solve(shade, &angled, light) == 0);
	assert(light[test_light_index(4U, 2U)] == 155U);
	assert(light[test_light_index(3U, 3U)] == 155U);

	shade[test_light_index(5U, 1U)] = 250U;
	assert(picosystem_garden_light_solve(shade, &noon, light) == 0);
	assert(light[test_light_index(5U, 2U)] == PICOSYSTEM_GARDEN_LIGHT_MINIMUM);
	assert(picosystem_garden_light_solve(shade, &midnight, light) == 0);
	for (uint16_t index = 0U; index < PICOSYSTEM_GARDEN_LIGHT_CELL_COUNT; ++index) {
		assert(light[index] == PICOSYSTEM_GARDEN_LIGHT_MINIMUM);
	}
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
		.flower_depth = 6U,
		.candidate_count = (kind == PICOSYSTEM_GARDEN_NODE_STEM) ? 5U : 3U,
		.sun_phase = PICOSYSTEM_GARDEN_SUN_NOON_PHASE,
		.sun_strength = UINT8_MAX,
		.maintenance_energy_cost = 1U,
		.maintenance_water_cost = 1U,
	};
	for (uint8_t index = 0U; index < observation.candidate_count; ++index) {
		observation.candidates[index].flags = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS |
						      PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE;
	}
	return observation;
}

static int remembering_agent_decide(const struct picosystem_garden_agent_observation *observation,
				    const struct picosystem_garden_agent_memory *memory,
				    struct picosystem_garden_agent_decision *decision,
				    const void *context)
{
	if (context == NULL) {
		return -EINVAL;
	}
	const int err =
		picosystem_garden_agent_baseline_decide(observation, memory, decision, NULL);
	if (err != 0) {
		return err;
	}
	const int16_t next_value = (int16_t)memory->hidden[0] + *(const int8_t *)context;
	decision->next_memory.hidden[0] =
		(next_value < INT8_MIN) ? INT8_MIN
					: ((next_value > INT8_MAX) ? INT8_MAX : (int8_t)next_value);
	return 0;
}

static int invalid_agent_decide(const struct picosystem_garden_agent_observation *observation,
				const struct picosystem_garden_agent_memory *memory,
				struct picosystem_garden_agent_decision *decision,
				const void *context)
{
	(void)context;
	const int err =
		picosystem_garden_agent_baseline_decide(observation, memory, decision, NULL);
	if (err != 0) {
		return err;
	}
	++decision->proposal.tip_index;
	decision->next_memory.hidden[0] = 99;
	return 0;
}

static int failing_agent_decide(const struct picosystem_garden_agent_observation *observation,
				const struct picosystem_garden_agent_memory *memory,
				struct picosystem_garden_agent_decision *decision,
				const void *context)
{
	(void)context;
	const int err =
		picosystem_garden_agent_baseline_decide(observation, memory, decision, NULL);
	if (err != 0) {
		return err;
	}
	decision->next_memory.hidden[0] = 88;
	return -EIO;
}

static int highest_tip_agent_decide(const struct picosystem_garden_agent_observation *observation,
				    const struct picosystem_garden_agent_memory *memory,
				    struct picosystem_garden_agent_decision *decision,
				    const void *context)
{
	const int err =
		picosystem_garden_agent_baseline_decide(observation, memory, decision, NULL);
	if (err != 0) {
		return err;
	}
	if ((context != NULL) && (observation->tip_index == *(const uint16_t *)context)) {
		++decision->proposal.tip_index;
		decision->next_memory.hidden[0] = 99;
		return 0;
	}
	decision->proposal.priority = (int16_t)observation->tip_index;
	decision->next_memory.hidden[0] = (int8_t)observation->tip_index;
	decision->next_memory.hidden[1] = memory->hidden[0];
	return 0;
}

static uint32_t test_random_next(uint32_t state)
{
	state ^= state << 13U;
	state ^= state >> 17U;
	state ^= state << 5U;
	return state;
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
	assert(observation.sun_phase == PICOSYSTEM_GARDEN_SUN_NOON_PHASE);
	assert(observation.sun_strength == UINT8_MAX);
	assert(observation.sun_ray_step_x_q4 == 0);
	assert(observation.stress == 0U);
	assert(observation.maintenance_energy_cost == 1U);
	assert(observation.maintenance_water_cost == 1U);
	assert(observation.maintenance_phase == 0U);
	assert(observation.last_energy_income == 0U);
	assert(observation.last_water_income == 0U);
	assert(observation.plant_flags == 0U);
	assert(memcmp(&observation.genome, &world.plants[0].genome, sizeof(observation.genome)) ==
	       0);
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

	const struct picosystem_garden_agent_policy *const baseline_policy =
		picosystem_garden_agent_baseline_policy();
	assert(baseline_policy != NULL);
	assert(baseline_policy->decide == picosystem_garden_agent_baseline_decide);
	assert(baseline_policy->arbitration == PICOSYSTEM_GARDEN_AGENT_ARBITRATION_PHASED);
	const struct picosystem_garden_agent_memory memory = {
		.hidden = {3, -2, 1, 0, 4, -4, 2, -1},
	};
	struct picosystem_garden_agent_decision decision;
	assert(picosystem_garden_agent_decide(baseline_policy, &observation, &memory, NULL) ==
	       -EINVAL);
	assert(picosystem_garden_agent_decide(NULL, &observation, &memory, &decision) == -EINVAL);
	assert(decision.proposal.tip_index == observation.tip_index);
	assert(decision.proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT);
	assert(decision.proposal.candidate_order[0] == PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE);
	const struct picosystem_garden_agent_memory empty_memory = {0};
	assert(memcmp(&decision.next_memory, &empty_memory, sizeof(empty_memory)) == 0);
	assert(picosystem_garden_agent_decide(baseline_policy, NULL, &memory, &decision) ==
	       -EINVAL);
	assert(decision.proposal.tip_index == 0U);
	assert(picosystem_garden_agent_decide(baseline_policy, &observation, NULL, &decision) ==
	       -EINVAL);
	struct picosystem_garden_agent_observation invalid_observation = observation;
	invalid_observation.version = 0U;
	assert(picosystem_garden_agent_decide(baseline_policy, &invalid_observation, &memory,
					      &decision) == -ERANGE);
	assert(decision.proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT);
	assert(memcmp(&decision.next_memory, &empty_memory, sizeof(empty_memory)) == 0);
	assert(picosystem_garden_agent_decide(baseline_policy, &observation, &memory, &decision) ==
	       0);
	assert(memcmp(&decision.next_memory, &memory, sizeof(memory)) == 0);
	assert(decision.proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND);
	assert(memcmp(decision.proposal.candidate_order, expected_root_order,
		      sizeof(expected_root_order)) == 0);
	const struct picosystem_garden_agent_policy failing_policy = {
		.decide = failing_agent_decide,
	};
	assert(picosystem_garden_agent_decide(&failing_policy, &observation, &memory, &decision) ==
	       -EIO);
	assert(decision.proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT);
	assert(memcmp(&decision.next_memory, &empty_memory, sizeof(empty_memory)) == 0);

	observation.candidates[0].flags = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE;
	assert(picosystem_garden_agent_baseline_propose(&observation, &proposal) == -ERANGE);
	assert(proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT);
	observation.candidates[0].flags = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS |
					  PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE |
					  PICOSYSTEM_GARDEN_AGENT_CANDIDATE_OWN_NEAR;
	assert(picosystem_garden_agent_baseline_propose(&observation, &proposal) == -ERANGE);
	assert(proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT);
	observation.candidates[0].flags = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS |
					  PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE;
	observation.sun_strength = PICOSYSTEM_GARDEN_LIGHT_MINIMUM - 1U;
	assert(picosystem_garden_agent_baseline_propose(&observation, &proposal) == -ERANGE);
	assert(proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT);
	observation.sun_strength = UINT8_MAX;
	observation.stress = PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD;
	assert(picosystem_garden_agent_baseline_propose(&observation, &proposal) == -ERANGE);
	assert(proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT);
	observation.stress = 0U;
	observation.genome.growth_rate = PICOSYSTEM_GARDEN_GENOME_TRAIT_MAX + 1;
	assert(picosystem_garden_agent_baseline_propose(&observation, &proposal) == -ERANGE);
	assert(proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT);
}

static void test_adaptive_agent_policy(void)
{
	const struct picosystem_garden_agent_policy *const adaptive_policy =
		picosystem_garden_agent_adaptive_policy();
	assert(adaptive_policy != NULL);
	assert(adaptive_policy->decide == picosystem_garden_agent_adaptive_decide);
	assert(adaptive_policy->arbitration == PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS);

	const struct picosystem_garden_agent_memory empty_memory = {0};
	struct picosystem_garden_agent_observation shoot =
		baseline_observation(PICOSYSTEM_GARDEN_NODE_STEM);
	struct picosystem_garden_agent_observation root =
		baseline_observation(PICOSYSTEM_GARDEN_NODE_ROOT);
	shoot.leaf_node_count = 3U;
	root.leaf_node_count = shoot.leaf_node_count;
	shoot.stored_energy = 256U;
	shoot.stored_water = 41U;
	root.stored_energy = shoot.stored_energy;
	root.stored_water = shoot.stored_water;
	struct picosystem_garden_agent_decision shoot_decision;
	struct picosystem_garden_agent_decision root_decision;
	assert(picosystem_garden_agent_decide(adaptive_policy, &shoot, &empty_memory,
					      &shoot_decision) == 0);
	assert(picosystem_garden_agent_decide(adaptive_policy, &root, &empty_memory,
					      &root_decision) == 0);
	assert(root_decision.proposal.priority > shoot_decision.proposal.priority);
	assert(root_decision.next_memory.hidden[0] < 0);
	assert(root_decision.next_memory.hidden[1] > 0);
	assert(root_decision.next_memory.hidden[2] > 0);
	assert(root_decision.next_memory.hidden[7] > 0);

	shoot.stored_energy = 41U;
	shoot.stored_water = 512U;
	root.stored_energy = shoot.stored_energy;
	root.stored_water = shoot.stored_water;
	assert(picosystem_garden_agent_decide(adaptive_policy, &shoot, &empty_memory,
					      &shoot_decision) == 0);
	assert(picosystem_garden_agent_decide(adaptive_policy, &root, &empty_memory,
					      &root_decision) == 0);
	assert(shoot_decision.proposal.priority > root_decision.proposal.priority);
	assert(shoot_decision.next_memory.hidden[0] > 0);
	assert(shoot_decision.next_memory.hidden[1] < 0);
	assert(shoot_decision.next_memory.hidden[2] < 0);
	assert(shoot_decision.next_memory.hidden[7] < 0);

	shoot.stored_energy = 40U;
	shoot.sun_strength = 128U;
	assert(picosystem_garden_agent_decide(adaptive_policy, &shoot, &empty_memory,
					      &shoot_decision) == 0);
	assert(shoot_decision.proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT);
	assert(shoot_decision.proposal.candidate_count == 0U);

	shoot.depth = shoot.maximum_depth;
	assert(picosystem_garden_agent_decide(adaptive_policy, &shoot, &empty_memory,
					      &shoot_decision) == 0);
	assert(shoot_decision.proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP);
	assert(shoot_decision.proposal.candidate_count == 0U);
	assert(shoot_decision.proposal.priority > root_decision.proposal.priority);

	root = baseline_observation(PICOSYSTEM_GARDEN_NODE_ROOT);
	for (uint8_t index = 0U; index < root.candidate_count; ++index) {
		root.candidates[index].flags = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS;
	}
	assert(picosystem_garden_agent_decide(adaptive_policy, &root, &empty_memory,
					      &root_decision) == 0);
	assert(root_decision.proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP);
	assert(root_decision.proposal.candidate_count == 0U);
	assert(root_decision.proposal.candidate_order[0] == PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE);

	root = baseline_observation(PICOSYSTEM_GARDEN_NODE_ROOT);
	root.stored_energy = 256U;
	root.stored_water = 512U;
	struct picosystem_garden_agent_memory recurrent_memory = {0};
	for (uint8_t decision_index = 0U; decision_index < 32U; ++decision_index) {
		assert(picosystem_garden_agent_decide(adaptive_policy, &root, &recurrent_memory,
						      &root_decision) == 0);
		recurrent_memory = root_decision.next_memory;
	}
	assert(recurrent_memory.hidden[2] == 64);
	assert(recurrent_memory.hidden[7] == 8);
}

static void water_all_plants(struct picosystem_garden_world *world)
{
	for (uint8_t index = 0U; index < world->plant_count; ++index) {
		assert(picosystem_garden_world_water(world, world->plants[index].base_column,
						     96U) == 0);
	}
}

static void step_garden(struct picosystem_garden_world *world, uint32_t tick_count)
{
	for (uint32_t tick = 0U; tick < tick_count; ++tick) {
		assert(picosystem_garden_world_step(world) == 0);
	}
}

static void step_garden_with_policy(struct picosystem_garden_world *world, uint32_t tick_count,
				    const struct picosystem_garden_agent_policy *policy)
{
	for (uint32_t tick = 0U; tick < tick_count; ++tick) {
		assert(picosystem_garden_world_step_with_policy(world, policy) == 0);
	}
}

static void test_injected_agent_policy_memory_and_rejection(void)
{
	static const int8_t memory_increment = 1;
	const struct picosystem_garden_agent_policy remembering_policy = {
		.decide = remembering_agent_decide,
		.context = &memory_increment,
	};
	const struct picosystem_garden_agent_policy empty_policy = {0};
	struct picosystem_garden_world left;
	struct picosystem_garden_world right;
	struct picosystem_garden_world baseline;
	assert(picosystem_garden_world_reset(&left, UINT32_C(0xfeed1234)) == 0);
	assert(picosystem_garden_world_plant_seed(&left, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 14U) ==
	       0);
	right = left;
	baseline = left;
	const struct picosystem_garden_world unchanged = left;
	assert(picosystem_garden_world_step_with_policy(&left, NULL) == -EINVAL);
	assert(memcmp(&left, &unchanged, sizeof(left)) == 0);
	assert(picosystem_garden_world_step_with_policy(&left, &empty_policy) == -EINVAL);
	assert(memcmp(&left, &unchanged, sizeof(left)) == 0);

	for (uint8_t tick = 0U; tick < PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR; ++tick) {
		assert(picosystem_garden_world_step_with_policy(&left, &remembering_policy) == 0);
		assert(picosystem_garden_world_step_with_policy(&right, &remembering_policy) == 0);
		assert(picosystem_garden_world_step_with_policy(
			       &baseline, picosystem_garden_agent_baseline_policy()) == 0);
	}
	assert(left.plants[0].agent_memory.hidden[0] == memory_increment);
	assert(left.plants[0].agent_telemetry.decision_count == 1U);
	assert(left.agent_telemetry.decision_count == 1U);
	assert(memcmp(&left.plants[0].agent_memory, &right.plants[0].agent_memory,
		      sizeof(left.plants[0].agent_memory)) == 0);
	assert(picosystem_garden_world_hash(&left) == picosystem_garden_world_hash(&right));
	assert(picosystem_garden_world_hash(&left) != picosystem_garden_world_hash(&baseline));
	left.plants[0].agent_memory = (struct picosystem_garden_agent_memory){0};
	assert(memcmp(&left, &baseline, sizeof(left)) == 0);
	assert(picosystem_garden_world_hash(&left) == picosystem_garden_world_hash(&baseline));

	struct picosystem_garden_world rejected;
	assert(picosystem_garden_world_reset(&rejected, UINT32_C(0xfeed5678)) == 0);
	assert(picosystem_garden_world_plant_seed(&rejected, PICOSYSTEM_GARDEN_SPECIES_FLOWER,
						  14U) == 0);
	step_garden(&rejected, PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR - 1U);
	const uint32_t random_state = rejected.plants[0].random_state;
	const uint16_t shoot_tip_index = rejected.plants[0].last_shoot_tip_index;
	const uint16_t root_tip_index = rejected.plants[0].last_root_tip_index;
	const uint16_t node_count = rejected.node_count;
	const uint8_t growth_phase = rejected.plants[0].growth_phase;
	const struct picosystem_garden_agent_policy invalid_policy = {
		.decide = invalid_agent_decide,
	};
	assert(picosystem_garden_world_step_with_policy(&rejected, &invalid_policy) == -ERANGE);
	assert(rejected.plants[0].random_state == random_state);
	assert(rejected.plants[0].last_shoot_tip_index == shoot_tip_index);
	assert(rejected.plants[0].last_root_tip_index == root_tip_index);
	assert(rejected.plants[0].growth_phase == growth_phase);
	assert(rejected.node_count == node_count);
	const struct picosystem_garden_agent_memory empty_memory = {0};
	assert(memcmp(&rejected.plants[0].agent_memory, &empty_memory, sizeof(empty_memory)) == 0);
}

static void test_all_tip_arbitration_and_rejection(void)
{
	const struct picosystem_garden_agent_policy highest_tip_policy = {
		.decide = highest_tip_agent_decide,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS,
	};
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, UINT32_C(0x31415926)) == 0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 14U) ==
	       0);
	for (uint8_t tick = 0U; tick < PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR - 1U; ++tick) {
		assert(picosystem_garden_world_step_with_policy(&world, &highest_tip_policy) == 0);
	}
	const uint32_t random_state = world.plants[0].random_state;
	assert(picosystem_garden_world_step_with_policy(&world, &highest_tip_policy) == 0);
	assert(world.node_count == 5U);
	assert(world.nodes[4].parent_index == 3U);
	assert(world.plants[0].last_shoot_tip_index == PICOSYSTEM_GARDEN_NODE_NONE);
	assert(world.plants[0].last_root_tip_index == 3U);
	assert(world.plants[0].agent_memory.hidden[0] == 3);
	assert(world.plants[0].agent_memory.hidden[1] == 0);
	assert(world.plants[0].agent_telemetry.decision_count == 1U);
	assert(world.plants[0].agent_telemetry.extend_count == 1U);
	assert(world.plants[0].agent_telemetry.root_decision_count == 1U);
	assert(world.plants[0].agent_telemetry.shoot_decision_count == 0U);
	assert(world.plants[0].agent_telemetry.root_extend_count == 1U);
	assert(world.plants[0].agent_telemetry.shoot_extend_count == 0U);
	assert(world.plants[0].agent_telemetry.last_priority == 3);
	assert(world.plants[0].agent_telemetry.last_tip_x == world.nodes[3].x);
	assert(world.plants[0].agent_telemetry.last_tip_y == world.nodes[3].y);
	assert(world.plants[0].agent_telemetry.last_tip_depth == world.nodes[3].depth);
	assert(world.plants[0].agent_telemetry.last_tissue_kind == PICOSYSTEM_GARDEN_NODE_ROOT);
	assert(world.plants[0].agent_telemetry.last_action ==
	       PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND);
	assert(memcmp(&world.plants[0].agent_telemetry, &world.agent_telemetry,
		      sizeof(world.agent_telemetry)) == 0);
	assert(world.plants[0].random_state == test_random_next(random_state));
	assert(world.plants[0].growth_phase == 1U);

	assert(picosystem_garden_world_reset(&world, UINT32_C(0x27182818)) == 0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 14U) ==
	       0);
	for (uint8_t tick = 0U; tick < PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR - 1U; ++tick) {
		assert(picosystem_garden_world_step_with_policy(&world, &highest_tip_policy) == 0);
	}
	const uint16_t rejected_tip = 3U;
	const struct picosystem_garden_agent_policy rejecting_policy = {
		.decide = highest_tip_agent_decide,
		.context = &rejected_tip,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS,
	};
	const uint32_t rejected_random_state = world.plants[0].random_state;
	const uint16_t rejected_shoot_tip = world.plants[0].last_shoot_tip_index;
	const uint16_t rejected_root_tip = world.plants[0].last_root_tip_index;
	const uint16_t rejected_node_count = world.node_count;
	const uint8_t rejected_growth_phase = world.plants[0].growth_phase;
	const struct picosystem_garden_agent_memory rejected_memory = world.plants[0].agent_memory;
	const struct picosystem_garden_agent_telemetry rejected_plant_telemetry =
		world.plants[0].agent_telemetry;
	const struct picosystem_garden_agent_telemetry rejected_world_telemetry =
		world.agent_telemetry;
	assert(picosystem_garden_world_step_with_policy(&world, &rejecting_policy) == -ERANGE);
	assert(world.plants[0].random_state == rejected_random_state);
	assert(world.plants[0].last_shoot_tip_index == rejected_shoot_tip);
	assert(world.plants[0].last_root_tip_index == rejected_root_tip);
	assert(world.plants[0].growth_phase == rejected_growth_phase);
	assert(world.node_count == rejected_node_count);
	assert(memcmp(&world.plants[0].agent_memory, &rejected_memory, sizeof(rejected_memory)) ==
	       0);
	assert(memcmp(&world.plants[0].agent_telemetry, &rejected_plant_telemetry,
		      sizeof(rejected_plant_telemetry)) == 0);
	assert(memcmp(&world.agent_telemetry, &rejected_world_telemetry,
		      sizeof(rejected_world_telemetry)) == 0);

	const struct picosystem_garden_world unchanged = world;
	const struct picosystem_garden_agent_policy invalid_arbitration = {
		.decide = highest_tip_agent_decide,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_COUNT,
	};
	assert(picosystem_garden_world_step_with_policy(&world, &invalid_arbitration) == -EINVAL);
	assert(memcmp(&world, &unchanged, sizeof(world)) == 0);
}

static void test_survival_stress_decomposition_and_reclamation(void)
{
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, UINT32_C(0x5a17c0de)) == 0);
	assert(picosystem_garden_world_living_plant_count(NULL) == 0U);
	assert(picosystem_garden_world_dead_plant_count(NULL) == 0U);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 14U) ==
	       0);
	assert(picosystem_garden_world_water(&world, 14U, UINT8_MAX) == 0);
	step_garden(&world, 3U * PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE *
				    PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR / 2U);
	assert(world.ecology_tick_count == 192U);
	assert(picosystem_garden_world_living_plant_count(&world) == 1U);
	assert((world.plants[0].flags & PICOSYSTEM_GARDEN_PLANT_DEAD) == 0U);
	assert(world.plants[0].stored_energy > 0U);
	assert(world.plants[0].stress == 0U);
	assert(picosystem_garden_world_dead_plant_count(&world) == 0U);
	assert(world.death_count == 0U);

	/* A plant without photosynthetic tissue becomes stressed, then recovers. */
	assert(picosystem_garden_world_reset(&world, UINT32_C(0x1eed1e55)) == 0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 14U) ==
	       0);
	for (uint16_t index = 0U; index < world.node_count; ++index) {
		world.nodes[index].flags &= (uint8_t)~PICOSYSTEM_GARDEN_NODE_LEAF;
	}
	world.plants[0].stored_energy = 0U;
	world.plants[0].stored_water = 512U;
	step_garden(&world, PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR *
				    PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR);
	assert(world.plants[0].stress == 1U);
	assert((world.plants[0].flags & PICOSYSTEM_GARDEN_PLANT_ENERGY_SHORTAGE) != 0U);
	assert((world.plants[0].flags & PICOSYSTEM_GARDEN_PLANT_WATER_SHORTAGE) == 0U);
	world.plants[0].stored_energy = 64U;
	step_garden(&world, PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR *
				    PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR);
	assert(world.plants[0].stress == 0U);
	assert((world.plants[0].flags & (PICOSYSTEM_GARDEN_PLANT_ENERGY_SHORTAGE |
					 PICOSYSTEM_GARDEN_PLANT_WATER_SHORTAGE)) == 0U);
	assert(world.death_count == 0U);

	assert(picosystem_garden_world_reset(&world, UINT32_C(0x12344321)) == 0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 4U) ==
	       0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_SHRUB, 16U) ==
	       0);
	world.plants[0].stored_energy = 0U;
	world.plants[0].stored_water = 0U;
	world.plants[0].stress = PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD - 1U;
	step_garden(&world, PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR *
				    PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR);
	assert(world.death_count == 1U);
	assert(picosystem_garden_world_living_plant_count(&world) == 1U);
	assert(picosystem_garden_world_dead_plant_count(&world) == 1U);
	assert((world.plants[0].flags & PICOSYSTEM_GARDEN_PLANT_DEAD) != 0U);
	assert((world.plants[0].flags & PICOSYSTEM_GARDEN_PLANT_WATER_SHORTAGE) != 0U);
	assert(world.plants[0].last_shoot_tip_index == PICOSYSTEM_GARDEN_NODE_NONE);
	assert(world.plants[0].last_root_tip_index == PICOSYSTEM_GARDEN_NODE_NONE);
	for (uint16_t index = 0U; index < world.node_count; ++index) {
		if (world.nodes[index].plant_index == 0U) {
			assert((world.nodes[index].flags & PICOSYSTEM_GARDEN_NODE_TIP) == 0U);
		}
	}
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 4U) ==
	       -EEXIST);

	for (uint32_t tick = 0U; (tick < (PICOSYSTEM_GARDEN_SUN_CYCLE_TICKS *
					  PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR)) &&
				 (world.reclaimed_plant_count == 0U);
	     ++tick) {
		if ((tick % 120U) == 0U) {
			assert(picosystem_garden_world_water(&world, 16U, 96U) == 0);
		}
		assert(picosystem_garden_world_step(&world) == 0);
	}
	assert(world.reclaimed_plant_count == 1U);
	assert(world.reclaimed_node_count == 4U);
	assert(world.plant_count == 1U);
	assert(world.plants[0].species_id == PICOSYSTEM_GARDEN_SPECIES_SHRUB);
	assert(world.plants[0].base_column == 16U);
	assert(world.plants[0].base_node_index == 0U);
	assert(picosystem_garden_world_living_plant_count(&world) == 1U);
	assert(picosystem_garden_world_dead_plant_count(&world) == 0U);
	for (uint16_t index = 0U; index < world.node_count; ++index) {
		assert(world.nodes[index].plant_index == 0U);
		assert((world.nodes[index].parent_index == PICOSYSTEM_GARDEN_NODE_NONE) ||
		       (world.nodes[index].parent_index < index));
	}
	assert(picosystem_garden_world_hash(&world) != 0U);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 4U) ==
	       0);

	struct picosystem_garden_world churn;
	assert(picosystem_garden_world_reset(&churn, UINT32_C(0xabcdef12)) == 0);
	for (uint8_t cycle = 0U; cycle < 12U; ++cycle) {
		assert(picosystem_garden_world_plant_seed(
			       &churn, PICOSYSTEM_GARDEN_SPECIES_GROUND_COVER, 10U) == 0);
		churn.plants[0].stored_energy = 0U;
		churn.plants[0].stored_water = 0U;
		churn.plants[0].stress = PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD - 1U;
		step_garden(&churn, PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR *
					    PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR);
		assert(picosystem_garden_world_dead_plant_count(&churn) == 1U);
		for (uint32_t tick = 0U; (tick < (PICOSYSTEM_GARDEN_SUN_CYCLE_TICKS *
						  PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR)) &&
					 (churn.plant_count > 0U);
		     ++tick) {
			assert(picosystem_garden_world_step(&churn) == 0);
		}
		assert(churn.plant_count == 0U);
		assert(churn.node_count == 0U);
		assert(picosystem_garden_world_hash(&churn) != 0U);
	}
	assert(churn.death_count == 12U);
	assert(churn.reclaimed_plant_count == 12U);
	assert(churn.reclaimed_node_count == 48U);
}

static void make_plant_reproductive(struct picosystem_garden_world *world, uint8_t plant_index)
{
	struct picosystem_garden_plant *const plant = &world->plants[plant_index];
	plant->stored_energy = 256U;
	plant->stored_water = 512U;
	plant->growth_cooldown = UINT8_MAX;
	for (uint16_t index = 0U; index < world->node_count; ++index) {
		struct picosystem_garden_node *const node = &world->nodes[index];
		if ((node->plant_index != plant_index) ||
		    (node->kind != PICOSYSTEM_GARDEN_NODE_STEM) ||
		    (node->parent_index == PICOSYSTEM_GARDEN_NODE_NONE)) {
			continue;
		}
		node->flags &=
			(uint8_t)~(PICOSYSTEM_GARDEN_NODE_TIP | PICOSYSTEM_GARDEN_NODE_PRUNED |
				   PICOSYSTEM_GARDEN_NODE_BRANCH_PENDING);
		node->flags |= PICOSYSTEM_GARDEN_NODE_LEAF | PICOSYSTEM_GARDEN_NODE_FLOWER;
		node->growth_progress = UINT8_MAX;
		return;
	}
	assert(false);
}

/* Mature, non-growing tissue with no uptake: tests control both resource stores. */
static void make_reproduction_fixture(struct picosystem_garden_world *world, uint16_t node_count)
{
	assert((node_count >= 4U) && (node_count <= PICOSYSTEM_GARDEN_MAX_NODES));
	assert(picosystem_garden_world_reset(world, UINT32_C(0x51eed123)) == 0);
	assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_SHRUB, 14U) ==
	       0);
	make_plant_reproductive(world, 0U);
	for (uint16_t index = 0U; index < node_count; ++index) {
		if (index >= world->node_count) {
			world->nodes[index] = (struct picosystem_garden_node){
				.parent_index = 0U,
				.x = world->nodes[0].x,
				.y = world->nodes[0].y,
				.kind = PICOSYSTEM_GARDEN_NODE_STEM,
				.growth_progress = UINT8_MAX,
			};
		}
		world->nodes[index].flags = (index == 1U) ? PICOSYSTEM_GARDEN_NODE_FLOWER : 0U;
	}
	world->node_count = node_count;
	world->plants[0].node_count = node_count;
	assert(picosystem_garden_world_hash(world) != 0U);
}

static void test_reproduction_resource_limits(void)
{
	static const uint16_t node_counts[] = {4U, 40U, 41U, 57U, 59U, PICOSYSTEM_GARDEN_MAX_NODES};
	for (size_t index = 0U; index < (sizeof(node_counts) / sizeof(node_counts[0])); ++index) {
		for (int8_t trait = PICOSYSTEM_GARDEN_GENOME_TRAIT_MIN;
		     trait <= PICOSYSTEM_GARDEN_GENOME_TRAIT_MAX; ++trait) {
			struct picosystem_garden_world world;
			make_reproduction_fixture(&world, node_counts[index]);
			world.plants[0].genome.reserve_strategy = trait;
			step_garden(&world, PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR *
						    PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR);
			const uint16_t energy_upkeep = (uint16_t)((node_counts[index] + 7U) / 8U);
			const uint16_t water_upkeep =
				(uint16_t)((node_counts[index] - 2U + 7U) / 8U);
			assert(world.seed_creation_count == 1U);
			assert(world.seed_count == 1U);
			assert(world.plants[0].stored_energy == 256U - energy_upkeep - 48U);
			assert(world.plants[0].stored_water == 512U - water_upkeep - 24U);
			assert(world.node_count == node_counts[index]);
		}
	}

	static const struct {
		uint16_t nodes;
		uint16_t energy;
		uint16_t water;
		bool reproduces;
	} boundaries[] = {
		/* Small plants retain the existing 96-energy floor after the seed debit. */
		{4U, 145U, 512U, true},
		{4U, 144U, 512U, false},
		/* Large plants must reach full pre-upkeep stores at the clamped gate. */
		{57U, 256U, 512U, true},
		{57U, 255U, 512U, false},
		{256U, 256U, 512U, true},
		{256U, 256U, 511U, false},
	};
	for (size_t index = 0U; index < (sizeof(boundaries) / sizeof(boundaries[0])); ++index) {
		struct picosystem_garden_world world;
		make_reproduction_fixture(&world, boundaries[index].nodes);
		world.plants[0].stored_energy = boundaries[index].energy;
		world.plants[0].stored_water = boundaries[index].water;
		const uint32_t random_before = world.plants[0].random_state;
		step_garden(&world, PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR *
					    PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR);
		assert(world.seed_count == (boundaries[index].reproduces ? 1U : 0U));
		assert(((world.nodes[1].flags & PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED) != 0U) ==
		       boundaries[index].reproduces);
		if (!boundaries[index].reproduces) {
			assert(world.plants[0].random_state == random_before);
			assert(world.plants[0].reproduction_cooldown == 0U);
		}
	}

	struct picosystem_garden_world stressed;
	make_reproduction_fixture(&stressed, 57U);
	stressed.plants[0].stress = 2U;
	step_garden(&stressed, PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR *
				       PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR);
	assert(stressed.plants[0].stress == 1U);
	assert(stressed.seed_count == 0U);
}

static void fill_test_seed_bank(struct picosystem_garden_world *world)
{
	world->seed_count = PICOSYSTEM_GARDEN_MAX_SEEDS;
	world->seed_creation_count = PICOSYSTEM_GARDEN_MAX_SEEDS;
	for (uint8_t index = 0U; index < world->seed_count; ++index) {
		world->seeds[index] = (struct picosystem_garden_seed){
			.parent_lineage_id = world->plants[0].lineage_id,
			.generation = 1U,
			.column = world->plants[0].base_column,
			.species_id = world->plants[0].species_id,
		};
	}
}

static void test_flower_renewal_and_capacity(void)
{
	const uint32_t dawn_tick =
		PICOSYSTEM_GARDEN_SUN_CYCLE_TICKS - PICOSYSTEM_GARDEN_SUN_INITIAL_PHASE;
	struct picosystem_garden_world world;
	make_reproduction_fixture(&world, 4U);
	step_garden(&world, PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR *
				    PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR);
	assert(world.seed_creation_count == 1U);
	while (world.ecology_tick_count < dawn_tick - 1U) {
		world.plants[0].stored_energy = 256U;
		world.plants[0].stored_water = 512U;
		step_garden(&world, PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR);
		assert(world.seed_creation_count == 1U);
		assert((world.nodes[1].flags & PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED) != 0U);
	}
	/* Renewal itself neither spends resources nor reproduces in dawn darkness. */
	world.plants[0].stored_energy = 256U;
	world.plants[0].stored_water = 512U;
	step_garden(&world, PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR);
	assert((world.nodes[1].flags & PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED) == 0U);
	assert(world.seed_creation_count == 1U);
	assert(world.plants[0].stored_energy == 255U);
	assert(world.plants[0].stored_water == 511U);
	step_garden(&world, PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR *
				    PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR);
	assert(world.seed_creation_count == 2U);
	assert(world.plants[0].stored_energy == 206U);
	assert(world.plants[0].stored_water == 486U);
	assert(world.node_count == 4U);
	assert((world.nodes[1].flags & PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED) != 0U);
	for (uint32_t tick = 0U; tick < 32U; ++tick) {
		world.plants[0].stored_energy = 256U;
		world.plants[0].stored_water = 512U;
		step_garden(&world, PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR);
		assert(world.seed_creation_count == 2U);
	}

	/* Multiple renewed flowers still share the existing 16-ecology-step cooldown. */
	make_reproduction_fixture(&world, 5U);
	world.nodes[4].flags = PICOSYSTEM_GARDEN_NODE_FLOWER;
	step_garden(&world, 4U * PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR);
	assert(world.seed_creation_count == 1U);
	for (uint32_t tick = 0U; tick < 15U; ++tick) {
		world.plants[0].stored_energy = 256U;
		world.plants[0].stored_water = 512U;
		step_garden(&world, PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR);
		assert(world.seed_creation_count == 1U);
	}
	step_garden(&world, PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR);
	assert(world.seed_creation_count == 2U);

	/* A full bank preserves the renewed opportunity and RNG until space returns. */
	make_reproduction_fixture(&world, 4U);
	fill_test_seed_bank(&world);
	world.nodes[1].flags |= PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED;
	world.ecology_tick_count = dawn_tick - 1U;
	world.logic_tick_count = world.ecology_tick_count * PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR;
	const uint32_t random_before = world.plants[0].random_state;
	step_garden(&world, 5U * PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR);
	assert(world.seed_count == PICOSYSTEM_GARDEN_MAX_SEEDS);
	assert(world.seed_creation_count == PICOSYSTEM_GARDEN_MAX_SEEDS);
	assert(world.plants[0].stored_energy == 254U);
	assert(world.plants[0].stored_water == 510U);
	assert(world.plants[0].random_state == random_before);
	assert(world.plants[0].reproduction_cooldown == 0U);
	assert((world.nodes[1].flags & PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED) == 0U);
	--world.seed_count;
	step_garden(&world, 4U * PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR);
	assert(world.seed_count == PICOSYSTEM_GARDEN_MAX_SEEDS);
	assert(world.seed_creation_count == PICOSYSTEM_GARDEN_MAX_SEEDS + 1U);
	assert(world.plants[0].stored_energy == 205U);
	assert(world.plants[0].stored_water == 485U);
	assert((world.nodes[1].flags & PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED) != 0U);

	/* Dead flowers remain spent during decomposition, including at dawn. */
	make_reproduction_fixture(&world, 4U);
	world.nodes[1].flags |= PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED;
	world.plants[0].flags |= PICOSYSTEM_GARDEN_PLANT_DEAD;
	world.plants[0].stress = PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD;
	world.plants[0].stored_energy = 0U;
	world.plants[0].stored_water = 0U;
	world.ecology_tick_count = dawn_tick - 1U;
	world.logic_tick_count = world.ecology_tick_count * PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR;
	step_garden(&world, 5U * PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR);
	assert((world.nodes[1].flags & PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED) != 0U);
	assert(world.seed_creation_count == 0U);
}

static uint8_t genome_difference_count(const struct picosystem_garden_genome *left,
				       const struct picosystem_garden_genome *right)
{
	return (uint8_t)((left->growth_rate != right->growth_rate) +
			 (left->shoot_bias != right->shoot_bias) +
			 (left->light_seeking != right->light_seeking) +
			 (left->water_seeking != right->water_seeking) +
			 (left->branching != right->branching) + (left->stature != right->stature) +
			 (left->reserve_strategy != right->reserve_strategy) +
			 (left->dispersal != right->dispersal));
}

static void test_reproduction_germination_and_seed_expiration(void)
{
	const struct picosystem_garden_agent_policy *const baseline_policy =
		picosystem_garden_agent_baseline_policy();
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, UINT32_C(0x51eed123)) == 0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_SHRUB, 14U) ==
	       0);
	assert(world.plants[0].lineage_id == 1U);
	assert(world.plants[0].parent_lineage_id == 0U);
	assert(world.plants[0].generation == 0U);
	world.plants[0].agent_memory.hidden[0] = 42;
	make_plant_reproductive(&world, 0U);
	step_garden_with_policy(&world,
				PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR *
					PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR,
				baseline_policy);
	assert(world.seed_count == 1U);
	assert(world.seed_creation_count == 1U);
	assert(world.germination_count == 0U);
	const struct picosystem_garden_seed seed = world.seeds[0];
	assert(seed.parent_lineage_id == world.plants[0].lineage_id);
	assert(seed.generation == 1U);
	assert(seed.species_id == PICOSYSTEM_GARDEN_SPECIES_SHRUB);
	assert((seed.column <= 11U) || (seed.column >= 17U));
	assert((world.mutation_count == 0U) || (world.mutation_count == 1U));
	assert(genome_difference_count(&world.plants[0].genome, &seed.genome) ==
	       world.mutation_count);
	assert(picosystem_garden_world_seed_at(&world, 0U) != NULL);
	assert(picosystem_garden_world_seed_at(&world, 1U) == NULL);
	uint8_t blockers = 0U;
	assert(picosystem_garden_world_seed_germination_blockers(NULL, 0U, &blockers) == -EINVAL);
	assert(picosystem_garden_world_seed_germination_blockers(&world, 0U, NULL) == -EINVAL);
	assert(picosystem_garden_world_seed_germination_blockers(&world, 1U, &blockers) == -ERANGE);
	assert(picosystem_garden_world_seed_germination_blockers(&world, 0U, &blockers) == 0);
	assert((blockers & PICOSYSTEM_GARDEN_SEED_BLOCKED_DORMANT) != 0U);
	assert((blockers & (uint8_t)~PICOSYSTEM_GARDEN_SEED_VALID_BLOCKERS) == 0U);

	struct picosystem_garden_world environmental_block = world;
	environmental_block.seeds[0].age_ecology_ticks = PICOSYSTEM_GARDEN_SEED_DORMANCY_TICKS;
	memset(environmental_block.moisture, 0, sizeof(environmental_block.moisture));
	memset(environmental_block.light, 0, sizeof(environmental_block.light));
	environmental_block.seeds[0].column = environmental_block.plants[0].base_column;
	assert(picosystem_garden_world_seed_germination_blockers(&environmental_block, 0U,
								 &blockers) == 0);
	assert((blockers & PICOSYSTEM_GARDEN_SEED_BLOCKED_DORMANT) == 0U);
	assert((blockers & PICOSYSTEM_GARDEN_SEED_BLOCKED_MOISTURE) != 0U);
	assert((blockers & PICOSYSTEM_GARDEN_SEED_BLOCKED_LIGHT) != 0U);
	assert((blockers & PICOSYSTEM_GARDEN_SEED_BLOCKED_SPACING) != 0U);

	struct picosystem_garden_world capacity_block = world;
	static const uint8_t extra_columns[] = {0U, 3U, 6U, 9U, 18U, 21U, 24U};
	for (size_t index = 0U; index < (sizeof(extra_columns) / sizeof(extra_columns[0]));
	     ++index) {
		assert(picosystem_garden_world_plant_seed(&capacity_block,
							  PICOSYSTEM_GARDEN_SPECIES_FLOWER,
							  extra_columns[index]) == 0);
	}
	assert(capacity_block.plant_count == PICOSYSTEM_GARDEN_MAX_PLANTS);
	assert(picosystem_garden_world_seed_germination_blockers(&capacity_block, 0U, &blockers) ==
	       0);
	assert((blockers & PICOSYSTEM_GARDEN_SEED_BLOCKED_PLANT_CAPACITY) != 0U);
	const uint16_t target_node_count = PICOSYSTEM_GARDEN_MAX_NODES - 3U;
	const uint16_t appended_node_count = target_node_count - capacity_block.node_count;
	for (uint16_t index = capacity_block.node_count; index < target_node_count; ++index) {
		capacity_block.nodes[index] = (struct picosystem_garden_node){
			.parent_index = capacity_block.plants[0].base_node_index,
			.plant_index = 0U,
			.kind = PICOSYSTEM_GARDEN_NODE_STEM,
		};
	}
	capacity_block.node_count = target_node_count;
	capacity_block.plants[0].node_count =
		(uint16_t)(capacity_block.plants[0].node_count + appended_node_count);
	assert(picosystem_garden_world_seed_germination_blockers(&capacity_block, 0U, &blockers) ==
	       0);
	assert((blockers & PICOSYSTEM_GARDEN_SEED_BLOCKED_NODE_CAPACITY) != 0U);

	for (uint16_t age = 0U; age < PICOSYSTEM_GARDEN_SEED_DORMANCY_TICKS; ++age) {
		assert(picosystem_garden_world_water(&world, seed.column, UINT8_MAX) == 0);
		step_garden_with_policy(&world, PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR,
					baseline_policy);
	}
	assert(world.seed_count == 0U);
	assert(world.germination_count == 1U);
	assert(world.plant_count == 2U);
	assert(world.maximum_generation == 1U);
	assert(world.plants[0].offspring_count == 1U);
	assert(world.plants[1].lineage_id == 2U);
	assert(world.plants[1].parent_lineage_id == world.plants[0].lineage_id);
	assert(world.plants[1].generation == 1U);
	assert(memcmp(&world.plants[1].genome, &seed.genome, sizeof(seed.genome)) == 0);
	const struct picosystem_garden_agent_memory empty_memory = {0};
	assert(memcmp(&world.plants[1].agent_memory, &empty_memory, sizeof(empty_memory)) == 0);
	assert(world.plants[0].agent_memory.hidden[0] == 42);
	assert(picosystem_garden_world_hash(&world) != 0U);

	assert(picosystem_garden_world_reset(&world, UINT32_C(0x51eed123)) == 0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_SHRUB, 14U) ==
	       0);
	make_plant_reproductive(&world, 0U);
	step_garden_with_policy(&world,
				PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR *
					PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR,
				baseline_policy);
	assert(world.seed_count == 1U);
	world.seeds[0].age_ecology_ticks = PICOSYSTEM_GARDEN_SEED_LIFETIME_TICKS - 1U;
	step_garden_with_policy(&world, PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR, baseline_policy);
	assert(world.seed_count == 0U);
	assert(world.germination_count == 0U);
	assert(world.seed_expiration_count == 1U);
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
	assert(left.death_count == 0U);
	assert(left.plants[PICOSYSTEM_GARDEN_SPECIES_FLOWER].node_count !=
	       left.plants[PICOSYSTEM_GARDEN_SPECIES_SHRUB].node_count);
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
	assert(picosystem_garden_world_living_plant_count(&left) >= 5U);
	assert(left.node_count <= PICOSYSTEM_GARDEN_MAX_NODES);
	assert(left.auto_action_count > 20U);
	assert(left.auto_decision_count > left.auto_action_count);
	assert(left.bloom_count > 0U);
	assert(left.moisture_total > 0U);
	assert(picosystem_garden_world_hash(&left) == picosystem_garden_world_hash(&right));
	printf("garden auto hash=%08x plants=%u nodes=%u blooms=%u deaths=%u generations=%u "
	       "actions=%u decisions=%u water=%u\n",
	       picosystem_garden_world_hash(&left), left.plant_count, left.node_count,
	       (unsigned int)left.bloom_count, (unsigned int)left.death_count,
	       (unsigned int)left.maximum_generation, (unsigned int)left.auto_action_count,
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
	test_seeded_rain_schedule();
	test_rain_deposition_and_independence();
	test_reset_and_validation();
	test_seed_spacing_capacity_and_access();
	test_water_flow_and_light_competition();
	test_directional_light_solver();
	test_agent_observation_and_baseline_policy();
	test_adaptive_agent_policy();
	test_injected_agent_policy_memory_and_rejection();
	test_all_tip_arbitration_and_rejection();
	test_survival_stress_decomposition_and_reclamation();
	test_reproduction_germination_and_seed_expiration();
	test_reproduction_resource_limits();
	test_flower_renewal_and_capacity();
	test_growth_variety_and_determinism();
	test_cursor_tools_and_pruning();
	test_pruning_rejects_distant_tip();
	test_auto_gardener_long_soak();
	return 0;
}
