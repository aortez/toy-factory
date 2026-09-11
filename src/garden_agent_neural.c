/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "garden_agent_neural.h"

#include <errno.h>
#include <limits.h>
#include <stddef.h>
#include <stdint.h>

#define GARDEN_NEURAL_MAX_ABSOLUTE_BIAS INT32_C(1000000)
#define GARDEN_NEURAL_TERMINAL_PRIORITY INT16_MAX
#define GARDEN_NEURAL_BLOCKED_PRIORITY  (INT16_MAX - 1)

enum garden_neural_reference_hidden_unit {
	GARDEN_NEURAL_HIDDEN_ROOT_WATER_PRESSURE,
	GARDEN_NEURAL_HIDDEN_SHOOT_ENERGY_PRESSURE,
	GARDEN_NEURAL_HIDDEN_ENERGY_PRESSURE,
	GARDEN_NEURAL_HIDDEN_WATER_PRESSURE,
	GARDEN_NEURAL_HIDDEN_ROOT_EXCESS,
	GARDEN_NEURAL_HIDDEN_SHOOT_EXCESS,
	GARDEN_NEURAL_HIDDEN_DARKNESS,
	GARDEN_NEURAL_HIDDEN_SHOOT_LEAF_DEFICIT,
	GARDEN_NEURAL_HIDDEN_ROOT,
	GARDEN_NEURAL_HIDDEN_SHOOT,
	GARDEN_NEURAL_HIDDEN_STRESS,
	GARDEN_NEURAL_HIDDEN_ENERGY_INCOME,
	GARDEN_NEURAL_HIDDEN_WATER_INCOME,
	GARDEN_NEURAL_HIDDEN_ACTIVE_TIPS,
	GARDEN_NEURAL_HIDDEN_SHAPE,
	GARDEN_NEURAL_HIDDEN_DEPTH,
	GARDEN_NEURAL_HIDDEN_REFERENCE_COUNT,
};

enum garden_neural_reference_candidate_unit {
	GARDEN_NEURAL_CANDIDATE_SHOOT_LIGHT,
	GARDEN_NEURAL_CANDIDATE_ROOT_MOISTURE,
	GARDEN_NEURAL_CANDIDATE_AVAILABLE,
	GARDEN_NEURAL_CANDIDATE_CLEARANCE,
	GARDEN_NEURAL_CANDIDATE_OWN_NEAR,
	GARDEN_NEURAL_CANDIDATE_FOREIGN_NEAR,
	GARDEN_NEURAL_CANDIDATE_SHOOT_UP,
	GARDEN_NEURAL_CANDIDATE_ROOT_DOWN,
	GARDEN_NEURAL_CANDIDATE_REFERENCE_COUNT,
};

_Static_assert(PICOSYSTEM_GARDEN_NEURAL_COMMON_FEATURE_ENUM_COUNT ==
		       PICOSYSTEM_GARDEN_NEURAL_COMMON_FEATURE_COUNT,
	       "Garden neural common feature count changed");
_Static_assert(PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_FEATURE_ENUM_COUNT ==
		       PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_FEATURE_COUNT,
	       "Garden neural candidate feature count changed");
_Static_assert(GARDEN_NEURAL_HIDDEN_REFERENCE_COUNT == PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT,
	       "Garden neural reference hidden layer changed");
_Static_assert(GARDEN_NEURAL_CANDIDATE_REFERENCE_COUNT ==
		       PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT,
	       "Garden neural reference candidate layer changed");
_Static_assert(sizeof(struct picosystem_garden_neural_features) == 77U,
	       "Garden neural feature layout changed");
_Static_assert(sizeof(struct picosystem_garden_neural_model) == PICOSYSTEM_GARDEN_NEURAL_MODEL_SIZE,
	       "Garden neural model ABI changed");

static int8_t clamp_i8(int32_t value)
{
	if (value < INT8_MIN) {
		return INT8_MIN;
	}
	return (value > INT8_MAX) ? INT8_MAX : (int8_t)value;
}

static int16_t clamp_i16(int32_t value)
{
	if (value < INT16_MIN) {
		return INT16_MIN;
	}
	return (value > INT16_MAX) ? INT16_MAX : (int16_t)value;
}

static int8_t flag_feature(uint8_t flags, uint8_t flag)
{
	return ((flags & flag) != 0U) ? INT8_C(127) : INT8_C(-127);
}

