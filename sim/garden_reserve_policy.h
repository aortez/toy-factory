/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_RESERVE_POLICY_H_
#define TOY_FACTORY_GARDEN_RESERVE_POLICY_H_

#include "garden_agent.h"

#if defined(__ZEPHYR__)
#error "Reserve policy is a host-only experiment"
#endif

#define TOY_FACTORY_GARDEN_RESERVE_NAME   "energy-reserve-v1"
#define TOY_FACTORY_GARDEN_RESERVE_POLICY "neural-reserve-growth"

struct toy_factory_garden_reserve_forecast {
	uint32_t post_nodes;
	uint32_t growth_cost;
	uint32_t maintenance_cost;
	uint32_t daylight_steps;
	uint32_t daylight_credit;
	uint32_t daylight_upkeep;
	uint32_t night_upkeep;
	int32_t projected_sunset;
	bool allowed;
};

/* Pure, bounded forecast from the existing observation. Invalid input returns
 * -EINVAL without changing output. WAIT needs no forecast; paid night actions fail.
 */
int toy_factory_garden_reserve_forecast(
	const struct picosystem_garden_agent_observation *observation, uint8_t action,
	struct toy_factory_garden_reserve_forecast *forecast);

/* Caller-owned immutable base must outlive policy. Rejected bids become WAIT;
 * priority, tip identity, arbitration and proposed memory remain unchanged.
 * Attach the existing leaf policy afterward, as with the night-veto adapter.
 * Invalid arguments return -EINVAL and leave policy untouched.
 */
int toy_factory_garden_reserve_init(const struct picosystem_garden_agent_policy *base,
				    struct picosystem_garden_agent_policy *policy);

#endif
