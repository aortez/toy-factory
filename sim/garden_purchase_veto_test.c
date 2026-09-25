/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_agent.h"
#include "garden_purchase_veto.h"

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

static void receipts(void)
{
	struct picosystem_garden_purchase_veto veto = {0};
	assert(picosystem_garden_purchase_parse("none", &veto.selection) == -EINVAL);
	assert(picosystem_garden_purchase_parse("bogus", &veto.selection) == -EINVAL);
	assert(veto.selection == PICOSYSTEM_GARDEN_PURCHASE_NONE);
	assert(picosystem_garden_purchase_parse("extension", &veto.selection) == 0);
	assert(picosystem_garden_purchase_parse("finish", &veto.selection) == -EINVAL);
	struct picosystem_garden_dark_event event = {
		.lineage_id = 21U,
		.node_index = 323U,
		.nodes_before = 32U,
		.nodes_after = 33U,
		.energy = 151U,
		.water = 510U,
		.energy_cost = 9U,
		.water_cost = 5U,
		.kind = PICOSYSTEM_GARDEN_EXPENSE_GROWTH,
	};
	assert(picosystem_garden_purchase_check(&veto, 66045U, &event, 1U) == 0);
	assert(picosystem_garden_purchase_validate(&veto, 66045U) == 0);
	assert(picosystem_garden_purchase_validate(&veto, 66060U) == -EINVAL);
	for (unsigned int defect = 0U; defect < 12U; ++defect) {
		struct picosystem_garden_dark_event bad = event;
		switch (defect) {
		case 0U:
			++bad.energy;
			break;
		case 1U:
			++bad.water;
			break;
		case 2U:
			++bad.nodes_before;
			break;
		case 3U:
			++bad.nodes_after;
			break;
		case 4U:
			++bad.node_index;
			break;
		case 5U:
			++bad.stress;
			break;
		case 6U:
			++bad.energy_cost;
			break;
		case 7U:
			++bad.water_cost;
			break;
		case 8U:
			bad.denied = true;
			break;
		case 9U:
			bad.invalid = true;
			break;
		case 10U:
			bad.before.supported = true;
			break;
		default:
			bad.kind = PICOSYSTEM_GARDEN_EXPENSE_SEED;
			break;
		}
		assert(picosystem_garden_purchase_check(&veto, 66060U, &bad, 1U) == -EINVAL);
		assert(veto.hits == 0U);
	}
	assert(picosystem_garden_purchase_check(&veto, 66060U, &event, 2U) == -EINVAL);
	++event.lineage_id;
	assert(picosystem_garden_purchase_check(&veto, 66060U, &event, 1U) == 0);
	--event.lineage_id;
	assert(picosystem_garden_purchase_check(&veto, 66060U, &event, 1U) == -ECANCELED);
	assert(picosystem_garden_purchase_validate(&veto, 66060U) == 0);
	assert(picosystem_garden_purchase_check(&veto, 66060U, &event, 1U) == -EALREADY);
	assert(picosystem_garden_purchase_check(&veto, 66075U, &event, 1U) == 0);
}

static void retry_receipts(void)
{
	struct picosystem_garden_purchase_veto veto = {0};
	assert(picosystem_garden_purchase_parse("finish-retry", &veto.selection) == 0);
	struct picosystem_garden_dark_event event = {
		.lineage_id = 22U,
		.node_index = 271U,
		.nodes_before = 21U,
		.nodes_after = 21U,
		.energy = 92U,
		.water = 152U,
		.energy_cost = 9U,
		.water_cost = 5U,
		.kind = PICOSYSTEM_GARDEN_EXPENSE_GROWTH,
	};
	assert(picosystem_garden_purchase_validate(&veto, 69884U) == 0);
	assert(picosystem_garden_purchase_check(&veto, 69900U, &event, 2U) == -EINVAL);
	assert(veto.hits == 0U);
	assert(picosystem_garden_purchase_check(&veto, 69885U, &event, 2U) == -ECANCELED);
	assert(picosystem_garden_purchase_validate(&veto, 69899U) == 0);
	assert(picosystem_garden_purchase_validate(&veto, 69900U) == -EINVAL);
	assert(picosystem_garden_purchase_check(&veto, 69900U, &event, 2U) == -EINVAL);
	assert(veto.hits == 1U);
	event.energy = 90U;
	event.water = 161U;
	assert(picosystem_garden_purchase_check(&veto, 69900U, &event, 2U) == -ECANCELED);
	assert(picosystem_garden_purchase_validate(&veto, 69900U) == 0);
	assert(picosystem_garden_purchase_check(&veto, 69900U, &event, 2U) == -EALREADY);
	/* The diagnostic has no authority over covered or later daylight attempts. */
	event.before.supported = true;
	event.after.supported = true;
	assert(picosystem_garden_purchase_check(&veto, 69915U, &event, 2U) == 0);
	assert(picosystem_garden_purchase_check(&veto, 73725U, &event, 2U) == 0);
	assert(picosystem_garden_purchase_validate(&veto, UINT32_MAX) == 0);
	assert(veto.hits == 2U);
	veto.hits = 3U;
	assert(picosystem_garden_purchase_validate(&veto, 69915U) == -EINVAL);
}

