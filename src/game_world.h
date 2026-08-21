/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_GAME_WORLD_H_
#define PICOSYSTEM_GAME_WORLD_H_

#include <stdint.h>

#include "physics_world.h"

#define PICOSYSTEM_GAME_TICK_RATE_HZ        120U
#define PICOSYSTEM_GAME_FIXED_FRACTION_BITS PICOSYSTEM_PHYSICS_FIXED_FRACTION_BITS
#define PICOSYSTEM_GAME_FIXED_ONE           PICOSYSTEM_PHYSICS_FIXED_ONE

#define PICOSYSTEM_GAME_PLAYFIELD_LEFT_PIXELS   5U
#define PICOSYSTEM_GAME_PLAYFIELD_RIGHT_PIXELS  234U
#define PICOSYSTEM_GAME_PLAYFIELD_TOP_PIXELS    31U
#define PICOSYSTEM_GAME_PLAYFIELD_BOTTOM_PIXELS 234U
#define PICOSYSTEM_GAME_BODY_COUNT              7U
#define PICOSYSTEM_GAME_STATIC_SEGMENT_COUNT    6U
#define PICOSYSTEM_GAME_DISTANCE_JOINT_COUNT    1U
#define PICOSYSTEM_GAME_REVOLUTE_JOINT_COUNT    3U
#define PICOSYSTEM_GAME_PRISMATIC_JOINT_COUNT   1U
#define PICOSYSTEM_GAME_BOX_SENSOR_COUNT        1U
#define PICOSYSTEM_GAME_FOCUS_BODY_INDEX        0U

struct picosystem_game_input {
	int8_t horizontal;
	int8_t vertical;
};

/* Caller-owned authoritative state; production code mutates it only through this API. */
struct picosystem_game_world {
	struct picosystem_physics_world physics;
	uint32_t logic_tick_count;
	uint32_t sensor_entry_count;
};

/* Restore the canonical deterministic powered-mechanism lab at tick zero. */
int picosystem_game_world_reset(struct picosystem_game_world *world);

/* Advance exactly one fixed 1/120-second tick. */
int picosystem_game_world_step(struct picosystem_game_world *world,
			       const struct picosystem_game_input *input);

/* Advance one profiled grid or reference tick using the normal game input mapping. */
int picosystem_game_world_step_profiled(struct picosystem_game_world *world,
					const struct picosystem_game_input *input,
					enum picosystem_physics_step_mode mode,
					const struct picosystem_physics_clock *clock,
					struct picosystem_physics_step_profile *profile);

/* Return the canonical focus body used by diagnostics and camera-independent controls. */
const struct picosystem_physics_body *
picosystem_game_world_focus_body(const struct picosystem_game_world *world);

/* Hash authoritative fields in a stable order without hashing structure padding. */
uint32_t picosystem_game_world_hash(const struct picosystem_game_world *world);

#endif /* PICOSYSTEM_GAME_WORLD_H_ */
