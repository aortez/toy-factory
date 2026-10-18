/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_placement.h"
#include "garden_dispersal.h"

#include <errno.h>
#include <inttypes.h>

int toy_factory_garden_placement_choose(const struct picosystem_garden_seed_placement *o,
					uint8_t enabled, uint8_t *choice)
{
	if ((o == NULL) || (choice == NULL)) {
		return -EINVAL;
	}
	const uint8_t choices = picosystem_garden_dispersal_choices_at(o->logic_tick);
	if ((enabled > 1U) || (o->parent == 0U) || (o->origin >= PICOSYSTEM_GARDEN_GRID_COLUMNS) ||
	    (o->dispersal < -2) || (o->dispersal > 2) ||
	    (choices > PICOSYSTEM_GARDEN_PLACEMENT_CHOICES) ||
	    (o->blocked_choices >= (1U << choices))) {
		return -ERANGE;
	}
	uint8_t clear[PICOSYSTEM_GARDEN_PLACEMENT_CHOICES];
	uint8_t count = 0U;
	for (uint8_t c = 0U; c < choices; ++c) {
		if (o->columns[c] != picosystem_garden_dispersed_column_at(o->origin, o->dispersal,
									   c, o->logic_tick)) {
			return -ERANGE;
		}
		for (uint8_t previous = 0U; previous < c; ++previous) {
			if ((o->columns[c] == o->columns[previous]) &&
			    (((o->blocked_choices >> c) & 1U) !=
			     ((o->blocked_choices >> previous) & 1U))) {
				return -ERANGE;
			}
		}
		if ((o->blocked_choices & (1U << c)) == 0U) {
			clear[count++] = c;
		}
	}
	uint8_t selected = (uint8_t)(o->random % choices);
	if ((enabled != 0U) && (count != 0U) && ((o->blocked_choices & (1U << selected)) != 0U)) {
		selected = clear[(o->random / choices) % count];
	}
	*choice = selected;
	return 0;
}

int toy_factory_garden_placement_decide(const struct picosystem_garden_seed_placement *o,
					uint8_t *choice, const void *opaque)
{
	const struct toy_factory_garden_placement_context *const context = opaque;
	if ((context == NULL) || (context->config == NULL) ||
	    (context->config->version != TOY_FACTORY_GARDEN_PLACEMENT_VERSION) ||
	    (choice == NULL)) {
		return -EINVAL;
	}
	uint8_t selected;
	const int err = toy_factory_garden_placement_choose(o, context->config->enabled, &selected);
	if (err != 0) {
		return err;
	}
	if (context->audit != NULL) {
		if (context->audit->count >= PICOSYSTEM_GARDEN_MAX_SEEDS) {
			return -ENOSPC;
		}
		context->audit->purchases[context->audit->count++] =
			(struct toy_factory_garden_placement_receipt){.observation = *o,
								      .selected = selected};
	}
	*choice = selected;
	return 0;
}

int toy_factory_garden_placement_print(FILE *stream, uint32_t tick,
				       const struct toy_factory_garden_placement_audit *audit)
{
	if ((stream == NULL) || (audit == NULL) || !audit->ecology_step ||
	    (audit->count > PICOSYSTEM_GARDEN_MAX_SEEDS)) {
		return -EINVAL;
	}
	fprintf(stream, "{\"tick\":%" PRIu32 ",\"purchases\":[", tick);
	for (uint8_t i = 0U; i < audit->count; ++i) {
		const struct toy_factory_garden_placement_receipt *const r = &audit->purchases[i];
		const struct picosystem_garden_seed_placement *const o = &r->observation;
		fprintf(stream,
			"%s{\"parent\":%" PRIu32 ",\"random\":%" PRIu32
			",\"origin\":%u,\"dispersal\":%d,\"blocked\":%u,\"selected\":%u,"
			"\"choices\":[",
			i ? "," : "", o->parent, o->random, o->origin, o->dispersal,
			o->blocked_choices, r->selected);
		for (uint8_t c = 0U; c < picosystem_garden_dispersal_choices_at(o->logic_tick);
		     ++c) {
			fprintf(stream, "%s%u", c ? "," : "", o->columns[c]);
		}
		fputs("]}", stream);
	}
	fputs("]}\n", stream);
	return ferror(stream) ? -EIO : 0;
}
