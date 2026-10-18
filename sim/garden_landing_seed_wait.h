/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_LANDING_SEED_WAIT_H_
#define TOY_FACTORY_GARDEN_LANDING_SEED_WAIT_H_

#include "garden_world.h"

#include <stddef.h>

struct toy_factory_garden_seed_wait_entry {
	uint32_t lineage;
	uint32_t since;
};

/* Host-only value state. A never-buyer waits from birth; only a paid purchase
 * resets its clock. Entries follow stored bodies, including retained corpses.
 */
struct toy_factory_garden_seed_wait {
	uint32_t after;
	uint8_t count;
	struct toy_factory_garden_seed_wait_entry entries[PICOSYSTEM_GARDEN_MAX_PLANTS];
};

int toy_factory_garden_seed_wait_init(const struct picosystem_garden_world *world, uint32_t after,
				      struct toy_factory_garden_seed_wait *state);
int toy_factory_garden_seed_wait_validate(const struct toy_factory_garden_seed_wait *state,
					  const struct picosystem_garden_world *world);
/* Called during reproduction, after births/growth. Unknown IDs are newborns
 * from this step; immutable prior-step context has not been published yet.
 */
int toy_factory_garden_seed_wait_order(const struct picosystem_garden_world *world, uint8_t *order,
				       size_t capacity, const void *context);
/* Internal commit helper: validated state/world and disjoint output required.
 * Call only after a successful ecology step; no fallible work follows commit.
 */
void toy_factory_garden_seed_wait_advance(const struct toy_factory_garden_seed_wait *state,
					  const struct picosystem_garden_world *world,
					  struct toy_factory_garden_seed_wait *next);
uint32_t toy_factory_garden_seed_wait_hash(const struct toy_factory_garden_seed_wait *state,
					   uint32_t base);

#endif
