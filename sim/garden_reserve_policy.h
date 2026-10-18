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

struct toy_factory_garden_afternoon_forecast {
	uint32_t maintenance_before;
	int32_t margin;
	bool applies;
	bool allowed;
};

/* Additional eligibility, not a replacement forecast. Only allocating daylight
 * maintenance increases at/after noon require already-stored energy. Other
 * actions return allowed with zero numeric fields. Invalid input preserves output.
 */
int toy_factory_garden_afternoon_forecast(
	const struct picosystem_garden_agent_observation *observation, uint8_t action,
	struct toy_factory_garden_afternoon_forecast *forecast);

struct toy_factory_garden_daylight_forecast {
	uint32_t useful_steps;
	uint32_t daylight_credit;
	int32_t projected_sunset;
	bool applies;
	bool allowed;
};

/* Extra eligibility only for paid noon/afternoon actions. Hold current global
 * attenuation fixed; credit half current income over estimated productive steps.
 * No future world access. Other actions allow with zero numeric fields; invalid
 * arguments preserve output. The original reserve forecast remains unchanged.
 */
int toy_factory_garden_daylight_forecast(
	const struct picosystem_garden_agent_observation *observation, uint8_t action,
	struct toy_factory_garden_daylight_forecast *forecast);

struct toy_factory_garden_dawn_forecast {
	uint32_t reserve;
	int32_t projected_margin;
	int32_t stores_margin;
	uint8_t first_light_phase;
	uint8_t payment_phase;
	bool applies;
	bool estimate_available;
	bool stores_applies;
	bool allowed;
};

/* Additional paid-afternoon eligibility: reserve post-action upkeep through the
 * first estimated productive morning phase, rounded up to a payment boundary.
 * Hold current global attenuation fixed, without future-world access. If no
 * productive morning can be estimated, deny the paid bid. Nonapplicable actions
 * allow with zero fields; invalid arguments leave output intact.
 */
int toy_factory_garden_dawn_forecast(const struct picosystem_garden_agent_observation *observation,
				     uint8_t action,
				     struct toy_factory_garden_dawn_forecast *forecast);

/* Caller-owned immutable base must outlive policy. Rejected bids become WAIT;
 * priority, tip identity, arbitration and proposed memory remain unchanged.
 * Attach the existing leaf policy afterward, as with the night-veto adapter.
 * Invalid arguments return -EINVAL and leave policy untouched.
 */
int toy_factory_garden_reserve_init(const struct picosystem_garden_agent_policy *base,
				    struct picosystem_garden_agent_policy *policy);

#endif
