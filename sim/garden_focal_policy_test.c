/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_evaluation.h"
#include "garden_focal_policy.h"
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
#include "garden_leaf_policies.h"
#endif

struct fixture {
	int error;
	int16_t priority;
};

static int base_decide(const struct picosystem_garden_agent_observation *observation,
		       const struct picosystem_garden_agent_memory *memory,
		       struct picosystem_garden_agent_decision *decision, const void *context)
{
	const struct fixture *const fixture = context;
	decision->next_memory = *memory;
	decision->next_memory.hidden[0] = (int8_t)fixture->priority;
	decision->proposal.tip_index = observation->tip_index;
	decision->proposal.priority = fixture->priority;
	return fixture->error;
}

int main(void)
{
	struct picosystem_garden_world world;
	assert(toy_factory_garden_evaluation_reset(&world, &toy_factory_garden_rainfed_scenarios[0],
						   123U) == 0);
	assert(world.plant_count >= 2U);
	const uint32_t founder_id = world.plants[1].lineage_id;
	struct picosystem_garden_agent_observation observation;
	bool found = false;
	for (uint16_t i = 0U; i < world.node_count; ++i) {
		if (picosystem_garden_agent_observe_tip(&world, 1U, i, 42U, &observation) == 0) {
			found = true;
			break;
		}
	}
	assert(found);
	struct fixture fixtures[2] = {{.priority = 17}, {.priority = 29}};
	struct picosystem_garden_agent_policy background = {
		.decide = base_decide,
		.context = &fixtures[0],
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS};
	struct picosystem_garden_agent_policy focal = background;
	focal.context = &fixtures[1];
	struct picosystem_garden_agent_policy routed;
	struct toy_factory_garden_focal_context context;
	assert(toy_factory_garden_focal_policy_init(&world, &background, &focal, founder_id,
						    &context, &routed) == 0);
	const struct picosystem_garden_world saved_world = world;
	const struct picosystem_garden_agent_observation saved_observation = observation;
	const struct picosystem_garden_agent_memory memory = {.hidden = {7, -2}};
	const struct picosystem_garden_agent_memory saved_memory = memory;
	struct picosystem_garden_agent_decision result, expected;
	for (uint8_t i = 0U; i < world.plant_count; ++i) {
		observation.plant_index = i;
		const struct picosystem_garden_agent_policy *const selected =
			i == 1U ? &focal : &background;
		assert(toy_factory_garden_focal_policy_select(&context, i) == selected);
		assert(picosystem_garden_agent_decide(selected, &observation, &memory, &expected) ==
		       0);
		assert(picosystem_garden_agent_decide(&routed, &observation, &memory, &result) ==
		       0);
		assert(memcmp(&result, &expected, sizeof(result)) == 0);
	}
	observation = saved_observation;
	assert(memcmp(&world, &saved_world, sizeof(world)) == 0);
	assert(memcmp(&memory, &saved_memory, sizeof(memory)) == 0);
	assert(picosystem_garden_agent_decide(&routed, &observation, &memory, &result) == 0);
	assert(memcmp(&observation, &saved_observation, sizeof(observation)) == 0);
	/* Compaction moves the founder; ancestry alone must not route descendants. */
	world.plants[0] = world.plants[1];
	world.plants[1].lineage_id = 100U;
	world.plants[1].parent_lineage_id = founder_id;
	world.plants[1].generation = 1U;
	assert(toy_factory_garden_focal_policy_select(&context, 0U) == &focal);
	assert(toy_factory_garden_focal_policy_select(&context, 1U) == &background);
	world.plants[0] = world.plants[1];
	assert(toy_factory_garden_focal_policy_select(&context, 0U) == &background);
	world = saved_world;
	/* Routing to self is exactly the original decision, including private memory. */
	assert(toy_factory_garden_focal_policy_init(&world, &background, &background, founder_id,
						    &context, &routed) == 0);
	assert(picosystem_garden_agent_decide(&background, &observation, &memory, &expected) == 0);
	assert(picosystem_garden_agent_decide(&routed, &observation, &memory, &result) == 0);
	assert(memcmp(&result, &expected, sizeof(result)) == 0);
	fixtures[0].error = -EIO;
	assert(picosystem_garden_agent_decide(&background, &observation, &memory, &expected) ==
	       -EIO);
	assert(picosystem_garden_agent_decide(&routed, &observation, &memory, &result) == -EIO);
	assert(memcmp(&result, &expected, sizeof(result)) == 0);
	fixtures[0].error = 0;
	assert(toy_factory_garden_focal_policy_select(NULL, 0U) == NULL);
	assert(toy_factory_garden_focal_policy_select(&context, world.plant_count) == NULL);
	assert(toy_factory_garden_focal_policy_select(&context, UINT8_MAX) == NULL);
	observation.plant_index = world.plant_count;
	assert(picosystem_garden_agent_decide(&routed, &observation, &memory, &result) == -EINVAL);
	assert(routed.decide(NULL, &memory, &result, routed.context) == -EINVAL);
	/* Failed initialization must not partially replace a usable router. */
	const struct toy_factory_garden_focal_context saved_context = context;
	const struct picosystem_garden_agent_policy saved_policy = routed;
	assert(toy_factory_garden_focal_policy_init(NULL, &background, &focal, founder_id, &context,
						    &routed) == -EINVAL);
	assert(toy_factory_garden_focal_policy_init(&world, NULL, &focal, founder_id, &context,
						    &routed) == -EINVAL);
	assert(toy_factory_garden_focal_policy_init(&world, &background, NULL, founder_id, &context,
						    &routed) == -EINVAL);
	assert(toy_factory_garden_focal_policy_init(&world, &background, &focal, founder_id, NULL,
						    &routed) == -EINVAL);
	assert(toy_factory_garden_focal_policy_init(&world, &background, &focal, founder_id,
						    &context, NULL) == -EINVAL);
	assert(toy_factory_garden_focal_policy_init(&world, &background, &focal, 0U, &context,
						    &routed) == -EINVAL);
	assert(toy_factory_garden_focal_policy_init(&world, &background, &focal, UINT32_MAX,
						    &context, &routed) == -ENOENT);
	assert(toy_factory_garden_focal_policy_init(&world, &background, &focal, founder_id,
						    &context, &background) == -EINVAL);
	assert(toy_factory_garden_focal_policy_init(&world, &background, &focal, founder_id,
						    &context, &focal) == -EINVAL);
	assert(toy_factory_garden_focal_policy_init(&world, &routed, &focal, founder_id, &context,
						    &background) == -EINVAL);
	for (uint8_t test = 0U; test < 9U; ++test) {
		struct picosystem_garden_agent_policy bad = focal;
		world = saved_world;
		if (test == 0U) {
			bad.decide = NULL;
		} else if (test == 1U) {
			bad.context = &context;
		} else if (test == 2U) {
			bad.arbitration = 0U;
		} else if (test == 3U) {
			world.logic_tick_count = 15U;
		} else if (test == 4U) {
			world.plants[1].parent_lineage_id = 1U;
		} else if (test == 5U) {
			world.plants[1].generation = 1U;
		} else if (test == 6U) {
			world.plants[1].flags |= PICOSYSTEM_GARDEN_PLANT_DEAD;
		} else if (test == 7U) {
			world.plants[0].lineage_id = founder_id;
		} else {
			world.plant_count = PICOSYSTEM_GARDEN_MAX_PLANTS + 1U;
		}
		assert(toy_factory_garden_focal_policy_init(&world, &background, &bad, founder_id,
							    &context, &routed) == -EINVAL);
	}
	world = saved_world;
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	focal.leaf_policy = toy_factory_garden_leaf_policy("selective");
	assert(toy_factory_garden_focal_policy_init(&world, &background, &focal, founder_id,
						    &context, &routed) == -EINVAL);
#endif
	assert(memcmp(&context, &saved_context, sizeof(context)) == 0);
	assert(memcmp(&routed, &saved_policy, sizeof(routed)) == 0);
	puts("Focal routing, descendants, compaction, identity, errors and preservation passed");
	return 0;
}
