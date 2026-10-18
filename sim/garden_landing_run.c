/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_run.h"
#include "garden_landing_internal.h"
#include "garden_landing_run_internal.h"
#include "garden_landing_growth.h"
#include "garden_landing_root_direction.h"

#include <errno.h>
#include <string.h>

static uint32_t build_rules(void)
{
	uint32_t rules = 0U;
#if defined(TOY_FACTORY_GARDEN_WIDE_DISPERSAL)
	rules |= 1U;
#endif
#if defined(TOY_FACTORY_GARDEN_FLOWER_DISPERSAL)
	rules |= 2U;
#endif
	return rules;
}

static int validate(const struct toy_factory_garden_landing_run *run)
{
	if ((run == NULL) || (run->version != TOY_FACTORY_GARDEN_LANDING_RUN_VERSION) ||
	    (run->rules != build_rules()) || run->world.auto_gardener_enabled ||
	    !picosystem_garden_landing_cache_is_valid(&run->cache) ||
	    (run->cache.ecology_tick != run->world.ecology_tick_count) ||
	    (run->world.logic_tick_count / PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR !=
	     run->cache.ecology_tick)) {
		return -EINVAL;
	}
	for (uint8_t c = 0U; c < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++c) {
		if ((run->cache.traces[3][c] > run->cache.traces[2][c]) ||
		    (run->cache.traces[2][c] > run->cache.traces[0][c]) ||
		    (run->cache.traces[2][c] > run->cache.traces[1][c])) {
			return -ERANGE;
		}
	}
	return toy_factory_garden_landing_model_validate(&run->model);
}

int toy_factory_garden_landing_run_init(const struct picosystem_garden_world *world,
					const struct toy_factory_garden_landing_model *model,
					struct toy_factory_garden_landing_run *run)
{
	if ((world == NULL) || (run == NULL)) {
		return -EINVAL;
	}
	int err = toy_factory_garden_landing_model_validate(model);
	if (err != 0) {
		return err;
	}
	struct picosystem_garden_landing_cache cache;
	err = picosystem_garden_landing_reset(world, &cache);
	if (err != 0) {
		return err;
	}
	*run = (struct toy_factory_garden_landing_run){
		.version = TOY_FACTORY_GARDEN_LANDING_RUN_VERSION,
		.rules = build_rules(),
		.world = *world,
		.cache = cache,
		.model = *model};
	return 0;
}

struct run_context {
	const struct toy_factory_garden_landing_model *model;
	const struct picosystem_garden_landing_cache *cache;
	const struct toy_factory_garden_landing_signal_config *probe;
	toy_factory_garden_landing_observe_fn observe;
	void *observer_context;
	uint8_t node_limit;
	uint8_t budget_mode;
	const struct picosystem_garden_world *world;
	const struct toy_factory_garden_growth_observer *growth_observer;
	const struct toy_factory_garden_root_choice *root_choice;
	const struct toy_factory_garden_root_allocation *root_allocation;
};

