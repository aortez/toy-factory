/* SPDX-License-Identifier: Apache-2.0 */
#include "research_foliage.h"
#include "garden_light.h"
#include "research_canopy.h"

#include <errno.h>
#include <inttypes.h>
#include <stdlib.h>
#include <string.h>

struct canopy_row {
	struct picosystem_garden_shade_source sources[PICOSYSTEM_GARDEN_MAX_NODES];
	uint8_t light[PICOSYSTEM_GARDEN_LIGHT_CELL_COUNT];
	struct picosystem_garden_sun sun;
	uint32_t tick;
	uint16_t count;
};

struct foliage_leaf {
	uint16_t node;
	uint8_t x, y, column, row, light, condition;
};

struct foliage_row {
	struct toy_factory_maintenance_sample sample;
	struct foliage_leaf leaves[RESEARCH_FOLIAGE_LEAVES];
	uint32_t tick;
	uint16_t count, selected, energy;
	uint8_t remainder, action, phase, strength;
};

struct research_foliage {
	uint32_t lineage;
	uint16_t count;
	bool pending;
	struct foliage_row staged;
	struct foliage_row rows[RESEARCH_FOLIAGE_ROWS];
	struct canopy_row *canopy;
	uint8_t canopy_count;
};

bool research_foliage_active(uint32_t tick)
{
	return tick > RESEARCH_FOLIAGE_FIRST && tick <= RESEARCH_FOLIAGE_END &&
	       tick % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR == 0U;
}

int research_foliage_open(uint32_t lineage, struct research_foliage **out)
{
	if (out == NULL || (lineage != 17U && lineage != 19U)) {
		return -EINVAL;
	}
	struct research_foliage *const trace = calloc(1U, sizeof(*trace));
	if (trace == NULL) {
		return -ENOMEM;
	}
	trace->lineage = lineage;
	*out = trace;
	return 0;
}

void research_foliage_close(struct research_foliage *trace)
{
	if (trace != NULL) {
		free(trace->canopy);
	}
	free(trace);
}

int research_foliage_canopy_start(struct research_foliage *trace)
{
	if (trace == NULL || trace->canopy != NULL || trace->count != 0U || trace->pending) {
		return -EINVAL;
	}
	trace->canopy = calloc(RESEARCH_CANOPY_ROWS, sizeof(*trace->canopy));
	return trace->canopy == NULL ? -ENOMEM : 0;
}

static int canopy_record(struct research_foliage *trace,
			 const struct picosystem_garden_world *before,
			 const struct picosystem_garden_world *current)
{
	const uint32_t tick = current->logic_tick_count;
	if (trace->canopy == NULL || tick <= RESEARCH_CANOPY_FIRST || tick > RESEARCH_CANOPY_END) {
		return 0;
	}
	if (trace->canopy_count == RESEARCH_CANOPY_ROWS ||
	    tick != RESEARCH_CANOPY_FIRST + (trace->canopy_count + 1U) * 15U) {
		return -ERANGE;
	}
	struct picosystem_garden_uptake_audit audit;
	const int err = research_canopy_project(before, &audit);
	if (err != 0) {
		return err;
	}
	const struct picosystem_garden_sun sun = picosystem_garden_world_sun(current);
	if (audit.tick != tick || audit.sun.phase != sun.phase ||
	    audit.sun.strength != sun.strength || audit.sun.ray_step_x_q4 != sun.ray_step_x_q4 ||
	    memcmp(audit.light, current->light, sizeof(audit.light)) != 0) {
		return -EFAULT;
	}
	struct canopy_row *const row = &trace->canopy[trace->canopy_count++];
	row->tick = tick;
	row->sun = sun;
	row->count = audit.source_count;
	memcpy(row->sources, audit.sources, sizeof(row->sources));
	memcpy(row->light, audit.light, sizeof(row->light));
	return 0;
}

static uint8_t cell(uint8_t pixel, uint8_t origin, uint8_t limit)
{
	const uint8_t index =
		pixel <= origin ? 0U : (uint8_t)((pixel - origin) / PICOSYSTEM_GARDEN_CELL_PIXELS);
	return index < limit ? index : (uint8_t)(limit - 1U);
}

