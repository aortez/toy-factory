/* SPDX-License-Identifier: Apache-2.0 */
#include "research_budget.h"

#include <errno.h>
#include <inttypes.h>
#include <stdlib.h>

static const uint32_t events[] = {587040U, 621660U, 709920U, 733500U,
				  733560U, 744540U, 764520U, 867420U};

struct budget_record {
	uint32_t tick;
	struct toy_factory_maintenance_sample sample;
	struct picosystem_garden_reproduction_visit visit;
	bool maintenance;
};

struct research_budget {
	uint16_t count;
	struct budget_record rows[RESEARCH_BUDGET_LIMIT];
};

bool research_budget_active(uint32_t tick)
{
	if (tick % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR != 0U) {
		return false;
	}
	for (size_t i = 0U; i < sizeof(events) / sizeof(events[0]); ++i) {
		if (tick > events[i] - 3840U && tick <= events[i] + 960U) {
			return true;
		}
	}
	return false;
}

static uint32_t next_tick(uint32_t previous)
{
	for (size_t i = 0U; i < sizeof(events) / sizeof(events[0]); ++i) {
		const uint32_t first = events[i] - 3840U + PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR;
		const uint32_t next = previous + PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR;
		const uint32_t tick = next > first ? next : first;
		if (tick <= events[i] + 960U) {
			return tick;
		}
	}
	return 0U;
}

int research_budget_open(struct research_budget **out)
{
	if (out == NULL) {
		return -EINVAL;
	}
	struct research_budget *const trace = calloc(1U, sizeof(*trace));
	if (trace == NULL) {
		return -ENOMEM;
	}
	*out = trace;
	return 0;
}

void research_budget_close(struct research_budget *trace)
{
	free(trace);
}

int research_budget_record(struct research_budget *trace,
			   const struct toy_factory_maintenance_step *step,
			   const struct picosystem_garden_reproduction_audit *audit)
{
	if (trace == NULL || step == NULL || step->count > PICOSYSTEM_GARDEN_MAX_PLANTS) {
		return -EINVAL;
	}
	if (trace->count == RESEARCH_BUDGET_LIMIT) {
		return -ENOSPC;
	}
	const uint32_t expected =
		next_tick(trace->count ? trace->rows[trace->count - 1U].tick : 0U);
	if (expected == 0U || step->tick != expected ||
	    step->maintenance != (step->tick % 60U == 0U)) {
		return -ERANGE;
	}
	const struct toy_factory_maintenance_sample *sample = NULL;
	for (uint8_t i = 0U; i < step->count; ++i) {
		if (step->plants[i].budget.lineage == RESEARCH_BUDGET_LINEAGE) {
			if (sample != NULL) {
				return -EFAULT;
			}
			sample = &step->plants[i];
		}
	}
	if (sample == NULL || sample->budget.born || sample->budget.died ||
	    sample->budget.point_mask != 63U) {
		return -EFAULT;
	}
	struct budget_record row = {
		.tick = step->tick, .sample = *sample, .maintenance = step->maintenance};
	if (step->maintenance) {
		if (audit == NULL || !audit->ecology_step ||
		    audit->count > PICOSYSTEM_GARDEN_MAX_PLANTS) {
			return -EINVAL;
		}
		const struct picosystem_garden_reproduction_visit *visit = NULL;
		for (uint8_t i = 0U; i < audit->count; ++i) {
			if (audit->visits[i].lineage == RESEARCH_BUDGET_LINEAGE) {
				if (visit != NULL) {
					return -EFAULT;
				}
				visit = &audit->visits[i];
			}
		}
		if (visit == NULL ||
		    visit->energy != sample->budget.energy.points[TOY_FACTORY_RESOURCE_GROWTH] ||
		    visit->water != sample->budget.water.points[TOY_FACTORY_RESOURCE_GROWTH] ||
		    visit->produced != (sample->budget.energy.seeds != 0U)) {
			return -EFAULT;
		}
		row.visit = *visit;
	} else if (audit != NULL) {
		return -EINVAL;
	}
	trace->rows[trace->count++] = row;
	return 0;
}

