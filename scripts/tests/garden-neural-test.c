/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "garden_agent_neural.h"
#include "garden_light.h"

static struct picosystem_garden_agent_observation
test_observation(enum picosystem_garden_node_kind kind)
{
	struct picosystem_garden_agent_observation observation = {
		.decision_nonce = 0U,
		.tip_index = 7U,
		.stored_energy = 128U,
		.stored_water = 256U,
		.plant_node_count = 4U,
		.shoot_node_count = 2U,
		.root_node_count = 2U,
		.active_tip_count = 2U,
		.version = PICOSYSTEM_GARDEN_AGENT_OBSERVATION_VERSION,
		.plant_index = 0U,
		.species_id = PICOSYSTEM_GARDEN_SPECIES_FLOWER,
		.tissue_kind = (uint8_t)kind,
		.depth = 2U,
		.tip_x = 14U,
		.tip_y = 10U,
		.tip_light = UINT8_MAX,
		.tip_moisture = 128U,
		.base_x = 14U,
		.maximum_depth = 10U,
		.flower_depth = 6U,
		.candidate_count = (kind == PICOSYSTEM_GARDEN_NODE_STEM) ? 5U : 3U,
		.sun_phase = PICOSYSTEM_GARDEN_SUN_NOON_PHASE,
		.sun_strength = UINT8_MAX,
		.maintenance_energy_cost = 1U,
		.maintenance_water_cost = 1U,
	};
	for (uint8_t index = 0U; index < observation.candidate_count; ++index) {
		observation.candidates[index] = (struct picosystem_garden_agent_candidate){
			.x = (uint8_t)(10U + index),
			.y = 9U,
			.light = (uint8_t)(index * 48U),
			.moisture = 128U,
			.clearance_squared = 128U,
			.flags = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS |
				 PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE,
		};
	}
	return observation;
}

