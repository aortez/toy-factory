/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_ledger.h"

#include <errno.h>
#include <inttypes.h>
#include <string.h>

#define STEP PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR

static int census(struct toy_factory_garden_landing_ledger *out,
		  const struct picosystem_garden_world *world,
		  const struct toy_factory_garden_lifetimes *lifetimes)
{
	if ((lifetimes->count > TOY_FACTORY_GARDEN_EVALUATION_MAX_TRACKED_LINEAGES) ||
	    (lifetimes->count != world->lineage_sequence)) {
		return -ENOSPC;
	}
	for (uint8_t i = 0U; i < world->plant_count; ++i) {
		const struct picosystem_garden_plant *p = &world->plants[i];
		if ((p->lineage_id == 0U) || (p->lineage_id > lifetimes->count)) {
			return -EFAULT;
		}
		if (p->lineage_id > out->count) {
			if ((p->lineage_id != out->count + 1U) ||
			    (lifetimes->records[p->lineage_id].birth_tick !=
			     world->logic_tick_count)) {
				return -EFAULT;
			}
			out->plants[p->lineage_id].generation = p->generation;
			out->plants[p->lineage_id].column = p->base_column;
			++out->count;
		}
	}
	return (out->count == lifetimes->count) ? 0 : -EFAULT;
}

int toy_factory_garden_landing_ledger_reset(struct toy_factory_garden_landing_ledger *out,
					    const struct picosystem_garden_world *world,
					    const struct toy_factory_garden_lifetimes *lifetimes)
{
	if ((out == NULL) || (world == NULL) || (lifetimes == NULL) ||
	    (world->logic_tick_count != 0U) || (world->seed_count != 0U)) {
		return -EINVAL;
	}
	memset(out, 0, sizeof(*out));
	return census(out, world, lifetimes);
}

