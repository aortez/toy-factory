/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_signal.h"
#include "garden_evaluation.h"

#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

static const struct toy_factory_garden_landing_feature_config current = {
	.version = TOY_FACTORY_GARDEN_LANDING_FEATURE_VERSION,
	.mode = TOY_FACTORY_GARDEN_LANDING_INPUT_CURRENT};
static const struct toy_factory_garden_landing_signal_config live = {
	.version = TOY_FACTORY_GARDEN_LANDING_SIGNAL_VERSION};

static struct picosystem_garden_world world_fixture(void)
{
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 3U) ==
	       0);
	return world;
}

static struct toy_factory_garden_landing_model model_fixture(void)
{
	struct toy_factory_garden_landing_model model;
	assert(toy_factory_garden_landing_model_import(picosystem_garden_neural_reference_model(),
						       &current, &model) == 0);
	for (uint8_t u = 0U; u < PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT; ++u) {
		for (uint8_t f = 0U; f < TOY_FACTORY_GARDEN_LANDING_COMMON_COUNT; ++f) {
			model.common_weights[u][f] = (int8_t)((int)(u + f) % 17 - 8);
		}
	}
	for (uint8_t u = 0U; u < PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT; ++u) {
		for (uint8_t f = 0U; f < TOY_FACTORY_GARDEN_LANDING_CANDIDATE_COUNT; ++f) {
			model.candidate_weights[u][f] = (int8_t)((int)(u + f) % 17 - 8);
		}
	}
	return model;
}

static void packet_transform(void)
{
	const struct picosystem_garden_world world = world_fixture();
	struct picosystem_garden_agent_observation observation;
	assert(picosystem_garden_agent_observe_tip(&world, 0U, 1U, 0U, &observation) == 0);
	observation.candidates[0].flags = 0U;
	struct picosystem_garden_landing_packet packet = {
		.version = PICOSYSTEM_GARDEN_LANDING_VERSION, .valid = 61U, .warmup_samples = 256U};
	const uint8_t values[] = {73U, 19U, 51U, 201U, 60U, 90U, 44U, 12U};
	for (uint8_t s = 0U; s < PICOSYSTEM_GARDEN_LANDING_SOURCES; ++s) {
		if ((packet.valid & (1U << s)) != 0U) {
			memcpy(packet.values[s], values, sizeof(values));
		}
	}
	const struct picosystem_garden_landing_packet original = packet;
	struct toy_factory_garden_landing_features before;
	assert(toy_factory_garden_landing_features_encode(&observation, &packet, &current,
							  &before) == 0);
	/* Independent expected raw constants; all 16 combinations, not only the panel. */
	const uint8_t occupancy[][2] = {{73U, 19U}, {128U, 128U}, {0U, 0U}, {255U, 0U}};
	const uint8_t resources[][2] = {{51U, 201U}, {128U, 128U}, {0U, 0U}, {255U, 255U}};
	for (uint8_t o = 0U; o < 4U; ++o) {
		for (uint8_t r = 0U; r < 4U; ++r) {
			const struct toy_factory_garden_landing_signal_config config = {
				.version = 1U, .occupancy = o, .resources = r};
			struct picosystem_garden_landing_packet actual;
			assert(toy_factory_garden_landing_signal_apply(&observation, &packet,
								       &config, &actual) == 0);
			struct picosystem_garden_landing_packet expected = packet;
			for (uint8_t s = 0U; s < PICOSYSTEM_GARDEN_LANDING_SOURCES; ++s) {
				if ((packet.valid & (1U << s)) != 0U) {
					memcpy(&expected.values[s][0], occupancy[o], 2U);
					memcpy(&expected.values[s][2], resources[r], 2U);
				}
			}
			assert(memcmp(&actual, &expected, sizeof(actual)) == 0);
			assert(memcmp(&packet, &original, sizeof(packet)) == 0);
			struct toy_factory_garden_landing_features after;
			assert(toy_factory_garden_landing_features_encode(&observation, &actual,
									  &current, &after) == 0);
			assert(memcmp(&before.legacy, &after.legacy, sizeof(before.legacy)) == 0);
			for (uint8_t f = 0U; f < 4U; ++f) {
				assert(after.landing.common[f] == (int)expected.values[0][f] - 128);
				assert(after.landing.candidates[0][f] == 0);
			}
			for (uint8_t f = 4U; f < TOY_FACTORY_GARDEN_LANDING_COMMON_COUNT; ++f) {
				assert(after.landing.common[f] == 0);
			}
		}
	}
	/* Root packets remain entirely masked, even with a nonzero fixed probe. */
	observation.tissue_kind = PICOSYSTEM_GARDEN_NODE_ROOT;
	observation.candidate_count = 3U;
	memset(packet.values, 0, sizeof(packet.values));
	packet.valid = 0U;
	const struct toy_factory_garden_landing_signal_config fixed = {
		.version = 1U, .occupancy = 3U, .resources = 3U};
	struct picosystem_garden_landing_packet output;
	assert(toy_factory_garden_landing_signal_apply(&observation, &packet, &fixed, &output) ==
	       0);
	assert(memcmp(&packet, &output, sizeof(packet)) == 0);

	memset(&output, 0xa5, sizeof(output));
	const struct picosystem_garden_landing_packet sentinel = output;
	assert(toy_factory_garden_landing_signal_apply(NULL, &packet, &live, &output) == -EINVAL);
	assert(toy_factory_garden_landing_signal_apply(&observation, NULL, &live, &output) ==
	       -EINVAL);
	assert(toy_factory_garden_landing_signal_apply(&observation, &packet, NULL, &output) ==
	       -EINVAL);
	assert(toy_factory_garden_landing_signal_apply(&observation, &packet, &live, NULL) ==
	       -EINVAL);
	for (uint8_t field = 0U; field < 4U; ++field) {
		struct toy_factory_garden_landing_signal_config bad = live;
		switch (field) {
		case 0U:
			bad.version = 0U;
			break;
		case 1U:
			bad.occupancy = 4U;
			break;
		case 2U:
			bad.resources = 4U;
			break;
		default:
			bad.reserved = 1U;
			break;
		}
		assert(toy_factory_garden_landing_signal_apply(&observation, &packet, &bad,
							       &output) == -ERANGE);
		assert(memcmp(&output, &sentinel, sizeof(output)) == 0);
	}
	packet.warmup_samples = 257U;
	assert(toy_factory_garden_landing_signal_apply(&observation, &packet, &live, &output) ==
	       -ERANGE);
	assert(memcmp(&output, &sentinel, sizeof(output)) == 0);
	packet.warmup_samples = 0U;
	packet.values[0][0] = 1U;
	assert(toy_factory_garden_landing_signal_apply(&observation, &packet, &live, &output) ==
	       -ERANGE);
	assert(memcmp(&output, &sentinel, sizeof(output)) == 0);
}

