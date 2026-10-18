/* SPDX-License-Identifier: Apache-2.0 */
#include "research_session.h"
#include "research_shadow.h"
#include "research_gate.h"
#include "research_purchase.h"
#include "research_reproduction.h"
#include "research_budget.h"
#include "research_foliage.h"
#include "research_canopy.h"
#include "research_fallback.h"
#include "garden_leaf_owned_internal.h"
#include "garden_landing_ledger.h"
#include "garden_maintenance_step.h"

#include <assert.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>

static struct toy_factory_leaf_replay observed;
static unsigned int allocations;
static unsigned int checked_steps;
static bool fail_allocation;
static bool fail_audit;
static bool check_steps;
static bool fail_trace;
static bool fail_shadow;
static bool fail_reproduction;
static bool corrupt_canopy;

int __real_research_canopy_project(const struct picosystem_garden_world *before,
				   struct picosystem_garden_uptake_audit *out);
int __wrap_research_canopy_project(const struct picosystem_garden_world *before,
				   struct picosystem_garden_uptake_audit *out)
{
	const int err = __real_research_canopy_project(before, out);
	if (err == 0 && corrupt_canopy) {
		out->light[0] ^= 1U;
	}
	return err;
}

void research_purchase_tests(void);
void research_fallback_tests(void);
void research_reproduction_tests(void);
void research_budget_tests(void);
void research_foliage_tests(void);

int __real_research_reproduction_record(struct research_reproduction *trace, uint32_t tick,
					const struct picosystem_garden_reproduction_audit *audit);
int __wrap_research_reproduction_record(struct research_reproduction *trace, uint32_t tick,
					const struct picosystem_garden_reproduction_audit *audit)
{
	return fail_reproduction ? -EIO : __real_research_reproduction_record(trace, tick, audit);
}

int __real_research_shadow_decide(const struct picosystem_garden_world *world,
				  const struct picosystem_garden_leaf_policy *candidate,
				  const struct picosystem_garden_leaf_observation *observation,
				  const struct picosystem_garden_agent_memory *memory,
				  struct picosystem_garden_leaf_decision *decision,
				  const void *context);
int __wrap_research_shadow_decide(const struct picosystem_garden_world *world,
				  const struct picosystem_garden_leaf_policy *candidate,
				  const struct picosystem_garden_leaf_observation *observation,
				  const struct picosystem_garden_agent_memory *memory,
				  struct picosystem_garden_leaf_decision *decision,
				  const void *context)
{
	return fail_shadow ? -EIO
			   : __real_research_shadow_decide(world, candidate, observation, memory,
							   decision, context);
}

int __real_toy_factory_maintenance_step_read(const struct picosystem_garden_world *before,
					     const struct picosystem_garden_world *after,
					     const struct picosystem_garden_resource_audit *audit,
					     struct toy_factory_maintenance_step *out);
int __wrap_toy_factory_maintenance_step_read(const struct picosystem_garden_world *before,
					     const struct picosystem_garden_world *after,
					     const struct picosystem_garden_resource_audit *audit,
					     struct toy_factory_maintenance_step *out)
{
	return fail_trace ? -EOVERFLOW
			  : __real_toy_factory_maintenance_step_read(before, after, audit, out);
}

void *__real_calloc(size_t count, size_t size);
void *__wrap_calloc(size_t count, size_t size)
{
	++allocations;
	return fail_allocation ? NULL : __real_calloc(count, size);
}

void *__real_malloc(size_t size);
void *__wrap_malloc(size_t size)
{
	++allocations;
	return fail_allocation ? NULL : __real_malloc(size);
}

int __real_toy_factory_garden_landing_ledger_step(
	struct toy_factory_garden_landing_ledger *out, const struct picosystem_garden_world *world,
	const struct toy_factory_garden_lifetimes *lifetimes,
	const struct picosystem_garden_seed_audit *audit);
int __wrap_toy_factory_garden_landing_ledger_step(
	struct toy_factory_garden_landing_ledger *out, const struct picosystem_garden_world *world,
	const struct toy_factory_garden_lifetimes *lifetimes,
	const struct picosystem_garden_seed_audit *audit)
{
	const int err = __real_toy_factory_garden_landing_ledger_step(out, world, lifetimes, audit);
	return ((err == 0) && fail_audit) ? -ENOSPC : err;
}

