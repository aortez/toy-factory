/* SPDX-License-Identifier: Apache-2.0 */
#include <errno.h>
#include <stddef.h>

#include "garden_dark_guard.h"
#include "garden_light.h"

int picosystem_garden_dark_project(uint16_t energy, uint16_t nodes, uint8_t stress,
				   uint8_t sun_phase, struct picosystem_garden_dark_budget *result)
{
	if ((result == NULL) || (energy > 256U) || (nodes == 0U) ||
	    (nodes > PICOSYSTEM_GARDEN_MAX_NODES) ||
	    (stress >= PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD)) {
		return -EINVAL;
	}
	_Static_assert(PICOSYSTEM_GARDEN_SUN_CYCLE_TICKS == 256U &&
			       PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR == 4U &&
			       PICOSYSTEM_GARDEN_SUN_INITIAL_PHASE % 4U == 0U,
		       "Revisit dark-budget phase/payment alignment");
	struct picosystem_garden_dark_budget budget = {
		.energy = energy,
		.stress = stress,
		.peak_stress = stress,
		.upkeep = (uint8_t)((nodes + 7U) / 8U),
	};
	for (uint16_t step = 1U; step <= PICOSYSTEM_GARDEN_SUN_CYCLE_TICKS; ++step) {
		const struct picosystem_garden_sun sun = picosystem_garden_sun_at(
			(uint32_t)sun_phase + step + PICOSYSTEM_GARDEN_SUN_CYCLE_TICKS -
			PICOSYSTEM_GARDEN_SUN_INITIAL_PHASE);
		if (sun.strength >= 64U) {
			break;
		}
		budget.supported = true;
		++budget.dark_steps;
		if ((sun.phase % PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR) != 0U) {
			continue;
		}
		++budget.payments;
		if (budget.death_step != 0U) {
			continue;
		}
		if (budget.energy >= budget.upkeep) {
			budget.energy = (uint16_t)(budget.energy - budget.upkeep);
			if (budget.stress > 0U) {
				--budget.stress;
			}
		} else {
			budget.energy = 0U;
			++budget.stress;
			if (budget.first_shortage_step == 0U) {
				budget.first_shortage_step = (uint8_t)step;
			}
			if (budget.stress == PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD) {
				budget.death_step = (uint8_t)step;
			}
		}
		if (budget.stress > budget.peak_stress) {
			budget.peak_stress = budget.stress;
		}
	}
	*result = budget;
	return 0;
}