static void write_flux(FILE *stream, const struct toy_factory_resource_flux *f, uint16_t repair)
{
	fputs("{\"points\":[", stream);
	for (uint8_t i = 0U; i < TOY_FACTORY_RESOURCE_POINT_COUNT; ++i) {
		fprintf(stream, "%s%u", i ? "," : "", f->points[i]);
	}
	fprintf(stream, "],\"repair\":%u", repair);
#define WRITE(field) fprintf(stream, ",\"" #field "\":%u", f->field)
	WRITE(before);
	WRITE(income);
	WRITE(overflow);
	WRITE(endowment);
	WRITE(upkeep_due);
	WRITE(upkeep_paid);
	WRITE(growth);
	WRITE(seeds);
	WRITE(discarded);
	WRITE(after);
#undef WRITE
	fputc('}', stream);
}

int research_budget_write(const struct research_budget *trace, FILE *stream)
{
	if (trace == NULL || stream == NULL) {
		return -EINVAL;
	}
	if (trace->count == 0U || next_tick(trace->rows[trace->count - 1U].tick) != 0U) {
		return -ERANGE;
	}
	fprintf(stream,
		"{\"schema\":\"garden-reproduction-budget-v1\",\"complete\":true,\"lineage\":%u,"
		"\"before_ticks\":3840,\"after_ticks\":960,\"limit\":%u,\"events\":[",
		RESEARCH_BUDGET_LINEAGE, RESEARCH_BUDGET_LIMIT);
	for (size_t i = 0U; i < sizeof(events) / sizeof(events[0]); ++i) {
		fprintf(stream, "%s%" PRIu32, i ? "," : "", events[i]);
	}
	fputs("],\"rows\":[", stream);
	for (uint16_t i = 0U; i < trace->count; ++i) {
		const struct budget_record *const row = &trace->rows[i];
		const struct toy_factory_maintenance_sample *const s = &row->sample;
		const struct toy_factory_resource_sample *const b = &s->budget;
		fprintf(stream, "%s{\"tick\":%" PRIu32 ",\"maintenance\":%s", i ? "," : "",
			row->tick, row->maintenance ? "true" : "false");
#define WRITE(field) fprintf(stream, ",\"" #field "\":%u", s->field)
		WRITE(leaves_before);
		WRITE(leaves_after);
		WRITE(condition_before);
		WRITE(condition_after);
		WRITE(condition_endowment);
		WRITE(worn);
		WRITE(restored);
		WRITE(observations);
		WRITE(proposals);
		WRITE(renewals);
		WRITE(remainder_before);
		WRITE(remainder_uptake);
		WRITE(remainder_after);
		WRITE(remainder_discarded);
#undef WRITE
		fprintf(stream,
			",\"nodes_before\":%u,\"nodes_after\":%u,\"stress_before\":%u,\"stress_"
			"after\":%u,\"energy\":",
			b->nodes_before, b->nodes_after, b->stress_before, b->stress_after);
		write_flux(stream, &b->energy, s->renewal_energy);
		fputs(",\"water\":", stream);
		write_flux(stream, &b->water, s->renewal_water);
		fputs(",\"visit\":", stream);
		if (row->maintenance) {
			const struct picosystem_garden_reproduction_visit *const v = &row->visit;
			fprintf(stream,
				"{\"blockers\":%u,\"seed_count\":%u,\"energy_required\":%" PRId32
				",\"water_required\":%" PRId32 "}",
				v->blockers, v->seed_count, v->energy_required, v->water_required);
		} else {
			fputs("null", stream);
		}
		fputc('}', stream);
	}
	fputs("]}\n", stream);
	return ferror(stream) || fflush(stream) != 0 ? -EIO : 0;
}
