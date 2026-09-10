/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "garden_light.h"

#include <errno.h>
#include <stdint.h>
#include <string.h>

#define GARDEN_SUN_RAY_FRACTION_BITS 4U
#define GARDEN_SUN_RAY_HALF_CELL     (1U << (GARDEN_SUN_RAY_FRACTION_BITS - 1U))

_Static_assert(PICOSYSTEM_GARDEN_SUN_CYCLE_TICKS == (UINT8_MAX + 1U),
	       "Garden sun phase must cover one byte exactly");
_Static_assert(PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE == (2U * PICOSYSTEM_GARDEN_SUN_NOON_PHASE),
	       "Garden daylight must be symmetric around noon");

static int16_t rounded_ray_offset(int8_t ray_step_x_q4, uint8_t row_distance)
{
	const int16_t product = (int16_t)ray_step_x_q4 * row_distance;
	if (product >= 0) {
		return (int16_t)((product + (int16_t)GARDEN_SUN_RAY_HALF_CELL) >>
				 GARDEN_SUN_RAY_FRACTION_BITS);
	}
	return (int16_t) -
	       (((-product) + (int16_t)GARDEN_SUN_RAY_HALF_CELL) >> GARDEN_SUN_RAY_FRACTION_BITS);
}

struct picosystem_garden_sun picosystem_garden_sun_at(uint32_t ecology_tick_count)
{
	const uint8_t phase =
		(uint8_t)((ecology_tick_count + PICOSYSTEM_GARDEN_SUN_INITIAL_PHASE) & UINT8_MAX);
	const uint16_t traversal = (phase <= PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE)
					   ? phase
					   : (uint16_t)(PICOSYSTEM_GARDEN_SUN_CYCLE_TICKS - phase);
	const uint16_t ray_range = 2U * PICOSYSTEM_GARDEN_SUN_MAX_RAY_STEP_X_Q4;
	const int16_t ray_step_x_q4 =
		PICOSYSTEM_GARDEN_SUN_MAX_RAY_STEP_X_Q4 -
		(int16_t)((traversal * ray_range + (PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE / 2U)) /
			  PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE);

	uint8_t strength = PICOSYSTEM_GARDEN_LIGHT_MINIMUM;
	if (phase <= PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE) {
		const uint8_t height =
			(phase <= PICOSYSTEM_GARDEN_SUN_NOON_PHASE)
				? phase
				: (uint8_t)(PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE - phase);
		const uint16_t strength_range = UINT8_MAX - PICOSYSTEM_GARDEN_LIGHT_MINIMUM;
		strength = (uint8_t)(PICOSYSTEM_GARDEN_LIGHT_MINIMUM +
				     (((uint16_t)height * strength_range +
				       (PICOSYSTEM_GARDEN_SUN_NOON_PHASE / 2U)) /
				      PICOSYSTEM_GARDEN_SUN_NOON_PHASE));
	}

	return (struct picosystem_garden_sun){
		.phase = phase,
		.strength = strength,
		.ray_step_x_q4 = (int8_t)ray_step_x_q4,
	};
}

int picosystem_garden_light_solve(const uint8_t shade[PICOSYSTEM_GARDEN_LIGHT_CELL_COUNT],
				  const struct picosystem_garden_sun *sun,
				  uint8_t light[PICOSYSTEM_GARDEN_LIGHT_CELL_COUNT])
{
	if ((shade == NULL) || (sun == NULL) || (light == NULL) || (shade == light)) {
		return -EINVAL;
	}
	if ((sun->strength < PICOSYSTEM_GARDEN_LIGHT_MINIMUM) ||
	    (sun->ray_step_x_q4 < -PICOSYSTEM_GARDEN_SUN_MAX_RAY_STEP_X_Q4) ||
	    (sun->ray_step_x_q4 > PICOSYSTEM_GARDEN_SUN_MAX_RAY_STEP_X_Q4)) {
		return -ERANGE;
	}
	if (sun->strength == PICOSYSTEM_GARDEN_LIGHT_MINIMUM) {
		memset(light, PICOSYSTEM_GARDEN_LIGHT_MINIMUM, PICOSYSTEM_GARDEN_LIGHT_CELL_COUNT);
		return 0;
	}

	const uint16_t maximum_reduction =
		(uint16_t)(sun->strength - PICOSYSTEM_GARDEN_LIGHT_MINIMUM);
	for (uint8_t row = 0U; row < PICOSYSTEM_GARDEN_CANOPY_ROWS; ++row) {
		for (uint8_t column = 0U; column < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++column) {
			uint16_t reduction = 0U;
			for (uint8_t distance = 1U; distance <= row; ++distance) {
				const int16_t source_column =
					(int16_t)column -
					rounded_ray_offset(sun->ray_step_x_q4, distance);
				if ((source_column < 0) ||
				    (source_column >= (int16_t)PICOSYSTEM_GARDEN_GRID_COLUMNS)) {
					break;
				}
				const uint8_t source_row = (uint8_t)(row - distance);
				const uint16_t source_index =
					(uint16_t)(((uint16_t)source_row *
						    PICOSYSTEM_GARDEN_GRID_COLUMNS) +
						   (uint16_t)source_column);
				reduction += shade[source_index];
				if (reduction >= maximum_reduction) {
					reduction = maximum_reduction;
					break;
				}
			}
			const uint16_t index =
				(uint16_t)(((uint16_t)row * PICOSYSTEM_GARDEN_GRID_COLUMNS) +
					   column);
			light[index] = (uint8_t)(sun->strength - reduction);
		}
	}
	return 0;
}
