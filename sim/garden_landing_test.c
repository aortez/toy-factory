/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_evaluation.h"
#include "garden_landing_internal.h"
#include "garden_seed_audit.h"
#include "garden_dispersal.h"

struct test_context {
	const struct picosystem_garden_world *world;
	const struct picosystem_garden_landing_cache *cache;
	const struct picosystem_garden_agent_policy *base;
	unsigned int *queries;
};

static int inspect_decide(const struct picosystem_garden_agent_observation *observation,
			  const struct picosystem_garden_agent_memory *memory,
			  struct picosystem_garden_agent_decision *decision, const void *context)
{
	const struct test_context *const ctx = context;
	assert(ctx->cache->ecology_tick == ctx->world->ecology_tick_count);
	const struct picosystem_garden_landing_cache cache_before = *ctx->cache;
	const struct picosystem_garden_agent_observation before = *observation;
	struct picosystem_garden_landing_packet first, second;
	assert(picosystem_garden_landing_observe(ctx->cache, observation, &first) == 0);
	assert(picosystem_garden_landing_observe(ctx->cache, observation, &second) == 0);
	assert(memcmp(&first, &second, sizeof(first)) == 0);
	assert(memcmp(&cache_before, ctx->cache, sizeof(cache_before)) == 0);
	assert(memcmp(&before, observation, sizeof(before)) == 0);
	assert(first.warmup_samples == ctx->cache->warmup_samples);
	if (observation->tissue_kind == PICOSYSTEM_GARDEN_NODE_ROOT) {
		assert(first.valid == 0U);
	} else {
		assert(first.valid & 1U);
	}
	for (uint8_t i = 0U; i < PICOSYSTEM_GARDEN_LANDING_SOURCES; ++i) {
		if ((first.valid & (1U << i)) == 0U) {
			const uint8_t zero[PICOSYSTEM_GARDEN_LANDING_FIELDS] = {0};
			assert(memcmp(first.values[i], zero, sizeof(zero)) == 0);
		}
#if !defined(TOY_FACTORY_GARDEN_FLOWER_DISPERSAL)
		else {
			assert(memcmp(first.values[0], first.values[i], sizeof(first.values[i])) ==
			       0);
		}
#endif
	}
	++*ctx->queries;
	return picosystem_garden_agent_decide(ctx->base, observation, memory, decision);
}

static int fail_decide(const struct picosystem_garden_agent_observation *observation,
		       const struct picosystem_garden_agent_memory *memory,
		       struct picosystem_garden_agent_decision *decision, const void *context)
{
	(void)observation;
	(void)memory;
	(void)decision;
	(void)context;
	return -EIO;
}

static void reset(struct picosystem_garden_world *world)
{
	assert(picosystem_garden_world_reset(world, 123U) == 0);
	world->auto_gardener_enabled = false;
	assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 0U) ==
	       0);
}

