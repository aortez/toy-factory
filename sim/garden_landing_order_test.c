/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_growth.h"
#include "garden_evaluation.h"

#include <assert.h>
#include <errno.h>
#include <string.h>

static int wait_decide(const struct picosystem_garden_agent_observation *o,
		       const struct picosystem_garden_agent_memory *memory,
		       struct picosystem_garden_agent_decision *d, const void *context)
{
	(void)context;
	*d = (struct picosystem_garden_agent_decision){
		.next_memory = *memory,
		.proposal = {.tip_index = o->tip_index,
			     .action = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT}};
	return 0;
}

static void fixture(struct picosystem_garden_world *world, uint8_t count, uint8_t bank,
		    uint32_t tick)
{
	assert(picosystem_garden_world_reset(world, 123U) == 0);
	world->auto_gardener_enabled = false;
	for (uint8_t i = 0U; i < count; ++i) {
		assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_FLOWER,
							  (uint8_t)(i * 3U)) == 0);
		world->plants[i].stored_energy = 256U;
		world->plants[i].stored_water = 512U;
		world->plants[i].genome.reserve_strategy = 0;
		world->plants[i].reproduction_cooldown = 0U;
	}
	for (uint16_t i = 0U; i < world->node_count; ++i) {
		world->nodes[i].kind = PICOSYSTEM_GARDEN_NODE_STEM;
		world->nodes[i].flags = i % 4U == 0U ? PICOSYSTEM_GARDEN_NODE_FLOWER : 0U;
		world->nodes[i].growth_progress = UINT8_MAX;
	}
	world->seed_count = bank;
	for (uint8_t i = 0U; i < bank; ++i) {
		world->seeds[i] = (struct picosystem_garden_seed){
			.parent_lineage_id = 1U,
			.generation = 1U,
			.column = 27U,
			.species_id = PICOSYSTEM_GARDEN_SPECIES_FLOWER};
	}
	world->logic_tick_count = tick - 1U;
	world->ecology_tick_count = tick / 15U - 1U;
}

static void traversal(void)
{
	const struct picosystem_garden_agent_policy policy = {
		.decide = wait_decide,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS,
		.reproduction_rotation_after = 840U};
	for (uint8_t count = 0U; count <= PICOSYSTEM_GARDEN_MAX_PLANTS; ++count) {
		for (uint32_t tick = 780U; tick <= 1440U; tick += 15U) {
			struct picosystem_garden_world world;
			fixture(&world, count, 0U, tick);
			struct picosystem_garden_world plain = world;
			struct picosystem_garden_reproduction_audit audit;
			assert(picosystem_garden_world_step_reproduction_audit(&world, &policy,
									       &audit) == 0);
			assert(picosystem_garden_world_step_with_policy(&plain, &policy) == 0);
			assert(memcmp(&plain, &world, sizeof(world)) == 0);
			assert(audit.count == count);
			const uint8_t start = (uint8_t)((count && tick > 840U && tick % 60U == 0U)
								? ((tick - 840U) / 60U) % count
								: 0U);
			for (uint8_t rank = 0U; rank < count; ++rank) {
				const uint8_t slot = (uint8_t)((start + rank) % count);
				assert(world.plants[rank].lineage_id == rank + 1U);
				assert(audit.visits[rank].lineage == world.plants[slot].lineage_id);
				assert(audit.visits[rank].produced ==
				       (audit.visits[rank].blockers == 0U));
			}
		}
	}
}