static bool leaf(const struct picosystem_garden_node *node)
{
	return node->kind == PICOSYSTEM_GARDEN_NODE_STEM &&
	       (node->flags & PICOSYSTEM_GARDEN_NODE_LEAF) != 0U;
}

int research_foliage_decide(const struct picosystem_garden_world *world,
			    const struct picosystem_garden_leaf_policy *candidate,
			    const struct picosystem_garden_leaf_observation *observation,
			    const struct picosystem_garden_agent_memory *memory,
			    struct picosystem_garden_leaf_decision *decision, const void *opaque)
{
	const struct research_foliage_context *const context = opaque;
	if (context == NULL || context->trace == NULL || context->next == NULL ||
	    context->next->decide == NULL || world == NULL || observation == NULL ||
	    candidate == NULL || memory == NULL || decision == NULL ||
	    world->plant_count > PICOSYSTEM_GARDEN_MAX_PLANTS ||
	    world->node_count > PICOSYSTEM_GARDEN_MAX_NODES ||
	    observation->plant_index >= world->plant_count ||
	    observation->node_index >= world->node_count) {
		return -EINVAL;
	}
	struct research_foliage *const trace = context->trace;
	const struct picosystem_garden_plant *const plant =
		&world->plants[observation->plant_index];
	const bool selected = plant->lineage_id == trace->lineage;
	struct foliage_row row = {0};
	if (selected) {
		if (trace->count == RESEARCH_FOLIAGE_ROWS || trace->pending ||
		    world->logic_tick_count !=
			    RESEARCH_FOLIAGE_FIRST +
				    (trace->count + 1U) * PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR ||
		    (plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) != 0U) {
			return -ERANGE;
		}
		row.tick = world->logic_tick_count;
		row.selected = observation->node_index;
		row.energy = plant->stored_energy;
		row.remainder = plant->leaf_energy_remainder;
		const struct picosystem_garden_sun sun = picosystem_garden_world_sun(world);
		row.phase = sun.phase;
		row.strength = sun.strength;
		bool found = false;
		for (uint16_t i = 0U; i < world->node_count; ++i) {
			const struct picosystem_garden_node *const n = &world->nodes[i];
			if (n->plant_index != observation->plant_index || !leaf(n)) {
				continue;
			}
			if (row.count == RESEARCH_FOLIAGE_LEAVES ||
			    n->growth_progress < PICOSYSTEM_GARDEN_LEAF_ACTIVE_PROGRESS) {
				return -ENOTSUP;
			}
			const uint8_t column = cell(n->x, PICOSYSTEM_GARDEN_ORIGIN_X_PIXELS,
						    PICOSYSTEM_GARDEN_GRID_COLUMNS);
			const uint8_t r = cell(n->y, PICOSYSTEM_GARDEN_CANOPY_TOP_PIXELS,
					       PICOSYSTEM_GARDEN_CANOPY_ROWS);
			row.leaves[row.count++] = (struct foliage_leaf){
				.node = i,
				.x = n->x,
				.y = n->y,
				.column = column,
				.row = r,
				.light = world->light[r * PICOSYSTEM_GARDEN_GRID_COLUMNS + column],
				.condition = world->leaf_condition[i]};
			found |= i == row.selected;
		}
		if (!found || row.count != observation->mature_leaf_count) {
			return -EFAULT;
		}
	}
	const int err = context->next->decide(world, candidate, observation, memory, decision,
					      context->next->context);
	if (err == 0 && selected) {
		const int canopy_err = canopy_record(trace, context->before, world);
		if (canopy_err != 0) {
			return canopy_err;
		}
		row.action = (uint8_t)decision->action;
		trace->staged = row;
		trace->pending = true;
	}
	return err;
}

