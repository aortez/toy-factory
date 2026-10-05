/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_root_choice.h"
#include "garden_landing_growth.h"
#include "garden_seedling_reserve.h"

#include <errno.h>

int toy_factory_garden_root_choice_validate(const struct toy_factory_garden_root_choice *choice)
{
	if (choice == NULL) {
		return -EINVAL;
	}
	return (((choice->tick == 0U) != (choice->lineage == 0U)) ||
		(choice->tick % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR != 0U) ||
		(choice->all_offspring && ((choice->tick != 0U) || !choice->daylight_energy)) ||
		(choice->energy_reserve && (choice->tick == 0U) && !choice->all_offspring) ||
		(choice->afternoon_reserve && !choice->energy_reserve) ||
		(choice->continuous_energy && !choice->afternoon_reserve) ||
		(choice->daylight_energy && !choice->continuous_energy) ||
		(choice->dawn_reserve && !choice->daylight_energy) ||
		(choice->wet_direction && !choice->all_offspring))
		       ? -ERANGE
		       : 0;
}

static bool offspring_active(const struct picosystem_garden_world *world,
			     const struct picosystem_garden_agent_observation *o)
{
	if ((o->plant_index >= world->plant_count) ||
	    (o->plant_index >= PICOSYSTEM_GARDEN_MAX_PLANTS) ||
	    (world->logic_tick_count % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR != 0U)) {
		return false;
	}
	const struct picosystem_garden_plant *const plant = &world->plants[o->plant_index];
	const uint32_t age = plant->age_ecology_ticks;
	return (plant->generation != 0U) && ((plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) == 0U) &&
	       (age != 0U) &&
	       (age <= world->logic_tick_count / PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) &&
	       (o->age_ecology_ticks == (age > UINT16_MAX ? UINT16_MAX : age));
}

bool toy_factory_garden_root_energy_active(const struct picosystem_garden_world *world,
					   const struct picosystem_garden_agent_observation *o,
					   const struct toy_factory_garden_root_choice *choice)
{
	if ((world == NULL) || (o == NULL) ||
	    (toy_factory_garden_root_choice_validate(choice) != 0) || !choice->energy_reserve ||
	    (world->logic_tick_count <= choice->tick) || (o->age_ecology_ticks < 2U)) {
		return false;
	}
	if (choice->all_offspring) {
		return offspring_active(world, o);
	}
	if (choice->continuous_energy) {
		if ((o->plant_index >= world->plant_count) ||
		    (o->plant_index >= PICOSYSTEM_GARDEN_MAX_PLANTS)) {
			return false;
		}
		const struct picosystem_garden_plant *const plant = &world->plants[o->plant_index];
		const uint32_t elapsed = world->logic_tick_count - choice->tick;
		const uint32_t age = elapsed / PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR + 1U;
		/* Lineage IDs are not reused; saturated age must not expire protection. */
		return (plant->lineage_id == choice->lineage) && (plant->generation != 0U) &&
		       ((plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) == 0U) &&
		       (plant->age_ecology_ticks == age) &&
		       (elapsed % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR == 0U) &&
		       (o->age_ecology_ticks == (age > UINT16_MAX ? UINT16_MAX : age));
	}
	const struct toy_factory_garden_seedling_reserve_context reserve = {
		.world = world, .lineage = choice->lineage};
	return toy_factory_garden_seedling_reserve_active(&reserve, o) &&
	       (world->logic_tick_count - choice->tick ==
		((uint32_t)o->age_ecology_ticks - 1U) * PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR);
}

int toy_factory_garden_root_energy_eligible(const struct picosystem_garden_world *world,
					    const struct picosystem_garden_agent_observation *o,
					    const struct toy_factory_garden_root_choice *choice,
					    const struct picosystem_garden_agent_decision *decision,
					    bool *allowed)
{
	if ((world == NULL) || (o == NULL) || (choice == NULL) || (decision == NULL) ||
	    (allowed == NULL)) {
		return -EINVAL;
	}
	int err = toy_factory_garden_root_choice_validate(choice);
	if (err != 0) {
		return err;
	}
	bool result = true;
	if (toy_factory_garden_root_energy_active(world, o, choice)) {
		struct toy_factory_garden_reserve_forecast forecast;
		err = toy_factory_garden_reserve_forecast(o, decision->proposal.action, &forecast);
		if (err != 0) {
			return err;
		}
		result = forecast.allowed;
		if (choice->afternoon_reserve) {
			struct toy_factory_garden_afternoon_forecast afternoon;
			err = toy_factory_garden_afternoon_forecast(o, decision->proposal.action,
								    &afternoon);
			if (err != 0) {
				return err;
			}
			result = result && afternoon.allowed;
		}
		if (choice->daylight_energy) {
			struct toy_factory_garden_daylight_forecast daylight;
			err = toy_factory_garden_daylight_forecast(o, decision->proposal.action,
								   &daylight);
			if (err != 0) {
				return err;
			}
			result = result && daylight.allowed;
		}
		if (choice->dawn_reserve) {
			struct toy_factory_garden_dawn_forecast dawn;
			err = toy_factory_garden_dawn_forecast(o, decision->proposal.action, &dawn);
			if (err != 0) {
				return err;
			}
			result = result && dawn.allowed;
		}
	}
	*allowed = result;
	return 0;
}

int toy_factory_garden_root_choice_apply(const struct picosystem_garden_world *world,
					 const struct picosystem_garden_agent_observation *o,
					 const struct toy_factory_garden_root_choice *choice,
					 uint8_t budget_mode,
					 struct picosystem_garden_agent_decision *decision)
{
	if ((world == NULL) || (o == NULL) || (choice == NULL) || (decision == NULL)) {
		return -EINVAL;
	}
	if (toy_factory_garden_root_choice_validate(choice) != 0) {
		return -ERANGE;
	}
	if (choice->all_offspring) {
		if (!offspring_active(world, o) || (o->age_ecology_ticks != 1U)) {
			return 0;
		}
	} else if ((choice->tick == 0U) || (world->logic_tick_count != choice->tick)) {
		return 0;
	}
	const struct toy_factory_garden_seedling_reserve_context reserve = {
		.world = world, .lineage = choice->lineage, .all_offspring = choice->all_offspring};
	if (!toy_factory_garden_seedling_reserve_active(&reserve, o) ||
	    (o->root_node_count != 2U) || (o->tissue_kind != PICOSYSTEM_GARDEN_NODE_ROOT) ||
	    (decision->proposal.action != PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND)) {
		return 0;
	}
	struct toy_factory_garden_budget_receipt budget;
	int err =
		toy_factory_garden_landing_budget_assess(world, o, decision, budget_mode, &budget);
	if (err != 0) {
		return err;
	}
	struct toy_factory_garden_seedling_reserve_forecast water;
	err = toy_factory_garden_seedling_reserve_forecast(o, &decision->proposal, &water);
	if (err != 0) {
		return err;
	}
	/* Reuse the existing first-day water guard, not its optional energy reserve.
	 * The ordinary executor still charges the same price and chooses one bid.
	 */
	if (budget.allocates && budget.allowed && water.water_allowed &&
	    (water.energy.growth_cost != 0U) && (o->stored_energy >= water.energy.growth_cost)) {
		decision->proposal.priority = INT16_MAX;
	}
	return 0;
}
