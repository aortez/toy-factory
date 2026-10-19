/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_RESEARCH_SHADOW_H_
#define TOY_FACTORY_RESEARCH_SHADOW_H_

#include "garden_leaf_family.h"
#include "garden_leaf_replay_route.h"
#include <stdio.h>

/* Private host diagnostic, not a policy replacement. The route returns only
 * the original candidate's decision. One bounded allocation, no step allocation.
 * Context borrows ancestry for one step; no world/observation pointers escape.
 */
struct research_shadow;
struct research_shadow_context {
	struct research_shadow *shadow;
	const struct toy_factory_leaf_family_owners *owners;
};
int research_shadow_open(uint8_t model, uint8_t founder, uint16_t first_day, uint16_t end_day,
			 struct research_shadow **out);
void research_shadow_close(struct research_shadow *shadow);
int research_shadow_decide(const struct picosystem_garden_world *world,
			   const struct picosystem_garden_leaf_policy *candidate,
			   const struct picosystem_garden_leaf_observation *observation,
			   const struct picosystem_garden_agent_memory *memory,
			   struct picosystem_garden_leaf_decision *decision, const void *context);
int research_shadow_write(const struct research_shadow *shadow, FILE *stream, uint32_t tick);

#endif
