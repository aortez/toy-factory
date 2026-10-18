/* SPDX-License-Identifier: Apache-2.0 */
#include <errno.h>
#include <string.h>

#include "garden_seedling_reserve.h"
#include "garden_light.h"

const char *
toy_factory_garden_seedling_component_name(enum toy_factory_garden_seedling_component component)
{
	switch (component) {
	case TOY_FACTORY_GARDEN_SEEDLING_BOTH:
		return "both";
	case TOY_FACTORY_GARDEN_SEEDLING_ENERGY:
		return "energy";
	case TOY_FACTORY_GARDEN_SEEDLING_WATER:
		return "water";
	default:
		return NULL;
	}
}

int toy_factory_garden_seedling_component_parse(
	const char *name, enum toy_factory_garden_seedling_component *component)
{
	if ((name == NULL) || (component == NULL)) {
		return -EINVAL;
	}
	static const enum toy_factory_garden_seedling_component values[] = {
		TOY_FACTORY_GARDEN_SEEDLING_BOTH,
		TOY_FACTORY_GARDEN_SEEDLING_ENERGY,
		TOY_FACTORY_GARDEN_SEEDLING_WATER,
	};
	for (size_t i = 0U; i < sizeof(values) / sizeof(values[0]); ++i) {
		if (strcmp(name, toy_factory_garden_seedling_component_name(values[i])) == 0) {
			*component = values[i];
			return 0;
		}
	}
	return -EINVAL;
}

bool toy_factory_garden_seedling_reserve_allows(
	const struct toy_factory_garden_seedling_reserve_forecast *forecast,
	enum toy_factory_garden_seedling_component component)
{
	if (forecast == NULL) {
		return false;
	}
	switch (component) {
	case TOY_FACTORY_GARDEN_SEEDLING_BOTH:
		return forecast->allowed;
	case TOY_FACTORY_GARDEN_SEEDLING_ENERGY:
		return forecast->energy.allowed;
	case TOY_FACTORY_GARDEN_SEEDLING_WATER:
		return forecast->water_allowed;
	default:
		return false;
	}
}

bool toy_factory_garden_seedling_reserve_active(
	const struct toy_factory_garden_seedling_reserve_context *context,
	const struct picosystem_garden_agent_observation *observation)
{
	if ((context == NULL) || (context->world == NULL) ||
	    (!context->all_offspring && (context->lineage == 0U)) || (observation == NULL) ||
	    (observation->plant_index >= context->world->plant_count) ||
	    (observation->plant_index >= PICOSYSTEM_GARDEN_MAX_PLANTS) ||
	    (observation->age_ecology_ticks == 0U) ||
	    (observation->age_ecology_ticks > PICOSYSTEM_GARDEN_SUN_CYCLE_TICKS)) {
		return false;
	}
	const struct picosystem_garden_plant *const plant =
		&context->world->plants[observation->plant_index];
	return (context->all_offspring || (plant->lineage_id == context->lineage)) &&
	       (plant->generation != 0U) && ((plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) == 0U);
}

