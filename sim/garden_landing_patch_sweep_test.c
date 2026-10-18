/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_patch_sweep.h"
#include "garden_landing_ledger.h"
#include <assert.h>
#include <errno.h>
#include <string.h>

static struct toy_factory_garden_lifetimes ledger, saved_ledger;
static struct toy_factory_garden_landing_ledger history;

static void clock_at(struct toy_factory_garden_landing_growth_run *run, uint32_t tick)
{
	run->base.world.logic_tick_count = tick;
	run->base.world.ecology_tick_count = tick / PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR;
	run->base.cache.ecology_tick = run->base.world.ecology_tick_count;
}

static void setup(struct toy_factory_garden_landing_growth_run *run, bool recurring)
{
	const uint32_t due = (recurring ? TOY_FACTORY_GARDEN_RECURRING_FIRST_DAY
					: TOY_FACTORY_GARDEN_PATCH_FIRST_DAY) *
			     TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS;
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	assert(toy_factory_garden_lifetimes_reset(&ledger) == 0);
	const uint8_t columns[] = {recurring ? 4U : 0U, recurring ? 7U : 3U, 14U};
	for (uint8_t i = 0U; i < 3U; ++i) {
		assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER,
							  columns[i]) == 0);
		assert(toy_factory_garden_lifetimes_birth(&ledger, (uint32_t)i + 1U, 0U, 0U, 0U) ==
		       0);
		world.plants[i].age_ecology_ticks = 512U;
		world.plants[i].agent_memory.hidden[0] = (int8_t)(i + 1U);
	}
	/* The same patch must include a young seedling, not just established adults. */
	world.plants[1].age_ecology_ticks = 1U;
	world.plants[0].age_ecology_ticks = 65536U;
	ledger.records[2].birth_tick = due - PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR;
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
	clock_at(run, due);
	run->base.cache.warmup_samples = 256U;
}

static void recurring_tests(void)
{
	struct toy_factory_garden_landing_growth_run run;
	struct toy_factory_garden_patch_sweep events = {0};
	setup(&run, true);
	const uint32_t first = run.base.world.logic_tick_count;
	run.seed_cursor.after = 320U * TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS;
	run.seed_cursor.last_buyer = 3U;
	clock_at(&run, first - 1U);
	const struct toy_factory_garden_landing_growth_run early = run;
	saved_ledger = ledger;
	assert(toy_factory_garden_patch_recurring_step(&run, &ledger, &events) == 0);
	assert(events.count == 0U && memcmp(&run, &early, sizeof(run)) == 0);
	assert(memcmp(&ledger, &saved_ledger, sizeof(ledger)) == 0);
	clock_at(&run, first);
	struct toy_factory_garden_landing_growth_run expected = run;
	assert(picosystem_garden_world_experimental_kill_patch(&expected.base.world, 4U, 7U) == 0);
	assert(toy_factory_garden_patch_recurring_step(&run, &ledger, &events) == 0);
	assert(memcmp(&run, &expected, sizeof(run)) == 0);
	assert(events.count == 1U && events.events[0].count == 2U);
	assert(events.events[0].victims[0].age == 65536U && events.events[0].victims[1].age == 1U);
	assert(ledger.records[1].death_tick == first && ledger.records[2].death_tick == first);
	assert(ledger.records[1].death_cause == 3U && ledger.records[2].death_cause == 3U);
	assert(run.base.world.plant_count == 3U && run.base.world.node_count == 12U);
	assert(run.base.world.reclaimed_plant_count == 0U);
	assert(toy_factory_garden_patch_recurring_step(&run, &ledger, &events) == 0 &&
	       events.count == 1U);
	for (uint8_t i = 1U; i < TOY_FACTORY_GARDEN_RECURRING_EVENTS; ++i) {
		clock_at(&run, first + (uint32_t)i * TOY_FACTORY_GARDEN_RECURRING_PERIOD_DAYS *
					       TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS);
		assert(toy_factory_garden_patch_recurring_step(&run, &ledger, &events) == 0);
		assert(events.events[i].first_column == 4U * (i + 1U));
		assert(events.events[i].last_column == 4U * (i + 1U) + 3U);
		assert(events.events[i].count == (i == 2U ? 1U : 0U));
		if (i != 2U) {
			assert(events.events[i].before_world_hash ==
			       events.events[i].after_world_hash);
			assert(events.events[i].before_run_hash == events.events[i].after_run_hash);
		}
	}
	const struct toy_factory_garden_landing_growth_run ended = run;
	assert(toy_factory_garden_patch_recurring_step(&run, &ledger, &events) == 0);
	assert(memcmp(&run, &ended, sizeof(run)) == 0 && events.count == 4U);
	FILE *stream = tmpfile();
	assert(stream != NULL && toy_factory_garden_patch_recurring_print(stream, &events) == 0);
	assert(fclose(stream) == 0);
	stream = fopen("/dev/full", "w");
	assert(stream != NULL && setvbuf(stream, NULL, _IONBF, 0U) == 0);
	assert(toy_factory_garden_patch_recurring_print(stream, &events) == -EIO);
	(void)fclose(stream);
	assert(toy_factory_garden_patch_recurring_print(NULL, &events) == -EINVAL);
	events.count = 5U;
	assert(toy_factory_garden_patch_recurring_step(&run, &ledger, &events) == -EINVAL);
	stream = tmpfile();
	assert(stream != NULL);
	assert(toy_factory_garden_patch_recurring_print(stream, &events) == -EINVAL);
	assert(ftell(stream) == 0L && fclose(stream) == 0);
	/* Same transaction must roll back an earlier victim if a later receipt fails. */
	setup(&run, true);
	events = (struct toy_factory_garden_patch_sweep){0};
	ledger.records[2].death_cause = 3U;
	saved_ledger = ledger;
	const struct toy_factory_garden_landing_growth_run rollback = run;
	const struct toy_factory_garden_patch_sweep empty = events;
	assert(toy_factory_garden_patch_recurring_step(&run, &ledger, &events) != 0);
	assert(memcmp(&run, &rollback, sizeof(run)) == 0);
	assert(memcmp(&ledger, &saved_ledger, sizeof(ledger)) == 0);
	assert(memcmp(&events, &empty, sizeof(events)) == 0);
	setup(&run, true);
	clock_at(&run, first + 1U);
	assert(toy_factory_garden_patch_recurring_step(&run, &ledger, &events) == -ERANGE);
	assert(toy_factory_garden_patch_recurring_step(NULL, &ledger, &events) == -EINVAL);
	assert(toy_factory_garden_patch_recurring_step(&run, NULL, &events) == -EINVAL);
	assert(toy_factory_garden_patch_recurring_step(&run, &ledger, NULL) == -EINVAL);
	assert(toy_factory_garden_patch_recurring_hash(1U) !=
	       toy_factory_garden_patch_recurring_hash(2U));
	assert(toy_factory_garden_patch_recurring_hash(1U) !=
	       toy_factory_garden_patch_sweep_hash(1U));
}

