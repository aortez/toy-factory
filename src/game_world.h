/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_GAME_WORLD_H_
#define PICOSYSTEM_GAME_WORLD_H_

#include <stdint.h>

#define PICOSYSTEM_GAME_TICK_RATE_HZ         120U
#define PICOSYSTEM_GAME_FIXED_FRACTION_BITS  16U
#define PICOSYSTEM_GAME_FIXED_ONE            (INT32_C(1) << PICOSYSTEM_GAME_FIXED_FRACTION_BITS)
#define PICOSYSTEM_GAME_SPRITE_WIDTH_PIXELS  16U
#define PICOSYSTEM_GAME_SPRITE_HEIGHT_PIXELS 16U
#define PICOSYSTEM_GAME_SPRITE_MIN_X_PIXELS  1U
#define PICOSYSTEM_GAME_SPRITE_MAX_X_PIXELS  223U
#define PICOSYSTEM_GAME_SPRITE_MIN_Y_PIXELS  25U
#define PICOSYSTEM_GAME_SPRITE_MAX_Y_PIXELS  223U

struct picosystem_game_input {
	int8_t horizontal;
	int8_t vertical;
};

/* Caller-owned authoritative state; production code mutates it only through this API. */
struct picosystem_game_world {
	int32_t sprite_x_fixed;
	int32_t sprite_y_fixed;
	int32_t velocity_x_fixed_per_second;
	int32_t velocity_y_fixed_per_second;
	uint32_t logic_tick_count;
};

/* Restore the canonical deterministic tick-zero state. */
int picosystem_game_world_reset(struct picosystem_game_world *world);

/* Advance exactly one fixed 1/120-second tick. */
int picosystem_game_world_step(struct picosystem_game_world *world,
			       const struct picosystem_game_input *input);

/* Hash authoritative fields in a stable order without hashing structure padding. */
uint32_t picosystem_game_world_hash(const struct picosystem_game_world *world);

#endif /* PICOSYSTEM_GAME_WORLD_H_ */