static int decide(const struct picosystem_garden_agent_observation *observation,
		  const struct picosystem_garden_agent_memory *memory,
		  struct picosystem_garden_agent_decision *decision, const void *context)
{
	const struct run_context *const ctx = context;
	struct picosystem_garden_landing_packet packet;
	int err = picosystem_garden_landing_observe(ctx->cache, observation, &packet);
	if (err != 0) {
		return err;
	}
	if (ctx->probe != NULL) {
		struct picosystem_garden_landing_packet changed;
		err = toy_factory_garden_landing_signal_apply(observation, &packet, ctx->probe,
							      &changed);
		if (err != 0) {
			return err;
		}
		packet = changed;
	}
	err = toy_factory_garden_landing_neural_decide(observation, memory, &packet, ctx->model,
						       decision);
	if (err != 0) {
		return err;
	}
	const struct picosystem_garden_agent_decision raw = *decision;
	if ((err == 0) && (ctx->node_limit != 0U) &&
	    (ctx->budget_mode == TOY_FACTORY_GARDEN_BUDGET_LEGACY)) {
		err = toy_factory_garden_landing_growth_apply(observation, ctx->node_limit,
							      decision);
	}
	if ((err == 0) && (ctx->root_choice != NULL)) {
		err = toy_factory_garden_root_choice_apply(
			ctx->world, observation, ctx->root_choice, ctx->budget_mode, decision);
		if ((err == 0) && ctx->root_choice->wet_direction) {
			err = toy_factory_garden_root_direction_apply(ctx->world, observation,
								      ctx->root_choice,
								      ctx->budget_mode, decision);
		}
	}
	if ((err == 0) && (ctx->root_allocation != NULL) && (ctx->root_allocation->version != 0U)) {
		err = toy_factory_garden_root_allocation_apply(
			ctx->world, observation, ctx->root_allocation, ctx->root_choice,
			ctx->budget_mode, decision, NULL);
	}
	if ((err == 0) && (ctx->observe != NULL)) {
		err = ctx->observe(observation, memory, &packet, decision, ctx->observer_context);
	}
	if ((err == 0) && (ctx->growth_observer != NULL)) {
		err = ctx->growth_observer->observe(ctx->world, observation, &raw, decision,
						    ctx->growth_observer->context);
	}
	return err;
}

static int budget_eligible(const struct picosystem_garden_agent_observation *observation,
			   const struct picosystem_garden_agent_decision *decision, bool *allowed,
			   const void *opaque)
{
	const struct run_context *const context = opaque;
	struct toy_factory_garden_budget_receipt budget;
	int err = toy_factory_garden_landing_budget_assess(context->world, observation, decision,
							   context->budget_mode, &budget);
	if (err != 0) {
		return err;
	}
	const struct toy_factory_garden_seedling_reserve_context reserve = {.world = context->world,
									    .all_offspring = true};
	bool water;
	err = toy_factory_garden_landing_water_eligible(observation, decision, &water, &reserve);
	bool energy = true;
	if ((err == 0) && (context->root_choice != NULL)) {
		err = toy_factory_garden_root_energy_eligible(
			context->world, observation, context->root_choice, decision, &energy);
	}
	if (err == 0) {
		*allowed = budget.allowed && water && energy;
	}
	return err;
}

