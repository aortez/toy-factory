/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_turnover.h"

#include <errno.h>
#include <inttypes.h>

int toy_factory_garden_landing_turnover_apply(struct toy_factory_garden_landing_growth_run *run,
					      struct toy_factory_garden_lifetimes *ledger,
					      uint32_t lineage_id,
					      struct toy_factory_garden_landing_turnover *result)
{
	if ((run == NULL) || (ledger == NULL) || (result == NULL)) {
		return -EINVAL;
	}
	const struct picosystem_garden_world *const world = &run->base.world;
	if ((ledger->count > TOY_FACTORY_GARDEN_EVALUATION_MAX_TRACKED_LINEAGES) ||
	    (ledger->count != world->lineage_sequence) || (lineage_id == 0U) ||
	    (lineage_id > ledger->count) || (world->plant_count > PICOSYSTEM_GARDEN_MAX_PLANTS) ||
	    (world->logic_tick_count % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR != 0U) ||
	    (world->death_count == UINT32_MAX)) {
		return -ERANGE;
	}
	const struct toy_factory_garden_lifetime *const life = &ledger->records[lineage_id];
	if ((life->death_cause != TOY_FACTORY_GARDEN_LIFETIME_CAUSES) ||
	    (life->removal_tick != 0U) || (world->logic_tick_count < life->birth_tick) ||
	    (world->logic_tick_count - life->birth_tick <=
	     TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS)) {
		return -EINVAL;
	}
	const struct picosystem_garden_plant *target = NULL;
	for (uint8_t i = 0U; i < world->plant_count; ++i) {
		if (world->plants[i].lineage_id == lineage_id) {
			target = &world->plants[i];
			break;
		}
	}
	if (target == NULL) {
		return -ENOENT;
	}
	if ((target->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) ||
	    (target->age_ecology_ticks <= PICOSYSTEM_GARDEN_SUN_CYCLE_TICKS)) {
		return -EINVAL;
	}
	for (uint8_t i = 0U; i < world->plant_count; ++i) {
		const struct picosystem_garden_plant *const p = &world->plants[i];
		if ((p != target) && !(p->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) &&
		    (p->base_column == target->base_column)) {
			return -EINVAL;
		}
	}
	struct toy_factory_garden_landing_turnover event = {
		.tick = world->logic_tick_count,
		.lineage_id = lineage_id,
		.column = target->base_column,
		.nodes = target->node_count,
		.energy = target->stored_energy,
		.water = target->stored_water,
	};
	struct toy_factory_garden_landing_growth_run candidate = *run;
	int err = picosystem_garden_world_experimental_kill_patch(&candidate.base.world,
								  event.column, event.column);
	if (err != 0) {
		return err;
	}
	if (candidate.base.world.death_count != world->death_count + 1U) {
		return -EFAULT;
	}
	err = toy_factory_garden_landing_growth_hash(run, &event.before_run_hash);
	if (err == 0) {
		err = toy_factory_garden_landing_growth_hash(&candidate, &event.after_run_hash);
	}
	if (err == 0) {
		event.before_world_hash = picosystem_garden_world_hash(world);
		event.after_world_hash = picosystem_garden_world_hash(&candidate.base.world);
		/* "Other" death, never invented energy/water starvation. The CLI labels
		 * this event explicitly as environmental in its lineage export.
		 */
		err = toy_factory_garden_lifetimes_death(ledger, lineage_id, event.tick,
							 PICOSYSTEM_GARDEN_PLANT_DEAD);
	}
	if (err == 0) {
		*run = candidate;
		*result = event;
	}
	return err;
}

uint32_t toy_factory_garden_landing_turnover_hash(uint32_t base, uint32_t tick, uint32_t lineage_id)
{
	uint32_t hash = 2166136261U;
	const uint8_t tag[] = {'G', 'L', 'T', '1'};
	for (size_t i = 0U; i < sizeof(tag); ++i) {
		hash = (hash ^ tag[i]) * 16777619U;
	}
	const uint32_t words[] = {base, tick, lineage_id};
	for (size_t i = 0U; i < sizeof(words) / sizeof(words[0]); ++i) {
		for (uint8_t byte = 0U; byte < 4U; ++byte) {
			hash = (hash ^ (uint8_t)(words[i] >> (byte * 8U))) * 16777619U;
		}
	}
	return hash;
}

static int print_event(FILE *stream, const struct toy_factory_garden_landing_turnover *event,
		       const char *name)
{
	if ((stream == NULL) || (event == NULL) || (event->lineage_id == 0U)) {
		return -EINVAL;
	}
	fprintf(stream,
		"\"%s\":{\"version\":1,\"tick\":%" PRIu32 ",\"lineage\":%" PRIu32
		",\"column\":%u,\"nodes\":%u,\"energy\":%u,\"water\":%u,"
		"\"before_world_hash\":\"%08" PRIx32 "\",\"after_world_hash\":\"%08" PRIx32
		"\",\"before_run_hash\":\"%08" PRIx32 "\",\"after_run_hash\":\"%08" PRIx32 "\"},",
		name, event->tick, event->lineage_id, event->column, event->nodes, event->energy,
		event->water, event->before_world_hash, event->after_world_hash,
		event->before_run_hash, event->after_run_hash);
	return ferror(stream) ? -EIO : 0;
}

int toy_factory_garden_landing_turnover_print(
	FILE *stream, const struct toy_factory_garden_landing_turnover *event)
{
	return print_event(stream, event, "turnover_probe");
}

int toy_factory_garden_landing_turnover_print_second(
	FILE *stream, const struct toy_factory_garden_landing_turnover *event)
{
	return print_event(stream, event, "second_turnover_probe");
}
