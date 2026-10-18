/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_growth.h"
#include "garden_landing_ledger.h"

#include <assert.h>
#include <errno.h>
#include <string.h>

static struct toy_factory_garden_landing_ledger history;
static struct toy_factory_garden_lifetimes lives;

static int wait_decide(const struct picosystem_garden_agent_observation *o,
		       const struct picosystem_garden_agent_memory *memory,
		       struct picosystem_garden_agent_decision *decision, const void *context)
{
	(void)context;
	*decision = (struct picosystem_garden_agent_decision){
		.next_memory = *memory,
		.proposal = {.tip_index = o->tip_index,
			     .action = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT}};
	return 0;
}

static struct picosystem_garden_agent_policy policy(void)
{
	static const struct toy_factory_garden_placement_config config = {.version = 1U,
									  .enabled = 1U};
	static const struct toy_factory_garden_placement_context context = {.config = &config};
	return (struct picosystem_garden_agent_policy){
		.decide = wait_decide,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS,
		.place_seed = toy_factory_garden_placement_decide,
		.placement_context = &context,
		.seed_replacement_after = 840U};
}

static void fixture(struct picosystem_garden_world *world)
{
	assert(picosystem_garden_world_reset(world, 123U) == 0);
	world->auto_gardener_enabled = false;
	for (uint8_t i = 0U; i < 3U; ++i) {
		assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_FLOWER,
							  (uint8_t)(10U * i)) == 0);
		world->plants[i].stored_energy = 256U;
		world->plants[i].stored_water = 512U;
		world->plants[i].genome.reserve_strategy = 0;
		world->plants[i].genome.dispersal = 0;
		world->plants[i].reproduction_cooldown = 0U;
	}
	for (uint16_t i = 0U; i < world->node_count; ++i) {
		world->nodes[i].kind = PICOSYSTEM_GARDEN_NODE_STEM;
		world->nodes[i].flags = i == 0U ? PICOSYSTEM_GARDEN_NODE_FLOWER : 0U;
		world->nodes[i].growth_progress = UINT8_MAX;
	}
	world->seed_count = 8U;
	world->seed_creation_count = 8U;
	for (uint8_t i = 0U; i < 8U; ++i) {
		world->seeds[i] = (struct picosystem_garden_seed){
			.parent_lineage_id = (i == 2U || i == 5U) ? 1U : 2U,
			.generation = 1U,
			.column = 0U,
			.age_ecology_ticks = (uint16_t)(10U + i),
			.species_id = PICOSYSTEM_GARDEN_SPECIES_FLOWER};
	}
	world->logic_tick_count = 899U;
	world->ecology_tick_count = 59U;
}