static int step(struct toy_factory_garden_landing_run *run,
		struct picosystem_garden_death_audit *audit,
		struct picosystem_garden_seed_audit *seeds,
		const struct toy_factory_garden_landing_signal_config *probe,
		toy_factory_garden_landing_observe_fn observe, void *observer_context,
		struct picosystem_garden_resource_audit *resources,
		const struct toy_factory_garden_landing_water_config *water,
		struct toy_factory_garden_landing_water_audit *water_audit, uint8_t node_limit,
		uint8_t budget_mode,
		const struct toy_factory_garden_growth_observer *growth_observer,
		const struct toy_factory_garden_placement_config *placement,
		struct toy_factory_garden_placement_audit *placement_audit,
		uint32_t seed_order_after, const struct toy_factory_garden_root_choice *root_choice,
		const struct toy_factory_garden_root_allocation *root_allocation,
		struct toy_factory_garden_seed_cursor *seed_cursor,
		struct toy_factory_garden_seed_wait *seed_wait)
{
	int err = validate(run);
	if (err != 0) {
		return err;
	}
	struct picosystem_garden_world world = run->world;
	struct picosystem_garden_landing_cache cache = run->cache;
	struct toy_factory_garden_landing_water_audit water_result;
	struct toy_factory_garden_landing_water_context water_context = {
		.world = &world,
		.audit = &water_result,
		.record_bids = (water != NULL) &&
			       (water->version == TOY_FACTORY_GARDEN_LANDING_ARBITRATION_VERSION)};
	if (water_audit != NULL) {
		memset(&water_result, 0, sizeof(water_result));
		observe = toy_factory_garden_landing_water_observe_internal;
		observer_context = &water_context;
	}
	const struct run_context context = {.model = &run->model,
					    .cache = &cache,
					    .probe = probe,
					    .observe = observe,
					    .observer_context = observer_context,
					    .node_limit = node_limit,
					    .budget_mode = budget_mode,
					    .world = &world,
					    .growth_observer = growth_observer,
					    .root_choice = root_choice,
					    .root_allocation = root_allocation};
	const struct picosystem_garden_agent_policy base_policy = {
		.decide = decide,
		.context = &context,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS};
	struct picosystem_garden_agent_policy policy = base_policy;
	policy.reproduction_rotation_after = seed_order_after;
	if ((seed_cursor != NULL) && (seed_cursor->after != 0U) &&
	    (world.logic_tick_count >= seed_cursor->after) &&
	    ((world.logic_tick_count + 1U) % (PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR *
					      PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR) ==
	     0U)) {
		policy.reproduction_purchase_order = true;
		policy.reproduction_after_lineage = seed_cursor->last_buyer;
	}
	if ((seed_wait != NULL) && (seed_wait->after != 0U) &&
	    (world.logic_tick_count >= seed_wait->after) && policy.reproduction_purchase_order) {
		policy.reproduction_purchase_order = false;
		policy.reproduction_order = toy_factory_garden_seed_wait_order;
		policy.reproduction_order_context = seed_wait;
	}
	struct toy_factory_garden_seedling_reserve_context reserve;
	if ((water != NULL) && (water->enabled != 0U)) {
		if (water->eligible != 0U) {
			reserve = (struct toy_factory_garden_seedling_reserve_context){
				.world = &world, .all_offspring = true};
			policy.eligible = toy_factory_garden_landing_water_eligible;
			policy.eligibility_context = &reserve;
		} else {
			err = toy_factory_garden_seedling_reserve_init(
				&base_policy, &world, 0U, TOY_FACTORY_GARDEN_SEEDLING_WATER,
				&reserve, &policy);
			if (err != 0) {
				return err;
			}
			reserve.all_offspring = true;
		}
	}
	if (budget_mode != TOY_FACTORY_GARDEN_BUDGET_LEGACY) {
		policy.eligible = budget_eligible;
		policy.eligibility_context = &context;
	}
	struct toy_factory_garden_placement_audit placement_result = {0};
	const struct toy_factory_garden_placement_context placement_context = {
		.config = placement, .audit = placement_audit ? &placement_result : NULL};
	if (placement != NULL) {
		policy.place_seed = toy_factory_garden_placement_decide;
		policy.placement_context = &placement_context;
		policy.seed_replacement_after = placement->replace_after;
	}
	if ((growth_observer != NULL) && (growth_observer->uptake != NULL)) {
		err = picosystem_garden_world_step_landing_uptake(
			&world, &policy, &cache, audit, seeds, resources,
			growth_observer->reproduction, growth_observer->uptake);
	} else if (growth_observer != NULL) {
		err = picosystem_garden_world_step_landing_reproduction(
			&world, &policy, &cache, audit, seeds, resources,
			growth_observer->reproduction);
	} else if (resources != NULL) {
		err = picosystem_garden_world_step_landing_resources(&world, &policy, &cache, audit,
								     seeds, resources);
	} else if (seeds != NULL) {
		err = picosystem_garden_world_step_landing_audits(&world, &policy, &cache, audit,
								  seeds);
	} else if (audit != NULL) {
		err = picosystem_garden_world_step_landing_death_audit(&world, &policy, &cache,
								       audit);
	} else {
		err = picosystem_garden_world_step_landing(&world, &policy, &cache);
	}
	if (err != 0) {
		return err;
	}
	/* Without replacement, purchases append in visit order after seed aging.
	 * Age-zero seeds therefore identify actual buyers even without observers.
	 * Publish this state only after the complete world/cache step succeeds.
	 */
	if ((seed_wait != NULL) && (seed_wait->after != 0U) &&
	    (world.logic_tick_count % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR == 0U)) {
		struct toy_factory_garden_seed_wait next;
		toy_factory_garden_seed_wait_advance(seed_wait, &world, &next);
		*seed_wait = next;
	}
	if ((seed_cursor != NULL) &&
	    (policy.reproduction_purchase_order || (policy.reproduction_order != NULL))) {
		for (uint8_t i = 0U; i < world.seed_count; ++i) {
			if (world.seeds[i].age_ecology_ticks == 0U) {
				seed_cursor->last_buyer = world.seeds[i].parent_lineage_id;
			}
		}
	}
	run->world = world;
	run->cache = cache;
	if (water_audit != NULL) {
		*water_audit = water_result;
	}
	if (placement_audit != NULL) {
		placement_result.ecology_step =
			world.logic_tick_count % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR == 0U;
		*placement_audit = placement_result;
	}
	return 0;
}

