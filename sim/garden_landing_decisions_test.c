/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_decisions.h"
#include "garden_landing_signal.h"
#include "garden_evaluation.h"

#include <assert.h>
#include <errno.h>
#include <string.h>

struct observer_context {
	const struct toy_factory_garden_landing_model *model;
	uint32_t queries;
	bool fail;
};

static int inspect(const struct picosystem_garden_agent_observation *o,
		   const struct picosystem_garden_agent_memory *memory,
		   const struct picosystem_garden_landing_packet *packet,
		   const struct picosystem_garden_agent_decision *live, void *context)
{
	struct observer_context *const ctx = context;
	++ctx->queries;
	if (ctx->fail) {
		return -EIO;
	}
	const struct picosystem_garden_landing_packet original_packet = *packet;
	const struct picosystem_garden_agent_memory original_memory = *memory;
	const struct picosystem_garden_agent_observation original_observation = *o;
	const uint8_t groups[10][2] = {{0U, 0U}, {1U, 0U}, {0U, 1U}, {1U, 1U}, {2U, 0U},
				       {3U, 0U}, {0U, 2U}, {0U, 3U}, {2U, 1U}, {3U, 1U}};
	for (uint8_t p = 0U; p < TOY_FACTORY_GARDEN_DECISION_PROBES; ++p) {
		struct picosystem_garden_agent_decision decision, expected;
		assert(toy_factory_garden_decision_probe(o, memory, packet, ctx->model, p,
							 &decision) == 0);
		struct picosystem_garden_landing_packet changed = *packet;
		if (p < 10U) {
			const struct toy_factory_garden_landing_signal_config config = {
				.version = 1U,
				.occupancy = groups[p][0],
				.resources = groups[p][1]};
			assert(toy_factory_garden_landing_signal_apply(o, packet, &config,
								       &changed) == 0);
		} else {
			const uint8_t values[] = {128U, 0U, 255U};
			const uint8_t field = (uint8_t)((p < 13U) ? 2U : 3U);
			for (uint8_t s = 0U; s < PICOSYSTEM_GARDEN_LANDING_SOURCES; ++s) {
				if ((packet->valid & (1U << s)) != 0U) {
					changed.values[s][field] = values[(p - 10U) % 3U];
				}
			}
		}
		assert(toy_factory_garden_landing_neural_decide(o, memory, &changed, ctx->model,
								&expected) == 0);
		assert(memcmp(&decision, &expected, sizeof(decision)) == 0);
		if ((p == 0U) || (o->tissue_kind == PICOSYSTEM_GARDEN_NODE_ROOT)) {
			assert(memcmp(&decision, live, sizeof(decision)) == 0);
		}
	}
	struct picosystem_garden_agent_decision unchanged = *live;
	assert(toy_factory_garden_decision_probe(o, memory, packet, ctx->model, 16U, &unchanged) ==
	       -EINVAL);
	assert(toy_factory_garden_decision_probe(NULL, memory, packet, ctx->model, 0U,
						 &unchanged) == -EINVAL);
	assert(toy_factory_garden_decision_probe(o, NULL, packet, ctx->model, 0U, &unchanged) ==
	       -EINVAL);
	assert(toy_factory_garden_decision_probe(o, memory, NULL, ctx->model, 0U, &unchanged) ==
	       -EINVAL);
	assert(toy_factory_garden_decision_probe(o, memory, packet, NULL, 0U, &unchanged) ==
	       -EINVAL);
	assert(memcmp(&unchanged, live, sizeof(unchanged)) == 0);
	assert(memcmp(packet, &original_packet, sizeof(*packet)) == 0);
	assert(memcmp(memory, &original_memory, sizeof(*memory)) == 0);
	assert(memcmp(o, &original_observation, sizeof(*o)) == 0);
	return 0;
}

int main(void)
{
	struct picosystem_garden_world world;
	assert(toy_factory_garden_evaluation_reset(&world, &toy_factory_garden_rainfed_scenarios[1],
						   123U) == 0);
	const struct toy_factory_garden_landing_feature_config config = {.version = 1U, .mode = 1U};
	struct toy_factory_garden_landing_model model;
	assert(toy_factory_garden_landing_model_import(picosystem_garden_neural_reference_model(),
						       &config, &model) == 0);
	for (uint8_t u = 0U; u < PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT; ++u) {
		for (uint8_t f = 0U; f < 9U; ++f) {
			model.common_weights[u][f] = (int8_t)((int)(u + f) % 17 - 8);
		}
	}
	for (uint8_t u = 0U; u < PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT; ++u) {
		for (uint8_t f = 0U; f < 8U; ++f) {
			model.candidate_weights[u][f] = (int8_t)((int)(u + f) % 13 - 6);
		}
	}
	struct toy_factory_garden_landing_run plain, observed;
	assert(toy_factory_garden_landing_run_init(&world, &model, &plain) == 0);
	observed = plain;
	struct observer_context ctx = {.model = &model};
	for (uint32_t tick = 0U; tick < 7681U; ++tick) {
		struct picosystem_garden_death_audit a, b;
		struct picosystem_garden_seed_audit x, y;
		assert(toy_factory_garden_landing_run_step_audits(&plain, &a, &x) == 0);
		assert(toy_factory_garden_landing_run_step_observed(&observed, &b, &y, inspect,
								    &ctx) == 0);
		assert(memcmp(&plain, &observed, sizeof(plain)) == 0);
		assert(memcmp(&a, &b, sizeof(a)) == 0);
		assert(memcmp(&x, &y, sizeof(x)) == 0);
	}
	assert(ctx.queries > 0U);
	assert(toy_factory_garden_landing_run_init(&world, &model, &observed) == 0);
	ctx.fail = true;
	bool failed = false;
	for (uint32_t tick = 0U; tick < 3840U; ++tick) {
		const struct toy_factory_garden_landing_run before = observed;
		struct picosystem_garden_death_audit deaths;
		struct picosystem_garden_seed_audit seeds;
		memset(&deaths, 0xa5, sizeof(deaths));
		memset(&seeds, 0xa5, sizeof(seeds));
		const struct picosystem_garden_death_audit old_deaths = deaths;
		const struct picosystem_garden_seed_audit old_seeds = seeds;
		const int err = toy_factory_garden_landing_run_step_observed(&observed, &deaths,
									     &seeds, inspect, &ctx);
		if (err != 0) {
			assert(err == -EIO);
			assert(memcmp(&observed, &before, sizeof(before)) == 0);
			assert(memcmp(&deaths, &old_deaths, sizeof(deaths)) == 0);
			assert(memcmp(&seeds, &old_seeds, sizeof(seeds)) == 0);
			assert(toy_factory_garden_landing_run_step_observed(
				       &observed, &deaths, &seeds, NULL, &ctx) == -EINVAL);
			ctx.fail = false;
			assert(toy_factory_garden_landing_run_step_observed(
				       &observed, &deaths, &seeds, inspect, &ctx) == 0);
			failed = true;
			break;
		}
	}
	assert(failed);
	FILE *stream = fopen("/dev/full", "w");
	if (stream != NULL) {
		assert(setvbuf(stream, NULL, _IONBF, 0) == 0);
		struct toy_factory_garden_decision_trace trace;
		memset(&trace, 0xa5, sizeof(trace));
		const struct toy_factory_garden_decision_trace before = trace;
		assert(toy_factory_garden_decision_trace_init(&trace, stream, &model) == -EIO);
		assert(memcmp(&trace, &before, sizeof(trace)) == 0);
		(void)fclose(stream);
	}
	puts("same-state probes, observer rollback and recovery passed");
	return 0;
}
