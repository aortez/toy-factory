/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_LANDING_RECRUITMENT_H_
#define TOY_FACTORY_GARDEN_LANDING_RECRUITMENT_H_

#include "garden_lifetimes.h"
#include "garden_resource_audit.h"
#include "garden_seed_audit.h"
#include <stdio.h>

/* Read-only JSONL publisher, called after lifetime accounting. Every seed check
 * and every descendant's birth-through-first-day resource sample is retained.
 * No persistent state or allocation. A failed write invalidates the whole trace.
 */
int toy_factory_garden_recruitment_print(FILE *stream, const struct picosystem_garden_world *world,
					 const struct toy_factory_garden_lifetimes *lifetimes,
					 const struct picosystem_garden_seed_audit *seeds,
					 const struct picosystem_garden_resource_audit *resources);

/* All living plants and this step's deaths, including founders and adults.
 * Same receipts as the first-day trace; caller owns the bounded time window.
 * Older corpses are omitted. Plant IDs remain stable through slot compaction.
 */
int toy_factory_garden_adult_resources_print(
	FILE *stream, const struct picosystem_garden_world *world,
	const struct toy_factory_garden_lifetimes *lifetimes,
	const struct picosystem_garden_seed_audit *seeds,
	const struct picosystem_garden_resource_audit *resources);

#endif
