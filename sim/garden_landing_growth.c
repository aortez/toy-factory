/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_growth.h"
#include "garden_landing_run_internal.h"

#include <errno.h>
#include <string.h>

static int validate_limit(uint8_t limit)
{
	return ((limit == 0U) || (limit == TOY_FACTORY_GARDEN_LANDING_GROWTH_LIMIT)) ? 0 : -ERANGE;
}

static int validate(const struct toy_factory_garden_landing_growth_run *run)
{
	if ((run == NULL) || (run->version != TOY_FACTORY_GARDEN_LANDING_GROWTH_VERSION)) {
		return -EINVAL;
	}
	if ((run->budget_mode >= TOY_FACTORY_GARDEN_BUDGET_COUNT) ||
	    ((run->budget_mode != TOY_FACTORY_GARDEN_BUDGET_LEGACY) &&
	     (run->node_limit != TOY_FACTORY_GARDEN_LANDING_GROWTH_LIMIT))) {
		return -ERANGE;
	}
	if ((run->placement.version > TOY_FACTORY_GARDEN_PLACEMENT_VERSION) ||
	    (run->placement.enabled > 1U) ||
	    ((run->placement.version == 0U) && (run->placement.enabled != 0U)) ||
	    ((run->placement.version != 0U) &&
	     (run->budget_mode == TOY_FACTORY_GARDEN_BUDGET_LEGACY))) {
		return -ERANGE;
	}
	if ((run->seed_order_after != 0U) &&
	    ((run->placement.version == 0U) ||
	     (run->seed_order_after % (PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR *
				       PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR) !=
	      0U))) {
		return -ERANGE;
	}
	if ((run->placement.replace_after != 0U) &&
	    ((run->placement.version == 0U) || (run->placement.enabled != 1U) ||
	     (run->placement.replace_after % (PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR *
					      PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR) !=
	      0U))) {
		return -ERANGE;
	}
	const struct toy_factory_garden_seed_cursor *const cursor = &run->seed_cursor;
	if ((toy_factory_garden_seed_wait_validate(&run->seed_wait, &run->base.world) != 0) ||
	    ((run->seed_wait.after != 0U) &&
	     ((cursor->after == 0U) || (run->seed_wait.after <= cursor->after)))) {
		return -ERANGE;
	}
	if ((cursor->after == 0U && cursor->last_buyer != 0U) ||
	    (cursor->after != 0U &&
	     ((run->placement.version == 0U) || (run->placement.enabled != 1U) ||
	      (run->seed_order_after != 0U) || (run->placement.replace_after != 0U) ||
	      (cursor->after % (PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR *
				PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR) !=
	       0U) ||
	      (cursor->last_buyer > run->base.world.lineage_sequence) ||
	      (run->base.world.logic_tick_count <= cursor->after && cursor->last_buyer != 0U)))) {
		return -ERANGE;
	}
	if ((toy_factory_garden_root_allocation_validate(&run->root_allocation, &run->root_choice,
							 run->budget_mode) != 0) ||
	    (toy_factory_garden_root_choice_validate(&run->root_choice) != 0) ||
	    (((run->root_choice.tick != 0U) || run->root_choice.all_offspring) &&
	     ((run->placement.version == 0U) ||
	      (run->budget_mode != TOY_FACTORY_GARDEN_BUDGET_SHOOT)))) {
		return -ERANGE;
	}
	return run->base.rules ? -ENOTSUP : validate_limit(run->node_limit);
}