int __real_toy_factory_leaf_replay_step_owned(
	struct toy_factory_leaf_replay *run, struct picosystem_garden_death_audit *deaths,
	struct picosystem_garden_seed_audit *seeds,
	struct picosystem_garden_resource_audit *resources,
	const struct toy_factory_garden_growth_observer *observer,
	const struct toy_factory_leaf_replay_route *route);
int __wrap_toy_factory_leaf_replay_step_owned(
	struct toy_factory_leaf_replay *run, struct picosystem_garden_death_audit *deaths,
	struct picosystem_garden_seed_audit *seeds,
	struct picosystem_garden_resource_audit *resources,
	const struct toy_factory_garden_growth_observer *observer,
	const struct toy_factory_leaf_replay_route *route)
{
	assert(observer == NULL || observer->observe == research_purchase_growth ||
	       observer->observe == research_reproduction_growth);
	struct toy_factory_leaf_replay reference = *run;
	const int err = __real_toy_factory_leaf_replay_step_owned(run, deaths, seeds, resources,
								  observer, route);
	if ((err == 0) && check_steps) {
		struct picosystem_garden_death_audit expected_deaths;
		struct picosystem_garden_seed_audit expected_seeds;
		struct picosystem_garden_resource_audit expected_resources;
		assert(toy_factory_leaf_replay_step(&reference, &expected_deaths, &expected_seeds,
						    &expected_resources, NULL) == 0);
		uint8_t first[TOY_FACTORY_LEAF_REPLAY_STATE_BYTES], second[sizeof(first)];
		size_t first_size, second_size;
		assert(toy_factory_leaf_replay_encode(run, first, sizeof(first), &first_size) == 0);
		assert(toy_factory_leaf_replay_encode(&reference, second, sizeof(second),
						      &second_size) == 0);
		assert(first_size == second_size && memcmp(first, second, first_size) == 0);
		assert(deaths->count == expected_deaths.count &&
		       seeds->count == expected_seeds.count);
		++checked_steps;
	}
	if (err == 0) {
		observed = *run;
	}
	return err;
}

static void verify(struct research_session *session)
{
	const struct picosystem_garden_world *const world = &observed.base.growth.base.world;
	uint8_t bytes[TOY_FACTORY_LEAF_FAMILY_MAX_STATE_BYTES];
	uint8_t inner[TOY_FACTORY_LEAF_REPLAY_STATE_BYTES];
	size_t size, inner_size;
	assert(research_session_encode(session, bytes, sizeof(bytes), &size) == 0);
	assert(memcmp(bytes, "TPR1", 4U) == 0 && bytes[4] == 0U && bytes[5] == 0U);
	assert(bytes[7] == 0U);
	uint32_t count = 0U;
	for (uint8_t i = 0U; i < 4U; ++i) {
		count |= (uint32_t)bytes[8U + i] << (8U * i);
	}
	assert(count == world->lineage_sequence);
	assert(size == 12U + count + sizeof(inner));
	assert(toy_factory_leaf_replay_encode(&observed, inner, sizeof(inner), &inner_size) == 0);
	assert(memcmp(bytes + 12U + count, inner, inner_size) == 0);
	const uint8_t *const roots = bytes + 11U;
	for (uint32_t id = 1U; id <= count; ++id) {
		assert(roots[id] >= 1U && roots[id] <= bytes[6]);
		assert(id > bytes[6] || roots[id] == id);
	}
	struct research_status status;
	struct research_family_view view;
	assert(research_session_status(session, &status) == 0);
	assert(research_session_family_view(session, &view) == 0);
	assert(status.tick == world->logic_tick_count && view.tick == status.tick);
	uint32_t living = 0U;
	uint16_t segments = 0U;
	for (uint8_t i = 0U; i < world->plant_count; ++i) {
		const struct picosystem_garden_plant *const plant = &world->plants[i];
		if (plant->parent_lineage_id != 0U) {
			assert(roots[plant->lineage_id] == roots[plant->parent_lineage_id]);
		}
		living += (plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) == 0U ? 1U : 0U;
	}
	for (uint16_t i = 0U; i < world->node_count; ++i) {
		const struct picosystem_garden_plant *const plant =
			&world->plants[world->nodes[i].plant_index];
		if ((plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) == 0U) {
			assert(view.segments[segments++].lineage == plant->lineage_id);
		}
	}
	assert(status.living == living && view.living == living);
	assert(view.segment_count == segments && status.pending == world->seed_count);
	assert(view.seed_count == world->seed_count);
	for (uint8_t i = 0U; i < world->seed_count; ++i) {
		assert(view.seeds[i].parent == world->seeds[i].parent_lineage_id);
	}
}

