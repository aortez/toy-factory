/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_neural.h"

#include <errno.h>
#include <limits.h>

_Static_assert(sizeof(struct toy_factory_garden_landing_model) ==
		       TOY_FACTORY_GARDEN_LANDING_MODEL_SIZE,
	       "landing model budget");
/* Every int8 product has magnitude <= 16384. The longest accumulator is
 * 32 common + 8 memory + 9 landing inputs. Candidate fan-in is 16 + 9 + 8.
 * These conservative bounds apply to every intermediate sum, not just outputs.
 */
_Static_assert(INT64_C(1000000) + (PICOSYSTEM_GARDEN_NEURAL_HIDDEN_INPUT_COUNT +
				   TOY_FACTORY_GARDEN_LANDING_COMMON_COUNT) *
					  INT64_C(16384) <
		       INT32_MAX,
	       "common accumulator bound");
_Static_assert(INT64_C(1000000) + (PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT +
				   PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_FEATURE_COUNT +
				   TOY_FACTORY_GARDEN_LANDING_CANDIDATE_COUNT) *
					  INT64_C(16384) <
		       INT32_MAX,
	       "candidate accumulator bound");
_Static_assert(PICOSYSTEM_GARDEN_NEURAL_MAX_ABSOLUTE_BIAS == 1000000, "bias bound");
_Static_assert(PICOSYSTEM_GARDEN_NEURAL_MAX_SHIFT <= 30U, "positive shift divisor");

int toy_factory_garden_landing_model_validate(const struct toy_factory_garden_landing_model *model)
{
	if (model == NULL) {
		return -EINVAL;
	}
	const struct toy_factory_garden_landing_feature_config *const c = &model->config;
	if ((c->version != TOY_FACTORY_GARDEN_LANDING_FEATURE_VERSION) ||
	    (c->mode >= TOY_FACTORY_GARDEN_LANDING_INPUT_MODE_COUNT) ||
	    ((c->flags & (uint8_t)~TOY_FACTORY_GARDEN_LANDING_OMIT_DEAD_ONLY) != 0U) ||
	    (c->reserved != 0U)) {
		return -ERANGE;
	}
	return picosystem_garden_neural_model_validate(&model->legacy);
}

int toy_factory_garden_landing_model_import(
	const struct picosystem_garden_neural_model *legacy,
	const struct toy_factory_garden_landing_feature_config *config,
	struct toy_factory_garden_landing_model *model)
{
	if ((legacy == NULL) || (config == NULL) || (model == NULL)) {
		return -EINVAL;
	}
	const struct toy_factory_garden_landing_model result = {.legacy = *legacy,
								.config = *config};
	const int err = toy_factory_garden_landing_model_validate(&result);
	if (err != 0) {
		return err;
	}
	*model = result;
	return 0;
}

static int32_t dot(int32_t bias, const int8_t *weights, const int8_t *values, size_t count)
{
	for (size_t i = 0U; i < count; ++i) {
		bias += (int32_t)weights[i] * values[i];
	}
	return bias;
}

static int32_t scale(int32_t value, uint8_t shift)
{
	/* Match v1 C11 division, including negative truncation toward zero. */
	return value / (INT32_C(1) << shift);
}

static int32_t clamp(int32_t value, int32_t low, int32_t high)
{
	return (value < low) ? low : ((value > high) ? high : value);
}

static int32_t score(const struct toy_factory_garden_landing_model *model,
		     const struct toy_factory_garden_landing_features *features,
		     const int8_t *hidden, uint8_t candidate)
{
	const struct picosystem_garden_neural_model *const m = &model->legacy;
	int8_t layer[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT];
	for (uint8_t u = 0U; u < PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT; ++u) {
		int32_t sum = dot(m->candidate_hidden_bias[u], m->candidate_hidden_weights[u],
				  hidden, PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT);
		sum = dot(sum, m->candidate_feature_weights[u],
			  features->legacy.candidates[candidate],
			  PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_FEATURE_COUNT);
		sum = dot(sum, model->candidate_weights[u], features->landing.candidates[candidate],
			  TOY_FACTORY_GARDEN_LANDING_CANDIDATE_COUNT);
		layer[u] = (int8_t)clamp(scale(sum, m->candidate_hidden_shift), 0, INT8_MAX);
	}
	return scale(dot(m->candidate_output_bias, m->candidate_output_weights, layer,
			 PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT),
		     m->output_shift);
}

