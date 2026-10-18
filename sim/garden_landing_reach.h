/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_LANDING_REACH_H_
#define TOY_FACTORY_GARDEN_LANDING_REACH_H_

#include "garden_seed_audit.h"
#include <stdio.h>

/* Host-only post-step publisher for ordinary ecology. Caller owns the stream,
 * world and exact sequential seed receipts. No allocation, RNG draw or retained
 * state. Validation precedes writes; any I/O failure invalidates the trace.
 * Purchase sites are post-final-light-refresh, not future germination checks.
 */
int toy_factory_garden_reach_print(FILE *stream, const struct picosystem_garden_world *world,
				   const struct picosystem_garden_seed_audit *seeds);

#endif
