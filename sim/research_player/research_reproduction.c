/* SPDX-License-Identifier: Apache-2.0 */
#include "research_reproduction.h"

#include <errno.h>
#include <inttypes.h>
#include <stdlib.h>

#define MASKS 1024U
#define SAMPLES                                                                                    \
	((RESEARCH_REPRODUCTION_END - RESEARCH_REPRODUCTION_FIRST) / RESEARCH_REPRODUCTION_CADENCE)

_Static_assert(PICOSYSTEM_GARDEN_MAX_SEEDS == 8U, "Frozen seed capacity");
_Static_assert(PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR *PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR ==
		       RESEARCH_REPRODUCTION_CADENCE,
	       "Frozen reproduction cadence");
_Static_assert(PICOSYSTEM_GARDEN_REPRODUCTION_FLOWER == MASKS / 2U, "Blocker mask width");

struct lineage_counts {
	uint32_t lineage;
	uint32_t masks[MASKS];
};

struct opening {
	uint32_t tick;
	struct picosystem_garden_reproduction_audit audit;
};

struct research_reproduction {
	uint32_t samples;
	uint16_t count;
	uint16_t openings;
	struct lineage_counts lineages[RESEARCH_REPRODUCTION_LINEAGES];
	struct opening records[RESEARCH_REPRODUCTION_OPENINGS];
};

int research_reproduction_open(struct research_reproduction **out)
{
	if (out == NULL) {
		return -EINVAL;
	}
	struct research_reproduction *const trace = calloc(1U, sizeof(*trace));
	if (trace == NULL) {
		return -ENOMEM;
	}
	*out = trace;
	return 0;
}

void research_reproduction_close(struct research_reproduction *trace)
{
	free(trace);
}

int research_reproduction_growth(const struct picosystem_garden_world *world,
				 const struct picosystem_garden_agent_observation *observation,
				 const struct picosystem_garden_agent_decision *raw,
				 const struct picosystem_garden_agent_decision *applied,
				 void *context)
{
	return world != NULL && observation != NULL && raw != NULL && applied != NULL &&
			       context != NULL
		       ? 0
		       : -EINVAL;
}

int research_reproduction_record(struct research_reproduction *trace, uint32_t tick,
				 const struct picosystem_garden_reproduction_audit *audit)
{
	if (trace == NULL || audit == NULL || !audit->ecology_step ||
	    audit->count > PICOSYSTEM_GARDEN_MAX_PLANTS) {
		return -EINVAL;
	}
	if (trace->samples >= SAMPLES ||
	    tick != RESEARCH_REPRODUCTION_FIRST +
			    (trace->samples + 1U) * RESEARCH_REPRODUCTION_CADENCE) {
		return -ERANGE;
	}
	bool open = false;
	for (uint8_t i = 0U; i < audit->count; ++i) {
		const struct picosystem_garden_reproduction_visit *const v = &audit->visits[i];
		if (v->lineage == 0U || v->blockers >= MASKS ||
		    (v->blockers & PICOSYSTEM_GARDEN_REPRODUCTION_CADENCE) != 0U ||
		    v->seed_count > PICOSYSTEM_GARDEN_MAX_SEEDS ||
		    (((v->blockers & PICOSYSTEM_GARDEN_REPRODUCTION_BANK) != 0U) !=
		     (v->seed_count == PICOSYSTEM_GARDEN_MAX_SEEDS)) ||
		    v->produced != (v->blockers == 0U)) {
			return -EFAULT;
		}
		if (i != 0U &&
		    v->seed_count != (uint8_t)(audit->visits[i - 1U].seed_count +
					       (audit->visits[i - 1U].produced ? 1U : 0U))) {
			return -EFAULT;
		}
		for (uint8_t j = 0U; j < i; ++j) {
			if (audit->visits[j].lineage == v->lineage) {
				return -EFAULT;
			}
		}
		open |= v->seed_count < PICOSYSTEM_GARDEN_MAX_SEEDS;
	}
	if (open && trace->openings == RESEARCH_REPRODUCTION_OPENINGS) {
		return -ENOSPC;
	}
	for (uint8_t i = 0U; i < audit->count; ++i) {
		const struct picosystem_garden_reproduction_visit *const v = &audit->visits[i];
		uint16_t index = 0U;
		while (index < trace->count && trace->lineages[index].lineage != v->lineage) {
			++index;
		}
		if (index == trace->count) {
			if (trace->count == RESEARCH_REPRODUCTION_LINEAGES) {
				return -ENOSPC;
			}
			trace->lineages[index].lineage = v->lineage;
			++trace->count;
		}
		++trace->lineages[index].masks[v->blockers];
	}
	if (open) {
		trace->records[trace->openings++] = (struct opening){.tick = tick, .audit = *audit};
	}
	++trace->samples;
	return 0;
}