static void compare_render_and_reset(struct research_session **session,
				     const struct research_options *options)
{
	uint8_t before[TOY_FACTORY_LEAF_FAMILY_MAX_STATE_BYTES], after[sizeof(before)];
	size_t before_size, after_size;
	assert(research_session_encode(*session, before, sizeof(before), &before_size) == 0);
	uint8_t pixels[RESEARCH_FRAME_BYTES];
	uint32_t crc;
	assert(research_session_render(*session, pixels, sizeof(pixels), &crc) == 0);
	assert(research_session_encode(*session, after, sizeof(after), &after_size) == 0);
	assert(before_size == after_size && memcmp(before, after, before_size) == 0);
	assert(research_session_encode(*session, after, 0U, &after_size) == -ENOSPC);
	assert(before_size == after_size && memcmp(before, after, before_size) == 0);
	assert(research_session_reset(session) == 0);
	struct research_session *fresh = NULL;
	assert(research_session_open(options, &fresh) == 0);
	assert(research_session_encode(*session, before, sizeof(before), &before_size) == 0);
	assert(research_session_encode(fresh, after, sizeof(after), &after_size) == 0);
	assert(before_size == after_size && memcmp(before, after, before_size) == 0);
	research_session_close(fresh);
}

static void trace_tests(void)
{
	struct research_options options = {.seed = UINT32_C(0x58d7d6ca),
					   .scope = RESEARCH_SCOPE_POPULATION};
	struct research_session *session = NULL;
	assert(research_session_trace_start(NULL, 2U) == -EINVAL);
	assert(research_session_open(&options, &session) == 0);
	FILE *const output = tmpfile();
	assert(output != NULL);
	assert(research_session_trace_write(session, output) == -EINVAL);
	assert(research_session_trace_start(session, 0U) == -EINVAL);
	assert(research_session_trace_start(session, 4U) == -EINVAL);
	fail_allocation = true;
	assert(research_session_trace_start(session, 2U) == -ENOMEM);
	fail_allocation = false;
	assert(research_session_trace_start(session, 2U) == 0);
	assert(research_session_trace_start(session, 2U) == -EINVAL);
	assert(research_session_step(session, 256U * RESEARCH_DAY_TICKS + 1U) == -ERANGE);
	struct research_status status;
	assert(research_session_status(session, &status) == 0 && status.tick == 0U);
	const unsigned int opened = allocations;
	assert(research_session_step(session, 14U) == 0);
	assert(allocations == opened);
	fail_trace = true;
	assert(research_session_step(session, 1U) == -EOVERFLOW);
	fail_trace = false;
	assert(research_session_step(session, 0U) == -EOVERFLOW);
	assert(research_session_write_json(session, output, NULL) == -EOVERFLOW);
	assert(research_session_trace_write(session, output) == -EOVERFLOW);
	assert(ftell(output) == 0L);
	assert(research_session_reset(&session) == 0);
	assert(research_session_trace_write(session, output) == -EINVAL);
	assert(research_session_step(session, 1U) == 0);
	assert(research_session_trace_start(session, 2U) == -EINVAL);
	assert(fclose(output) == 0);
	research_session_close(session);
	options.scope = RESEARCH_SCOPE_FAMILY;
	options.founder = 1U;
	assert(research_session_open(&options, &session) == 0);
	assert(research_session_trace_start(session, 1U) == -EINVAL);
	research_session_close(session);
}

