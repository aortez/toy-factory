/* SPDX-License-Identifier: Apache-2.0 */
#include "research_trace.h"
#include "research_session.h"

#include <errno.h>
#include <inttypes.h>
#include <stdlib.h>

#define TRACE_DAYS       256U
#define TRACE_PLANT_ROWS 4096U
#define TRACE_SEEDS      1024U
#define TRACE_MASKS      128U

_Static_assert(PICOSYSTEM_GARDEN_SEED_VALID_BLOCKERS == 127U, "Seven frozen blockers");
_Static_assert(RESEARCH_DAY_TICKS / PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR == 256U,
	       "Bounded daily counters");

struct trace_flux {
	uint32_t income, overflow, endowment, upkeep_due, upkeep_paid, growth, seeds, discarded,
		repair;
	uint16_t before, after;
};

struct trace_plant {
	uint32_t day, lineage, first_tick, last_tick, samples, maintenance, energy_short,
		water_short;
	struct trace_flux energy, water;
	uint32_t observations, proposals, renewals, worn, restored, condition_endowment;
	struct toy_factory_maintenance_sample first, last;
	uint8_t stress_max;
	bool born, died;
};

struct trace_checks {
	uint32_t masks[TRACE_MASKS], no_living_masks[TRACE_MASKS];
	uint32_t open_sites[PICOSYSTEM_GARDEN_GRID_COLUMNS];
	uint32_t checks, expired, germinated;
	uint8_t light_min, light_max, moisture_min, moisture_max;
};

struct trace_seed {
	uint32_t parent, birth_tick, first_tick, last_tick, child;
	uint16_t generation;
	uint8_t column, species, outcome;
	struct trace_checks checks;
};

struct research_trace {
	uint8_t founder;
	uint32_t plant_count, seed_count, ecology_steps;
	struct trace_plant plants[TRACE_PLANT_ROWS];
	struct trace_seed seeds[TRACE_SEEDS];
	struct trace_checks days[TRACE_DAYS];
};

int research_trace_open(uint8_t founder, struct research_trace **out)
{
	if ((out == NULL) || (founder == 0U) || (founder > 5U)) {
		return -EINVAL;
	}
	struct research_trace *const trace = calloc(1U, sizeof(*trace));
	if (trace == NULL) {
		return -ENOMEM;
	}
	trace->founder = founder;
	*out = trace;
	return 0;
}

void research_trace_close(struct research_trace *trace)
{
	free(trace);
}

static void flux_add(struct trace_flux *out, const struct toy_factory_resource_flux *in,
		     uint16_t repair, bool first)
{
	if (first) {
		out->before = in->before;
	}
	/* At most 256 ecology samples per lineage/day, each flux fits uint16_t. */
#define ADD(field) out->field += in->field
	ADD(income);
	ADD(overflow);
	ADD(endowment);
	ADD(upkeep_due);
	ADD(upkeep_paid);
	ADD(growth);
	ADD(seeds);
	ADD(discarded);
#undef ADD
	out->repair += repair;
	out->after = in->after;
}

static int plant_add(struct research_trace *trace,
		     const struct toy_factory_maintenance_sample *sample, uint32_t tick,
		     uint32_t day, bool maintenance)
{
	struct trace_plant *row = NULL;
	for (uint32_t i = trace->plant_count; i > 0U; --i) {
		struct trace_plant *const candidate = &trace->plants[i - 1U];
		if (candidate->day != day) {
			break;
		}
		if (candidate->lineage == sample->budget.lineage) {
			row = candidate;
			break;
		}
	}
	if (row == NULL) {
		if (trace->plant_count == TRACE_PLANT_ROWS) {
			return -ENOSPC;
		}
		row = &trace->plants[trace->plant_count++];
		row->day = day;
		row->lineage = sample->budget.lineage;
		row->first_tick = tick;
		row->first = *sample;
	}
	const struct toy_factory_resource_sample *const budget = &sample->budget;
	flux_add(&row->energy, &budget->energy, sample->renewal_energy, row->samples == 0U);
	flux_add(&row->water, &budget->water, sample->renewal_water, row->samples == 0U);
	++row->samples;
	row->maintenance += maintenance && !budget->born ? 1U : 0U;
	row->energy_short += budget->energy.upkeep_paid < budget->energy.upkeep_due ? 1U : 0U;
	row->water_short += budget->water.upkeep_paid < budget->water.upkeep_due ? 1U : 0U;
	row->last_tick = tick;
	row->last = *sample;
	row->born |= budget->born;
	row->died |= budget->died;
	if (budget->stress_after > row->stress_max) {
		row->stress_max = budget->stress_after;
	}
#define ADD(field) row->field += sample->field
	ADD(observations);
	ADD(proposals);
	ADD(renewals);
	ADD(worn);
	ADD(restored);
	ADD(condition_endowment);
#undef ADD
	return 0;
}

