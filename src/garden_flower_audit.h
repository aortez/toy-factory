/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_FLOWER_AUDIT_H_
#define TOY_FACTORY_GARDEN_FLOWER_AUDIT_H_

#include "garden_reproduction_audit.h"

/* These are hypothetical flower-origin supports even in a base-origin build.
 * Node indices identify geometry only within this step, not persistent IDs.
 */
struct picosystem_garden_flower_reach {
	uint32_t columns;
	uint16_t node_index;
	uint8_t x;
	uint8_t y;
};

struct picosystem_garden_flower_purchase {
	uint32_t lineage;
	uint32_t columns;
	uint16_t flower_offset;
	uint16_t flower_count;
	uint16_t selected_flower;
	uint8_t base_column;
	uint8_t origin;
	uint8_t species;
	int8_t dispersal;
	uint8_t choice;
	uint8_t landed_column;
};

struct picosystem_garden_flower_site {
	uint8_t moisture;
	uint8_t light;
	uint8_t blockers;
};

/* All storage is caller-owned and host-only. Every eligible node belongs to
 * exactly one plant, and each plant can buy at most once per step, so the total
 * number of captured flowers cannot exceed the existing node capacity.
 */
struct picosystem_garden_flower_audit {
	struct picosystem_garden_reproduction_audit production;
	struct picosystem_garden_flower_site sites[PICOSYSTEM_GARDEN_GRID_COLUMNS];
	struct picosystem_garden_flower_purchase purchases[PICOSYSTEM_GARDEN_MAX_PLANTS];
	struct picosystem_garden_flower_reach flowers[PICOSYSTEM_GARDEN_MAX_NODES];
	uint16_t flower_count;
	uint8_t count;
};

/* Observe successful purchases only, with eligibility captured before marking
 * the selected flower spent. Sites are evaluated after the same step's normal
 * final light refresh; no site-affecting change occurs between production visits.
 * Blockers describe a hypothetical mature seed, not a newly dropped seed's future.
 * The recorded draw is the real production draw, not an additional RNG draw.
 *
 * Same output/error/non-aliasing contract as the reproduction audit. Only ordinary
 * narrow/wide and flower-origin host ecology is supported. No observer state is
 * retained in the world. With no purchases, sites and flower records are zero.
 */
int picosystem_garden_world_step_flower_audit(struct picosystem_garden_world *world,
					      const struct picosystem_garden_agent_policy *policy,
					      struct picosystem_garden_flower_audit *audit);

#endif
