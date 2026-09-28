/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_REPRODUCTION_AUDIT_H_
#define TOY_FACTORY_GARDEN_REPRODUCTION_AUDIT_H_

#include "garden_world.h"

#if defined(__ZEPHYR__)
#error "Reproduction accounting is restricted to host diagnostics"
#endif

/* Ordered like the ordinary production short-circuit checks. All simultaneous
 * limits are recorded; the lowest set bit is the first failed check, not a
 * claim that removing that check alone would permit a purchase.
 */
enum picosystem_garden_reproduction_blocker {
	PICOSYSTEM_GARDEN_REPRODUCTION_COOLDOWN = 1U << 0U,
	PICOSYSTEM_GARDEN_REPRODUCTION_CADENCE = 1U << 1U,
	PICOSYSTEM_GARDEN_REPRODUCTION_BANK = 1U << 2U,
	PICOSYSTEM_GARDEN_REPRODUCTION_DEAD = 1U << 3U,
	PICOSYSTEM_GARDEN_REPRODUCTION_STRESS = 1U << 4U,
	PICOSYSTEM_GARDEN_REPRODUCTION_LIGHT = 1U << 5U,
	PICOSYSTEM_GARDEN_REPRODUCTION_GENERATION = 1U << 6U,
	PICOSYSTEM_GARDEN_REPRODUCTION_ENERGY = 1U << 7U,
	PICOSYSTEM_GARDEN_REPRODUCTION_WATER = 1U << 8U,
	PICOSYSTEM_GARDEN_REPRODUCTION_FLOWER = 1U << 9U,
};

struct picosystem_garden_reproduction_visit {
	uint32_t lineage;
	uint16_t blockers;
	uint16_t energy;
	uint16_t water;
	int32_t energy_required;
	int32_t water_required;
	uint16_t immature_flowers;
	uint16_t spent_flowers;
	uint16_t ready_flowers;
	uint16_t flower_index;
	uint8_t cooldown;
	uint8_t seed_count;
	uint8_t stress;
	uint8_t sun_strength;
	bool produced;
};

struct picosystem_garden_reproduction_audit {
	bool ecology_step;
	uint8_t count;
	struct picosystem_garden_reproduction_visit visits[PICOSYSTEM_GARDEN_MAX_PLANTS];
};

/* Exact sequential visits after growth, dawn flower renewal and cooldown
 * decrement, before any seed debit. Flower categories partition all flowers:
 * immature takes precedence over spent. Caller owns separate world/output;
 * no callbacks, RNG draws, persistent fields or allocations are introduced.
 * Gardener must be off. Output is replaced on success (zero on ordinary ticks),
 * unchanged on error; an internal error need not roll back the world.
 * Unsupported experimental production rules return -ENOTSUP without stepping.
 */
int picosystem_garden_world_step_reproduction_audit(
	struct picosystem_garden_world *world, const struct picosystem_garden_agent_policy *policy,
	struct picosystem_garden_reproduction_audit *audit);

#endif
