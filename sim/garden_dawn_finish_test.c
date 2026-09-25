/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_agent.h"
#include "garden_dawn_finish.h"

static void receipts(void)
{
	struct picosystem_garden_dawn_finish state = {0};
	assert(picosystem_garden_dawn_finish_parse(NULL, &state) == -EINVAL);
	assert(picosystem_garden_dawn_finish_parse("defer", NULL) == -EINVAL);
	assert(picosystem_garden_dawn_finish_parse("none", &state) == -EINVAL);
	assert(!state.enabled);
	assert(picosystem_garden_dawn_finish_parse("defer", &state) == 0);
	assert(picosystem_garden_dawn_finish_parse("defer", &state) == -EINVAL);
	struct picosystem_garden_dark_event event = {
		.lineage_id = 12U,
		.node_index = 378U,
		.nodes_before = 61U,
		.nodes_after = 61U,
		.energy = 251U,
		.water = 512U,
		.energy_cost = 8U,
		.water_cost = 5U,
		.kind = PICOSYSTEM_GARDEN_EXPENSE_GROWTH,
		.before = {.supported = true},
		.after = {.supported = true},
	};
	struct picosystem_garden_agent_observation observation = {
		.tip_index = 378U,
		.tissue_kind = PICOSYSTEM_GARDEN_NODE_ROOT,
		.tip_x = 47U,
		.tip_y = 193U,
		.depth = 9U,
		.maximum_depth = 9U,
	};
	assert(picosystem_garden_dawn_finish_validate(&state, 66089U) == 0);
	assert(picosystem_garden_dawn_finish_validate(&state, 66090U) == -EINVAL);
	assert(picosystem_garden_dawn_finish_check(&state, 66075U, &event, &observation, 2U) == 0);
	const struct picosystem_garden_dawn_finish before = state;
	for (unsigned int defect = 0U; defect < 15U; ++defect) {
		struct picosystem_garden_dark_event bad = event;
		struct picosystem_garden_agent_observation wrong = observation;
		switch (defect) {
		case 0U:
			++bad.energy;
			break;
		case 1U:
			--bad.water;
			break;
		case 2U:
			++bad.nodes_before;
			break;
		case 3U:
			++bad.nodes_after;
			break;
		case 4U:
			++bad.stress;
			break;
		case 5U:
			++bad.energy_cost;
			break;
		case 6U:
			++bad.water_cost;
			break;
		case 7U:
			bad.denied = true;
			break;
		case 8U:
			bad.invalid = true;
			break;
		case 9U:
			bad.before.supported = false;
			break;
		case 10U:
			bad.after.death_step = 1U;
			break;
		case 11U:
			++wrong.tip_x;
			break;
		case 12U:
			--wrong.depth;
			break;
		case 13U:
			wrong.tissue_kind = PICOSYSTEM_GARDEN_NODE_STEM;
			break;
		default:
			--wrong.tip_index;
			break;
		}
		assert(picosystem_garden_dawn_finish_check(&state, 66090U, &bad, &wrong, 2U) ==
		       -EINVAL);
		assert(memcmp(&state, &before, sizeof(state)) == 0);
	}
	assert(picosystem_garden_dawn_finish_check(&state, 66090U, &event, &observation, 1U) ==
	       -EINVAL);
	assert(picosystem_garden_dawn_finish_check(&state, 66105U, &event, &observation, 2U) ==
	       -EINVAL);
	++event.lineage_id;
	assert(picosystem_garden_dawn_finish_check(&state, 66090U, &event, &observation, 2U) == 0);
	--event.lineage_id;
	assert(picosystem_garden_dawn_finish_check(&state, 66090U, &event, &observation, 2U) ==
	       -ECANCELED);
	assert(picosystem_garden_dawn_finish_check(&state, 66090U, &event, &observation, 2U) ==
	       -EALREADY);
	++event.lineage_id;
	assert(picosystem_garden_dawn_finish_check(&state, 66090U, &event, &observation, 2U) == 0);
	--event.lineage_id;
	/* A compacted node index is allowed; identity/position/depth are unchanged. */
	event.node_index = observation.tip_index = 60U;
	event.energy = 100U;
	event.water = 300U;
	assert(picosystem_garden_dawn_finish_check(&state, 66105U, &event, &observation, 2U) ==
	       -ECANCELED);
	assert(state.hits == 2U && state.last_node == 60U);
	assert(picosystem_garden_dawn_finish_check(&state, 68340U, &event, &observation, 2U) ==
	       -ECANCELED);
	const struct picosystem_garden_dawn_finish released = state;
	assert(picosystem_garden_dawn_finish_check(&state, 68355U, &event, &observation, 2U) == 0);
	assert(memcmp(&released, &state, sizeof(state)) == 0);
	assert(picosystem_garden_dawn_finish_validate(&state, 245760U) == 0);
	state.hits = UINT16_MAX;
	assert(picosystem_garden_dawn_finish_validate(&state, 245760U) == -EINVAL);
}

