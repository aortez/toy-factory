/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_DISTURBANCE_H_
#define TOY_FACTORY_GARDEN_DISTURBANCE_H_

#include "garden_evaluation.h"

#if !defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE) || defined(__ZEPHYR__)
#error "Patch disturbance is a host-only maintenance assay"
#endif

#define TOY_FACTORY_GARDEN_DISTURBANCE_PROTOCOL   "patch-death-v1"
#define TOY_FACTORY_GARDEN_DISTURBANCE_MAX_TICKS  737280U
#define TOY_FACTORY_GARDEN_DISTURBANCE_MAX_EVENTS 45U

struct toy_factory_garden_disturbance_event {
	uint32_t tick;
	uint32_t index;
	uint32_t seed;
	uint32_t before_hash;
	uint32_t after_hash;
	uint32_t killed_ids[PICOSYSTEM_GARDEN_MAX_PLANTS];
	uint16_t lost_energy;
	uint16_t lost_water;
	uint16_t killed_nodes;
	uint8_t first_column;
	uint8_t last_column;
	uint8_t killed_count;
};

struct toy_factory_garden_disturbance_totals {
	uint32_t events;
	uint32_t killed;
};

typedef int (*toy_factory_garden_disturbance_observer_fn)(
	const struct picosystem_garden_world *world,
	const struct toy_factory_garden_disturbance_event *event, void *context);

/* Stateless schedule; independent of world state and world RNG. Index is zero-based.
 * -ENOENT beyond the 192-day horizon. Output unchanged on failure.
 */
int toy_factory_garden_disturbance_plan(uint32_t seed, uint32_t index,
					struct toy_factory_garden_disturbance_event *event);
/* Plan's seed/index/tick/columns must agree, at an ecology boundary. Atomic on failure. */
int toy_factory_garden_disturbance_apply(struct picosystem_garden_world *world,
					 struct toy_factory_garden_disturbance_event *event);
/* Advance to an absolute end tick, applying events after their ordinary ecology step.
 * Ordinary observers see pre-event state; event observers see post-event state.
 * Resume only worlds previously advanced with this same schedule; events at or
 * before the starting tick are assumed already applied.
 * A callback failure stops progression but does not roll back completed steps/events.
 */
int toy_factory_garden_disturbance_advance(
	struct picosystem_garden_world *world,
	const struct toy_factory_garden_evaluation_scenario *scenario,
	const struct picosystem_garden_agent_policy *policy, uint32_t end_tick, uint32_t seed,
	toy_factory_garden_evaluation_observer_fn observer,
	toy_factory_garden_disturbance_observer_fn event_observer, void *context,
	struct toy_factory_garden_disturbance_totals *totals);
int toy_factory_garden_disturbance_print(const struct toy_factory_garden_disturbance_event *event);

#endif
