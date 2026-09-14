/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_WATER_AUDIT_H_
#define TOY_FACTORY_GARDEN_WATER_AUDIT_H_

#include "garden_world.h"

#if !defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE) || defined(__ZEPHYR__)
#error "Water accounting is restricted to the host maintenance experiment"
#endif

enum picosystem_garden_water_stage {
	PICOSYSTEM_GARDEN_WATER_START,
	PICOSYSTEM_GARDEN_WATER_RAIN,
	PICOSYSTEM_GARDEN_WATER_TRANSPORT,
	PICOSYSTEM_GARDEN_WATER_UPTAKE,
	PICOSYSTEM_GARDEN_WATER_DECOMPOSITION,
	PICOSYSTEM_GARDEN_WATER_MAINTENANCE,
	PICOSYSTEM_GARDEN_WATER_GERMINATION,
	PICOSYSTEM_GARDEN_WATER_GROWTH,
	PICOSYSTEM_GARDEN_WATER_REPRODUCTION,
	PICOSYSTEM_GARDEN_WATER_STAGE_COUNT,
};

struct picosystem_garden_water_inventory {
	uint32_t soil;
	uint32_t plants;
};

struct picosystem_garden_water_audit {
	bool ecology_step;
	uint32_t drainage;
	struct picosystem_garden_water_inventory stages[PICOSYSTEM_GARDEN_WATER_STAGE_COUNT];
};

/* Same step implementation, caller-owned observation only; no global observer or
 * world-layout/hash changes. Requires gardener off. Output is replaced on success
 * (zeroed for a non-ecology step), unchanged on error. As with the ordinary step,
 * an internal simulation error need not roll back the world. No aliasing world/output.
 */
int picosystem_garden_world_step_water_audit(struct picosystem_garden_world *world,
					     const struct picosystem_garden_agent_policy *policy,
					     struct picosystem_garden_water_audit *audit);

#endif