int research_foliage_finish(struct research_foliage *trace,
			    const struct picosystem_garden_world *before,
			    const struct toy_factory_maintenance_step *step)
{
	if (trace == NULL || before == NULL || step == NULL ||
	    before->plant_count > PICOSYSTEM_GARDEN_MAX_PLANTS ||
	    before->node_count > PICOSYSTEM_GARDEN_MAX_NODES ||
	    step->count > PICOSYSTEM_GARDEN_MAX_PLANTS) {
		return -EINVAL;
	}
	if (!trace->pending || trace->count == RESEARCH_FOLIAGE_ROWS ||
	    step->tick != trace->staged.tick || before->logic_tick_count + 1U != step->tick) {
		return -ERANGE;
	}
	const struct toy_factory_maintenance_sample *sample = NULL;
	for (uint8_t i = 0U; i < step->count; ++i) {
		if (step->plants[i].budget.lineage == trace->lineage) {
			if (sample != NULL) {
				return -EFAULT;
			}
			sample = &step->plants[i];
		}
	}
	struct foliage_row *const row = &trace->staged;
	if (sample == NULL || sample->budget.born || sample->budget.died ||
	    sample->budget.point_mask != 63U ||
	    sample->budget.nodes_before != sample->budget.nodes_after ||
	    sample->leaves_before != row->count || sample->leaves_after != row->count ||
	    sample->observations != 1U || sample->budget.energy.growth != 0U ||
	    sample->budget.water.growth != 0U || row->remainder != sample->remainder_uptake ||
	    row->energy != sample->budget.energy.points[TOY_FACTORY_RESOURCE_GERMINATION]) {
		return -EFAULT;
	}
	uint16_t count = 0U, condition = 0U;
	uint32_t numerator = sample->remainder_before;
	/* Reclamation preserves body order but changes global node/plant indices.
	 * Match the unchanged focal leaf roster in that order, not by slot.
	 */
	for (uint16_t i = 0U; i < before->node_count; ++i) {
		const struct picosystem_garden_node *const n = &before->nodes[i];
		if (n->plant_index >= before->plant_count) {
			return -EFAULT;
		}
		if (before->plants[n->plant_index].lineage_id != trace->lineage || !leaf(n)) {
			continue;
		}
		if (count >= row->count ||
		    n->growth_progress < PICOSYSTEM_GARDEN_LEAF_ACTIVE_PROGRESS) {
			return -EFAULT;
		}
		const struct foliage_leaf *const f = &row->leaves[count++];
		const uint8_t old = before->leaf_condition[i];
		const uint8_t worn = (uint8_t)(old - ((step->maintenance && old != 0U) ? 1U : 0U));
		if (n->x != f->x || n->y != f->y || worn != f->condition) {
			return -EFAULT;
		}
		condition = (uint16_t)(condition + f->condition);
		numerator += (uint32_t)(f->light / 64U) * f->condition;
	}
	if (count != row->count || condition + sample->worn != sample->condition_before ||
	    numerator / 255U != sample->budget.energy.income ||
	    numerator % 255U != sample->remainder_uptake) {
		return -EFAULT;
	}
	row->sample = *sample;
	trace->rows[trace->count++] = *row;
	trace->pending = false;
	return 0;
}

