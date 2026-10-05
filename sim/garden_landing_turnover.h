/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_LANDING_TURNOVER_H_
#define TOY_FACTORY_GARDEN_LANDING_TURNOVER_H_

#include "garden_landing_growth.h"
#include "garden_lifetimes.h"
#include <stdio.h>

struct toy_factory_garden_landing_turnover {
	uint32_t tick, lineage_id;
	uint32_t before_world_hash, after_world_hash;
	uint32_t before_run_hash, after_run_hash;
	uint16_t nodes, energy, water;
	uint8_t column;
};

/* Host-only, post-observation ecology boundary. Kill one named >one-day adult
 * while retaining its body for ordinary decomposition. Preserve cache history,
 * seeds, soil and RNG. Disjoint outputs; failure changes none of them.
 */
int toy_factory_garden_landing_turnover_apply(struct toy_factory_garden_landing_growth_run *run,
					      struct toy_factory_garden_lifetimes *ledger,
					      uint32_t lineage_id,
					      struct toy_factory_garden_landing_turnover *result);
uint32_t toy_factory_garden_landing_turnover_hash(uint32_t base, uint32_t tick,
						  uint32_t lineage_id);
int toy_factory_garden_landing_turnover_print(
	FILE *stream, const struct toy_factory_garden_landing_turnover *result);
int toy_factory_garden_landing_turnover_print_second(
	FILE *stream, const struct toy_factory_garden_landing_turnover *result);

#endif
