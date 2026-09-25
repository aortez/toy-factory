/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_ROOT_BOOTSTRAP_H_
#define TOY_FACTORY_GARDEN_ROOT_BOOTSTRAP_H_

#include "garden_agent.h"

#define TOY_FACTORY_GARDEN_ROOT_BOOTSTRAP_RULE "wet-root-bootstrap-v1"

/* Caller-owned, immutable policy context; world access selects the experiment
 * cohort only. The root choice uses the existing local observation contract.
 */
struct toy_factory_garden_root_bootstrap_context {
	const struct picosystem_garden_agent_policy *base;
	const struct picosystem_garden_world *world;
	uint32_t after_tick;
};

/* Zero after_tick disables the probe. Errors preserve both output objects. */
int toy_factory_garden_root_bootstrap_init(
	const struct picosystem_garden_agent_policy *base,
	const struct picosystem_garden_world *world, uint32_t after_tick,
	struct toy_factory_garden_root_bootstrap_context *context,
	struct picosystem_garden_agent_policy *policy);

#endif