static void boundaries(void)
{
	struct picosystem_garden_world world;
	reset(&world);
	struct picosystem_garden_landing_cache cache;
	memset(&cache, 0x5a, sizeof(cache));
	const struct picosystem_garden_landing_cache sentinel = cache;
	assert(picosystem_garden_landing_reset(NULL, &cache) == -EINVAL);
	assert(picosystem_garden_landing_reset(&world, NULL) == -EINVAL);
	world.auto_gardener_enabled = true;
	assert(picosystem_garden_landing_reset(&world, &cache) == -EINVAL);
	world.auto_gardener_enabled = false;
	world.logic_tick_count = 1U;
	assert(picosystem_garden_landing_reset(&world, &cache) == -EINVAL);
	assert(memcmp(&cache, &sentinel, sizeof(cache)) == 0);
	world.logic_tick_count = 0U;
	assert(picosystem_garden_landing_reset(&world, &cache) == 0);
	const struct picosystem_garden_landing_cache initial = cache;
	const struct picosystem_garden_world initial_world = world;
	const struct picosystem_garden_agent_policy *const base =
		picosystem_garden_agent_baseline_policy();
	assert(picosystem_garden_world_step_landing(&world, NULL, &cache) == -EINVAL);
	assert(picosystem_garden_world_step_landing(NULL, base, &cache) == -EINVAL);
	assert(picosystem_garden_world_step_landing(&world, base, NULL) == -EINVAL);
	assert(memcmp(&world, &initial_world, sizeof(world)) == 0);
	assert(memcmp(&cache, &initial, sizeof(cache)) == 0);
	cache.version = 2U;
	assert(picosystem_garden_world_step_landing(&world, base, &cache) == -EINVAL);
	cache = initial;
	cache.traces[0][0] = 1U;
	assert(!picosystem_garden_landing_cache_is_valid(&cache));
	cache = initial;
	cache.occupied[27] = 4U;
	assert(!picosystem_garden_landing_cache_is_valid(&cache));
	cache = initial;
	assert(picosystem_garden_landing_capture(&world, false, &cache) == -EINVAL);
	world.ecology_tick_count = 2U;
	assert(picosystem_garden_landing_capture(&world, false, &cache) == -EINVAL);
	assert(picosystem_garden_world_step_landing(&world, base, &cache) == -EINVAL);
	assert(memcmp(&cache, &initial, sizeof(cache)) == 0);
	world = initial_world;
	world.logic_tick_count = UINT32_MAX;
	assert(picosystem_garden_world_step_landing(&world, base, &cache) == -EINVAL);
	world = initial_world;
	world.logic_tick_count = 14U;
	world.plants[0].growth_cooldown = 0U;
	const struct picosystem_garden_agent_policy failing = {.decide = fail_decide};
	assert(picosystem_garden_world_step_landing(&world, &failing, &cache) == -EIO);
	assert(world.ecology_tick_count == 1U);
	assert(memcmp(&cache, &initial, sizeof(cache)) == 0);
	assert(picosystem_garden_world_step_landing(&world, base, &cache) == -EINVAL);
}

