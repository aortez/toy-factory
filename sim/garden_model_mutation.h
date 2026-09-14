/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_MODEL_MUTATION_H_
#define TOY_FACTORY_GARDEN_MODEL_MUTATION_H_

#include "garden_agent_neural.h"

struct toy_factory_garden_mutation_rng {
	uint32_t state;
};

/* Exact legacy trainer draw order and clipping. Caller owns both objects.
 * 1..4096 mutations; invalid arguments leave model and RNG unchanged.
 */
int toy_factory_garden_model_mutate(struct picosystem_garden_neural_model *model,
				    struct toy_factory_garden_mutation_rng *rng,
				    uint32_t mutation_count);

#endif
