/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <string.h>

#include "garden_light.h"
#include "garden_policy_probe.h"

static int decide(const struct picosystem_garden_agent_observation *observation,
		  const struct picosystem_garden_agent_memory *memory,
		  struct picosystem_garden_agent_decision *decision, const void *context)
{
	const struct picosystem_garden_agent_policy *const base = context;
	const int err = picosystem_garden_agent_decide(base, observation, memory, decision);
	if (err != 0) {
		return err;
	}
	if ((observation->sun_phase >= PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE) &&
	    ((decision->proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND) ||
	     (decision->proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP))) {
		decision->proposal.action = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT;
		decision->proposal.candidate_count = 0U;
		memset(decision->proposal.candidate_order, PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE,
		       sizeof(decision->proposal.candidate_order));
	}
	return 0;
}

int toy_factory_garden_no_night_growth_init(const struct picosystem_garden_agent_policy *base,
					    struct picosystem_garden_agent_policy *policy)
{
	if ((base == NULL) || (policy == NULL) || (base == policy) || (base->decide == NULL) ||
	    (base->decide == decide)) {
		return -EINVAL;
	}
	*policy = (struct picosystem_garden_agent_policy){
		.decide = decide,
		.context = base,
		.arbitration = base->arbitration,
	};
	return 0;
}