static void shadow_tests(void)
{
	struct research_options options = {.seed = UINT32_C(0x58d7d6ca),
					   .scope = RESEARCH_SCOPE_POPULATION};
	assert(research_session_shadow_start(NULL, 2U, 0U, 1U) == -EINVAL);
	for (uint8_t model = 0U; model < 3U; ++model) {
		options.model = model;
		struct research_session *session = NULL;
		assert(research_session_open(&options, &session) == 0);
		FILE *const output = tmpfile();
		assert(output != NULL);
		assert(research_session_shadow_write(session, output) == -EINVAL);
		assert(research_session_shadow_start(session, 0U, 0U, 1U) == -EINVAL);
		assert(research_session_shadow_start(session, 4U, 0U, 1U) == -EINVAL);
		assert(research_session_shadow_start(session, 2U, 1U, 1U) == -EINVAL);
		assert(research_session_shadow_start(session, 2U, 0U, 17U) == -EINVAL);
		assert(research_session_shadow_start(session, 2U, 255U, 257U) == -EINVAL);
		fail_allocation = true;
		assert(research_session_shadow_start(session, 2U, 0U, 1U) == -ENOMEM);
		fail_allocation = false;
		assert(research_session_shadow_start(session, 2U, 0U, 1U) == 0);
		assert(research_session_shadow_start(session, 2U, 0U, 1U) == -EINVAL);
		assert(research_session_shadow_write(session, output) == -ERANGE);
		assert(research_session_step(session, 256U * RESEARCH_DAY_TICKS + 1U) == -ERANGE);
		const unsigned int opened = allocations;
		check_steps = true;
		assert(research_session_step(session, RESEARCH_DAY_TICKS) == 0);
		check_steps = false;
		assert(allocations == opened);
		assert(ftell(output) == 0L);
		assert(research_session_shadow_write(session, output) == 0);
		assert(ftell(output) > 200L);
		assert(fclose(output) == 0);
		verify(session);
		assert(research_session_reset(&session) == 0);
		FILE *const failed = tmpfile();
		assert(failed != NULL);
		assert(research_session_shadow_write(session, failed) == -EINVAL);
		assert(research_session_shadow_start(session, 2U, 0U, 1U) == 0);
		fail_shadow = true;
		assert(research_session_step(session, RESEARCH_DAY_TICKS) == -EIO);
		fail_shadow = false;
		assert(research_session_step(session, 0U) == -EIO);
		assert(research_session_shadow_write(session, failed) == -EIO);
		assert(research_session_write_json(session, failed, NULL) == -EIO);
		assert(ftell(failed) == 0L && fclose(failed) == 0);
		assert(research_session_reset(&session) == 0);
		assert(research_session_step(session, 1U) == 0);
		assert(research_session_shadow_start(session, 2U, 0U, 1U) == -EINVAL);
		research_session_close(session);
	}
	options.scope = RESEARCH_SCOPE_FAMILY;
	options.founder = 1U;
	struct research_session *session = NULL;
	assert(research_session_open(&options, &session) == 0);
	assert(research_session_shadow_start(session, 1U, 0U, 1U) == -EINVAL);
	research_session_close(session);
}

void research_gate_routing_tests(void);

static void gate_tests(void)
{
	struct research_options options = {
		.seed = UINT32_C(0x58d7d6ca), .model = 1U, .scope = RESEARCH_SCOPE_POPULATION};
	struct research_session *session = NULL;
	assert(research_session_gate_start(NULL, 0U) == -EINVAL);
	assert(research_session_gate_continue(NULL) == -EINVAL);
	assert(research_session_open(&options, &session) == 0);
	assert(research_session_gate_continue(session) == -EINVAL);
	assert(research_session_gate_start(session, 4U) == -EINVAL);
	fail_allocation = true;
	assert(research_session_gate_start(session, 0U) == -ENOMEM);
	fail_allocation = false;
	for (uint8_t variant = 0U; variant < 4U; ++variant) {
		assert(research_session_gate_start(session, variant) == 0);
		assert(research_session_gate_continue(session) == -EINVAL);
		assert(research_session_gate_start(session, variant) == -EINVAL);
		assert(research_session_shadow_start(session, 2U, 0U, 1U) == -EINVAL);
		assert(research_session_step(session, 256U * RESEARCH_DAY_TICKS + 1U) == -ERANGE);
		uint8_t encoded[TOY_FACTORY_LEAF_FAMILY_MAX_STATE_BYTES +
				RESEARCH_GATE_HEADER_BYTES];
		size_t size;
		assert(research_session_encode(session, encoded, sizeof(encoded), &size) == 0);
		assert(memcmp(encoded, "TGR1", 4U) == 0 && encoded[4] == variant);
		assert(memcmp(encoded + RESEARCH_GATE_HEADER_BYTES, "TPR1", 4U) == 0);
		uint8_t small[RESEARCH_GATE_HEADER_BYTES + 1U];
		memset(small, 0x5a, sizeof(small));
		const size_t saved_size = size;
		assert(research_session_encode(session, small, sizeof(small), &size) == -ENOSPC);
		assert(size == saved_size);
		for (size_t i = 0U; i < sizeof(small); ++i) {
			assert(small[i] == 0x5a);
		}
		const unsigned int opened = allocations;
		check_steps = true;
		assert(research_session_step(session, 512U) == 0);
		check_steps = false;
		assert(allocations == opened);
		uint8_t pixels[RESEARCH_FRAME_BYTES];
		uint32_t crc;
		assert(research_session_render(session, pixels, sizeof(pixels), &crc) == 0);
		fail_audit = true;
		assert(research_session_step(session, 15U) == -ENOSPC);
		fail_audit = false;
		assert(research_session_gate_continue(session) == -ENOSPC);
		assert(research_session_encode(session, encoded, sizeof(encoded), &size) ==
		       -ENOSPC);
		assert(research_session_reset(&session) == 0);
		assert(research_session_encode(session, encoded, sizeof(encoded), &size) == 0);
		assert(memcmp(encoded, "TPR1", 4U) == 0);
	}
	assert(research_session_shadow_start(session, 2U, 0U, 1U) == 0);
	assert(research_session_gate_start(session, 0U) == -EINVAL);
	assert(research_session_reset(&session) == 0);
	assert(research_session_step(session, 1U) == 0);
	assert(research_session_gate_start(session, 0U) == -EINVAL);
	research_session_close(session);
	options.model = 0U;
	assert(research_session_open(&options, &session) == 0);
	assert(research_session_gate_start(session, 0U) == -EINVAL);
	research_session_close(session);
	research_gate_routing_tests();
}