static void setup_followup(struct toy_factory_garden_landing_growth_run *run)
{
	setup(run, true);
	const uint32_t due =
		TOY_FACTORY_GARDEN_PATCH_FOLLOWUP_DAY * TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS;
	clock_at(run, due);
	run->base.world.plants[0].base_column = 20U;
	run->base.world.plants[1].base_column = 23U;
	ledger.records[2].birth_tick = due - PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR;
}

static void followup_tests(void)
{
	struct toy_factory_garden_landing_growth_run run;
	struct toy_factory_garden_patch_sweep events = {0};
	setup_followup(&run);
	const uint32_t due = run.base.world.logic_tick_count;
	clock_at(&run, due - 1U);
	struct toy_factory_garden_landing_growth_run expected = run;
	saved_ledger = ledger;
	assert(toy_factory_garden_patch_followup_step(&run, &ledger, &events) == 0);
	assert(memcmp(&run, &expected, sizeof(run)) == 0 && events.count == 0U);
	assert(memcmp(&ledger, &saved_ledger, sizeof(ledger)) == 0);
	clock_at(&run, due);
	expected = run;
	/* The old recurring schedule must still stop after four events. */
	struct toy_factory_garden_patch_sweep old = {.count = 4U};
	assert(toy_factory_garden_patch_recurring_step(&run, &ledger, &old) == 0);
	assert(memcmp(&run, &expected, sizeof(run)) == 0 && old.count == 4U);
	assert(picosystem_garden_world_experimental_kill_patch(&expected.base.world, 20U, 23U) ==
	       0);
	assert(toy_factory_garden_patch_followup_step(&run, &ledger, &events) == 0);
	assert(memcmp(&run, &expected, sizeof(run)) == 0);
	assert(events.count == 1U && events.events[0].count == 2U);
	assert(events.events[0].tick == due && events.events[0].first_column == 20U &&
	       events.events[0].last_column == 23U);
	assert(events.events[0].victims[1].age == 1U);
	assert(ledger.records[1].death_tick == due && ledger.records[2].death_tick == due);
	assert(run.base.world.plant_count == 3U && run.base.world.node_count == 12U);
	assert(toy_factory_garden_patch_followup_step(&run, &ledger, &events) == 0);
	assert(memcmp(&run, &expected, sizeof(run)) == 0 && events.count == 1U);
	FILE *stream = tmpfile();
	assert(stream != NULL && toy_factory_garden_patch_followup_print(stream, &events) == 0);
	assert(fclose(stream) == 0);
	stream = fopen("/dev/full", "w");
	assert(stream != NULL && setvbuf(stream, NULL, _IONBF, 0U) == 0);
	assert(toy_factory_garden_patch_followup_print(stream, &events) == -EIO);
	(void)fclose(stream);
	assert(toy_factory_garden_patch_followup_print(NULL, &events) == -EINVAL);
	events.count = 2U;
	assert(toy_factory_garden_patch_followup_step(&run, &ledger, &events) == -EINVAL);
	stream = tmpfile();
	assert(stream != NULL &&
	       toy_factory_garden_patch_followup_print(stream, &events) == -EINVAL);
	assert(ftell(stream) == 0L && fclose(stream) == 0);
	setup_followup(&run);
	events = (struct toy_factory_garden_patch_sweep){0};
	ledger.records[2].death_cause = 3U;
	saved_ledger = ledger;
	expected = run;
	const struct toy_factory_garden_patch_sweep empty = events;
	assert(toy_factory_garden_patch_followup_step(&run, &ledger, &events) != 0);
	assert(memcmp(&run, &expected, sizeof(run)) == 0);
	assert(memcmp(&ledger, &saved_ledger, sizeof(ledger)) == 0);
	assert(memcmp(&events, &empty, sizeof(events)) == 0);
	setup_followup(&run);
	clock_at(&run, due + 1U);
	assert(toy_factory_garden_patch_followup_step(&run, &ledger, &events) == -ERANGE);
	assert(toy_factory_garden_patch_followup_step(NULL, &ledger, &events) == -EINVAL);
	assert(toy_factory_garden_patch_followup_step(&run, NULL, &events) == -EINVAL);
	assert(toy_factory_garden_patch_followup_step(&run, &ledger, NULL) == -EINVAL);
	setup_followup(&run);
	run.base.world.plants[0].base_column = 19U;
	run.base.world.plants[1].base_column = 24U;
	expected = run;
	saved_ledger = ledger;
	assert(toy_factory_garden_patch_followup_step(&run, &ledger, &events) == 0);
	assert(events.count == 1U && events.events[0].count == 0U);
	assert(events.events[0].before_world_hash == events.events[0].after_world_hash);
	assert(events.events[0].before_run_hash == events.events[0].after_run_hash);
	assert(memcmp(&run, &expected, sizeof(run)) == 0);
	assert(memcmp(&ledger, &saved_ledger, sizeof(ledger)) == 0);
	assert(toy_factory_garden_patch_followup_hash(1U) !=
	       toy_factory_garden_patch_followup_hash(2U));
	assert(toy_factory_garden_patch_followup_hash(1U) !=
	       toy_factory_garden_patch_recurring_hash(1U));
}