int toy_factory_garden_landing_budget_assess(
	const struct picosystem_garden_world *world,
	const struct picosystem_garden_agent_observation *o,
	const struct picosystem_garden_agent_decision *decision, uint8_t mode,
	struct toy_factory_garden_budget_receipt *receipt)
{
	if ((world == NULL) || (o == NULL) || (decision == NULL) || (receipt == NULL)) {
		return -EINVAL;
	}
	if ((mode < TOY_FACTORY_GARDEN_BUDGET_ELIGIBLE) ||
	    (mode >= TOY_FACTORY_GARDEN_BUDGET_COUNT) ||
	    (world->plant_count > PICOSYSTEM_GARDEN_MAX_PLANTS) ||
	    (world->node_count > PICOSYSTEM_GARDEN_MAX_NODES) ||
	    (o->plant_index >= world->plant_count) || (o->tip_index >= world->node_count) ||
	    (o->plant_node_count > world->node_count) ||
	    (world->nodes[o->tip_index].plant_index != o->plant_index) ||
	    (o->plant_node_count != world->plants[o->plant_index].node_count) ||
	    (decision->proposal.tip_index != o->tip_index) ||
	    (decision->proposal.action >= PICOSYSTEM_GARDEN_AGENT_ACTION_COUNT) ||
	    (o->candidate_count > PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES)) {
		return -ERANGE;
	}
	struct toy_factory_garden_budget_receipt result = {.leader = PICOSYSTEM_GARDEN_NODE_NONE,
							   .allowed = true};
	if (decision->proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND) {
		if (decision->proposal.candidate_count != o->candidate_count) {
			return -ERANGE;
		}
		uint8_t visited = 0U;
		for (uint8_t i = 0U; i < decision->proposal.candidate_count; ++i) {
			const uint8_t c = decision->proposal.candidate_order[i];
			if ((c >= o->candidate_count) || ((visited & (uint8_t)(1U << c)) != 0U)) {
				return -ERANGE;
			}
			visited |= (uint8_t)(1U << c);
			result.allocates |= (o->candidates[c].flags &
					     PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE) != 0U;
		}
	}
	/* Reserve completion of one path, not a fixed root/shoot ratio. */
	if (mode == TOY_FACTORY_GARDEN_BUDGET_SHOOT) {
		for (uint16_t i = 0U; i < world->node_count; ++i) {
			const struct picosystem_garden_node *const node = &world->nodes[i];
			if ((node->plant_index != o->plant_index) ||
			    (node->kind != PICOSYSTEM_GARDEN_NODE_STEM)) {
				continue;
			}
			result.flower |= (node->flags & PICOSYSTEM_GARDEN_NODE_FLOWER) != 0U;
			if (((node->flags & PICOSYSTEM_GARDEN_NODE_TIP) != 0U) &&
			    ((result.leader == PICOSYSTEM_GARDEN_NODE_NONE) ||
			     (node->depth > world->nodes[result.leader].depth))) {
				result.leader = i;
			}
		}
		if (!result.flower && (result.leader != PICOSYSTEM_GARDEN_NODE_NONE)) {
			struct picosystem_garden_agent_observation leader;
			const int err = picosystem_garden_agent_observe_tip(
				world, o->plant_index, result.leader, 0U, &leader);
			if (err != 0) {
				return err;
			}
			result.remaining = (leader.maximum_depth > leader.depth)
						   ? (uint8_t)(leader.maximum_depth - leader.depth)
						   : 0U;
		}
	}
	result.required = o->plant_node_count;
	if (result.allocates) {
		uint16_t remaining = result.remaining;
		if ((o->tip_index == result.leader) && (remaining > 0U)) {
			--remaining;
		}
		result.required = (uint16_t)(o->plant_node_count + 1U + remaining);
		result.allowed = result.required <= TOY_FACTORY_GARDEN_LANDING_GROWTH_LIMIT;
	}
	*receipt = result;
	return 0;
}

int toy_factory_garden_landing_growth_apply(
	const struct picosystem_garden_agent_observation *observation, uint8_t node_limit,
	struct picosystem_garden_agent_decision *decision)
{
	if ((observation == NULL) || (decision == NULL)) {
		return -EINVAL;
	}
	const int err = validate_limit(node_limit);
	if (err != 0) {
		return err;
	}
	if ((node_limit == 0U) || (observation->plant_node_count < node_limit) ||
	    (decision->proposal.action != PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND)) {
		return 0;
	}
	if ((observation->candidate_count > PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES) ||
	    (decision->proposal.candidate_count != observation->candidate_count)) {
		return -ERANGE;
	}
	bool allocates = false;
	uint8_t visited = 0U;
	for (uint8_t i = 0U; i < decision->proposal.candidate_count; ++i) {
		const uint8_t c = decision->proposal.candidate_order[i];
		if ((c >= observation->candidate_count) || ((visited & (uint8_t)(1U << c)) != 0U)) {
			return -ERANGE;
		}
		visited |= (uint8_t)(1U << c);
		allocates |= (observation->candidates[c].flags &
			      PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE) != 0U;
	}
	if (allocates) {
		decision->proposal.action = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT;
		decision->proposal.candidate_count = 0U;
		memset(decision->proposal.candidate_order, PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE,
		       sizeof(decision->proposal.candidate_order));
	}
	return 0;
}