int toy_factory_garden_landing_run_step(struct toy_factory_garden_landing_run *run)
{
	return step(run, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 0U, 0U, NULL, NULL, NULL,
		    0U, NULL, NULL, NULL, NULL);
}

int toy_factory_garden_landing_run_step_death_audit(struct toy_factory_garden_landing_run *run,
						    struct picosystem_garden_death_audit *audit)
{
	return (audit == NULL) ? -EINVAL
			       : step(run, audit, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 0U, 0U,
				      NULL, NULL, NULL, 0U, NULL, NULL, NULL, NULL);
}

int toy_factory_garden_landing_run_step_audits(struct toy_factory_garden_landing_run *run,
					       struct picosystem_garden_death_audit *deaths,
					       struct picosystem_garden_seed_audit *seeds)
{
	return ((deaths == NULL) || (seeds == NULL))
		       ? -EINVAL
		       : step(run, deaths, seeds, NULL, NULL, NULL, NULL, NULL, NULL, 0U, 0U, NULL,
			      NULL, NULL, 0U, NULL, NULL, NULL, NULL);
}

int toy_factory_garden_landing_run_step_resources(
	struct toy_factory_garden_landing_run *run, struct picosystem_garden_death_audit *deaths,
	struct picosystem_garden_seed_audit *seeds,
	struct picosystem_garden_resource_audit *resources)
{
	return ((deaths == NULL) || (seeds == NULL) || (resources == NULL))
		       ? -EINVAL
		       : step(run, deaths, seeds, NULL, NULL, NULL, resources, NULL, NULL, 0U, 0U,
			      NULL, NULL, NULL, 0U, NULL, NULL, NULL, NULL);
}

int toy_factory_garden_landing_run_step_observed(struct toy_factory_garden_landing_run *run,
						 struct picosystem_garden_death_audit *deaths,
						 struct picosystem_garden_seed_audit *seeds,
						 toy_factory_garden_landing_observe_fn observe,
						 void *context)
{
	return ((deaths == NULL) || (seeds == NULL) || (observe == NULL))
		       ? -EINVAL
		       : step(run, deaths, seeds, NULL, observe, context, NULL, NULL, NULL, 0U, 0U,
			      NULL, NULL, NULL, 0U, NULL, NULL, NULL, NULL);
}

int toy_factory_garden_landing_run_step_signal_internal(
	struct toy_factory_garden_landing_run *run,
	const struct toy_factory_garden_landing_signal_config *config,
	struct picosystem_garden_death_audit *deaths, struct picosystem_garden_seed_audit *seeds)
{
	return step(run, deaths, seeds, config, NULL, NULL, NULL, NULL, NULL, 0U, 0U, NULL, NULL,
		    NULL, 0U, NULL, NULL, NULL, NULL);
}

