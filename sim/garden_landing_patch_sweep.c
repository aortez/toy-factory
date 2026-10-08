/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_patch_sweep.h"

#include <errno.h>
#include <inttypes.h>

_Static_assert(PICOSYSTEM_GARDEN_GRID_COLUMNS % TOY_FACTORY_GARDEN_PATCH_WIDTH == 0U,
	       "patch schedule must cover complete equal-width bands");
_Static_assert(TOY_FACTORY_GARDEN_RECURRING_EVENTS <= TOY_FACTORY_GARDEN_PATCH_EVENTS,
	       "recurring log must fit existing bounded storage");
_Static_assert(TOY_FACTORY_GARDEN_PATCH_FOLLOWUP_EVENTS <= TOY_FACTORY_GARDEN_PATCH_EVENTS,
	       "follow-up log must fit existing bounded storage");
_Static_assert(TOY_FACTORY_GARDEN_PATCH_RENEWAL_EVENTS <= TOY_FACTORY_GARDEN_PATCH_EVENTS,
	       "renewal log must fit existing bounded storage");

struct patch_schedule {
	const char *name;
	char tag;
	uint32_t first_day, period_days;
	uint8_t first_patch, event_count;
	bool explicit_first_patch;
	bool explicit_enabled;
};

static const struct patch_schedule sweep_schedule = {
	.name = "patch_sweep_probe",
	.tag = 'S',
	.first_day = TOY_FACTORY_GARDEN_PATCH_FIRST_DAY,
	.period_days = TOY_FACTORY_GARDEN_PATCH_PERIOD_DAYS,
	.event_count = TOY_FACTORY_GARDEN_PATCH_EVENTS};

static const struct patch_schedule recurring_schedule = {
	.name = "patch_recurring_probe",
	.tag = 'R',
	.first_day = TOY_FACTORY_GARDEN_RECURRING_FIRST_DAY,
	.period_days = TOY_FACTORY_GARDEN_RECURRING_PERIOD_DAYS,
	.first_patch = TOY_FACTORY_GARDEN_RECURRING_FIRST_PATCH,
	.event_count = TOY_FACTORY_GARDEN_RECURRING_EVENTS,
	.explicit_first_patch = true};

static const struct patch_schedule followup_schedule = {
	.name = "patch_recurring_followup_probe",
	.tag = 'F',
	.first_day = TOY_FACTORY_GARDEN_PATCH_FOLLOWUP_DAY,
	.period_days = TOY_FACTORY_GARDEN_RECURRING_PERIOD_DAYS,
	.first_patch = TOY_FACTORY_GARDEN_PATCH_FOLLOWUP_FIRST_PATCH,
	.event_count = TOY_FACTORY_GARDEN_PATCH_FOLLOWUP_EVENTS,
	.explicit_first_patch = true};

static const struct patch_schedule renewal_schedule = {
	.name = "patch_renewal_probe",
	.tag = 'N',
	.first_day = TOY_FACTORY_GARDEN_RECURRING_FIRST_DAY,
	.period_days = TOY_FACTORY_GARDEN_RECURRING_PERIOD_DAYS,
	.first_patch = TOY_FACTORY_GARDEN_RECURRING_FIRST_PATCH,
	.event_count = TOY_FACTORY_GARDEN_PATCH_RENEWAL_EVENTS,
	.explicit_first_patch = true,
	.explicit_enabled = true};

