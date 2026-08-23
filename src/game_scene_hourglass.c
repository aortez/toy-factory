/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "game_scene.h"

#include <errno.h>
#include <stdint.h>

#define FIXED(value) PICOSYSTEM_PHYSICS_FIXED_FROM_INT(value)
#define RATIO(n, d)  PICOSYSTEM_PHYSICS_FIXED_RATIO(n, d)

#define HOURGLASS_CENTER_X_PIXELS 120
#define HOURGLASS_CENTER_Y_PIXELS 135
#define HOURGLASS_GRAIN_SPACING   5

#if defined(CONFIG_TOY_FACTORY_HOURGLASS_96_GRAIN_BENCHMARK)
#define HOURGLASS_GRAIN_COUNT 96U
#else
#define HOURGLASS_GRAIN_COUNT 192U
#endif

static const struct picosystem_granular_boundary_config boundaries[] = {
	{
		.start = {.x = FIXED(196), .y = FIXED(42)},
		.end = {.x = FIXED(129), .y = FIXED(HOURGLASS_CENTER_Y_PIXELS)},
		.active_minimum_y = FIXED(42),
		.active_maximum_y = FIXED(HOURGLASS_CENTER_Y_PIXELS),
		.id = 601U,
	},
	{
		.start = {.x = FIXED(129), .y = FIXED(HOURGLASS_CENTER_Y_PIXELS)},
		.end = {.x = FIXED(196), .y = FIXED(228)},
		.active_minimum_y = FIXED(HOURGLASS_CENTER_Y_PIXELS),
		.active_maximum_y = FIXED(228),
		.id = 602U,
	},
	{
		.start = {.x = FIXED(44), .y = FIXED(228)},
		.end = {.x = FIXED(111), .y = FIXED(HOURGLASS_CENTER_Y_PIXELS)},
		.active_minimum_y = FIXED(HOURGLASS_CENTER_Y_PIXELS),
		.active_maximum_y = FIXED(228),
		.id = 603U,
	},
	{
		.start = {.x = FIXED(111), .y = FIXED(HOURGLASS_CENTER_Y_PIXELS)},
		.end = {.x = FIXED(44), .y = FIXED(42)},
		.active_minimum_y = FIXED(42),
		.active_maximum_y = FIXED(HOURGLASS_CENTER_Y_PIXELS),
		.id = 604U,
	},
	/* Resolve caps after sloped walls so corner corrections finish inside both planes. */
	{
		.start = {.x = FIXED(44), .y = FIXED(42)},
		.end = {.x = FIXED(196), .y = FIXED(42)},
		.active_minimum_y = 0,
		.active_maximum_y = FIXED(239),
		.id = 605U,
	},
	{
		.start = {.x = FIXED(196), .y = FIXED(228)},
		.end = {.x = FIXED(44), .y = FIXED(228)},
		.active_minimum_y = 0,
		.active_maximum_y = FIXED(239),
		.id = 606U,
	},
};

#if defined(CONFIG_TOY_FACTORY_HOURGLASS_96_GRAIN_BENCHMARK)
static const uint8_t row_particle_counts[] = {6U, 8U, 10U, 12U, 14U, 16U, 16U, 14U};
_Static_assert(6U + 8U + 10U + 12U + 14U + 16U + 16U + 14U == HOURGLASS_GRAIN_COUNT,
	       "hourglass row population must match its grain count");
#else
static const uint8_t row_particle_counts[] = {8U,  10U, 12U, 14U, 14U, 16U,
					      16U, 18U, 18U, 20U, 22U, 24U};
_Static_assert(8U + 10U + 12U + 14U + 14U + 16U + 16U + 18U + 18U + 20U + 22U + 24U ==
		       HOURGLASS_GRAIN_COUNT,
	       "hourglass row population must match its grain count");
#endif

_Static_assert(HOURGLASS_GRAIN_COUNT <= PICOSYSTEM_GRANULAR_MAX_PARTICLES,
	       "hourglass grains must fit granular storage");
_Static_assert(sizeof(boundaries) / sizeof(boundaries[0]) <= PICOSYSTEM_GRANULAR_MAX_BOUNDARIES,
	       "hourglass boundaries must fit granular storage");
int picosystem_game_scene_hourglass_reset(struct picosystem_granular_world *world)
{
	if (world == NULL) {
		return -EINVAL;
	}
	const struct picosystem_granular_world_config config = {
		.boundaries = boundaries,
		.flip_center = {.x = FIXED(HOURGLASS_CENTER_X_PIXELS),
				.y = FIXED(HOURGLASS_CENTER_Y_PIXELS)},
		.particle_radius = FIXED(2),
		.maximum_speed_per_tick = FIXED(4),
		.velocity_damping = RATIO(255, 256),
		.passage_deadband = FIXED(3),
		.passage_y = FIXED(HOURGLASS_CENTER_Y_PIXELS),
		.boundary_count = (uint16_t)(sizeof(boundaries) / sizeof(boundaries[0])),
	};
	int err = picosystem_granular_world_init(world, &config);
	if (err != 0) {
		return err;
	}

	for (uint16_t row = 0U;
	     row < (sizeof(row_particle_counts) / sizeof(row_particle_counts[0])); ++row) {
		const uint16_t count = row_particle_counts[row];
		const int32_t doubled_span = (int32_t)(count - 1U) * HOURGLASS_GRAIN_SPACING;
		for (uint16_t column = 0U; column < count; ++column) {
			const int32_t doubled_offset =
				((int32_t)column * HOURGLASS_GRAIN_SPACING * 2) - doubled_span;
			const struct picosystem_physics_vector position = {
				.x = FIXED(HOURGLASS_CENTER_X_PIXELS) +
				     ((doubled_offset * PICOSYSTEM_PHYSICS_FIXED_ONE) / 2),
				.y = FIXED(113) - ((int32_t)row * FIXED(HOURGLASS_GRAIN_SPACING)),
			};
			err = picosystem_granular_world_add_particle(world, &position);
			if (err != 0) {
				return err;
			}
		}
	}
	return (world->particle_count == HOURGLASS_GRAIN_COUNT) ? 0 : -ERANGE;
}