int toy_factory_garden_landing_neural_decide(
	const struct picosystem_garden_agent_observation *observation,
	const struct picosystem_garden_agent_memory *memory,
	const struct picosystem_garden_landing_packet *packet,
	const struct toy_factory_garden_landing_model *model,
	struct picosystem_garden_agent_decision *decision)
{
	if ((observation == NULL) || (memory == NULL) || (decision == NULL)) {
		return -EINVAL;
	}
	int err = toy_factory_garden_landing_model_validate(model);
	if (err != 0) {
		return err;
	}
	struct toy_factory_garden_landing_features features;
	err = toy_factory_garden_landing_features_encode(observation, packet, &model->config,
							 &features);
	if (err != 0) {
		return err;
	}
	const struct picosystem_garden_neural_model *const m = &model->legacy;
	int8_t hidden[PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT];
	for (uint8_t u = 0U; u < PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT; ++u) {
		int32_t sum = dot(m->hidden_bias[u], m->hidden_weights[u], features.legacy.common,
				  PICOSYSTEM_GARDEN_NEURAL_COMMON_FEATURE_COUNT);
		sum = dot(sum, &m->hidden_weights[u][PICOSYSTEM_GARDEN_NEURAL_COMMON_FEATURE_COUNT],
			  memory->hidden, PICOSYSTEM_GARDEN_AGENT_MEMORY_WIDTH);
		sum = dot(sum, model->common_weights[u], features.landing.common,
			  TOY_FACTORY_GARDEN_LANDING_COMMON_COUNT);
		hidden[u] = (int8_t)clamp(scale(sum, m->hidden_shift), 0, INT8_MAX);
	}
	struct picosystem_garden_agent_decision result = {.proposal.tip_index =
								  observation->tip_index};
	for (uint8_t i = 0U; i < PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES; ++i) {
		result.proposal.candidate_order[i] = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE;
	}
	int32_t best = INT32_MIN;
	for (uint8_t action = 0U; action < PICOSYSTEM_GARDEN_AGENT_ACTION_COUNT; ++action) {
		const int32_t value = scale(dot(m->action_bias[action], m->action_weights[action],
						hidden, PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT),
					    m->output_shift);
		if (value > best) {
			best = value;
			result.proposal.action = action;
		}
	}
	result.proposal.priority =
		(int16_t)clamp(scale(dot(m->priority_bias, m->priority_weights, hidden,
					 PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT),
				     m->output_shift),
			       INT16_MIN, INT16_MAX);
	for (uint8_t i = 0U; i < PICOSYSTEM_GARDEN_AGENT_MEMORY_WIDTH; ++i) {
		result.next_memory.hidden[i] =
			(int8_t)clamp(scale(dot(m->memory_bias[i], m->memory_weights[i], hidden,
						PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT),
					    m->output_shift),
				      INT8_MIN, INT8_MAX);
	}
	bool available = false;
	for (uint8_t i = 0U; i < observation->candidate_count; ++i) {
		available |= (observation->candidates[i].flags &
			      PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE) != 0U;
	}
	if ((observation->depth >= observation->maximum_depth) || !available) {
		result.proposal.action = PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP;
		result.proposal.priority = (observation->depth >= observation->maximum_depth)
						   ? INT16_MAX
						   : INT16_MAX - 1;
	} else if (result.proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND) {
		int32_t scores[PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES];
		const uint8_t rotation =
			(uint8_t)(observation->decision_nonce % observation->candidate_count);
		result.proposal.candidate_count = observation->candidate_count;
		for (uint8_t i = 0U; i < observation->candidate_count; ++i) {
			const uint8_t index =
				(uint8_t)((rotation + i) % observation->candidate_count);
			result.proposal.candidate_order[i] = index;
			scores[i] = score(model, &features, hidden, index);
		}
		/* Match v1 stable ordering for ties, including unavailable candidates. */
		for (uint8_t i = 1U; i < observation->candidate_count; ++i) {
			const uint8_t index = result.proposal.candidate_order[i];
			const int32_t value = scores[i];
			uint8_t pos = i;
			while ((pos > 0U) && (scores[pos - 1U] < value)) {
				result.proposal.candidate_order[pos] =
					result.proposal.candidate_order[pos - 1U];
				scores[pos] = scores[pos - 1U];
				--pos;
			}
			result.proposal.candidate_order[pos] = index;
			scores[pos] = value;
		}
	}
	*decision = result;
	return 0;
}