static int32_t scale_accumulator(int32_t value, uint8_t shift)
{
	/* Signed division has deterministic truncation toward zero in C11. */
	return value / (INT32_C(1) << shift);
}

static int8_t relu_i8(int32_t value)
{
	if (value <= 0) {
		return 0;
	}
	return (value > INT8_MAX) ? INT8_MAX : (int8_t)value;
}

static int32_t dot_product(int32_t bias, const int8_t *weights, const int8_t *values, size_t count)
{
	int32_t accumulator = bias;
	for (size_t index = 0U; index < count; ++index) {
		accumulator += (int32_t)weights[index] * values[index];
	}
	return accumulator;
}

static void initialize_decision(uint16_t tip_index,
				struct picosystem_garden_agent_decision *decision)
{
	*decision = (struct picosystem_garden_agent_decision){
		.proposal =
			{
				.tip_index = tip_index,
				.action = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT,
			},
	};
	for (uint8_t index = 0U; index < PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES; ++index) {
		decision->proposal.candidate_order[index] = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE;
	}
}

int picosystem_garden_neural_encode_features(
	const struct picosystem_garden_agent_observation *observation,
	struct picosystem_garden_neural_features *features)
{
	if (features == NULL) {
		return -EINVAL;
	}
	*features = (struct picosystem_garden_neural_features){0};
	if (observation == NULL) {
		return -EINVAL;
	}
	if (!picosystem_garden_agent_observation_is_valid(observation)) {
		return -ERANGE;
	}

	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_SPECIES_FLOWER] =
		(observation->species_id == PICOSYSTEM_GARDEN_SPECIES_FLOWER) ? INT8_MAX : 0;
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_SPECIES_SHRUB] =
		(observation->species_id == PICOSYSTEM_GARDEN_SPECIES_SHRUB) ? INT8_MAX : 0;
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_SPECIES_GROUND_COVER] =
		(observation->species_id == PICOSYSTEM_GARDEN_SPECIES_GROUND_COVER) ? INT8_MAX : 0;
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_TISSUE] =
		(observation->tissue_kind == PICOSYSTEM_GARDEN_NODE_STEM) ? INT8_MAX : -INT8_MAX;
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_DEPTH] =
		clamp_i8((int32_t)observation->depth * 8);
	const int32_t remaining_depth = (observation->depth < observation->maximum_depth)
						? observation->maximum_depth - observation->depth
						: 0;
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_REMAINING_DEPTH] =
		clamp_i8(remaining_depth * 8);
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_TIP_FROM_BASE_X] =
		clamp_i8(((int32_t)observation->tip_x - observation->base_x) * 8);
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_PARENT_DELTA_X] =
		clamp_i8((int32_t)observation->parent_delta_x * 16);
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_PARENT_DELTA_Y] =
		clamp_i8((int32_t)observation->parent_delta_y * 16);
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_TIP_LIGHT] =
		clamp_i8((int32_t)observation->tip_light - 128);
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_TIP_MOISTURE] =
		clamp_i8((int32_t)observation->tip_moisture - 128);
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_ENERGY] =
		clamp_i8((int32_t)observation->stored_energy - 128);
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_WATER] =
		clamp_i8(((int32_t)observation->stored_water / 2) - 128);

	const int32_t reserve_periods = PICOSYSTEM_GARDEN_NIGHT_RESERVE_PERIODS +
					((int32_t)observation->genome.reserve_strategy *
					 PICOSYSTEM_GARDEN_RESERVE_TRAIT_PERIOD_STEP);
	const int32_t energy_reserve =
		(int32_t)observation->maintenance_energy_cost * reserve_periods;
	const int32_t water_reserve =
		(int32_t)observation->maintenance_water_cost * reserve_periods;
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_ENERGY_RESERVE] =
		clamp_i8(((int32_t)observation->stored_energy - energy_reserve) / 4);
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_WATER_RESERVE] =
		clamp_i8(((int32_t)observation->stored_water - water_reserve) / 4);
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_STRESS] =
		clamp_i8((int32_t)observation->stress * 16);
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_ENERGY_INCOME] =
		clamp_i8((int32_t)observation->last_energy_income * 8);
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_WATER_INCOME] =
		clamp_i8((int32_t)observation->last_water_income * 8);
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_ROOT_SHOOT_BALANCE] = clamp_i8(
		((int32_t)observation->root_node_count - observation->shoot_node_count) * 8);
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_LEAF_COUNT] =
		clamp_i8((int32_t)observation->leaf_node_count * 8);
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_ACTIVE_TIP_COUNT] =
		clamp_i8((int32_t)observation->active_tip_count * 8);
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_VIGOR] =
		clamp_i8((int32_t)observation->vigor * 64);
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_SUN_STRENGTH] =
		clamp_i8((int32_t)observation->sun_strength - 128);
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_SUN_RAY_STEP] =
		clamp_i8((int32_t)observation->sun_ray_step_x_q4 * 8);
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_MAINTENANCE_PHASE] =
		clamp_i8(((int32_t)observation->maintenance_phase * 64) - 96);
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_SHAPE_TENDENCY] =
		clamp_i8(((int32_t)observation->lean + observation->horizontal_tendency) * 24);
	if (observation->tissue_kind == PICOSYSTEM_GARDEN_NODE_STEM) {
		features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_FLOWER_REMAINING] =
			clamp_i8(((int32_t)observation->flower_depth - observation->depth) * 8);
	}
	if ((observation->tip_flags & PICOSYSTEM_GARDEN_NODE_BRANCH_PENDING) != 0U) {
		features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_TIP_STATE] = INT8_MAX;
	} else if ((observation->tip_flags & PICOSYSTEM_GARDEN_NODE_PRUNED) != 0U) {
		features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_TIP_STATE] = -INT8_MAX;
	}
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_GROWTH_RATE] =
		clamp_i8((int32_t)observation->genome.growth_rate * 32);
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_SHOOT_BIAS] =
		clamp_i8((int32_t)observation->genome.shoot_bias * 32);
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_LIGHT_SEEKING] =
		clamp_i8((int32_t)observation->genome.light_seeking * 32);
	features->common[PICOSYSTEM_GARDEN_NEURAL_COMMON_WATER_SEEKING] =
		clamp_i8((int32_t)observation->genome.water_seeking * 32);

	for (uint8_t index = 0U; index < observation->candidate_count; ++index) {
		const struct picosystem_garden_agent_candidate *const candidate =
			&observation->candidates[index];
		int8_t *const encoded = features->candidates[index];
		encoded[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_DELTA_X] =
			clamp_i8((int32_t)candidate->delta_x * 16);
		encoded[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_DELTA_Y] =
			clamp_i8((int32_t)candidate->delta_y * 16);
		encoded[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_LIGHT] =
			clamp_i8((int32_t)candidate->light - 128);
		encoded[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_MOISTURE] =
			clamp_i8((int32_t)candidate->moisture - 128);
		encoded[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_CLEARANCE] =
			clamp_i8((int32_t)candidate->clearance_squared - 128);
		encoded[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_IN_BOUNDS] =
			flag_feature(candidate->flags, PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS);
		encoded[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_AVAILABLE] =
			flag_feature(candidate->flags, PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE);
		encoded[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_OWN_NEAR] =
			flag_feature(candidate->flags, PICOSYSTEM_GARDEN_AGENT_CANDIDATE_OWN_NEAR);
		encoded[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_FOREIGN_NEAR] = flag_feature(
			candidate->flags, PICOSYSTEM_GARDEN_AGENT_CANDIDATE_FOREIGN_NEAR);
	}
	return 0;
}

