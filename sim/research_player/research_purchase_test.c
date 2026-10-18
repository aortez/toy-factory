/* SPDX-License-Identifier: Apache-2.0 */
#include "research_purchase.h"
#include "research_session.h"
#include "research_fallback.h"
#include "garden_dispersal.h"
#include "garden_leaf_family.h"

#include <assert.h>
#include <errno.h>
#include <string.h>

static unsigned int original_calls;
static int original_failure;

int __real_research_fallback_step_owned(struct toy_factory_leaf_replay *run,
					struct picosystem_garden_death_audit *deaths,
					struct picosystem_garden_seed_audit *seeds,
					struct picosystem_garden_resource_audit *resources,
					const struct toy_factory_garden_growth_observer *observer,
					const struct toy_factory_leaf_replay_route *leaf,
					const struct research_fallback_route *placement);

int __wrap_research_fallback_step_owned(struct toy_factory_leaf_replay *run,
					struct picosystem_garden_death_audit *deaths,
					struct picosystem_garden_seed_audit *seeds,
					struct picosystem_garden_resource_audit *resources,
					const struct toy_factory_garden_growth_observer *observer,
					const struct toy_factory_leaf_replay_route *leaf,
					const struct research_fallback_route *placement)
{
	if (original_failure == 0) {
		return __real_research_fallback_step_owned(run, deaths, seeds, resources, observer,
							   leaf, placement);
	}
	const struct toy_factory_leaf_replay saved = *run;
	memset(deaths, 0xa5, sizeof(*deaths));
	memset(seeds, 0xa5, sizeof(*seeds));
	memset(resources, 0xa5, sizeof(*resources));
	const struct picosystem_garden_death_audit saved_deaths = *deaths;
	const struct picosystem_garden_seed_audit saved_seeds = *seeds;
	const struct picosystem_garden_resource_audit saved_resources = *resources;
	const int err = __real_research_fallback_step_owned(run, deaths, seeds, resources, observer,
							    leaf, placement);
	if (err != 0) {
		assert(err == original_failure && memcmp(run, &saved, sizeof(saved)) == 0);
		assert(memcmp(deaths, &saved_deaths, sizeof(*deaths)) == 0);
		assert(memcmp(seeds, &saved_seeds, sizeof(*seeds)) == 0);
		assert(memcmp(resources, &saved_resources, sizeof(*resources)) == 0);
	}
	return err;
}

int __real_toy_factory_garden_placement_decide(const struct picosystem_garden_seed_placement *o,
					       uint8_t *choice, const void *context);
int __wrap_toy_factory_garden_placement_decide(const struct picosystem_garden_seed_placement *o,
					       uint8_t *choice, const void *context)
{
	++original_calls;
	return original_failure ? original_failure
				: __real_toy_factory_garden_placement_decide(o, choice, context);
}

static void callback_tests(void)
{
	struct research_purchase *trace = NULL;
	assert(research_purchase_open(NULL) == -EINVAL);
	assert(research_purchase_open(&trace) == 0);
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_SHRUB, 13U) ==
	       0);
	struct picosystem_garden_seed_placement o = {.parent = world.plants[0].lineage_id,
						     .origin = world.plants[0].base_column,
						     .dispersal = world.plants[0].genome.dispersal,
						     .random = 7U};
	const struct toy_factory_garden_placement_config config = {.version = 1U, .enabled = 1U};
	const struct toy_factory_garden_placement_context base = {.world = &world,
								  .config = &config};
	const struct toy_factory_garden_growth_observer observer = {
		.observe = research_purchase_growth, .context = trace};
	struct research_purchase_context context = {.base = &base, .observer = &observer};
	for (uint8_t c = 0U; c < PICOSYSTEM_GARDEN_PLACEMENT_CHOICES; ++c) {
		o.columns[c] = picosystem_garden_dispersed_column_at(o.origin, o.dispersal, c, 0U);
		for (uint8_t p = 0U; p < world.plant_count; ++p) {
			const int gap = (int)o.columns[c] - world.plants[p].base_column;
			if (gap > -3 && gap < 3) {
				o.blocked_choices |= (uint16_t)(1U << c);
			}
		}
	}
	uint8_t expected;
	assert(toy_factory_garden_placement_choose(&o, 1U, &expected) == 0);
	FILE *const output = tmpfile();
	assert(output != NULL);
	assert(research_purchase_write(trace, RESEARCH_PURCHASE_END - 1U, output) == -ERANGE);
	assert(ftell(output) == 0L);
	const uint32_t ticks[] = {RESEARCH_PURCHASE_BEGIN - 1U, RESEARCH_PURCHASE_END,
				  RESEARCH_PURCHASE_BEGIN, RESEARCH_PURCHASE_END - 1U};
	original_calls = 0U;
	for (size_t i = 0U; i < sizeof(ticks) / sizeof(ticks[0]); ++i) {
		world.logic_tick_count = ticks[i];
		o.logic_tick = ticks[i];
		const struct picosystem_garden_world saved = world;
		uint8_t selected = UINT8_MAX;
		assert(research_purchase_decide(&o, &selected, &context) == 0);
		assert(selected == expected && original_calls == i + 1U);
		assert(memcmp(&saved, &world, sizeof(world)) == 0);
	}
	uint8_t selected = UINT8_MAX;
	original_failure = -EIO;
	assert(research_purchase_decide(&o, &selected, &context) == -EIO);
	assert(selected == UINT8_MAX);
	original_failure = 0;
	for (uint16_t i = 2U; i < RESEARCH_PURCHASE_LIMIT; ++i) {
		assert(research_purchase_decide(&o, &selected, &context) == 0);
	}
	const unsigned int saved_calls = original_calls;
	selected = UINT8_MAX;
	assert(research_purchase_decide(&o, &selected, &context) == -ENOSPC);
	assert(selected == UINT8_MAX && original_calls == saved_calls);
	context.observer = NULL;
	assert(research_purchase_decide(&o, &selected, &context) == 0);
	assert(original_calls == saved_calls + 1U);
	assert(research_purchase_write(trace, RESEARCH_PURCHASE_END, output) == 0);
	assert(ftell(output) > 0L && fclose(output) == 0);
	FILE *const full = fopen("/dev/full", "w");
	assert(full != NULL && research_purchase_write(trace, RESEARCH_PURCHASE_END, full) == -EIO);
	(void)fclose(full);
	research_purchase_close(trace);
	research_purchase_close(NULL);
}