/* Only the compile-time schedules above call this helper. */
static int step(struct toy_factory_garden_landing_growth_run *run,
		struct toy_factory_garden_lifetimes *ledger,
		struct toy_factory_garden_patch_sweep *sweep, const struct patch_schedule *schedule)
{
	if ((run == NULL) || (ledger == NULL) || (sweep == NULL) ||
	    (sweep->count > schedule->event_count)) {
		return -EINVAL;
	}
	if (sweep->count == schedule->event_count) {
		return 0;
	}
	const uint32_t due =
		(schedule->first_day + (uint32_t)sweep->count * schedule->period_days) *
		TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS;
	const struct picosystem_garden_world *const world = &run->base.world;
	if (world->logic_tick_count < due) {
		return 0;
	}
	if ((world->logic_tick_count != due) ||
	    (world->plant_count > PICOSYSTEM_GARDEN_MAX_PLANTS) ||
	    (ledger->count > TOY_FACTORY_GARDEN_EVALUATION_MAX_TRACKED_LINEAGES) ||
	    (ledger->count != world->lineage_sequence) || (ledger->last_event_tick > due)) {
		return -ERANGE;
	}
	const uint8_t first =
		(uint8_t)(((schedule->first_patch + sweep->count) %
			   (PICOSYSTEM_GARDEN_GRID_COLUMNS / TOY_FACTORY_GARDEN_PATCH_WIDTH)) *
			  TOY_FACTORY_GARDEN_PATCH_WIDTH);
	struct toy_factory_garden_patch_event event = {
		.tick = due,
		.first_column = first,
		.last_column = (uint8_t)(first + TOY_FACTORY_GARDEN_PATCH_WIDTH - 1U)};
	for (uint8_t i = 0U; i < world->plant_count; ++i) {
		const struct picosystem_garden_plant *const plant = &world->plants[i];
		if ((plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) || (plant->base_column < first) ||
		    (plant->base_column > event.last_column)) {
			continue;
		}
		if ((plant->lineage_id == 0U) || (plant->lineage_id > ledger->count) ||
		    (ledger->records[plant->lineage_id].removal_tick != 0U)) {
			return -EINVAL;
		}
		event.victims[event.count++] =
			(struct toy_factory_garden_patch_victim){.lineage = plant->lineage_id,
								 .age = plant->age_ecology_ticks,
								 .nodes = plant->node_count,
								 .energy = plant->stored_energy,
								 .water = plant->stored_water};
	}
	if (world->death_count > UINT32_MAX - event.count) {
		return -ERANGE;
	}
	int err = toy_factory_garden_landing_growth_hash(run, &event.before_run_hash);
	if (err != 0) {
		return err;
	}
	/* Host-only copies include the lifetime ledger: a late victim failure must
	 * not leave earlier victims dead in either representation.
	 */
	struct toy_factory_garden_landing_growth_run candidate = *run;
	struct toy_factory_garden_lifetimes deaths = *ledger;
	err = picosystem_garden_world_experimental_kill_patch(&candidate.base.world, first,
							      event.last_column);
	if (err != 0) {
		return err;
	}
	if (candidate.base.world.death_count != world->death_count + event.count) {
		return -EFAULT;
	}
	for (uint8_t i = 0U; (i < event.count) && (err == 0); ++i) {
		err = toy_factory_garden_lifetimes_death(&deaths, event.victims[i].lineage, due,
							 PICOSYSTEM_GARDEN_PLANT_DEAD);
	}
	if (err == 0) {
		err = toy_factory_garden_landing_growth_hash(&candidate, &event.after_run_hash);
	}
	if (err == 0) {
		event.before_world_hash = picosystem_garden_world_hash(world);
		event.after_world_hash = picosystem_garden_world_hash(&candidate.base.world);
		*run = candidate;
		*ledger = deaths;
		sweep->events[sweep->count++] = event;
	}
	return err;
}

int toy_factory_garden_patch_sweep_step(struct toy_factory_garden_landing_growth_run *run,
					struct toy_factory_garden_lifetimes *ledger,
					struct toy_factory_garden_patch_sweep *sweep)
{
	return step(run, ledger, sweep, &sweep_schedule);
}

int toy_factory_garden_patch_recurring_step(struct toy_factory_garden_landing_growth_run *run,
					    struct toy_factory_garden_lifetimes *ledger,
					    struct toy_factory_garden_patch_sweep *recurring)
{
	return step(run, ledger, recurring, &recurring_schedule);
}

int toy_factory_garden_patch_followup_step(struct toy_factory_garden_landing_growth_run *run,
					   struct toy_factory_garden_lifetimes *ledger,
					   struct toy_factory_garden_patch_sweep *followup)
{
	return step(run, ledger, followup, &followup_schedule);
}

int toy_factory_garden_patch_renewal_step(struct toy_factory_garden_landing_growth_run *run,
					  struct toy_factory_garden_lifetimes *ledger,
					  struct toy_factory_garden_patch_sweep *renewal)
{
	return step(run, ledger, renewal, &renewal_schedule);
}