static void swap_and_observer_neutrality(void)
{
	struct picosystem_garden_world world;
	fixture(&world);
	const struct picosystem_garden_world before = world;
	struct picosystem_garden_world plain = world, control = world;
	const struct picosystem_garden_agent_policy enabled = policy();
	struct picosystem_garden_agent_policy disabled = enabled;
	disabled.seed_replacement_after = 0U;
	struct picosystem_garden_seed_audit audit;
	assert(picosystem_garden_world_step_seed_audit(&world, &enabled, &audit) == 0);
	assert(picosystem_garden_world_step_with_policy(&plain, &enabled) == 0);
	assert(picosystem_garden_world_step_with_policy(&control, &disabled) == 0);
	assert(memcmp(&world, &plain, sizeof(world)) == 0);
	assert(audit.count == 8U && audit.replacement_count == 1U);
	assert(audit.replacements[0].previous.parent_lineage_id == 1U);
	assert(audit.replacements[0].previous.age_ecology_ticks == 16U);
	assert(audit.replacements[0].previous.column == 0U);
	assert(world.seed_count == 8U && world.seed_creation_count == 9U);
	assert(world.seed_expiration_count == 0U && world.germination_count == 0U);
	assert(world.seeds[5].age_ecology_ticks == 0U);
	assert(world.seeds[5].column >= 3U && world.seeds[5].column <= 7U);
	assert(world.seeds[5].column == audit.replacements[0].new_column);
	assert(world.plants[0].stored_energy + 48U == control.plants[0].stored_energy);
	assert(world.plants[0].stored_water + 24U == control.plants[0].stored_water);
	assert(world.plants[0].reproduction_cooldown == 16U);
	assert((world.nodes[0].flags & PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED) != 0U);
	for (uint8_t i = 0U; i < 8U; ++i) {
		assert(audit.attempts[i].outcome == PICOSYSTEM_GARDEN_SEED_WAIT);
		if (i != 5U) {
			assert(memcmp(&world.seeds[i], &control.seeds[i], sizeof(world.seeds[i])) ==
			       0);
		}
	}
	uint8_t blockers;
	assert(picosystem_garden_world_seed_germination_blockers(&world, 5U, &blockers) == 0);
	assert((blockers & PICOSYSTEM_GARDEN_SEED_BLOCKED_DORMANT) != 0U);
	assert(PICOSYSTEM_GARDEN_SEED_LIFETIME_TICKS == 8192U);
	/* Reconcile one production exit and one new purchase, without changing the
	 * eight pre-production WAIT observations or inventing an expiry.
	 */
	memset(&history, 0, sizeof(history));
	assert(toy_factory_garden_lifetimes_reset(&lives) == 0);
	for (uint32_t id = 1U; id <= 3U; ++id) {
		assert(toy_factory_garden_lifetimes_birth(&lives, id, 0U, 0U, 0U) == 0);
	}
	history.count = 3U;
	history.seed_count = history.active_count = 8U;
	history.last_tick = 885U;
	for (uint8_t i = 0U; i < 8U; ++i) {
		const struct picosystem_garden_seed *const s = &before.seeds[i];
		history.active[i] = i;
		history.seeds[i] = (struct toy_factory_garden_landing_purchase){
			.parent = s->parent_lineage_id,
			.birth = 885U - (uint32_t)s->age_ecology_ticks * 15U,
			.generation = s->generation,
			.column = s->column,
			.species = s->species_id};
	}
	assert(toy_factory_garden_landing_ledger_step(&history, &world, &lives, &audit) == 0);
	assert(history.seed_count == 9U && history.active_count == 8U);
	assert(history.seeds[5].outcome == PICOSYSTEM_GARDEN_SEED_REPLACED);
	assert(history.seeds[5].end == 900U && history.seeds[5].child == 0U);
	assert(history.seeds[8].birth == 900U && history.seeds[8].parent == 1U);
}

static void gate_and_selection_cases(void)
{
	for (uint8_t failure = 0U; failure < 10U; ++failure) {
		struct picosystem_garden_world world;
		fixture(&world);
		struct picosystem_garden_agent_policy enabled = policy();
		if (failure == 0U) {
			enabled.seed_replacement_after = 900U;
		} else if (failure == 1U) {
			world.plants[0].stored_energy = 0U;
		} else if (failure == 2U) {
			world.plants[0].stored_water = 0U;
			memset(world.moisture, 0, sizeof(world.moisture));
		} else if (failure == 3U) {
			world.plants[0].reproduction_cooldown = 2U;
		} else if (failure == 4U) {
			world.nodes[0].flags = 0U;
		} else if (failure == 5U) {
			for (uint8_t i = 0U; i < world.seed_count; ++i) {
				world.seeds[i].parent_lineage_id = 2U;
			}
		} else if (failure == 6U) {
			for (uint8_t i = 0U; i < world.seed_count; ++i) {
				world.seeds[i].column = 6U;
				world.seeds[i].age_ecology_ticks = 1U;
			}
		} else if (failure == 7U) {
			world.plants[1].base_column = 4U;
			world.plants[2].base_column = 8U;
		} else if (failure == 8U) {
			while (world.node_count < 253U) {
				world.nodes[world.node_count++] = (struct picosystem_garden_node){
					.plant_index = 2U,
					.kind = PICOSYSTEM_GARDEN_NODE_STEM,
					.parent_index = PICOSYSTEM_GARDEN_NODE_NONE};
				++world.plants[2].node_count;
			}
		} else {
			const uint8_t columns[] = {3U, 6U, 13U, 16U, 23U};
			for (size_t i = 0U; i < sizeof(columns); ++i) {
				assert(picosystem_garden_world_plant_seed(
					       &world, PICOSYSTEM_GARDEN_SPECIES_FLOWER,
					       columns[i]) == 0);
			}
		}
		struct picosystem_garden_world control = world;
		struct picosystem_garden_agent_policy disabled = enabled;
		disabled.seed_replacement_after = 0U;
		struct picosystem_garden_seed_audit audit;
		const int err = picosystem_garden_world_step_seed_audit(&world, &enabled, &audit);
		if (err != 0) {
			fprintf(stderr, "replacement gate case %u: %d\n", failure, err);
		}
		assert(err == 0);
		assert(picosystem_garden_world_step_with_policy(&control, &disabled) == 0);
		assert(audit.replacement_count == 0U);
		assert(memcmp(&world, &control, sizeof(world)) == 0);
	}
	struct picosystem_garden_world world;
	fixture(&world);
	world.seeds[2].age_ecology_ticks = world.seeds[5].age_ecology_ticks;
	const struct picosystem_garden_agent_policy enabled = policy();
	assert(picosystem_garden_world_step_with_policy(&world, &enabled) == 0);
	assert(world.seeds[2].age_ecology_ticks == 0U && world.seeds[5].age_ecology_ticks != 0U);
	fixture(&world);
	world.seed_count = 7U;
	world.seed_creation_count = 7U;
	struct picosystem_garden_seed_audit audit;
	assert(picosystem_garden_world_step_seed_audit(&world, &enabled, &audit) == 0);
	assert(audit.replacement_count == 0U && world.seed_count == 8U);
	assert(world.seeds[7].age_ecology_ticks == 0U && world.seeds[5].age_ecology_ticks != 0U);
}

