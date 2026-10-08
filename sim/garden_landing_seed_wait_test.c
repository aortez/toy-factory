/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_growth.h"

#include <assert.h>
#include <errno.h>
#include <string.h>

static void fixture(struct toy_factory_garden_landing_growth_run *run, uint8_t bank, uint32_t tick)
{
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	world.auto_gardener_enabled = false;
	for (uint8_t i = 0U; i < 3U; ++i) {
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
	assert(toy_factory_garden_seed_wait_init(&world, 840U, &run->seed_wait) == 0);
	run->seed_wait.entries[0].since = 180U;
	run->seed_wait.entries[2].since = 120U;
	run->seed_cursor.after = 60U;
	run->seed_cursor.last_buyer = 1U;
	run->base.world.logic_tick_count = tick - 1U;
	run->base.world.ecology_tick_count = (tick - 1U) / PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR;
	run->base.cache.ecology_tick = run->base.world.ecology_tick_count;
	run->base.cache.warmup_samples = (uint16_t)run->base.cache.ecology_tick;
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

static void purchases_and_gates(void)
{
	for (uint8_t bank = 6U; bank <= 8U; ++bank) {
		struct toy_factory_garden_landing_growth_run run;
		fixture(&run, bank, 900U);
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
		const uint32_t order[] = {2U, 3U, 1U};
		const uint32_t old[] = {180U, 0U, 120U};
		for (uint8_t i = 0U; i < 3U; ++i) {
			const struct picosystem_garden_reproduction_visit *const v =
				&reproduction.visits[i];
			assert(v->lineage == order[i]);
			assert(v->produced == (v->blockers == 0U));
			const uint8_t slot = (uint8_t)(v->lineage - 1U);
			assert(run.base.world.plants[slot].stored_energy ==
			       v->energy - (v->produced ? 48U : 0U));
			assert(run.base.world.plants[slot].stored_water ==
			       v->water - (v->produced ? 24U : 0U));
			assert(run.seed_wait.entries[slot].since ==
			       (v->produced ? 900U : old[slot]));
		}
		const struct toy_factory_garden_seed_wait saved = run.seed_wait;
		for (uint8_t i = 0U; i < 14U; ++i) {
			assert(toy_factory_garden_landing_growth_step(&run, &deaths, &seeds,
								      NULL) == 0);
			assert(memcmp(&run.seed_wait, &saved, sizeof(saved)) == 0);
		}
	}
	for (uint8_t reason = 0U; reason < 5U; ++reason) {
		struct toy_factory_garden_landing_growth_run run;
		fixture(&run, 7U, 900U);
		struct picosystem_garden_world *const world = &run.base.world;
		if (reason == 0U) {
			world->plants[1].stored_energy = 0U;
		} else if (reason == 1U) {
			world->plants[1].reproduction_cooldown = 2U;
		} else if (reason == 2U) {
			world->nodes[world->plants[1].base_node_index].flags = 0U;
		} else if (reason == 3U) {
			world->plants[1].stored_water = 0U;
		} else {
			world->plants[1].flags |= PICOSYSTEM_GARDEN_PLANT_DEAD;
			world->plants[1].stress = PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD;
			world->death_count = 1U;
		}
		struct picosystem_garden_death_audit deaths;
		struct picosystem_garden_seed_audit seeds;
		assert(toy_factory_garden_landing_growth_step(&run, &deaths, &seeds, NULL) == 0);
		assert(world->seeds[7].parent_lineage_id == 3U);
		assert(run.seed_wait.entries[1].since == 0U);
		assert(run.seed_wait.entries[2].since == 900U);
	}
}

static void identities_and_births(void)
{
	struct toy_factory_garden_landing_growth_run run;
	fixture(&run, 8U, 900U);
	struct picosystem_garden_world world = run.base.world;
	world.logic_tick_count = 915U;
	world.plants[0].lineage_id = 3U;
	world.plants[1].lineage_id = 9U;
	world.plant_count = 2U;
	uint8_t order[PICOSYSTEM_GARDEN_MAX_PLANTS];
	assert(toy_factory_garden_seed_wait_order(&world, order, sizeof(order), &run.seed_wait) ==
	       0);
	assert(order[0] == 0U && order[1] == 1U);
	struct toy_factory_garden_seed_wait next;
	toy_factory_garden_seed_wait_advance(&run.seed_wait, &world, &next);
	assert(next.count == 2U && next.entries[0].lineage == 3U && next.entries[0].since == 120U);
	assert(next.entries[1].lineage == 9U && next.entries[1].since == 915U);
	assert(next.entries[2].lineage == 0U && next.entries[2].since == 0U);
	assert(toy_factory_garden_seed_wait_validate(&next, &world) == 0);
	next.entries[0].since = 915U;
	assert(toy_factory_garden_seed_wait_order(&world, order, sizeof(order), &next) == 0);
	assert(order[0] == 0U); /* Equal clocks use stable ID, not physical slot. */
	world.plants[0].lineage_id = 9U;
	world.plants[1].lineage_id = 3U;
	assert(toy_factory_garden_seed_wait_order(&world, order, sizeof(order), &next) == 0);
	assert(order[0] == 1U);
	assert(toy_factory_garden_seed_wait_order(&world, order, 1U, &next) == -ERANGE);
	world.plant_count = 0U;
	toy_factory_garden_seed_wait_advance(&next, &world, &run.seed_wait);
	assert(run.seed_wait.count == 0U);
	assert(toy_factory_garden_seed_wait_order(&world, order, sizeof(order), &run.seed_wait) ==
	       0);
}

static void boundaries_and_rollback(void)
{
	for (uint32_t tick = 840U; tick <= 900U; ++tick) {
		struct toy_factory_garden_landing_growth_run run;
		fixture(&run, 7U, tick);
		run.seed_wait.entries[0].since = 0U;
		run.seed_wait.entries[1].since = 120U;
		struct toy_factory_garden_landing_growth_run cursor = run;
		cursor.seed_wait = (struct toy_factory_garden_seed_wait){0};
		struct picosystem_garden_death_audit deaths;
		struct picosystem_garden_seed_audit seeds;
		assert(toy_factory_garden_landing_growth_step(&run, &deaths, &seeds, NULL) == 0);
		assert(toy_factory_garden_landing_growth_step(&cursor, &deaths, &seeds, NULL) == 0);
		if (tick < 900U) {
			assert(memcmp(&run.base, &cursor.base, sizeof(run.base)) == 0);
		} else {
			assert(run.base.world.seeds[7].parent_lineage_id == 1U);
			assert(cursor.base.world.seeds[7].parent_lineage_id == 2U);
		}
	}
	struct toy_factory_garden_landing_growth_run run;
	fixture(&run, 7U, 900U);
	run.base.world.nodes[1].flags = PICOSYSTEM_GARDEN_NODE_TIP;
	const struct toy_factory_garden_landing_growth_run saved = run;
	struct picosystem_garden_death_audit deaths = {0};
	struct picosystem_garden_seed_audit seeds = {0};
	struct picosystem_garden_resource_audit resources = {0};
	struct picosystem_garden_reproduction_audit reproduction = {0};
	const struct toy_factory_garden_growth_observer observer = {
		.observe = observe, .context = &run, .reproduction = &reproduction};
	assert(toy_factory_garden_landing_growth_step_observed(&run, &deaths, &seeds, &resources,
							       &observer) == -EIO);
	assert(memcmp(&run, &saved, sizeof(run)) == 0);
	uint32_t a, b;
	assert(toy_factory_garden_landing_growth_hash(&run, &a) == 0);
	run.seed_wait.entries[0].since += 15U;
	assert(toy_factory_garden_landing_growth_hash(&run, &b) == 0 && a != b);
	for (uint8_t fault = 0U; fault < 5U; ++fault) {
		run = saved;
		if (fault == 0U) {
			run.seed_wait.after = 61U;
		} else if (fault == 1U) {
			run.seed_wait.after = 60U;
		} else if (fault == 2U) {
			run.seed_wait.entries[0].lineage = 2U;
		} else if (fault == 3U) {
			run.seed_wait.entries[0].since = 900U;
		} else {
			run.seed_wait.count = 2U;
		}
		const struct toy_factory_garden_landing_growth_run old = run;
		assert(toy_factory_garden_landing_growth_step(&run, &deaths, &seeds, NULL) ==
		       -ERANGE);
		assert(memcmp(&run, &old, sizeof(run)) == 0);
	}
}

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

static int bad_order(const struct picosystem_garden_world *world, uint8_t *order, size_t capacity,
		     const void *context)
{
	(void)world;
	assert(capacity == PICOSYSTEM_GARDEN_MAX_PLANTS);
	const uint8_t fault = *(const uint8_t *)context;
	if (fault == 3U) {
		return -EIO;
	}
	if (fault == 1U) {
		return 0;
	} /* Unfilled sentinel indices must be rejected. */
	order[0] = fault == 2U ? PICOSYSTEM_GARDEN_MAX_PLANTS : 0U;
	order[1] = 0U;
	order[2] = 2U;
	return 0;
}

static void callback_contract(void)
{
	for (uint8_t fault = 0U; fault < 4U; ++fault) {
		struct toy_factory_garden_landing_growth_run run;
		fixture(&run, 7U, 900U);
		struct picosystem_garden_reproduction_audit audit = {0};
		const struct picosystem_garden_reproduction_audit before = audit;
		const struct picosystem_garden_agent_policy policy = {
			.decide = wait_decide,
			.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS,
			.reproduction_order = bad_order,
			.reproduction_order_context = &fault};
		assert(picosystem_garden_world_step_reproduction_audit(
			       &run.base.world, &policy, &audit) == (fault == 3U ? -EIO : -ERANGE));
		assert(memcmp(&audit, &before, sizeof(audit)) == 0);
	}
	struct toy_factory_garden_landing_growth_run run;
	fixture(&run, 7U, 900U);
	const struct toy_factory_garden_seed_wait before = run.seed_wait;
	assert(toy_factory_garden_seed_wait_init(&run.base.world, 840U, &run.seed_wait) == -ERANGE);
	assert(memcmp(&run.seed_wait, &before, sizeof(before)) == 0);
}

int main(void)
{
	purchases_and_gates();
	identities_and_births();
	boundaries_and_rollback();
	callback_contract();
	return 0;
}
