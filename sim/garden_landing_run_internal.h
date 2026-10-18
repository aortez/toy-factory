/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_LANDING_RUN_INTERNAL_H_
#define TOY_FACTORY_GARDEN_LANDING_RUN_INTERNAL_H_

#include "garden_landing_signal.h"
#include "garden_landing_water.h"
#include "garden_landing_growth.h"

/* Internal bridge: signal_run owns/validates config and includes it in identity.
 * All step paths share the same world/cache/audit rollback implementation.
 */
int toy_factory_garden_landing_run_step_signal_internal(
	struct toy_factory_garden_landing_run *run,
	const struct toy_factory_garden_landing_signal_config *config,
	struct picosystem_garden_death_audit *deaths, struct picosystem_garden_seed_audit *seeds);

struct toy_factory_garden_landing_water_context {
	const struct picosystem_garden_world *world;
	struct toy_factory_garden_landing_water_audit *audit;
	bool record_bids;
};
int toy_factory_garden_landing_water_observe_internal(
	const struct picosystem_garden_agent_observation *observation,
	const struct picosystem_garden_agent_memory *memory,
	const struct picosystem_garden_landing_packet *packet,
	const struct picosystem_garden_agent_decision *decision, void *context);
int toy_factory_garden_landing_run_step_water_internal(
	struct toy_factory_garden_landing_run *run,
	const struct toy_factory_garden_landing_water_config *config,
	struct picosystem_garden_death_audit *deaths, struct picosystem_garden_seed_audit *seeds,
	struct picosystem_garden_resource_audit *resources,
	struct toy_factory_garden_landing_water_audit *audit);

int toy_factory_garden_landing_run_step_growth_internal(
	struct toy_factory_garden_landing_run *run, uint8_t node_limit, uint8_t budget_mode,
	struct picosystem_garden_death_audit *deaths, struct picosystem_garden_seed_audit *seeds,
	struct picosystem_garden_resource_audit *resources,
	const struct toy_factory_garden_growth_observer *observer,
	const struct toy_factory_garden_placement_config *placement,
	struct toy_factory_garden_placement_audit *placement_audit, uint32_t seed_order_after,
	const struct toy_factory_garden_root_choice *root_choice,
	const struct toy_factory_garden_root_allocation *root_allocation,
	struct toy_factory_garden_seed_cursor *seed_cursor,
	struct toy_factory_garden_seed_wait *seed_wait);

#endif