int toy_factory_garden_seedling_reserve_forecast(
	const struct picosystem_garden_agent_observation *observation,
	const struct picosystem_garden_agent_proposal *proposal,
	struct toy_factory_garden_seedling_reserve_forecast *forecast)
{
	if ((forecast == NULL) || (proposal == NULL) ||
	    !picosystem_garden_agent_observation_is_valid(observation) ||
	    (observation->root_node_count > observation->plant_node_count) ||
	    (proposal->tip_index != observation->tip_index) ||
	    (proposal->action >= PICOSYSTEM_GARDEN_AGENT_ACTION_COUNT)) {
		return -EINVAL;
	}
	struct toy_factory_garden_seedling_reserve_forecast result = {
		.destination = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE,
		.water_allowed = true,
	};
	const bool extend = proposal->action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND;
	if (proposal->candidate_count != (extend ? observation->candidate_count : 0U)) {
		return -EINVAL;
	}
	uint8_t visited = 0U;
	for (uint8_t position = 0U; position < proposal->candidate_count; ++position) {
		const uint8_t index = proposal->candidate_order[position];
		if ((index >= observation->candidate_count) || ((visited & (1U << index)) != 0U)) {
			return -EINVAL;
		}
		visited |= (uint8_t)(1U << index);
		if ((result.destination == PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE) &&
		    ((observation->candidates[index].flags &
		      PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE) != 0U)) {
			result.destination = index;
		}
	}
	const int err =
		toy_factory_garden_reserve_forecast(observation, proposal->action, &result.energy);
	if (err != 0) {
		return err;
	}
	if (proposal->action != PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT) {
		static const uint8_t water_costs[PICOSYSTEM_GARDEN_SPECIES_COUNT] = {5U, 5U, 4U};
		result.water_cost = water_costs[observation->species_id];
		const bool root = observation->tissue_kind == PICOSYSTEM_GARDEN_NODE_ROOT;
		const bool has_destination =
			result.destination != PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE;
		const uint32_t post_shoots = (uint32_t)observation->plant_node_count -
					     observation->root_node_count +
					     (extend && has_destination && !root ? 1U : 0U);
		result.water_upkeep = (post_shoots + 7U) / 8U;
		if (root && extend && has_destination) {
			const struct picosystem_garden_agent_candidate *const candidate =
				&observation->candidates[result.destination];
			result.wet_root = (candidate->y >= PICOSYSTEM_GARDEN_SOIL_TOP_PIXELS) &&
					  (candidate->moisture >= result.water_cost) &&
					  (candidate->moisture > observation->tip_moisture);
		}
		/* A wetter destination is an opportunity, not guaranteed future uptake.
		 * Keep a charge even for that root; never borrow hypothetical water.
		 */
		result.water_reserve = result.water_upkeep * (result.wet_root ? 1U : 4U);
		result.water_allowed =
			observation->stored_water >= result.water_cost + result.water_reserve;
	}
	result.allowed = result.energy.allowed && result.water_allowed;
	*forecast = result;
	return 0;
}

int toy_factory_garden_seedling_reserve_offspring_init(
	const struct picosystem_garden_agent_policy *base,
	const struct picosystem_garden_world *world,
	struct toy_factory_garden_seedling_reserve_context *context,
	struct picosystem_garden_agent_policy *policy)
{
	const int err = toy_factory_garden_seedling_reserve_init(
		base, world, 0U, TOY_FACTORY_GARDEN_SEEDLING_BOTH, context, policy);
	if (err == 0) {
		context->all_offspring = true;
	}
	return err;
}

static int decide(const struct picosystem_garden_agent_observation *observation,
		  const struct picosystem_garden_agent_memory *memory,
		  struct picosystem_garden_agent_decision *decision, const void *opaque)
{
	const struct toy_factory_garden_seedling_reserve_context *const context = opaque;
	struct picosystem_garden_agent_decision result;
	int err = picosystem_garden_agent_decide(context->base, observation, memory, &result);
	if (err != 0) {
		return err;
	}
	if (toy_factory_garden_seedling_reserve_active(context, observation)) {
		struct toy_factory_garden_seedling_reserve_forecast forecast;
		err = toy_factory_garden_seedling_reserve_forecast(observation, &result.proposal,
								   &forecast);
		if (err != 0) {
			return err;
		}
		if (!toy_factory_garden_seedling_reserve_allows(&forecast, context->component)) {
			result.proposal.action = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT;
			result.proposal.candidate_count = 0U;
			memset(result.proposal.candidate_order,
			       PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE,
			       sizeof(result.proposal.candidate_order));
		}
	}
	*decision = result;
	return 0;
}

int toy_factory_garden_seedling_reserve_init(
	const struct picosystem_garden_agent_policy *base,
	const struct picosystem_garden_world *world, uint32_t lineage,
	enum toy_factory_garden_seedling_component component,
	struct toy_factory_garden_seedling_reserve_context *context,
	struct picosystem_garden_agent_policy *policy)
{
	if ((base == NULL) || (world == NULL) || (context == NULL) || (policy == NULL) ||
	    (base == policy) || (base->decide == NULL) || (base->decide == decide) ||
	    (toy_factory_garden_seedling_component_name(component) == NULL)) {
		return -EINVAL;
	}
	*context = (struct toy_factory_garden_seedling_reserve_context){
		.base = base, .world = world, .lineage = lineage, .component = component};
	*policy = *base;
	policy->decide = decide;
	policy->context = context;
	return 0;
}
