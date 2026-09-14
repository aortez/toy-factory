/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_agent.h"
#include "garden_leaf_policies.h"
#include "game_snapshot.h"
#include "garden_damage.h"
#include "graphics_raster.h"

static int growth_wait(const struct picosystem_garden_agent_observation *observation,
		       const struct picosystem_garden_agent_memory *memory,
		       struct picosystem_garden_agent_decision *decision, const void *context)
{
	(void)context;
	assert(memory->hidden[0] == 0);
	*decision = (struct picosystem_garden_agent_decision){
		.proposal = {.tip_index = observation->tip_index,
			     .action = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT},
		.next_memory = *memory};
	decision->next_memory.hidden[0] = 2;
	return 0;
}

static void setup(struct picosystem_garden_world *world)
{
	assert(picosystem_garden_world_reset(world, 123U) == 0);
	assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 4U) ==
	       0);
	world->nodes[1].growth_progress = UINT8_MAX;
	world->auto_gardener_enabled = false;
}

static void ecology_step(struct picosystem_garden_world *world,
			 const struct picosystem_garden_agent_policy *policy)
{
	world->logic_tick_count = (world->ecology_tick_count + 1U) * 15U - 1U;
	assert(picosystem_garden_world_step_with_policy(world, policy) == 0);
}

static void test_action(void)
{
	struct picosystem_garden_world world;
	setup(&world);
	world.leaf_condition[1] = 100U;
	world.nodes[1].flags |=
		PICOSYSTEM_GARDEN_NODE_FLOWER | PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED;
	world.plants[0].stored_energy = 9U;
	world.plants[0].stored_water = 5U;
	struct picosystem_garden_world expected = world;
	expected.leaf_condition[1] = UINT8_MAX;
	expected.plants[0].stored_energy = 0U;
	expected.plants[0].stored_water = 0U;
	expected.plants[0].leaf_telemetry.renewals = 1U;
	expected.plants[0].leaf_telemetry.restored = 155U;
	expected.leaf_telemetry = expected.plants[0].leaf_telemetry;
	assert(picosystem_garden_leaf_renew(&world, 0U, 1U) == 0);
	assert(memcmp(&world, &expected, sizeof(world)) == 0);
	assert(picosystem_garden_leaf_renew(&world, 0U, 1U) == -EALREADY);
	assert(memcmp(&world, &expected, sizeof(world)) == 0);
	world.leaf_condition[1] = 0U;
	for (uint16_t energy = 8U; energy <= 9U; ++energy) {
		world.plants[0].stored_energy = energy;
		world.plants[0].stored_water = energy == 8U ? 5U : 4U;
		expected = world;
		assert(picosystem_garden_leaf_renew(&world, 0U, 1U) == -EAGAIN);
		assert(memcmp(&world, &expected, sizeof(world)) == 0);
	}
	assert(picosystem_garden_leaf_renew(&world, 1U, 1U) == -EINVAL);
	assert(picosystem_garden_leaf_renew(&world, 0U, 0U) == -EINVAL);
	assert(picosystem_garden_leaf_renew(&world, 0U, UINT16_MAX) == -EINVAL);
	assert(memcmp(&world, &expected, sizeof(world)) == 0);
	const uint32_t hash = picosystem_garden_world_hash(&world);
	++world.leaf_condition[1];
	assert(hash != picosystem_garden_world_hash(&world));
	--world.leaf_condition[1];
	++world.plants[0].leaf_energy_remainder;
	assert(hash != picosystem_garden_world_hash(&world));
}

static int leaf_bid(const struct picosystem_garden_leaf_observation *observation,
		    const struct picosystem_garden_agent_memory *memory,
		    struct picosystem_garden_leaf_decision *decision, const void *context)
{
	assert(memory->hidden[0] == 0);
	*decision = (struct picosystem_garden_leaf_decision){.node_index = observation->node_index,
							     .next_memory = *memory,
							     .action = *(const uint8_t *)context};
	decision->next_memory.hidden[0] = 1;
	return 0;
}

