/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_LANDING_PATCH_SWEEP_H_
#define TOY_FACTORY_GARDEN_LANDING_PATCH_SWEEP_H_

#include "garden_landing_growth.h"
#include "garden_lifetimes.h"
#include <stdio.h>

#define TOY_FACTORY_GARDEN_PATCH_FIRST_DAY   192U
#define TOY_FACTORY_GARDEN_PATCH_PERIOD_DAYS 8U
#define TOY_FACTORY_GARDEN_PATCH_WIDTH       4U
#define TOY_FACTORY_GARDEN_PATCH_EVENTS      15U
#define TOY_FACTORY_GARDEN_PATCH_MAX_VICTIMS                                                       \
	(TOY_FACTORY_GARDEN_PATCH_EVENTS * PICOSYSTEM_GARDEN_MAX_PLANTS)

#define TOY_FACTORY_GARDEN_RECURRING_FIRST_DAY   396U
#define TOY_FACTORY_GARDEN_RECURRING_PERIOD_DAYS 32U
#define TOY_FACTORY_GARDEN_RECURRING_FIRST_PATCH 1U
#define TOY_FACTORY_GARDEN_RECURRING_EVENTS      4U
#define TOY_FACTORY_GARDEN_RECURRING_MAX_VICTIMS                                                   \
	(TOY_FACTORY_GARDEN_RECURRING_EVENTS * PICOSYSTEM_GARDEN_MAX_PLANTS)

#define TOY_FACTORY_GARDEN_PATCH_FOLLOWUP_DAY         524U
#define TOY_FACTORY_GARDEN_PATCH_FOLLOWUP_FIRST_PATCH 5U
#define TOY_FACTORY_GARDEN_PATCH_FOLLOWUP_EVENTS      1U
#define TOY_FACTORY_GARDEN_PATCH_FOLLOWUP_MAX_VICTIMS PICOSYSTEM_GARDEN_MAX_PLANTS

#define TOY_FACTORY_GARDEN_PATCH_RENEWAL_EVENTS 7U
#define TOY_FACTORY_GARDEN_PATCH_RENEWAL_MAX_VICTIMS                                               \
	(TOY_FACTORY_GARDEN_PATCH_RENEWAL_EVENTS * PICOSYSTEM_GARDEN_MAX_PLANTS)

struct toy_factory_garden_patch_victim {
	uint32_t lineage, age;
	uint16_t nodes, energy, water;
};

struct toy_factory_garden_patch_event {
	uint32_t tick, before_world_hash, after_world_hash, before_run_hash, after_run_hash;
	uint8_t first_column, last_column, count;
	struct toy_factory_garden_patch_victim victims[PICOSYSTEM_GARDEN_MAX_PLANTS];
};

/* Host-owned, zero-initialized log. Empty spatial hits are events too. */
struct toy_factory_garden_patch_sweep {
	uint8_t count;
	struct toy_factory_garden_patch_event events[TOY_FACTORY_GARDEN_PATCH_EVENTS];
};

/* Call after each ordinary step and its observers. Fixed schedule, no RNG,
 * age/lineage preference or fallback site. Run, ledger and log are disjoint;
 * failure changes none. Corpses remain until ordinary decomposition.
 */
int toy_factory_garden_patch_sweep_step(struct toy_factory_garden_landing_growth_run *run,
					struct toy_factory_garden_lifetimes *ledger,
					struct toy_factory_garden_patch_sweep *sweep);
uint32_t toy_factory_garden_patch_sweep_hash(uint32_t base);
int toy_factory_garden_patch_sweep_print(FILE *stream,
					 const struct toy_factory_garden_patch_sweep *sweep);

/* Separate fixed host continuation. Use a distinct zero-initialized log;
 * original sweep receipts and hashes are never relabeled or replaced.
 */
int toy_factory_garden_patch_recurring_step(struct toy_factory_garden_landing_growth_run *run,
					    struct toy_factory_garden_lifetimes *ledger,
					    struct toy_factory_garden_patch_sweep *recurring);
uint32_t toy_factory_garden_patch_recurring_hash(uint32_t base);
int toy_factory_garden_patch_recurring_print(
	FILE *stream, const struct toy_factory_garden_patch_sweep *recurring);

/* One additional winter, separately receipted. Does not extend or relabel the
 * four-event recurring preset; the CLI requires that history explicitly.
 */
int toy_factory_garden_patch_followup_step(struct toy_factory_garden_landing_growth_run *run,
					   struct toy_factory_garden_lifetimes *ledger,
					   struct toy_factory_garden_patch_sweep *followup);
uint32_t toy_factory_garden_patch_followup_hash(uint32_t base);
int toy_factory_garden_patch_followup_print(FILE *stream,
					    const struct toy_factory_garden_patch_sweep *followup);

/* A complete seven-band recurring cycle, distinct from the older presets.
 * Disabled control receipts must contain no events. The CLI owns the mode.
 */
int toy_factory_garden_patch_renewal_step(struct toy_factory_garden_landing_growth_run *run,
					  struct toy_factory_garden_lifetimes *ledger,
					  struct toy_factory_garden_patch_sweep *renewal);
uint32_t toy_factory_garden_patch_renewal_hash(uint32_t base, bool enabled);
int toy_factory_garden_patch_renewal_print(FILE *stream,
					   const struct toy_factory_garden_patch_sweep *renewal,
					   bool enabled);

#endif