static uint32_t fingerprint(const struct toy_factory_garden_landing_signal_run *run)
{
	uint32_t hash;
	assert(toy_factory_garden_landing_signal_hash(run, &hash) == 0);
	return hash;
}

static void trajectories(void)
{
	struct picosystem_garden_world world;
	assert(toy_factory_garden_evaluation_reset(&world, &toy_factory_garden_rainfed_scenarios[1],
						   0x1234U) == 0);
	assert(picosystem_garden_world_set_climate(&world, PICOSYSTEM_GARDEN_CLIMATE_SEASONAL) ==
	       0);
	const struct toy_factory_garden_landing_model model = model_fixture();
	uint32_t hashes[16];
	for (uint8_t o = 0U; o < 4U; ++o) {
		for (uint8_t r = 0U; r < 4U; ++r) {
			const struct toy_factory_garden_landing_signal_config config = {
				.version = 1U, .occupancy = o, .resources = r};
			struct toy_factory_garden_landing_signal_run run;
			assert(toy_factory_garden_landing_signal_init(&world, &model, &config,
								      &run) == 0);
			hashes[o * 4U + r] = fingerprint(&run);
			for (uint8_t previous = 0U; previous < o * 4U + r; ++previous) {
				assert(hashes[previous] != hashes[o * 4U + r]);
			}
			struct picosystem_garden_death_audit deaths, repeated_deaths;
			struct picosystem_garden_seed_audit seeds, repeated_seeds;
			for (uint32_t tick = 0U; tick < 129U; ++tick) {
				assert(toy_factory_garden_landing_signal_step(&run, &deaths,
									      &seeds) == 0);
			}
			struct toy_factory_garden_landing_signal_run copy = run;
			for (uint32_t tick = 0U; tick < 4000U; ++tick) {
				assert(toy_factory_garden_landing_signal_step(&run, &deaths,
									      &seeds) == 0);
				assert(toy_factory_garden_landing_signal_step(
					       &copy, &repeated_deaths, &repeated_seeds) == 0);
				assert(memcmp(&run, &copy, sizeof(run)) == 0);
				assert(memcmp(&deaths, &repeated_deaths, sizeof(deaths)) == 0);
				assert(memcmp(&seeds, &repeated_seeds, sizeof(seeds)) == 0);
			}
			assert(fingerprint(&run) == fingerprint(&copy));
			assert(memcmp(&run.base.model, &model, sizeof(model)) == 0);
		}
	}
	for (uint8_t neutral = 0U; neutral < 2U; ++neutral) {
		const struct toy_factory_garden_landing_signal_config config = {
			.version = 1U, .occupancy = neutral, .resources = neutral};
		struct toy_factory_garden_landing_signal_run probe;
		struct toy_factory_garden_landing_run plain;
		struct toy_factory_garden_landing_model control = model;
		if (neutral != 0U) {
			control.config.mode = TOY_FACTORY_GARDEN_LANDING_INPUT_OFF;
		}
		assert(toy_factory_garden_landing_signal_init(&world, &model, &config, &probe) ==
		       0);
		assert(toy_factory_garden_landing_run_init(&world, &control, &plain) == 0);
		for (uint32_t tick = 0U; tick < 7681U; ++tick) {
			struct picosystem_garden_death_audit a, b;
			struct picosystem_garden_seed_audit x, y;
			assert(toy_factory_garden_landing_signal_step(&probe, &a, &x) == 0);
			assert(toy_factory_garden_landing_run_step_audits(&plain, &b, &y) == 0);
			assert(memcmp(&probe.base.world, &plain.world, sizeof(plain.world)) == 0);
			assert(memcmp(&probe.base.cache, &plain.cache, sizeof(plain.cache)) == 0);
			assert(memcmp(&a, &b, sizeof(a)) == 0);
			assert(memcmp(&x, &y, sizeof(x)) == 0);
		}
	}
}

