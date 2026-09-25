/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_agent.h"
#include "garden_leaf.h"

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

static int mixed_decide(const struct picosystem_garden_agent_observation *observation,
			const struct picosystem_garden_agent_memory *memory,
			struct picosystem_garden_agent_decision *decision, const void *context)
{
	(void)context;
	const uint8_t action = observation->tip_index == 1U
				       ? PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND
				       : PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP;
	const int err = decide(observation, memory, decision, &action);
	decision->proposal.priority = observation->tip_index == 1U ? 100 : 50;
	return err;
}

/* One small living owner plus non-reclaiming dead filler: isolate global storage. */
static void fixture(struct picosystem_garden_world *world, uint16_t count)
{
	assert(count >= 8U && count <= 512U);
	assert(picosystem_garden_world_reset(world, 123U) == 0);
	assert(!world->full_pool.enabled && world->full_pool.count == 0U);
	world->auto_gardener_enabled = false;
	assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_SHRUB, 4U) == 0);
	assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_SHRUB, 20U) ==
	       0);
	for (uint16_t i = 8U; i < count; ++i) {
		world->nodes[i] = world->nodes[4];
		world->nodes[i].parent_index = 4U;
	}
	world->node_count = count;
	world->plants[1].node_count = (uint16_t)(count - 4U);
	world->plants[1].flags = PICOSYSTEM_GARDEN_PLANT_DEAD;
	world->plants[1].stress = PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD;
	world->plants[1].stored_energy = world->plants[1].stored_water = 0U;
	world->plants[0].stored_energy = 256U;
	world->plants[0].stored_water = 512U;
	world->plants[0].vigor = 0;
	for (uint16_t i = 0U; i < count; ++i) {
		world->nodes[i].flags = 0U;
		world->nodes[i].growth_progress = UINT8_MAX;
		world->leaf_condition[i] = 0U;
	}
	world->nodes[1].flags = PICOSYSTEM_GARDEN_NODE_TIP;
	world->full_pool.enabled = true;
}

static void step_at(struct picosystem_garden_world *world, uint32_t tick,
		    const struct picosystem_garden_agent_policy *policy)
{
	world->logic_tick_count = tick - 1U;
	world->ecology_tick_count = tick / 15U - 1U;
	assert(picosystem_garden_world_step_with_policy(world, policy) == 0);
}

static void private_unchanged(const struct picosystem_garden_plant *a,
			      const struct picosystem_garden_plant *b)
{
	assert(a->random_state == b->random_state && a->growth_phase == b->growth_phase);
	assert(a->growth_cooldown == b->growth_cooldown);
	assert(a->last_shoot_tip_index == b->last_shoot_tip_index);
	assert(a->last_root_tip_index == b->last_root_tip_index);
	assert(memcmp(&a->agent_memory, &b->agent_memory, sizeof(a->agent_memory)) == 0);
	assert(memcmp(&a->agent_telemetry, &b->agent_telemetry, sizeof(a->agent_telemetry)) == 0);
}

static void actions(void)
{
	for (uint8_t arbitration = 0U; arbitration < PICOSYSTEM_GARDEN_AGENT_ARBITRATION_COUNT;
	     ++arbitration) {
		for (uint8_t action = 0U; action < PICOSYSTEM_GARDEN_AGENT_ACTION_COUNT; ++action) {
			struct picosystem_garden_world world, control;
			fixture(&world, 512U);
			control = world;
			control.full_pool.enabled = false;
			assert(picosystem_garden_world_hash(&world) ==
			       picosystem_garden_world_hash(&control));
			const struct picosystem_garden_agent_policy policy = {
				.decide = decide,
				.context = &action,
				.arbitration = arbitration,
			};
			step_at(&world, 69135U, &policy);
			step_at(&control, 69135U, &policy);
			assert(world.node_count == 512U && world.full_pool.count == 1U);
			assert(world.full_pool.evaluated[action] == 1U);
			if (action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND) {
				assert(world.full_pool.denied == 1U &&
				       world.dark_guard.count == 0U);
				private_unchanged(&world.plants[0], &control.plants[0]);
				/* No physical, resource, private or committed telemetry difference.
				 */
				world.full_pool = (struct picosystem_garden_full_pool_audit){0};
				assert(memcmp(&world, &control, sizeof(world)) == 0);
			} else {
				assert(world.full_pool.denied == 0U);
				assert(world.plants[0].agent_memory.hidden[0] == 42);
				assert(world.plants[0].agent_telemetry.decision_count == 1U);
				assert(world.plants[0].random_state !=
				       control.plants[0].random_state);
				const bool finish =
					action == PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP;
				assert(world.plants[0].stored_energy == (finish ? 248U : 256U));
				assert(world.plants[0].stored_water == (finish ? 507U : 512U));
				assert(world.plants[0].growth_cooldown == (finish ? 2U : 0U));
				assert(((world.nodes[1].flags & PICOSYSTEM_GARDEN_NODE_TIP) ==
					0U) == finish);
			}
		}
	}
}

