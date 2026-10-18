/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_uptake_trace.h"

#include <errno.h>
#include <inttypes.h>

int toy_factory_garden_uptake_header(FILE *stream,
				     const struct toy_factory_garden_uptake_window *windows,
				     size_t count, uint32_t stop)
{
	if ((stream == NULL) || (windows == NULL) || (count == 0U) ||
	    (count > TOY_FACTORY_GARDEN_UPTAKE_WINDOWS)) {
		return -EINVAL;
	}
	for (size_t i = 0U; i < count; ++i) {
		if ((windows[i].start == 0U) || (windows[i].stop < windows[i].start) ||
		    (windows[i].stop > stop) ||
		    (windows[i].start % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR != 0U) ||
		    (windows[i].stop % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR != 0U) ||
		    ((i > 0U) && (windows[i].start <= windows[i - 1U].stop))) {
			return -ERANGE;
		}
	}
	fprintf(stream, "{\"schema\":\"landing-uptake-v1\",\"stop\":%" PRIu32 ",\"windows\":[",
		stop);
	for (size_t i = 0U; i < count; ++i) {
		fprintf(stream, "%s[%" PRIu32 ",%" PRIu32 "]", i ? "," : "", windows[i].start,
			windows[i].stop);
	}
	fputs("]}\n", stream);
	return ferror(stream) ? -EIO : 0;
}

bool toy_factory_garden_uptake_selected(const struct toy_factory_garden_uptake_window *windows,
					size_t count, uint32_t tick)
{
	if ((windows == NULL) || (count > TOY_FACTORY_GARDEN_UPTAKE_WINDOWS) ||
	    (tick % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR != 0U)) {
		return false;
	}
	for (size_t i = 0U; i < count; ++i) {
		if ((tick >= windows[i].start) && (tick <= windows[i].stop)) {
			return true;
		}
	}
	return false;
}

static void hex_grid(FILE *stream, const uint8_t *grid, size_t size)
{
	fputc('"', stream);
	for (size_t i = 0U; i < size; ++i) {
		fprintf(stream, "%02x", (unsigned int)grid[i]);
	}
	fputc('"', stream);
}

int toy_factory_garden_uptake_print(FILE *stream, const struct picosystem_garden_uptake_audit *a)
{
	if ((stream == NULL) || (a == NULL) || !a->ecology_step ||
	    (a->source_count > PICOSYSTEM_GARDEN_MAX_NODES) ||
	    (a->root_count > PICOSYSTEM_GARDEN_MAX_NODES) ||
	    (a->leaf_count > PICOSYSTEM_GARDEN_MAX_NODES)) {
		return -EINVAL;
	}
	fprintf(stream, "{\"tick\":%" PRIu32 ",\"sun\":[%u,%u,%d],\"sources\":[", a->tick,
		a->sun.phase, a->sun.strength, a->sun.ray_step_x_q4);
	for (uint16_t i = 0U; i < a->source_count; ++i) {
		const struct picosystem_garden_shade_source *s = &a->sources[i];
		fprintf(stream, "%s[%u,%" PRIu32 ",%u,%u,%u,%u,%u]", i ? "," : "", s->node,
			s->lineage, s->dead ? 1U : 0U, s->column, s->row, s->center, s->neighbor);
	}
	fputs("],\"roots\":[", stream);
	for (uint16_t i = 0U; i < a->root_count; ++i) {
		const struct picosystem_garden_root_uptake *r = &a->roots[i];
		fprintf(stream, "%s[%u,%" PRIu32 ",%u,%u,%u,%u,%u,%u,%u,%u,%u]", i ? "," : "",
			r->node, r->lineage, r->slot, r->column, r->row, r->limit, r->before,
			r->taken, r->after, r->stored_before, r->stored_after);
	}
	fputs("],\"leaves\":[", stream);
	for (uint16_t i = 0U; i < a->leaf_count; ++i) {
		const struct picosystem_garden_leaf_uptake *l = &a->leaves[i];
		fprintf(stream, "%s[%u,%" PRIu32 ",%u,%u,%u,%u]", i ? "," : "", l->node, l->lineage,
			l->column, l->row, l->light, l->income);
	}
	fputs("],\"soil_before\":", stream);
	hex_grid(stream, a->soil_before, sizeof(a->soil_before));
	fputs(",\"soil_after\":", stream);
	hex_grid(stream, a->soil_after, sizeof(a->soil_after));
	fputs(",\"light\":", stream);
	hex_grid(stream, a->light, sizeof(a->light));
	fputs("}\n", stream);
	return ferror(stream) ? -EIO : 0;
}
