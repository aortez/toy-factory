/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_agent.h"
#include "garden_night_capacity.h"

static int decide(const struct picosystem_garden_agent_observation *observation,
		  const struct picosystem_garden_agent_memory *memory,
		  struct picosystem_garden_agent_decision *decision, const void *context)
{
	*decision = (struct picosystem_garden_agent_decision){
		.next_memory = *memory,
		.proposal = {.tip_index = observation->tip_index,
			     .action = *(const uint8_t *)context},
	};
	decision->next_memory.hidden[0] = 42;
	if (decision->proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND) {
		decision->proposal.candidate_count = observation->candidate_count;
		for (uint8_t i = 0U; i < observation->candidate_count; ++i) {
			decision->proposal.candidate_order[i] = i;
		}
	}
	return 0;
}

static void fixture(struct picosystem_garden_world *world, uint16_t nodes, uint16_t energy)
{
	assert(picosystem_garden_world_reset(world, 123U) == 0);
	assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_SHRUB, 4U) == 0);
	world->auto_gardener_enabled = false;
	for (uint16_t i = 4U; i < nodes; ++i) {
		world->nodes[i] = world->nodes[0];
		world->nodes[i].parent_index = 0U;
		world->nodes[i].x = 8U;
		world->nodes[i].y = 32U;
	}
	world->node_count = nodes;
	world->plants[0].node_count = nodes;
	world->plants[0].stored_energy = energy;
	world->plants[0].stored_water = 512U;
	world->plants[0].vigor = 0;
	for (uint16_t i = 0U; i < nodes; ++i) {
		world->nodes[i].flags = 0U;
		world->nodes[i].growth_progress = UINT8_MAX;
		world->leaf_condition[i] = 0U;
	}
	world->nodes[1].flags = PICOSYSTEM_GARDEN_NODE_TIP | PICOSYSTEM_GARDEN_NODE_LEAF;
}

static void step_at(struct picosystem_garden_world *world, uint32_t tick,
		    const struct picosystem_garden_agent_policy *policy)
{
	world->logic_tick_count = tick - 1U;
	world->ecology_tick_count = tick / 15U - 1U;
	assert(picosystem_garden_world_step_with_policy(world, policy) == 0);
}

static void projection(bool print_reference)
{
	for (uint16_t n = 1U; n <= PICOSYSTEM_GARDEN_MAX_NODES; ++n) {
		struct picosystem_garden_dark_budget b;
		assert(picosystem_garden_night_project(n, &b) == 0);
		assert(b.supported && b.payments == 37U && b.dark_steps == 149U);
		assert((b.death_step == 0U) == (((n + 7U) / 8U) * 30U <= 256U));
		if (print_reference) {
			printf("%u %u %u %u %u %u %u %u %u %u\n", n, b.energy, b.stress,
			       b.peak_stress, b.upkeep, b.dark_steps, b.payments,
			       b.first_shortage_step, b.death_step, b.supported);
		}
	}
	struct picosystem_garden_dark_budget b;
	memset(&b, 0x5a, sizeof(b));
	const struct picosystem_garden_dark_budget original = b;
	assert(picosystem_garden_night_project(0U, &b) == -EINVAL);
	assert(memcmp(&b, &original, sizeof(b)) == 0);
	assert(picosystem_garden_night_project(513U, &b) == -EINVAL);
	assert(memcmp(&b, &original, sizeof(b)) == 0);
	assert(picosystem_garden_night_project(64U, NULL) == -EINVAL);
}

static void transactions(void)
{
	for (uint8_t arbitration = 0U; arbitration < PICOSYSTEM_GARDEN_AGENT_ARBITRATION_COUNT;
	     ++arbitration) {
		const uint8_t action = PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND;
		const struct picosystem_garden_agent_policy policy = {
			.decide = decide, .context = &action, .arbitration = arbitration};
		for (uint16_t nodes = 63U; nodes <= 65U; ++nodes) {
			struct picosystem_garden_world world;
			fixture(&world, nodes, 256U);
			const struct picosystem_garden_plant before = world.plants[0];
			const struct picosystem_garden_world original = world;
			step_at(&world, 15U, &policy);
			assert(world.dark_guard.count == 1U && !world.dark_guard.events[0].denied);
			assert(world.night_capacity.count == 1U &&
			       world.night_capacity.evaluated == 1U);
			assert(world.night_capacity.events[0].expense_index == 0U);
			if (nodes == 63U) {
				assert(world.node_count == 64U &&
				       world.plants[0].stored_energy == 248U);
				assert(world.agent_telemetry.extend_count == 1U);
				assert(world.plants[0].agent_memory.hidden[0] == 42);
				assert(world.night_capacity.denied == 0U);
				continue;
			}
			assert(world.night_capacity.denied == 1U);
			assert(world.night_capacity.events[0].denied);
			assert(world.node_count == nodes && world.plants[0].stored_energy == 256U);
			assert(world.plants[0].stored_water == before.stored_water);
			assert(world.plants[0].random_state == before.random_state);
			assert(memcmp(&world.plants[0].agent_memory, &before.agent_memory,
				      sizeof(before.agent_memory)) == 0);
			assert(world.plants[0].growth_phase == before.growth_phase);
			assert(world.plants[0].growth_cooldown == 0U);
			assert(world.plants[0].last_shoot_tip_index == before.last_shoot_tip_index);
			assert(world.plants[0].last_root_tip_index == before.last_root_tip_index);
			assert(world.agent_telemetry.decision_count == 0U);
			assert(memcmp(world.nodes, original.nodes, sizeof(world.nodes)) == 0);
			step_at(&world, 30U, &policy);
			assert(world.night_capacity.count == 1U &&
			       world.night_capacity.denied == 2U);
			assert(world.night_capacity.evaluated == 2U);
			assert(world.node_count == nodes &&
			       world.plants[0].random_state == before.random_state);
			assert(world.agent_telemetry.decision_count == 0U);
		}
		struct picosystem_garden_world world;
		fixture(&world, 64U, 256U);
		step_at(&world, 4635U, &policy);
		assert(world.dark_guard.events[0].denied && world.night_capacity.count == 0U);
		step_at(&world, 6885U, &policy);
		assert(!world.dark_guard.events[0].denied && world.night_capacity.denied == 1U);
		assert(world.node_count == 64U && world.agent_telemetry.decision_count == 0U);
	}
}