static void boundaries(void)
{
	const uint8_t action = PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND;
	const struct picosystem_garden_agent_policy policy = {.decide = decide, .context = &action};
	struct picosystem_garden_world world, control;
	fixture(&world, 512U);
	control = world;
	control.full_pool.enabled = false;
	step_at(&world, 69120U, &policy);
	step_at(&control, 69120U, &policy);
	world.full_pool.enabled = false;
	assert(memcmp(&world, &control, sizeof(world)) == 0);
	fixture(&world, 511U);
	control = world;
	control.full_pool.enabled = false;
	step_at(&world, 69135U, &policy);
	step_at(&control, 69135U, &policy);
	assert(world.node_count == 512U && world.full_pool.count == 0U);
	world.full_pool.enabled = false;
	assert(memcmp(&world, &control, sizeof(world)) == 0);
	world.node_count = 513U;
	const struct picosystem_garden_world invalid = world;
	assert(picosystem_garden_world_step_with_policy(&world, &policy) == -EINVAL);
	assert(memcmp(&world, &invalid, sizeof(world)) == 0);
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	const struct picosystem_garden_full_pool_audit zero = {0};
	assert(memcmp(&world.full_pool, &zero, sizeof(zero)) == 0);
}

static void precedence_and_guards(void)
{
	const uint8_t finish = PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP;
	struct picosystem_garden_agent_policy policy = {.decide = decide, .context = &finish};
	struct picosystem_garden_world world;
	fixture(&world, 512U);
	world.plants[0].growth_cooldown = 1U;
	step_at(&world, 69135U, &policy);
	assert(world.full_pool.count == 0U && world.plants[0].growth_cooldown == 0U);
	assert(world.plants[0].agent_memory.hidden[0] == 0);
	fixture(&world, 512U);
	world.plants[0].stored_energy = 7U;
	step_at(&world, 69135U, &policy);
	assert(world.full_pool.count == 0U && world.plants[0].agent_telemetry.decision_count == 0U);
	fixture(&world, 512U);
	world.plants[0].stored_energy = 30U;
	const struct picosystem_garden_plant before = world.plants[0];
	step_at(&world, 69915U, &policy); /* phase 117: existing dark guard still refuses. */
	assert(world.full_pool.count == 1U && world.full_pool.denied == 0U);
	assert(world.dark_guard.count == 1U && world.dark_guard.events[0].denied);
	assert(world.plants[0].stored_energy == 30U && world.plants[0].stored_water == 512U);
	private_unchanged(&world.plants[0], &before);
	fixture(&world, 512U);
	world.nodes[1].flags |= PICOSYSTEM_GARDEN_NODE_LEAF;
	const struct picosystem_garden_leaf_policy leaf = {.decide = renew};
	policy.leaf_policy = &leaf;
	step_at(&world, 69135U, &policy);
	assert(world.full_pool.count == 0U && world.leaf_telemetry.renewals == 1U);
	assert(world.plants[0].agent_memory.hidden[0] == 17);
	assert(world.plants[0].agent_telemetry.decision_count == 0U);
	assert(world.plants[0].stored_energy == 247U && world.plants[0].stored_water == 507U);
}

static void exhausted_and_flowering_tips(void)
{
	struct picosystem_garden_world world;
	fixture(&world, 512U);
	world.nodes[1].y = PICOSYSTEM_GARDEN_CANOPY_TOP_PIXELS;
	uint8_t action = PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND;
	const struct picosystem_garden_agent_policy policy = {.decide = decide, .context = &action};
	step_at(&world, 69135U, &policy);
	assert(world.full_pool.evaluated[1] == 1U && world.full_pool.denied == 0U);
	assert(world.plants[0].agent_telemetry.extend_count == 1U);
	assert(world.plants[0].stored_energy == 248U && world.node_count == 512U);
	assert((world.nodes[1].flags & PICOSYSTEM_GARDEN_NODE_TIP) == 0U);
	fixture(&world, 512U);
	world.nodes[1].depth = 10U;
	action = PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP;
	step_at(&world, 69135U, &policy);
	assert(world.node_count == 512U && world.bloom_count == 1U);
	assert((world.nodes[1].flags & PICOSYSTEM_GARDEN_NODE_FLOWER) != 0U);
	assert(world.seed_count == 0U); /* Young body cannot reproduce yet. */
}

