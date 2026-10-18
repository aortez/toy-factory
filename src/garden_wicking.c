/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_wicking.h"
#include "garden_world.h"

#include <errno.h>

_Static_assert(PICOSYSTEM_GARDEN_WICKING_PERIOD == 4U * PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR,
	       "wicking cadence must remain four ecology steps");

int picosystem_garden_wicking_step(uint8_t *moisture, size_t count, uint32_t logic_tick)
{
	if ((moisture == NULL) || (count != PICOSYSTEM_GARDEN_SOIL_CELL_COUNT)) {
		return -EINVAL;
	}
	if ((logic_tick <= PICOSYSTEM_GARDEN_WICKING_AFTER_TICK) ||
	    ((logic_tick % PICOSYSTEM_GARDEN_WICKING_PERIOD) != 0U)) {
		return 0;
	}
	int moved = 0;
	/* Ascending rows prevent newly lifted water from rising twice this pass. */
	for (size_t row = 0U; row + 1U < PICOSYSTEM_GARDEN_SOIL_ROWS; ++row) {
		for (size_t column = 0U; column < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++column) {
			uint8_t *const upper =
				&moisture[row * PICOSYSTEM_GARDEN_GRID_COLUMNS + column];
			uint8_t *const lower = upper + PICOSYSTEM_GARDEN_GRID_COLUMNS;
			if ((unsigned int)*lower > (unsigned int)*upper + 1U) {
				--*lower;
				++*upper;
				++moved;
			}
		}
	}
	return moved;
}
