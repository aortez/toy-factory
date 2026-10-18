/* SPDX-License-Identifier: Apache-2.0 */
#ifndef PICOSYSTEM_GARDEN_DISPERSAL_H_
#define PICOSYSTEM_GARDEN_DISPERSAL_H_

#include "garden_world.h"
#if defined(TOY_FACTORY_GARDEN_LATE_DISPERSAL)
#include "garden_late_dispersal.h"
#endif

/* Pure placement transform shared by production and observers. Caller supplies
 * a valid origin/parent trait and an existing draw; this never advances RNG.
 */
static inline uint8_t picosystem_garden_dispersed_column_range(uint8_t origin, int8_t trait,
							       uint32_t random, uint8_t minimum,
							       uint8_t distances)
{
	const int32_t distance = minimum + trait + (int32_t)((random >> 1U) % distances);
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

static inline uint8_t picosystem_garden_dispersed_column(uint8_t origin, int8_t trait,
							 uint32_t random)
{
	return picosystem_garden_dispersed_column_range(origin, trait, random,
							PICOSYSTEM_GARDEN_DISPERSAL_MINIMUM,
							PICOSYSTEM_GARDEN_DISPERSAL_CHOICES);
}

/* Clock-dependent support is compile-time isolated. These helpers also serve
 * observers so their reach maps cannot silently describe the old support.
 */
static inline uint8_t picosystem_garden_dispersal_choices_at(uint32_t tick)
{
#if defined(TOY_FACTORY_GARDEN_LATE_DISPERSAL)
	if (tick > PICOSYSTEM_GARDEN_LATE_DISPERSAL_AFTER_TICK) {
		return 2U * PICOSYSTEM_GARDEN_LATE_DISPERSAL_DISTANCES;
	}
#else
	(void)tick;
#endif
	return 2U * PICOSYSTEM_GARDEN_DISPERSAL_CHOICES;
}

static inline uint8_t picosystem_garden_dispersed_column_at(uint8_t origin, int8_t trait,
							    uint32_t random, uint32_t tick)
{
#if defined(TOY_FACTORY_GARDEN_LATE_DISPERSAL)
	if (tick > PICOSYSTEM_GARDEN_LATE_DISPERSAL_AFTER_TICK) {
		return picosystem_garden_dispersed_column_range(
			origin, trait, random, PICOSYSTEM_GARDEN_LATE_DISPERSAL_MINIMUM,
			PICOSYSTEM_GARDEN_LATE_DISPERSAL_DISTANCES);
	}
#else
	(void)tick;
#endif
	return picosystem_garden_dispersed_column(origin, trait, random);
}

#endif