int toy_factory_garden_landing_growth_init(const struct picosystem_garden_world *world,
					   const struct toy_factory_garden_landing_model *model,
					   uint8_t node_limit,
					   struct toy_factory_garden_landing_growth_run *run)
{
	if (run == NULL) {
		return -EINVAL;
	}
	int err = validate_limit(node_limit);
	if (err != 0) {
		return err;
	}
	struct toy_factory_garden_landing_growth_run result = {
		.version = TOY_FACTORY_GARDEN_LANDING_GROWTH_VERSION, .node_limit = node_limit};
	err = toy_factory_garden_landing_run_init(world, model, &result.base);
	if (err == 0) {
		err = validate(&result);
	}
	if (err == 0) {
		*run = result;
	}
	return err;
}

int toy_factory_garden_landing_growth_step(struct toy_factory_garden_landing_growth_run *run,
					   struct picosystem_garden_death_audit *deaths,
					   struct picosystem_garden_seed_audit *seeds,
					   struct picosystem_garden_resource_audit *resources)
{
	if ((deaths == NULL) || (seeds == NULL)) {
		return -EINVAL;
	}
	const int err = validate(run);
	return err ? err
		   : toy_factory_garden_landing_run_step_growth_internal(
			     &run->base, run->node_limit, run->budget_mode, deaths, seeds,
			     resources, NULL, run->placement.version ? &run->placement : NULL, NULL,
			     run->seed_order_after, &run->root_choice, &run->root_allocation,
			     &run->seed_cursor, &run->seed_wait);
}

int toy_factory_garden_landing_growth_step_placement(
	struct toy_factory_garden_landing_growth_run *run,
	struct picosystem_garden_death_audit *deaths, struct picosystem_garden_seed_audit *seeds,
	struct picosystem_garden_resource_audit *resources,
	struct toy_factory_garden_placement_audit *placement)
{
	if ((deaths == NULL) || (seeds == NULL) || (placement == NULL) || (run == NULL) ||
	    (run->placement.version == 0U)) {
		return -EINVAL;
	}
	const int err = validate(run);
	return err ? err
		   : toy_factory_garden_landing_run_step_growth_internal(
			     &run->base, run->node_limit, run->budget_mode, deaths, seeds,
			     resources, NULL, &run->placement, placement, run->seed_order_after,
			     &run->root_choice, &run->root_allocation, &run->seed_cursor,
			     &run->seed_wait);
}

int toy_factory_garden_landing_growth_step_observed(
	struct toy_factory_garden_landing_growth_run *run,
	struct picosystem_garden_death_audit *deaths, struct picosystem_garden_seed_audit *seeds,
	struct picosystem_garden_resource_audit *resources,
	const struct toy_factory_garden_growth_observer *observer)
{
	if ((deaths == NULL) || (seeds == NULL) || (resources == NULL) || (observer == NULL) ||
	    (observer->observe == NULL) || (observer->reproduction == NULL)) {
		return -EINVAL;
	}
	const int err = validate(run);
	return err ? err
		   : toy_factory_garden_landing_run_step_growth_internal(
			     &run->base, run->node_limit, run->budget_mode, deaths, seeds,
			     resources, observer, run->placement.version ? &run->placement : NULL,
			     NULL, run->seed_order_after, &run->root_choice, &run->root_allocation,
			     &run->seed_cursor, &run->seed_wait);
}

int toy_factory_garden_landing_budget_init(const struct picosystem_garden_world *world,
					   const struct toy_factory_garden_landing_model *model,
					   uint8_t shoot_reserve,
					   struct toy_factory_garden_landing_growth_run *run)
{
	if (run == NULL) {
		return -EINVAL;
	}
	if (shoot_reserve > 1U) {
		return -ERANGE;
	}
	struct toy_factory_garden_landing_growth_run result;
	const int err = toy_factory_garden_landing_growth_init(
		world, model, TOY_FACTORY_GARDEN_LANDING_GROWTH_LIMIT, &result);
	if (err == 0) {
		result.budget_mode = shoot_reserve ? TOY_FACTORY_GARDEN_BUDGET_SHOOT
						   : TOY_FACTORY_GARDEN_BUDGET_ELIGIBLE;
		*run = result;
	}
	return err;
}

int toy_factory_garden_landing_placement_init(const struct picosystem_garden_world *world,
					      const struct toy_factory_garden_landing_model *model,
					      uint8_t shoot_reserve, uint8_t enabled,
					      struct toy_factory_garden_landing_growth_run *run)
{
	if (run == NULL) {
		return -EINVAL;
	}
	if (enabled > 1U) {
		return -ERANGE;
	}
	struct toy_factory_garden_landing_growth_run result;
	const int err =
		toy_factory_garden_landing_budget_init(world, model, shoot_reserve, &result);
	if (err == 0) {
		result.placement = (struct toy_factory_garden_placement_config){
			.version = TOY_FACTORY_GARDEN_PLACEMENT_VERSION, .enabled = enabled};
		*run = result;
	}
	return err;
}

