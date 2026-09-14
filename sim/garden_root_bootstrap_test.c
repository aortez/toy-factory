/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_evaluation.h"
#include "garden_root_bootstrap.h"

struct fixture {
	int error;
	uint8_t action;
	bool invalid_order;
};

static int base_decide(const struct picosystem_garden_agent_observation *o,
		       const struct picosystem_garden_agent_memory *memory,
		       struct picosystem_garden_agent_decision *decision, const void *context)
{
	const struct fixture *fixture = context;
	*decision = (struct picosystem_garden_agent_decision){
		.next_memory = *memory,
		.proposal = {.tip_index = o->tip_index,
			     .priority = 17,
			     .action = fixture->action,
			     .candidate_count = fixture->action == 1U ? o->candidate_count : 0U,
			     .candidate_order = {2U, 0U, 1U}},
	};
	decision->next_memory.hidden[0] = 31;
	if (fixture->invalid_order) {
		decision->proposal.candidate_order[1] = 2U;
	}
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
		if ((world.nodes[i].kind == PICOSYSTEM_GARDEN_NODE_ROOT) &&
		    (picosystem_garden_agent_observe_tip(&world, 0U, i, 42U, &o) == 0)) {
			found = true;
			break;
		}
	}
	assert(found);
	world.logic_tick_count = 915U;
	world.plants[0].generation = 1U;
	o.age_ecology_ticks = 1U;
	o.root_node_count = 2U;
	o.stored_water = 24U;
	o.stored_energy = 64U;
	o.tip_moisture = 2U;
	o.species_id = PICOSYSTEM_GARDEN_SPECIES_SHRUB;
	o.vigor = 0;
	for (uint8_t i = 0U; i < o.candidate_count; ++i) {
		o.candidates[i].flags = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS |
					PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE;
		o.candidates[i].y =
			PICOSYSTEM_GARDEN_SOIL_TOP_PIXELS + PICOSYSTEM_GARDEN_CELL_PIXELS;
		o.candidates[i].moisture = i == 1U ? 20U : 10U;
	}
	struct fixture fixture = {.action = 1U};
	struct picosystem_garden_agent_policy base = {
		.decide = base_decide,
		.context = &fixture,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS};
	struct picosystem_garden_agent_policy policy;
	struct toy_factory_garden_root_bootstrap_context context;
	assert(toy_factory_garden_root_bootstrap_init(&base, &world, 900U, &context, &policy) == 0);
	const struct picosystem_garden_agent_memory memory = {.hidden = {7, -2}};
	struct picosystem_garden_agent_decision result;
	assert(picosystem_garden_agent_decide(&policy, &o, &memory, &result) == 0);
	assert(result.proposal.priority == INT16_MAX && result.proposal.candidate_order[0] == 1U &&
	       result.proposal.candidate_order[1] == 2U &&
	       result.proposal.candidate_order[2] == 0U && result.next_memory.hidden[0] == 31 &&
	       memory.hidden[0] == 7);
	const struct picosystem_garden_agent_observation saved = o;
	const struct picosystem_garden_world saved_world = world;
	/* Exactly affordable prices qualify. One less does not. */
	for (uint8_t species = 0U; species < PICOSYSTEM_GARDEN_SPECIES_COUNT; ++species) {
		for (int8_t vigor = 0; vigor <= 1; ++vigor) {
			o = saved;
			o.species_id = species;
			o.vigor = vigor;
			o.stored_energy = (uint16_t)(9U - species - (vigor > 0 ? 1U : 0U));
			o.stored_water =
				species == PICOSYSTEM_GARDEN_SPECIES_GROUND_COVER ? 4U : 5U;
			assert(picosystem_garden_agent_decide(&policy, &o, &memory, &result) == 0 &&
			       result.proposal.priority == INT16_MAX);
			--o.stored_water;
			assert(picosystem_garden_agent_decide(&policy, &o, &memory, &result) == 0 &&
			       result.proposal.priority == 17);
			++o.stored_water;
			--o.stored_energy;
			assert(picosystem_garden_agent_decide(&policy, &o, &memory, &result) == 0 &&
			       result.proposal.priority == 17);
		}
	}
	/* No output changes for disabled, old, adult, expanded, dry or blocked roots. */
	for (uint8_t test = 0U; test < 11U; ++test) {
		o = saved;
		world = saved_world;
		context.after_tick = 900U;
		if (test == 0U) {
			context.after_tick = 0U;
		}
		if (test == 1U) {
			world.logic_tick_count = 900U;
		}
		if (test == 2U) {
			o.age_ecology_ticks = 2U;
		}
		if (test == 3U) {
			world.plants[0].generation = 0U;
		}
		if (test == 4U) {
			o.root_node_count = 3U;
		}
		if (test == 5U) {
			o.age_ecology_ticks = 257U;
		}
		if (test == 6U) {
			o.depth = 2U;
		}
		if (test == 7U) {
			o.tip_moisture = 20U;
		}
		for (uint8_t i = 0U; i < o.candidate_count; ++i) {
			if (test == 8U) {
				o.candidates[i].moisture = 4U;
			}
			if (test == 9U) {
				o.candidates[i].flags = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS;
			}
			if (test == 10U) {
				o.candidates[i].y = o.tip_y;
			}
		}
		struct picosystem_garden_agent_decision expected;
		assert(picosystem_garden_agent_decide(&base, &o, &memory, &expected) == 0);
		assert(picosystem_garden_agent_decide(&policy, &o, &memory, &result) == 0);
		assert(memcmp(&result, &expected, sizeof(result)) == 0);
	}
	o = saved;
	world = saved_world;
	context.after_tick = 900U;
	o.candidates[1].moisture = 10U;
	assert(picosystem_garden_agent_decide(&policy, &o, &memory, &result) == 0 &&
	       result.proposal.candidate_order[0] == 2U);
	/* The wrapper cannot override a night/energy WAIT or FINISH. */
	for (uint8_t action = 0U; action <= 2U; action = (uint8_t)(action + 2U)) {
		fixture.action = action;
		assert(picosystem_garden_agent_decide(&policy, &o, &memory, &result) == 0 &&
		       result.proposal.priority == 17 && result.proposal.action == action);
	}
	const struct picosystem_garden_agent_decision before = result;
	fixture.error = -EIO;
	/* The callback preserves its output on error; the public dispatcher instead
	 * intentionally initializes an empty decision. Keep that existing contract.
	 */
	assert(policy.decide(&o, &memory, &result, policy.context) == -EIO &&
	       memcmp(&result, &before, sizeof(result)) == 0);
	struct picosystem_garden_agent_decision cleared;
	assert(picosystem_garden_agent_decide(&base, &o, &memory, &cleared) == -EIO);
	assert(picosystem_garden_agent_decide(&policy, &o, &memory, &result) == -EIO &&
	       memcmp(&result, &cleared, sizeof(result)) == 0);
	result = before;
	fixture.error = 0;
	fixture.action = 1U;
	fixture.invalid_order = true;
	assert(policy.decide(&o, &memory, &result, policy.context) == -EINVAL &&
	       memcmp(&result, &before, sizeof(result)) == 0);
	const struct toy_factory_garden_root_bootstrap_context saved_context = context;
	const struct picosystem_garden_agent_policy saved_policy = policy;
	assert(toy_factory_garden_root_bootstrap_init(NULL, &world, 900U, &context, &policy) ==
	       -EINVAL);
	assert(toy_factory_garden_root_bootstrap_init(&base, NULL, 900U, &context, &policy) ==
	       -EINVAL);
	assert(toy_factory_garden_root_bootstrap_init(&base, &world, 901U, &context, &policy) ==
	       -EINVAL);
	assert(toy_factory_garden_root_bootstrap_init(&base, &world, 900U, NULL, &policy) ==
	       -EINVAL);
	assert(toy_factory_garden_root_bootstrap_init(&base, &world, 900U, &context, NULL) ==
	       -EINVAL);
	assert(toy_factory_garden_root_bootstrap_init(&base, &world, 900U, &context, &base) ==
	       -EINVAL);
	assert(toy_factory_garden_root_bootstrap_init(&policy, &world, 900U, &context, &base) ==
	       -EINVAL);
	assert(memcmp(&context, &saved_context, sizeof(context)) == 0 &&
	       memcmp(&policy, &saved_policy, sizeof(policy)) == 0);
	assert(memcmp(&world, &saved_world, sizeof(world)) == 0);
	puts("Wet-root bootstrap boundaries, base decisions and state preservation passed");
	return 0;
}
