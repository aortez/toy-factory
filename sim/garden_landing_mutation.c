/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_mutation.h"

#include <errno.h>
#include <limits.h>
#include <stddef.h>

static uint32_t next(struct toy_factory_garden_mutation_rng *rng)
{
	uint32_t value = rng->state;
	value ^= value << 13U;
	value ^= value >> 17U;
	value ^= value << 5U;
	rng->state = (value == 0U) ? UINT32_C(0x74726169) : value;
	return rng->state;
}

int toy_factory_garden_landing_mutate(struct toy_factory_garden_landing_model *model,
				      struct toy_factory_garden_mutation_rng *rng,
				      uint32_t legacy_count, uint32_t landing_count)
{
	if ((rng == NULL) || (legacy_count > 4096U) || (landing_count > 4096U) ||
	    ((legacy_count == 0U) && (landing_count == 0U)) ||
	    (toy_factory_garden_landing_model_validate(model) != 0)) {
		return -EINVAL;
	}
	struct toy_factory_garden_landing_model result = *model;
	struct toy_factory_garden_mutation_rng state = *rng;
	if (legacy_count != 0U) {
		const int err =
			toy_factory_garden_model_mutate(&result.legacy, &state, legacy_count);
		if (err != 0) {
			return err;
		}
	}
	const uint32_t common_count = sizeof(result.common_weights);
	const uint32_t total = common_count + sizeof(result.candidate_weights);
	for (uint32_t i = 0U; i < landing_count; ++i) {
		uint32_t index = next(&state) % total;
		int8_t *weight;
		if (index < common_count) {
			weight = &result.common_weights[index /
							TOY_FACTORY_GARDEN_LANDING_COMMON_COUNT]
						       [index %
							TOY_FACTORY_GARDEN_LANDING_COMMON_COUNT];
		} else {
			index -= common_count;
			weight = &result.candidate_weights
					  [index / TOY_FACTORY_GARDEN_LANDING_CANDIDATE_COUNT]
					  [index % TOY_FACTORY_GARDEN_LANDING_CANDIDATE_COUNT];
		}
		int32_t delta = (int32_t)(next(&state) % 17U) - 8;
		if (delta == 0) {
			delta = ((next(&state) & 1U) == 0U) ? -1 : 1;
		}
		const int32_t value = (int32_t)*weight + delta;
		*weight = value < INT8_MIN ? INT8_MIN : value > INT8_MAX ? INT8_MAX : (int8_t)value;
	}
	*model = result;
	*rng = state;
	return 0;
}