int research_foliage_canopy_write(const struct research_foliage *trace, FILE *stream)
{
	if (trace == NULL || trace->canopy == NULL || stream == NULL) {
		return -EINVAL;
	}
	if (trace->canopy_count != RESEARCH_CANOPY_ROWS || trace->count != RESEARCH_FOLIAGE_ROWS ||
	    trace->pending) {
		return -ERANGE;
	}
	fprintf(stream,
		"{\"schema\":\"garden-canopy-sources-v1\",\"lineage\":%" PRIu32
		",\"first_tick_exclusive\":%u,\"end_tick\":%u,"
		"\"source_fields\":[\"lineage\",\"node\",\"column\",\"row\",\"center\","
		"\"neighbor\",\"dead\"],\"rows\":[",
		trace->lineage, RESEARCH_CANOPY_FIRST, RESEARCH_CANOPY_END);
	for (uint8_t i = 0U; i < trace->canopy_count; ++i) {
		const struct canopy_row *const row = &trace->canopy[i];
		fprintf(stream,
			"%s{\"tick\":%" PRIu32
			",\"phase\":%u,\"strength\":%u,\"ray\":%d,\"light\":[",
			i ? "," : "", row->tick, row->sun.phase, row->sun.strength,
			row->sun.ray_step_x_q4);
		for (uint16_t c = 0U; c < PICOSYSTEM_GARDEN_LIGHT_CELL_COUNT; ++c) {
			fprintf(stream, "%s%u", c ? "," : "", row->light[c]);
		}
		fputs("],\"sources\":[", stream);
		for (uint16_t n = 0U; n < row->count; ++n) {
			const struct picosystem_garden_shade_source *const s = &row->sources[n];
			fprintf(stream, "%s[%" PRIu32 ",%u,%u,%u,%u,%u,%s]", n ? "," : "",
				s->lineage, s->node, s->column, s->row, s->center, s->neighbor,
				s->dead ? "true" : "false");
		}
		fputs("]}", stream);
	}
	fputs("]}\n", stream);
	return ferror(stream) || fflush(stream) != 0 ? -EIO : 0;
}

int research_foliage_write(const struct research_foliage *trace, FILE *stream)
{
	if (trace == NULL || stream == NULL) {
		return -EINVAL;
	}
	if (trace->count != RESEARCH_FOLIAGE_ROWS || trace->pending) {
		return -ERANGE;
	}
	fprintf(stream,
		"{\"schema\":\"garden-foliage-uptake-v1\",\"complete\":true,\"lineage\":%" PRIu32
		",\"first_tick_exclusive\":%u,\"end_tick\":%u,\"leaf_limit\":%u,"
		"\"leaf_fields\":[\"node\",\"x\",\"y\",\"column\",\"row\",\"light\",\"condition\"],"
		"\"rows\":[",
		trace->lineage, RESEARCH_FOLIAGE_FIRST, RESEARCH_FOLIAGE_END,
		RESEARCH_FOLIAGE_LEAVES);
	for (uint16_t i = 0U; i < trace->count; ++i) {
		const struct foliage_row *const row = &trace->rows[i];
		const struct toy_factory_maintenance_sample *const s = &row->sample;
		fprintf(stream,
			"%s{\"tick\":%" PRIu32
			",\"phase\":%u,\"strength\":%u,\"selected\":%u,\"action\":%u",
			i ? "," : "", row->tick, row->phase, row->strength, row->selected,
			row->action);
#define WRITE(field) fprintf(stream, ",\"" #field "\":%u", s->field)
		WRITE(remainder_before);
		WRITE(remainder_uptake);
		WRITE(remainder_after);
		WRITE(condition_before);
		WRITE(condition_after);
		WRITE(worn);
		WRITE(restored);
		WRITE(renewals);
		WRITE(renewal_energy);
		WRITE(renewal_water);
#undef WRITE
		const struct toy_factory_resource_flux *const f = &s->budget.energy;
		fputs(",\"energy\":{\"points\":[", stream);
		for (uint8_t p = 0U; p < TOY_FACTORY_RESOURCE_POINT_COUNT; ++p) {
			fprintf(stream, "%s%u", p ? "," : "", f->points[p]);
		}
		fputs("]", stream);
#define WRITE(field) fprintf(stream, ",\"" #field "\":%u", f->field)
		WRITE(before);
		WRITE(income);
		WRITE(overflow);
		WRITE(upkeep_due);
		WRITE(upkeep_paid);
		WRITE(growth);
		WRITE(seeds);
		WRITE(after);
#undef WRITE
		fputs("},\"leaves\":[", stream);
		for (uint16_t l = 0U; l < row->count; ++l) {
			const struct foliage_leaf *const f = &row->leaves[l];
			fprintf(stream, "%s[%u,%u,%u,%u,%u,%u,%u]", l ? "," : "", f->node, f->x,
				f->y, f->column, f->row, f->light, f->condition);
		}
		fputs("]}", stream);
	}
	fputs("]}\n", stream);
	return ferror(stream) || fflush(stream) != 0 ? -EIO : 0;
}
