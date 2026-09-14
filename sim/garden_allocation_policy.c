/* SPDX-License-Identifier: Apache-2.0 */
#include <errno.h>

#include "garden_allocation_policy.h"

static int decide(const struct picosystem_garden_agent_observation *observation,
		  const struct picosystem_garden_agent_memory *memory,
		  struct picosystem_garden_agent_decision *decision, const void *opaque)
{
	const struct toy_factory_garden_allocation_context *context = opaque;
	if (observation->plant_index >= context->world->plant_count) {
		return -EINVAL;
	}
	const bool selected =
		context->world->logic_tick_count >= context->start_tick &&
		context->world->plants[observation->plant_index].lineage_id == context->lineage;
	struct picosystem_garden_agent_decision result;
	const int err = picosystem_garden_agent_decide(
		selected ? context->candidate : context->reference, observation, memory, &result);
	if (err == 0) {
		*decision = result;
	}
	return err;
}

int toy_factory_garden_allocation_init(const struct picosystem_garden_world *world,
				       const struct picosystem_garden_agent_policy *reference,
				       const struct picosystem_garden_agent_policy *candidate,
				       uint32_t lineage, uint32_t start_tick,
				       struct toy_factory_garden_allocation_context *context,
				       struct picosystem_garden_agent_policy *policy)
{
	if ((world == NULL) || (reference == NULL) || (candidate == NULL) || (context == NULL) ||
	    (policy == NULL) || (reference == policy) || (candidate == policy) ||
	    (reference->decide == NULL) || (candidate->decide == NULL) ||
	    (reference->decide == decide) || (candidate->decide == decide) ||
	    (reference->arbitration != PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS) ||
	    (candidate->arbitration != PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS) ||
	    (lineage == 0U) || (start_tick == 0U) ||
	    ((start_tick % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) != 0U)) {
		return -EINVAL;
	}
	*context = (struct toy_factory_garden_allocation_context){.world = world,
								  .reference = reference,
								  .candidate = candidate,
								  .lineage = lineage,
								  .start_tick = start_tick};
	*policy = *reference;
	policy->decide = decide;
	policy->context = context;
	return 0;
}
