/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_run.h"
#include "garden_evaluation.h"

#include <assert.h>
#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>

static uint32_t random_state = UINT32_C(0x7ca2bd91);

static uint32_t draw(void)
{
	random_state ^= random_state << 13U;
	random_state ^= random_state >> 17U;
	random_state ^= random_state << 5U;
	return random_state;
}

static int8_t weight(void)
{
	return (int8_t)((int32_t)(draw() & 255U) - 128);
}

static int32_t bias(void)
{
	return (int32_t)(draw() % 2000001U) - 1000000;
}

static void fill(int8_t *values, size_t count, uint32_t index)
{
	for (size_t i = 0U; i < count; ++i) {
		values[i] = (index % 32U == 0U) ? INT8_MIN
						: ((index % 32U == 31U) ? INT8_MAX : weight());
	}
}

static struct toy_factory_garden_landing_model random_model(uint32_t index)
{
	struct toy_factory_garden_landing_model result;
	const struct toy_factory_garden_landing_feature_config config = {
		.version = 1U, .mode = (uint8_t)(index % 3U), .flags = (uint8_t)(index % 2U)};
	assert(toy_factory_garden_landing_model_import(picosystem_garden_neural_reference_model(),
						       &config, &result) == 0);
	struct picosystem_garden_neural_model *const m = &result.legacy;
	m->hidden_shift = (uint8_t)(index % 16U);
	m->output_shift = (uint8_t)((index / 16U) % 16U);
	m->candidate_hidden_shift = (uint8_t)((index / 3U) % 16U);
	for (size_t u = 0U; u < PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT; ++u) {
		m->hidden_bias[u] = bias();
		fill(m->hidden_weights[u], sizeof(m->hidden_weights[u]), index);
		fill(result.common_weights[u], sizeof(result.common_weights[u]), index);
	}
	for (size_t a = 0U; a < PICOSYSTEM_GARDEN_AGENT_ACTION_COUNT; ++a) {
		m->action_bias[a] = bias();
		fill(m->action_weights[a], sizeof(m->action_weights[a]), index);
	}
	if (index % 4U == 0U) {
		m->action_bias[0] = -1000000;
		m->action_bias[1] = 1000000;
		m->action_bias[2] = -1000000;
	}
	m->priority_bias = bias();
	fill(m->priority_weights, sizeof(m->priority_weights), index);
	for (size_t u = 0U; u < PICOSYSTEM_GARDEN_AGENT_MEMORY_WIDTH; ++u) {
		m->memory_bias[u] = bias();
		fill(m->memory_weights[u], sizeof(m->memory_weights[u]), index);
	}
	for (size_t u = 0U; u < PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT; ++u) {
		m->candidate_hidden_bias[u] = bias();
		fill(m->candidate_hidden_weights[u], sizeof(m->candidate_hidden_weights[u]), index);
		fill(m->candidate_feature_weights[u], sizeof(m->candidate_feature_weights[u]),
		     index);
		fill(result.candidate_weights[u], sizeof(result.candidate_weights[u]), index);
	}
	m->candidate_output_bias = bias();
	fill(m->candidate_output_weights, sizeof(m->candidate_output_weights), index);
	assert(toy_factory_garden_landing_model_validate(&result) == 0);
	return result;
}

static struct picosystem_garden_agent_observation observation(uint32_t index)
{
	struct picosystem_garden_world world;
	struct picosystem_garden_agent_observation result;
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 3U) ==
	       0);
	uint16_t tip = PICOSYSTEM_GARDEN_NODE_NONE;
	const uint8_t kind =
		(index % 2U) ? PICOSYSTEM_GARDEN_NODE_STEM : PICOSYSTEM_GARDEN_NODE_ROOT;
	for (uint16_t i = 0U; i < world.node_count; ++i) {
		if ((world.nodes[i].kind == kind) &&
		    ((world.nodes[i].flags & PICOSYSTEM_GARDEN_NODE_TIP) != 0U)) {
			tip = i;
			break;
		}
	}
	assert(tip != PICOSYSTEM_GARDEN_NODE_NONE);
	assert(picosystem_garden_agent_observe_tip(&world, 0U, tip, draw(), &result) == 0);
	result.stored_energy = (uint16_t)draw();
	result.stored_water = (uint16_t)draw();
	if (index % 11U == 0U) {
		result.depth = result.maximum_depth;
	}
	for (uint8_t i = 0U; i < result.candidate_count; ++i) {
		result.candidates[i].flags = (index % 13U == 0U) ? 1U : 3U;
		result.candidates[i].light = (uint8_t)draw();
		result.candidates[i].moisture = (uint8_t)draw();
	}
	if (index % 7U == 0U) {
		result.candidates[1].flags = 0U;
	}
	if (index % 5U == 0U) {
		result.candidates[0].flags = 5U;
	}
	assert(picosystem_garden_agent_observation_is_valid(&result));
	return result;
}

