/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_turnover.h"
#include "garden_landing_ledger.h"
#include <assert.h>
#include <errno.h>
#include <string.h>

static struct toy_factory_garden_lifetimes ledger, saved_ledger;
static struct toy_factory_garden_landing_ledger history;

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
	assert(picosystem_garden_world_experimental_kill_patch(&expected.base.world, 13U, 13U) ==
	       0);
	struct toy_factory_garden_landing_turnover event = {0};
	assert(toy_factory_garden_landing_turnover_apply(&run, &ledger, 2U, &event) == 0);
	assert(memcmp(&run, &expected, sizeof(run)) == 0);
	assert(memcmp(&run.base.cache, &before.base.cache, sizeof(run.base.cache)) == 0);
	assert(memcmp(run.base.world.seeds, before.base.world.seeds,
		      sizeof(run.base.world.seeds)) == 0);
	assert(memcmp(run.base.world.moisture, before.base.world.moisture,
		      sizeof(run.base.world.moisture)) == 0);
	assert(run.base.world.random_state == before.base.world.random_state);
	assert(run.base.world.plant_count == 3U && run.base.world.node_count == 12U);
	assert(run.base.world.death_count == 1U && run.base.world.reclaimed_plant_count == 0U);
	assert(run.base.world.plants[1].flags == PICOSYSTEM_GARDEN_PLANT_DEAD);
	assert(run.base.world.plants[1].stored_energy == 0U &&
	       run.base.world.plants[1].stored_water == 0U);
	assert(memcmp(&run.base.world.plants[0], &before.base.world.plants[0],
		      sizeof(run.base.world.plants[0])) == 0);
	assert(memcmp(&run.base.world.plants[2], &before.base.world.plants[2],
		      sizeof(run.base.world.plants[2])) == 0);
	assert(ledger.records[2].death_tick == 7680U && ledger.records[2].death_cause == 3U);
	assert(ledger.records[2].removal_tick == 0U);
	assert(event.tick == 7680U && event.lineage_id == 2U && event.nodes == 4U);
	assert(event.before_run_hash != event.after_run_hash);
	assert(event.before_world_hash != event.after_world_hash);
	assert(toy_factory_garden_landing_turnover_hash(1U, 7680U, 2U) !=
	       toy_factory_garden_landing_turnover_hash(1U, 7680U, 3U));
	history.count = 3U;
	FILE *stream = tmpfile();
	assert(stream != NULL);
	assert(toy_factory_garden_landing_ledger_print_environmental(stream, &history, &ledger,
								     1U) == -EINVAL);
	assert(ftell(stream) == 0L);
	assert(toy_factory_garden_landing_ledger_print_environmental(stream, &history, &ledger,
								     2U) == 0);
	rewind(stream);
	char json[4096] = {0};
	assert(fread(json, 1U, sizeof(json) - 1U, stream) > 0U);
	assert(strstr(json, "\"environmental_death\":true") != NULL);
	assert(fclose(stream) == 0);
	for (uint32_t tick = 0U; tick < TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS; ++tick) {
		struct picosystem_garden_death_audit deaths;
		struct picosystem_garden_seed_audit seeds;
		assert(toy_factory_garden_landing_growth_step(&run, &deaths, &seeds, NULL) == 0);
		if (tick == 0U) {
			assert(run.base.world.plant_count == 3U);
		}
	}
	for (uint8_t i = 0U; i < run.base.world.plant_count; ++i) {
		assert(run.base.world.plants[i].lineage_id != 2U);
	}
	assert(run.base.world.reclaimed_plant_count >= 1U);
	/* Sequential imposed deaths retain both causes and never export either body. */
	setup(&run);
	assert(toy_factory_garden_landing_turnover_apply(&run, &ledger, 2U, &event) == 0);
	run.base.world.logic_tick_count += PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR;
	++run.base.world.ecology_tick_count;
	++run.base.cache.ecology_tick;
	assert(toy_factory_garden_landing_turnover_apply(&run, &ledger, 1U, &event) == 0);
	assert(ledger.records[2].death_tick == 7680U && ledger.records[1].death_tick == 7695U);
	assert(run.base.world.plant_count == 3U && run.base.world.node_count == 12U);
	assert(run.base.world.death_count == 2U && run.base.world.reclaimed_plant_count == 0U);
	stream = tmpfile();
	assert(stream != NULL);
	const uint32_t invalid[][2] = {{0U, 1U}, {1U, 1U}, {2U, 3U}, {2U, 4U}};
	for (size_t i = 0U; i < sizeof(invalid) / sizeof(invalid[0]); ++i) {
		assert(toy_factory_garden_landing_ledger_print_environmental_pair(
			       stream, &history, &ledger, invalid[i][0], invalid[i][1]) == -EINVAL);
		assert(ftell(stream) == 0L);
	}
	assert(toy_factory_garden_landing_ledger_print_environmental_pair(stream, &history, &ledger,
									  2U, 1U) == 0);
	rewind(stream);
	memset(json, 0, sizeof(json));
	assert(fread(json, 1U, sizeof(json) - 1U, stream) > 0U);
	const char *first = strstr(json, "\"environmental_death\":true");
	assert(first != NULL);
	const char *second = strstr(first + 1, "\"environmental_death\":true");
	assert(second != NULL && strstr(second + 1, "\"environmental_death\":true") == NULL);
	assert(fclose(stream) == 0);
	const struct toy_factory_garden_landing_growth_run after_pair = run;
	saved_ledger = ledger;
	const struct toy_factory_garden_landing_turnover saved_event = event;
	assert(toy_factory_garden_landing_turnover_apply(&run, &ledger, 2U, &event) < 0);
	assert(memcmp(&after_pair, &run, sizeof(run)) == 0);
	assert(memcmp(&saved_ledger, &ledger, sizeof(ledger)) == 0);
	assert(memcmp(&saved_event, &event, sizeof(event)) == 0);
	for (uint8_t fault = 0U; fault < 10U; ++fault) {
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
		} else if (fault == 4U) {
			--ledger.count;
		} else if (fault == 5U) {
			ledger.last_event_tick = 7695U;
		} else if (fault == 6U) {
			run.base.world.plants[0].base_column = 13U;
		} else if (fault == 7U) {
			run.base.world.plants[1].age_ecology_ticks = 256U;
		} else if (fault == 8U) {
			ledger.records[2].death_cause = 3U;
		} else {
			run.base.cache.version = 0U;
		}
		const struct toy_factory_garden_landing_growth_run unchanged = run;
		const struct toy_factory_garden_landing_turnover old_event = event;
		saved_ledger = ledger;
		assert(toy_factory_garden_landing_turnover_apply(&run, &ledger, id, &event) < 0);
		assert(memcmp(&unchanged, &run, sizeof(run)) == 0);
		assert(memcmp(&saved_ledger, &ledger, sizeof(ledger)) == 0);
		assert(memcmp(&old_event, &event, sizeof(event)) == 0);
	}
	assert(toy_factory_garden_landing_turnover_apply(NULL, &ledger, 2U, &event) == -EINVAL);
	assert(toy_factory_garden_landing_turnover_apply(&run, NULL, 2U, &event) == -EINVAL);
	assert(toy_factory_garden_landing_turnover_apply(&run, &ledger, 2U, NULL) == -EINVAL);
	return 0;
}