static int invalid_placement(const struct picosystem_garden_seed_placement *o, uint8_t *choice,
			     const void *context)
{
	*choice = UINT8_MAX;
	if (context != NULL) {
		for (uint8_t i = 0U; i < PICOSYSTEM_GARDEN_PLACEMENT_CHOICES; ++i) {
			if ((o->blocked_choices & (uint16_t)(1U << i)) != 0U) {
				*choice = i;
				break;
			}
		}
	}
	return 0;
}

static void invalid_purchase_preserves_seed_and_purchase_rng(bool blocked)
{
	struct picosystem_garden_world world;
	fixture(&world);
	struct picosystem_garden_world control = world;
	struct picosystem_garden_agent_policy enabled = policy(), disabled = enabled;
	enabled.place_seed = invalid_placement;
	enabled.placement_context = blocked ? &world : NULL;
	disabled.seed_replacement_after = 0U;
	assert(picosystem_garden_world_step_with_policy(&control, &disabled) == 0);
	struct picosystem_garden_seed_audit audit, sentinel;
	memset(&sentinel, 0x5a, sizeof(sentinel));
	audit = sentinel;
	assert(picosystem_garden_world_step_seed_audit(&world, &enabled, &audit) == -ERANGE);
	assert(memcmp(&audit, &sentinel, sizeof(audit)) == 0);
	assert(memcmp(world.seeds, control.seeds, sizeof(world.seeds)) == 0);
	assert(world.plants[0].random_state == control.plants[0].random_state);
	assert(world.plants[0].stored_energy == control.plants[0].stored_energy);
	assert(world.plants[0].stored_water == control.plants[0].stored_water);
	assert(world.seed_creation_count == 8U);
}

static void invalid_policy_preserves_world(void)
{
	for (uint8_t failure = 0U; failure < 3U; ++failure) {
		struct picosystem_garden_world world;
		fixture(&world);
		struct picosystem_garden_agent_policy enabled = policy();
		if (failure == 0U) {
			enabled.place_seed = NULL;
		} else if (failure == 1U) {
			enabled.seed_replacement_after = 841U;
		} else {
			world.auto_gardener_enabled = true;
		}
		const struct picosystem_garden_world before = world;
		assert(picosystem_garden_world_step_with_policy(&world, &enabled) == -EINVAL);
		assert(memcmp(&world, &before, sizeof(world)) == 0);
	}
}

int main(void)
{
	swap_and_observer_neutrality();
	gate_and_selection_cases();
	invalid_purchase_preserves_seed_and_purchase_rng(false);
	invalid_purchase_preserves_seed_and_purchase_rng(true);
	invalid_policy_preserves_world();
	return 0;
}