static void gate_seed_tests(void)
{
	struct research_options options = {
		.seed = UINT32_C(0x59818bc3), .model = 1U, .scope = RESEARCH_SCOPE_POPULATION};
	struct research_session *session = NULL;
	assert(research_session_open(&options, &session) == 0);
	for (uint8_t variant = 0U; variant < 4U; ++variant) {
		uint8_t plain[TOY_FACTORY_LEAF_FAMILY_MAX_STATE_BYTES];
		uint8_t gated[sizeof(plain) + RESEARCH_GATE_HEADER_BYTES];
		size_t plain_size, gated_size;
		assert(research_session_encode(session, plain, sizeof(plain), &plain_size) == 0);
		assert(research_session_gate_start(session, variant) == 0);
		assert(research_session_encode(session, gated, sizeof(gated), &gated_size) == 0);
		assert(gated_size == plain_size + RESEARCH_GATE_HEADER_BYTES);
		assert(memcmp(gated + RESEARCH_GATE_HEADER_BYTES, plain, plain_size) == 0);
		const unsigned int opened = allocations;
		check_steps = true;
		assert(research_session_step(session, 512U) == 0);
		check_steps = false;
		assert(allocations == opened);
		assert(research_session_reset(&session) == 0);
	}
	research_session_close(session);
	/* Known ordinary replay seeds are not automatically intervention cases. */
	options.seed = UINT32_C(0x9a903368);
	assert(research_session_open(&options, &session) == 0);
	assert(research_session_gate_start(session, 0U) == -EINVAL);
	research_session_close(session);
}

