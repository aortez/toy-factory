/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "garden_evaluation.h"

#include <errno.h>
#include <stddef.h>
#include <stdint.h>

const struct toy_factory_garden_evaluation_scenario
	toy_factory_garden_evaluation_scenarios[TOY_FACTORY_GARDEN_EVALUATION_SCENARIO_COUNT] = {
		{
			.name = "unassisted",
			.initial_water = 128U,
			.plant_count = 3U,
			.columns = {4U, 13U, 22U},
			.species =
				{
					PICOSYSTEM_GARDEN_SPECIES_FLOWER,
					PICOSYSTEM_GARDEN_SPECIES_SHRUB,
					PICOSYSTEM_GARDEN_SPECIES_GROUND_COVER,
				},
		},
		{
			.name = "irrigated",
			.irrigation_period_ticks = 960U,
			.initial_water = 128U,
			.irrigation_water = 8U,
			.plant_count = 3U,
			.columns = {4U, 13U, 22U},
			.species =
				{
					PICOSYSTEM_GARDEN_SPECIES_FLOWER,
					PICOSYSTEM_GARDEN_SPECIES_SHRUB,
					PICOSYSTEM_GARDEN_SPECIES_GROUND_COVER,
				},
		},
		{
			.name = "crowded",
			.irrigation_period_ticks = 960U,
			.initial_water = 96U,
			.irrigation_water = 8U,
			.plant_count = 5U,
			.columns = {3U, 8U, 13U, 18U, 23U},
			.species =
				{
					PICOSYSTEM_GARDEN_SPECIES_FLOWER,
					PICOSYSTEM_GARDEN_SPECIES_SHRUB,
					PICOSYSTEM_GARDEN_SPECIES_GROUND_COVER,
					PICOSYSTEM_GARDEN_SPECIES_SHRUB,
					PICOSYSTEM_GARDEN_SPECIES_FLOWER,
				},
		},
};

const struct toy_factory_garden_evaluation_scenario
	toy_factory_garden_rainfed_scenarios[TOY_FACTORY_GARDEN_RAINFED_SCENARIO_COUNT] = {
		{
			.name = "rainfed",
			.initial_water = 128U,
			.plant_count = 3U,
			.columns = {4U, 13U, 22U},
			.species = {PICOSYSTEM_GARDEN_SPECIES_FLOWER,
				    PICOSYSTEM_GARDEN_SPECIES_SHRUB,
				    PICOSYSTEM_GARDEN_SPECIES_GROUND_COVER},
			.rain_enabled = true,
		},
		{
			.name = "rainfed-crowded",
			.initial_water = 96U,
			.plant_count = 5U,
			.columns = {3U, 8U, 13U, 18U, 23U},
			.species = {PICOSYSTEM_GARDEN_SPECIES_FLOWER,
				    PICOSYSTEM_GARDEN_SPECIES_SHRUB,
				    PICOSYSTEM_GARDEN_SPECIES_GROUND_COVER,
				    PICOSYSTEM_GARDEN_SPECIES_SHRUB,
				    PICOSYSTEM_GARDEN_SPECIES_FLOWER},
			.rain_enabled = true,
		},
};

static int irrigate(struct picosystem_garden_world *world, uint8_t amount)
{
	/* Exogenous input must not scale with a policy's current plants or seeds. */
	for (uint8_t column = 0U; column < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++column) {
		const int err = picosystem_garden_world_water(world, column, amount);
		if (err != 0) {
			return err;
		}
	}
	return 0;
}

static bool plant_has_active_leaf(const struct picosystem_garden_world *world, uint8_t plant_index)
{
	for (uint16_t index = 0U; index < world->node_count; ++index) {
		const struct picosystem_garden_node *const node = &world->nodes[index];
		if ((node->plant_index == plant_index) &&
		    ((node->flags & PICOSYSTEM_GARDEN_NODE_LEAF) != 0U) &&
		    (node->growth_progress >= PICOSYSTEM_GARDEN_LEAF_ACTIVE_PROGRESS)) {
			return true;
		}
	}
	return false;
}

uint32_t toy_factory_garden_evaluation_trial_seed(uint32_t base_seed, uint32_t trial_index)
{
	uint32_t value = base_seed ^ ((trial_index + 1U) * UINT32_C(0x9e3779b9));
	value ^= value << 13U;
	value ^= value >> 17U;
	value ^= value << 5U;
	return (value == 0U) ? TOY_FACTORY_GARDEN_EVALUATION_DEFAULT_SEED : value;
}

int toy_factory_garden_evaluation_reset(
	struct picosystem_garden_world *world,
	const struct toy_factory_garden_evaluation_scenario *scenario, uint32_t random_seed)
{
	if ((world == NULL) || (scenario == NULL)) {
		return -EINVAL;
	}
	if ((scenario->name == NULL) || (scenario->plant_count == 0U) ||
	    (scenario->plant_count > TOY_FACTORY_GARDEN_EVALUATION_MAX_PLANTS)) {
		return -ERANGE;
	}

	int err = picosystem_garden_world_reset(world, random_seed);
	if ((err == 0) && scenario->rain_enabled) {
		/* Capture the reset seed before founder creation consumes world randomness. */
		err = picosystem_garden_world_set_weather(world, world->random_state);
	}
	for (uint8_t index = 0U; (err == 0) && (index < scenario->plant_count); ++index) {
		if (scenario->species[index] >= PICOSYSTEM_GARDEN_SPECIES_COUNT) {
			return -ERANGE;
		}
		err = picosystem_garden_world_plant_seed(
			world, (enum picosystem_garden_species_id)scenario->species[index],
			scenario->columns[index]);
	}
	for (uint8_t index = 0U; (err == 0) && (index < world->plant_count); ++index) {
		err = picosystem_garden_world_water(world, world->plants[index].base_column,
						    scenario->initial_water);
	}
	return err;
}

int toy_factory_garden_evaluation_advance(
	struct picosystem_garden_world *world,
	const struct toy_factory_garden_evaluation_scenario *scenario,
	const struct picosystem_garden_agent_policy *policy, uint32_t tick_count,
	toy_factory_garden_evaluation_observer_fn observer, void *observer_context)
{
	if ((world == NULL) || (scenario == NULL) || (policy == NULL)) {
		return -EINVAL;
	}
	for (uint32_t index = 0U; index < tick_count; ++index) {
		const uint32_t tick = world->logic_tick_count;
		if ((scenario->irrigation_period_ticks != 0U) && (tick != 0U) &&
		    ((tick % scenario->irrigation_period_ticks) == 0U)) {
			const int err = irrigate(world, scenario->irrigation_water);
			if (err != 0) {
				return err;
			}
		}
		int err = picosystem_garden_world_step_with_policy(world, policy);
		if (err != 0) {
			return err;
		}
		if (observer != NULL) {
			const bool ecology_sample = (world->logic_tick_count %
						     PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) == 0U;
			err = observer(world, ecology_sample, observer_context);
			if (err != 0) {
				return err;
			}
		}
	}
	return 0;
}

bool toy_factory_garden_evaluation_plant_is_established(const struct picosystem_garden_world *world,
							uint8_t plant_index)
{
	if ((world == NULL) || (plant_index >= world->plant_count)) {
		return false;
	}
	const struct picosystem_garden_plant *const plant = &world->plants[plant_index];
	return (plant->generation > 0U) && ((plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) == 0U) &&
	       (plant->stress == 0U) &&
	       (plant->age_ecology_ticks >= TOY_FACTORY_GARDEN_ESTABLISHED_MINIMUM_AGE) &&
	       plant_has_active_leaf(world, plant_index);
}
