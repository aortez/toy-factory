/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_growth.h"
#include "garden_dispersal.h"
#include "garden_evaluation.h"

#include <assert.h>
#include <errno.h>
#include <string.h>

static void mapping(void)
{
	for (uint8_t origin = 0U; origin < 28U; ++origin) {
		for (int8_t trait = -2; trait <= 2; ++trait) {
			struct picosystem_garden_seed_placement o = {
				.parent = 1U, .origin = origin, .dispersal = trait};
			for (uint8_t c = 0U; c < 6U; ++c) {
				o.columns[c] = picosystem_garden_dispersed_column(origin, trait, c);
			}
			for (uint8_t mask = 0U; mask < 64U; ++mask) {
				o.blocked_choices = mask;
				bool consistent = true;
				uint8_t clear[6], count = 0U;
				for (uint8_t c = 0U; c < 6U; ++c) {
					for (uint8_t j = 0U; j < c; ++j) {
						if (o.columns[j] == o.columns[c]) {
							consistent &=
								(((uint32_t)mask >> j) & 1U) ==
								(((uint32_t)mask >> c) & 1U);
						}
					}
					if ((mask & (1U << c)) == 0U) {
						clear[count++] = c;
					}
				}
				for (uint32_t r = 0U; r <= 42U; ++r) {
					o.random = r == 42U ? UINT32_MAX : r;
					const struct picosystem_garden_seed_placement before = o;
					uint8_t selected = 99U;
					const int err = toy_factory_garden_placement_choose(
						&o, 1U, &selected);
					assert(memcmp(&o, &before, sizeof(o)) == 0);
					if (!consistent) {
						assert(err == -ERANGE && selected == 99U);
						continue;
					}
					assert(err == 0);
					const uint8_t original = (uint8_t)(o.random % 6U);
					assert(o.columns[original] ==
					       picosystem_garden_dispersed_column(origin, trait,
										  o.random));
					assert(selected == ((count && (mask & (1U << original)))
								    ? clear[(o.random / 6U) % count]
								    : original));
					assert(toy_factory_garden_placement_choose(
						       &o, 0U, &selected) == 0 &&
					       selected == original);
				}
			}
		}
	}
	uint8_t out = 99U;
	struct picosystem_garden_seed_placement o = {0};
	assert(toy_factory_garden_placement_choose(NULL, 0U, &out) == -EINVAL);
	assert(toy_factory_garden_placement_choose(&o, 0U, NULL) == -EINVAL);
	assert(toy_factory_garden_placement_choose(&o, 2U, &out) == -ERANGE && out == 99U);
}

static uint8_t reference_column(uint8_t origin, int8_t trait, uint32_t random, bool wide)
{
	const int32_t distance =
		(wide ? 3 : 5) + trait + (int32_t)((random / 2U) % (wide ? 7U : 3U));
	const int32_t offset = (random % 2U) ? distance : -distance;
	int32_t column = origin + offset;
	if ((column < 0) || (column > 27)) {
		column = origin - offset;
	}
	return (uint8_t)(column < 0 ? 0 : column > 27 ? 27 : column);
}

static void timed_mapping(void)
{
	const uint32_t ticks[] = {0U, 626580U, 626581U, 626595U, UINT32_MAX};
	for (size_t t = 0U; t < sizeof(ticks) / sizeof(ticks[0]); ++t) {
		bool wide = false;
#if defined(TOY_FACTORY_GARDEN_LATE_DISPERSAL)
		wide = ticks[t] > 626580U;
#endif
		const uint8_t choices = wide ? 14U : 6U;
		assert(picosystem_garden_dispersal_choices_at(ticks[t]) == choices);
		for (uint8_t origin = 0U; origin < 28U; ++origin) {
			for (int8_t trait = -2; trait <= 2; ++trait) {
				struct picosystem_garden_seed_placement o = {.parent = 1U,
									     .origin = origin,
									     .dispersal = trait,
									     .logic_tick =
										     ticks[t]};
				for (uint8_t c = 0U; c < choices; ++c) {
					o.columns[c] = reference_column(origin, trait, c, wide);
					assert(o.columns[c] ==
					       picosystem_garden_dispersed_column_at(origin, trait,
										     c, ticks[t]));
				}
				/* Empty/full, each individual blocked/clear column, and
				 * alternating occupancy. Reflected aliases share a bit.
				 */
				for (uint8_t pattern = 0U; pattern < 59U; ++pattern) {
					uint8_t clear[14], count = 0U;
					o.blocked_choices = 0U;
					for (uint8_t c = 0U; c < choices; ++c) {
						const bool blocked =
							pattern == 1U ||
							(pattern >= 2U && pattern < 30U &&
							 o.columns[c] == pattern - 2U) ||
							(pattern >= 30U && pattern < 58U &&
							 o.columns[c] != pattern - 30U) ||
							(pattern == 58U && o.columns[c] % 2U);
						if (blocked) {
							o.blocked_choices |= (uint16_t)(1U << c);
						} else {
							clear[count++] = c;
						}
					}
					for (uint32_t r = 0U; r <= 2U * choices; ++r) {
						o.random = r == 2U * choices ? UINT32_MAX : r;
						const struct picosystem_garden_seed_placement
							before = o;
						const uint8_t original =
							(uint8_t)(o.random % choices);
						assert(o.columns[original] ==
						       reference_column(origin, trait, o.random,
									wide));
						uint8_t selected = 99U;
						assert(toy_factory_garden_placement_choose(
							       &o, 1U, &selected) == 0);
						assert(selected ==
						       (count && (o.blocked_choices &
								  (1U << original))
								? clear[(o.random / choices) %
									count]
								: original));
						assert(toy_factory_garden_placement_choose(
							       &o, 0U, &selected) == 0 &&
						       selected == original);
						assert(memcmp(&before, &o, sizeof(o)) == 0);
					}
				}
				uint8_t selected = 99U;
				o.blocked_choices = (uint16_t)(1U << choices);
				assert(toy_factory_garden_placement_choose(&o, 1U, &selected) ==
					       -ERANGE &&
				       selected == 99U);
				o.blocked_choices = 0U;
				o.columns[choices - 1U] = UINT8_MAX;
				assert(toy_factory_garden_placement_choose(&o, 1U, &selected) ==
					       -ERANGE &&
				       selected == 99U);
			}
		}
	}
}

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

