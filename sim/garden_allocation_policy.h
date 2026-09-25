/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_ALLOCATION_POLICY_H_
#define TOY_FACTORY_GARDEN_ALLOCATION_POLICY_H_

#include "garden_agent.h"

#if defined(__ZEPHYR__)
#error "Allocation routing is a host-only diagnostic"
#endif

/* Immutable caller-owned selector. Routing adds no candidate inputs: the
 * selected callback receives its own context, ordinary observation and memory.
 */
struct toy_factory_garden_allocation_context {
	const struct picosystem_garden_world *world;
	const struct picosystem_garden_agent_policy *reference;
	const struct picosystem_garden_agent_policy *candidate;
	uint32_t lineage;
	uint32_t start_tick;
};

/* Both policies/context/world must outlive the result. Errors preserve outputs;
 * leaf maintenance belongs to reference, growth arbitration must be ALL_TIPS.
 */
int toy_factory_garden_allocation_init(const struct picosystem_garden_world *world,
				       const struct picosystem_garden_agent_policy *reference,
				       const struct picosystem_garden_agent_policy *candidate,
				       uint32_t lineage, uint32_t start_tick,
				       struct toy_factory_garden_allocation_context *context,
				       struct picosystem_garden_agent_policy *policy);

#endif
