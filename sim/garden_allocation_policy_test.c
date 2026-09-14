/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_allocation_policy.h"
#include "garden_evaluation.h"

struct fixture {
	int16_t priority;
	int error;
};

static int proposal(const struct picosystem_garden_agent_observation *observation,
		    const struct picosystem_garden_agent_memory *memory,
		    struct picosystem_garden_agent_decision *decision, const void *opaque)
{
	const struct fixture *fixture = opaque;
	*decision = (struct picosystem_garden_agent_decision){
		.proposal = {.tip_index = observation->tip_index,
			     .priority = fixture->priority,
			     .action = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT},
		.next_memory = *memory};
	decision->next_memory.hidden[0] = (int8_t)fixture->priority;
	return fixture->error;
}

int main(void)
{
	struct picosystem_garden_world world;
	assert(toy_factory_garden_evaluation_reset(&world, &toy_factory_garden_rainfed_scenarios[0],
						   123U) == 0);
	struct picosystem_garden_agent_observation o;
	bool found = false;
	for (uint16_t i = 0U; i < world.node_count; ++i) {
		if (picosystem_garden_agent_observe_tip(&world, 0U, i, 1U, &o) == 0) {
			found = true;
			break;
		}
	}
	assert(found);
	struct fixture ref = {.priority = 11}, alt = {.priority = 22};
	const struct picosystem_garden_agent_policy reference = {
		.decide = proposal,
		.context = &ref,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS};
	const struct picosystem_garden_agent_policy candidate = {
		.decide = proposal,
		.context = &alt,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS};
	struct toy_factory_garden_allocation_context context;
	struct picosystem_garden_agent_policy policy;
	const uint32_t lineage = world.plants[0].lineage_id;
	assert(toy_factory_garden_allocation_init(&world, &reference, &candidate, lineage, 15U,
						  &context, &policy) == 0);
	const struct picosystem_garden_agent_memory memory = {.hidden = {7, -2}};
	struct picosystem_garden_agent_decision decision;
	for (uint32_t tick = 0U; tick <= 30U; ++tick) {
		world.logic_tick_count = tick;
		const struct picosystem_garden_world saved = world;
		assert(picosystem_garden_agent_decide(&policy, &o, &memory, &decision) == 0);
		assert(decision.proposal.priority == (tick < 15U ? 11 : 22));
		assert(decision.next_memory.hidden[0] == decision.proposal.priority);
		assert(memcmp(&world, &saved, sizeof(world)) == 0 && memory.hidden[0] == 7);
	}
	world.plants[0].lineage_id = lineage + 50U; /* Slot reuse/descendant is not selected. */
	assert(picosystem_garden_agent_decide(&policy, &o, &memory, &decision) == 0);
	assert(decision.proposal.priority == 11);
	world.plants[0].lineage_id = lineage;
	alt.error = -EIO;
	const struct picosystem_garden_agent_decision saved = decision;
	assert(policy.decide(&o, &memory, &decision, policy.context) == -EIO);
	assert(memcmp(&decision, &saved, sizeof(saved)) == 0);
	o.plant_index = world.plant_count;
	assert(policy.decide(&o, &memory, &decision, policy.context) == -EINVAL);
	assert(memcmp(&decision, &saved, sizeof(saved)) == 0);
	const struct toy_factory_garden_allocation_context saved_context = context;
	const struct picosystem_garden_agent_policy saved_policy = policy;
	for (unsigned int i = 0U; i < 8U; ++i) {
		assert(toy_factory_garden_allocation_init(i == 0U ? NULL : &world,
							  i == 1U   ? NULL
							  : i == 2U ? &policy
								    : &reference,
							  i == 3U   ? NULL
							  : i == 4U ? &policy
								    : &candidate,
							  i == 5U ? 0U : lineage,
							  i == 6U   ? 0U
							  : i == 7U ? 16U
								    : 15U,
							  &context, &policy) == -EINVAL);
		assert(memcmp(&context, &saved_context, sizeof(context)) == 0);
		assert(memcmp(&policy, &saved_policy, sizeof(policy)) == 0);
	}
	struct picosystem_garden_agent_policy invalid = candidate;
	invalid.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_PHASED;
	assert(toy_factory_garden_allocation_init(&world, &reference, &invalid, lineage, 15U,
						  &context, &policy) == -EINVAL);
	invalid = candidate;
	invalid.decide = NULL;
	assert(toy_factory_garden_allocation_init(&world, &reference, &invalid, lineage, 15U,
						  &context, &policy) == -EINVAL);
	assert(toy_factory_garden_allocation_init(&world, &saved_policy, &candidate, lineage, 15U,
						  &context, &policy) ==
	       -EINVAL); /* Nested routing rejected. */
	puts("Allocation routing boundaries, memory, ownership and failures passed");
	return 0;
}
