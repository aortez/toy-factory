/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_growth.h"

#include <assert.h>
#include <errno.h>
#include <string.h>

static void fixture(struct toy_factory_garden_landing_growth_run *run, uint8_t count, uint8_t bank,
		    uint32_t tick)
{
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	world.auto_gardener_enabled = false;
	for (uint8_t i = 0U; i < count; ++i) {
		assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER,
							  (uint8_t)(i * 3U)) == 0);
		world.plants[i].stored_energy = 256U;
		world.plants[i].stored_water = 512U;
		world.plants[i].genome.reserve_strategy = 0;
		world.plants[i].reproduction_cooldown = 0U;
	}
	for (uint16_t i = 0U; i < world.node_count; ++i) {
		world.nodes[i].kind = PICOSYSTEM_GARDEN_NODE_STEM;
		world.nodes[i].flags = i % 4U == 0U ? PICOSYSTEM_GARDEN_NODE_FLOWER : 0U;
		world.nodes[i].growth_progress = UINT8_MAX;
	}
	world.seed_count = bank;
	for (uint8_t i = 0U; i < bank; ++i) {
		world.seeds[i] = (struct picosystem_garden_seed){
			.parent_lineage_id = 1U,
			.generation = 1U,
			.column = 27U,
			.species_id = PICOSYSTEM_GARDEN_SPECIES_FLOWER};
	}
	struct toy_factory_garden_landing_model model;
	const struct toy_factory_garden_landing_feature_config features = {.version = 1U,
									   .mode = 1U};
	assert(toy_factory_garden_landing_model_import(picosystem_garden_neural_reference_model(),
						       &features, &model) == 0);
	assert(toy_factory_garden_landing_placement_init(&world, &model, 1U, 1U, run) == 0);
	run->base.world.logic_tick_count = tick - 1U;
	run->base.world.ecology_tick_count = (tick - 1U) / PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR;
	run->base.cache.ecology_tick = run->base.world.ecology_tick_count;
	run->base.cache.warmup_samples = (uint16_t)run->base.cache.ecology_tick;
	run->seed_cursor.after = 60U;
}

static int observe(const struct picosystem_garden_world *world,
		   const struct picosystem_garden_agent_observation *o,
		   const struct picosystem_garden_agent_decision *raw,
		   const struct picosystem_garden_agent_decision *applied, void *context)
{
	(void)world;
	(void)o;
	(void)raw;
	(void)applied;
	return context == NULL ? 0 : -EIO;
}

static void purchases(void)
{
	for (uint8_t bank = 6U; bank <= 8U; ++bank) {
		struct toy_factory_garden_landing_growth_run run;
		fixture(&run, 3U, bank, 900U);
		run.seed_cursor.last_buyer = 1U;
		struct toy_factory_garden_landing_growth_run plain = run;
		struct picosystem_garden_death_audit deaths;
		struct picosystem_garden_seed_audit seeds;
		struct picosystem_garden_resource_audit resources;
		struct picosystem_garden_reproduction_audit reproduction;
		const struct toy_factory_garden_growth_observer observer = {
			.observe = observe, .reproduction = &reproduction};
		assert(toy_factory_garden_landing_growth_step_observed(&run, &deaths, &seeds,
								       &resources, &observer) == 0);
		assert(toy_factory_garden_landing_growth_step(&plain, &deaths, &seeds, NULL) == 0);
		assert(memcmp(&run, &plain, sizeof(run)) == 0);
		assert(run.seed_cursor.last_buyer == (bank == 8U ? 1U : bank == 7U ? 2U : 3U));
		assert(run.base.world.seed_count == 8U);
		for (uint8_t rank = 0U; rank < 3U; ++rank) {
			const struct picosystem_garden_reproduction_visit *const v =
				&reproduction.visits[rank];
			assert(v->lineage == (uint32_t)((rank + 1U) % 3U) + 1U);
			const struct picosystem_garden_plant *const p =
				&run.base.world.plants[v->lineage - 1U];
			assert(p->stored_energy == v->energy - (v->produced ? 48U : 0U));
			assert(p->stored_water == v->water - (v->produced ? 24U : 0U));
		}
	}
	/* A wraparound batch ends at plant 2, not the greatest buyer ID. */
	struct toy_factory_garden_landing_growth_run run;
	fixture(&run, 3U, 5U, 900U);
	run.seed_cursor.last_buyer = 2U;
	struct picosystem_garden_death_audit deaths;
	struct picosystem_garden_seed_audit seeds;
	assert(toy_factory_garden_landing_growth_step(&run, &deaths, &seeds, NULL) == 0);
	assert(run.base.world.seeds[5].parent_lineage_id == 3U);
	assert(run.base.world.seeds[6].parent_lineage_id == 1U);
	assert(run.base.world.seeds[7].parent_lineage_id == 2U);
	assert(run.seed_cursor.last_buyer == 2U);
}

