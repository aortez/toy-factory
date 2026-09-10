/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_GARDEN_LIGHT_H_
#define PICOSYSTEM_GARDEN_LIGHT_H_

#include <stdint.h>

#include "garden_world.h"

#define PICOSYSTEM_GARDEN_LIGHT_MINIMUM         24U
#define PICOSYSTEM_GARDEN_SUN_CYCLE_TICKS       256U
#define PICOSYSTEM_GARDEN_SUN_NOON_PHASE        64U
#define PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE      128U
#define PICOSYSTEM_GARDEN_SUN_INITIAL_PHASE     PICOSYSTEM_GARDEN_SUN_NOON_PHASE
#define PICOSYSTEM_GARDEN_SUN_MAX_RAY_STEP_X_Q4 12

/* ray_step_x_q4 is the horizontal cell displacement per 16 rows of descent. */
struct picosystem_garden_sun {
	uint8_t phase;
	uint8_t strength;
	int8_t ray_step_x_q4;
};

/* Derive the complete light-source state without storing redundant world state. */
struct picosystem_garden_sun picosystem_garden_sun_at(uint32_t ecology_tick_count);

/* Cast the supplied per-cell opacity field into a caller-owned light field. */
int picosystem_garden_light_solve(const uint8_t shade[PICOSYSTEM_GARDEN_LIGHT_CELL_COUNT],
				  const struct picosystem_garden_sun *sun,
				  uint8_t light[PICOSYSTEM_GARDEN_LIGHT_CELL_COUNT]);

#endif /* PICOSYSTEM_GARDEN_LIGHT_H_ */