static struct picosystem_garden_landing_packet
packet_for(const struct picosystem_garden_agent_observation *obs, uint16_t samples)
{
	struct picosystem_garden_landing_packet packet = {.version = 1U, .warmup_samples = samples};
	if (obs->tissue_kind == PICOSYSTEM_GARDEN_NODE_ROOT) {
		return packet;
	}
	for (uint8_t i = 0U; i < PICOSYSTEM_GARDEN_LANDING_SOURCES; ++i) {
		if ((i > 0U) && ((obs->candidates[i - 1U].flags & 1U) == 0U)) {
			continue;
		}
		packet.valid |= (uint8_t)(1U << i);
		packet.values[i][0] = (uint8_t)(draw() & 127U);
		packet.values[i][1] = (uint8_t)(draw() & 127U);
		packet.values[i][2] = (uint8_t)draw();
		packet.values[i][3] = (uint8_t)draw();
		if (samples != 0U) {
			const uint8_t v = (uint8_t)draw();
			packet.values[i][4] = v;
			packet.values[i][5] = v;
			packet.values[i][6] = v / 2U;
			packet.values[i][7] = v / 4U;
		}
	}
	return packet;
}

static void same_decision(const struct picosystem_garden_agent_decision *a,
			  const struct picosystem_garden_agent_decision *b)
{
	assert(a->proposal.tip_index == b->proposal.tip_index);
	assert(a->proposal.action == b->proposal.action);
	assert(a->proposal.priority == b->proposal.priority);
	assert(a->proposal.candidate_count == b->proposal.candidate_count);
	assert(memcmp(a->proposal.candidate_order, b->proposal.candidate_order, 5U) == 0);
	assert(memcmp(&a->next_memory, &b->next_memory, sizeof(a->next_memory)) == 0);
}

static void legacy_equivalence(void)
{
	for (uint32_t i = 0U; i < 512U; ++i) {
		const struct toy_factory_garden_landing_model source = random_model(i);
		const struct picosystem_garden_agent_observation obs = observation(i);
		const struct picosystem_garden_landing_packet packet =
			packet_for(&obs, (uint16_t)(i % 257U));
		struct picosystem_garden_agent_memory memory;
		fill(memory.hidden, sizeof(memory.hidden), i);
		struct picosystem_garden_agent_decision old, actual;
		assert(picosystem_garden_agent_neural_decide(&obs, &memory, &old, &source.legacy) ==
		       0);
		for (uint8_t mode = 0U; mode < 3U; ++mode) {
			for (uint8_t flags = 0U; flags < 2U; ++flags) {
				const struct toy_factory_garden_landing_feature_config config = {
					.version = 1U, .mode = mode, .flags = flags};
				struct toy_factory_garden_landing_model model;
				assert(toy_factory_garden_landing_model_import(
					       &source.legacy, &config, &model) == 0);
				assert(toy_factory_garden_landing_neural_decide(
					       &obs, &memory, &packet, &model, &actual) == 0);
				same_decision(&old, &actual);
				if (mode == 0U) {
					assert(toy_factory_garden_landing_neural_decide(
						       &obs, &memory, NULL, &model, &actual) == 0);
					same_decision(&old, &actual);
				}
			}
		}
	}
}

static struct toy_factory_garden_landing_model sensor_model(void)
{
	struct toy_factory_garden_landing_model m = {0};
	m.legacy.magic = PICOSYSTEM_GARDEN_NEURAL_MODEL_MAGIC;
	m.legacy.model_version = 1U;
	m.legacy.feature_version = 1U;
	m.legacy.model_size = PICOSYSTEM_GARDEN_NEURAL_MODEL_SIZE;
	m.config.version = 1U;
	m.config.mode = TOY_FACTORY_GARDEN_LANDING_INPUT_HISTORY;
	m.legacy.action_bias[1] = 1;
	m.legacy.candidate_hidden_bias[0] = 128;
	m.candidate_weights[0][TOY_FACTORY_GARDEN_LANDING_WET_EMA] = 1;
	m.legacy.candidate_output_weights[0] = 1;
	/* Make private memory respond to the common wet-history channel too. */
	m.common_weights[0][TOY_FACTORY_GARDEN_LANDING_WET_EMA] = 1;
	m.legacy.hidden_bias[0] = 128;
	m.legacy.memory_weights[0][0] = 1;
	assert(toy_factory_garden_landing_model_validate(&m) == 0);
	return m;
}

