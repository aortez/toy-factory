/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_run.h"
#include "garden_evaluation.h"

#include <assert.h>
#include <errno.h>
#include <string.h>

int main(void)
{
	struct picosystem_garden_world world;
	assert(toy_factory_garden_evaluation_reset(&world, &toy_factory_garden_rainfed_scenarios[1],
						   0x940cfdc4U) == 0);
	struct toy_factory_garden_landing_model model;
	const struct toy_factory_garden_landing_feature_config config = {.version = 1U, .mode = 1U};
	assert(toy_factory_garden_landing_model_import(picosystem_garden_neural_reference_model(),
						       &config, &model) == 0);
	struct toy_factory_garden_landing_run traced;
	assert(toy_factory_garden_landing_run_init(&world, &model, &traced) == 0);
	struct toy_factory_garden_landing_run plain = traced;
	struct picosystem_garden_death_audit deaths, control_deaths;
	struct picosystem_garden_seed_audit seeds, control_seeds;
	struct picosystem_garden_resource_audit resources;
	bool income_seen = false, death_seen = false;
	for (uint32_t tick = 0U; tick < 32U * 3840U; ++tick) {
		assert(toy_factory_garden_landing_run_step_resources(&traced, &deaths, &seeds,
								     &resources) == 0);
		assert(toy_factory_garden_landing_run_step_audits(&plain, &control_deaths,
								  &control_seeds) == 0);
		assert(memcmp(&traced, &plain, sizeof(plain)) == 0);
		assert(memcmp(&deaths, &control_deaths, sizeof(deaths)) == 0);
		assert(memcmp(&seeds, &control_seeds, sizeof(seeds)) == 0);
		if (!deaths.ecology_step) {
			const struct picosystem_garden_resource_audit empty = {0};
			assert(memcmp(&resources, &empty, sizeof(empty)) == 0);
			continue;
		}
		for (uint8_t i = 0U; i < resources.uptake.count; ++i) {
			const struct picosystem_garden_death_event *const r =
				&resources.uptake.events[i];
			const struct picosystem_garden_resource_plant *p = NULL;
			for (uint8_t j = 0U; j < resources.stages[0].count; ++j) {
				if (resources.stages[0].plants[j].lineage_id == r->lineage_id) {
					p = &resources.stages[0].plants[j];
				}
			}
			assert(p != NULL);
			assert(p->energy ==
			       r->energy.before + r->energy.income - r->energy.overflow);
			assert(p->water == r->water.before + r->water.income - r->water.overflow);
			income_seen |= r->energy.income > 0U || r->water.income > 0U;
		}
		for (uint8_t i = 0U; i < deaths.count; ++i) {
			bool found = false;
			for (uint8_t j = 0U; j < resources.uptake.count; ++j) {
				if (deaths.events[i].lineage_id ==
				    resources.uptake.events[j].lineage_id) {
					assert(memcmp(&deaths.events[i],
						      &resources.uptake.events[j],
						      sizeof(deaths.events[i])) == 0);
					found = true;
				}
			}
			assert(found);
			death_seen = true;
		}
	}
	assert(income_seen && death_seen);
	/* Internal growth failure after uptake/sampling cannot publish partial output. */
	assert(picosystem_garden_world_reset(&world, 3U) == 0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 3U) ==
	       0);
	assert(toy_factory_garden_landing_run_init(&world, &model, &traced) == 0);
	traced.world.logic_tick_count = 14U;
	traced.world.nodes[1].x = 0U;
	const struct toy_factory_garden_landing_run failing = traced;
	memset(&resources, 0xa5, sizeof(resources));
	memset(&seeds, 0xa5, sizeof(seeds));
	memset(&deaths, 0xa5, sizeof(deaths));
	const struct picosystem_garden_resource_audit before = resources;
	control_seeds = seeds;
	control_deaths = deaths;
	assert(toy_factory_garden_landing_run_step_resources(&traced, &deaths, &seeds,
							     &resources) != 0);
	assert(memcmp(&traced, &failing, sizeof(traced)) == 0);
	assert(memcmp(&resources, &before, sizeof(resources)) == 0);
	assert(memcmp(&seeds, &control_seeds, sizeof(seeds)) == 0);
	assert(memcmp(&deaths, &control_deaths, sizeof(deaths)) == 0);
	assert(toy_factory_garden_landing_run_step_resources(NULL, &deaths, &seeds, &resources) ==
	       -EINVAL);
	assert(toy_factory_garden_landing_run_step_resources(&traced, NULL, &seeds, &resources) ==
	       -EINVAL);
	assert(toy_factory_garden_landing_run_step_resources(&traced, &deaths, NULL, &resources) ==
	       -EINVAL);
	assert(toy_factory_garden_landing_run_step_resources(&traced, &deaths, &seeds, NULL) ==
	       -EINVAL);
	assert(memcmp(&resources, &before, sizeof(resources)) == 0);
	return 0;
}
