/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_run.h"
#include "garden_landing_internal.h"

#include <errno.h>

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
};

static int decide(const struct picosystem_garden_agent_observation *observation,
		  const struct picosystem_garden_agent_memory *memory,
		  struct picosystem_garden_agent_decision *decision, const void *context)
{
	const struct run_context *const ctx = context;
	struct picosystem_garden_landing_packet packet;
	const int err = picosystem_garden_landing_observe(ctx->cache, observation, &packet);
	if (err != 0) {
		return err;
	}
	return toy_factory_garden_landing_neural_decide(observation, memory, &packet, ctx->model,
							decision);
}

static int step(struct toy_factory_garden_landing_run *run,
		struct picosystem_garden_death_audit *audit)
{
	int err = validate(run);
	if (err != 0) {
		return err;
	}
	struct picosystem_garden_world world = run->world;
	struct picosystem_garden_landing_cache cache = run->cache;
	const struct run_context context = {.model = &run->model, .cache = &cache};
	const struct picosystem_garden_agent_policy policy = {
		.decide = decide,
		.context = &context,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS};
	err = (audit == NULL) ? picosystem_garden_world_step_landing(&world, &policy, &cache)
			      : picosystem_garden_world_step_landing_death_audit(&world, &policy,
										 &cache, audit);
	if (err != 0) {
		return err;
	}
	run->world = world;
	run->cache = cache;
	return 0;
}

int toy_factory_garden_landing_run_step(struct toy_factory_garden_landing_run *run)
{
	return step(run, NULL);
}

int toy_factory_garden_landing_run_step_death_audit(struct toy_factory_garden_landing_run *run,
						    struct picosystem_garden_death_audit *audit)
{
	return (audit == NULL) ? -EINVAL : step(run, audit);
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
