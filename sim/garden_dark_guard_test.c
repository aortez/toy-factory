/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_agent.h"
#include "garden_leaf.h"

#if defined(TOY_FACTORY_GARDEN_DARK_GUARD)
static const bool guarded = true;
#else
static const bool guarded = false;
#endif

static int decide(const struct picosystem_garden_agent_observation *observation,
		  const struct picosystem_garden_agent_memory *memory,
		  struct picosystem_garden_agent_decision *decision, const void *context)
{
	const uint8_t action = *(const uint8_t *)context;
	*decision = (struct picosystem_garden_agent_decision){
		.next_memory = *memory,
		.proposal = {.tip_index = observation->tip_index, .action = action},
	};
	decision->next_memory.hidden[0] = 42;
	if (action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND) {
		decision->proposal.candidate_count = observation->candidate_count;
		for (uint8_t i = 0U; i < observation->candidate_count; ++i) {
			decision->proposal.candidate_order[i] = i;
		}
	}
	return 0;
}

static int renew(const struct picosystem_garden_leaf_observation *observation,
		 const struct picosystem_garden_agent_memory *memory,
		 struct picosystem_garden_leaf_decision *decision, const void *context)
{
	(void)context;
	*decision = (struct picosystem_garden_leaf_decision){
		.node_index = observation->node_index,
		.action = PICOSYSTEM_GARDEN_LEAF_RENEW,
		.next_memory = *memory,
	};
	decision->next_memory.hidden[0] = 17;
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

static void growth_transaction(void)
{
	for (uint8_t arbitration = 0U; arbitration < PICOSYSTEM_GARDEN_AGENT_ARBITRATION_COUNT;
	     ++arbitration) {
		for (uint8_t action = PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND;
		     action <= PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP; ++action) {
			struct picosystem_garden_world world;
			fixture(&world, 56U,
				action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND ? 246U : 210U);
			const struct picosystem_garden_world before = world;
			const struct picosystem_garden_agent_policy policy = {
				.decide = decide,
				.context = &action,
				.arbitration = arbitration,
			};
			step_at(&world, 4635U, &policy);
			if (guarded) {
				assert(world.plants[0].stored_energy ==
				       before.plants[0].stored_energy);
				assert(world.plants[0].stored_water ==
				       before.plants[0].stored_water);
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
				assert(world.agent_telemetry.decision_count == 0U);
				assert(memcmp(world.nodes, before.nodes, sizeof(world.nodes)) == 0);
			} else {
				assert(world.plants[0].stored_energy ==
				       before.plants[0].stored_energy - 8U);
				assert(world.plants[0].agent_memory.hidden[0] == 42);
				assert(world.agent_telemetry.decision_count == 1U);
			}
#if defined(TOY_FACTORY_GARDEN_DARK_GUARD)
			assert(world.dark_guard.count == 1U && world.dark_guard.events[0].denied);
			const uint16_t added =
				action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND ? 1U : 0U;
			assert(world.dark_guard.events[0].nodes_after == 56U + added);
			assert(world.dark_guard.events[0].before.death_step == 0U);
			/* Retry can proceed once there is possible income, without changing the
			 * model. */
			step_at(&world, 6885U, &policy);
			assert(world.agent_telemetry.decision_count == 1U);
			assert(!world.dark_guard.events[0].after.supported &&
			       !world.dark_guard.events[0].denied);
#endif
		}
	}
}

static void blocked_extension(void)
{
	struct picosystem_garden_world world;
	fixture(&world, 56U, 246U);
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
	step_at(&world, 4635U, &policy);
	assert(world.node_count == 56U && world.plants[0].stored_energy == 238U);
	assert((world.nodes[1].flags & PICOSYSTEM_GARDEN_NODE_TIP) == 0U);
#if defined(TOY_FACTORY_GARDEN_DARK_GUARD)
	assert(world.dark_guard.count == 1U && world.dark_guard.events[0].nodes_after == 56U);
	assert(!world.dark_guard.events[0].denied && world.dark_guard.events[0].after.stress == 3U);
#endif
}

static void renewal_and_growth_fallback(void)
{
	struct picosystem_garden_world world;
	fixture(&world, 55U, 216U);
	world.logic_tick_count = 4635U;
	world.ecology_tick_count = 309U;
	const struct picosystem_garden_world before = world;
	const int err = picosystem_garden_leaf_renew(&world, 0U, 1U);
	assert(err == (guarded ? -EAGAIN : 0));
	assert(world.leaf_condition[1] == (guarded ? 0U : UINT8_MAX));
	assert(world.plants[0].stored_energy == (guarded ? 216U : 207U));
	assert(world.plants[0].stored_water == (guarded ? 512U : 507U));
	assert(world.plants[0].random_state == before.plants[0].random_state);
	assert(memcmp(&world.plants[0].agent_memory, &before.plants[0].agent_memory,
		      sizeof(world.plants[0].agent_memory)) == 0);
	/* A denied renewal must not commit its memory or consume the growth slot. */
	fixture(&world, 55U, 256U);
	const uint8_t wait = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT;
	const struct picosystem_garden_leaf_policy leaf = {.decide = renew};
	const struct picosystem_garden_agent_policy policy = {
		.decide = decide, .context = &wait, .leaf_policy = &leaf};
	world.plants[0].stored_energy = 216U;
	step_at(&world, 4635U, &policy);
	assert(world.leaf_telemetry.proposals == 1U);
	assert(world.leaf_telemetry.renewals == (guarded ? 0U : 1U));
	assert(world.plants[0].agent_memory.hidden[0] == (guarded ? 42 : 17));
	assert(world.agent_telemetry.wait_count == (guarded ? 1U : 0U));
#if defined(TOY_FACTORY_GARDEN_DARK_GUARD)
	/* Diagnostics never alter the authoritative hash; bounded overflow fails closed. */
	const uint32_t hash = picosystem_garden_world_hash(&world);
	world.dark_guard.count = PICOSYSTEM_GARDEN_DARK_EVENTS;
	assert(picosystem_garden_world_hash(&world) == hash);
	assert(picosystem_garden_leaf_renew(&world, 0U, 1U) == -EAGAIN);
	assert(world.dark_guard.overflow && picosystem_garden_world_hash(&world) == hash);
#endif
}

static void seeds_and_same_step_order(void)
{
	for (uint16_t count = 48U; count <= 56U; count += 8U) {
		struct picosystem_garden_world world;
		fixture(&world, count, 256U);
		world.nodes[0].flags = PICOSYSTEM_GARDEN_NODE_FLOWER;
		world.nodes[1].flags &= (uint8_t)~PICOSYSTEM_GARDEN_NODE_TIP;
		const uint8_t wait = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT;
		const struct picosystem_garden_agent_policy policy = {.decide = decide,
								      .context = &wait};
		const uint32_t random = world.plants[0].random_state;
		step_at(&world, 4680U, &policy);
		const bool allowed = !guarded || count == 48U;
		assert(world.seed_count == (allowed ? 1U : 0U));
		assert(world.seed_creation_count == world.seed_count);
		assert((world.plants[0].random_state != random) == allowed);
		assert(world.plants[0].stored_energy ==
		       256U - (count + 7U) / 8U - (allowed ? 48U : 0U));
		assert(world.plants[0].reproduction_cooldown == (allowed ? 16U : 0U));
		assert(((world.nodes[0].flags & PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED) != 0U) ==
		       allowed);
#if defined(TOY_FACTORY_GARDEN_DARK_GUARD)
		assert(world.dark_guard.count == 1U &&
		       world.dark_guard.events[0].denied == !allowed);
#endif
	}
	struct picosystem_garden_world world;
	fixture(&world, 48U, 256U);
	world.plants[0].genome.reserve_strategy = -2;
	world.nodes[0].flags = PICOSYSTEM_GARDEN_NODE_FLOWER;
	const uint8_t finish = PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP;
	const struct picosystem_garden_agent_policy policy = {.decide = decide, .context = &finish};
	step_at(&world, 4680U, &policy);
	assert(world.agent_telemetry.finish_count == 1U);
	assert(world.plants[0].stored_energy == 194U && world.seed_count == 1U);
#if defined(TOY_FACTORY_GARDEN_DARK_GUARD)
	assert(world.dark_guard.count == 2U);
	assert(world.dark_guard.events[0].kind == PICOSYSTEM_GARDEN_EXPENSE_GROWTH);
	assert(world.dark_guard.events[1].kind == PICOSYSTEM_GARDEN_EXPENSE_SEED);
	assert(world.dark_guard.events[1].energy == 242U && !world.dark_guard.events[1].denied);
#endif
}

#if defined(TOY_FACTORY_GARDEN_DARK_GUARD)
static void forecast_tests(bool print_reference)
{
	const uint16_t energies[] = {0U, 208U, 256U};
	const uint16_t nodes[] = {1U, 8U, 55U, 512U};
	for (uint16_t phase = 0U; phase < 256U; ++phase) {
		for (size_t e = 0U; e < sizeof(energies) / sizeof(energies[0]); ++e) {
			for (size_t n = 0U; n < sizeof(nodes) / sizeof(nodes[0]); ++n) {
				for (uint8_t stress = 0U; stress <= 7U; stress += 7U) {
					struct picosystem_garden_dark_budget f;
					assert(picosystem_garden_dark_project(
						       energies[e], nodes[n], stress,
						       (uint8_t)phase, &f) == 0);
					assert(f.supported == ((phase >= 117U) || (phase < 10U)));
					assert(f.dark_steps <= 149U && f.payments <= 37U);
					if (print_reference) {
						printf("%u %u %u %u %u %u %u %u %u %u %u %u %u\n",
						       phase, energies[e], nodes[n], stress,
						       f.supported, f.energy, f.stress,
						       f.peak_stress, f.upkeep, f.dark_steps,
						       f.payments, f.first_shortage_step,
						       f.death_step);
					}
				}
			}
		}
	}
	struct picosystem_garden_dark_budget f = {.energy = 123U};
	const struct picosystem_garden_dark_budget before = f;
	assert(picosystem_garden_dark_project(257U, 8U, 0U, 117U, &f) == -EINVAL);
	assert(picosystem_garden_dark_project(0U, 0U, 0U, 117U, &f) == -EINVAL);
	assert(picosystem_garden_dark_project(0U, 513U, 0U, 117U, &f) == -EINVAL);
	assert(picosystem_garden_dark_project(0U, 8U, 8U, 117U, &f) == -EINVAL);
	assert(picosystem_garden_dark_project(0U, 8U, 0U, 117U, NULL) == -EINVAL);
	assert(memcmp(&before, &f, sizeof(f)) == 0);
}
#endif

int main(int argc, char **argv)
{
#if defined(TOY_FACTORY_GARDEN_DARK_GUARD)
	const bool reference = argc == 2 && strcmp(argv[1], "--reference") == 0;
	forecast_tests(reference);
	if (reference) {
		return 0;
	}
#else
	(void)argc;
	(void)argv;
#endif
	growth_transaction();
	blocked_extension();
	renewal_and_growth_fallback();
	seeds_and_same_step_order();
	puts("Dark guard forecast, atomic rejection, retries and native expense ordering passed");
	return 0;
}