static void rollback(void)
{
	const struct picosystem_garden_world world = world_fixture();
	struct toy_factory_garden_landing_model model = model_fixture();
	struct toy_factory_garden_landing_signal_run run;
	memset(&run, 0xa5, sizeof(run));
	const struct toy_factory_garden_landing_signal_run sentinel = run;
	for (uint8_t mode = 0U; mode < 3U; mode += 2U) {
		model.config.mode = mode;
		assert(toy_factory_garden_landing_signal_init(&world, &model, &live, &run) ==
		       -ENOTSUP);
		assert(memcmp(&run, &sentinel, sizeof(run)) == 0);
	}
	model.config.mode = TOY_FACTORY_GARDEN_LANDING_INPUT_CURRENT;
	assert(toy_factory_garden_landing_signal_init(&world, &model, &live, &run) == 0);
	struct picosystem_garden_death_audit deaths;
	struct picosystem_garden_seed_audit seeds;
	memset(&deaths, 0xa5, sizeof(deaths));
	memset(&seeds, 0xa5, sizeof(seeds));
	const struct picosystem_garden_death_audit old_deaths = deaths;
	const struct picosystem_garden_seed_audit old_seeds = seeds;
	const struct toy_factory_garden_landing_signal_run initial = run;
	for (uint8_t failure = 0U; failure < 4U; ++failure) {
		run = initial;
		switch (failure) {
		case 0U:
			run.config.reserved = 1U;
			break;
		case 1U:
			run.base.cache.ecology_tick++;
			break;
		case 2U:
			/* A growth failure after sampling must roll back cache and world. */
			run.base.world.logic_tick_count = 14U;
			run.base.world.nodes[1].x = 0U;
			break;
		default:
			run.base.model.legacy.hidden_shift = 31U;
			break;
		}
		const struct toy_factory_garden_landing_signal_run failing = run;
		assert(toy_factory_garden_landing_signal_step(&run, &deaths, &seeds) != 0);
		assert(memcmp(&run, &failing, sizeof(run)) == 0);
		assert(memcmp(&deaths, &old_deaths, sizeof(deaths)) == 0);
		assert(memcmp(&seeds, &old_seeds, sizeof(seeds)) == 0);
		if (failure != 2U) {
			uint32_t hash = UINT32_C(0xa5a5a5a5);
			assert(toy_factory_garden_landing_signal_hash(&run, &hash) != 0);
			assert(hash == UINT32_C(0xa5a5a5a5));
		}
	}
	run = initial;
	assert(toy_factory_garden_landing_signal_step(NULL, &deaths, &seeds) == -EINVAL);
	assert(toy_factory_garden_landing_signal_step(&run, NULL, &seeds) == -EINVAL);
	assert(toy_factory_garden_landing_signal_step(&run, &deaths, NULL) == -EINVAL);
	assert(memcmp(&run, &initial, sizeof(run)) == 0);
	assert(toy_factory_garden_landing_signal_init(NULL, &model, &live, &run) == -EINVAL);
	assert(toy_factory_garden_landing_signal_init(&world, NULL, &live, &run) == -EINVAL);
	assert(toy_factory_garden_landing_signal_init(&world, &model, NULL, &run) == -EINVAL);
	assert(toy_factory_garden_landing_signal_init(&world, &model, &live, NULL) == -EINVAL);
	assert(memcmp(&run, &initial, sizeof(run)) == 0);
	model.config.flags = TOY_FACTORY_GARDEN_LANDING_OMIT_DEAD_ONLY;
	assert(toy_factory_garden_landing_signal_init(&world, &model, &live, &run) == -ENOTSUP);
	assert(memcmp(&run, &initial, sizeof(run)) == 0);
}

int main(void)
{
	packet_transform();
	trajectories();
	rollback();
	puts("landing signal packet, checkpoint and rollback tests passed");
	return 0;
}