static void gate_early_tests(void)
{
	static const uint32_t seeds[] = {UINT32_C(0x58d7d6ca), UINT32_C(0x9a903368),
					 UINT32_C(0x6b9c1a3e), UINT32_C(0x59818bc3)};
	struct research_options options = {.model = 1U, .scope = RESEARCH_SCOPE_POPULATION};
	assert(research_session_gate_start_early(NULL, 0U) == -EINVAL);
	for (size_t seed = 0U; seed < sizeof(seeds) / sizeof(seeds[0]); ++seed) {
		options.seed = seeds[seed];
		struct research_session *session = NULL;
		assert(research_session_open(&options, &session) == 0);
		assert(research_session_gate_start_early(session, 4U) == -EINVAL);
		fail_allocation = true;
		assert(research_session_gate_start_early(session, 0U) == -ENOMEM);
		fail_allocation = false;
		for (uint8_t variant = 0U; variant < 4U; ++variant) {
			uint8_t plain[TOY_FACTORY_LEAF_FAMILY_MAX_STATE_BYTES];
			uint8_t gated[sizeof(plain) + RESEARCH_GATE_HEADER_BYTES];
			size_t plain_size, gated_size;
			assert(research_session_encode(session, plain, sizeof(plain),
						       &plain_size) == 0);
			assert(memcmp(plain, "TPR1", 4U) == 0);
			assert(research_session_gate_start_early(session, variant) == 0);
			assert(research_session_gate_start_early(session, variant) == -EINVAL);
			assert(research_session_gate_start(session, variant) == -EINVAL);
			assert(research_session_shadow_start(session, 2U, 0U, 1U) == -EINVAL);
			assert(research_session_encode(session, gated, sizeof(gated),
						       &gated_size) == 0);
			assert(gated_size == plain_size + RESEARCH_GATE_HEADER_BYTES);
			assert(memcmp(gated, "TGR1", 4U) == 0 && gated[4] == variant);
			assert(gated[8] == 0U && gated[9] == 0U && gated[10] == 0U &&
			       gated[11] == 0U);
			assert(memcmp(gated + RESEARCH_GATE_HEADER_BYTES, plain, plain_size) == 0);
			const unsigned int opened = allocations;
			assert(research_session_step(session, 512U) == 0);
			assert(allocations == opened);
			fail_audit = true;
			assert(research_session_step(session, 15U) == -ENOSPC);
			fail_audit = false;
			assert(research_session_step(session, 0U) == -ENOSPC);
			assert(research_session_encode(session, gated, sizeof(gated),
						       &gated_size) == -ENOSPC);
			assert(research_session_reset(&session) == 0);
		}
		assert(research_session_shadow_start(session, 2U, 0U, 1U) == 0);
		assert(research_session_gate_start_early(session, 0U) == -EINVAL);
		assert(research_session_reset(&session) == 0);
		assert(research_session_step(session, 1U) == 0);
		assert(research_session_gate_start_early(session, 0U) == -EINVAL);
		research_session_close(session);
	}
	struct research_session *session = NULL;
	options.seed = UINT32_C(0x98a89374);
	assert(research_session_open(&options, &session) == 0);
	assert(research_session_gate_start_early(session, 0U) == -EINVAL);
	research_session_close(session);
	options.seed = seeds[0];
	options.model = 0U;
	assert(research_session_open(&options, &session) == 0);
	assert(research_session_gate_start_early(session, 0U) == -EINVAL);
	research_session_close(session);
}

static void gate_continue_tests(void)
{
	const struct research_options options = {
		.seed = UINT32_C(0x58d7d6ca), .model = 1U, .scope = RESEARCH_SCOPE_POPULATION};
	struct research_session *session = NULL;
	assert(research_session_open(&options, &session) == 0);
	assert(research_session_gate_start(session, 3U) == 0);
	assert(research_session_trace_start(session, 2U) == 0);
	const unsigned int opened = allocations;
	assert(research_session_step(session, 256U * RESEARCH_DAY_TICKS - 1U) == 0);
	assert(research_session_gate_continue(session) == -EINVAL);
	assert(research_session_step(session, 1U) == 0);
	assert(research_session_step(session, 1U) == -ERANGE);
	uint8_t before[TOY_FACTORY_LEAF_FAMILY_MAX_STATE_BYTES + RESEARCH_GATE_HEADER_BYTES];
	uint8_t after[sizeof(before)];
	size_t before_size, after_size;
	assert(research_session_encode(session, before, sizeof(before), &before_size) == 0);
	FILE *const prefix = tmpfile();
	FILE *const final = tmpfile();
	assert(prefix != NULL && final != NULL);
	assert(research_session_trace_write(session, prefix) == 0);
	assert(research_session_gate_continue(session) == 0);
	assert(research_session_gate_continue(session) == -EINVAL);
	assert(research_session_encode(session, after, sizeof(after), &after_size) == 0);
	assert(before_size == after_size && memcmp(before, after, before_size) == 0);
	assert(research_session_step(session, 352U * RESEARCH_DAY_TICKS + 1U) == -ERANGE);
	/* Continuing must neither record into the frozen prefix nor allocate. */
	fail_trace = true;
	assert(research_session_step(session, 352U * RESEARCH_DAY_TICKS) == 0);
	fail_trace = false;
	assert(allocations == opened);
	assert(research_session_step(session, 1U) == -ERANGE);
	assert(research_session_trace_write(session, final) == 0);
	rewind(prefix);
	rewind(final);
	int byte;
	do {
		byte = fgetc(prefix);
		assert(byte == fgetc(final));
	} while (byte != EOF);
	assert(!ferror(prefix) && !ferror(final));
	assert(fclose(prefix) == 0 && fclose(final) == 0);
	assert(research_session_reset(&session) == 0);
	assert(research_session_gate_continue(session) == -EINVAL);
	assert(research_session_gate_start(session, 0U) == 0);
	assert(research_session_step(session, 256U * RESEARCH_DAY_TICKS + 1U) == -ERANGE);
	research_session_close(session);
}