static bool bias_is_safe(int32_t value)
{
	return (value >= -GARDEN_NEURAL_MAX_ABSOLUTE_BIAS) &&
	       (value <= GARDEN_NEURAL_MAX_ABSOLUTE_BIAS);
}

int picosystem_garden_neural_model_validate(const struct picosystem_garden_neural_model *model)
{
	if (model == NULL) {
		return -EINVAL;
	}
	if ((model->magic != PICOSYSTEM_GARDEN_NEURAL_MODEL_MAGIC) ||
	    (model->model_version != PICOSYSTEM_GARDEN_NEURAL_MODEL_VERSION) ||
	    (model->feature_version != PICOSYSTEM_GARDEN_NEURAL_FEATURE_VERSION) ||
	    (model->model_size != sizeof(*model)) ||
	    (model->hidden_shift > PICOSYSTEM_GARDEN_NEURAL_MAX_SHIFT) ||
	    (model->output_shift > PICOSYSTEM_GARDEN_NEURAL_MAX_SHIFT) ||
	    (model->candidate_hidden_shift > PICOSYSTEM_GARDEN_NEURAL_MAX_SHIFT) ||
	    (model->reserved[0] != 0U) || (model->reserved[1] != 0U) ||
	    (model->reserved[2] != 0U) || !bias_is_safe(model->priority_bias) ||
	    !bias_is_safe(model->candidate_output_bias)) {
		return -ERANGE;
	}
	for (uint8_t index = 0U; index < PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT; ++index) {
		if (!bias_is_safe(model->hidden_bias[index])) {
			return -ERANGE;
		}
	}
	for (uint8_t index = 0U; index < PICOSYSTEM_GARDEN_AGENT_ACTION_COUNT; ++index) {
		if (!bias_is_safe(model->action_bias[index])) {
			return -ERANGE;
		}
	}
	for (uint8_t index = 0U; index < PICOSYSTEM_GARDEN_AGENT_MEMORY_WIDTH; ++index) {
		if (!bias_is_safe(model->memory_bias[index])) {
			return -ERANGE;
		}
	}
	for (uint8_t index = 0U; index < PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT; ++index) {
		if (!bias_is_safe(model->candidate_hidden_bias[index])) {
			return -ERANGE;
		}
	}
	return 0;
}

