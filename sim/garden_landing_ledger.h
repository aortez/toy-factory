/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_LANDING_LEDGER_H_
#define TOY_FACTORY_GARDEN_LANDING_LEDGER_H_

#include "garden_lifetimes.h"
#include "garden_seed_audit.h"
#include <stdio.h>

#define TOY_FACTORY_GARDEN_LANDING_MAX_PURCHASES 65536U

struct toy_factory_garden_landing_purchase {
	uint32_t parent, birth, end, child;
	uint16_t generation;
	uint8_t column, species, outcome;
};

/* Host-owned, single-trial append ledger; no allocation or simulation state.
 * Reset at tick zero, then census after each audited ecology step. The shared
 * lifetime ledger has already received that step's deaths and births. Errors
 * abort the trial: this diagnostic ledger need not roll back partial appends.
 */
struct toy_factory_garden_landing_ledger {
	struct {
		uint32_t purchases;
		uint16_t generation;
		uint8_t column;
	} plants[TOY_FACTORY_GARDEN_EVALUATION_MAX_TRACKED_LINEAGES + 1U];
	struct toy_factory_garden_landing_purchase seeds[TOY_FACTORY_GARDEN_LANDING_MAX_PURCHASES];
	uint32_t active[PICOSYSTEM_GARDEN_MAX_SEEDS];
	uint32_t count, seed_count, active_count, last_tick;
};

int toy_factory_garden_landing_ledger_reset(struct toy_factory_garden_landing_ledger *out,
					    const struct picosystem_garden_world *world,
					    const struct toy_factory_garden_lifetimes *lifetimes);
int toy_factory_garden_landing_ledger_step(struct toy_factory_garden_landing_ledger *out,
					   const struct picosystem_garden_world *world,
					   const struct toy_factory_garden_lifetimes *lifetimes,
					   const struct picosystem_garden_seed_audit *audit);
/* JSON object members, without enclosing braces. Origin is zero; no pruning. */
int toy_factory_garden_landing_ledger_print(FILE *stream,
					    const struct toy_factory_garden_landing_ledger *ledger,
					    const struct toy_factory_garden_lifetimes *lifetimes);

#endif
