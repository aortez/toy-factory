/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_LANDING_WATER_H_
#define TOY_FACTORY_GARDEN_LANDING_WATER_H_

#include "garden_landing_run.h"
#include "garden_seedling_reserve.h"

#include <stdio.h>

#define TOY_FACTORY_GARDEN_LANDING_WATER_VERSION       1U
#define TOY_FACTORY_GARDEN_LANDING_ARBITRATION_VERSION 2U

struct toy_factory_garden_landing_water_config {
	uint8_t version;
	uint8_t enabled;
	/* Version 1 requires zero. Version 2 requires enabled=1; zero is the
	 * original veto, one ranks only water-eligible bids. Never a device mode.
	 */
	uint8_t eligible;
};

/* Model and config are fixed for this host-only run. Value copies resume
 * independently; no retained pointers or hidden mutable state.
 */
struct toy_factory_garden_landing_water_run {
	struct toy_factory_garden_landing_run base;
	struct toy_factory_garden_landing_water_config config;
};

struct toy_factory_garden_landing_water_winner {
	uint32_t lineage;
	uint16_t bids;
	uint16_t denied_bids;
	uint16_t funded_wet_root_bids;
	struct picosystem_garden_agent_observation observation;
	struct picosystem_garden_agent_decision original;
	struct toy_factory_garden_seedling_reserve_forecast forecast;
};

/* Bounded per-plant winners, indexed only for the duration of one step.
 * Only ages 1..256 of living descendants are present. A zero lineage is absent.
 * All outputs, including this audit, remain unchanged on step failure.
 */
struct toy_factory_garden_landing_water_audit {
	struct toy_factory_garden_landing_water_winner plants[PICOSYSTEM_GARDEN_MAX_PLANTS];
	uint16_t bid_count;
	struct {
		struct picosystem_garden_agent_observation observation;
		struct picosystem_garden_agent_decision decision;
		struct picosystem_garden_agent_memory memory;
		struct toy_factory_garden_seedling_reserve_forecast forecast;
	} bids[PICOSYSTEM_GARDEN_MAX_NODES];
};

int toy_factory_garden_landing_water_init(
	const struct picosystem_garden_world *world,
	const struct toy_factory_garden_landing_model *model,
	const struct toy_factory_garden_landing_water_config *config,
	struct toy_factory_garden_landing_water_run *run);
/* Caller-owned outputs must not alias the run or each other. Resources and
 * the winner audit are independently optional; deaths and seeds are required.
 */
int toy_factory_garden_landing_water_step(struct toy_factory_garden_landing_water_run *run,
					  struct picosystem_garden_death_audit *deaths,
					  struct picosystem_garden_seed_audit *seeds,
					  struct picosystem_garden_resource_audit *resources,
					  struct toy_factory_garden_landing_water_audit *audit);
int toy_factory_garden_landing_water_hash(const struct toy_factory_garden_landing_water_run *run,
					  uint32_t *hash);
int toy_factory_garden_landing_water_print(
	FILE *stream, const struct toy_factory_garden_landing_water_run *run,
	const struct toy_factory_garden_landing_water_audit *audit);

/* Local-observation water predicate; does not change the decision or memory. */
int toy_factory_garden_landing_water_eligible(
	const struct picosystem_garden_agent_observation *observation,
	const struct picosystem_garden_agent_decision *decision, bool *allowed,
	const void *context);

#endif
