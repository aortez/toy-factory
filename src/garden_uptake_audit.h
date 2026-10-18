/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_UPTAKE_AUDIT_H_
#define TOY_FACTORY_GARDEN_UPTAKE_AUDIT_H_

#include "garden_light.h"

#if defined(__ZEPHYR__)
#error "Uptake attribution is restricted to host diagnostics"
#endif

struct picosystem_garden_shade_source {
	uint32_t lineage;
	uint16_t node;
	uint8_t column, row, center, neighbor;
	bool dead;
};

struct picosystem_garden_root_uptake {
	uint32_t lineage;
	uint16_t node, stored_before, stored_after;
	uint8_t slot, column, row, limit, before, taken, after;
};

struct picosystem_garden_leaf_uptake {
	uint32_t lineage;
	uint16_t node;
	uint8_t column, row, light, income;
};

/* Actual pre-maintenance uptake, before any death/compaction/germination.
 * Each bounded list has at most one record per world node. Sources are emitted
 * by the real opacity builder; roots are in actual plant/node visitation order.
 * Node/slot indices are valid only within this sample; lineage survives reuse.
 * No authoritative fields or pointers. Caller owns separate storage, published
 * on success only (zero on non-ecology ticks). Default additive light/uptake only.
 */
struct picosystem_garden_uptake_audit {
	uint32_t tick;
	bool ecology_step;
	struct picosystem_garden_sun sun;
	uint16_t source_count, root_count, leaf_count;
	struct picosystem_garden_shade_source sources[PICOSYSTEM_GARDEN_MAX_NODES];
	struct picosystem_garden_root_uptake roots[PICOSYSTEM_GARDEN_MAX_NODES];
	struct picosystem_garden_leaf_uptake leaves[PICOSYSTEM_GARDEN_MAX_NODES];
	uint8_t soil_before[PICOSYSTEM_GARDEN_SOIL_CELL_COUNT];
	uint8_t soil_after[PICOSYSTEM_GARDEN_SOIL_CELL_COUNT];
	uint8_t light[PICOSYSTEM_GARDEN_LIGHT_CELL_COUNT];
};

#endif
