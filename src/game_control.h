/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_GAME_CONTROL_H_
#define PICOSYSTEM_GAME_CONTROL_H_

#include <stdbool.h>
#include <stdint.h>

#include "game_demo.h"

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
	int32_t sprite_x_fixed;
	int32_t sprite_y_fixed;
	int32_t velocity_x_fixed_per_second;
	int32_t velocity_y_fixed_per_second;
	uint32_t logic_tick_count;
	uint32_t state_hash;
	uint32_t published_snapshot_sequence;
	uint32_t presented_snapshot_sequence;
	struct picosystem_game_input input;
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
