/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_evaluation.h"
#include "garden_landing_features.h"

static const struct toy_factory_garden_landing_feature_config history = {
	.version = TOY_FACTORY_GARDEN_LANDING_FEATURE_VERSION,
	.mode = TOY_FACTORY_GARDEN_LANDING_INPUT_HISTORY,
};

static struct picosystem_garden_agent_observation fixture(void)
{
	struct picosystem_garden_world world;
	struct picosystem_garden_agent_observation observation;
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 3U) ==
	       0);
	assert(picosystem_garden_agent_observe_tip(&world, 0U, 1U, 0U, &observation) == 0);
	return observation;
}

static void unchanged_on_error(const struct picosystem_garden_agent_observation *observation,
			       const struct picosystem_garden_landing_packet *packet,
			       const struct toy_factory_garden_landing_feature_config *config,
			       int expected)
{
	struct toy_factory_garden_landing_features result;
	memset(&result, 0x5a, sizeof(result));
	const struct toy_factory_garden_landing_features before = result;
	assert(toy_factory_garden_landing_features_encode(observation, packet, config, &result) ==
	       expected);
	assert(memcmp(&result, &before, sizeof(result)) == 0);
}

static void failures(void)
{
	struct picosystem_garden_agent_observation observation = fixture();
	struct picosystem_garden_landing_packet packet = {
		.version = PICOSYSTEM_GARDEN_LANDING_VERSION,
		.valid = 63U,
		.warmup_samples = 1U,
	};
	struct toy_factory_garden_landing_feature_config config = history;
	unchanged_on_error(NULL, &packet, &config, -EINVAL);
	unchanged_on_error(&observation, NULL, &config, -EINVAL);
	unchanged_on_error(&observation, &packet, NULL, -EINVAL);
	assert(toy_factory_garden_landing_features_encode(&observation, &packet, &config, NULL) ==
	       -EINVAL);
	for (uint8_t i = 0U; i < 4U; ++i) {
		config = history;
		switch (i) {
		case 0U:
			config.version = 2U;
			break;
		case 1U:
			config.mode = TOY_FACTORY_GARDEN_LANDING_INPUT_MODE_COUNT;
			break;
		case 2U:
			config.flags = 2U;
			break;
		default:
			config.reserved = 1U;
			break;
		}
		unchanged_on_error(&observation, &packet, &config, -ERANGE);
	}
	config = history;
	packet.version = 2U;
	unchanged_on_error(&observation, &packet, &config, -ERANGE);
	config.mode = TOY_FACTORY_GARDEN_LANDING_INPUT_OFF;
	unchanged_on_error(&observation, &packet, &config, -ERANGE);
	config = history;
	packet.version = PICOSYSTEM_GARDEN_LANDING_VERSION;
	packet.warmup_samples = 257U;
	unchanged_on_error(&observation, &packet, &config, -ERANGE);
	packet.warmup_samples = 0U;
	packet.values[0][TOY_FACTORY_GARDEN_LANDING_WET_EMA] = 1U;
	unchanged_on_error(&observation, &packet, &config, -ERANGE);
	packet.warmup_samples = 1U;
	packet.values[0][TOY_FACTORY_GARDEN_LANDING_WET_LIGHT_EMA] = 2U;
	unchanged_on_error(&observation, &packet, &config, -ERANGE);
	memset(packet.values, 0, sizeof(packet.values));
	packet.valid = 127U;
	unchanged_on_error(&observation, &packet, &config, -ERANGE);
	packet.valid = 63U;
	observation.candidates[0].flags = 0U;
	unchanged_on_error(&observation, &packet, &config, -ERANGE);
	packet.valid = 61U;
	packet.values[1][0] = 1U;
	unchanged_on_error(&observation, &packet, &config, -ERANGE);
	packet.values[1][0] = 0U;
	observation.version = 0U;
	unchanged_on_error(&observation, &packet, &config, -ERANGE);
}

