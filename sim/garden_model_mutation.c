/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_model_mutation.h"

#include <errno.h>
#include <limits.h>
#include <stddef.h>
#include "portable_util.h"

struct garden_mutation_i8_span {
	int8_t *values;
	size_t count;
};

struct garden_mutation_i32_span {
	int32_t *values;
	size_t count;
};

static uint32_t rng_next(struct toy_factory_garden_mutation_rng *rng)
{
	uint32_t value = rng->state;
	value ^= value << 13U;
	value ^= value >> 17U;
	value ^= value << 5U;
	rng->state = (value == 0U) ? UINT32_C(0x74726169) : value;
	return rng->state;
}

static int8_t clamp_i8(int32_t value)
{
	if (value < INT8_MIN) {
		return INT8_MIN;
	}
	return (value > INT8_MAX) ? INT8_MAX : (int8_t)value;
}

static int32_t clamp_bias(int32_t value)
{
	if (value < -PICOSYSTEM_GARDEN_NEURAL_MAX_ABSOLUTE_BIAS) {
		return -PICOSYSTEM_GARDEN_NEURAL_MAX_ABSOLUTE_BIAS;
	}
	return (value > PICOSYSTEM_GARDEN_NEURAL_MAX_ABSOLUTE_BIAS)
		       ? PICOSYSTEM_GARDEN_NEURAL_MAX_ABSOLUTE_BIAS
		       : value;
}

static void mutate_weight(struct picosystem_garden_neural_model *model,
			  struct toy_factory_garden_mutation_rng *rng, size_t flat_index)
{
	struct garden_mutation_i8_span spans[] = {
		{&model->hidden_weights[0][0], sizeof(model->hidden_weights)},
		{&model->action_weights[0][0], sizeof(model->action_weights)},
		{model->priority_weights, sizeof(model->priority_weights)},
		{&model->memory_weights[0][0], sizeof(model->memory_weights)},
		{&model->candidate_hidden_weights[0][0], sizeof(model->candidate_hidden_weights)},
		{&model->candidate_feature_weights[0][0], sizeof(model->candidate_feature_weights)},
		{model->candidate_output_weights, sizeof(model->candidate_output_weights)},
	};
	for (size_t index = 0U; index < TOY_FACTORY_ARRAY_SIZE(spans); ++index) {
		if (flat_index < spans[index].count) {
			int32_t delta = (int32_t)(rng_next(rng) % 17U) - 8;
			if (delta == 0) {
				delta = ((rng_next(rng) & 1U) == 0U) ? -1 : 1;
			}
			spans[index].values[flat_index] =
				clamp_i8((int32_t)spans[index].values[flat_index] + delta);
			return;
		}
		flat_index -= spans[index].count;
	}
}

static void mutate_bias(struct picosystem_garden_neural_model *model,
			struct toy_factory_garden_mutation_rng *rng, size_t flat_index)
{
	struct garden_mutation_i32_span spans[] = {
		{model->hidden_bias, TOY_FACTORY_ARRAY_SIZE(model->hidden_bias)},
		{model->action_bias, TOY_FACTORY_ARRAY_SIZE(model->action_bias)},
		{&model->priority_bias, 1U},
		{model->memory_bias, TOY_FACTORY_ARRAY_SIZE(model->memory_bias)},
		{model->candidate_hidden_bias,
		 TOY_FACTORY_ARRAY_SIZE(model->candidate_hidden_bias)},
		{&model->candidate_output_bias, 1U},
	};
	for (size_t index = 0U; index < TOY_FACTORY_ARRAY_SIZE(spans); ++index) {
		if (flat_index < spans[index].count) {
			int32_t delta = (int32_t)(rng_next(rng) % 513U) - 256;
			if (delta == 0) {
				delta = ((rng_next(rng) & 1U) == 0U) ? -1 : 1;
			}
			spans[index].values[flat_index] =
				clamp_bias(spans[index].values[flat_index] + delta);
			return;
		}
		flat_index -= spans[index].count;
	}
}

int toy_factory_garden_model_mutate(struct picosystem_garden_neural_model *model,
				    struct toy_factory_garden_mutation_rng *rng,
				    uint32_t mutation_count)
{
	if ((model == NULL) || (rng == NULL) || (mutation_count == 0U) ||
	    (mutation_count > 4096U) || (picosystem_garden_neural_model_validate(model) != 0)) {
		return -EINVAL;
	}

	const size_t weight_count =
		sizeof(model->hidden_weights) + sizeof(model->action_weights) +
		sizeof(model->priority_weights) + sizeof(model->memory_weights) +
		sizeof(model->candidate_hidden_weights) + sizeof(model->candidate_feature_weights) +
		sizeof(model->candidate_output_weights);
	const size_t bias_count = TOY_FACTORY_ARRAY_SIZE(model->hidden_bias) +
				  TOY_FACTORY_ARRAY_SIZE(model->action_bias) + 1U +
				  TOY_FACTORY_ARRAY_SIZE(model->memory_bias) +
				  TOY_FACTORY_ARRAY_SIZE(model->candidate_hidden_bias) + 1U;
	for (uint32_t index = 0U; index < mutation_count; ++index) {
		const size_t parameter =
			(size_t)(rng_next(rng) % (uint32_t)(weight_count + bias_count));
		if (parameter < weight_count) {
			mutate_weight(model, rng, parameter);
		} else {
			mutate_bias(model, rng, parameter - weight_count);
		}
	}
	return 0;
}
