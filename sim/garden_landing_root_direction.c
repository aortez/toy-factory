/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_root_direction.h"
#include "garden_landing_growth.h"
#include "garden_seedling_reserve.h"

#include <errno.h>

static void promote(struct picosystem_garden_agent_proposal *proposal, uint8_t position)
{
	const uint8_t candidate = proposal->candidate_order[position];
	for (uint8_t i = position; i > 0U; --i) {
		proposal->candidate_order[i] = proposal->candidate_order[i - 1U];
	}
	proposal->candidate_order[0] = candidate;
}

int toy_factory_garden_root_direction_apply(const struct picosystem_garden_world *world,
					    const struct picosystem_garden_agent_observation *o,
					    const struct toy_factory_garden_root_choice *choice,
					    uint8_t budget_mode,
					    struct picosystem_garden_agent_decision *decision)
{
	if ((world == NULL) || (o == NULL) || (choice == NULL) || (decision == NULL)) {
		return -EINVAL;
	}
	int err = toy_factory_garden_root_choice_validate(choice);
	if ((err != 0) || !choice->wet_direction) {
		return err;
	}
	if (!picosystem_garden_agent_observation_is_valid(o) ||
	    (budget_mode != TOY_FACTORY_GARDEN_BUDGET_SHOOT)) {
		return -EINVAL;
	}
	if ((o->tissue_kind != PICOSYSTEM_GARDEN_NODE_ROOT) ||
	    (decision->proposal.action != PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND) ||
	    (o->depth >= o->maximum_depth)) {
		return 0;
	}
	struct toy_factory_garden_budget_receipt budget;
	err = toy_factory_garden_landing_budget_assess(world, o, decision, budget_mode, &budget);
	if (err != 0) {
		return err;
	}
	struct toy_factory_garden_seedling_reserve_forecast water;
	err = toy_factory_garden_seedling_reserve_forecast(o, &decision->proposal, &water);
	if (err != 0) {
		return err;
	}
	const struct toy_factory_garden_seedling_reserve_context reserve = {.world = world,
									    .all_offspring = true};
	const bool water_active = toy_factory_garden_seedling_reserve_active(&reserve, o);
	bool energy;
	err = toy_factory_garden_root_energy_eligible(world, o, choice, decision, &energy);
	if (err != 0) {
		return err;
	}
	/* Refused bids remain refused, even if a different destination could pass
	 * the wet-root discount. This changes direction, not arbitration policy.
	 */
	if (!budget.allocates || !budget.allowed || !energy ||
	    (water_active && !water.water_allowed) ||
	    (o->stored_energy < water.energy.growth_cost) || (o->stored_water < water.water_cost)) {
		return 0;
	}
	static const uint8_t uptake_limits[PICOSYSTEM_GARDEN_SPECIES_COUNT] = {3U, 3U, 2U};
	const uint8_t limit = uptake_limits[o->species_id];
	const uint8_t moisture = o->candidates[water.destination].moisture;
	uint8_t best = moisture < limit ? moisture : limit;
	struct picosystem_garden_agent_decision result = *decision;
	for (uint8_t i = 0U; i < decision->proposal.candidate_count; ++i) {
		const uint8_t c = decision->proposal.candidate_order[i];
		const struct picosystem_garden_agent_candidate *const candidate = &o->candidates[c];
		const uint8_t potential = candidate->moisture < limit ? candidate->moisture : limit;
		if (((candidate->flags & PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE) == 0U) ||
		    (potential <= best)) {
			continue;
		}
		struct picosystem_garden_agent_proposal alternative = decision->proposal;
		promote(&alternative, i);
		struct toy_factory_garden_seedling_reserve_forecast forecast;
		err = toy_factory_garden_seedling_reserve_forecast(o, &alternative, &forecast);
		if (err != 0) {
			return err;
		}
		if (!water_active || forecast.water_allowed) {
			result.proposal = alternative;
			best = potential;
		}
	}
	*decision = result;
	return 0;
}