int toy_factory_garden_landing_run_step_water_internal(
	struct toy_factory_garden_landing_run *run,
	const struct toy_factory_garden_landing_water_config *config,
	struct picosystem_garden_death_audit *deaths, struct picosystem_garden_seed_audit *seeds,
	struct picosystem_garden_resource_audit *resources,
	struct toy_factory_garden_landing_water_audit *audit)
{
	return step(run, deaths, seeds, NULL, NULL, NULL, resources, config, audit, 0U, 0U, NULL,
		    NULL, NULL, 0U, NULL, NULL, NULL, NULL);
}

int toy_factory_garden_landing_run_step_growth_internal(
	struct toy_factory_garden_landing_run *run, uint8_t node_limit, uint8_t budget_mode,
	struct picosystem_garden_death_audit *deaths, struct picosystem_garden_seed_audit *seeds,
	struct picosystem_garden_resource_audit *resources,
	const struct toy_factory_garden_growth_observer *observer,
	const struct toy_factory_garden_placement_config *placement,
	struct toy_factory_garden_placement_audit *placement_audit, uint32_t seed_order_after,
	const struct toy_factory_garden_root_choice *root_choice,
	const struct toy_factory_garden_root_allocation *root_allocation,
	struct toy_factory_garden_seed_cursor *seed_cursor,
	struct toy_factory_garden_seed_wait *seed_wait)
{
	const struct toy_factory_garden_landing_water_config water = {
		.version = TOY_FACTORY_GARDEN_LANDING_ARBITRATION_VERSION,
		.enabled = 1U,
		.eligible = 1U};
	return step(run, deaths, seeds, NULL, NULL, NULL, resources, &water, NULL, node_limit,
		    budget_mode, observer, placement, placement_audit, seed_order_after,
		    root_choice, root_allocation, seed_cursor, seed_wait);
}

static uint32_t hash_byte(uint32_t hash, uint8_t value)
{
	return (hash ^ value) * UINT32_C(16777619);
}

static uint32_t hash_le(uint32_t hash, uint32_t value, uint8_t bytes)
{
	for (uint8_t i = 0U; i < bytes; ++i) {
		hash = hash_byte(hash, (uint8_t)(value >> (8U * i)));
	}
	return hash;
}

int toy_factory_garden_landing_run_hash(const struct toy_factory_garden_landing_run *run,
					uint32_t *hash)
{
	if (hash == NULL) {
		return -EINVAL;
	}
	int err = validate(run);
	if (err != 0) {
		return err;
	}
	uint8_t model[TOY_FACTORY_GARDEN_LANDING_FILE_SIZE];
	err = toy_factory_garden_landing_model_encode(&run->model, model, sizeof(model));
	if (err != 0) {
		return err;
	}
	uint32_t h = hash_le(UINT32_C(2166136261), UINT32_C(0x31524c47), 4U); /* GLR1 */
	h = hash_le(h, run->version, 4U);
	h = hash_le(h, run->rules, 4U);
	h = hash_le(h, picosystem_garden_world_hash(&run->world), 4U);
	h = hash_le(h, run->cache.ecology_tick, 4U);
	h = hash_le(h, run->cache.warmup_samples, 2U);
	h = hash_byte(h, run->cache.version);
	h = hash_byte(h, run->cache.flags);
	for (uint8_t t = 0U; t < PICOSYSTEM_GARDEN_LANDING_TRACES; ++t) {
		for (uint8_t c = 0U; c < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++c) {
			h = hash_le(h, run->cache.traces[t][c], 2U);
		}
	}
	for (uint8_t c = 0U; c < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++c) {
		h = hash_byte(h, run->cache.water[c]);
		h = hash_byte(h, run->cache.light[c]);
		h = hash_byte(h, run->cache.occupied[c]);
	}
	for (size_t i = 0U; i < sizeof(model); ++i) {
		h = hash_byte(h, model[i]);
	}
	*hash = h;
	return 0;
}