static void sensor_effect_and_failures(void)
{
	struct toy_factory_garden_landing_model m = sensor_model();
	struct picosystem_garden_agent_observation obs = observation(1U);
	obs.decision_nonce = 0U;
	struct picosystem_garden_landing_packet p = {
		.version = 1U, .valid = 63U, .warmup_samples = 256U};
	p.values[3][4] = 120U;
	p.values[0][4] = 50U;
	const struct picosystem_garden_agent_memory memory = {0};
	struct picosystem_garden_agent_decision decision;
	assert(toy_factory_garden_landing_neural_decide(&obs, &memory, &p, &m, &decision) == 0);
	assert(decision.proposal.candidate_order[0] == 2U);
	assert(decision.next_memory.hidden[0] == 50);
	m.config.mode = TOY_FACTORY_GARDEN_LANDING_INPUT_CURRENT;
	assert(toy_factory_garden_landing_neural_decide(&obs, &memory, &p, &m, &decision) == 0);
	assert(decision.proposal.candidate_order[0] == 0U);
	assert(decision.next_memory.hidden[0] == 127);
	m.config.mode = TOY_FACTORY_GARDEN_LANDING_INPUT_HISTORY;
	/* Signed division must truncate -3 / 2 to -1, not arithmetic-shift -2. */
	m.legacy.memory_bias[1] = -3;
	m.legacy.output_shift = 1U;
	assert(toy_factory_garden_landing_neural_decide(&obs, &memory, &p, &m, &decision) == 0);
	assert(decision.next_memory.hidden[1] == -1);
	memset(&decision, 0x5a, sizeof(decision));
	const struct picosystem_garden_agent_decision sentinel = decision;
	assert(toy_factory_garden_landing_neural_decide(NULL, &memory, &p, &m, &decision) ==
	       -EINVAL);
	assert(toy_factory_garden_landing_neural_decide(&obs, NULL, &p, &m, &decision) == -EINVAL);
	assert(toy_factory_garden_landing_neural_decide(&obs, &memory, &p, NULL, &decision) ==
	       -EINVAL);
	assert(toy_factory_garden_landing_neural_decide(&obs, &memory, NULL, &m, &decision) ==
	       -EINVAL);
	m.config.version = 2U;
	assert(toy_factory_garden_landing_neural_decide(&obs, &memory, &p, &m, &decision) ==
	       -ERANGE);
	m.config.version = 1U;
	p.valid = 0U;
	assert(toy_factory_garden_landing_neural_decide(&obs, &memory, &p, &m, &decision) ==
	       -ERANGE);
	assert(memcmp(&decision, &sentinel, sizeof(decision)) == 0);
}

static void codec(void)
{
	struct toy_factory_garden_landing_model m = random_model(19U), restored;
	uint8_t file[TOY_FACTORY_GARDEN_LANDING_FILE_SIZE + 1U], again[sizeof(file)];
	memset(file, 0xa5, sizeof(file));
	assert(toy_factory_garden_landing_model_encode(&m, file, sizeof(file) - 2U) == -ENOSPC);
	for (size_t i = 0U; i < sizeof(file); ++i) {
		assert(file[i] == 0xa5U);
	}
	assert(toy_factory_garden_landing_model_encode(&m, file, sizeof(file)) == 0);
	assert(file[sizeof(file) - 1U] == 0xa5U);
	assert(toy_factory_garden_landing_model_decode(file, sizeof(file) - 1U, &restored) == 0);
	assert(memcmp(&m, &restored, sizeof(m)) == 0);
	assert(toy_factory_garden_landing_model_encode(&restored, again, sizeof(again)) == 0);
	assert(memcmp(file, again, sizeof(file) - 1U) == 0);
	const struct toy_factory_garden_landing_model before = restored;
	assert(toy_factory_garden_landing_model_decode(file, sizeof(file), &restored) == -ERANGE);
	assert(toy_factory_garden_landing_model_decode(file, sizeof(file) - 2U, &restored) ==
	       -ERANGE);
	for (size_t i = 0U; i < sizeof(file) - 1U; ++i) {
		file[i] ^= 1U;
		assert(toy_factory_garden_landing_model_decode(file, sizeof(file) - 1U,
							       &restored) != 0);
		assert(memcmp(&restored, &before, sizeof(before)) == 0);
		file[i] ^= 1U;
	}
	struct picosystem_garden_neural_model old;
	assert(picosystem_garden_neural_model_decode(file, sizeof(file) - 1U, &old) != 0);
	assert(picosystem_garden_neural_model_decode(&file[16], PICOSYSTEM_GARDEN_NEURAL_FILE_SIZE,
						     &old) == 0);
	assert(memcmp(&old, &m.legacy, sizeof(old)) == 0);
	m.config.reserved = 1U;
	assert(toy_factory_garden_landing_model_import(&m.legacy, &m.config, &restored) == -ERANGE);
	assert(memcmp(&restored, &before, sizeof(before)) == 0);
}