static void purchases(void)
{
	const struct picosystem_garden_agent_policy fixed = {
		.decide = wait_decide, .arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS};
	struct picosystem_garden_agent_policy rotated = fixed;
	rotated.reproduction_rotation_after = 840U;
	for (uint8_t bank = 6U; bank <= 8U; ++bank) {
		struct picosystem_garden_world a, b;
		fixture(&a, 3U, bank, 900U);
		b = a;
		struct picosystem_garden_reproduction_audit audit;
		assert(picosystem_garden_world_step_with_policy(&a, &fixed) == 0);
		assert(picosystem_garden_world_step_reproduction_audit(&b, &rotated, &audit) == 0);
		assert(a.seed_count == 8U && b.seed_count == 8U);
		for (uint8_t i = bank; i < 8U; ++i) {
			assert(a.seeds[i].parent_lineage_id == (uint32_t)(i - bank + 1U));
			assert(b.seeds[i].parent_lineage_id == (uint32_t)(i - bank + 2U));
		}
		for (uint8_t rank = 0U; rank < 3U; ++rank) {
			const struct picosystem_garden_reproduction_visit *const v =
				&audit.visits[rank];
			const struct picosystem_garden_plant *const p = &b.plants[v->lineage - 1U];
			assert(p->stored_energy == v->energy - (v->produced ? 48U : 0U));
			assert(p->stored_water == v->water - (v->produced ? 24U : 0U));
			assert(p->reproduction_cooldown == (v->produced ? 16U : 0U));
		}
	}
	for (uint8_t failure = 0U; failure < 4U; ++failure) {
		struct picosystem_garden_world world;
		fixture(&world, 3U, 7U, 900U);
		if (failure == 0U) {
			world.plants[1].stored_energy = 0U;
		} else if (failure == 1U) {
			world.plants[1].reproduction_cooldown = 2U;
		} else if (failure == 2U) {
			world.nodes[world.plants[1].base_node_index].flags = 0U;
		} else {
			world.plants[1].flags |= PICOSYSTEM_GARDEN_PLANT_DEAD;
			world.plants[1].stress = PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD;
			world.death_count = 1U;
		}
		assert(picosystem_garden_world_step_with_policy(&world, &rotated) == 0);
		assert(world.seeds[7].parent_lineage_id == 3U);
		if (failure == 1U) {
			assert(world.plants[1].reproduction_cooldown == 1U);
		}
	}
}

static void run_contract(void)
{
	struct picosystem_garden_world world;
	assert(toy_factory_garden_evaluation_reset(&world, &toy_factory_garden_rainfed_scenarios[1],
						   0x940cfdc4U) == 0);
	struct toy_factory_garden_landing_model model;
	const struct toy_factory_garden_landing_feature_config features = {.version = 1U,
									   .mode = 1U};
	assert(toy_factory_garden_landing_model_import(picosystem_garden_neural_reference_model(),
						       &features, &model) == 0);
	struct toy_factory_garden_landing_growth_run fixed, rotated;
	assert(toy_factory_garden_landing_placement_init(&world, &model, 1U, 1U, &fixed) == 0);
	rotated = fixed;
	rotated.seed_order_after = 3840U;
	uint32_t a, b;
	assert(toy_factory_garden_landing_growth_hash(&fixed, &a) == 0);
	assert(toy_factory_garden_landing_growth_hash(&rotated, &b) == 0 && a != b);
	struct picosystem_garden_death_audit deaths;
	struct picosystem_garden_seed_audit seeds;
	for (uint32_t i = 0U; i < 3840U; ++i) {
		assert(toy_factory_garden_landing_growth_step(&fixed, &deaths, &seeds, NULL) == 0);
		assert(toy_factory_garden_landing_growth_step(&rotated, &deaths, &seeds, NULL) ==
		       0);
		assert(memcmp(&fixed.base, &rotated.base, sizeof(fixed.base)) == 0);
	}
	rotated.seed_order_after = 61U;
	const struct toy_factory_garden_landing_growth_run saved = rotated;
	const struct picosystem_garden_death_audit saved_deaths = deaths;
	const struct picosystem_garden_seed_audit saved_seeds = seeds;
	b = 123U;
	assert(toy_factory_garden_landing_growth_hash(&rotated, &b) == -ERANGE && b == 123U);
	assert(toy_factory_garden_landing_growth_step(&rotated, &deaths, &seeds, NULL) == -ERANGE);
	assert(memcmp(&rotated, &saved, sizeof(saved)) == 0);
	assert(memcmp(&deaths, &saved_deaths, sizeof(deaths)) == 0);
	assert(memcmp(&seeds, &saved_seeds, sizeof(seeds)) == 0);
	rotated.seed_order_after = 60U;
	rotated.placement = (struct toy_factory_garden_placement_config){0};
	assert(toy_factory_garden_landing_growth_hash(&rotated, &b) == -ERANGE);
}

int main(void)
{
	traversal();
	purchases();
	run_contract();
	return 0;
}