static void encoding(void)
{
	struct picosystem_garden_agent_observation observation = fixture();
	struct picosystem_garden_landing_packet packet = {
		.version = PICOSYSTEM_GARDEN_LANDING_VERSION,
		.valid = 63U,
		.warmup_samples = 1U,
	};
	struct toy_factory_garden_landing_features result;
	struct picosystem_garden_neural_features legacy;
	assert(picosystem_garden_neural_encode_features(&observation, &legacy) == 0);
	for (uint16_t v = 0U; v <= 255U; ++v) {
		for (uint8_t s = 0U; s < PICOSYSTEM_GARDEN_LANDING_SOURCES; ++s) {
			for (uint8_t f = 0U; f < PICOSYSTEM_GARDEN_LANDING_FIELDS; ++f) {
				packet.values[s][f] = (f == TOY_FACTORY_GARDEN_LANDING_DEAD_ONLY)
							      ? 0U
							      : (uint8_t)v;
			}
		}
		assert(toy_factory_garden_landing_features_encode(&observation, &packet, &history,
								  &result) == 0);
		assert(memcmp(&legacy, &result.legacy, sizeof(legacy)) == 0);
		for (uint8_t f = 0U; f < PICOSYSTEM_GARDEN_LANDING_FIELDS; ++f) {
			const int expected =
				(f == TOY_FACTORY_GARDEN_LANDING_DEAD_ONLY) ? -128 : (int)v - 128;
			assert(result.landing.common[f] == expected);
			for (uint8_t s = 0U; s < observation.candidate_count; ++s) {
				assert(result.landing.candidates[s][f] == expected);
			}
		}
	}
	memset(packet.values, 0, sizeof(packet.values));
	int previous = -129;
	for (uint16_t samples = 0U; samples <= 256U; ++samples) {
		packet.warmup_samples = samples;
		assert(toy_factory_garden_landing_features_encode(&observation, &packet, &history,
								  &result) == 0);
		const int warmup = result.landing.common[TOY_FACTORY_GARDEN_LANDING_WARMUP];
		assert(warmup >= previous && warmup == (int)((samples * 255U + 128U) / 256U) - 128);
		assert((warmup == 127) == (samples == 256U));
		assert(result.landing.common[TOY_FACTORY_GARDEN_LANDING_WET_EMA] ==
		       (samples ? -128 : 0));
		previous = warmup;
	}
	struct toy_factory_garden_landing_feature_config config = history;
	config.mode = TOY_FACTORY_GARDEN_LANDING_INPUT_CURRENT;
	assert(toy_factory_garden_landing_features_encode(&observation, &packet, &config,
							  &result) == 0);
	for (uint8_t f = TOY_FACTORY_GARDEN_LANDING_WET_EMA;
	     f < TOY_FACTORY_GARDEN_LANDING_COMMON_COUNT; ++f) {
		assert(result.landing.common[f] == 0);
	}
	config.flags = TOY_FACTORY_GARDEN_LANDING_OMIT_DEAD_ONLY;
	assert(toy_factory_garden_landing_features_encode(&observation, &packet, &config,
							  &result) == 0);
	assert(result.landing.common[TOY_FACTORY_GARDEN_LANDING_DEAD_ONLY] == 0);
	config.mode = TOY_FACTORY_GARDEN_LANDING_INPUT_OFF;
	assert(toy_factory_garden_landing_features_encode(&observation, NULL, &config, &result) ==
	       0);
	const struct toy_factory_garden_landing_inputs zero = {0};
	assert(memcmp(&result.landing, &zero, sizeof(zero)) == 0);
	assert(memcmp(&result.legacy, &legacy, sizeof(legacy)) == 0);
	packet.values[0][0] = 128U;
	packet.values[0][1] = 128U;
	assert(toy_factory_garden_landing_features_encode(&observation, &packet, &history,
							  &result) == 0);
	packet.values[0][0] = 129U;
	unchanged_on_error(&observation, &packet, &history, -ERANGE);
}

static void bounds_and_order(void)
{
	struct picosystem_garden_agent_observation observation = fixture();
	struct picosystem_garden_landing_packet packet = {
		.version = PICOSYSTEM_GARDEN_LANDING_VERSION,
		.valid = 59U,
		.warmup_samples = 256U,
	};
	observation.candidates[1].flags = 0U;
	observation.candidates[0].flags = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS |
					  PICOSYSTEM_GARDEN_AGENT_CANDIDATE_OWN_NEAR;
	packet.values[1][2] = 18U;
	packet.values[5][2] = 239U;
	struct toy_factory_garden_landing_features first, reordered;
	assert(toy_factory_garden_landing_features_encode(&observation, &packet, &history,
							  &first) == 0);
	assert(first.landing.candidates[0][2] == -110);
	for (uint8_t f = 0U; f < TOY_FACTORY_GARDEN_LANDING_CANDIDATE_COUNT; ++f) {
		assert(first.landing.candidates[1][f] == 0);
	}
	const struct picosystem_garden_agent_candidate candidate = observation.candidates[0];
	observation.candidates[0] = observation.candidates[4];
	observation.candidates[4] = candidate;
	uint8_t values[PICOSYSTEM_GARDEN_LANDING_FIELDS];
	memcpy(values, packet.values[1], sizeof(values));
	memcpy(packet.values[1], packet.values[5], sizeof(values));
	memcpy(packet.values[5], values, sizeof(values));
	assert(toy_factory_garden_landing_features_encode(&observation, &packet, &history,
							  &reordered) == 0);
	assert(memcmp(first.landing.candidates[0], reordered.landing.candidates[4],
		      sizeof(values)) == 0);
	assert(memcmp(first.landing.candidates[4], reordered.landing.candidates[0],
		      sizeof(values)) == 0);
	observation.tissue_kind = PICOSYSTEM_GARDEN_NODE_ROOT;
	observation.candidate_count = 3U;
	packet.valid = 0U;
	memset(packet.values, 0, sizeof(packet.values));
	assert(toy_factory_garden_landing_features_encode(&observation, &packet, &history,
							  &first) == 0);
	const struct toy_factory_garden_landing_inputs zero = {0};
	assert(memcmp(&first.landing, &zero, sizeof(zero)) == 0);
}

