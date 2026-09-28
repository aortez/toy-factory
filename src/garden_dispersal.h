/* SPDX-License-Identifier: Apache-2.0 */
#ifndef PICOSYSTEM_GARDEN_DISPERSAL_H_
#define PICOSYSTEM_GARDEN_DISPERSAL_H_

#include "garden_world.h"

/* Pure placement transform shared by production and observers. Caller supplies
 * a valid origin/parent trait and an existing draw; this never advances RNG.
 */
static inline uint8_t picosystem_garden_dispersed_column(uint8_t origin, int8_t trait,
							 uint32_t random)
{
	const int32_t distance = PICOSYSTEM_GARDEN_DISPERSAL_MINIMUM + trait +
				 (int32_t)((random >> 1U) % PICOSYSTEM_GARDEN_DISPERSAL_CHOICES);
	const int32_t direction = ((random & 1U) != 0U) ? 1 : -1;
	int32_t column = (int32_t)origin + (direction * distance);
	if ((column < 0) || (column >= (int32_t)PICOSYSTEM_GARDEN_GRID_COLUMNS)) {
		column = (int32_t)origin - (direction * distance);
	}
	if (column < 0) {
		column = 0;
	} else if (column >= (int32_t)PICOSYSTEM_GARDEN_GRID_COLUMNS) {
		column = PICOSYSTEM_GARDEN_GRID_COLUMNS - 1U;
	}
	return (uint8_t)column;
}

#endif
