/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_LANDING_SIGNAL_H_
#define TOY_FACTORY_GARDEN_LANDING_SIGNAL_H_

#include "garden_landing_run.h"

#define TOY_FACTORY_GARDEN_LANDING_SIGNAL_VERSION 1U

enum toy_factory_garden_landing_occupancy_probe {
	TOY_FACTORY_GARDEN_LANDING_OCCUPANCY_LIVE,
	TOY_FACTORY_GARDEN_LANDING_OCCUPANCY_NEUTRAL,
	TOY_FACTORY_GARDEN_LANDING_OCCUPANCY_OCCUPIED,
	TOY_FACTORY_GARDEN_LANDING_OCCUPANCY_OPEN,
	TOY_FACTORY_GARDEN_LANDING_OCCUPANCY_COUNT,
};

enum toy_factory_garden_landing_resource_probe {
	TOY_FACTORY_GARDEN_LANDING_RESOURCE_LIVE,
	TOY_FACTORY_GARDEN_LANDING_RESOURCE_MID,
	TOY_FACTORY_GARDEN_LANDING_RESOURCE_LOW,
	TOY_FACTORY_GARDEN_LANDING_RESOURCE_HIGH,
	TOY_FACTORY_GARDEN_LANDING_RESOURCE_COUNT,
};

struct toy_factory_garden_landing_signal_config {
	uint8_t version;
	uint8_t occupancy;
	uint8_t resources;
	uint8_t reserved;
};

/* Complete host-only checkpoint. Config and model are fixed for the run;
 * value copies resume independently, with no pointers or hidden global state.
 */
struct toy_factory_garden_landing_signal_run {
	struct toy_factory_garden_landing_run base;
	struct toy_factory_garden_landing_signal_config config;
};

/* Pure packet-copy transformation. Real packet, cache and legacy inputs remain
 * unchanged. Only valid sources change; roots/OOB/absent sources stay masked.
 * Current-only, flags=0 is the supported model contract. Every output is
 * caller-owned, non-aliasing and unchanged on failure.
 */
int toy_factory_garden_landing_signal_apply(
	const struct picosystem_garden_agent_observation *observation,
	const struct picosystem_garden_landing_packet *packet,
	const struct toy_factory_garden_landing_signal_config *config,
	struct picosystem_garden_landing_packet *output);
int toy_factory_garden_landing_signal_init(
	const struct picosystem_garden_world *world,
	const struct toy_factory_garden_landing_model *model,
	const struct toy_factory_garden_landing_signal_config *config,
	struct toy_factory_garden_landing_signal_run *run);
int toy_factory_garden_landing_signal_step(struct toy_factory_garden_landing_signal_run *run,
					   struct picosystem_garden_death_audit *deaths,
					   struct picosystem_garden_seed_audit *seeds);

/* Separate GSP1 identity includes base state/model/cache and every config byte.
 * Diagnostic fingerprint, not authentication or a collision-free identifier.
 */
int toy_factory_garden_landing_signal_hash(const struct toy_factory_garden_landing_signal_run *run,
					   uint32_t *hash);

#endif
