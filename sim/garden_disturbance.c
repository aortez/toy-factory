/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_disturbance.h"

#include <errno.h>
#include <inttypes.h>
#include <stdio.h>

_Static_assert(PICOSYSTEM_GARDEN_GRID_COLUMNS == 28U, "patch-death-v1 uses 28 ground columns");
_Static_assert(TOY_FACTORY_GARDEN_DISTURBANCE_MAX_TICKS / 15U < UINT16_MAX,
	       "Long-run assay must not cross the existing plant-age wrap boundary");

static uint32_t mix(uint32_t value)
{
	value ^= value >> 16;
	value *= UINT32_C(0x7feb352d);
	value ^= value >> 15;
	value *= UINT32_C(0x846ca68b);
	return value ^ (value >> 16);
}

int toy_factory_garden_disturbance_plan(uint32_t seed, uint32_t index,
					struct toy_factory_garden_disturbance_event *event)
{
	if ((seed == 0U) || (event == NULL)) {
		return -EINVAL;
	}
	if (index >= TOY_FACTORY_GARDEN_DISTURBANCE_MAX_EVENTS) {
		return -ENOENT;
	}
	uint32_t tick = 61440U;
	for (uint32_t i = 0U; i < index; ++i) {
		tick += (1024U + mix(seed ^ UINT32_C(0x696e7476) ^ i) % 1025U) * 15U;
	}
	if (tick > TOY_FACTORY_GARDEN_DISTURBANCE_MAX_TICKS) {
		return -ENOENT;
	}
	/* Centers -1..28 give every ground column three possible hits, including edges. */
	const int center = (int)(mix(seed ^ UINT32_C(0x6c6f6361) ^ index) % 30U) - 1;
	*event = (struct toy_factory_garden_disturbance_event){
		.tick = tick,
		.index = index,
		.seed = seed,
		.first_column = (uint8_t)(center < 1 ? 0 : center - 1),
		.last_column = (uint8_t)(center > 26 ? 27 : center + 1),
	};
	return 0;
}

int toy_factory_garden_disturbance_apply(struct picosystem_garden_world *world,
					 struct toy_factory_garden_disturbance_event *event)
{
	if ((world == NULL) || (event == NULL) ||
	    (world->plant_count > PICOSYSTEM_GARDEN_MAX_PLANTS)) {
		return -EINVAL;
	}
	struct toy_factory_garden_disturbance_event result;
	if ((toy_factory_garden_disturbance_plan(event->seed, event->index, &result) != 0) ||
	    (event->tick != result.tick) || (event->first_column != result.first_column) ||
	    (event->last_column != result.last_column) ||
	    (world->logic_tick_count != result.tick)) {
		return -EINVAL;
	}
	const struct picosystem_garden_world before = *world;
	const int err = picosystem_garden_world_experimental_kill_patch(world, result.first_column,
									result.last_column);
	if (err != 0) {
		return err;
	}
	for (uint8_t i = 0U; i < before.plant_count; ++i) {
		const struct picosystem_garden_plant *plant = &before.plants[i];
		if (!(plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) &&
		    (world->plants[i].flags & PICOSYSTEM_GARDEN_PLANT_DEAD)) {
			result.killed_ids[result.killed_count++] = plant->lineage_id;
			result.lost_energy = (uint16_t)(result.lost_energy + plant->stored_energy);
			result.lost_water = (uint16_t)(result.lost_water + plant->stored_water);
			result.killed_nodes = (uint16_t)(result.killed_nodes + plant->node_count);
		}
	}
	result.before_hash = picosystem_garden_world_hash(&before);
	result.after_hash = picosystem_garden_world_hash(world);
	*event = result;
	return 0;
}

int toy_factory_garden_disturbance_advance(
	struct picosystem_garden_world *world,
	const struct toy_factory_garden_evaluation_scenario *scenario,
	const struct picosystem_garden_agent_policy *policy, uint32_t end_tick, uint32_t seed,
	toy_factory_garden_evaluation_observer_fn observer,
	toy_factory_garden_disturbance_observer_fn event_observer, void *context,
	struct toy_factory_garden_disturbance_totals *totals)
{
	if ((world == NULL) || (totals == NULL) || (seed == 0U) ||
	    (end_tick > TOY_FACTORY_GARDEN_DISTURBANCE_MAX_TICKS) ||
	    (end_tick < world->logic_tick_count)) {
		return -EINVAL;
	}
	for (uint32_t index = 0U; index < TOY_FACTORY_GARDEN_DISTURBANCE_MAX_EVENTS; ++index) {
		struct toy_factory_garden_disturbance_event event;
		const int planned = toy_factory_garden_disturbance_plan(seed, index, &event);
		if ((planned == -ENOENT) || ((planned == 0) && (event.tick > end_tick))) {
			break;
		}
		if (planned != 0) {
			return planned;
		}
		if (event.tick <= world->logic_tick_count) {
			continue;
		}
		int err = toy_factory_garden_evaluation_advance(
			world, scenario, policy, event.tick - world->logic_tick_count, observer,
			context);
		if (err == 0) {
			err = toy_factory_garden_disturbance_apply(world, &event);
		}
		if (err != 0) {
			return err;
		}
		++totals->events;
		totals->killed += event.killed_count;
		if (event_observer != NULL) {
			err = event_observer(world, &event, context);
			if (err != 0) {
				return err;
			}
		}
	}
	return toy_factory_garden_evaluation_advance(
		world, scenario, policy, end_tick - world->logic_tick_count, observer, context);
}

int toy_factory_garden_disturbance_print(const struct toy_factory_garden_disturbance_event *event)
{
	if ((event == NULL) || (event->killed_count > PICOSYSTEM_GARDEN_MAX_PLANTS)) {
		return -EINVAL;
	}
	printf("{\"type\":\"disturbance\",\"protocol\":\"%s\",\"seed\":\"%08" PRIx32
	       "\",\"index\":%" PRIu32 ",\"tick\":%" PRIu32
	       ",\"first_column\":%u,\"last_column\":%u,\"before_hash\":\"%08" PRIx32
	       "\",\"after_hash\":\"%08" PRIx32
	       "\",\"energy\":%u,\"water\":%u,\"nodes\":%u,\"killed\":[",
	       TOY_FACTORY_GARDEN_DISTURBANCE_PROTOCOL, event->seed, event->index, event->tick,
	       event->first_column, event->last_column, event->before_hash, event->after_hash,
	       event->lost_energy, event->lost_water, event->killed_nodes);
	for (uint8_t i = 0U; i < event->killed_count; ++i) {
		printf("%s%" PRIu32, i == 0U ? "" : ",", event->killed_ids[i]);
	}
	puts("]}");
	return ferror(stdout) ? -EIO : 0;
}
