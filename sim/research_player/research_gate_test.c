/* SPDX-License-Identifier: Apache-2.0 */
#include "research_gate.h"

#include <assert.h>
#include <errno.h>
#include <string.h>

static unsigned int calls;
static int failure;
struct expected_inputs {
	const struct picosystem_garden_leaf_observation *observation;
	const struct picosystem_garden_agent_memory *memory;
};

static int original(const struct picosystem_garden_leaf_observation *observation,
		    const struct picosystem_garden_agent_memory *memory,
		    struct picosystem_garden_leaf_decision *decision, const void *context)
{
	const struct expected_inputs *const expected = context;
	assert(expected != NULL && observation == expected->observation &&
	       memory == expected->memory);
	++calls;
	*decision = (struct picosystem_garden_leaf_decision){.node_index = observation->node_index,
							     .next_memory = *memory,
							     .action = PICOSYSTEM_GARDEN_LEAF_WAIT};
	return failure;
}

void research_gate_routing_tests(void)
{
	struct picosystem_garden_world world = {.plant_count = 1U, .node_count = 1U};
	world.plants[0].lineage_id = 2U;
	struct toy_factory_leaf_family_owners owners = {
		.count = 3U, .founders = 3U, .root = {0U, 1U, 2U, 3U}};
	struct picosystem_garden_leaf_observation observation = {.condition = 135U,
								 .light = 139U,
								 .stored_energy = 192U,
								 .stored_water = 512U,
								 .mature_leaf_count = 21U,
								 .maintenance_energy = 4U,
								 .maintenance_water = 3U,
								 .renewal_energy = 9U,
								 .renewal_water = 5U};
	const struct picosystem_garden_agent_memory memory = {
		.hidden = {-3, 2, -1, 4, 0, 1, -5, 2}};
	const struct expected_inputs expected = {.observation = &observation, .memory = &memory};
	const struct picosystem_garden_leaf_policy candidate = {.decide = original,
								.context = &expected};
	struct research_gate *invalid = NULL;
	assert(research_gate_open(0U, 1U, &invalid) == -EINVAL && invalid == NULL);
	assert(research_gate_open(0U, UINT32_MAX, &invalid) == -EINVAL && invalid == NULL);
	for (uint8_t timing = 0U; timing < 2U; ++timing) {
		const uint32_t after = timing == 0U ? 0U : RESEARCH_GATE_AFTER;
		for (uint8_t variant = 0U; variant < 4U; ++variant) {
			struct research_gate *gate = NULL;
			assert(research_gate_open(variant, after, &gate) == 0);
			const struct research_gate_context context = {.gate = gate,
								      .owners = &owners};
			uint8_t header[RESEARCH_GATE_HEADER_BYTES];
			research_gate_header(gate, header);
			assert(memcmp(header, "TGR1", 4U) == 0 && header[4] == variant &&
			       header[5] == 2U);
			assert(header[6] == 0U && header[7] == 0U);
			for (uint8_t i = 0U; i < 4U; ++i) {
				assert(header[8U + i] == (uint8_t)(after >> (8U * i)));
			}
			struct toy_factory_leaf_neural_model derived;
			assert(toy_factory_leaf_neural_decode(header + 12U, sizeof(header) - 12U,
							      &derived) == 0);
			struct picosystem_garden_leaf_decision output;
			for (uint32_t tick = after == 0U ? 0U : after - 1U; tick <= after + 1U;
			     ++tick) {
				world.logic_tick_count = tick;
				const unsigned int before = calls;
				assert(research_gate_decide(&world, &candidate, &observation,
							    &memory, &output, &context) == 0);
				assert(calls == before + (tick <= after ? 1U : 0U));
				assert(output.action == (tick > after && (variant & 1U) ? 1U : 0U));
				assert(output.node_index == observation.node_index &&
				       memcmp(output.next_memory.hidden, memory.hidden,
					      sizeof(memory.hidden)) == 0);
			}
			/* An established descendant and a newborn whose parent no longer occupies a
			 * slot.
			 */
			for (uint32_t id = 2U; id <= 4U; ++id) {
				world.plants[0].lineage_id = id;
				world.plants[0].parent_lineage_id = id == 4U ? 2U : 0U;
				const unsigned int before = calls;
				assert(research_gate_decide(&world, &candidate, &observation,
							    &memory, &output, &context) == 0);
				assert(calls == before + (id == 3U ? 1U : 0U));
				assert(output.action == (id != 3U && (variant & 1U) ? 1U : 0U));
			}
			owners.count = 4U;
			owners.root[4] = 2U;
			assert(research_gate_decide(&world, &candidate, &observation, &memory,
						    &output, &context) == 0);
			assert(output.action == ((variant & 1U) ? 1U : 0U));
			owners.count = 3U;
			world.plants[0].lineage_id = 2U;
			world.plants[0].parent_lineage_id = 0U;
			observation.condition = 192U;
			observation.light = 200U;
			observation.stored_energy = 256U;
			assert(research_gate_decide(&world, &candidate, &observation, &memory,
						    &output, &context) == 0);
			assert(output.action == ((variant & 2U) ? 1U : 0U));
			observation.condition = 135U;
			observation.light = 139U;
			observation.stored_energy = 192U;
			memset(&output, 0xa5, sizeof(output));
			const struct picosystem_garden_leaf_decision saved = output;
			world.plants[0].lineage_id = 4U;
			assert(research_gate_decide(&world, &candidate, &observation, &memory,
						    &output, &context) == -ERANGE);
			assert(memcmp(&output, &saved, sizeof(output)) == 0);
			world.plants[0].lineage_id = 3U;
			failure = -EIO;
			assert(research_gate_decide(&world, &candidate, &observation, &memory,
						    &output, &context) == -EIO);
			failure = 0;
			assert(memcmp(&output, &saved, sizeof(output)) == 0);
			world.plants[0].lineage_id = 2U;
			research_gate_close(gate);
		}
	}
}