static void checks_add(struct trace_checks *out,
		       const struct picosystem_garden_seed_attempt *attempt, bool no_living)
{
	if (attempt->outcome == PICOSYSTEM_GARDEN_SEED_EXPIRED) {
		++out->expired;
		return; /* Expiry precedes checks; its zero mask is NOT an open site. */
	}
	if ((out->checks == 0U) || (attempt->light < out->light_min)) {
		out->light_min = attempt->light;
	}
	if ((out->checks == 0U) || (attempt->moisture < out->moisture_min)) {
		out->moisture_min = attempt->moisture;
	}
	if (attempt->light > out->light_max) {
		out->light_max = attempt->light;
	}
	if (attempt->moisture > out->moisture_max) {
		out->moisture_max = attempt->moisture;
	}
	++out->checks;
	++out->masks[attempt->blockers];
	if (no_living) {
		++out->no_living_masks[attempt->blockers];
	}
	out->germinated += attempt->outcome == PICOSYSTEM_GARDEN_SEED_GERMINATED ? 1U : 0U;
	for (uint8_t i = 0U; i < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++i) {
		out->open_sites[i] += attempt->sites[i] == 0U ? 1U : 0U;
	}
}

static int seed_add(struct research_trace *trace,
		    const struct picosystem_garden_seed_attempt *attempt, uint32_t tick,
		    uint32_t day, bool no_living)
{
	const uint32_t age_ticks = (uint32_t)attempt->age * PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR;
	if ((age_ticks > tick) || (attempt->blockers >= TRACE_MASKS) ||
	    (attempt->outcome > PICOSYSTEM_GARDEN_SEED_GERMINATED)) {
		return -EINVAL;
	}
	const uint32_t birth = tick - age_ticks;
	struct trace_seed *row = NULL;
	for (uint32_t i = 0U; i < trace->seed_count; ++i) {
		struct trace_seed *const candidate = &trace->seeds[i];
		if ((candidate->parent == attempt->parent) && (candidate->birth_tick == birth) &&
		    (candidate->column == attempt->column)) {
			row = candidate;
			break;
		}
	}
	if (row == NULL) {
		if (trace->seed_count == TRACE_SEEDS) {
			return -ENOSPC;
		}
		row = &trace->seeds[trace->seed_count++];
		row->parent = attempt->parent;
		row->birth_tick = birth;
		row->column = attempt->column;
		row->generation = attempt->generation;
		row->species = attempt->species;
		row->first_tick = tick;
	}
	if ((row->outcome != PICOSYSTEM_GARDEN_SEED_WAIT) ||
	    (row->generation != attempt->generation) || (row->species != attempt->species)) {
		return -EINVAL;
	}
	row->last_tick = tick;
	row->outcome = attempt->outcome;
	row->child = attempt->child;
	checks_add(&row->checks, attempt, no_living);
	checks_add(&trace->days[day], attempt, no_living);
	return 0;
}

int research_trace_record(struct research_trace *trace,
			  const struct picosystem_garden_world *before,
			  const struct picosystem_garden_world *after,
			  const struct picosystem_garden_resource_audit *resources,
			  const struct picosystem_garden_seed_audit *seeds, const uint8_t *roots,
			  uint32_t count)
{
	if ((trace == NULL) || (before == NULL) || (after == NULL) || (resources == NULL) ||
	    (seeds == NULL) || (roots == NULL) || !seeds->ecology_step ||
	    (seeds->count > PICOSYSTEM_GARDEN_MAX_SEEDS) ||
	    (after->logic_tick_count > RESEARCH_TRACE_STOP) ||
	    (after->logic_tick_count !=
	     (trace->ecology_steps + 1U) * PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR)) {
		return -EINVAL;
	}
	struct toy_factory_maintenance_step step;
	int err = toy_factory_maintenance_step_read(before, after, resources, &step);
	if (err != 0) {
		return err;
	}
	const uint32_t day = (step.tick - 1U) / RESEARCH_DAY_TICKS;
	uint32_t living = 0U;
	for (uint8_t i = 0U; i < step.count; ++i) {
		const struct toy_factory_maintenance_sample *const sample = &step.plants[i];
		const struct toy_factory_resource_sample *const budget = &sample->budget;
		if ((budget->lineage == 0U) || (budget->lineage > count)) {
			return -EINVAL;
		}
		if (roots[budget->lineage] == trace->founder) {
			err = plant_add(trace, sample, step.tick, day, step.maintenance);
			if (err != 0) {
				return err;
			}
			/* Start of seed checks is after upkeep, before newborns. */
			living += !budget->born && !budget->died ? 1U : 0U;
		}
	}
	for (uint8_t i = 0U; i < seeds->count; ++i) {
		const struct picosystem_garden_seed_attempt *const attempt = &seeds->attempts[i];
		if ((attempt->parent == 0U) || (attempt->parent > count)) {
			return -EINVAL;
		}
		if (roots[attempt->parent] == trace->founder) {
			err = seed_add(trace, attempt, step.tick, day, living == 0U);
			if (err != 0) {
				return err;
			}
			living += attempt->outcome == PICOSYSTEM_GARDEN_SEED_GERMINATED ? 1U : 0U;
		}
	}
	++trace->ecology_steps;
	return 0;
}

