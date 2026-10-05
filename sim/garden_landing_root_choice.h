/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_LANDING_ROOT_CHOICE_H_
#define TOY_FACTORY_GARDEN_LANDING_ROOT_CHOICE_H_

#include "garden_agent.h"

#if defined(__ZEPHYR__)
#error "Root choice is a host-only counterfactual, not a firmware policy"
#endif

/* Both zero disables the focal probe. Otherwise tick is positive/ecology-aligned.
 * Pure configuration: no fired flag, random draw or checkpoint-owned state.
 */
struct toy_factory_garden_root_choice {
	uint32_t tick;
	uint32_t lineage;
	/* Mutually exclusive with focal IDs; requires the complete daylight chain.
	 * Birth-root preference at age 1, spending checks from age 2 for every
	 * living non-founder, including later descendants. Never a default.
	 */
	bool all_offspring;
	bool energy_reserve;
	/* Requires energy_reserve; same first-day scope, never a default. */
	bool afternoon_reserve;
	/* Requires both checks; only removes their first-day cutoff. */
	bool continuous_energy;
	/* Requires continuous_energy; tighter current-light afternoon forecast only. */
	bool daylight_energy;
	/* Requires daylight_energy; add an estimated dawn upkeep reserve. */
	bool dawn_reserve;
	/* Explicit direction trial over this population guard configuration.
	 * Applies to eligible roots of founders and offspring; never a default.
	 */
	bool wet_direction;
};

int toy_factory_garden_root_choice_validate(const struct toy_factory_garden_root_choice *choice);

/* Called inside ordinary growth arbitration, after its global affordability
 * check. Only boosts existing eligible root EXTEND bids; all other decision
 * fields and normal tie-breaking remain intact. Errors leave decision intact.
 */
int toy_factory_garden_root_choice_apply(
	const struct picosystem_garden_world *world,
	const struct picosystem_garden_agent_observation *observation,
	const struct toy_factory_garden_root_choice *choice, uint8_t budget_mode,
	struct picosystem_garden_agent_decision *decision);

/* Optional follow-up: ages 2..256 of the named offspring born at choice.tick,
 * or its remaining lifetime with continuous_energy.
 * With all_offspring, applies to all living non-founders from age 2.
 * Birth/root purchases stay unguarded. Pure eligibility,
 * not a proposal rewrite. Errors leave allowed intact.
 */
bool toy_factory_garden_root_energy_active(
	const struct picosystem_garden_world *world,
	const struct picosystem_garden_agent_observation *observation,
	const struct toy_factory_garden_root_choice *choice);
int toy_factory_garden_root_energy_eligible(
	const struct picosystem_garden_world *world,
	const struct picosystem_garden_agent_observation *observation,
	const struct toy_factory_garden_root_choice *choice,
	const struct picosystem_garden_agent_decision *decision, bool *allowed);

#endif
