/* SPDX-License-Identifier: Apache-2.0 */
#include <errno.h>

#include "garden_root_bootstrap.h"
#include "garden_light.h"

#if defined(__ZEPHYR__)
#error "Root bootstrap is an explicit host experiment, not a firmware policy"
#endif

static bool eligible(const struct toy_factory_garden_root_bootstrap_context *context,
		     const struct picosystem_garden_agent_observation *observation)
{
	if ((context->after_tick == 0U) ||
	    (context->world->logic_tick_count <= context->after_tick) ||
	    (observation->plant_index >= context->world->plant_count) ||
	    (context->world->plants[observation->plant_index].generation == 0U) ||
	    (observation->age_ecology_ticks == 0U) ||
	    (observation->age_ecology_ticks > PICOSYSTEM_GARDEN_SUN_CYCLE_TICKS) ||
	    (observation->root_node_count != 2U) ||
	    (observation->tissue_kind != PICOSYSTEM_GARDEN_NODE_ROOT) ||
	    (observation->depth != 1U) ||
	    (observation->tip_y < PICOSYSTEM_GARDEN_SOIL_TOP_PIXELS) ||
	    (observation->tip_y >=
	     PICOSYSTEM_GARDEN_SOIL_TOP_PIXELS + PICOSYSTEM_GARDEN_CELL_PIXELS)) {
		return false;
	}
	/* Age is incremented before the birth-step decision. Avoid unsigned subtraction
	 * until the range is known; founders and pre-window offspring remain unchanged.
	 */
	const uint32_t elapsed = (uint32_t)(observation->age_ecology_ticks - 1U) *
				 PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR;
	return (context->world->logic_tick_count >= elapsed) &&
	       (context->world->logic_tick_count - elapsed > context->after_tick);
}

static int decide(const struct picosystem_garden_agent_observation *observation,
		  const struct picosystem_garden_agent_memory *memory,
		  struct picosystem_garden_agent_decision *decision, const void *opaque)
{
	const struct toy_factory_garden_root_bootstrap_context *context = opaque;
	struct picosystem_garden_agent_decision result;
	const int err = picosystem_garden_agent_decide(context->base, observation, memory, &result);
	if (err != 0) {
		return err;
	}
	if (!eligible(context, observation) ||
	    (result.proposal.action != PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND)) {
		*decision = result;
		return 0;
	}
	static const uint8_t water_costs[PICOSYSTEM_GARDEN_SPECIES_COUNT] = {5U, 5U, 4U};
	static const uint8_t energy_costs[PICOSYSTEM_GARDEN_SPECIES_COUNT] = {9U, 8U, 7U};
	const uint8_t water_cost = water_costs[observation->species_id];
	const uint8_t energy_cost = (uint8_t)(energy_costs[observation->species_id] -
					      (observation->vigor > 0 ? 1U : 0U));
	if ((observation->stored_water < water_cost) ||
	    (observation->stored_energy < energy_cost)) {
		*decision = result;
		return 0;
	}
	/* Preserve the base policy's tie order. Do not invent an EXTEND after an energy
	 * or night veto, and do not spend on a blocked or equally dry destination.
	 */
	if (result.proposal.candidate_count != observation->candidate_count) {
		return -EINVAL;
	}
	uint8_t visited = 0U;
	uint8_t best_position = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE;
	uint8_t best_moisture = observation->tip_moisture;
	for (uint8_t position = 0U; position < result.proposal.candidate_count; ++position) {
		const uint8_t index = result.proposal.candidate_order[position];
		if ((index >= observation->candidate_count) || ((visited & (1U << index)) != 0U)) {
			return -EINVAL;
		}
		visited |= (uint8_t)(1U << index);
		const struct picosystem_garden_agent_candidate *candidate =
			&observation->candidates[index];
		if (((candidate->flags & PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE) != 0U) &&
		    (candidate->y >=
		     PICOSYSTEM_GARDEN_SOIL_TOP_PIXELS + PICOSYSTEM_GARDEN_CELL_PIXELS) &&
		    (candidate->moisture >= water_cost) && (candidate->moisture > best_moisture)) {
			best_position = position;
			best_moisture = candidate->moisture;
		}
	}
	if (best_position != PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE) {
		const uint8_t selected = result.proposal.candidate_order[best_position];
		for (uint8_t position = best_position; position > 0U; --position) {
			result.proposal.candidate_order[position] =
				result.proposal.candidate_order[position - 1U];
		}
		result.proposal.candidate_order[0] = selected;
		result.proposal.priority = INT16_MAX;
	}
	*decision = result;
	return 0;
}

int toy_factory_garden_root_bootstrap_init(
	const struct picosystem_garden_agent_policy *base,
	const struct picosystem_garden_world *world, uint32_t after_tick,
	struct toy_factory_garden_root_bootstrap_context *context,
	struct picosystem_garden_agent_policy *policy)
{
	if ((base == NULL) || (world == NULL) || (context == NULL) || (policy == NULL) ||
	    (base == policy) || (base->decide == NULL) || (base->decide == decide) ||
	    (base->arbitration != PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS) ||
	    ((after_tick % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) != 0U)) {
		return -EINVAL;
	}
	*context = (struct toy_factory_garden_root_bootstrap_context){
		.base = base, .world = world, .after_tick = after_tick};
	*policy = *base;
	policy->decide = decide;
	policy->context = context;
	return 0;
}
