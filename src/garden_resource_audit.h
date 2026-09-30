/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_RESOURCE_AUDIT_H_
#define TOY_FACTORY_GARDEN_RESOURCE_AUDIT_H_

#include "garden_death_audit.h"

enum picosystem_garden_resource_stage {
	PICOSYSTEM_GARDEN_RESOURCE_UPTAKE,
	PICOSYSTEM_GARDEN_RESOURCE_MAINTENANCE,
	PICOSYSTEM_GARDEN_RESOURCE_GERMINATION,
	PICOSYSTEM_GARDEN_RESOURCE_GROWTH,
	PICOSYSTEM_GARDEN_RESOURCE_REPRODUCTION,
	PICOSYSTEM_GARDEN_RESOURCE_STAGE_COUNT,
};

struct picosystem_garden_resource_plant {
	uint32_t lineage_id;
	uint16_t energy;
	uint16_t water;
	uint16_t nodes;
	uint8_t stress;
	uint8_t flags;
};

/* Host-owned snapshots keyed by lineage, never by a persistent compacted slot.
 * Uptake retains unsaturated transfers for ALL preexisting living plants;
 * upkeep fields in those receipts are meaningful only for maintenance deaths.
 * No pointers, RNG draws or authoritative world fields. Five snapshots let the
 * reader separate upkeep, birth endowment, growth and reproductive spending.
 */
struct picosystem_garden_resource_audit {
	struct picosystem_garden_death_audit uptake;
	struct {
		struct picosystem_garden_resource_plant plants[PICOSYSTEM_GARDEN_MAX_PLANTS];
		uint8_t count;
	} stages[PICOSYSTEM_GARDEN_RESOURCE_STAGE_COUNT];
};

#endif