int picosystem_garden_neural_policy_init(const struct picosystem_garden_neural_model *model,
					 struct picosystem_garden_agent_policy *policy)
{
	if (policy == NULL) {
		return -EINVAL;
	}
	*policy = (struct picosystem_garden_agent_policy){0};
	const int err = picosystem_garden_neural_model_validate(model);
	if (err != 0) {
		return err;
	}
	*policy = (struct picosystem_garden_agent_policy){
		.decide = picosystem_garden_agent_neural_decide,
		.context = model,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS,
	};
	return 0;
}

static void evaluate_hidden(const struct picosystem_garden_neural_model *model,
			    const struct picosystem_garden_neural_features *features,
			    const struct picosystem_garden_agent_memory *memory, int8_t *hidden)
{
	for (uint8_t unit = 0U; unit < PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT; ++unit) {
		int32_t accumulator = dot_product(model->hidden_bias[unit],
						  model->hidden_weights[unit], features->common,
						  PICOSYSTEM_GARDEN_NEURAL_COMMON_FEATURE_COUNT);
		accumulator = dot_product(
			accumulator,
			&model->hidden_weights[unit][PICOSYSTEM_GARDEN_NEURAL_COMMON_FEATURE_COUNT],
			memory->hidden, PICOSYSTEM_GARDEN_AGENT_MEMORY_WIDTH);
		hidden[unit] = relu_i8(scale_accumulator(accumulator, model->hidden_shift));
	}
}

static int32_t candidate_score(const struct picosystem_garden_neural_model *model,
			       const struct picosystem_garden_neural_features *features,
			       const int8_t *hidden, uint8_t candidate_index)
{
	int8_t candidate_hidden[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT];
	for (uint8_t unit = 0U; unit < PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT; ++unit) {
		int32_t accumulator = dot_product(model->candidate_hidden_bias[unit],
						  model->candidate_hidden_weights[unit], hidden,
						  PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT);
		accumulator = dot_product(accumulator, model->candidate_feature_weights[unit],
					  features->candidates[candidate_index],
					  PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_FEATURE_COUNT);
		candidate_hidden[unit] =
			relu_i8(scale_accumulator(accumulator, model->candidate_hidden_shift));
	}
	return scale_accumulator(dot_product(model->candidate_output_bias,
					     model->candidate_output_weights, candidate_hidden,
					     PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT),
				 model->output_shift);
}

static void rank_candidates(const struct picosystem_garden_neural_model *model,
			    const struct picosystem_garden_neural_features *features,
			    const int8_t *hidden,
			    const struct picosystem_garden_agent_observation *observation,
			    struct picosystem_garden_agent_proposal *proposal)
{
	int32_t scores[PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES];
	const uint8_t rotation =
		(uint8_t)(observation->decision_nonce % observation->candidate_count);
	proposal->candidate_count = observation->candidate_count;
	for (uint8_t offset = 0U; offset < observation->candidate_count; ++offset) {
		const uint8_t candidate_index =
			(uint8_t)((rotation + offset) % observation->candidate_count);
		proposal->candidate_order[offset] = candidate_index;
		scores[offset] = candidate_score(model, features, hidden, candidate_index);
	}

