/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_SEEDLING_RESERVE_H_
#define TOY_FACTORY_GARDEN_SEEDLING_RESERVE_H_

#include "garden_reserve_policy.h"

#if defined(__ZEPHYR__)
#error "Seedling reserve is an explicit host-only diagnostic"
#endif

#define TOY_FACTORY_GARDEN_SEEDLING_RESERVE_NAME "seedling-maintenance-reserve-v1"

enum toy_factory_garden_seedling_component {
	TOY_FACTORY_GARDEN_SEEDLING_BOTH,
	TOY_FACTORY_GARDEN_SEEDLING_ENERGY,
	TOY_FACTORY_GARDEN_SEEDLING_WATER,
};

struct toy_factory_garden_seedling_reserve_forecast {
	struct toy_factory_garden_reserve_forecast energy;
	uint32_t water_cost;
	uint32_t water_upkeep;
	uint32_t water_reserve;
	uint8_t destination;
	bool wet_root;
	bool water_allowed;
	bool allowed;
};

/* Only cohort selection sees the world; the forecast uses the local observation.
 * Caller owns the immutable context/base for the policy's entire lifetime.
 */
struct toy_factory_garden_seedling_reserve_context {
	const struct picosystem_garden_agent_policy *base;
	const struct picosystem_garden_world *world;
	uint32_t lineage;
	enum toy_factory_garden_seedling_component component;
	bool all_offspring;
};

/* Invalid names leave output unchanged; invalid values have no name. */
int toy_factory_garden_seedling_component_parse(
	const char *name, enum toy_factory_garden_seedling_component *component);
const char *
toy_factory_garden_seedling_component_name(enum toy_factory_garden_seedling_component component);

/* Forecast always contains both tests; select the enforced component here.
 * Invalid arguments fail closed. No thresholds depend on the selection.
 */
bool toy_factory_garden_seedling_reserve_allows(
	const struct toy_factory_garden_seedling_reserve_forecast *forecast,
	enum toy_factory_garden_seedling_component component);

bool toy_factory_garden_seedling_reserve_active(
	const struct toy_factory_garden_seedling_reserve_context *context,
	const struct picosystem_garden_agent_observation *observation);

/* Pure forecast; malformed input leaves output unchanged. Candidate order must
 * be the full base-policy permutation for EXTEND, empty for WAIT/FINISH.
 */
int toy_factory_garden_seedling_reserve_forecast(
	const struct picosystem_garden_agent_observation *observation,
	const struct picosystem_garden_agent_proposal *proposal,
	struct toy_factory_garden_seedling_reserve_forecast *forecast);

/* Lineage zero disables the adapter. Only offspring ages 1..256 are eligible.
 * Vetoes clear candidate order but preserve priority, arbitration and memory.
 * Errors leave both output objects unchanged.
 */
int toy_factory_garden_seedling_reserve_init(
	const struct picosystem_garden_agent_policy *base,
	const struct picosystem_garden_world *world, uint32_t lineage,
	enum toy_factory_garden_seedling_component component,
	struct toy_factory_garden_seedling_reserve_context *context,
	struct picosystem_garden_agent_policy *policy);

/* Explicit population experiment: the same age window and combined forecast,
 * without selecting individual lineages. Founders are never eligible.
 * Errors leave both output objects unchanged, as with the named initializer.
 */
int toy_factory_garden_seedling_reserve_offspring_init(
	const struct picosystem_garden_agent_policy *base,
	const struct picosystem_garden_world *world,
	struct toy_factory_garden_seedling_reserve_context *context,
	struct picosystem_garden_agent_policy *policy);

#endif