struct observer_context {
	const struct picosystem_garden_agent_policy *policy;
	const struct picosystem_garden_landing_cache *cache;
	uint32_t *queries;
};

static int encode_decide(const struct picosystem_garden_agent_observation *observation,
			 const struct picosystem_garden_agent_memory *memory,
			 struct picosystem_garden_agent_decision *decision, const void *context)
{
	const struct observer_context *const ctx = context;
	const struct picosystem_garden_agent_observation before = *observation;
	const struct picosystem_garden_agent_memory before_memory = *memory;
	const struct picosystem_garden_landing_cache before_cache = *ctx->cache;
	struct picosystem_garden_landing_packet packet;
	assert(picosystem_garden_landing_observe(ctx->cache, observation, &packet) == 0);
	const struct picosystem_garden_landing_packet before_packet = packet;
	struct picosystem_garden_neural_features legacy;
	assert(picosystem_garden_neural_encode_features(observation, &legacy) == 0);
	for (uint8_t mode = 0U; mode < TOY_FACTORY_GARDEN_LANDING_INPUT_MODE_COUNT; ++mode) {
		for (uint8_t flags = 0U; flags <= TOY_FACTORY_GARDEN_LANDING_OMIT_DEAD_ONLY;
		     ++flags) {
			struct toy_factory_garden_landing_feature_config config = history;
			config.mode = mode;
			config.flags = flags;
			struct toy_factory_garden_landing_features result;
			assert(toy_factory_garden_landing_features_encode(observation, &packet,
									  &config, &result) == 0);
			assert(memcmp(&legacy, &result.legacy, sizeof(legacy)) == 0);
		}
	}
	assert(memcmp(observation, &before, sizeof(before)) == 0);
	assert(memcmp(memory, &before_memory, sizeof(before_memory)) == 0);
	assert(memcmp(ctx->cache, &before_cache, sizeof(before_cache)) == 0);
	assert(memcmp(&packet, &before_packet, sizeof(packet)) == 0);
	++*ctx->queries;
	return picosystem_garden_agent_decide(ctx->policy, observation, memory, decision);
}

static void legacy_compatibility(void)
{
	assert(PICOSYSTEM_GARDEN_NEURAL_FEATURE_VERSION == 1U);
	assert(PICOSYSTEM_GARDEN_NEURAL_MODEL_VERSION == 1U);
	assert(PICOSYSTEM_GARDEN_NEURAL_FILE_SIZE == 1220U);
	uint8_t file[PICOSYSTEM_GARDEN_NEURAL_FILE_SIZE], after[PICOSYSTEM_GARDEN_NEURAL_FILE_SIZE];
	const struct picosystem_garden_neural_model *const model =
		picosystem_garden_neural_reference_model();
	assert(picosystem_garden_neural_model_encode(model, file, sizeof(file)) == 0);
	const struct picosystem_garden_agent_policy *const policies[] = {
		picosystem_garden_agent_baseline_policy(),
		picosystem_garden_agent_adaptive_policy(),
		picosystem_garden_agent_neural_reference_policy(),
	};
	for (uint8_t p = 0U; p < 3U; ++p) {
		struct picosystem_garden_world plain;
		assert(toy_factory_garden_evaluation_reset(
			       &plain, &toy_factory_garden_rainfed_scenarios[1], 0xed52188cU) == 0);
		assert(picosystem_garden_world_set_climate(
			       &plain, PICOSYSTEM_GARDEN_CLIMATE_SEASONAL) == 0);
		struct picosystem_garden_world observed = plain;
		struct picosystem_garden_landing_cache cache;
		assert(picosystem_garden_landing_reset(&observed, &cache) == 0);
		uint32_t queries = 0U;
		const struct observer_context ctx = {
			.policy = policies[p], .cache = &cache, .queries = &queries};
		struct picosystem_garden_agent_policy observer = *policies[p];
		observer.decide = encode_decide;
		observer.context = &ctx;
		for (uint32_t tick = 1U; tick <= 32U * 3840U; ++tick) {
			assert(picosystem_garden_world_step_with_policy(&plain, policies[p]) == 0);
			assert(picosystem_garden_world_step_landing(&observed, &observer, &cache) ==
			       0);
			assert(memcmp(&plain, &observed, sizeof(plain)) == 0);
		}
		assert(queries > 100U);
	}
	assert(picosystem_garden_neural_model_encode(model, after, sizeof(after)) == 0);
	assert(memcmp(file, after, sizeof(file)) == 0);
	struct picosystem_garden_neural_model restored;
	assert(picosystem_garden_neural_model_decode(file, sizeof(file), &restored) == 0);
	assert(memcmp(&restored, model, sizeof(restored)) == 0);
}

int main(void)
{
	failures();
	encoding();
	bounds_and_order();
	legacy_compatibility();
	puts("Landing feature encoding/masking/failure tests and legacy trajectory/model checks "
	     "passed");
	return 0;
}