static void eligibility_and_stable_ids(void)
{
	for (uint8_t reason = 0U; reason < 4U; ++reason) {
		struct toy_factory_garden_landing_growth_run run;
		fixture(&run, 3U, 7U, 900U);
		run.seed_cursor.last_buyer = 1U;
		struct picosystem_garden_world *const world = &run.base.world;
		if (reason == 0U) {
			world->plants[1].stored_energy = 0U;
		} else if (reason == 1U) {
			world->plants[1].reproduction_cooldown = 2U;
		} else if (reason == 2U) {
			world->nodes[world->plants[1].base_node_index].flags = 0U;
		} else {
			world->plants[1].flags |= PICOSYSTEM_GARDEN_PLANT_DEAD;
			world->plants[1].stress = PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD;
			world->death_count = 1U;
		}
		struct picosystem_garden_death_audit deaths;
		struct picosystem_garden_seed_audit seeds;
		assert(toy_factory_garden_landing_growth_step(&run, &deaths, &seeds, NULL) == 0);
		assert(run.seed_cursor.last_buyer == 3U && world->seeds[7].parent_lineage_id == 3U);
	}
	for (uint32_t last = 2U; last <= 8U; last += 6U) {
		struct toy_factory_garden_landing_growth_run run;
		fixture(&run, 3U, 7U, 900U);
		run.base.world.plants[0].lineage_id = 1U;
		run.base.world.plants[1].lineage_id = 3U;
		run.base.world.plants[2].lineage_id = 8U;
		run.base.world.lineage_sequence = 8U;
		run.seed_cursor.last_buyer = last;
		struct picosystem_garden_death_audit deaths;
		struct picosystem_garden_seed_audit seeds;
		assert(toy_factory_garden_landing_growth_step(&run, &deaths, &seeds, NULL) == 0);
		assert(run.seed_cursor.last_buyer == (last == 2U ? 3U : 1U));
	}
}

static void boundaries_and_failures(void)
{
	for (uint32_t tick = 840U; tick <= 900U; ++tick) {
		struct toy_factory_garden_landing_growth_run run;
		fixture(&run, 3U, 7U, tick);
		run.seed_cursor.after = 840U;
		struct toy_factory_garden_landing_growth_run fixed = run;
		fixed.seed_cursor.after = 0U;
		struct picosystem_garden_death_audit deaths;
		struct picosystem_garden_seed_audit seeds;
		assert(toy_factory_garden_landing_growth_step(&run, &deaths, &seeds, NULL) == 0);
		assert(toy_factory_garden_landing_growth_step(&fixed, &deaths, &seeds, NULL) == 0);
		assert(memcmp(&run.base, &fixed.base, sizeof(run.base)) == 0);
		assert(run.seed_cursor.last_buyer == (tick == 900U ? 1U : 0U));
	}
	struct toy_factory_garden_landing_growth_run empty;
	fixture(&empty, 0U, 0U, 900U);
	struct picosystem_garden_death_audit deaths;
	struct picosystem_garden_seed_audit seeds;
	assert(toy_factory_garden_landing_growth_step(&empty, &deaths, &seeds, NULL) == 0);
	assert(empty.seed_cursor.last_buyer == 0U);
	for (uint8_t problem = 0U; problem < 6U; ++problem) {
		struct toy_factory_garden_landing_growth_run run;
		fixture(&run, 3U, 7U, 900U);
		if (problem == 0U) {
			run.seed_cursor.after = 61U;
		} else if (problem == 1U) {
			run.seed_order_after = 60U;
		} else if (problem == 2U) {
			run.placement.replace_after = 60U;
		} else if (problem == 3U) {
			run.seed_cursor.last_buyer = 4U;
		} else if (problem == 4U) {
			run.seed_cursor.after = 900U;
			run.seed_cursor.last_buyer = 1U;
		} else {
			run.seed_cursor.after = 0U;
			run.seed_cursor.last_buyer = 1U;
		}
		const struct toy_factory_garden_landing_growth_run saved = run;
		const struct picosystem_garden_death_audit old_deaths = deaths;
		const struct picosystem_garden_seed_audit old_seeds = seeds;
		uint32_t hash = 123U;
		assert(toy_factory_garden_landing_growth_hash(&run, &hash) == -ERANGE &&
		       hash == 123U);
		assert(toy_factory_garden_landing_growth_step(&run, &deaths, &seeds, NULL) ==
		       -ERANGE);
		assert(memcmp(&run, &saved, sizeof(run)) == 0);
		assert(memcmp(&deaths, &old_deaths, sizeof(deaths)) == 0);
		assert(memcmp(&seeds, &old_seeds, sizeof(seeds)) == 0);
	}
	struct toy_factory_garden_landing_growth_run run;
	fixture(&run, 3U, 7U, 900U);
	run.base.world.nodes[1].flags = PICOSYSTEM_GARDEN_NODE_TIP;
	const struct toy_factory_garden_landing_growth_run saved = run;
	struct picosystem_garden_resource_audit resources;
	struct picosystem_garden_reproduction_audit reproduction;
	memset(&resources, 0x51, sizeof(resources));
	memset(&reproduction, 0x52, sizeof(reproduction));
	const struct picosystem_garden_resource_audit old_resources = resources;
	const struct picosystem_garden_reproduction_audit old_reproduction = reproduction;
	const struct toy_factory_garden_growth_observer observer = {
		.observe = observe, .context = &run, .reproduction = &reproduction};
	assert(toy_factory_garden_landing_growth_step_observed(&run, &deaths, &seeds, &resources,
							       &observer) == -EIO);
	assert(memcmp(&run, &saved, sizeof(run)) == 0);
	assert(memcmp(&resources, &old_resources, sizeof(resources)) == 0);
	assert(memcmp(&reproduction, &old_reproduction, sizeof(reproduction)) == 0);
	uint32_t a, b;
	assert(toy_factory_garden_landing_growth_hash(&run, &a) == 0);
	run.seed_cursor.last_buyer = 1U;
	assert(toy_factory_garden_landing_growth_hash(&run, &b) == 0 && a != b);
	run.seed_cursor = (struct toy_factory_garden_seed_cursor){0};
	assert(toy_factory_garden_landing_growth_hash(&run, &b) == 0 && a != b);
}

int main(void)
{
	purchases();
	eligibility_and_stable_ids();
	boundaries_and_failures();
	return 0;
}