static void test_scheduling(void)
{
	for (uint8_t action = 0U; action <= 1U; ++action) {
		for (int blocked = 0; blocked < 4; ++blocked) {
			struct picosystem_garden_world world;
			setup(&world);
			world.leaf_condition[1] = 100U;
			if (blocked == 1) { /* Tipless. */
				for (uint16_t i = 0U; i < world.node_count; ++i) {
					world.nodes[i].flags &=
						(uint8_t)~PICOSYSTEM_GARDEN_NODE_TIP;
				}
			} else if (blocked == 2) { /* Full pool, valid non-leaf filler. */
				for (uint16_t i = world.node_count; i < PICOSYSTEM_GARDEN_MAX_NODES;
				     ++i) {
					world.nodes[i] = world.nodes[0];
				}
				world.node_count = PICOSYSTEM_GARDEN_MAX_NODES;
				world.plants[0].node_count = world.node_count;
			} else if (blocked == 3) {
				world.plants[0].growth_cooldown = 2U;
			}
			const struct picosystem_garden_leaf_policy leaf = {.decide = leaf_bid,
									   .context = &action};
			const struct picosystem_garden_agent_policy policy = {
				.decide = growth_wait,
				.leaf_policy = &leaf,
				.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS};
			ecology_step(&world, &policy);
			assert(world.leaf_telemetry.observations == 1U);
			assert(world.leaf_telemetry.renewals == action);
			assert(world.agent_telemetry.decision_count +
				       world.leaf_telemetry.renewals <=
			       1U);
			assert(world.plants[0].agent_memory.hidden[0] ==
			       ((action == 0U && blocked == 0) ? 2 : 1));
			if (blocked == 3) {
				assert(world.plants[0].growth_cooldown == 1U);
			}
		}
	}
	struct picosystem_garden_world world;
	setup(&world);
	world.leaf_condition[1] = 0U;
	world.plants[0].stored_energy = 0U;
	world.plants[0].stored_water = 0U;
	memset(world.moisture, 0, sizeof(world.moisture));
	const uint8_t renew = PICOSYSTEM_GARDEN_LEAF_RENEW;
	const struct picosystem_garden_leaf_policy leaf = {.decide = leaf_bid, .context = &renew};
	const struct picosystem_garden_agent_policy policy = {.decide = growth_wait,
							      .leaf_policy = &leaf};
	ecology_step(&world, &policy);
	assert(world.leaf_telemetry.observations == 1U);
	assert(world.leaf_telemetry.proposals == 1U);
	assert(world.leaf_telemetry.renewals == 0U);
	assert(world.plants[0].agent_memory.hidden[0] == 0);
	assert(world.plants[0].stored_energy == 0U && world.plants[0].stored_water == 0U);
}

static void test_wear_income_and_shade(void)
{
	struct picosystem_garden_world full, empty;
	setup(&full);
	full.nodes[1].y = 80U; /* Leave canopy cells below the leaf for ray attenuation. */
	empty = full;
	empty.leaf_condition[1] = 0U;
	struct picosystem_garden_agent_policy policy = *picosystem_garden_agent_baseline_policy();
	/* Block growth without blocking collection/maintenance. */
	full.plants[0].growth_cooldown = 10U;
	empty.plants[0].growth_cooldown = 10U;
	ecology_step(&full, &policy);
	ecology_step(&empty, &policy);
	bool less_shade = false;
	for (size_t i = 0U; i < sizeof(full.light); ++i) {
		assert(empty.light[i] >= full.light[i]);
		less_shade |= empty.light[i] > full.light[i];
	}
	assert(less_shade);
	assert(full.plants[0].last_energy_income > 0U);
	assert(empty.plants[0].last_energy_income == 0U);
	for (unsigned int condition = 0U; condition <= 255U; ++condition) {
		setup(&full);
		full.ecology_tick_count = 3U;
		full.plants[0].growth_cooldown = 10U;
		full.leaf_condition[1] = (uint8_t)condition;
		full.plants[0].leaf_energy_remainder = 137U;
		ecology_step(&full, &policy);
		const unsigned int worn = condition > 0U ? condition - 1U : 0U;
		assert(full.leaf_condition[1] == worn);
		assert(full.leaf_telemetry.worn == (condition > 0U ? 1U : 0U));
		const unsigned int column = (full.nodes[1].x - 8U) / 8U;
		const unsigned int row = (full.nodes[1].y - 32U) / 8U;
		const unsigned int numerator = (full.light[row * 28U + column] / 64U) * worn + 137U;
		assert(full.plants[0].last_energy_income == numerator / 255U);
		assert(full.plants[0].leaf_energy_remainder == numerator % 255U);
	}
}

