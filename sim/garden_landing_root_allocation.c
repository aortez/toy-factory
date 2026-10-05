/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_root_allocation.h"
#include "garden_landing_growth.h"
#include "garden_seedling_reserve.h"

#include <errno.h>

int toy_factory_garden_root_allocation_validate(const struct toy_factory_garden_root_allocation *c,
						const struct toy_factory_garden_root_choice *guards,
						uint8_t budget_mode)
{
	if ((c == NULL) || (guards == NULL)) {
		return -EINVAL;
	}
	if (c->version == 0U) {
		return (c->lineage || c->birth_tick || c->parent || c->generation || c->column ||
			c->species)
			       ? -ERANGE
			       : 0;
	}
	if ((c->version != 1U) || (c->lineage == 0U) || (c->birth_tick == 0U) ||
	    (c->birth_tick % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR != 0U) || (c->parent == 0U) ||
	    (c->parent >= c->lineage) || (c->generation == 0U) || (c->generation > UINT16_MAX) ||
	    (c->column >= PICOSYSTEM_GARDEN_GRID_COLUMNS) ||
	    (c->species >= PICOSYSTEM_GARDEN_SPECIES_COUNT) ||
	    (toy_factory_garden_root_choice_validate(guards) != 0) || !guards->all_offspring ||
	    guards->wet_direction || (budget_mode != TOY_FACTORY_GARDEN_BUDGET_SHOOT)) {
		return -ERANGE;
	}
	return 0;
}

int toy_factory_garden_root_allocation_apply(
	const struct picosystem_garden_world *world,
	const struct picosystem_garden_agent_observation *o,
	const struct toy_factory_garden_root_allocation *config,
	const struct toy_factory_garden_root_choice *guards, uint8_t budget_mode,
	struct picosystem_garden_agent_decision *decision,
	struct toy_factory_garden_root_allocation_receipt *receipt)
{
	if ((world == NULL) || (o == NULL) || (decision == NULL)) {
		return -EINVAL;
	}
	int err = toy_factory_garden_root_allocation_validate(config, guards, budget_mode);
	if (err != 0) {
		return err;
	}
	struct toy_factory_garden_root_allocation_receipt result = {0};
	if (config->version == 0U) {
		if (receipt != NULL) {
			*receipt = result;
		}
		return 0;
	}
	if (!picosystem_garden_agent_observation_is_valid(o) ||
	    (world->plant_count > PICOSYSTEM_GARDEN_MAX_PLANTS) ||
	    (o->plant_index >= world->plant_count)) {
		return -EINVAL;
	}
	const struct picosystem_garden_plant *const p = &world->plants[o->plant_index];
	if ((p->lineage_id == config->lineage) && (world->logic_tick_count >= config->birth_tick)) {
		const uint32_t elapsed = world->logic_tick_count - config->birth_tick;
		const uint32_t age = elapsed / PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR + 1U;
		if ((elapsed % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR == 0U) &&
		    (p->age_ecology_ticks == age)) {
			if ((p->parent_lineage_id != config->parent) ||
			    (p->generation != config->generation) ||
			    (p->base_column != config->column) ||
			    (p->species_id != config->species) ||
			    (o->age_ecology_ticks != (age > UINT16_MAX ? UINT16_MAX : age))) {
				return -ESTALE;
			}
			result.active =
				(age >= 2U) && ((p->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) == 0U);
		}
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
	bool energy;
	err = toy_factory_garden_root_energy_eligible(world, o, guards, decision, &energy);
	if (err != 0) {
		return err;
	}
	result.eligible =
		(o->tissue_kind == PICOSYSTEM_GARDEN_NODE_ROOT) &&
		(decision->proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND) &&
		(o->depth < o->maximum_depth) && budget.allocates && budget.allowed && energy &&
		(!toy_factory_garden_seedling_reserve_active(&reserve, o) || water.water_allowed) &&
		(o->stored_energy >= water.energy.growth_cost) &&
		(o->stored_water >= water.water_cost);
	result.prefer =
		result.active && result.eligible &&
		(water.destination != PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE) &&
		(o->candidates[water.destination].moisture > 0U) &&
		((uint32_t)o->last_water_income * PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR <=
		 water.water_upkeep) &&
		((uint32_t)o->last_energy_income * PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR >=
		 water.energy.maintenance_cost);
	/* Mandatory terminal closures retain their higher priorities. */
	if (result.prefer && (decision->proposal.priority < INT16_MAX - 2)) {
		decision->proposal.priority = INT16_MAX - 2;
	}
	if (receipt != NULL) {
		*receipt = result;
	}
	return 0;
}