static uint32_t run_hash(const struct toy_factory_garden_landing_run *run)
{
	uint32_t hash;
	assert(toy_factory_garden_landing_run_hash(run, &hash) == 0);
	return hash;
}

static void history_affects_run(void)
{
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 3U) ==
	       0);
	struct toy_factory_garden_landing_model model = sensor_model();
	model.legacy.priority_weights[0] = -1;
	struct toy_factory_garden_landing_run dry;
	assert(toy_factory_garden_landing_run_init(&world, &model, &dry) == 0);
	for (uint8_t i = 0U; i < 15U; ++i) {
		assert(toy_factory_garden_landing_run_step(&dry) == 0);
	}
	struct toy_factory_garden_landing_run wet = dry;
	/* Deliberately injected counterfactual histories, not claimed natural runs. */
	memset(dry.cache.traces, 0, sizeof(dry.cache.traces));
	memset(wet.cache.traces, 0, sizeof(wet.cache.traces));
	for (uint8_t c = 0U; c < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++c) {
		wet.cache.traces[0][c] = 255U * 256U;
	}
	assert(picosystem_garden_world_hash(&dry.world) ==
	       picosystem_garden_world_hash(&wet.world));
	assert(run_hash(&dry) != run_hash(&wet));
	bool diverged = false;
	for (uint16_t i = 0U; i < 1024U; ++i) {
		assert(toy_factory_garden_landing_run_step(&dry) == 0);
		assert(toy_factory_garden_landing_run_step(&wet) == 0);
		if (picosystem_garden_world_hash(&dry.world) !=
		    picosystem_garden_world_hash(&wet.world)) {
			diverged = true;
			break;
		}
	}
	assert(diverged);
}

static void world_equivalence(void)
{
	for (uint8_t mode = 0U; mode < 3U; ++mode) {
		struct picosystem_garden_world plain;
		assert(toy_factory_garden_evaluation_reset(
			       &plain, &toy_factory_garden_rainfed_scenarios[1], 0xed52188cU) == 0);
		assert(picosystem_garden_world_set_climate(
			       &plain, PICOSYSTEM_GARDEN_CLIMATE_SEASONAL) == 0);
		const struct toy_factory_garden_landing_feature_config config = {.version = 1U,
										 .mode = mode};
		struct toy_factory_garden_landing_model model;
		assert(toy_factory_garden_landing_model_import(
			       picosystem_garden_neural_reference_model(), &config, &model) == 0);
		struct toy_factory_garden_landing_run run;
		assert(toy_factory_garden_landing_run_init(&plain, &model, &run) == 0);
		struct toy_factory_garden_landing_run audited = run;
		struct toy_factory_garden_landing_run combined = run;
		struct picosystem_garden_world seed_world = plain;
		uint32_t deaths = 0U;
		for (uint32_t tick = 0U; tick < 32U * 3840U; ++tick) {
			struct picosystem_garden_death_audit expected;
			struct picosystem_garden_death_audit actual;
			struct picosystem_garden_death_audit both_deaths;
			struct picosystem_garden_seed_audit expected_seeds, actual_seeds;
			assert(picosystem_garden_world_step_death_audit(
				       &plain, picosystem_garden_agent_neural_reference_policy(),
				       &expected) == 0);
			assert(toy_factory_garden_landing_run_step(&run) == 0);
			assert(toy_factory_garden_landing_run_step_death_audit(&audited, &actual) ==
			       0);
			assert(picosystem_garden_world_step_seed_audit(
				       &seed_world,
				       picosystem_garden_agent_neural_reference_policy(),
				       &expected_seeds) == 0);
			assert(toy_factory_garden_landing_run_step_audits(&combined, &both_deaths,
									  &actual_seeds) == 0);
			assert(memcmp(&plain, &run.world, sizeof(plain)) == 0);
			assert(memcmp(&plain, &seed_world, sizeof(plain)) == 0);
			assert(memcmp(&run, &audited, sizeof(run)) == 0);
			assert(memcmp(&run, &combined, sizeof(run)) == 0);
			assert(memcmp(&expected, &actual, sizeof(expected)) == 0);
			assert(memcmp(&expected, &both_deaths, sizeof(expected)) == 0);
			assert(memcmp(&expected_seeds, &actual_seeds, sizeof(expected_seeds)) == 0);
			deaths += actual.count;
		}
		assert(deaths > 0U && deaths == plain.death_count);
		assert(plain.agent_telemetry.decision_count > 100U);
	}
}