static void no_node_actions(void)
{
	for (uint8_t action = 0U; action <= PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP;
	     action += 2U) {
		struct picosystem_garden_world world;
		fixture(&world, 65U, 256U);
		const struct picosystem_garden_agent_policy policy = {.decide = decide,
								      .context = &action};
		step_at(&world, 15U, &policy);
		assert(world.node_count == 65U && world.night_capacity.count == 0U);
		assert(world.agent_telemetry.decision_count == 1U);
		assert(world.plants[0].stored_energy == (action == 0U ? 256U : 248U));
	}
	struct picosystem_garden_world world;
	fixture(&world, 64U, 256U);
	struct picosystem_garden_agent_observation observation;
	assert(picosystem_garden_agent_observe_tip(&world, 0U, 1U, 0U, &observation) == 0);
	for (uint8_t i = 0U; i < observation.candidate_count; ++i) {
		if ((observation.candidates[i].flags &
		     PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS) != 0U) {
			world.nodes[4U + i].x = observation.candidates[i].x;
			world.nodes[4U + i].y = observation.candidates[i].y;
		}
	}
	const uint8_t action = PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND;
	const struct picosystem_garden_agent_policy policy = {.decide = decide, .context = &action};
	step_at(&world, 15U, &policy);
	assert(world.node_count == 64U && world.plants[0].stored_energy == 248U);
	assert(world.night_capacity.count == 0U && world.agent_telemetry.extend_count == 1U);
	assert((world.nodes[1].flags & PICOSYSTEM_GARDEN_NODE_TIP) == 0U);
	fixture(&world, 64U, 7U);
	step_at(&world, 15U, &policy);
	assert(world.night_capacity.evaluated == 0U && world.dark_guard.count == 0U);
	assert(world.agent_telemetry.decision_count == 0U);
}

static void errors_and_diagnostics(void)
{
	struct picosystem_garden_night_audit audit = {0};
	const struct picosystem_garden_dark_event event = {
		.kind = PICOSYSTEM_GARDEN_EXPENSE_GROWTH, .nodes_before = 64U, .nodes_after = 65U};
	assert(picosystem_garden_night_check(NULL, &event, 0U) == -EINVAL);
	assert(picosystem_garden_night_check(&audit, NULL, 0U) == -EINVAL);
	assert(picosystem_garden_night_check(&audit, &event, PICOSYSTEM_GARDEN_DARK_EVENTS) ==
	       -EINVAL);
	for (unsigned int defect = 0U; defect < 6U; ++defect) {
		struct picosystem_garden_dark_event bad = event;
		switch (defect) {
		case 0U:
			bad.denied = true;
			break;
		case 1U:
			bad.invalid = true;
			break;
		case 2U:
			bad.kind = PICOSYSTEM_GARDEN_EXPENSE_SEED;
			break;
		case 3U:
			bad.nodes_after = 66U;
			break;
		case 4U:
			bad.nodes_before = 0U;
			break;
		default:
			bad.nodes_after = 513U;
			break;
		}
		assert(picosystem_garden_night_check(&audit, &bad, 0U) == -EINVAL);
		assert(audit.count == 0U && audit.evaluated == 0U && !audit.overflow);
	}
	audit.count = PICOSYSTEM_GARDEN_NIGHT_EVENTS;
	assert(picosystem_garden_night_check(&audit, &event, 0U) == -EOVERFLOW && audit.overflow);
	assert(picosystem_garden_night_print(&audit) == -EOVERFLOW);
	audit = (struct picosystem_garden_night_audit){.evaluated = UINT32_MAX};
	assert(picosystem_garden_night_check(&audit, &event, 0U) == -EOVERFLOW && audit.overflow);
	assert(picosystem_garden_night_print(NULL) == -EINVAL);
	struct picosystem_garden_world world;
	fixture(&world, 64U, 256U);
	const uint32_t hash = picosystem_garden_world_hash(&world);
	world.night_capacity = audit;
	assert(picosystem_garden_world_hash(&world) == hash);
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	assert(world.night_capacity.count == 0U && world.night_capacity.evaluated == 0U &&
	       world.night_capacity.denied == 0U && !world.night_capacity.overflow);
}

int main(int argc, char **argv)
{
	const bool print_reference = argc == 2 && strcmp(argv[1], "--reference") == 0;
	assert(argc == 1 || print_reference);
	projection(print_reference);
	transactions();
	no_node_actions();
	errors_and_diagnostics();
	if (!print_reference) {
		puts("Full-night capacity projection, transactions and diagnostics passed");
	}
	return 0;
}
