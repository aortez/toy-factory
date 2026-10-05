/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_vacancy.h"
#include <assert.h>
#include <errno.h>
#include <string.h>

static struct toy_factory_garden_lifetimes ledger, saved_ledger;

static void setup(struct toy_factory_garden_landing_growth_run *run)
{
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	assert(toy_factory_garden_lifetimes_reset(&ledger) == 0);
	for (uint8_t i = 0U; i < 3U; ++i) {
		assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER,
							  (uint8_t)(4U + 9U * i)) == 0);
		assert(toy_factory_garden_lifetimes_birth(&ledger, (uint32_t)i + 1U, 0U, 0U, 0U) ==
		       0);
		world.plants[i].age_ecology_ticks = 512U;
		world.plants[i].agent_memory.hidden[0] = (int8_t)(i + 1U);
	}
	world.auto_gardener_enabled = false;
	world.seeds[0] = (struct picosystem_garden_seed){
		.parent_lineage_id = 2U, .generation = 1U, .column = 15U, .age_ecology_ticks = 20U};
	world.seed_count = 1U;
	world.seed_creation_count = 1U;
	struct toy_factory_garden_landing_model model;
	const struct toy_factory_garden_landing_feature_config config = {.version = 1U, .mode = 1U};
	assert(toy_factory_garden_landing_model_import(picosystem_garden_neural_reference_model(),
						       &config, &model) == 0);
	assert(toy_factory_garden_landing_placement_init(&world, &model, 1U, 1U, run) == 0);
	run->base.world.logic_tick_count = 7680U;
	run->base.world.ecology_tick_count = 512U;
	run->base.cache.ecology_tick = 512U;
	run->base.cache.warmup_samples = 256U;
}

int main(void)
{
	struct toy_factory_garden_landing_growth_run run;
	setup(&run);
	const struct toy_factory_garden_landing_growth_run before = run;
	struct toy_factory_garden_landing_growth_run expected = run;
	assert(picosystem_garden_world_experimental_clear(&expected.base.world, 2U) == 0);
	struct toy_factory_garden_landing_vacancy event = {0};
	assert(toy_factory_garden_landing_vacancy_apply(&run, &ledger, 2U, &event) == 0);
	assert(memcmp(&run, &expected, sizeof(run)) == 0);
	assert(memcmp(&run.base.cache, &before.base.cache, sizeof(run.base.cache)) == 0);
	assert(memcmp(run.base.world.seeds, before.base.world.seeds,
		      sizeof(run.base.world.seeds)) == 0);
	assert(run.base.world.death_count == 0U && run.base.world.reclaimed_plant_count == 0U);
	assert(run.base.world.random_state == before.base.world.random_state);
	assert(run.base.world.plants[1].agent_memory.hidden[0] == 3);
	assert(ledger.records[2].removal_tick == 7680U);
	assert(event.gap.tick == 7680U && event.gap.lineage_id == 2U && event.gap.nodes == 4U);
	assert(event.before_run_hash != event.after_run_hash);
	for (uint8_t fault = 0U; fault < 5U; ++fault) {
		setup(&run);
		uint32_t id = 2U;
		if (fault == 0U) {
			id = 99U;
		} else if (fault == 1U) {
			ledger.records[2].birth_tick = 3840U;
		} else if (fault == 2U) {
			ledger.records[2].removal_tick = 7665U;
		} else if (fault == 3U) {
			++run.base.world.logic_tick_count;
		} else {
			--ledger.count;
		}
		const struct toy_factory_garden_landing_growth_run unchanged = run;
		const struct toy_factory_garden_landing_vacancy old_event = event;
		saved_ledger = ledger;
		assert(toy_factory_garden_landing_vacancy_apply(&run, &ledger, id, &event) < 0);
		assert(memcmp(&unchanged, &run, sizeof(run)) == 0);
		assert(memcmp(&saved_ledger, &ledger, sizeof(ledger)) == 0);
		assert(memcmp(&old_event, &event, sizeof(event)) == 0);
	}
	assert(toy_factory_garden_landing_vacancy_apply(NULL, &ledger, 2U, &event) == -EINVAL);
	return 0;
}