static void test_feature_contract(void)
{
	assert(sizeof(struct picosystem_garden_neural_features) == 77U);
	assert(sizeof(struct picosystem_garden_neural_model) ==
	       PICOSYSTEM_GARDEN_NEURAL_MODEL_SIZE);

	struct picosystem_garden_agent_observation observation =
		test_observation(PICOSYSTEM_GARDEN_NODE_ROOT);
	observation.species_id = PICOSYSTEM_GARDEN_SPECIES_SHRUB;
	observation.stored_energy = 200U;
	observation.stored_water = 300U;
	observation.plant_node_count = 99U;
	observation.shoot_node_count = 5U;
	observation.root_node_count = 8U;
	observation.leaf_node_count = 3U;
	observation.active_tip_count = 2U;
	observation.parent_delta_x = -1;
	observation.parent_delta_y = 2;
	observation.depth = 3U;
	observation.tip_x = 30U;
	observation.base_x = 32U;
	observation.tip_moisture = 0U;
	observation.sun_strength = PICOSYSTEM_GARDEN_LIGHT_MINIMUM;
	observation.sun_ray_step_x_q4 = -PICOSYSTEM_GARDEN_SUN_MAX_RAY_STEP_X_Q4;
	observation.stress = 3U;
	observation.maintenance_energy_cost = 2U;
	observation.maintenance_water_cost = 3U;
	observation.maintenance_phase = 2U;
	observation.last_energy_income = 4U;
	observation.last_water_income = 20U;
	observation.tip_flags = PICOSYSTEM_GARDEN_NODE_BRANCH_PENDING;
	observation.lean = -2;
	observation.vigor = -1;
	observation.horizontal_tendency = 4;
	observation.genome = (struct picosystem_garden_genome){
		.growth_rate = -2,
		.shoot_bias = 2,
		.light_seeking = -1,
		.water_seeking = 1,
		.reserve_strategy = 1,
	};
	observation.candidates[0] = (struct picosystem_garden_agent_candidate){
		.delta_x = -1,
		.delta_y = 1,
		.light = 0U,
		.moisture = UINT8_MAX,
		.clearance_squared = 128U,
		.flags = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS |
			 PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE,
	};
	observation.candidates[1].flags = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS |
					  PICOSYSTEM_GARDEN_AGENT_CANDIDATE_OWN_NEAR;

	struct picosystem_garden_neural_features features;
	assert(picosystem_garden_neural_encode_features(&observation, &features) == 0);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_SPECIES_FLOWER] == 0);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_SPECIES_SHRUB] == INT8_MAX);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_SPECIES_GROUND_COVER] == 0);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_TISSUE] == -INT8_MAX);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_DEPTH] == 24);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_REMAINING_DEPTH] == 56);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_TIP_FROM_BASE_X] == -16);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_PARENT_DELTA_X] == -16);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_PARENT_DELTA_Y] == 32);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_TIP_LIGHT] == INT8_MAX);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_TIP_MOISTURE] == INT8_MIN);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_ENERGY] == 72);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_WATER] == 22);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_ENERGY_RESERVE] == 28);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_WATER_RESERVE] == 42);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_STRESS] == 48);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_ENERGY_INCOME] == 32);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_WATER_INCOME] == INT8_MAX);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_ROOT_SHOOT_BALANCE] == 24);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_LEAF_COUNT] == 24);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_ACTIVE_TIP_COUNT] == 16);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_VIGOR] == -64);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_SUN_STRENGTH] ==
	       (int8_t)((int32_t)PICOSYSTEM_GARDEN_LIGHT_MINIMUM - 128));
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_SUN_RAY_STEP] ==
	       -PICOSYSTEM_GARDEN_SUN_MAX_RAY_STEP_X_Q4 * 8);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_MAINTENANCE_PHASE] == 32);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_SHAPE_TENDENCY] == 48);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_FLOWER_REMAINING] == 0);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_TIP_STATE] == INT8_MAX);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_GROWTH_RATE] == -64);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_SHOOT_BIAS] == 64);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_LIGHT_SEEKING] == -32);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_WATER_SEEKING] == 32);

	assert(features.candidates[0][PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_DELTA_X] == -16);
	assert(features.candidates[0][PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_DELTA_Y] == 16);
	assert(features.candidates[0][PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_LIGHT] == INT8_MIN);
	assert(features.candidates[0][PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_MOISTURE] == INT8_MAX);
	assert(features.candidates[0][PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_CLEARANCE] == 0);
	assert(features.candidates[0][PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_IN_BOUNDS] == INT8_MAX);
	assert(features.candidates[0][PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_AVAILABLE] == INT8_MAX);
	assert(features.candidates[0][PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_OWN_NEAR] == -INT8_MAX);
	assert(features.candidates[1][PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_AVAILABLE] == -INT8_MAX);
	assert(features.candidates[1][PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_OWN_NEAR] == INT8_MAX);
	const int8_t empty_candidate[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_FEATURE_COUNT] = {0};
	assert(memcmp(features.candidates[3], empty_candidate, sizeof(empty_candidate)) == 0);
	struct picosystem_garden_agent_observation shoot =
		test_observation(PICOSYSTEM_GARDEN_NODE_STEM);
	assert(picosystem_garden_neural_encode_features(&shoot, &features) == 0);
	assert(features.common[PICOSYSTEM_GARDEN_NEURAL_COMMON_FLOWER_REMAINING] == 32);
	shoot.flower_depth = 0U;
	assert(picosystem_garden_neural_encode_features(&shoot, &features) == -ERANGE);
	shoot = test_observation(PICOSYSTEM_GARDEN_NODE_STEM);
	shoot.tip_flags = UINT8_C(0x80);
	assert(picosystem_garden_neural_encode_features(&shoot, &features) == -ERANGE);

	memset(&features, 0x55, sizeof(features));
	assert(picosystem_garden_neural_encode_features(NULL, &features) == -EINVAL);
	const struct picosystem_garden_neural_features empty_features = {0};
	assert(memcmp(&features, &empty_features, sizeof(features)) == 0);
	observation.version = 0U;
	memset(&features, 0x55, sizeof(features));
	assert(picosystem_garden_neural_encode_features(&observation, &features) == -ERANGE);
	assert(memcmp(&features, &empty_features, sizeof(features)) == 0);
	assert(picosystem_garden_neural_encode_features(&observation, NULL) == -EINVAL);
}

