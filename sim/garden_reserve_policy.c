/* SPDX-License-Identifier: Apache-2.0 */
#include <errno.h>
#include <string.h>

#include "garden_light.h"
#include "garden_reserve_policy.h"

int toy_factory_garden_reserve_forecast(
	const struct picosystem_garden_agent_observation *observation, uint8_t action,
	struct toy_factory_garden_reserve_forecast *forecast)
{
	if ((forecast == NULL) || !picosystem_garden_agent_observation_is_valid(observation) ||
	    (action >= PICOSYSTEM_GARDEN_AGENT_ACTION_COUNT)) {
		return -EINVAL;
	}
	struct toy_factory_garden_reserve_forecast result = {
		.allowed = action == PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT,
	};
	if (result.allowed || (observation->sun_phase >= PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE)) {
		*forecast = result;
		return 0;
	}
	/* Mirror only action prices and the one-node upper bound, not growth execution.
	 * Fixture tests cover these prices; ordinary trace budgets independently verify them.
	 */
	static const uint8_t energy_costs[PICOSYSTEM_GARDEN_SPECIES_COUNT] = {9U, 8U, 7U};
	result.growth_cost = (uint32_t)energy_costs[observation->species_id] -
			     (observation->vigor > 0 ? 1U : 0U);
	bool can_extend = false;
	for (uint8_t index = 0U; index < observation->candidate_count; ++index) {
		can_extend |= (observation->candidates[index].flags &
			       PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE) != 0U;
	}
	result.post_nodes =
		observation->plant_node_count +
		((action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND) && can_extend ? 1U : 0U);
	result.maintenance_cost = (result.post_nodes + 7U) / 8U;
	if (result.maintenance_cost == 0U) {
		result.maintenance_cost = 1U;
	}
	result.daylight_steps = PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE - observation->sun_phase;
	/* Half current income over the remaining pre-sunset steps is a fixed heuristic,
	 * not a prediction of shading, new leaves or weather. No future-world access.
	 */
	result.daylight_credit =
		((uint32_t)observation->last_energy_income * (result.daylight_steps - 1U)) / 2U;
	result.daylight_upkeep = ((result.daylight_steps + observation->maintenance_phase) /
				  PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR) *
				 result.maintenance_cost;
	result.night_upkeep =
		((PICOSYSTEM_GARDEN_SUN_CYCLE_TICKS - PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE) /
		 PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR) *
		result.maintenance_cost;
	const int32_t after_cost =
		(int32_t)observation->stored_energy - (int32_t)result.growth_cost;
	result.projected_sunset =
		after_cost + (int32_t)result.daylight_credit - (int32_t)result.daylight_upkeep;
	if (result.projected_sunset > 256) {
		result.projected_sunset = 256;
	}
	result.allowed = (after_cost >= (int32_t)result.maintenance_cost) &&
			 (result.projected_sunset >= (int32_t)result.night_upkeep);
	*forecast = result;
	return 0;
}

static int decide(const struct picosystem_garden_agent_observation *observation,
		  const struct picosystem_garden_agent_memory *memory,
		  struct picosystem_garden_agent_decision *decision, const void *context)
{
	const struct picosystem_garden_agent_policy *const base = context;
	int err = picosystem_garden_agent_decide(base, observation, memory, decision);
	struct toy_factory_garden_reserve_forecast forecast;
	if (err == 0) {
		err = toy_factory_garden_reserve_forecast(observation, decision->proposal.action,
							  &forecast);
	}
	if ((err == 0) && !forecast.allowed) {
		decision->proposal.action = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT;
		decision->proposal.candidate_count = 0U;
		memset(decision->proposal.candidate_order, PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE,
		       sizeof(decision->proposal.candidate_order));
	}
	return err;
}

int toy_factory_garden_reserve_init(const struct picosystem_garden_agent_policy *base,
				    struct picosystem_garden_agent_policy *policy)
{
	if ((base == NULL) || (policy == NULL) || (base == policy) || (base->decide == NULL) ||
	    (base->decide == decide)) {
		return -EINVAL;
	}
	*policy = (struct picosystem_garden_agent_policy){
		.decide = decide,
		.context = base,
		.arbitration = base->arbitration,
	};
	return 0;
}
