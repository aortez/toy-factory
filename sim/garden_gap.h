/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_GAP_H_
#define TOY_FACTORY_GARDEN_GAP_H_

#include "garden_world.h"

#if !defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE) || defined(__ZEPHYR__)
#error "Gap recovery is a host-only maintenance assay"
#endif

#define TOY_FACTORY_GARDEN_GAP_PROTOCOL "largest-adult-export-v1"

struct toy_factory_garden_gap {
	uint32_t tick;
	uint32_t lineage_id;
	uint32_t before_hash;
	uint32_t after_hash;
	uint16_t nodes;
	uint16_t energy;
	uint16_t water;
	uint8_t column;
};

/* Largest living >=one-day adult, ties by lowest lineage ID; no eligible adult is an error.
 * Neither output nor world is modified on failure. Call only at an ecology boundary.
 */
int toy_factory_garden_gap_apply(struct picosystem_garden_world *world,
				 struct toy_factory_garden_gap *result);
int toy_factory_garden_gap_print(const struct toy_factory_garden_gap *gap);

#endif