static void test_model_validation_and_policy_init(void)
{
	const struct picosystem_garden_neural_model *const reference =
		picosystem_garden_neural_reference_model();
	assert(reference != NULL);
	assert(picosystem_garden_neural_model_validate(reference) == 0);
	assert(picosystem_garden_neural_model_validate(NULL) == -EINVAL);

	struct picosystem_garden_neural_model model = *reference;
	model.magic = 0U;
	assert(picosystem_garden_neural_model_validate(&model) == -ERANGE);
	model = *reference;
	++model.model_version;
	assert(picosystem_garden_neural_model_validate(&model) == -ERANGE);
	model = *reference;
	++model.feature_version;
	assert(picosystem_garden_neural_model_validate(&model) == -ERANGE);
	model = *reference;
	--model.model_size;
	assert(picosystem_garden_neural_model_validate(&model) == -ERANGE);
	model = *reference;
	model.hidden_shift = PICOSYSTEM_GARDEN_NEURAL_MAX_SHIFT + 1U;
	assert(picosystem_garden_neural_model_validate(&model) == -ERANGE);
	model = *reference;
	model.output_shift = PICOSYSTEM_GARDEN_NEURAL_MAX_SHIFT + 1U;
	assert(picosystem_garden_neural_model_validate(&model) == -ERANGE);
	model = *reference;
	model.candidate_hidden_shift = PICOSYSTEM_GARDEN_NEURAL_MAX_SHIFT + 1U;
	assert(picosystem_garden_neural_model_validate(&model) == -ERANGE);
	model = *reference;
	model.reserved[1] = 1U;
	assert(picosystem_garden_neural_model_validate(&model) == -ERANGE);
	model = *reference;
	model.hidden_bias[3] = INT32_MAX;
	assert(picosystem_garden_neural_model_validate(&model) == -ERANGE);
	model = *reference;
	model.action_bias[1] = INT32_MIN;
	assert(picosystem_garden_neural_model_validate(&model) == -ERANGE);
	model = *reference;
	model.memory_bias[7] = INT32_MAX;
	assert(picosystem_garden_neural_model_validate(&model) == -ERANGE);
	model = *reference;
	model.candidate_hidden_bias[2] = INT32_MIN;
	assert(picosystem_garden_neural_model_validate(&model) == -ERANGE);
	model = *reference;
	model.priority_bias = INT32_MAX;
	assert(picosystem_garden_neural_model_validate(&model) == -ERANGE);
	model = *reference;
	model.candidate_output_bias = INT32_MIN;
	assert(picosystem_garden_neural_model_validate(&model) == -ERANGE);

	assert(picosystem_garden_neural_policy_init(reference, NULL) == -EINVAL);
	struct picosystem_garden_agent_policy policy;
	assert(picosystem_garden_neural_policy_init(reference, &policy) == 0);
	assert(policy.decide == picosystem_garden_agent_neural_decide);
	assert(policy.context == reference);
	assert(policy.arbitration == PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS);
	model = *reference;
	model.magic = 0U;
	policy = (struct picosystem_garden_agent_policy){
		.decide = picosystem_garden_agent_baseline_decide,
		.context = reference,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_PHASED,
	};
	assert(picosystem_garden_neural_policy_init(&model, &policy) == -ERANGE);
	const struct picosystem_garden_agent_policy empty_policy = {0};
	assert(memcmp(&policy, &empty_policy, sizeof(policy)) == 0);

	const struct picosystem_garden_agent_policy *const reference_policy =
		picosystem_garden_agent_neural_reference_policy();
	assert(reference_policy != NULL);
	assert(reference_policy->decide == picosystem_garden_agent_neural_decide);
	assert(reference_policy->context == reference);
	assert(reference_policy->arbitration == PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS);
}

static struct picosystem_garden_neural_model synthetic_model(void)
{
	return (struct picosystem_garden_neural_model){
		.magic = PICOSYSTEM_GARDEN_NEURAL_MODEL_MAGIC,
		.model_version = PICOSYSTEM_GARDEN_NEURAL_MODEL_VERSION,
		.feature_version = PICOSYSTEM_GARDEN_NEURAL_FEATURE_VERSION,
		.model_size = PICOSYSTEM_GARDEN_NEURAL_MODEL_SIZE,
	};
}