static void phase_and_traces(void)
{
	struct picosystem_garden_world world;
	reset(&world);
	memset(world.moisture, UINT8_MAX, sizeof(world.moisture));
	world.seed_count = 1U;
	world.seeds[0] = (struct picosystem_garden_seed){
		.parent_lineage_id = 1U,
		.generation = 1U,
		.column = 14U,
		.species_id = PICOSYSTEM_GARDEN_SPECIES_FLOWER,
		.age_ecology_ticks = 7U,
	};
	struct picosystem_garden_landing_cache cache;
	assert(picosystem_garden_landing_reset(&world, &cache) == 0);
	world.logic_tick_count = 14U;
	struct picosystem_garden_world audited = world;
	struct picosystem_garden_seed_audit seeds;
	const struct picosystem_garden_agent_policy *const base =
		picosystem_garden_agent_baseline_policy();
	assert(picosystem_garden_world_step_seed_audit(&audited, base, &seeds) == 0);
	assert(picosystem_garden_world_step_landing(&world, base, &cache) == 0);
	assert(memcmp(&world, &audited, sizeof(world)) == 0);
	assert(seeds.count == 1U && seeds.attempts[0].outcome == PICOSYSTEM_GARDEN_SEED_GERMINATED);
	assert(cache.water[14] == seeds.attempts[0].moisture - 12U);
	assert(cache.light[14] == seeds.attempts[0].light);
	assert(cache.occupied[14] == PICOSYSTEM_GARDEN_LANDING_LIVE);
	assert(cache.warmup_samples == 1U);
	assert(cache.traces[0][14] == 255U);
	assert(cache.traces[3][14] == 0U);
	reset(&world);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 3U) ==
	       0);
	world.plants[0].flags = PICOSYSTEM_GARDEN_PLANT_DEAD;
	assert(picosystem_garden_landing_capture(&world, true, &cache) == 0);
	assert(cache.occupied[0] == PICOSYSTEM_GARDEN_LANDING_DEAD);
	assert(cache.occupied[1] ==
	       (PICOSYSTEM_GARDEN_LANDING_LIVE | PICOSYSTEM_GARDEN_LANDING_DEAD));
	assert(cache.occupied[3] == PICOSYSTEM_GARDEN_LANDING_LIVE);
	const struct picosystem_garden_landing_cache occupied = cache;
	const struct picosystem_garden_plant swap = world.plants[0];
	world.plants[0] = world.plants[1];
	world.plants[1] = swap;
	assert(picosystem_garden_landing_capture(&world, true, &cache) == 0);
	assert(memcmp(&cache, &occupied, sizeof(cache)) == 0);
	reset(&world);
	world.plant_count = 0U;
	world.node_count = 0U;
	memset(world.moisture, 0, sizeof(world.moisture));
	memset(world.light, 0, sizeof(world.light));
	assert(picosystem_garden_landing_reset(&world, &cache) == 0);
	for (uint32_t tick = 1U; tick <= 512U; ++tick) {
		world.ecology_tick_count = tick;
		world.moisture[0] = (tick & 1U) ? 12U : 11U;
		world.light[(PICOSYSTEM_GARDEN_CANOPY_ROWS - 1U) * PICOSYSTEM_GARDEN_GRID_COLUMNS] =
			(tick & 1U) ? 79U : 80U;
		assert(picosystem_garden_landing_capture(&world, false, &cache) == 0);
	}
	assert(cache.traces[0][0] > 0U && cache.traces[1][0] > 0U);
	assert(cache.traces[2][0] == 0U && cache.traces[3][0] == 0U);
	assert(cache.warmup_samples == 256U);
	cache.traces[0][0] = UINT16_MAX;
	assert(!picosystem_garden_landing_cache_is_valid(&cache));
	cache.traces[0][0] = 0U;
	cache.ecology_tick = UINT32_MAX;
	assert(picosystem_garden_landing_capture(&world, false, &cache) == -EINVAL);
}

static void geometry_and_queries(void)
{
	struct picosystem_garden_world world;
	reset(&world);
	struct picosystem_garden_landing_cache cache;
	assert(picosystem_garden_landing_reset(&world, &cache) == 0);
	struct picosystem_garden_agent_observation observation;
	assert(picosystem_garden_agent_observe_tip(&world, 0U, 1U, 0U, &observation) == 0);
	assert(observation.tissue_kind == PICOSYSTEM_GARDEN_NODE_STEM);
	struct picosystem_garden_landing_packet packet;
	memset(&packet, 0x5a, sizeof(packet));
	const struct picosystem_garden_landing_packet sentinel = packet;
	assert(picosystem_garden_landing_observe(NULL, &observation, &packet) == -EINVAL);
	assert(picosystem_garden_landing_observe(&cache, NULL, &packet) == -EINVAL);
	assert(picosystem_garden_landing_observe(&cache, &observation, NULL) == -EINVAL);
	assert(memcmp(&packet, &sentinel, sizeof(packet)) == 0);
	/* A vertically OOB endpoint must be masked even if its x is on screen. */
	observation.candidates[0].x = 12U;
	observation.candidates[0].flags = 0U;
	assert(picosystem_garden_landing_observe(&cache, &observation, &packet) == 0);
	assert((packet.valid & 2U) == 0U);
	observation.candidates[0].flags = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS |
					  PICOSYSTEM_GARDEN_AGENT_CANDIDATE_OWN_NEAR;
	assert(picosystem_garden_landing_observe(&cache, &observation, &packet) == 0);
	assert(packet.valid & 2U);
	const struct picosystem_garden_landing_packet first = packet;
	const struct picosystem_garden_agent_candidate swap = observation.candidates[0];
	observation.candidates[0] = observation.candidates[4];
	observation.candidates[4] = swap;
	assert(picosystem_garden_landing_observe(&cache, &observation, &packet) == 0);
	assert(memcmp(first.values[1], packet.values[5], sizeof(first.values[1])) == 0);
	assert(memcmp(first.values[5], packet.values[1], sizeof(first.values[1])) == 0);
	for (uint8_t column = 0U; column < 28U; ++column) {
		for (int8_t trait = -2; trait <= 2; ++trait) {
			for (uint32_t branch = 0U;
			     branch < 2U * PICOSYSTEM_GARDEN_DISPERSAL_CHOICES; ++branch) {
				const int offset = ((branch & 1U) ? 1 : -1) *
						   (PICOSYSTEM_GARDEN_DISPERSAL_MINIMUM + trait +
						    (int)(branch / 2U));
				int expected = column + offset;
				if ((expected < 0) || (expected >= 28)) {
					expected = column - offset;
				}
				assert(picosystem_garden_dispersed_column(column, trait, branch) ==
				       expected);
			}
		}
	}
}

