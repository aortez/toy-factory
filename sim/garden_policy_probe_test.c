/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_evaluation.h"
#include "garden_policy_probe.h"

struct test_context {
	uint8_t action;
	int result;
};

static unsigned int calls;

static int test_decide(const struct picosystem_garden_agent_observation *observation,
		       const struct picosystem_garden_agent_memory *memory,
		       struct picosystem_garden_agent_decision *decision, const void *context)
{
	const struct test_context *const settings = context;
	++calls;
	decision->proposal.tip_index = observation->tip_index;
	decision->proposal.priority = -123;
	decision->proposal.action = settings->action;
	decision->proposal.candidate_count = 1U;
	decision->proposal.candidate_order[0] = 0U;
	decision->next_memory = *memory;
	decision->next_memory.hidden[0] = 17;
	return settings->result;
}

int main(void)
{
	struct picosystem_garden_world world;
	assert(toy_factory_garden_evaluation_reset(&world, &toy_factory_garden_rainfed_scenarios[0],
						   123U) == 0);
	struct picosystem_garden_agent_observation observation;
	bool found = false;
	for (uint16_t index = 0U; index < world.node_count; ++index) {
		if (picosystem_garden_agent_observe_tip(&world, 0U, index, 42U, &observation) ==
		    0) {
			found = true;
			break;
		}
	}
	assert(found);
	const struct picosystem_garden_agent_memory memory = {.hidden = {3, -7, 9}};
	struct test_context settings = {0};
	struct picosystem_garden_agent_policy base = {
		.decide = test_decide,
		.context = &settings,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS,
	};
	struct picosystem_garden_agent_policy probe;
	assert(toy_factory_garden_no_night_growth_init(&base, &probe) == 0);
	assert(probe.arbitration == base.arbitration);
	for (uint16_t phase = 0U; phase <= UINT8_MAX; ++phase) {
		observation.sun_phase = (uint8_t)phase;
		const struct picosystem_garden_agent_observation before = observation;
		for (uint8_t action = 0U; action <= PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP;
		     ++action) {
			settings.action = action;
			struct picosystem_garden_agent_decision actual;
			struct picosystem_garden_agent_decision expected;
			calls = 0U;
			assert(picosystem_garden_agent_decide(&probe, &observation, &memory,
							      &actual) == 0);
			assert(calls == 1U);
			assert(picosystem_garden_agent_decide(&base, &observation, &memory,
							      &expected) == 0);
			if ((phase >= 128U) && (action != PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT)) {
				expected.proposal.action = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT;
				expected.proposal.candidate_count = 0U;
				memset(expected.proposal.candidate_order,
				       PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE,
				       sizeof(expected.proposal.candidate_order));
			}
			assert(memcmp(&actual, &expected, sizeof(actual)) == 0);
			assert(memcmp(&observation, &before, sizeof(observation)) == 0);
			assert(memory.hidden[0] == 3);
		}
	}
	struct picosystem_garden_agent_decision decision;
	settings.result = -EIO;
	assert(picosystem_garden_agent_decide(&probe, &observation, &memory, &decision) == -EIO);
	assert(decision.proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT);
	assert(decision.next_memory.hidden[0] == 0);
	settings.result = 1;
	assert(picosystem_garden_agent_decide(&probe, &observation, &memory, &decision) == -EINVAL);
	calls = 0U;
	observation.version = 0U;
	assert(picosystem_garden_agent_decide(&probe, &observation, &memory, &decision) == -ERANGE);
	assert(calls == 0U);
	const struct picosystem_garden_agent_policy before = probe;
	assert(toy_factory_garden_no_night_growth_init(NULL, &probe) == -EINVAL);
	assert(toy_factory_garden_no_night_growth_init(&base, NULL) == -EINVAL);
	assert(toy_factory_garden_no_night_growth_init(&probe, &probe) == -EINVAL);
	assert(toy_factory_garden_no_night_growth_init(&probe, &base) == -EINVAL);
	base.decide = NULL;
	assert(toy_factory_garden_no_night_growth_init(&base, &probe) == -EINVAL);
	assert(memcmp(&probe, &before, sizeof(probe)) == 0);
	puts("PASS: night-growth probe preserves the policy contract across all sun phases");
	return 0;
}