static int decide(const struct picosystem_garden_agent_observation *observation,
		  const struct picosystem_garden_agent_memory *memory,
		  struct picosystem_garden_agent_decision *decision, const void *context)
{
	(void)context;
	*decision = (struct picosystem_garden_agent_decision){
		.next_memory = *memory,
		.proposal = {.tip_index = observation->tip_index,
			     .action = PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP},
	};
	decision->next_memory.hidden[0] = 42;
	return 0;
}

static void reserve_receipts(void)
{
	struct picosystem_garden_dawn_finish state = {0};
	assert(picosystem_garden_dawn_finish_parse("reserve", &state) == 0);
	assert(state.enabled && state.reserve_handoff);
	assert(picosystem_garden_dawn_finish_parse("defer", &state) == -EINVAL);
	struct picosystem_garden_dark_event event = {
		.lineage_id = 12U,
		.node_index = 378U,
		.nodes_before = 61U,
		.nodes_after = 61U,
		.energy = 251U,
		.water = 512U,
		.energy_cost = 8U,
		.water_cost = 5U,
		.kind = PICOSYSTEM_GARDEN_EXPENSE_GROWTH,
		.before = {.supported = true},
		.after = {.supported = true},
	};
	struct picosystem_garden_agent_observation observation = {
		.tip_index = 378U,
		.tissue_kind = PICOSYSTEM_GARDEN_NODE_ROOT,
		.tip_x = 47U,
		.tip_y = 193U,
		.depth = 9U,
		.maximum_depth = 9U,
		.maintenance_energy_cost = 8U,
	};
	assert(picosystem_garden_dawn_finish_check(&state, 66090U, &event, &observation, 2U) ==
	       -ECANCELED);
	assert(picosystem_garden_dawn_finish_check(&state, 68340U, &event, &observation, 2U) ==
	       -ECANCELED);
	const struct picosystem_garden_dawn_finish dawn = state;
	event.energy = 15U;
	observation.maintenance_energy_cost = 7U;
	assert(picosystem_garden_dawn_finish_check(&state, 68355U, &event, &observation, 2U) ==
	       -EINVAL);
	assert(memcmp(&state, &dawn, sizeof(state)) == 0);
	observation.maintenance_energy_cost = 8U;
	assert(picosystem_garden_dawn_finish_check(&state, 68355U, &event, &observation, 2U) ==
	       -ECANCELED);
	assert(state.hits == 3U && state.handoff_tick == 0U);
	event.energy = 16U;
	assert(picosystem_garden_dawn_finish_check(&state, 68370U, &event, &observation, 2U) == 0);
	assert(state.hits == 3U && state.handoff_tick == 68370U && state.handoff_energy == 16U &&
	       state.handoff_node == 378U);
	assert(picosystem_garden_dawn_finish_check(&state, 68370U, &event, &observation, 2U) ==
	       -EALREADY);
	const struct picosystem_garden_dawn_finish handed_off = state;
	assert(picosystem_garden_dawn_finish_check(&state, 68385U, &event, &observation, 1U) == 0);
	assert(memcmp(&state, &handed_off, sizeof(state)) == 0);
	assert(picosystem_garden_dawn_finish_validate(&state, 245760U) == 0);
	for (unsigned int defect = 0U; defect < 7U; ++defect) {
		struct picosystem_garden_dawn_finish bad = state;
		switch (defect) {
		case 0U:
			bad.reserve_handoff = false;
			break;
		case 1U:
			bad.handoff_tick = 0U;
			break;
		case 2U:
			bad.handoff_tick = 68340U;
			break;
		case 3U:
			bad.handoff_tick = 69120U;
			break;
		case 4U:
			bad.handoff_energy = 15U;
			break;
		case 5U:
			bad.handoff_node = PICOSYSTEM_GARDEN_MAX_NODES;
			break;
		default:
			bad.enabled = false;
			break;
		}
		assert(picosystem_garden_dawn_finish_validate(&bad, 245760U) == -EINVAL);
	}
	state = dawn;
	event.energy = 15U;
	assert(picosystem_garden_dawn_finish_check(&state, 69105U, &event, &observation, 2U) ==
	       -ECANCELED);
	const struct picosystem_garden_dawn_finish expired = state;
	assert(picosystem_garden_dawn_finish_check(&state, 69120U, &event, &observation, 2U) == 0);
	assert(memcmp(&state, &expired, sizeof(state)) == 0);
	assert(picosystem_garden_dawn_finish_validate(&state, 245760U) == 0);
	state = (struct picosystem_garden_dawn_finish){.reserve_handoff = true};
	assert(picosystem_garden_dawn_finish_parse("reserve", &state) == -EINVAL);
}

