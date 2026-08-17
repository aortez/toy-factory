/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "game_world.h"

#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define SPRITE_SPEED_PIXELS_PER_SECOND INT32_C(125)
#define SPRITE_START_X_PIXELS                                                                      \
	((PICOSYSTEM_GAME_SPRITE_MIN_X_PIXELS + PICOSYSTEM_GAME_SPRITE_MAX_X_PIXELS) / 2U)
#define SPRITE_START_Y_PIXELS                                                                      \
	((PICOSYSTEM_GAME_SPRITE_MIN_Y_PIXELS + PICOSYSTEM_GAME_SPRITE_MAX_Y_PIXELS) / 2U)
#define SPRITE_SPEED_FIXED (SPRITE_SPEED_PIXELS_PER_SECOND * PICOSYSTEM_GAME_FIXED_ONE)
#define SPRITE_STEP_FIXED  (SPRITE_SPEED_FIXED / (int32_t)PICOSYSTEM_GAME_TICK_RATE_HZ)
#define SPRITE_MIN_X_FIXED                                                                         \
	((int32_t)PICOSYSTEM_GAME_SPRITE_MIN_X_PIXELS * PICOSYSTEM_GAME_FIXED_ONE)
#define SPRITE_MAX_X_FIXED                                                                         \
	((int32_t)PICOSYSTEM_GAME_SPRITE_MAX_X_PIXELS * PICOSYSTEM_GAME_FIXED_ONE)
#define SPRITE_MIN_Y_FIXED                                                                         \
	((int32_t)PICOSYSTEM_GAME_SPRITE_MIN_Y_PIXELS * PICOSYSTEM_GAME_FIXED_ONE)
#define SPRITE_MAX_Y_FIXED                                                                         \
	((int32_t)PICOSYSTEM_GAME_SPRITE_MAX_Y_PIXELS * PICOSYSTEM_GAME_FIXED_ONE)

/* Change this whenever authoritative hash field order or meaning changes. */
#define GAME_WORLD_HASH_VERSION UINT32_C(1)
#define FNV1A_OFFSET_BASIS      UINT32_C(2166136261)
#define FNV1A_PRIME             UINT32_C(16777619)

_Static_assert(SPRITE_MIN_X_FIXED >= 0, "minimum sprite X must be nonnegative");
_Static_assert(SPRITE_MAX_X_FIXED <= (INT32_MAX - SPRITE_STEP_FIXED),
	       "maximum sprite X plus one step must fit in Q16.16");
_Static_assert(SPRITE_MIN_Y_FIXED >= 0, "minimum sprite Y must be nonnegative");
_Static_assert(SPRITE_MAX_Y_FIXED <= (INT32_MAX - SPRITE_STEP_FIXED),
	       "maximum sprite Y plus one step must fit in Q16.16");
_Static_assert(SPRITE_SPEED_FIXED <= INT32_MAX, "sprite speed must fit in Q16.16");

static void increment_saturated(uint32_t *value)
{
	if (*value < UINT32_MAX) {
		++*value;
	}
}

static bool velocity_is_valid(int32_t velocity)
{
	return (velocity == SPRITE_SPEED_FIXED) || (velocity == -SPRITE_SPEED_FIXED);
}

static bool world_is_valid(const struct picosystem_game_world *world)
{
	return (world->sprite_x_fixed >= SPRITE_MIN_X_FIXED) &&
	       (world->sprite_x_fixed <= SPRITE_MAX_X_FIXED) &&
	       (world->sprite_y_fixed >= SPRITE_MIN_Y_FIXED) &&
	       (world->sprite_y_fixed <= SPRITE_MAX_Y_FIXED) &&
	       velocity_is_valid(world->velocity_x_fixed_per_second) &&
	       velocity_is_valid(world->velocity_y_fixed_per_second);
}

static int32_t move_coordinate(int32_t current, int32_t *velocity, int32_t minimum, int32_t maximum)
{
	const int32_t speed = (*velocity < 0) ? -*velocity : *velocity;
	int32_t requested = current + (*velocity / (int32_t)PICOSYSTEM_GAME_TICK_RATE_HZ);

	if (requested < minimum) {
		requested = minimum;
		*velocity = speed;
	} else if (requested > maximum) {
		requested = maximum;
		*velocity = -speed;
	}

	return requested;
}

static uint32_t fnv1a_u32(uint32_t hash, uint32_t value)
{
	for (uint32_t shift = 0U; shift < 32U; shift += 8U) {
		hash ^= (value >> shift) & UINT32_C(0xff);
		hash *= FNV1A_PRIME;
	}

	return hash;
}

int picosystem_game_world_reset(struct picosystem_game_world *world)
{
	if (world == NULL) {
		return -EINVAL;
	}

	*world = (struct picosystem_game_world){
		.sprite_x_fixed = (int32_t)SPRITE_START_X_PIXELS * PICOSYSTEM_GAME_FIXED_ONE,
		.sprite_y_fixed = (int32_t)SPRITE_START_Y_PIXELS * PICOSYSTEM_GAME_FIXED_ONE,
		.velocity_x_fixed_per_second = SPRITE_SPEED_FIXED,
		.velocity_y_fixed_per_second = SPRITE_SPEED_FIXED,
	};
	return 0;
}

int picosystem_game_world_step(struct picosystem_game_world *world,
			       const struct picosystem_game_input *input)
{
	if ((world == NULL) || (input == NULL)) {
		return -EINVAL;
	}
	if ((input->horizontal < -1) || (input->horizontal > 1) || (input->vertical < -1) ||
	    (input->vertical > 1) || !world_is_valid(world)) {
		return -ERANGE;
	}

	if (input->horizontal != 0) {
		world->velocity_x_fixed_per_second = input->horizontal * SPRITE_SPEED_FIXED;
	}
	if (input->vertical != 0) {
		world->velocity_y_fixed_per_second = input->vertical * SPRITE_SPEED_FIXED;
	}

	world->sprite_x_fixed =
		move_coordinate(world->sprite_x_fixed, &world->velocity_x_fixed_per_second,
				SPRITE_MIN_X_FIXED, SPRITE_MAX_X_FIXED);
	world->sprite_y_fixed =
		move_coordinate(world->sprite_y_fixed, &world->velocity_y_fixed_per_second,
				SPRITE_MIN_Y_FIXED, SPRITE_MAX_Y_FIXED);
	increment_saturated(&world->logic_tick_count);
	return 0;
}

uint32_t picosystem_game_world_hash(const struct picosystem_game_world *world)
{
	if (world == NULL) {
		return 0U;
	}

	uint32_t hash = fnv1a_u32(FNV1A_OFFSET_BASIS, GAME_WORLD_HASH_VERSION);
	hash = fnv1a_u32(hash, world->logic_tick_count);
	hash = fnv1a_u32(hash, (uint32_t)world->sprite_x_fixed);
	hash = fnv1a_u32(hash, (uint32_t)world->sprite_y_fixed);
	hash = fnv1a_u32(hash, (uint32_t)world->velocity_x_fixed_per_second);
	return fnv1a_u32(hash, (uint32_t)world->velocity_y_fixed_per_second);
}
