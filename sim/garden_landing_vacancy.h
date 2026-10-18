/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_LANDING_VACANCY_H_
#define TOY_FACTORY_GARDEN_LANDING_VACANCY_H_

#include "garden_gap.h"
#include "garden_landing_growth.h"
#include "garden_lifetimes.h"

struct toy_factory_garden_landing_vacancy {
	struct toy_factory_garden_gap gap;
	uint32_t before_run_hash;
	uint32_t after_run_hash;
};

/* All outputs are disjoint. At an ecology boundary, export an explicitly
 * named >one-day adult. Failure preserves run, ledger and output. Keep cache
 * history; the next ordinary capture precedes the next policy decision.
 */
int toy_factory_garden_landing_vacancy_apply(struct toy_factory_garden_landing_growth_run *run,
					     struct toy_factory_garden_lifetimes *ledger,
					     uint32_t lineage_id,
					     struct toy_factory_garden_landing_vacancy *result);
uint32_t toy_factory_garden_landing_vacancy_hash(uint32_t base, uint32_t tick, uint32_t lineage_id);
int toy_factory_garden_landing_vacancy_print(
	FILE *stream, uint32_t tick, uint32_t lineage_id,
	const struct toy_factory_garden_landing_vacancy *result);

#endif
