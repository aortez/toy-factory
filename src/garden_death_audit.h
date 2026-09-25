/* SPDX-License-Identifier: Apache-2.0 */
#ifndef PICOSYSTEM_GARDEN_DEATH_AUDIT_H_
#define PICOSYSTEM_GARDEN_DEATH_AUDIT_H_

#include "garden_world.h"

#if defined(__ZEPHYR__)
#error "Death-step accounting is a host-only diagnostic"
#endif

#define PICOSYSTEM_GARDEN_DEATH_AUDIT_VERSION 1U

/* Actual transfers, not estimates from the saturated public income counters. */
struct picosystem_garden_death_resource {
	uint16_t before;
	uint16_t income;
	uint16_t overflow;
	uint16_t upkeep_due;
	uint16_t upkeep_paid;
	uint16_t discarded;
};

struct picosystem_garden_death_event {
	uint32_t lineage_id;
	struct picosystem_garden_death_resource energy;
	struct picosystem_garden_death_resource water;
	uint8_t stress_before;
	uint8_t flags;
};

struct picosystem_garden_death_audit {
	struct picosystem_garden_death_event events[PICOSYSTEM_GARDEN_MAX_PLANTS];
	uint8_t count;
	bool ecology_step;
};

/* Same authoritative step, with caller-owned natural-maintenance death receipts.
 * No world fields, RNG draws or persistent buffers. Gardener must be off; external
 * patch deaths are not maintenance deaths. Output is replaced on success (empty
 * on non-ecology ticks), unchanged on error. Internal errors need not roll back
 * the world. World, output and policy context must not alias.
 */
int picosystem_garden_world_step_death_audit(struct picosystem_garden_world *world,
					     const struct picosystem_garden_agent_policy *policy,
					     struct picosystem_garden_death_audit *audit);

#endif
