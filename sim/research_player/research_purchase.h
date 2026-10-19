/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_RESEARCH_PURCHASE_H_
#define TOY_FACTORY_RESEARCH_PURCHASE_H_

#include "garden_landing_growth.h"

#define RESEARCH_PURCHASE_BEGIN (30U * 3840U)
#define RESEARCH_PURCHASE_END   (35U * 3840U)
#define RESEARCH_PURCHASE_LIMIT 256U

/* Exclusive session owner; one bounded allocation, none in callbacks. The
 * adapter borrows the live placement context for one step, never stores it.
 * Discard diagnostics on any step failure; the session latches that failure.
 */
struct research_purchase;
struct research_fallback_route;
struct research_purchase_context {
	const struct toy_factory_garden_placement_context *base;
	const struct toy_factory_garden_growth_observer *observer;
	const struct research_fallback_route *fallback;
};
int research_purchase_open(struct research_purchase **out);
void research_purchase_close(struct research_purchase *trace);
int research_purchase_write(const struct research_purchase *trace, uint32_t tick, FILE *stream);
/* Marker callback identifies the private context; unrelated growth observers
 * pass through without casting their context or recording purchases.
 */
int research_purchase_growth(const struct picosystem_garden_world *world,
			     const struct picosystem_garden_agent_observation *observation,
			     const struct picosystem_garden_agent_decision *raw,
			     const struct picosystem_garden_agent_decision *applied, void *context);
int research_purchase_decide(const struct picosystem_garden_seed_placement *observation,
			     uint8_t *choice, const void *context);

#endif
