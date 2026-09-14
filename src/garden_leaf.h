/* SPDX-License-Identifier: Apache-2.0 */
#ifndef PICOSYSTEM_GARDEN_LEAF_H_
#define PICOSYSTEM_GARDEN_LEAF_H_

#include "garden_world.h"

#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
enum picosystem_garden_leaf_action {
	PICOSYSTEM_GARDEN_LEAF_WAIT,
	PICOSYSTEM_GARDEN_LEAF_RENEW,
};

/* Typed mature-leaf site: no invented growth candidates/depth fields. */
struct picosystem_garden_leaf_observation {
	uint16_t node_index;
	uint16_t stored_energy;
	uint16_t stored_water;
	uint16_t mature_leaf_count;
	int16_t base_delta_x;
	int16_t base_delta_y;
	uint8_t plant_index;
	uint8_t condition;
	uint8_t light;
	uint8_t maintenance_energy;
	uint8_t maintenance_water;
	uint8_t renewal_energy;
	uint8_t renewal_water;
};

struct picosystem_garden_leaf_decision {
	struct picosystem_garden_agent_memory next_memory;
	uint16_t node_index;
	uint8_t action;
};

struct picosystem_garden_leaf_policy {
	int (*decide)(const struct picosystem_garden_leaf_observation *observation,
		      const struct picosystem_garden_agent_memory *memory,
		      struct picosystem_garden_leaf_decision *decision, const void *context);
	const void *context;
};

/* Read-only sampled site. ENOENT means no mature living leaf, not low resources. */
int picosystem_garden_leaf_observe(const struct picosystem_garden_world *world, uint8_t plant_index,
				   struct picosystem_garden_leaf_observation *observation);

/* Validate before any mutation. Does not allocate, advance time, or commit memory. */
int picosystem_garden_leaf_renew(struct picosystem_garden_world *world, uint8_t plant_index,
				 uint16_t node_index);
#endif
#endif
