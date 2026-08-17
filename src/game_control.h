/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_GAME_CONTROL_H_
#define PICOSYSTEM_GAME_CONTROL_H_

#include <stdbool.h>
#include <stdint.h>

#include "game_world.h"

#define PICOSYSTEM_GAME_CONTROL_MAX_STEPS 120U

enum picosystem_game_control_operation {
	PICOSYSTEM_GAME_CONTROL_PAUSE,
	PICOSYSTEM_GAME_CONTROL_RUN,
	PICOSYSTEM_GAME_CONTROL_RESET,
	PICOSYSTEM_GAME_CONTROL_STEP,
	PICOSYSTEM_GAME_CONTROL_SET_INPUT,
	PICOSYSTEM_GAME_CONTROL_GET_STATE,
};

struct picosystem_game_control_request {
	int64_t deadline_uptime_ms;
	uint32_t id;
	uint32_t step_count;
	struct picosystem_game_input input;
	enum picosystem_game_control_operation operation;
	bool remote_input_enabled;
};

struct picosystem_game_control_state {
	int32_t focus_x_fixed;
	int32_t focus_y_fixed;
	int32_t focus_velocity_x_fixed_per_tick;
	int32_t focus_velocity_y_fixed_per_tick;
	int32_t focus_angular_velocity_fixed_per_tick;
	uint32_t logic_tick_count;
	uint32_t state_hash;
	uint32_t published_snapshot_sequence;
	uint32_t presented_snapshot_sequence;
	uint32_t focus_angle_turns;
	struct picosystem_game_input input;
	uint16_t focus_body_id;
	uint8_t focus_shape;
	bool paused;
	bool remote_input_enabled;
};

/* Submit one request from a client thread and wait for main-thread acknowledgement. */
int picosystem_game_control_submit(const struct picosystem_game_control_request *request,
				   struct picosystem_game_control_state *state);

/* Take one non-expired request without waiting. Called only by the main thread. */
int picosystem_game_control_take(struct picosystem_game_control_request *request);

/* Complete a request with the state observed after applying it. */
int picosystem_game_control_complete(uint32_t request_id, int result,
				     const struct picosystem_game_control_state *state);

#endif /* PICOSYSTEM_GAME_CONTROL_H_ */
