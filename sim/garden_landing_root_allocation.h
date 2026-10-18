/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_LANDING_ROOT_ALLOCATION_H_
#define TOY_FACTORY_GARDEN_LANDING_ROOT_ALLOCATION_H_

#include "garden_landing_root_choice.h"

/* Immutable host-only diagnostic selector. Zero initialization disables it.
 * The selector is independent of the all-offspring spending guard scope.
 */
struct toy_factory_garden_root_allocation {
	uint32_t version;
	uint32_t lineage;
	uint32_t birth_tick;
	uint32_t parent;
	uint32_t generation;
	uint32_t column;
	uint32_t species;
};

#define TOY_FACTORY_GARDEN_ROOT_ALLOCATION_FOCAL                                                   \
	{                                                                                          \
		.version = 1U, .lineage = 9U, .birth_tick = 403365U, .parent = 4U,                 \
		.generation = 1U, .column = 24U, .species = PICOSYSTEM_GARDEN_SPECIES_SHRUB        \
	}

struct toy_factory_garden_root_allocation_receipt {
	bool active;
	bool eligible;
	bool prefer;
};

int toy_factory_garden_root_allocation_validate(
	const struct toy_factory_garden_root_allocation *config,
	const struct toy_factory_garden_root_choice *guards, uint8_t budget_mode);

/* Pure priority adjustment. No destination search, memory update or random draw.
 * An optional receipt is published only on success, as is the decision.
 * A matching lineage/birth with unexpected ancestry/site is an error, not a
 * different individual silently receiving treatment.
 */
int toy_factory_garden_root_allocation_apply(
	const struct picosystem_garden_world *world,
	const struct picosystem_garden_agent_observation *observation,
	const struct toy_factory_garden_root_allocation *config,
	const struct toy_factory_garden_root_choice *guards, uint8_t budget_mode,
	struct picosystem_garden_agent_decision *decision,
	struct toy_factory_garden_root_allocation_receipt *receipt);

#endif