static void test_policy_controls(void)
{
	struct picosystem_garden_leaf_observation observation = {.condition = 128U,
								 .light = 255U,
								 .stored_energy = 256U,
								 .stored_water = 512U,
								 .renewal_energy = 9U,
								 .renewal_water = 5U,
								 .maintenance_energy = 5U,
								 .maintenance_water = 3U};
	const struct picosystem_garden_agent_memory memory = {0};
	struct picosystem_garden_leaf_decision decision;
	const char *names[] = {"none", "all", "selective"};
	for (unsigned int mode = 0U; mode < 3U; ++mode) {
		const struct picosystem_garden_leaf_policy *policy =
			toy_factory_garden_leaf_policy(names[mode]);
		observation.light = 255U;
		observation.stored_water = 512U;
		assert(policy->decide(&observation, &memory, &decision, policy->context) == 0);
		assert(decision.action ==
		       (mode == 0U ? PICOSYSTEM_GARDEN_LEAF_WAIT : PICOSYSTEM_GARDEN_LEAF_RENEW));
		observation.light = 0U;
		assert(policy->decide(&observation, &memory, &decision, policy->context) == 0);
		assert(decision.action ==
		       (mode == 1U ? PICOSYSTEM_GARDEN_LEAF_RENEW : PICOSYSTEM_GARDEN_LEAF_WAIT));
		observation.light = 255U;
		observation.stored_water = 5U;
		assert(policy->decide(&observation, &memory, &decision, policy->context) == 0);
		assert(decision.action ==
		       (mode == 1U ? PICOSYSTEM_GARDEN_LEAF_RENEW : PICOSYSTEM_GARDEN_LEAF_WAIT));
		observation.stored_water = 4U;
		assert(policy->decide(&observation, &memory, &decision, policy->context) == 0);
		assert(decision.action == PICOSYSTEM_GARDEN_LEAF_WAIT);
	}
}

static void test_sampling(void)
{
	struct picosystem_garden_world world;
	setup(&world);
	for (uint16_t index = 4U; index < 8U; ++index) {
		world.nodes[index] = world.nodes[1];
		world.nodes[index].flags = PICOSYSTEM_GARDEN_NODE_LEAF;
		world.leaf_condition[index] = 255U;
	}
	world.node_count = 8U;
	world.plants[0].node_count = 8U;
	bool seen[8] = {false};
	for (uint32_t tick = 0U; tick < 5U; ++tick) {
		world.ecology_tick_count = tick;
		const struct picosystem_garden_world before = world;
		struct picosystem_garden_leaf_observation observation;
		assert(picosystem_garden_leaf_observe(&world, 0U, &observation) == 0);
		assert(observation.mature_leaf_count == 5U);
		assert(!seen[observation.node_index]);
		seen[observation.node_index] = true;
		assert(memcmp(&world, &before, sizeof(world)) == 0);
	}
	/* Immature leaves are neither sampled nor worn. */
	for (uint16_t index = 0U; index < world.node_count; ++index) {
		world.nodes[index].growth_progress = 0U;
	}
	world.ecology_tick_count = 3U;
	world.plants[0].growth_cooldown = 10U;
	struct picosystem_garden_leaf_observation observation;
	assert(picosystem_garden_leaf_observe(&world, 0U, &observation) == -ENOENT);
	assert(picosystem_garden_leaf_renew(&world, 0U, 1U) == -EINVAL);
	ecology_step(&world, picosystem_garden_agent_baseline_policy());
	assert(world.leaf_telemetry.worn == 0U);
	assert(world.leaf_condition[1] == 255U);
}

static void test_controlled_payback(void)
{
	/* Short controlled body experiments, not alternative training environments. */
	for (unsigned int environment = 0U; environment < 3U; ++environment) {
		uint16_t energies[3], waters[3];
		uint8_t stresses[3];
		uint32_t renewals[3];
		const char *modes[] = {"none", "all", "selective"};
		for (unsigned int mode = 0U; mode < 3U; ++mode) {
			struct picosystem_garden_world world;
			setup(&world);
			world.nodes[1].y = 80U;
			world.leaf_condition[1] = 100U;
			world.plants[0].stored_water = environment == 2U ? 5U : 256U;
			memset(world.moisture, environment == 2U ? 0 : 32, sizeof(world.moisture));
			for (uint16_t index = 0U; index < world.node_count; ++index) {
				world.nodes[index].flags &= (uint8_t)~PICOSYSTEM_GARDEN_NODE_TIP;
			}
			if (environment == 1U) {
				/* Fixed overhead foliage casts actual ray-solved shade. */
				assert(picosystem_garden_world_plant_seed(
					       &world, PICOSYSTEM_GARDEN_SPECIES_SHRUB, 12U) == 0);
				world.plants[1].growth_cooldown = UINT8_MAX;
				for (uint8_t column = 2U; column <= 6U; ++column) {
					for (uint8_t layer = 0U; layer < 8U; ++layer) {
						const uint16_t index = world.node_count++;
						world.nodes
							[index] = (struct picosystem_garden_node){
							.parent_index = 4U,
							.plant_index = 1U,
							.x = (uint8_t)(12U + column * 8U),
							.y = 48U,
							.growth_progress = UINT8_MAX,
							.depth = 1U,
							.flags = PICOSYSTEM_GARDEN_NODE_LEAF};
						world.leaf_condition[index] = UINT8_MAX;
						++world.plants[1].node_count;
					}
				}
			}
			struct picosystem_garden_agent_policy policy =
				*picosystem_garden_agent_baseline_policy();
			policy.leaf_policy = toy_factory_garden_leaf_policy(modes[mode]);
			for (unsigned int tick = 0U; tick < 8U; ++tick) {
				ecology_step(&world, &policy);
			}
			energies[mode] = world.plants[0].stored_energy;
			waters[mode] = world.plants[0].stored_water;
			stresses[mode] = world.plants[0].stress;
			renewals[mode] = world.plants[0].leaf_telemetry.renewals;
			printf("Controlled case=%u mode=%s energy=%u water=%u stress=%u "
			       "renewals=%u\n",
			       environment, modes[mode], energies[mode], waters[mode],
			       stresses[mode], renewals[mode]);
		}
		assert(renewals[0] == 0U && renewals[1] == 1U);
		if (environment == 0U) {
			assert(renewals[2] == 1U);
			assert(energies[1] > energies[0] && energies[2] == energies[1]);
		} else {
			assert(renewals[2] == 0U);
			if (environment == 1U) {
				assert(energies[0] == energies[2] &&
				       energies[1] + 9U == energies[0]);
			} else {
				assert(waters[0] == waters[2] && waters[1] < waters[0]);
				assert(stresses[1] > stresses[2]);
			}
		}
	}
}