static void replay_and_rollback(void)
{
	struct picosystem_garden_world world;
	assert(toy_factory_garden_evaluation_reset(&world, &toy_factory_garden_rainfed_scenarios[1],
						   0x82deacfdU) == 0);
	assert(picosystem_garden_world_set_climate(&world, PICOSYSTEM_GARDEN_CLIMATE_SEASONAL) ==
	       0);
	const struct toy_factory_garden_landing_model model = sensor_model();
	struct toy_factory_garden_landing_run run;
	assert(toy_factory_garden_landing_run_init(&world, &model, &run) == 0);
	/* Fork before/after sampling, before/after warmup, and mid-day. */
	const uint32_t checkpoints[] = {0U, 14U, 15U, 3839U, 3840U, 7687U};
	for (size_t c = 0U; c < sizeof(checkpoints) / sizeof(checkpoints[0]); ++c) {
		while (run.world.logic_tick_count < checkpoints[c]) {
			assert(toy_factory_garden_landing_run_step(&run) == 0);
		}
		const struct toy_factory_garden_landing_run saved = run;
		struct toy_factory_garden_landing_run copy = saved;
		assert(run_hash(&saved) == run_hash(&copy));
		for (uint32_t t = 0U; t < 1000U; ++t) {
			assert(toy_factory_garden_landing_run_step(&run) == 0);
			assert(toy_factory_garden_landing_run_step(&copy) == 0);
			assert(memcmp(&run, &copy, sizeof(run)) == 0);
		}
		assert(run_hash(&run) == run_hash(&copy));
		run = saved;
	}
	const struct toy_factory_garden_landing_run saved = run;
	const uint32_t original = run_hash(&run);
	run.cache.traces[0][0] ^= 1U;
	assert(picosystem_garden_world_hash(&run.world) ==
	       picosystem_garden_world_hash(&saved.world));
	/* Keep the marginal above its joint for a structurally valid counterexample. */
	if (run.cache.traces[0][0] < run.cache.traces[2][0]) {
		run.cache.traces[0][0] += 2U;
	}
	assert(run_hash(&run) != original);
	run = saved;
	run.model.common_weights[0][0] ^= 1;
	assert(run_hash(&run) != original);
	run = saved;
	run.model.config.mode = TOY_FACTORY_GARDEN_LANDING_INPUT_CURRENT;
	assert(run_hash(&run) != original);
	run = saved;
	run.cache.ecology_tick++;
	const struct toy_factory_garden_landing_run invalid = run;
	assert(toy_factory_garden_landing_run_step(&run) != 0);
	assert(memcmp(&run, &invalid, sizeof(run)) == 0);
	/* Valid clock but an internal growth error after sampling: bad tip x. */
	assert(picosystem_garden_world_reset(&world, 3U) == 0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 3U) ==
	       0);
	assert(toy_factory_garden_landing_run_init(&world, &model, &run) == 0);
	run.world.logic_tick_count = 14U;
	run.world.nodes[1].x = 0U;
	const struct toy_factory_garden_landing_run failing = run;
	assert(toy_factory_garden_landing_run_step(&run) != 0);
	assert(memcmp(&run, &failing, sizeof(run)) == 0);
	struct picosystem_garden_death_audit audit;
	memset(&audit, 0xa5, sizeof(audit));
	const struct picosystem_garden_death_audit before = audit;
	assert(toy_factory_garden_landing_run_step_death_audit(&run, &audit) != 0);
	assert(memcmp(&run, &failing, sizeof(run)) == 0);
	assert(memcmp(&audit, &before, sizeof(audit)) == 0);
	struct picosystem_garden_seed_audit seeds;
	memset(&seeds, 0xa5, sizeof(seeds));
	const struct picosystem_garden_seed_audit seeds_before = seeds;
	assert(toy_factory_garden_landing_run_step_audits(&run, &audit, &seeds) != 0);
	assert(memcmp(&run, &failing, sizeof(run)) == 0);
	assert(memcmp(&audit, &before, sizeof(audit)) == 0);
	assert(memcmp(&seeds, &seeds_before, sizeof(seeds)) == 0);
	assert(toy_factory_garden_landing_run_step_death_audit(NULL, &audit) == -EINVAL);
	assert(memcmp(&audit, &before, sizeof(audit)) == 0);
	run = saved;
	assert(toy_factory_garden_landing_run_step_death_audit(&run, NULL) == -EINVAL);
	assert(toy_factory_garden_landing_run_step_audits(&run, NULL, &seeds) == -EINVAL);
	assert(toy_factory_garden_landing_run_step_audits(&run, &audit, NULL) == -EINVAL);
	assert(memcmp(&run, &saved, sizeof(run)) == 0);
}