static void renewal_tests(void)
{
	struct toy_factory_garden_landing_growth_run run;
	struct toy_factory_garden_patch_sweep events = {0}, old_events = {0};
	setup(&run, true);
	run.base.world.plants[2].base_column = 0U;
	const uint32_t first = run.base.world.logic_tick_count;
	clock_at(&run, first - 1U);
	struct toy_factory_garden_landing_growth_run expected = run;
	assert(toy_factory_garden_patch_renewal_step(&run, &ledger, &events) == 0);
	assert(events.count == 0U && memcmp(&run, &expected, sizeof(run)) == 0);
	for (uint8_t i = 0U; i < TOY_FACTORY_GARDEN_PATCH_RENEWAL_EVENTS; ++i) {
		clock_at(&run, first + (uint32_t)i * 32U * TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS);
		expected = run;
		saved_ledger = ledger;
		if (i < TOY_FACTORY_GARDEN_RECURRING_EVENTS) {
			assert(toy_factory_garden_patch_recurring_step(&expected, &saved_ledger,
								       &old_events) == 0);
		}
		assert(toy_factory_garden_patch_renewal_step(&run, &ledger, &events) == 0);
		assert(events.count == i + 1U);
		assert(events.events[i].first_column == ((i + 1U) % 7U) * 4U);
		assert(events.events[i].last_column == ((i + 1U) % 7U) * 4U + 3U);
		assert(events.events[i].count == (i == 0U ? 2U : (i == 6U ? 1U : 0U)));
		if (i < TOY_FACTORY_GARDEN_RECURRING_EVENTS) {
			assert(memcmp(&run, &expected, sizeof(run)) == 0);
			assert(memcmp(&ledger, &saved_ledger, sizeof(ledger)) == 0);
			assert(memcmp(&events.events[i], &old_events.events[i],
				      sizeof(events.events[i])) == 0);
		}
		if ((i > 0U) && (i < 6U)) {
			assert(events.events[i].before_world_hash ==
			       events.events[i].after_world_hash);
			assert(events.events[i].before_run_hash == events.events[i].after_run_hash);
		}
	}
	assert(events.events[6].tick == 588U * TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS);
	assert(events.events[0].victims[1].age == 1U && run.base.world.plant_count == 3U);
	assert(run.base.world.node_count == 12U &&
	       ledger.records[3].death_tick == events.events[6].tick);
	expected = run;
	assert(toy_factory_garden_patch_renewal_step(&run, &ledger, &events) == 0);
	assert(memcmp(&run, &expected, sizeof(run)) == 0 && events.count == 7U);
	FILE *stream = tmpfile();
	assert(stream != NULL &&
	       toy_factory_garden_patch_renewal_print(stream, &events, false) == -EINVAL);
	assert(ftell(stream) == 0L);
	assert(toy_factory_garden_patch_renewal_print(stream, &events, true) == 0);
	assert(fclose(stream) == 0);
	events.count = 8U;
	assert(toy_factory_garden_patch_renewal_step(&run, &ledger, &events) == -EINVAL);
	setup(&run, true);
	events = (struct toy_factory_garden_patch_sweep){0};
	ledger.records[2].death_cause = 3U;
	saved_ledger = ledger;
	expected = run;
	assert(toy_factory_garden_patch_renewal_step(&run, &ledger, &events) != 0);
	assert(memcmp(&run, &expected, sizeof(run)) == 0 && events.count == 0U);
	assert(memcmp(&ledger, &saved_ledger, sizeof(ledger)) == 0);
	assert(toy_factory_garden_patch_renewal_hash(1U, true) !=
	       toy_factory_garden_patch_renewal_hash(1U, false));
	assert(toy_factory_garden_patch_renewal_hash(1U, true) !=
	       toy_factory_garden_patch_recurring_hash(1U));
	stream = tmpfile();
	assert(stream != NULL &&
	       toy_factory_garden_patch_renewal_print(stream, &events, false) == 0);
	assert(fclose(stream) == 0);
}

