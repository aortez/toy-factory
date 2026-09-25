/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_FOCAL_POLICY_H_
#define TOY_FACTORY_GARDEN_FOCAL_POLICY_H_

#include "garden_agent.h"

#define TOY_FACTORY_GARDEN_FOCAL_POLICY_RULE "founder-policy-swap-v1"

/* Caller-owned lifetime. World access only routes policy; it never supplies
 * extra neural observations. Descendants retain the background controller.
 */
struct toy_factory_garden_focal_context {
	const struct picosystem_garden_world *world;
	const struct picosystem_garden_agent_policy *background;
	const struct picosystem_garden_agent_policy *focal;
	uint32_t founder_id;
};

/* Initialize at reset, for an existing living founder. Identical arbitration
 * and leaf policies are required. On error, both output objects are unchanged.
 */
int toy_factory_garden_focal_policy_init(const struct picosystem_garden_world *world,
					 const struct picosystem_garden_agent_policy *background,
					 const struct picosystem_garden_agent_policy *focal,
					 uint32_t founder_id,
					 struct toy_factory_garden_focal_context *context,
					 struct picosystem_garden_agent_policy *policy);

/* A stable lineage, not its current compacted slot, determines routing.
 * NULL indicates an invalid context/index; no world/policy state is changed.
 */
const struct picosystem_garden_agent_policy *
toy_factory_garden_focal_policy_select(const struct toy_factory_garden_focal_context *context,
				       uint8_t plant_index);

#endif
