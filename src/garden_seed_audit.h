/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_SEED_AUDIT_H_
#define TOY_FACTORY_GARDEN_SEED_AUDIT_H_

#include "garden_world.h"

#if !defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE) || defined(__ZEPHYR__)
#error "Seed accounting is restricted to the host maintenance experiment"
#endif

enum picosystem_garden_seed_outcome {
	PICOSYSTEM_GARDEN_SEED_WAIT,
	PICOSYSTEM_GARDEN_SEED_EXPIRED,
	PICOSYSTEM_GARDEN_SEED_GERMINATED,
};

enum picosystem_garden_seed_stage {
	PICOSYSTEM_GARDEN_SEED_START,
	PICOSYSTEM_GARDEN_SEED_BEFORE_CHECKS,
	PICOSYSTEM_GARDEN_SEED_AFTER_CHECKS,
	PICOSYSTEM_GARDEN_SEED_AFTER_GROWTH,
	PICOSYSTEM_GARDEN_SEED_AFTER_REPRODUCTION,
	PICOSYSTEM_GARDEN_SEED_STAGE_COUNT,
};

struct picosystem_garden_seed_inventory {
	uint16_t nodes;
	uint8_t plants;
	uint8_t seeds;
};

struct picosystem_garden_seed_attempt {
	uint32_t parent;
	uint32_t child;
	uint16_t age;
	uint16_t generation;
	uint16_t nodes;
	uint8_t plants;
	uint8_t column;
	uint8_t species;
	uint8_t moisture;
	uint8_t light;
	uint8_t blockers;
	uint8_t outcome;
	/* Mature hypothetical sites at this exact sequential check. Expired entries
	 * never undergo a check: sites/resources/blockers stay zero for those entries.
	 */
	uint8_t sites[PICOSYSTEM_GARDEN_GRID_COLUMNS];
};

struct picosystem_garden_seed_audit {
	bool ecology_step;
	uint8_t count;
	uint8_t sites_before[PICOSYSTEM_GARDEN_GRID_COLUMNS];
	struct picosystem_garden_seed_inventory stages[PICOSYSTEM_GARDEN_SEED_STAGE_COUNT];
	struct picosystem_garden_seed_attempt attempts[PICOSYSTEM_GARDEN_MAX_SEEDS];
};

/* Same authoritative step, no callbacks, global observer, RNG draws or world
 * fields. Gardener must be off. Output replaced on success (zero for ordinary
 * non-ecology ticks), unchanged on error; world need not roll back an internal
 * simulation error. Caller-owned world and output must not alias.
 */
int picosystem_garden_world_step_seed_audit(struct picosystem_garden_world *world,
					    const struct picosystem_garden_agent_policy *policy,
					    struct picosystem_garden_seed_audit *audit);

#endif