static void transactions(void)
{
	for (enum picosystem_garden_purchase_selection selection =
		     PICOSYSTEM_GARDEN_PURCHASE_EXTENSION;
	     selection < PICOSYSTEM_GARDEN_PURCHASE_COUNT; ++selection) {
		const bool extend = selection == PICOSYSTEM_GARDEN_PURCHASE_EXTENSION;
		const bool retry = selection == PICOSYSTEM_GARDEN_PURCHASE_FINISH_RETRY;
		const uint8_t action = extend ? 1U : 2U;
		for (uint8_t arbitration = 0U;
		     arbitration < PICOSYSTEM_GARDEN_AGENT_ARBITRATION_COUNT; ++arbitration) {
			const uint16_t nodes = extend ? 32U : 21U;
			const uint16_t tip = extend ? 323U : 271U;
			const uint32_t tick = extend ? 66060U : 69885U;
			struct picosystem_garden_world world;
			assert(picosystem_garden_world_reset(&world, 123U) == 0);
			assert(picosystem_garden_world_plant_seed(
				       &world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 4U) == 0);
			world.auto_gardener_enabled = false;
			memset(world.moisture, 0, sizeof(world.moisture));
			const struct picosystem_garden_node shoot = world.nodes[1];
			world.plant_count = 2U;
			world.lineage_sequence = 99U;
			memset(world.leaf_condition, 0, sizeof(world.leaf_condition));
			world.plants[1] = world.plants[0];
			world.plants[1].flags = PICOSYSTEM_GARDEN_PLANT_DEAD;
			world.plants[1].stress = PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD;
			world.plants[1].stored_energy = 0U;
			world.plants[1].stored_water = 0U;
			world.plants[1].base_node_index = (uint16_t)(nodes - 1U);
			world.plants[1].lineage_id = 99U;
			world.node_count = tip + 1U;
			for (uint16_t i = 0U; i <= tip; ++i) {
				world.nodes[i] = shoot;
				world.nodes[i].x = 8U;
				world.nodes[i].y = 160U;
				world.nodes[i].flags = 0U;
				world.nodes[i].parent_index = PICOSYSTEM_GARDEN_NODE_NONE;
				world.nodes[i].kind = i < 15U ? PICOSYSTEM_GARDEN_NODE_STEM
							      : PICOSYSTEM_GARDEN_NODE_ROOT;
				world.nodes[i].plant_index = (uint8_t)(i < nodes - 1U ? 0U : 1U);
				world.nodes[i].growth_progress = UINT8_MAX;
			}
			world.nodes[tip] = shoot;
			world.nodes[tip].flags = PICOSYSTEM_GARDEN_NODE_TIP;
			world.nodes[tip].growth_progress = UINT8_MAX;
			world.plants[0].node_count = nodes;
			world.plants[0].lineage_id = extend ? 21U : 22U;
			world.plants[0].vigor = 0;
			world.plants[0].stored_energy = extend ? 155U : 92U;
			world.plants[0].stored_water = extend ? 512U : 152U;
			world.plants[0].genome.shoot_bias = 2;
			world.plants[0].growth_phase = 1U;
			world.plants[1].node_count = (uint16_t)(world.node_count - nodes);
			world.logic_tick_count = tick - 1U;
			world.ecology_tick_count = tick / 15U - 1U;
			const struct picosystem_garden_world before = world;
			const uint32_t hash = picosystem_garden_world_hash(&world);
			world.purchase_veto.selection = selection;
			assert(picosystem_garden_world_hash(&world) == hash);
			const struct picosystem_garden_agent_policy policy = {
				.decide = decide, .context = &action, .arbitration = arbitration};
			const int err = picosystem_garden_world_step_with_policy(&world, &policy);
			if (err != 0) {
				fprintf(stderr,
					"transaction action=%u arbitration=%u err=%d E=%u W=%u\n",
					action, arbitration, err, world.plants[0].stored_energy,
					world.plants[0].stored_water);
			}
			assert(err == 0);
			assert(world.purchase_veto.hits == 1U);
			assert(world.dark_guard.count == 1U && !world.dark_guard.events[0].denied);
			assert(world.plants[0].stored_energy == (extend ? 151U : 92U));
			assert(world.plants[0].stored_water == (extend ? 510U : 152U));
			assert(world.plants[0].node_count == nodes);
			assert(world.plants[0].random_state == before.plants[0].random_state);
			assert(memcmp(&world.plants[0].agent_memory, &before.plants[0].agent_memory,
				      sizeof(world.plants[0].agent_memory)) == 0);
			assert(world.plants[0].growth_phase == before.plants[0].growth_phase);
			assert(world.plants[0].growth_cooldown == 0U);
			assert(world.plants[0].last_shoot_tip_index ==
			       before.plants[0].last_shoot_tip_index);
			assert(world.plants[0].last_root_tip_index ==
			       before.plants[0].last_root_tip_index);
			assert(world.agent_telemetry.decision_count == 0U);
			assert(memcmp(&world.nodes[tip], &before.nodes[tip],
				      sizeof(world.nodes[tip])) == 0);
			if (retry) {
				/* Inject the known next receipt's uptake-equivalent starting
				 * stores; the fixture intentionally has no photosynthesizing
				 * leaves/rain.
				 */
				world.plants[0].stored_energy = 93U;
				world.plants[0].stored_water = 163U;
				world.logic_tick_count = 69899U;
				assert(picosystem_garden_world_step_with_policy(&world, &policy) ==
				       0);
				assert(world.purchase_veto.hits == 2U);
				assert(world.dark_guard.count == 1U &&
				       !world.dark_guard.events[0].denied);
				assert(world.plants[0].stored_energy == 90U &&
				       world.plants[0].stored_water == 161U);
				assert(world.plants[0].random_state ==
				       before.plants[0].random_state);
				assert(memcmp(&world.plants[0].agent_memory,
					      &before.plants[0].agent_memory,
					      sizeof(world.plants[0].agent_memory)) == 0);
				assert(world.plants[0].growth_phase ==
				       before.plants[0].growth_phase);
				assert(world.plants[0].growth_cooldown == 0U);
				assert(world.plants[0].last_shoot_tip_index ==
				       before.plants[0].last_shoot_tip_index);
				assert(world.plants[0].last_root_tip_index ==
				       before.plants[0].last_root_tip_index);
				assert(memcmp(&world.nodes[tip], &before.nodes[tip],
					      sizeof(world.nodes[tip])) == 0);
				world.logic_tick_count = 69914U;
				assert(picosystem_garden_world_step_with_policy(&world, &policy) ==
				       0);
				assert(world.dark_guard.count == 1U &&
				       world.dark_guard.events[0].denied);
				assert(world.dark_guard.events[0].after.supported);
				assert(world.purchase_veto.hits == 2U &&
				       world.agent_telemetry.decision_count == 0U);
			}
			world.logic_tick_count = tick + 3840U - 1U;
			world.ecology_tick_count = (tick + 3840U) / 15U - 1U;
			assert(picosystem_garden_world_step_with_policy(&world, &policy) == 0);
			assert(world.agent_telemetry.decision_count == 1U);
			assert(world.purchase_veto.hits == (retry ? 2U : 1U));
			assert(picosystem_garden_world_reset(&world, 123U) == 0);
			assert(world.purchase_veto.selection == PICOSYSTEM_GARDEN_PURCHASE_NONE &&
			       world.purchase_veto.hits == 0U);
		}
	}
}

int main(void)
{
	receipts();
	retry_receipts();
	transactions();
	puts("Purchase veto: exact receipts, atomic rejection, normal retry, reset and both "
	     "arbitration modes passed");
	return 0;
}
