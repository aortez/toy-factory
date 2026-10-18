/* SPDX-License-Identifier: Apache-2.0 */
/* Included once in the adapted landing runner, beside the original bridge. */
#include "research_fallback.h"

int research_fallback_step_internal(struct toy_factory_maintenance_run *run,
				    const struct picosystem_garden_leaf_policy *leaf,
				    struct picosystem_garden_death_audit *deaths,
				    struct picosystem_garden_seed_audit *seeds,
				    struct picosystem_garden_resource_audit *resources,
				    const struct toy_factory_garden_growth_observer *observer,
				    const struct toy_factory_leaf_replay_route *route,
				    const struct research_fallback_route *placement)
{
	if ((run == NULL) || (leaf == NULL) || (leaf->decide == NULL) || (placement == NULL)) {
		return -EINVAL;
	}
	struct toy_factory_garden_landing_growth_run *const g = &run->growth;
	const struct toy_factory_garden_landing_water_config water = {
		.version = TOY_FACTORY_GARDEN_LANDING_ARBITRATION_VERSION,
		.enabled = 1U,
		.eligible = 1U};
	return step_with_placement(&g->base, deaths, seeds, NULL, NULL, NULL, resources, &water,
				   NULL, g->node_limit, g->budget_mode, observer, &g->placement,
				   NULL, g->seed_order_after, &g->root_choice, &g->root_allocation,
				   &g->seed_cursor, &g->seed_wait, NULL, leaf, route, placement);
}