static uint32_t schedule_hash(uint32_t base, const struct patch_schedule *schedule, bool enabled)
{
	uint32_t hash = 2166136261U;
	const uint8_t tag[] = {'G', 'P', (uint8_t)schedule->tag, '1'};
	for (size_t i = 0U; i < sizeof(tag); ++i) {
		hash = (hash ^ tag[i]) * 16777619U;
	}
	const uint32_t words[] = {base,
				  schedule->first_day,
				  schedule->period_days,
				  TOY_FACTORY_GARDEN_PATCH_WIDTH,
				  schedule->event_count,
				  schedule->first_patch,
				  enabled ? 1U : 0U};
	const size_t count =
		schedule->explicit_enabled ? 7U : (schedule->explicit_first_patch ? 6U : 5U);
	for (size_t i = 0U; i < count; ++i) {
		for (uint8_t byte = 0U; byte < 4U; ++byte) {
			hash = (hash ^ (uint8_t)(words[i] >> (byte * 8U))) * 16777619U;
		}
	}
	return hash;
}

uint32_t toy_factory_garden_patch_sweep_hash(uint32_t base)
{
	return schedule_hash(base, &sweep_schedule, true);
}

uint32_t toy_factory_garden_patch_recurring_hash(uint32_t base)
{
	return schedule_hash(base, &recurring_schedule, true);
}

uint32_t toy_factory_garden_patch_followup_hash(uint32_t base)
{
	return schedule_hash(base, &followup_schedule, true);
}

uint32_t toy_factory_garden_patch_renewal_hash(uint32_t base, bool enabled)
{
	return schedule_hash(base, &renewal_schedule, enabled);
}

static int print(FILE *stream, const struct toy_factory_garden_patch_sweep *sweep,
		 const struct patch_schedule *schedule, bool enabled)
{
	if ((stream == NULL) || (sweep == NULL) || (sweep->count > schedule->event_count) ||
	    (!enabled && (sweep->count != 0U))) {
		return -EINVAL;
	}
	for (uint8_t i = 0U; i < sweep->count; ++i) {
		if (sweep->events[i].count > PICOSYSTEM_GARDEN_MAX_PLANTS) {
			return -EINVAL;
		}
	}
	fprintf(stream,
		"\"%s\":{\"version\":1,\"first_day\":%u,"
		"\"period_days\":%u,\"width\":%u,\"scheduled_events\":%u,",
		schedule->name, schedule->first_day, schedule->period_days,
		TOY_FACTORY_GARDEN_PATCH_WIDTH, schedule->event_count);
	if (schedule->explicit_first_patch) {
		fprintf(stream, "\"first_patch\":%u,", schedule->first_patch);
	}
	if (schedule->explicit_enabled) {
		fprintf(stream, "\"enabled\":%s,", enabled ? "true" : "false");
	}
	fputs("\"events\":[", stream);
	for (uint8_t i = 0U; i < sweep->count; ++i) {
		const struct toy_factory_garden_patch_event *const event = &sweep->events[i];
		fprintf(stream,
			"%s{\"tick\":%" PRIu32 ",\"first\":%u,\"last\":%u,"
			"\"before_world_hash\":\"%08" PRIx32 "\",\"after_world_hash\":\"%08" PRIx32
			"\",\"before_run_hash\":\"%08" PRIx32 "\",\"after_run_hash\":\"%08" PRIx32
			"\",\"victims\":[",
			i ? "," : "", event->tick, event->first_column, event->last_column,
			event->before_world_hash, event->after_world_hash, event->before_run_hash,
			event->after_run_hash);
		for (uint8_t j = 0U; j < event->count; ++j) {
			const struct toy_factory_garden_patch_victim *const v = &event->victims[j];
			fprintf(stream,
				"%s{\"lineage\":%" PRIu32 ",\"age\":%" PRIu32 ",\"nodes\":%u,"
				"\"energy\":%u,\"water\":%u}",
				j ? "," : "", v->lineage, v->age, v->nodes, v->energy, v->water);
		}
		fputs("]}", stream);
	}
	fputs("]},", stream);
	return ferror(stream) ? -EIO : 0;
}

int toy_factory_garden_patch_sweep_print(FILE *stream,
					 const struct toy_factory_garden_patch_sweep *sweep)
{
	return print(stream, sweep, &sweep_schedule, true);
}

int toy_factory_garden_patch_recurring_print(FILE *stream,
					     const struct toy_factory_garden_patch_sweep *recurring)
{
	return print(stream, recurring, &recurring_schedule, true);
}

int toy_factory_garden_patch_followup_print(FILE *stream,
					    const struct toy_factory_garden_patch_sweep *followup)
{
	return print(stream, followup, &followup_schedule, true);
}

int toy_factory_garden_patch_renewal_print(FILE *stream,
					   const struct toy_factory_garden_patch_sweep *renewal,
					   bool enabled)
{
	return print(stream, renewal, &renewal_schedule, enabled);
}