int research_reproduction_write(const struct research_reproduction *trace, FILE *stream)
{
	if (trace == NULL || stream == NULL) {
		return -EINVAL;
	}
	if (trace->samples != SAMPLES) {
		return -ERANGE;
	}
	fprintf(stream,
		"{\"schema\":\"garden-reproduction-access-v1\",\"complete\":true,\"first_tick_"
		"exclusive\":%u,\"end_tick\":%u,\"cadence\":%u,\"samples\":%" PRIu32
		",\"seed_capacity\":%u,\"lineage_limit\":%u,\"opening_limit\":%u,\"lineages\":[",
		RESEARCH_REPRODUCTION_FIRST, RESEARCH_REPRODUCTION_END,
		RESEARCH_REPRODUCTION_CADENCE, trace->samples, PICOSYSTEM_GARDEN_MAX_SEEDS,
		RESEARCH_REPRODUCTION_LINEAGES, RESEARCH_REPRODUCTION_OPENINGS);
	for (uint16_t i = 0U; i < trace->count; ++i) {
		const struct lineage_counts *const row = &trace->lineages[i];
		fprintf(stream, "%s{\"lineage\":%" PRIu32 ",\"masks\":{", i ? "," : "",
			row->lineage);
		bool comma = false;
		for (uint16_t mask = 0U; mask < MASKS; ++mask) {
			if (row->masks[mask] != 0U) {
				fprintf(stream, "%s\"%u\":%" PRIu32, comma ? "," : "", mask,
					row->masks[mask]);
				comma = true;
			}
		}
		fputs("}}", stream);
	}
	fputs("],\"openings\":[", stream);
	for (uint16_t i = 0U; i < trace->openings; ++i) {
		const struct opening *const r = &trace->records[i];
		fprintf(stream, "%s{\"tick\":%" PRIu32 ",\"visits\":[", i ? "," : "", r->tick);
		for (uint8_t j = 0U; j < r->audit.count; ++j) {
			const struct picosystem_garden_reproduction_visit *const v =
				&r->audit.visits[j];
			fprintf(stream,
				"%s{\"lineage\":%" PRIu32
				",\"blockers\":%u,\"energy\":%u,\"water\":%u,\"energy_required\":"
				"%" PRId32 ",\"water_required\":%" PRId32
				",\"immature_flowers\":%u,\"spent_flowers\":%u,\"ready_flowers\":%"
				"u,\"flower_index\":%u,\"cooldown\":%u,\"seed_count\":%u,"
				"\"stress\":%u,\"sun_strength\":%u,\"produced\":%s}",
				j ? "," : "", v->lineage, v->blockers, v->energy, v->water,
				v->energy_required, v->water_required, v->immature_flowers,
				v->spent_flowers, v->ready_flowers, v->flower_index, v->cooldown,
				v->seed_count, v->stress, v->sun_strength,
				v->produced ? "true" : "false");
		}
		fputs("]}", stream);
	}
	fputs("]}\n", stream);
	return ferror(stream) || fflush(stream) != 0 ? -EIO : 0;
}