int toy_factory_garden_landing_ledger_step(struct toy_factory_garden_landing_ledger *out,
					   const struct picosystem_garden_world *world,
					   const struct toy_factory_garden_lifetimes *lifetimes,
					   const struct picosystem_garden_seed_audit *audit)
{
	if ((out == NULL) || (world == NULL) || (lifetimes == NULL) || (audit == NULL) ||
	    !audit->ecology_step || (audit->count > PICOSYSTEM_GARDEN_MAX_SEEDS) ||
	    (audit->replacement_count > PICOSYSTEM_GARDEN_MAX_PLANTS) ||
	    (out->active_count != audit->count) ||
	    (world->logic_tick_count != out->last_tick + STEP)) {
		return -EINVAL;
	}
	int err = census(out, world, lifetimes);
	if (err != 0) {
		return err;
	}
	uint32_t visited[PICOSYSTEM_GARDEN_MAX_SEEDS] = {0};
	for (uint8_t i = 0U; i < audit->count; ++i) {
		const struct picosystem_garden_seed_attempt *a = &audit->attempts[i];
		const uint32_t age = (uint32_t)a->age * STEP;
		if ((age > world->logic_tick_count) ||
		    (a->outcome > PICOSYSTEM_GARDEN_SEED_GERMINATED)) {
			return -EFAULT;
		}
		const uint32_t birth = world->logic_tick_count - age;
		uint32_t slot = 0U;
		while (slot < out->active_count) {
			const uint32_t index = out->active[slot];
			if (index >= out->seed_count) {
				return -EFAULT;
			}
			if ((out->seeds[index].parent == a->parent) &&
			    (out->seeds[index].birth == birth)) {
				break;
			}
			++slot;
		}
		if (slot == out->active_count) {
			return -ENOENT;
		}
		const uint32_t index = out->active[slot];
		for (uint8_t j = 0U; j < i; ++j) {
			if (visited[j] == index) {
				return -EFAULT;
			}
		}
		visited[i] = index;
		struct toy_factory_garden_landing_purchase *s = &out->seeds[index];
		if ((s->generation != a->generation) || (s->column != a->column) ||
		    (s->species != a->species)) {
			return -EFAULT;
		}
		if (a->outcome != PICOSYSTEM_GARDEN_SEED_WAIT) {
			s->end = world->logic_tick_count;
			s->child = a->child;
			s->outcome = a->outcome;
			out->active[slot] = out->active[--out->active_count];
		}
	}
	/* These exits happen after the germination checks above. Do not overwrite
	 * those observations or pretend a paid replacement died of old age.
	 */
	for (uint8_t i = 0U; i < audit->replacement_count; ++i) {
		const struct picosystem_garden_seed_replacement *const r = &audit->replacements[i];
		const struct picosystem_garden_seed *const old = &r->previous;
		const uint32_t age = (uint32_t)old->age_ecology_ticks * STEP;
		if ((age == 0U) || (age > world->logic_tick_count) ||
		    (world->seed_count != PICOSYSTEM_GARDEN_MAX_SEEDS)) {
			return -EFAULT;
		}
		uint32_t slot = 0U;
		while (slot < out->active_count) {
			const struct toy_factory_garden_landing_purchase *const s =
				&out->seeds[out->active[slot]];
			if ((s->parent == old->parent_lineage_id) &&
			    (s->birth == world->logic_tick_count - age)) {
				break;
			}
			++slot;
		}
		if (slot == out->active_count) {
			return -ENOENT;
		}
		struct toy_factory_garden_landing_purchase *const s =
			&out->seeds[out->active[slot]];
		bool purchased = false;
		for (uint8_t j = 0U; j < world->seed_count; ++j) {
			const struct picosystem_garden_seed *const fresh = &world->seeds[j];
			purchased |= (fresh->age_ecology_ticks == 0U) &&
				     (fresh->parent_lineage_id == old->parent_lineage_id) &&
				     (fresh->column == r->new_column);
		}
		if (!purchased || (s->outcome != PICOSYSTEM_GARDEN_SEED_WAIT) ||
		    (s->column != old->column) || (s->generation != old->generation) ||
		    (s->species != old->species_id)) {
			return -EFAULT;
		}
		s->end = world->logic_tick_count;
		s->outcome = PICOSYSTEM_GARDEN_SEED_REPLACED;
		out->active[slot] = out->active[--out->active_count];
	}
	for (uint8_t i = 0U; i < world->seed_count; ++i) {
		const struct picosystem_garden_seed *s = &world->seeds[i];
		if (s->age_ecology_ticks != 0U) {
			continue;
		}
		if ((out->seed_count == TOY_FACTORY_GARDEN_LANDING_MAX_PURCHASES) ||
		    (out->active_count == PICOSYSTEM_GARDEN_MAX_SEEDS)) {
			return -ENOSPC;
		}
		if ((s->parent_lineage_id == 0U) || (s->parent_lineage_id > out->count) ||
		    (lifetimes->records[s->parent_lineage_id].removal_tick != 0U) ||
		    (lifetimes->records[s->parent_lineage_id].death_cause !=
		     TOY_FACTORY_GARDEN_LIFETIME_CAUSES)) {
			return -EFAULT;
		}
		out->seeds[out->seed_count] = (struct toy_factory_garden_landing_purchase){
			.parent = s->parent_lineage_id,
			.birth = world->logic_tick_count,
			.generation = s->generation,
			.column = s->column,
			.species = s->species_id};
		out->active[out->active_count++] = out->seed_count++;
		++out->plants[s->parent_lineage_id].purchases;
	}
	if ((out->seed_count != world->seed_creation_count) ||
	    (out->active_count != world->seed_count)) {
		return -EFAULT;
	}
	out->last_tick = world->logic_tick_count;
	return 0;
}

int toy_factory_garden_landing_ledger_print(FILE *stream,
					    const struct toy_factory_garden_landing_ledger *ledger,
					    const struct toy_factory_garden_lifetimes *lifetimes)
{
	return toy_factory_garden_landing_ledger_print_environmental(stream, ledger, lifetimes, 0U);
}

int toy_factory_garden_landing_ledger_print_environmental(
	FILE *stream, const struct toy_factory_garden_landing_ledger *ledger,
	const struct toy_factory_garden_lifetimes *lifetimes, uint32_t lineage_id)
{
	return toy_factory_garden_landing_ledger_print_environmental_pair(stream, ledger, lifetimes,
									  lineage_id, 0U);
}