int main(void)
{
	bool descendant = false, reused = false, posthumous = false;
	for (uint8_t model = 0U; model < 3U; ++model) {
		for (uint8_t layout = 0U; layout < 2U; ++layout) {
			struct research_options options = {.seed = UINT32_C(0x58d7d6ca),
							   .model = model,
							   .layout = layout,
							   .scope = RESEARCH_SCOPE_POPULATION};
			struct research_session *session = NULL;
			const unsigned int before = allocations;
			assert(research_session_open(&options, &session) == 0);
			assert(allocations == before + 1U);
			struct research_session *const saved = session;
			options.founder = 1U;
			assert(research_session_open(&options, &session) == -EINVAL &&
			       session == saved);
			options.founder = 0U;
			options.scope = (enum research_scope)2;
			assert(research_session_open(&options, &session) == -EINVAL &&
			       session == saved);
			options.scope = RESEARCH_SCOPE_POPULATION;
			fail_allocation = true;
			assert(research_session_reset(&session) == -ENOMEM && session == saved);
			fail_allocation = false;
			const unsigned int opened = allocations;
			check_steps = true;
			assert(research_session_step(session, 512U) == 0);
			check_steps = false;
			verify(session);
			assert(research_session_step(session, RESEARCH_DAY_TICKS - 512U) == 0);
			for (uint32_t day = 1U; day < 64U; ++day) {
				assert(research_session_step(session, RESEARCH_DAY_TICKS) == 0);
				verify(session);
				const struct picosystem_garden_world *const world =
					&observed.base.growth.base.world;
				for (uint8_t i = 0U; i < world->plant_count; ++i) {
					descendant |= world->plants[i].parent_lineage_id != 0U;
					reused |= world->plants[i].lineage_id != (uint32_t)i + 1U;
				}
				for (uint8_t i = 0U; i < world->seed_count; ++i) {
					bool alive = false;
					for (uint8_t p = 0U; p < world->plant_count; ++p) {
						alive |=
							world->plants[p].lineage_id ==
								world->seeds[i].parent_lineage_id &&
							(world->plants[p].flags &
							 PICOSYSTEM_GARDEN_PLANT_DEAD) == 0U;
					}
					posthumous |= !alive;
				}
			}
			assert(allocations == opened);
			compare_render_and_reset(&session, &options);
			fail_audit = true;
			assert(research_session_step(session, 15U) == -ENOSPC);
			fail_audit = false;
			struct research_status status = {.tick = 123U};
			assert(research_session_step(session, 0U) == -ENOSPC);
			assert(research_session_status(session, &status) == -ENOSPC &&
			       status.tick == 123U);
			FILE *const output = tmpfile();
			assert(output != NULL);
			assert(research_session_write_json(session, output, NULL) == -ENOSPC);
			assert(ftell(output) == 0L && fclose(output) == 0);
			assert(research_session_reset(&session) == 0);
			assert(research_session_step(session, 1U) == 0);
			research_session_close(session);
		}
	}
	assert(checked_steps == 3072U && descendant && reused && posthumous);
	trace_tests();
	shadow_tests();
	assert(checked_steps == 3072U + 3U * RESEARCH_DAY_TICKS);
	gate_tests();
	gate_seed_tests();
	gate_early_tests();
	gate_continue_tests();
	struct research_session *purchases = NULL;
	const struct research_options purchase_options = {
		.seed = UINT32_C(0x9a903368), .model = 1U, .scope = RESEARCH_SCOPE_POPULATION};
	assert(research_session_open(&purchase_options, &purchases) == 0);
	assert(research_session_gate_start_early(purchases, 0U) == 0);
	fail_allocation = true;
	assert(research_session_purchase_start(purchases) == -ENOMEM);
	fail_allocation = false;
	assert(research_session_purchase_start(purchases) == 0);
	const unsigned int purchase_allocations = allocations;
	assert(research_session_fallback_start(purchases) == 0);
	assert(research_session_step(purchases, RESEARCH_PURCHASE_END) == 0);
	assert(allocations == purchase_allocations);
	fail_allocation = true;
	assert(research_session_reset(&purchases) == -ENOMEM);
	fail_allocation = false;
	struct research_status purchase_status;
	assert(research_session_status(purchases, &purchase_status) == 0 &&
	       purchase_status.tick == RESEARCH_PURCHASE_END);
	research_session_close(purchases);
	research_purchase_tests();
	research_fallback_tests();
	research_reproduction_tests();
	research_budget_tests();
	research_foliage_tests();
	struct research_session *reproduction = NULL;
	assert(research_session_open(&purchase_options, &reproduction) == 0);
	assert(research_session_gate_start_early(reproduction, 2U) == 0);
	fail_allocation = true;
	assert(research_session_reproduction_start(reproduction) == -ENOMEM);
	fail_allocation = false;
	assert(research_session_reproduction_start(reproduction) == 0);
	const unsigned int reproduction_allocations = allocations;
	assert(research_session_step(reproduction, RESEARCH_REPRODUCTION_FIRST +
							   RESEARCH_REPRODUCTION_CADENCE) == 0);
	assert(allocations == reproduction_allocations);
	fail_reproduction = true;
	assert(research_session_step(reproduction, RESEARCH_REPRODUCTION_CADENCE) == -EIO);
	fail_reproduction = false;
	assert(research_session_step(reproduction, 0U) == -EIO);
	FILE *const reproduction_output = tmpfile();
	assert(reproduction_output != NULL);
	assert(research_session_reproduction_write(reproduction, reproduction_output) == -EIO);
	assert(research_session_write_json(reproduction, reproduction_output, NULL) == -EIO);
	assert(ftell(reproduction_output) == 0L && fclose(reproduction_output) == 0);
	assert(research_session_reset(&reproduction) == 0);
	assert(research_session_budget_start(reproduction) == -EINVAL);
	assert(research_session_gate_start_early(reproduction, 2U) == 0);
	assert(research_session_reproduction_start(reproduction) == 0);
	assert(research_session_fallback_start(reproduction) == 0);
	fail_allocation = true;
	assert(research_session_budget_start(reproduction) == -ENOMEM);
	fail_allocation = false;
	assert(research_session_budget_start(reproduction) == 0);
	fail_allocation = true;
	assert(research_session_foliage_start(reproduction) == -ENOMEM);
	fail_allocation = false;
	assert(research_session_foliage_start(reproduction) == 0);
	fail_allocation = true;
	assert(research_session_canopy_start(reproduction) == -ENOMEM);
	fail_allocation = false;
	assert(research_session_canopy_start(reproduction) == 0);
	const unsigned int budget_allocations = allocations;
	assert(research_session_step(reproduction, RESEARCH_CANOPY_FIRST + 15U) == 0);
	assert(allocations == budget_allocations);
	fail_trace = true;
	assert(research_session_step(reproduction, 15U) == -EOVERFLOW);
	fail_trace = false;
	FILE *const budget_output = tmpfile();
	assert(budget_output != NULL);
	assert(research_session_budget_write(reproduction, budget_output) == -EOVERFLOW);
	assert(research_session_foliage_write(reproduction, budget_output) == -EOVERFLOW);
	assert(research_session_canopy_write(reproduction, budget_output) == -EOVERFLOW);
	assert(research_session_write_json(reproduction, budget_output, NULL) == -EOVERFLOW);
	assert(ftell(budget_output) == 0L && fclose(budget_output) == 0);
	assert(research_session_reset(&reproduction) == 0);
	assert(research_session_gate_start_early(reproduction, 2U) == 0);
	assert(research_session_reproduction_start(reproduction) == 0);
	assert(research_session_foliage_start(reproduction) == 0);
	assert(research_session_canopy_start(reproduction) == 0);
	assert(research_session_step(reproduction, RESEARCH_CANOPY_FIRST) == 0);
	corrupt_canopy = true;
	assert(research_session_step(reproduction, 15U) == -EFAULT);
	corrupt_canopy = false;
	assert(research_session_step(reproduction, 0U) == -EFAULT);
	FILE *const rejected_canopy = tmpfile();
	assert(rejected_canopy != NULL);
	assert(research_session_canopy_write(reproduction, rejected_canopy) == -EFAULT);
	assert(ftell(rejected_canopy) == 0L && fclose(rejected_canopy) == 0);
	assert(research_session_reset(&reproduction) == 0);
	assert(research_session_step(reproduction, 1U) == 0);
	research_session_close(reproduction);
	assert(checked_steps == 3072U + 3U * RESEARCH_DAY_TICKS + 8U * 512U);
	puts("Population session: uniform parity, ancestry, turnover, rendering, reset and "
	     "failures pass.");
	return 0;
}