static void test_compaction_and_snapshot(void)
{
	struct picosystem_garden_world world;
	setup(&world);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_SHRUB, 12U) ==
	       0);
	world.leaf_condition[5] = 77U;
	world.plants[1].leaf_energy_remainder = 12U;
	world.nodes[5].growth_progress = UINT8_MAX;
	world.plants[1].growth_cooldown = 10U;
	world.plants[0].flags = PICOSYSTEM_GARDEN_PLANT_DEAD;
	world.plants[0].stress = PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD;
	world.plants[0].stored_energy = 0U;
	world.plants[0].stored_water = 0U;
	world.leaf_condition[1] = 33U;
	for (uint16_t i = 0U; i < 4U; ++i) {
		world.nodes[i].growth_progress = 1U;
		world.nodes[i].flags &= (uint8_t)~PICOSYSTEM_GARDEN_NODE_TIP;
	}
	assert(picosystem_garden_leaf_renew(&world, 0U, 1U) == -EINVAL);
	ecology_step(&world, picosystem_garden_agent_baseline_policy());
	assert(world.plant_count == 1U && world.node_count == 4U);
	assert(world.leaf_condition[1] == 77U);
	for (uint16_t i = 4U; i < PICOSYSTEM_GARDEN_MAX_NODES; ++i) {
		assert(world.leaf_condition[i] == 0U);
	}
	struct picosystem_game_world render_world = {.garden = world,
						     .scene_id = PICOSYSTEM_GAME_SCENE_GARDEN};
	struct picosystem_scene_snapshot before, after;
	assert(picosystem_game_snapshot_build(&render_world, 1U, 0U, 0, &before) == 0);
	assert(before.payload.garden.leaf_condition[1] == 77U);
	render_world.garden.leaf_condition[1] = 255U;
	assert(before.payload.garden.leaf_condition[1] == 77U);
	assert(picosystem_game_snapshot_build(&render_world, 2U, 0U, 0, &after) == 0);
	assert(picosystem_scene_render_full(&before) == 0);
	const uint32_t old_crc = picosystem_graphics_raster_crc32();
	struct picosystem_garden_damage_plan plan;
	struct picosystem_garden_damage_iterator iterator;
	assert(picosystem_garden_damage_plan_build(&before, &after, &plan) == 0);
	assert(picosystem_garden_damage_iterator_init(&iterator) == 0);
	struct picosystem_rect region;
	int next;
	while ((next = picosystem_garden_damage_next_region(&plan, &iterator, &region)) > 0) {
		assert(picosystem_scene_render_region(&after, &region) == 0);
	}
	assert(next == 0);
	const uint32_t partial_crc = picosystem_graphics_raster_crc32();
	assert(partial_crc != old_crc);
	assert(picosystem_scene_render_full(&after) == 0);
	assert(partial_crc == picosystem_graphics_raster_crc32());
	setup(&world);
	assert(world.leaf_condition[1] == 255U);
	assert(world.leaf_telemetry.renewals == 0U);
	assert(world.plants[0].leaf_energy_remainder == 0U);
}

int main(void)
{
	test_action();
	test_scheduling();
	test_wear_income_and_shade();
	test_policy_controls();
	test_sampling();
	test_controlled_payback();
	test_compaction_and_snapshot();
	printf("Leaf tests passed: world=%zu plant=%zu node=%zu snapshot=%zu observation=%zu "
	       "decision=%zu\n",
	       sizeof(struct picosystem_garden_world), sizeof(struct picosystem_garden_plant),
	       sizeof(struct picosystem_garden_node), sizeof(struct picosystem_scene_snapshot),
	       sizeof(struct picosystem_garden_leaf_observation),
	       sizeof(struct picosystem_garden_leaf_decision));
	return 0;
}