int toy_factory_garden_landing_ledger_print_environmental_pair(
	FILE *stream, const struct toy_factory_garden_landing_ledger *ledger,
	const struct toy_factory_garden_lifetimes *lifetimes, uint32_t first_id, uint32_t second_id)
{
	if ((stream == NULL) || (ledger == NULL) || (lifetimes == NULL) ||
	    (ledger->count != lifetimes->count) ||
	    (ledger->count > TOY_FACTORY_GARDEN_EVALUATION_MAX_TRACKED_LINEAGES) ||
	    (ledger->seed_count > TOY_FACTORY_GARDEN_LANDING_MAX_PURCHASES)) {
		return -EINVAL;
	}
	if ((second_id != 0U) && ((first_id == 0U) || (first_id == second_id))) {
		return -EINVAL;
	}
	const uint32_t events[] = {first_id, second_id};
	for (size_t i = 0U; i < sizeof(events) / sizeof(events[0]); ++i) {
		const uint32_t id = events[i];
		if ((id > lifetimes->count) ||
		    ((id != 0U) && ((lifetimes->records[id].death_cause != 3U) ||
				    (lifetimes->records[id].removal_tick != 0U)))) {
			return -EINVAL;
		}
	}
	fputs("\"ledger_start_tick\":0,\"lineages\":[", stream);
	for (uint32_t id = 1U; id <= ledger->count; ++id) {
		const struct toy_factory_garden_lifetime *r = &lifetimes->records[id];
		fprintf(stream,
			"%s{\"id\":%" PRIu32 ",\"parent\":%" PRIu32 ",\"birth_tick\":%" PRIu32
			",\"death_tick\":",
			id == 1U ? "" : ",", id, r->parent_id, r->birth_tick);
		if (r->death_cause == TOY_FACTORY_GARDEN_LIFETIME_CAUSES) {
			fputs("null", stream);
		} else {
			fprintf(stream, "%" PRIu32, r->death_tick);
		}
		if (r->removal_tick != 0U) {
			fprintf(stream, ",\"removal_tick\":%" PRIu32, r->removal_tick);
		}
		fprintf(stream,
			",\"environmental_death\":%s,\"column\":%u,\"generation\":%u,"
			"\"species\":%u,"
			"\"seeds_created\":%" PRIu32 ",\"late_seeds_created\":%" PRIu32 "}",
			(id == first_id) || (id == second_id) ? "true" : "false",
			ledger->plants[id].column, ledger->plants[id].generation, r->species_id,
			ledger->plants[id].purchases, ledger->plants[id].purchases);
	}
	fputs("],\"seeds\":[", stream);
	for (uint32_t i = 0U; i < ledger->seed_count; ++i) {
		const struct toy_factory_garden_landing_purchase *s = &ledger->seeds[i];
		fprintf(stream,
			"%s{\"parent\":%" PRIu32 ",\"birth_tick\":%" PRIu32 ",\"end_tick\":",
			i == 0U ? "" : ",", s->parent, s->birth);
		if (s->end == 0U) {
			fputs("null", stream);
		} else {
			fprintf(stream, "%" PRIu32, s->end);
		}
		fputs(",\"child_id\":", stream);
		if (s->child == 0U) {
			fputs("null", stream);
		} else {
			fprintf(stream, "%" PRIu32, s->child);
		}
		fprintf(stream,
			",\"lifetime_ecology_ticks\":%u,\"generation\":%u,\"column\":%u,"
			"\"species\":%u,\"outcome\":\"%s\"}",
			PICOSYSTEM_GARDEN_SEED_LIFETIME_TICKS, s->generation, s->column, s->species,
			s->outcome == PICOSYSTEM_GARDEN_SEED_EXPIRED      ? "expired"
			: s->outcome == PICOSYSTEM_GARDEN_SEED_GERMINATED ? "germinated"
			: s->outcome == PICOSYSTEM_GARDEN_SEED_REPLACED   ? "replaced"
									  : "pending");
	}
	fputc(']', stream);
	return ferror(stream) ? -EIO : 0;
}

int toy_factory_garden_landing_replacements_print(FILE *stream, uint32_t tick,
						  const struct picosystem_garden_seed_audit *audit)
{
	if ((stream == NULL) || (audit == NULL) || !audit->ecology_step ||
	    (audit->replacement_count > PICOSYSTEM_GARDEN_MAX_PLANTS)) {
		return -EINVAL;
	}
	fprintf(stream, "{\"tick\":%" PRIu32 ",\"replacements\":[", tick);
	for (uint8_t i = 0U; i < audit->replacement_count; ++i) {
		const struct picosystem_garden_seed_replacement *const r = &audit->replacements[i];
		const struct picosystem_garden_seed *const s = &r->previous;
		fprintf(stream,
			"%s{\"parent\":%" PRIu32 ",\"age\":%u,\"column\":%u,"
			"\"generation\":%u,\"species\":%u,\"new_column\":%u}",
			i ? "," : "", s->parent_lineage_id, s->age_ecology_ticks, s->column,
			s->generation, s->species_id, r->new_column);
	}
	fputs("]}\n", stream);
	return ferror(stream) ? -EIO : 0;
}