static void ready(struct picosystem_garden_world *world, uint32_t seed)
{
	assert(picosystem_garden_world_reset(world, seed) == 0);
	world->auto_gardener_enabled = false;
	for (uint8_t i = 0U; i < 3U; ++i) {
		assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_FLOWER,
							  (uint8_t)(i * 8U)) == 0);
		world->plants[i].stored_energy = 145U;
		world->plants[i].stored_water = 65U;
		world->plants[i].genome = (struct picosystem_garden_genome){0};
		world->plants[i].reproduction_cooldown = 0U;
	}
	for (uint16_t i = 0U; i < world->node_count; ++i) {
		world->nodes[i].kind = PICOSYSTEM_GARDEN_NODE_STEM;
		world->nodes[i].flags = i % 4U == 0U ? PICOSYSTEM_GARDEN_NODE_FLOWER : 0U;
		world->nodes[i].growth_progress = UINT8_MAX;
	}
	world->logic_tick_count = 899U;
	world->ecology_tick_count = 59U;
}

static int invalid_choice(const struct picosystem_garden_seed_placement *o, uint8_t *choice,
			  const void *context)
{
	(void)o;
	(void)context;
	*choice = 6U;
	return 0;
}

static void production(void)
{
	const struct toy_factory_garden_placement_config config = {.version = 1U, .enabled = 1U};
	struct toy_factory_garden_placement_audit audit;
	const struct toy_factory_garden_placement_context context = {.config = &config,
								     .audit = &audit};
	const struct picosystem_garden_agent_policy plain = {
		.decide = wait_decide, .arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS};
	struct picosystem_garden_agent_policy placing = plain;
	placing.place_seed = toy_factory_garden_placement_decide;
	placing.placement_context = &context;
	uint32_t changes = 0U;
	for (uint32_t seed = 1U; seed <= 32U; ++seed) {
		struct picosystem_garden_world control;
		ready(&control, seed);
		struct picosystem_garden_world candidate = control;
		audit = (struct toy_factory_garden_placement_audit){0};
		assert(picosystem_garden_world_step_with_policy(&control, &plain) == 0);
		assert(picosystem_garden_world_step_with_policy(&candidate, &placing) == 0);
		assert(audit.count == control.seed_count && audit.count == 3U);
		assert(audit.purchases[0].observation.blocked_choices == 60U);
		for (uint8_t i = 0U; i < candidate.seed_count; ++i) {
			changes += candidate.seeds[i].column != control.seeds[i].column;
			candidate.seeds[i].column = control.seeds[i].column;
		}
		/* Only seed columns differ: RNG, mutations, paid resources, cooldowns,
		 * seed counts and flower consumption must all remain byte-identical.
		 */
		assert(memcmp(&candidate, &control, sizeof(control)) == 0);
	}
	assert(changes > 0U);
	struct picosystem_garden_world world;
	ready(&world, 42U);
	world.plants[1].flags |= PICOSYSTEM_GARDEN_PLANT_DEAD;
	world.plants[1].stress = PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD;
	world.death_count = 1U;
	world.plants[1].stored_energy = 0U;
	audit = (struct toy_factory_garden_placement_audit){0};
	assert(picosystem_garden_world_step_with_policy(&world, &placing) == 0);
	assert(audit.purchases[0].observation.blocked_choices == 60U);
	ready(&world, 42U);
	placing.place_seed = invalid_choice;
	assert(picosystem_garden_world_step_with_policy(&world, &placing) == -ERANGE);
}