void research_purchase_tests(void)
{
	callback_tests();
	for (uint8_t fallback = 0U; fallback < 2U; ++fallback) {
		const struct research_options options = {.seed = UINT32_C(0x9a903368),
							 .model = 1U,
							 .scope = RESEARCH_SCOPE_POPULATION};
		struct research_session *off = NULL, *on = NULL;
		assert(research_session_purchase_start(NULL) == -EINVAL);
		assert(research_session_open(&options, &on) == 0);
		assert(research_session_open(&options, &off) == 0);
		assert(research_session_purchase_start(on) == -EINVAL);
		assert(research_session_gate_start_early(on, 3U) == 0);
		assert(research_session_gate_start_early(off, 3U) == 0);
		if (fallback != 0U) {
			assert(research_session_fallback_start(on) == 0);
			assert(research_session_fallback_start(off) == 0);
			assert(research_session_fallback_start(on) == -EINVAL);
		}
		assert(research_session_purchase_start(on) == 0);
		assert(research_session_purchase_start(on) == -EINVAL);
		FILE *const output = tmpfile();
		assert(output != NULL);
		assert(research_session_purchase_write(on, output) == -ERANGE);
		assert(ftell(output) == 0L);
		assert(research_session_step(on, RESEARCH_PURCHASE_END) == 0);
		assert(research_session_step(off, RESEARCH_PURCHASE_END) == 0);
		uint8_t first[TOY_FACTORY_LEAF_FAMILY_MAX_STATE_BYTES + 184U +
			      RESEARCH_FALLBACK_HEADER_BYTES],
			second[sizeof(first)];
		size_t size, other_size;
		assert(research_session_encode(on, first, sizeof(first), &size) == 0);
		assert(research_session_encode(off, second, sizeof(second), &other_size) == 0);
		assert(size == other_size && memcmp(first, second, size) == 0);
		assert(memcmp(first, fallback ? "TBF1" : "TGR1", 4U) == 0);
		assert(research_session_fallback_start(off) == -EINVAL);
		assert(research_session_purchase_write(on, output) == 0 && ftell(output) > 0L);
		assert(fclose(output) == 0);
		assert(research_session_reset(&on) == 0);
		FILE *const failed = tmpfile();
		assert(failed != NULL);
		assert(research_session_purchase_write(on, failed) == -EINVAL);
		assert(research_session_purchase_start(on) == -EINVAL);
		assert(research_session_gate_start_early(on, 3U) == 0);
		if (fallback != 0U) {
			assert(research_session_fallback_start(on) == 0);
		}
		assert(research_session_purchase_start(on) == 0);
		assert(research_session_step(on, RESEARCH_PURCHASE_BEGIN) == 0);
		original_failure = -EIO;
		assert(research_session_step(on, RESEARCH_PURCHASE_END - RESEARCH_PURCHASE_BEGIN) ==
		       -EIO);
		original_failure = 0;
		assert(research_session_step(on, 0U) == -EIO);
		assert(research_session_purchase_write(on, failed) == -EIO);
		assert(research_session_write_json(on, failed, NULL) == -EIO);
		assert(ftell(failed) == 0L && fclose(failed) == 0);
		assert(research_session_reset(&on) == 0);
		assert(research_session_encode(on, first, sizeof(first), &size) == 0);
		assert(memcmp(first, "TPR1", 4U) == 0);
		assert(research_session_step(on, 1U) == 0);
		research_session_close(on);
		research_session_close(off);
	}
}
