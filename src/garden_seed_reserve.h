/* SPDX-License-Identifier: Apache-2.0 */
#ifndef PICOSYSTEM_GARDEN_SEED_RESERVE_H_
#define PICOSYSTEM_GARDEN_SEED_RESERVE_H_

#include "garden_world.h"

#if !defined(TOY_FACTORY_GARDEN_SEED_RESERVE)
#error "Seed reserve forecast is an explicit host experiment"
#endif

struct picosystem_garden_seed_reserve_forecast {
	int32_t after_seed;
	int32_t projected_sunset;
	uint16_t maintenance_cost;
	uint16_t night_upkeep;
	bool allowed;
};

/* Call at the reproduction decision point, after current upkeep/growth/renewal.
 * Pure bounded heuristic; assumes fixed body/income and no subsequent optional
 * spending. Covers sunset through the last night payment, not dawn recovery.
 * Invalid input leaves output unchanged. No state, allocation or RNG access.
 */
int picosystem_garden_seed_reserve_forecast(
	uint16_t energy, uint8_t income, uint16_t nodes, uint8_t sun_phase,
	struct picosystem_garden_seed_reserve_forecast *forecast);
#endif