static void write_flux(FILE *stream, const struct trace_flux *value)
{
	fprintf(stream, "{\"before\":%u,\"after\":%u", value->before, value->after);
#define WRITE(field) fprintf(stream, ",\"" #field "\":%" PRIu32, value->field)
	WRITE(income);
	WRITE(overflow);
	WRITE(endowment);
	WRITE(upkeep_due);
	WRITE(upkeep_paid);
	WRITE(growth);
	WRITE(seeds);
	WRITE(discarded);
	WRITE(repair);
#undef WRITE
	fputc('}', stream);
}

static void write_counts(FILE *stream, const uint32_t *counts, size_t count)
{
	bool first = true;
	fputc('{', stream);
	for (size_t i = 0U; i < count; ++i) {
		if (counts[i] != 0U) {
			fprintf(stream, "%s\"%zu\":%" PRIu32, first ? "" : ",", i, counts[i]);
			first = false;
		}
	}
	fputc('}', stream);
}

static void write_checks(FILE *stream, const struct trace_checks *row)
{
	fprintf(stream,
		"{\"checks\":%" PRIu32 ",\"expired\":%" PRIu32 ",\"germinated\":%" PRIu32
		",\"light_min\":%u,\"light_max\":%u,"
		"\"moisture_min\":%u,\"moisture_max\":%u,\"masks\":",
		row->checks, row->expired, row->germinated, row->light_min, row->light_max,
		row->moisture_min, row->moisture_max);
	write_counts(stream, row->masks, TRACE_MASKS);
	fputs(",\"no_living_masks\":", stream);
	write_counts(stream, row->no_living_masks, TRACE_MASKS);
	fputs(",\"open_sites\":", stream);
	write_counts(stream, row->open_sites, PICOSYSTEM_GARDEN_GRID_COLUMNS);
	fputc('}', stream);
}

int research_trace_write(const struct research_trace *trace, FILE *stream, uint32_t tick)
{
	if ((trace == NULL) || (stream == NULL) || (tick > RESEARCH_TRACE_STOP) ||
	    (trace->ecology_steps != tick / PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR)) {
		return -EINVAL;
	}
	fprintf(stream,
		"{\"schema\":\"garden-population-trace-v1\",\"complete\":true,"
		"\"founder\":%u,\"ticks\":%" PRIu32 ",\"ecology_steps\":%" PRIu32
		",\"plant_days\":[",
		trace->founder, tick, trace->ecology_steps);
	for (uint32_t i = 0U; i < trace->plant_count; ++i) {
		const struct trace_plant *const row = &trace->plants[i];
		fprintf(stream, "%s{\"day\":%" PRIu32, i == 0U ? "" : ",", row->day);
#define WRITE(field) fprintf(stream, ",\"" #field "\":%" PRIu32, row->field)
		WRITE(lineage);
		WRITE(first_tick);
		WRITE(last_tick);
		WRITE(samples);
		WRITE(maintenance);
		WRITE(energy_short);
		WRITE(water_short);
		WRITE(observations);
		WRITE(proposals);
		WRITE(renewals);
		WRITE(worn);
		WRITE(restored);
		WRITE(condition_endowment);
#undef WRITE
		fprintf(stream,
			",\"born\":%s,\"died\":%s,\"stress_max\":%u,\"stress_after\":%u,"
			"\"nodes_before\":%u,\"nodes_after\":%u,\"leaves_before\":%u,"
			"\"leaves_after\":%u,\"condition_before\":%u,\"condition_after\":%u,"
			"\"energy\":",
			row->born ? "true" : "false", row->died ? "true" : "false", row->stress_max,
			row->last.budget.stress_after, row->first.budget.nodes_before,
			row->last.budget.nodes_after, row->first.leaves_before,
			row->last.leaves_after, row->first.condition_before,
			row->last.condition_after);
		write_flux(stream, &row->energy);
		fputs(",\"water\":", stream);
		write_flux(stream, &row->water);
		fputc('}', stream);
	}
	fputs("],\"seeds\":[", stream);
	for (uint32_t i = 0U; i < trace->seed_count; ++i) {
		const struct trace_seed *const row = &trace->seeds[i];
		fprintf(stream,
			"%s{\"parent\":%" PRIu32 ",\"birth_tick\":%" PRIu32
			",\"first_tick\":%" PRIu32 ",\"last_tick\":%" PRIu32 ",\"child\":%" PRIu32
			",\"column\":%u,\"generation\":%u,"
			"\"species\":%u,\"outcome\":%u,\"attempts\":",
			i == 0U ? "" : ",", row->parent, row->birth_tick, row->first_tick,
			row->last_tick, row->child, row->column, row->generation, row->species,
			row->outcome);
		write_checks(stream, &row->checks);
		fputc('}', stream);
	}
	fputs("],\"seed_days\":[", stream);
	const uint32_t days = (tick + RESEARCH_DAY_TICKS - 1U) / RESEARCH_DAY_TICKS;
	for (uint32_t i = 0U; i < days; ++i) {
		if (i != 0U) {
			fputc(',', stream);
		}
		write_checks(stream, &trace->days[i]);
	}
	fputs("]}\n", stream);
	return ferror(stream) ? -EIO : 0;
}