	/* Stable insertion sort preserves the nonce-rotated order for exact ties. */
	for (uint8_t index = 1U; index < observation->candidate_count; ++index) {
		const uint8_t candidate_index = proposal->candidate_order[index];
		const int32_t score = scores[index];
		uint8_t destination = index;
		while ((destination > 0U) && (scores[destination - 1U] < score)) {
			proposal->candidate_order[destination] =
				proposal->candidate_order[destination - 1U];
			scores[destination] = scores[destination - 1U];
			--destination;
		}
		proposal->candidate_order[destination] = candidate_index;
		scores[destination] = score;
	}
}

static void clear_candidates(struct picosystem_garden_agent_proposal *proposal)
{
	proposal->candidate_count = 0U;
	for (uint8_t index = 0U; index < PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES; ++index) {
		proposal->candidate_order[index] = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE;
	}
}

static bool has_available_candidate(const struct picosystem_garden_agent_observation *observation)
{
	for (uint8_t index = 0U; index < observation->candidate_count; ++index) {
		if ((observation->candidates[index].flags &
		     PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE) != 0U) {
			return true;
		}
	}
	return false;
}

int picosystem_garden_agent_neural_decide(
	const struct picosystem_garden_agent_observation *observation,
	const struct picosystem_garden_agent_memory *memory,
	struct picosystem_garden_agent_decision *decision, const void *context)
{
	if (decision == NULL) {
		return -EINVAL;
	}
	initialize_decision((observation == NULL) ? 0U : observation->tip_index, decision);
	if ((observation == NULL) || (memory == NULL) || (context == NULL)) {
		return -EINVAL;
	}
	const struct picosystem_garden_neural_model *const model = context;
	int err = picosystem_garden_neural_model_validate(model);
	if (err != 0) {
		return err;
	}
	struct picosystem_garden_neural_features features;
	err = picosystem_garden_neural_encode_features(observation, &features);
	if (err != 0) {
		return err;
	}

	int8_t hidden[PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT];
	evaluate_hidden(model, &features, memory, hidden);
	uint8_t selected_action = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT;
	int32_t selected_logit =
		scale_accumulator(dot_product(model->action_bias[selected_action],
					      model->action_weights[selected_action], hidden,
					      PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT),
				  model->output_shift);
	for (uint8_t action = 1U; action < PICOSYSTEM_GARDEN_AGENT_ACTION_COUNT; ++action) {
		const int32_t logit = scale_accumulator(
			dot_product(model->action_bias[action], model->action_weights[action],
				    hidden, PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT),
			model->output_shift);
		if (logit > selected_logit) {
			selected_action = action;
			selected_logit = logit;
		}
	}
	decision->proposal.action = selected_action;
	decision->proposal.priority = clamp_i16(
		scale_accumulator(dot_product(model->priority_bias, model->priority_weights, hidden,
					      PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT),
				  model->output_shift));
	for (uint8_t index = 0U; index < PICOSYSTEM_GARDEN_AGENT_MEMORY_WIDTH; ++index) {
		decision->next_memory.hidden[index] = clamp_i8(scale_accumulator(
			dot_product(model->memory_bias[index], model->memory_weights[index], hidden,
				    PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT),
			model->output_shift));
	}

	if (observation->depth >= observation->maximum_depth) {
		decision->proposal.action = PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP;
		decision->proposal.priority = GARDEN_NEURAL_TERMINAL_PRIORITY;
		return 0;
	}
	if (!has_available_candidate(observation)) {
		decision->proposal.action = PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP;
		decision->proposal.priority = GARDEN_NEURAL_BLOCKED_PRIORITY;
		return 0;
	}
	if (decision->proposal.action != PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND) {
		clear_candidates(&decision->proposal);
		return 0;
	}
	rank_candidates(model, &features, hidden, observation, &decision->proposal);
	return 0;
}