static void diagnostic_bounds(void)
{
	struct picosystem_garden_full_pool_audit audit = {.enabled = true};
	const struct picosystem_garden_full_pool_audit before = audit;
	assert(picosystem_garden_full_pool_check(NULL, 1U, 1U, 0U, false) == -EINVAL);
	assert(picosystem_garden_full_pool_check(&audit, 0U, 1U, 0U, false) == -EINVAL);
	assert(picosystem_garden_full_pool_check(&audit, 1U, 512U, 0U, false) == -EINVAL);
	assert(picosystem_garden_full_pool_check(&audit, 1U, 1U, 3U, false) == -EINVAL);
	assert(picosystem_garden_full_pool_check(&audit, 1U, 1U, 2U, true) == -EINVAL);
	assert(memcmp(&audit, &before, sizeof(audit)) == 0);
	for (uint32_t i = 1U; i <= 16U; ++i) {
		assert(picosystem_garden_full_pool_check(&audit, i, 511U, 1U, true) == -ECANCELED);
	}
	assert(audit.count == 16U && audit.denied == 16U && !audit.overflow);
	assert(picosystem_garden_full_pool_check(&audit, 17U, 1U, 0U, false) == -EOVERFLOW);
	assert(audit.count == 16U && audit.evaluated[0] == 0U && audit.overflow);
	assert(picosystem_garden_full_pool_print(&audit, 69135U) == -EOVERFLOW);
	audit = before;
	audit.evaluated[0] = UINT32_MAX;
	assert(picosystem_garden_full_pool_check(&audit, 1U, 1U, 0U, false) == -EOVERFLOW);
	assert(audit.count == 0U && audit.evaluated[0] == UINT32_MAX);
	bool enabled = false;
	assert(picosystem_garden_full_pool_parse(NULL, &enabled) == -EINVAL);
	assert(picosystem_garden_full_pool_parse("nonallocating", NULL) == -EINVAL);
	assert(picosystem_garden_full_pool_parse("other", &enabled) == -EINVAL && !enabled);
	assert(picosystem_garden_full_pool_parse("nonallocating", &enabled) == 0 && enabled);
	assert(picosystem_garden_full_pool_parse("nonallocating", &enabled) == -EINVAL && enabled);
	assert(!picosystem_garden_full_pool_active(true, 69120U));
	assert(picosystem_garden_full_pool_active(true, 69121U));
	assert(!picosystem_garden_full_pool_active(false, UINT32_MAX));
}

static void arbitration_and_birth(void)
{
	struct picosystem_garden_world world;
	fixture(&world, 512U);
	world.nodes[2].flags = PICOSYSTEM_GARDEN_NODE_TIP;
	const struct picosystem_garden_plant before = world.plants[0];
	struct picosystem_garden_agent_policy policy = {
		.decide = mixed_decide,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS,
	};
	step_at(&world, 69135U, &policy);
	assert(world.full_pool.count == 1U && world.full_pool.denied == 1U);
	assert(world.full_pool.events[0].node == 1U);
	assert((world.nodes[2].flags & PICOSYSTEM_GARDEN_NODE_TIP) != 0U);
	private_unchanged(&world.plants[0], &before);
	fixture(&world, 508U);
	world.wet_germination_enabled = true;
	memset(world.moisture, UINT8_MAX, sizeof(world.moisture));
	world.seed_count = 1U;
	world.seeds[0] = (struct picosystem_garden_seed){
		.genome = world.plants[0].genome,
		.parent_lineage_id = 1U,
		.generation = 1U,
		.column = 10U,
		.age_ecology_ticks = 7U,
		.species_id = PICOSYSTEM_GARDEN_SPECIES_SHRUB,
	};
	const uint8_t extend = PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND;
	policy.decide = decide;
	policy.context = &extend;
	step_at(&world, 69135U, &policy);
	assert(world.plant_count == 3U && world.seed_count == 0U && world.node_count == 512U);
	assert(world.full_pool.count == 2U && world.full_pool.denied == 2U);
	assert(world.plants[2].node_count == 4U && world.plants[2].stored_energy == 64U &&
	       world.plants[2].stored_water == 24U);
	assert(world.plants[2].agent_telemetry.decision_count == 0U &&
	       world.plants[2].agent_memory.hidden[0] == 0);
}

int main(void)
{
	_Static_assert(PICOSYSTEM_GARDEN_MAX_NODES == 512U && PICOSYSTEM_GARDEN_MAX_SEEDS == 8U &&
			       PICOSYSTEM_GARDEN_MAX_PLANTS == 16U,
		       "No capacity changes");
	_Static_assert(PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT == 0U &&
			       PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND == 1U &&
			       PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP == 2U,
		       "Diagnostic action order");
	actions();
	boundaries();
	precedence_and_guards();
	exhausted_and_flowering_tips();
	diagnostic_bounds();
	arbitration_and_birth();
	printf("Full-pool transaction/bounds passed; world=%zu audit=%zu bytes\n",
	       sizeof(struct picosystem_garden_world),
	       sizeof(struct picosystem_garden_full_pool_audit));
	return 0;
}