static void json_values(const int8_t *p, size_t size)
{
	putchar('[');
	for (size_t i = 0U; i < size; ++i) {
		printf("%s%d", i ? "," : "", (int)p[i]);
	}
	putchar(']');
}

static void vectors(void)
{
	for (uint32_t i = 0U; i < 512U; ++i) {
		const struct toy_factory_garden_landing_model model = random_model(i);
		const struct picosystem_garden_agent_observation obs = observation(i);
		const struct picosystem_garden_landing_packet packet =
			packet_for(&obs, (uint16_t)(i % 257U));
		struct picosystem_garden_agent_memory memory;
		fill(memory.hidden, sizeof(memory.hidden), i);
		struct toy_factory_garden_landing_features features;
		struct picosystem_garden_agent_decision decision;
		assert(toy_factory_garden_landing_features_encode(&obs, &packet, &model.config,
								  &features) == 0);
		assert(toy_factory_garden_landing_neural_decide(&obs, &memory, &packet, &model,
								&decision) == 0);
		uint8_t file[TOY_FACTORY_GARDEN_LANDING_FILE_SIZE];
		assert(toy_factory_garden_landing_model_encode(&model, file, sizeof(file)) == 0);
		printf("{\"model\":\"");
		for (size_t n = 0U; n < sizeof(file); ++n) {
			printf("%02x", file[n]);
		}
		printf("\",\"common\":");
		json_values(features.legacy.common, 32U);
		printf(",\"candidates\":[");
		for (uint8_t c = 0U; c < 5U; ++c) {
			if (c) {
				putchar(',');
			}
			json_values(features.legacy.candidates[c], 9U);
		}
		printf("],\"landing_common\":");
		json_values(features.landing.common, 9U);
		printf(",\"landing_candidates\":[");
		for (uint8_t c = 0U; c < 5U; ++c) {
			if (c) {
				putchar(',');
			}
			json_values(features.landing.candidates[c], 8U);
		}
		printf("],\"memory\":");
		json_values(memory.hidden, 8U);
		printf(",\"nonce\":%" PRIu32
		       ",\"depth\":%u,\"maximum\":%u,\"count\":%u,\"flags\":[",
		       obs.decision_nonce, obs.depth, obs.maximum_depth, obs.candidate_count);
		for (uint8_t c = 0U; c < obs.candidate_count; ++c) {
			printf("%s%u", c ? "," : "", obs.candidates[c].flags);
		}
		printf("],\"actual\":{\"action\":%u,\"priority\":%d,\"count\":%u,\"order\":[",
		       decision.proposal.action, decision.proposal.priority,
		       decision.proposal.candidate_count);
		for (uint8_t c = 0U; c < 5U; ++c) {
			printf("%s%u", c ? "," : "", decision.proposal.candidate_order[c]);
		}
		printf("],\"memory\":");
		json_values(decision.next_memory.hidden, 8U);
		printf("}}\n");
	}
}

int main(int argc, char **argv)
{
	if ((argc == 2) && (strcmp(argv[1], "--vectors") == 0)) {
		vectors();
		return (fflush(stdout) == 0 && !ferror(stdout)) ? 0 : 1;
	}
	if (argc != 1) {
		return 2;
	}
	legacy_equivalence();
	sensor_effect_and_failures();
	codec();
	history_affects_run();
	world_equivalence();
	replay_and_rollback();
	puts("Landing inference: 3072 legacy comparisons, nonzero sensors, codec, 3 x 32-day "
	     "worlds, 6 checkpoints passed");
	return 0;
}