int main(void)
{
	struct toy_factory_garden_landing_growth_run run;
	struct toy_factory_garden_patch_sweep sweep = {0};
	setup(&run, false);
	const uint32_t first_tick = run.base.world.logic_tick_count;
	clock_at(&run, first_tick - 1U);
	const struct toy_factory_garden_landing_growth_run pre = run;
	saved_ledger = ledger;
	assert(toy_factory_garden_patch_sweep_step(&run, &ledger, &sweep) == 0);
	assert(memcmp(&run, &pre, sizeof(run)) == 0 && sweep.count == 0U);
	assert(memcmp(&ledger, &saved_ledger, sizeof(ledger)) == 0);
	clock_at(&run, first_tick);
	const struct toy_factory_garden_landing_growth_run before = run;
	struct toy_factory_garden_landing_growth_run expected = run;
	assert(picosystem_garden_world_experimental_kill_patch(&expected.base.world, 0U, 3U) == 0);
	assert(toy_factory_garden_patch_sweep_step(&run, &ledger, &sweep) == 0);
	assert(memcmp(&run, &expected, sizeof(run)) == 0);
	assert(sweep.count == 1U && sweep.events[0].count == 2U);
	assert(sweep.events[0].victims[0].lineage == 1U &&
	       sweep.events[0].victims[1].lineage == 2U);
	assert(sweep.events[0].victims[1].age == 1U);
	assert(sweep.events[0].victims[0].age == 65536U);
	assert(ledger.records[1].death_tick == first_tick &&
	       ledger.records[2].death_tick == first_tick);
	assert(ledger.records[1].death_cause == 3U && ledger.records[2].death_cause == 3U);
	assert(ledger.records[3].death_cause == TOY_FACTORY_GARDEN_LIFETIME_CAUSES);
	assert(run.base.world.plant_count == 3U && run.base.world.node_count == 12U);
	assert(run.base.world.reclaimed_plant_count == 0U);
	assert(memcmp(&run.base.cache, &before.base.cache, sizeof(run.base.cache)) == 0);
	assert(memcmp(run.base.world.seeds, before.base.world.seeds,
		      sizeof(run.base.world.seeds)) == 0);
	assert(memcmp(run.base.world.moisture, before.base.world.moisture,
		      sizeof(run.base.world.moisture)) == 0);
	assert(run.base.world.random_state == before.base.world.random_state);
	assert(memcmp(&run.base.world.plants[2], &before.base.world.plants[2],
		      sizeof(run.base.world.plants[2])) == 0);
	assert(toy_factory_garden_patch_sweep_step(&run, &ledger, &sweep) == 0 &&
	       sweep.count == 1U);
	/* Complete every fixed patch, including empty hits and the second sweep. */
	for (uint8_t i = 1U; i < TOY_FACTORY_GARDEN_PATCH_EVENTS; ++i) {
		clock_at(&run, first_tick + (uint32_t)i * TOY_FACTORY_GARDEN_PATCH_PERIOD_DAYS *
						    TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS);
		assert(toy_factory_garden_patch_sweep_step(&run, &ledger, &sweep) == 0);
		assert(sweep.events[i].first_column == (i % 7U) * 4U);
		assert(sweep.events[i].last_column == (i % 7U) * 4U + 3U);
		assert(sweep.events[i].count == (i == 3U ? 1U : 0U));
		if (i != 3U) {
			assert(sweep.events[i].before_world_hash ==
			       sweep.events[i].after_world_hash);
			assert(sweep.events[i].before_run_hash == sweep.events[i].after_run_hash);
		}
	}
	assert(sweep.count == 15U && run.base.world.death_count == 3U);
	FILE *stream = tmpfile();
	assert(stream != NULL);
	history.count = ledger.count;
	const uint32_t ids[] = {1U, 2U, 3U};
	assert(toy_factory_garden_landing_ledger_print_environmental_ids(stream, &history, &ledger,
									 ids, 3U) == 0);
	assert(fclose(stream) == 0);
	/* A failure on the second victim rolls back the first death as well. */
	setup(&run, false);
	sweep = (struct toy_factory_garden_patch_sweep){0};
	ledger.records[2].death_cause = 3U;
	saved_ledger = ledger;
	const struct toy_factory_garden_landing_growth_run rollback = run;
	const struct toy_factory_garden_patch_sweep untouched = sweep;
	assert(toy_factory_garden_patch_sweep_step(&run, &ledger, &sweep) != 0);
	assert(memcmp(&run, &rollback, sizeof(run)) == 0);
	assert(memcmp(&ledger, &saved_ledger, sizeof(ledger)) == 0);
	assert(memcmp(&sweep, &untouched, sizeof(sweep)) == 0);
	setup(&run, false);
	clock_at(&run, first_tick + 1U);
	assert(toy_factory_garden_patch_sweep_step(&run, &ledger, &sweep) == -ERANGE);
	assert(toy_factory_garden_patch_sweep_step(NULL, &ledger, &sweep) == -EINVAL);
	assert(toy_factory_garden_patch_sweep_step(&run, NULL, &sweep) == -EINVAL);
	assert(toy_factory_garden_patch_sweep_step(&run, &ledger, NULL) == -EINVAL);
	/* Invalid environmental sets are rejected before writing any output. */
	history.count = ledger.count;
	assert(toy_factory_garden_lifetimes_death(&ledger, 1U, first_tick,
						  PICOSYSTEM_GARDEN_PLANT_DEAD) == 0);
	const uint32_t duplicate[] = {1U, 1U}, zero[] = {0U}, missing[] = {4U};
	stream = tmpfile();
	assert(stream != NULL);
	assert(toy_factory_garden_landing_ledger_print_environmental_ids(stream, &history, &ledger,
									 duplicate, 2U) == -EINVAL);
	assert(toy_factory_garden_landing_ledger_print_environmental_ids(stream, &history, &ledger,
									 zero, 1U) == -EINVAL);
	assert(toy_factory_garden_landing_ledger_print_environmental_ids(stream, &history, &ledger,
									 missing, 1U) == -EINVAL);
	assert(toy_factory_garden_landing_ledger_print_environmental_ids(stream, &history, &ledger,
									 NULL, 1U) == -EINVAL);
	assert(ftell(stream) == 0L);
	assert(fclose(stream) == 0);
	assert(toy_factory_garden_patch_sweep_hash(1U) != toy_factory_garden_patch_sweep_hash(2U));
	recurring_tests();
	followup_tests();
	renewal_tests();
	return 0;
}
