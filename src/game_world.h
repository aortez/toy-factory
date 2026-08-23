/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_GAME_WORLD_H_
#define PICOSYSTEM_GAME_WORLD_H_

#include <stddef.h>
#include <stdint.h>

#include "granular_world.h"
#include "physics_world.h"

#define PICOSYSTEM_GAME_TICK_RATE_HZ        60U
#define PICOSYSTEM_GAME_FIXED_FRACTION_BITS PICOSYSTEM_PHYSICS_FIXED_FRACTION_BITS
#define PICOSYSTEM_GAME_FIXED_ONE           PICOSYSTEM_PHYSICS_FIXED_ONE

#define PICOSYSTEM_GAME_PLAYFIELD_LEFT_PIXELS   5U
#define PICOSYSTEM_GAME_PLAYFIELD_RIGHT_PIXELS  234U
#define PICOSYSTEM_GAME_PLAYFIELD_TOP_PIXELS    31U
#define PICOSYSTEM_GAME_PLAYFIELD_BOTTOM_PIXELS 234U
/* Stable Machine Lab fixture sizes used by native tests and isolated profiling. */
#define PICOSYSTEM_GAME_BODY_COUNT              7U
#define PICOSYSTEM_GAME_STATIC_SEGMENT_COUNT    6U
#define PICOSYSTEM_GAME_DISTANCE_JOINT_COUNT    1U
#define PICOSYSTEM_GAME_REVOLUTE_JOINT_COUNT    3U
#define PICOSYSTEM_GAME_PRISMATIC_JOINT_COUNT   1U
#define PICOSYSTEM_GAME_BOX_SENSOR_COUNT        1U
#define PICOSYSTEM_GAME_ROPE_COUNT              1U
#define PICOSYSTEM_GAME_FOCUS_BODY_INDEX        0U

enum picosystem_game_scene_id {
	PICOSYSTEM_GAME_SCENE_MACHINE_LAB,
	PICOSYSTEM_GAME_SCENE_CLOCKWORK,
	PICOSYSTEM_GAME_SCENE_DIAGNOSTIC_CHAIN,
	PICOSYSTEM_GAME_SCENE_HOURGLASS,
	PICOSYSTEM_GAME_SCENE_COUNT,
};

enum picosystem_game_body_render_style {
	PICOSYSTEM_GAME_BODY_RENDER_STYLE_DEFAULT,
	PICOSYSTEM_GAME_BODY_RENDER_STYLE_GEAR,
	PICOSYSTEM_GAME_BODY_RENDER_STYLE_COUNT,
};

struct picosystem_game_input {
	int8_t horizontal;
	int8_t vertical;
};

/* Caller-owned authoritative state; production code mutates it only through this API. */
struct picosystem_game_world {
	/* scene_id tags the one authoritative simulation state active in this union. */
	union {
		struct picosystem_physics_world physics;
		struct picosystem_granular_world granular;
	};
	/* Derived diagnostic proxy used when the active scene has no rigid bodies. */
	struct picosystem_physics_body focus_proxy;
	uint32_t logic_tick_count;
	uint32_t sensor_entry_count;
	uint8_t scene_id;
};

/* Restore the canonical deterministic Machine Lab profiling fixture at tick zero. */
int picosystem_game_world_reset(struct picosystem_game_world *world);

/* Restore one configured playable scene at tick zero. */
int picosystem_game_world_reset_scene(struct picosystem_game_world *world,
				      enum picosystem_game_scene_id scene_id);

/* Advance exactly one fixed 1/60-second tick. */
int picosystem_game_world_step(struct picosystem_game_world *world,
			       const struct picosystem_game_input *input);

/* Advance one profiled grid or reference tick using the normal game input mapping. */
int picosystem_game_world_step_profiled(struct picosystem_game_world *world,
					const struct picosystem_game_input *input,
					enum picosystem_physics_step_mode mode,
					const struct picosystem_physics_clock *clock,
					struct picosystem_physics_step_profile *profile);

/* Advance an Hourglass tick while attributing granular solver cycles. */
int picosystem_game_world_step_granular_profiled(struct picosystem_game_world *world,
						 const struct picosystem_game_input *input,
						 const struct picosystem_physics_clock *clock,
						 struct picosystem_granular_step_profile *profile);

/* Rotate a scene-defined symmetric container and its contents by 180 degrees. */
int picosystem_game_world_flip(struct picosystem_game_world *world);

/* Return the scene's first body, used by diagnostics and camera-independent controls. */
const struct picosystem_physics_body *
picosystem_game_world_focus_body(const struct picosystem_game_world *world);

/* Return presentation metadata without exposing the internal scene descriptor. */
enum picosystem_game_body_render_style
picosystem_game_world_body_render_style(const struct picosystem_game_world *world, size_t index);

/* Hash authoritative fields in a stable order without hashing structure padding. */
uint32_t picosystem_game_world_hash(const struct picosystem_game_world *world);

#endif /* PICOSYSTEM_GAME_WORLD_H_ */
