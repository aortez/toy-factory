/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef TOY_FACTORY_GARDEN_EVALUATION_H_
#define TOY_FACTORY_GARDEN_EVALUATION_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "garden_agent.h"
#include "garden_world.h"

#define TOY_FACTORY_GARDEN_EVALUATION_DEFAULT_SEED         UINT32_C(0x6576616c)
#define TOY_FACTORY_GARDEN_EVALUATION_MAX_PLANTS           5U
#define TOY_FACTORY_GARDEN_EVALUATION_SCENARIO_COUNT       3U
#define TOY_FACTORY_GARDEN_EVALUATION_MAX_TRACKED_LINEAGES 4096U

#define TOY_FACTORY_GARDEN_ESTABLISHED_MINIMUM_AGE (PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR + 1U)

struct toy_factory_garden_evaluation_scenario {
	const char *name;
	uint32_t irrigation_period_ticks;
	uint8_t initial_water;
	uint8_t irrigation_water;
	uint8_t plant_count;
	uint8_t columns[TOY_FACTORY_GARDEN_EVALUATION_MAX_PLANTS];
	uint8_t species[TOY_FACTORY_GARDEN_EVALUATION_MAX_PLANTS];
};

typedef int (*toy_factory_garden_evaluation_observer_fn)(
	const struct picosystem_garden_world *world, bool ecology_sample, void *context);

extern const struct toy_factory_garden_evaluation_scenario
	toy_factory_garden_evaluation_scenarios[TOY_FACTORY_GARDEN_EVALUATION_SCENARIO_COUNT];

/* Derive one stable nonzero world seed from a batch seed and trial index. */
uint32_t toy_factory_garden_evaluation_trial_seed(uint32_t base_seed, uint32_t trial_index);

/* Reset the world and apply a scenario's plants and initial water. */
int toy_factory_garden_evaluation_reset(
	struct picosystem_garden_world *world,
	const struct toy_factory_garden_evaluation_scenario *scenario, uint32_t random_seed);

/* Advance an initialized scenario, observing each completed authoritative tick. */
int toy_factory_garden_evaluation_advance(
	struct picosystem_garden_world *world,
	const struct toy_factory_garden_evaluation_scenario *scenario,
	const struct picosystem_garden_agent_policy *policy, uint32_t tick_count,
	toy_factory_garden_evaluation_observer_fn observer, void *observer_context);

/* Shared offspring-quality definition used by reports and evolutionary fitness. */
bool toy_factory_garden_evaluation_plant_is_established(const struct picosystem_garden_world *world,
							uint8_t plant_index);

#endif /* TOY_FACTORY_GARDEN_EVALUATION_H_ */