static const struct picosystem_garden_neural_model reference_model = {
	.magic = PICOSYSTEM_GARDEN_NEURAL_MODEL_MAGIC,
	.model_version = PICOSYSTEM_GARDEN_NEURAL_MODEL_VERSION,
	.feature_version = PICOSYSTEM_GARDEN_NEURAL_FEATURE_VERSION,
	.model_size = PICOSYSTEM_GARDEN_NEURAL_MODEL_SIZE,
	.hidden_shift = 7U,
	.output_shift = 7U,
	.candidate_hidden_shift = 7U,
	.hidden_bias =
		{
			[GARDEN_NEURAL_HIDDEN_SHOOT_LEAF_DEFICIT] = 1016,
		},
	.hidden_weights =
		{
			[GARDEN_NEURAL_HIDDEN_ROOT_WATER_PRESSURE] =
				{
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_TISSUE] = -16,
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_WATER] = -16,
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_FEATURE_COUNT + 1U] = 32,
				},
			[GARDEN_NEURAL_HIDDEN_SHOOT_ENERGY_PRESSURE] =
				{
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_TISSUE] = 16,
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_ENERGY] = -16,
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_FEATURE_COUNT] = 32,
				},
			[GARDEN_NEURAL_HIDDEN_ENERGY_PRESSURE] =
				{
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_ENERGY] = -16,
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_FEATURE_COUNT] = 32,
				},
			[GARDEN_NEURAL_HIDDEN_WATER_PRESSURE] =
				{
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_WATER] = -16,
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_FEATURE_COUNT + 1U] = 32,
				},
			[GARDEN_NEURAL_HIDDEN_ROOT_EXCESS] =
				{
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_ROOT_SHOOT_BALANCE] = 16,
				},
			[GARDEN_NEURAL_HIDDEN_SHOOT_EXCESS] =
				{
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_ROOT_SHOOT_BALANCE] = -16,
				},
			[GARDEN_NEURAL_HIDDEN_DARKNESS] =
				{
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_SUN_STRENGTH] = -16,
				},
			[GARDEN_NEURAL_HIDDEN_SHOOT_LEAF_DEFICIT] =
				{
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_TISSUE] = 8,
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_LEAF_COUNT] = -16,
				},
			[GARDEN_NEURAL_HIDDEN_ROOT] =
				{
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_TISSUE] = -64,
				},
			[GARDEN_NEURAL_HIDDEN_SHOOT] =
				{
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_TISSUE] = 64,
				},
			[GARDEN_NEURAL_HIDDEN_STRESS] =
				{
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_STRESS] = 16,
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_FEATURE_COUNT + 3U] = 32,
				},
			[GARDEN_NEURAL_HIDDEN_ENERGY_INCOME] =
				{
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_ENERGY_INCOME] = 32,
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_FEATURE_COUNT + 4U] = 32,
				},
			[GARDEN_NEURAL_HIDDEN_WATER_INCOME] =
				{
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_WATER_INCOME] = 32,
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_FEATURE_COUNT + 5U] = 32,
				},
			[GARDEN_NEURAL_HIDDEN_ACTIVE_TIPS] =
				{
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_ACTIVE_TIP_COUNT] = 16,
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_FEATURE_COUNT + 6U] = 32,
				},
			[GARDEN_NEURAL_HIDDEN_SHAPE] =
				{
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_SHAPE_TENDENCY] = 8,
				},
			[GARDEN_NEURAL_HIDDEN_DEPTH] =
				{
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_DEPTH] = 8,
					[PICOSYSTEM_GARDEN_NEURAL_COMMON_FEATURE_COUNT + 7U] = 32,
				},
		},
	.action_bias =
		{
			[PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT] = -256,
			[PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND] = 2304,
			[PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP] = -2048,
		},
	.action_weights =
		{
			[PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT] =
				{
					[GARDEN_NEURAL_HIDDEN_ENERGY_PRESSURE] = 64,
					[GARDEN_NEURAL_HIDDEN_WATER_PRESSURE] = 64,
					[GARDEN_NEURAL_HIDDEN_DARKNESS] = 32,
					[GARDEN_NEURAL_HIDDEN_STRESS] = 64,
				},
			[PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND] =
				{
					[GARDEN_NEURAL_HIDDEN_SHOOT_LEAF_DEFICIT] = 16,
					[GARDEN_NEURAL_HIDDEN_ENERGY_INCOME] = 32,
					[GARDEN_NEURAL_HIDDEN_WATER_INCOME] = 32,
				},
		},
	.priority_weights =
		{
			[GARDEN_NEURAL_HIDDEN_ROOT_WATER_PRESSURE] = 96,
			[GARDEN_NEURAL_HIDDEN_SHOOT_ENERGY_PRESSURE] = 96,
			[GARDEN_NEURAL_HIDDEN_SHOOT_LEAF_DEFICIT] = 32,
			[GARDEN_NEURAL_HIDDEN_STRESS] = 16,
		},
	.memory_weights =
		{
			[0] = {[GARDEN_NEURAL_HIDDEN_ENERGY_PRESSURE] = 96},
			[1] = {[GARDEN_NEURAL_HIDDEN_WATER_PRESSURE] = 96},
			[2] =
				{
					[GARDEN_NEURAL_HIDDEN_ROOT_EXCESS] = 96,
					[GARDEN_NEURAL_HIDDEN_SHOOT_EXCESS] = -96,
				},
			[3] = {[GARDEN_NEURAL_HIDDEN_STRESS] = 96},
			[4] = {[GARDEN_NEURAL_HIDDEN_ENERGY_INCOME] = 96},
			[5] = {[GARDEN_NEURAL_HIDDEN_WATER_INCOME] = 96},
			[6] = {[GARDEN_NEURAL_HIDDEN_ACTIVE_TIPS] = 96},
			[7] = {[GARDEN_NEURAL_HIDDEN_DEPTH] = 96},
		},
	.candidate_hidden_weights =
		{
			[GARDEN_NEURAL_CANDIDATE_SHOOT_LIGHT] =
				{
					[GARDEN_NEURAL_HIDDEN_SHOOT] = 64,
				},
			[GARDEN_NEURAL_CANDIDATE_ROOT_MOISTURE] =
				{
					[GARDEN_NEURAL_HIDDEN_ROOT] = 64,
				},
			[GARDEN_NEURAL_CANDIDATE_SHOOT_UP] =
				{
					[GARDEN_NEURAL_HIDDEN_SHOOT] = 64,
				},
			[GARDEN_NEURAL_CANDIDATE_ROOT_DOWN] =
				{
					[GARDEN_NEURAL_HIDDEN_ROOT] = 64,
				},
		},
	.candidate_feature_weights =
		{
			[GARDEN_NEURAL_CANDIDATE_SHOOT_LIGHT] =
				{
					[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_LIGHT] = 16,
				},
			[GARDEN_NEURAL_CANDIDATE_ROOT_MOISTURE] =
				{
					[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_MOISTURE] = 16,
				},
			[GARDEN_NEURAL_CANDIDATE_AVAILABLE] =
				{
					[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_AVAILABLE] = 64,
				},
			[GARDEN_NEURAL_CANDIDATE_CLEARANCE] =
				{
					[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_CLEARANCE] = 16,
				},
			[GARDEN_NEURAL_CANDIDATE_OWN_NEAR] =
				{
					[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_OWN_NEAR] = 64,
				},
			[GARDEN_NEURAL_CANDIDATE_FOREIGN_NEAR] =
				{
					[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_FOREIGN_NEAR] = 64,
				},
			[GARDEN_NEURAL_CANDIDATE_SHOOT_UP] =
				{
					[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_DELTA_Y] = -32,
				},
			[GARDEN_NEURAL_CANDIDATE_ROOT_DOWN] =
				{
					[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_DELTA_Y] = 32,
				},
		},
	.candidate_output_weights =
		{
			[GARDEN_NEURAL_CANDIDATE_SHOOT_LIGHT] = 24,
			[GARDEN_NEURAL_CANDIDATE_ROOT_MOISTURE] = 24,
			[GARDEN_NEURAL_CANDIDATE_AVAILABLE] = 64,
			[GARDEN_NEURAL_CANDIDATE_CLEARANCE] = 8,
			[GARDEN_NEURAL_CANDIDATE_OWN_NEAR] = -32,
			[GARDEN_NEURAL_CANDIDATE_FOREIGN_NEAR] = -48,
			[GARDEN_NEURAL_CANDIDATE_SHOOT_UP] = 16,
			[GARDEN_NEURAL_CANDIDATE_ROOT_DOWN] = 16,
		},
};

const struct picosystem_garden_neural_model *picosystem_garden_neural_reference_model(void)
{
	return &reference_model;
}

const struct picosystem_garden_agent_policy *picosystem_garden_agent_neural_reference_policy(void)
{
	static const struct picosystem_garden_agent_policy policy = {
		.decide = picosystem_garden_agent_neural_decide,
		.context = &reference_model,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS,
	};
	return &policy;
}