static void trajectories(void)
{
	for (unsigned int p = 0U; p < 2U; ++p) {
		struct picosystem_garden_world plain;
		assert(toy_factory_garden_evaluation_reset(
			       &plain, &toy_factory_garden_rainfed_scenarios[1], 0xed52188cU) == 0);
		assert(picosystem_garden_world_set_climate(
			       &plain, PICOSYSTEM_GARDEN_CLIMATE_SEASONAL) == 0);
		struct picosystem_garden_world observed = plain;
		struct picosystem_garden_landing_cache cache;
		assert(picosystem_garden_landing_reset(&observed, &cache) == 0);
		unsigned int queries = 0U;
		const struct picosystem_garden_agent_policy *const base =
			p ? picosystem_garden_agent_adaptive_policy()
			  : picosystem_garden_agent_baseline_policy();
		const struct test_context context = {
			.world = &observed, .cache = &cache, .base = base, .queries = &queries};
		struct picosystem_garden_agent_policy policy = *base;
		policy.decide = inspect_decide;
		policy.context = &context;
		for (uint32_t tick = 1U; tick <= 32U * 3840U; ++tick) {
			const struct picosystem_garden_landing_cache before = cache;
			assert(picosystem_garden_world_step_with_policy(&plain, base) == 0);
			assert(picosystem_garden_world_step_landing(&observed, &policy, &cache) ==
			       0);
			assert(memcmp(&plain, &observed, sizeof(plain)) == 0);
			assert(cache.ecology_tick == tick / 15U);
			if ((tick % 15U) != 0U) {
				assert(memcmp(&cache, &before, sizeof(cache)) == 0);
			}
			if (tick == 3840U) {
				const struct picosystem_garden_world saved = observed;
				const struct picosystem_garden_landing_cache saved_cache = cache;
				for (unsigned int i = 0U; i < 15U; ++i) {
					assert(picosystem_garden_world_step_landing(
						       &observed, &policy, &cache) == 0);
				}
				const struct picosystem_garden_world next = observed;
				const struct picosystem_garden_landing_cache next_cache = cache;
				observed = saved;
				cache = saved_cache;
				for (unsigned int i = 0U; i < 15U; ++i) {
					assert(picosystem_garden_world_step_landing(
						       &observed, &policy, &cache) == 0);
				}
				assert(memcmp(&observed, &next, sizeof(next)) == 0);
				assert(memcmp(&cache, &next_cache, sizeof(cache)) == 0);
				observed = saved;
				cache = saved_cache;
			}
		}
		assert(queries > 100U);
	}
}

int main(void)
{
	boundaries();
	phase_and_traces();
	geometry_and_queries();
	trajectories();
	puts("Landing observer phase, geometry, failure, replay and byte-identical world checks "
	     "passed");
	return 0;
}
