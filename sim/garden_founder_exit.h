/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_FOUNDER_EXIT_H_
#define TOY_FACTORY_GARDEN_FOUNDER_EXIT_H_

#include "garden_world.h"

#if !defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE) || defined(__ZEPHYR__)
#error "Founder exit is a host-only maintenance diagnostic"
#endif

#define TOY_FACTORY_GARDEN_FOUNDER_EXIT_RULE "founder-exit-v1"

struct toy_factory_garden_founder_exit {
	uint32_t tick;
	uint32_t before_hash;
	uint32_t after_hash;
	uint32_t killed_ids[PICOSYSTEM_GARDEN_MAX_PLANTS];
	uint16_t energy;
	uint16_t water;
	uint16_t nodes;
	uint8_t count;
};

/* Kill living parent-zero plants using ordinary death, without immediate reclaim.
 * Caller-owned host world/result must not alias. Both unchanged on failure;
 * a valid world with no living founders succeeds unchanged. Gardener must be off
 * and the caller must apply this after the ordinary step/patch at this tick.
 */
int toy_factory_garden_founder_exit_apply(struct picosystem_garden_world *world,
					  struct toy_factory_garden_founder_exit *result);
/* One JSON object, without a separator or newline. */
int toy_factory_garden_founder_exit_print(const struct toy_factory_garden_founder_exit *result);

#endif