static void timed_production(void)
{
	const struct toy_factory_garden_placement_config config = {.version = 1U, .enabled = 1U};
	struct toy_factory_garden_placement_audit audit;
	const struct toy_factory_garden_placement_context context = {.config = &config,
								     .audit = &audit};
	const struct picosystem_garden_agent_policy plain = {
		.decide = wait_decide, .arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS};
	struct picosystem_garden_agent_policy placing = plain;
	placing.place_seed = toy_factory_garden_placement_decide;
	placing.placement_context = &context;
	for (uint32_t tick = 626580U; tick <= 626640U; tick += 60U) {
		for (uint32_t seed = 1U; seed <= 32U; ++seed) {
			struct picosystem_garden_world control;
			ready(&control, seed);
			control.logic_tick_count = tick - 1U;
			control.ecology_tick_count = (tick - 1U) / 15U;
			struct picosystem_garden_world candidate = control;
			audit = (struct toy_factory_garden_placement_audit){0};
			assert(picosystem_garden_world_step_with_policy(&control, &plain) == 0);
			assert(picosystem_garden_world_step_with_policy(&candidate, &placing) == 0);
			assert(audit.count == 3U && candidate.seed_count == control.seed_count);
			struct picosystem_garden_seed_sites sites;
			assert(picosystem_garden_world_seed_sites(&candidate, &sites) == 0);
			for (uint8_t i = 0U; i < audit.count; ++i) {
				const struct picosystem_garden_seed_placement *const o =
					&audit.purchases[i].observation;
				assert(o->logic_tick == tick);
				uint32_t support = 0U;
				for (uint8_t c = 0U;
				     c < picosystem_garden_dispersal_choices_at(tick); ++c) {
					support |= UINT32_C(1) << o->columns[c];
				}
				assert(support == sites.dispersal_columns[i]);
				assert(candidate.seeds[i].column ==
				       o->columns[audit.purchases[i].selected]);
				candidate.seeds[i].column = control.seeds[i].column;
			}
			/* Broader support still leaves expenses, genome mutation and
			 * RNG state unchanged when only placement choice differs.
			 */
			assert(memcmp(&candidate, &control, sizeof(control)) == 0);
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
	struct toy_factory_garden_landing_growth_run budget, off, on, traced;
	assert(toy_factory_garden_landing_budget_init(&world, &model, 1U, &budget) == 0);
	assert(toy_factory_garden_landing_placement_init(&world, &model, 1U, 0U, &off) == 0);
	assert(toy_factory_garden_landing_placement_init(&world, &model, 1U, 1U, &on) == 0);
	traced = on;
	struct picosystem_garden_death_audit deaths;
	struct picosystem_garden_seed_audit seeds;
	struct picosystem_garden_resource_audit resources;
	struct toy_factory_garden_placement_audit audit;
	uint32_t h[3];
	assert(toy_factory_garden_landing_growth_hash(&budget, &h[0]) == 0);
	assert(toy_factory_garden_landing_growth_hash(&off, &h[1]) == 0);
	assert(toy_factory_garden_landing_growth_hash(&on, &h[2]) == 0);
	assert(h[0] != h[1] && h[1] != h[2] && h[0] != h[2]);
	for (uint32_t i = 0U; i < 8U * 3840U; ++i) {
		assert(toy_factory_garden_landing_growth_step(&budget, &deaths, &seeds, NULL) == 0);
		assert(toy_factory_garden_landing_growth_step(&off, &deaths, &seeds, NULL) == 0);
		assert(memcmp(&budget.base, &off.base, sizeof(off.base)) == 0);
		assert(toy_factory_garden_landing_growth_step(&on, &deaths, &seeds, NULL) == 0);
		assert(toy_factory_garden_landing_growth_step_placement(&traced, &deaths, &seeds,
									&resources, &audit) == 0);
		assert(memcmp(&on, &traced, sizeof(on)) == 0);
		assert(audit.ecology_step == ((i + 1U) % 15U == 0U));
	}
	const struct toy_factory_garden_landing_growth_run saved = on;
	assert(toy_factory_garden_landing_placement_init(&world, &model, 1U, 2U, &on) == -ERANGE);
	assert(memcmp(&saved, &on, sizeof(on)) == 0);
	on.placement.version = 2U;
	h[0] = 99U;
	assert(toy_factory_garden_landing_growth_hash(&on, &h[0]) == -ERANGE && h[0] == 99U);
	assert(toy_factory_garden_landing_placement_init(&world, &model, 1U, 1U, &on) == 0);
	on.base.world.logic_tick_count = 14U;
	on.base.world.nodes[1].x = 0U;
	const struct toy_factory_garden_landing_growth_run failing = on;
	memset(&audit, 0xa5, sizeof(audit));
	const struct toy_factory_garden_placement_audit old_audit = audit;
	assert(toy_factory_garden_landing_growth_step_placement(&on, &deaths, &seeds, &resources,
								&audit) != 0);
	assert(memcmp(&on, &failing, sizeof(on)) == 0 &&
	       memcmp(&audit, &old_audit, sizeof(audit)) == 0);
}

int main(void)
{
	mapping();
	timed_mapping();
	production();
	timed_production();
	run_contract();
	return 0;
}
