/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_reach.h"
#include "garden_dispersal.h"

#include <errno.h>
#include <inttypes.h>

static void print_sites(FILE *stream, const uint8_t *sites)
{
	fputc('"', stream);
	for (uint8_t c = 0U; c < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++c) {
		fprintf(stream, "%02x", sites[c]);
	}
	fputc('"', stream);
}

int toy_factory_garden_reach_print(FILE *stream, const struct picosystem_garden_world *world,
				   const struct picosystem_garden_seed_audit *seeds)
{
	if ((stream == NULL) || (world == NULL) || (seeds == NULL) || !seeds->ecology_step ||
	    (seeds->count > PICOSYSTEM_GARDEN_MAX_SEEDS)) {
		return -EINVAL;
	}
#if defined(TOY_FACTORY_GARDEN_WIDE_DISPERSAL) || defined(TOY_FACTORY_GARDEN_FLOWER_DISPERSAL)
	return -ENOTSUP;
#endif
	struct picosystem_garden_seed_sites sites;
	const int err = picosystem_garden_world_seed_sites(world, &sites);
	if (err != 0) {
		return err;
	}
	/* Reproduction cannot kill a parent, mutate its genome or compact its slot.
	 * Age-zero seeds therefore still have their actual producing parent here.
	 */
	const struct picosystem_garden_plant *parents[PICOSYSTEM_GARDEN_MAX_SEEDS] = {0};
	for (uint8_t i = 0U; i < world->seed_count; ++i) {
		const struct picosystem_garden_seed *const seed = &world->seeds[i];
		if (seed->age_ecology_ticks != 0U) {
			continue;
		}
		for (uint8_t j = 0U; j < world->plant_count; ++j) {
			const struct picosystem_garden_plant *const parent = &world->plants[j];
			if (parent->lineage_id == seed->parent_lineage_id) {
				if ((parent->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) ||
				    !(sites.dispersal_columns[j] & (UINT32_C(1) << seed->column))) {
					return -EFAULT;
				}
				parents[i] = parent;
				break;
			}
		}
		if (parents[i] == NULL) {
			return -EFAULT;
		}
	}
	fprintf(stream, "{\"tick\":%" PRIu32 ",\"purchases\":[", world->logic_tick_count);
	bool first = true;
	for (uint8_t i = 0U; i < world->seed_count; ++i) {
		const struct picosystem_garden_plant *const p = parents[i];
		if (p == NULL) {
			continue;
		}
		fprintf(stream,
			"%s{\"parent\":%" PRIu32
			",\"column\":%u,\"origin\":%u,\"dispersal\":%d,\"choices\":[",
			first ? "" : ",", p->lineage_id, world->seeds[i].column, p->base_column,
			p->genome.dispersal);
		first = false;
		for (uint32_t choice = 0U;
		     choice < picosystem_garden_dispersal_choices_at(world->logic_tick_count);
		     ++choice) {
			fprintf(stream, "%s%u", choice ? "," : "",
				picosystem_garden_dispersed_column_at(p->base_column,
								      p->genome.dispersal, choice,
								      world->logic_tick_count));
		}
		fputs("],\"sites\":", stream);
		print_sites(stream, sites.blockers);
		fputc('}', stream);
	}
	fputs("],\"checks\":[", stream);
	for (uint8_t i = 0U; i < seeds->count; ++i) {
		const struct picosystem_garden_seed_attempt *const a = &seeds->attempts[i];
		fprintf(stream, "%s[%" PRIu32 ",%u,%u,%u,%u,%" PRIu32 ",", i ? "," : "", a->parent,
			a->age, a->column, a->blockers, a->outcome, a->child);
		if (a->outcome == PICOSYSTEM_GARDEN_SEED_EXPIRED) {
			fputs("null", stream);
		} else {
			print_sites(stream, a->sites);
		}
		fputc(']', stream);
	}
	fputs("]}\n", stream);
	return ferror(stream) ? -EIO : 0;
}