int toy_factory_garden_landing_growth_hash(const struct toy_factory_garden_landing_growth_run *run,
					   uint32_t *hash)
{
	if (hash == NULL) {
		return -EINVAL;
	}
	int err = validate(run);
	uint32_t base;
	if (err == 0) {
		err = toy_factory_garden_landing_run_hash(&run->base, &base);
	}
	if (err != 0) {
		return err;
	}
	const uint8_t bytes[] = {'G',
				 'L',
				 run->budget_mode == TOY_FACTORY_GARDEN_BUDGET_LEGACY ? 'C' : 'B',
				 '1',
				 (uint8_t)base,
				 (uint8_t)(base >> 8U),
				 (uint8_t)(base >> 16U),
				 (uint8_t)(base >> 24U),
				 run->version,
				 run->node_limit};
	uint32_t h = UINT32_C(2166136261);
	for (size_t i = 0U; i < sizeof(bytes); ++i) {
		h = (h ^ bytes[i]) * UINT32_C(16777619);
	}
	if (run->budget_mode != TOY_FACTORY_GARDEN_BUDGET_LEGACY) {
		h = (h ^ run->budget_mode) * UINT32_C(16777619);
	}
	if (run->placement.version != 0U) {
		const uint8_t placement[] = {'G',
					     'L',
					     'P',
					     '1',
					     (uint8_t)h,
					     (uint8_t)(h >> 8U),
					     (uint8_t)(h >> 16U),
					     (uint8_t)(h >> 24U),
					     run->placement.version,
					     run->placement.enabled};
		h = UINT32_C(2166136261);
		for (size_t i = 0U; i < sizeof(placement); ++i) {
			h = (h ^ placement[i]) * UINT32_C(16777619);
		}
	}
	if (run->seed_order_after != 0U) {
		const uint8_t tag[] = {'G', 'L', 'R', '1'};
		const uint32_t words[] = {h, run->seed_order_after};
		h = UINT32_C(2166136261);
		for (size_t i = 0U; i < sizeof(tag); ++i) {
			h = (h ^ tag[i]) * UINT32_C(16777619);
		}
		for (size_t i = 0U; i < sizeof(words) / sizeof(words[0]); ++i) {
			for (uint8_t byte = 0U; byte < 4U; ++byte) {
				h = (h ^ (uint8_t)(words[i] >> (byte * 8U))) * UINT32_C(16777619);
			}
		}
	}
	if (run->root_choice.tick != 0U) {
		const uint8_t tag[] = {'G', 'L', 'Q', '1'};
		const uint32_t words[] = {h, run->root_choice.tick, run->root_choice.lineage};
		h = UINT32_C(2166136261);
		for (size_t i = 0U; i < sizeof(tag); ++i) {
			h = (h ^ tag[i]) * UINT32_C(16777619);
		}
		for (size_t i = 0U; i < sizeof(words) / sizeof(words[0]); ++i) {
			for (uint8_t byte = 0U; byte < 4U; ++byte) {
				h = (h ^ (uint8_t)(words[i] >> (byte * 8U))) * UINT32_C(16777619);
			}
		}
	}
	if (run->root_choice.all_offspring) {
		const uint8_t bytes[] = {'G',
					 'L',
					 'F',
					 '1',
					 (uint8_t)h,
					 (uint8_t)(h >> 8U),
					 (uint8_t)(h >> 16U),
					 (uint8_t)(h >> 24U)};
		h = UINT32_C(2166136261);
		for (size_t i = 0U; i < sizeof(bytes); ++i) {
			h = (h ^ bytes[i]) * UINT32_C(16777619);
		}
	}
	if (run->root_choice.energy_reserve) {
		const uint8_t bytes[] = {'G',
					 'L',
					 'E',
					 '1',
					 (uint8_t)h,
					 (uint8_t)(h >> 8U),
					 (uint8_t)(h >> 16U),
					 (uint8_t)(h >> 24U)};
		h = UINT32_C(2166136261);
		for (size_t i = 0U; i < sizeof(bytes); ++i) {
			h = (h ^ bytes[i]) * UINT32_C(16777619);
		}
	}
	if (run->root_choice.afternoon_reserve) {
		const uint8_t bytes[] = {'G',
					 'L',
					 'N',
					 '1',
					 (uint8_t)h,
					 (uint8_t)(h >> 8U),
					 (uint8_t)(h >> 16U),
					 (uint8_t)(h >> 24U)};
		h = UINT32_C(2166136261);
		for (size_t i = 0U; i < sizeof(bytes); ++i) {
			h = (h ^ bytes[i]) * UINT32_C(16777619);
		}
	}
	if (run->root_choice.continuous_energy) {
		const uint8_t bytes[] = {'G',
					 'L',
					 'U',
					 '1',
					 (uint8_t)h,
					 (uint8_t)(h >> 8U),
					 (uint8_t)(h >> 16U),
					 (uint8_t)(h >> 24U)};
		h = UINT32_C(2166136261);
		for (size_t i = 0U; i < sizeof(bytes); ++i) {
			h = (h ^ bytes[i]) * UINT32_C(16777619);
		}
	}
	if (run->root_choice.daylight_energy) {
		const uint8_t bytes[] = {'G',
					 'L',
					 'D',
					 '1',
					 (uint8_t)h,
					 (uint8_t)(h >> 8U),
					 (uint8_t)(h >> 16U),
					 (uint8_t)(h >> 24U)};
		h = UINT32_C(2166136261);
		for (size_t i = 0U; i < sizeof(bytes); ++i) {
			h = (h ^ bytes[i]) * UINT32_C(16777619);
		}
	}
	if (run->root_choice.dawn_reserve) {
		const uint8_t bytes[] = {'G',
					 'L',
					 'M',
					 '1',
					 (uint8_t)h,
					 (uint8_t)(h >> 8U),
					 (uint8_t)(h >> 16U),
					 (uint8_t)(h >> 24U)};
		h = UINT32_C(2166136261);
		for (size_t i = 0U; i < sizeof(bytes); ++i) {
			h = (h ^ bytes[i]) * UINT32_C(16777619);
		}
	}
	if (run->root_choice.wet_direction) {
		const uint8_t bytes[] = {'G',
					 'L',
					 'W',
					 '1',
					 (uint8_t)h,
					 (uint8_t)(h >> 8U),
					 (uint8_t)(h >> 16U),
					 (uint8_t)(h >> 24U)};
		h = UINT32_C(2166136261);
		for (size_t i = 0U; i < sizeof(bytes); ++i) {
			h = (h ^ bytes[i]) * UINT32_C(16777619);
		}
	}
	if (run->root_allocation.version != 0U) {
		const struct toy_factory_garden_root_allocation *const c = &run->root_allocation;
		const uint8_t tag[] = {'G', 'L', 'A', '1'};
		const uint32_t words[] = {h,         c->version,    c->lineage, c->birth_tick,
					  c->parent, c->generation, c->column,  c->species};
		h = UINT32_C(2166136261);
		for (size_t i = 0U; i < sizeof(tag); ++i) {
			h = (h ^ tag[i]) * UINT32_C(16777619);
		}
		for (size_t i = 0U; i < sizeof(words) / sizeof(words[0]); ++i) {
			for (uint8_t byte = 0U; byte < 4U; ++byte) {
				h = (h ^ (uint8_t)(words[i] >> (byte * 8U))) * UINT32_C(16777619);
			}
		}
	}
	if (run->placement.replace_after != 0U) {
		const uint8_t tag[] = {'G', 'L', 'X', '1'};
		const uint32_t words[] = {h, run->placement.replace_after};
		h = UINT32_C(2166136261);
		for (size_t i = 0U; i < sizeof(tag); ++i) {
			h = (h ^ tag[i]) * UINT32_C(16777619);
		}
		for (size_t i = 0U; i < sizeof(words) / sizeof(words[0]); ++i) {
			for (uint8_t byte = 0U; byte < 4U; ++byte) {
				h = (h ^ (uint8_t)(words[i] >> (byte * 8U))) * UINT32_C(16777619);
			}
		}
	}
	if (run->seed_cursor.after != 0U) {
		const uint8_t tag[] = {'G', 'S', 'C', '1'};
		const uint32_t words[] = {h, run->seed_cursor.after, run->seed_cursor.last_buyer};
		h = UINT32_C(2166136261);
		for (size_t i = 0U; i < sizeof(tag); ++i) {
			h = (h ^ tag[i]) * UINT32_C(16777619);
		}
		for (size_t i = 0U; i < sizeof(words) / sizeof(words[0]); ++i) {
			for (uint8_t byte = 0U; byte < 4U; ++byte) {
				h = (h ^ (uint8_t)(words[i] >> (byte * 8U))) * UINT32_C(16777619);
			}
		}
	}
	*hash = toy_factory_garden_seed_wait_hash(&run->seed_wait, h);
	return 0;
}
