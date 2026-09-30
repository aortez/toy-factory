/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_LANDING_MUTATION_H_
#define TOY_FACTORY_GARDEN_LANDING_MUTATION_H_

#include "garden_landing_neural.h"
#include "garden_model_mutation.h"

/* Legacy mutations first, then extension byte weights (including masked ones).
 * No config/scale mutation. Counts 0..4096, at least one nonzero. Caller owns
 * disjoint model/RNG. On failure BOTH remain unchanged.
 */
int toy_factory_garden_landing_mutate(struct toy_factory_garden_landing_model *model,
				      struct toy_factory_garden_mutation_rng *rng,
				      uint32_t legacy_count, uint32_t landing_count);

#endif