static void test_integer_inference_and_ranking(void)
{
	struct picosystem_garden_neural_model model = synthetic_model();
	model.action_bias[PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND] = 10;
	model.priority_bias = 123;
	model.memory_bias[0] = 200;
	model.memory_bias[1] = -200;
	model.candidate_feature_weights[0][PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_AVAILABLE] = 1;
	model.candidate_feature_weights[1][PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_LIGHT] = 1;
	model.candidate_output_weights[0] = 2;
	model.candidate_output_weights[1] = 1;
	assert(picosystem_garden_neural_model_validate(&model) == 0);

	struct picosystem_garden_agent_observation observation =
		test_observation(PICOSYSTEM_GARDEN_NODE_STEM);
	observation.candidates[0].light = 0U;
	observation.candidates[1].light = 64U;
	observation.candidates[2].light = 128U;
	observation.candidates[3].light = 192U;
	observation.candidates[4].light = UINT8_MAX;
	const struct picosystem_garden_agent_memory memory = {0};
	struct picosystem_garden_agent_decision decision;
	assert(picosystem_garden_agent_neural_decide(&observation, &memory, &decision, &model) ==
	       0);
	assert(decision.proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND);
	assert(decision.proposal.priority == 123);
	assert(decision.proposal.candidate_count == 5U);
	const uint8_t expected_order[] = {4U, 3U, 0U, 1U, 2U};
	assert(memcmp(decision.proposal.candidate_order, expected_order, sizeof(expected_order)) ==
	       0);
	assert(decision.next_memory.hidden[0] == INT8_MAX);
	assert(decision.next_memory.hidden[1] == INT8_MIN);

	model.action_bias[PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT] = 11;
	assert(picosystem_garden_agent_neural_decide(&observation, &memory, &decision, &model) ==
	       0);
	assert(decision.proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT);
	assert(decision.proposal.candidate_count == 0U);
	for (uint8_t index = 0U; index < PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES; ++index) {
		assert(decision.proposal.candidate_order[index] ==
		       PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE);
	}
	model.action_bias[PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP] = 12;
	assert(picosystem_garden_agent_neural_decide(&observation, &memory, &decision, &model) ==
	       0);
	assert(decision.proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP);

	model = synthetic_model();
	model.action_bias[PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND] = 1;
	observation.decision_nonce = 2U;
	assert(picosystem_garden_agent_neural_decide(&observation, &memory, &decision, &model) ==
	       0);
	const uint8_t expected_tie_order[] = {2U, 3U, 4U, 0U, 1U};
	assert(memcmp(decision.proposal.candidate_order, expected_tie_order,
		      sizeof(expected_tie_order)) == 0);

	observation.depth = observation.maximum_depth;
	assert(picosystem_garden_agent_neural_decide(&observation, &memory, &decision, &model) ==
	       0);
	assert(decision.proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP);
	assert(decision.proposal.priority == INT16_MAX);
	assert(decision.proposal.candidate_count == 0U);
	observation.depth = 2U;
	for (uint8_t index = 0U; index < observation.candidate_count; ++index) {
		observation.candidates[index].flags = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS;
	}
	assert(picosystem_garden_agent_neural_decide(&observation, &memory, &decision, &model) ==
	       0);
	assert(decision.proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP);
	assert(decision.proposal.priority == INT16_MAX - 1);

	assert(picosystem_garden_agent_neural_decide(&observation, &memory, NULL, &model) ==
	       -EINVAL);
	assert(picosystem_garden_agent_neural_decide(NULL, &memory, &decision, &model) == -EINVAL);
	assert(decision.proposal.tip_index == 0U);
	assert(picosystem_garden_agent_neural_decide(&observation, NULL, &decision, &model) ==
	       -EINVAL);
	assert(picosystem_garden_agent_neural_decide(&observation, &memory, &decision, NULL) ==
	       -EINVAL);
}

static void test_context_conditioned_candidate_layer(void)
{
	struct picosystem_garden_neural_model model = synthetic_model();
	model.action_bias[PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND] = 1;
	model.hidden_weights[0][PICOSYSTEM_GARDEN_NEURAL_COMMON_TISSUE] = 1;
	model.candidate_hidden_bias[0] = -127;
	model.candidate_hidden_weights[0][0] = 1;
	model.candidate_feature_weights[0][PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_LIGHT] = 1;
	model.candidate_output_weights[0] = 1;
	const struct picosystem_garden_agent_memory memory = {0};
	struct picosystem_garden_agent_decision decision;

	struct picosystem_garden_agent_observation shoot =
		test_observation(PICOSYSTEM_GARDEN_NODE_STEM);
	shoot.decision_nonce = 1U;
	shoot.candidates[4].light = UINT8_MAX;
	assert(picosystem_garden_agent_neural_decide(&shoot, &memory, &decision, &model) == 0);
	assert(decision.proposal.candidate_order[0] == 4U);

	struct picosystem_garden_agent_observation root =
		test_observation(PICOSYSTEM_GARDEN_NODE_ROOT);
	root.decision_nonce = 1U;
	root.candidates[2].light = UINT8_MAX;
	assert(picosystem_garden_agent_neural_decide(&root, &memory, &decision, &model) == 0);
	assert(decision.proposal.candidate_order[0] == 1U);
}

static void test_reference_policy_determinism(void)
{
	const struct picosystem_garden_agent_policy *const policy =
		picosystem_garden_agent_neural_reference_policy();
	const struct picosystem_garden_agent_memory memory = {0};
	struct picosystem_garden_agent_observation observation =
		test_observation(PICOSYSTEM_GARDEN_NODE_STEM);
	struct picosystem_garden_agent_decision first;
	struct picosystem_garden_agent_decision second;
	assert(picosystem_garden_agent_decide(policy, &observation, &memory, &first) == 0);
	assert(picosystem_garden_agent_decide(policy, &observation, &memory, &second) == 0);
	assert(memcmp(&first, &second, sizeof(first)) == 0);
	assert(first.proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND);
	const struct picosystem_garden_agent_memory empty_memory = {0};
	assert(memcmp(&first.next_memory, &empty_memory, sizeof(empty_memory)) != 0);

	observation.depth = observation.maximum_depth;
	assert(picosystem_garden_agent_decide(policy, &observation, &memory, &first) == 0);
	assert(first.proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP);
	assert(first.proposal.priority == INT16_MAX);
}

int main(void)
{
	test_feature_contract();
	test_model_validation_and_policy_init();
	test_integer_inference_and_ranking();
	test_context_conditioned_candidate_layer();
	test_reference_policy_determinism();
	puts("garden neural tests passed");
	return 0;
}