static void step_at(struct picosystem_garden_world *world, uint32_t tick,
		    const struct picosystem_garden_agent_policy *policy)
{
	world->logic_tick_count = tick - 1U;
	world->ecology_tick_count = tick / 15U - 1U;
	const int err = picosystem_garden_world_step_with_policy(world, policy);
	if (err != 0) {
		fprintf(stderr, "step %u err=%d hits=%u energy=%u water=%u events=%u\n", tick, err,
			world->dawn_finish.hits, world->plants[0].stored_energy,
			world->plants[0].stored_water, world->dark_guard.count);
	}
	assert(err == 0);
}

static void transactions(void)
{
	for (uint8_t arbitration = 0U; arbitration < PICOSYSTEM_GARDEN_AGENT_ARBITRATION_COUNT;
	     ++arbitration) {
		struct picosystem_garden_world world;
		assert(picosystem_garden_world_reset(&world, 123U) == 0);
		assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_SHRUB,
							  4U) == 0);
		world.auto_gardener_enabled = false;
		memset(world.moisture, 0, sizeof(world.moisture));
		memset(world.leaf_condition, 0, sizeof(world.leaf_condition));
		world.plant_count = 2U;
		world.lineage_sequence = 13U;
		world.plants[1] = world.plants[0];
		world.plants[1].lineage_id = 13U;
		world.plants[1].base_node_index = 60U;
		world.plants[1].node_count = 318U;
		world.node_count = 379U;
		for (uint16_t i = 0U; i < world.node_count; ++i) {
			world.nodes[i] = (struct picosystem_garden_node){
				.x = 8U,
				.y = 160U,
				.growth_progress = UINT8_MAX,
				.kind = PICOSYSTEM_GARDEN_NODE_ROOT,
				.plant_index = (uint8_t)((i < 60U || i == 378U) ? 0U : 1U),
				.parent_index = PICOSYSTEM_GARDEN_NODE_NONE,
			};
		}
		world.nodes[378].x = 47U;
		world.nodes[0].kind = PICOSYSTEM_GARDEN_NODE_STEM;
		world.nodes[378].y = 193U;
		world.nodes[378].depth = 9U;
		world.nodes[378].flags = PICOSYSTEM_GARDEN_NODE_TIP;
		world.plants[0].lineage_id = 12U;
		world.plants[0].node_count = 61U;
		world.plants[0].vigor = 0;
		world.plants[0].genome.stature = 0;
		world.plants[0].genome.shoot_bias = 2;
		world.plants[0].growth_phase = 3U;
		world.plants[0].stored_energy = 251U;
		world.plants[0].stored_water = 512U;
		const struct picosystem_garden_world original = world;
		const uint32_t hash = picosystem_garden_world_hash(&world);
		world.dawn_finish.enabled = true;
		assert(picosystem_garden_world_hash(&world) == hash);
		const struct picosystem_garden_agent_policy policy = {
			.decide = decide,
			.arbitration = arbitration,
		};
		step_at(&world, 66090U, &policy);
		step_at(&world, 66105U, &policy);
		assert(world.dawn_finish.hits == 2U);
		assert(world.dark_guard.count == 1U && !world.dark_guard.events[0].denied);
		assert(world.night_capacity.count == 0U);
		assert(world.plants[0].stored_energy == 251U &&
		       world.plants[0].stored_water == 512U);
		assert(world.plants[0].random_state == original.plants[0].random_state);
		assert(memcmp(&world.plants[0].agent_memory, &original.plants[0].agent_memory,
			      sizeof(world.plants[0].agent_memory)) == 0);
		assert(world.plants[0].growth_phase == original.plants[0].growth_phase);
		assert(world.plants[0].growth_cooldown == 0U);
		assert(world.plants[0].last_root_tip_index ==
		       original.plants[0].last_root_tip_index);
		assert(world.plants[0].last_shoot_tip_index ==
		       original.plants[0].last_shoot_tip_index);
		assert(world.plants[0].agent_telemetry.decision_count == 0U);
		assert(memcmp(world.nodes, original.nodes, sizeof(world.nodes)) == 0);
		struct picosystem_garden_world reserve = world;
		reserve.dawn_finish.reserve_handoff = true;
		reserve.plants[0].stored_energy = 15U;
		step_at(&reserve, 68385U, &policy);
		assert(reserve.dawn_finish.hits == 3U && reserve.dawn_finish.handoff_tick == 0U);
		assert(reserve.plants[0].stored_energy == 15U &&
		       reserve.plants[0].stored_water == 512U);
		assert(reserve.plants[0].random_state == original.plants[0].random_state);
		assert(memcmp(&reserve.plants[0].agent_memory, &original.plants[0].agent_memory,
			      sizeof(reserve.plants[0].agent_memory)) == 0);
		assert(reserve.plants[0].growth_phase == original.plants[0].growth_phase);
		assert(reserve.plants[0].growth_cooldown == 0U);
		assert(reserve.plants[0].last_root_tip_index ==
		       original.plants[0].last_root_tip_index);
		assert(reserve.plants[0].last_shoot_tip_index ==
		       original.plants[0].last_shoot_tip_index);
		assert(reserve.plants[0].agent_telemetry.decision_count == 0U);
		assert(memcmp(reserve.nodes, original.nodes, sizeof(reserve.nodes)) == 0);
		reserve.plants[0].stored_energy = 16U;
		step_at(&reserve, 68415U, &policy);
		assert(reserve.dawn_finish.hits == 3U &&
		       reserve.dawn_finish.handoff_tick == 68415U &&
		       reserve.dawn_finish.handoff_energy == 16U);
		assert(reserve.plants[0].stored_energy == 8U &&
		       reserve.plants[0].stored_water == 507U);
		assert(reserve.plants[0].agent_telemetry.finish_count == 1U);
		assert(reserve.plants[0].agent_memory.hidden[0] == 42);
		assert((reserve.nodes[378].flags & PICOSYSTEM_GARDEN_NODE_TIP) == 0U);
		step_at(&reserve, 68460U, &policy);
		assert(reserve.plants[0].stored_energy == 0U && reserve.plants[0].stress == 0U);
		assert(picosystem_garden_world_reset(&reserve, 123U) == 0);
		const struct picosystem_garden_dawn_finish empty = {0};
		assert(memcmp(&reserve.dawn_finish, &empty, sizeof(empty)) == 0);
		step_at(&world, 68340U, &policy);
		assert(world.dawn_finish.hits == 3U &&
		       world.plants[0].agent_telemetry.decision_count == 0U);
		step_at(&world, 68355U, &policy);
		assert(world.dawn_finish.hits == 3U &&
		       world.plants[0].agent_telemetry.finish_count == 1U);
		assert(world.plants[0].agent_memory.hidden[0] == 42);
		assert((world.nodes[378].flags & PICOSYSTEM_GARDEN_NODE_TIP) == 0U);
		struct picosystem_garden_world control = original;
		step_at(&control, 66090U, &policy);
		assert(control.plants[0].stored_energy == 243U &&
		       control.plants[0].stored_water == 507U);
		assert(control.plants[0].agent_telemetry.finish_count == 1U);
		assert(picosystem_garden_world_reset(&world, 123U) == 0);
		assert(!world.dawn_finish.enabled && world.dawn_finish.hits == 0U);
		assert(picosystem_garden_dawn_finish_validate(&world.dawn_finish, 0U) == 0);
	}
}

int main(void)
{
	receipts();
	reserve_receipts();
	transactions();
	puts("Dawn FINISH: scoped receipts, retries, compaction identity, atomic rejection, "
	     "reserve handoff, noon expiry, release and reset passed");
	return 0;
}
