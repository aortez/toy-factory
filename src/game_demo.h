/*
 * Copyright (c) 2026 PicoSystem Playground contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_GAME_DEMO_H_
#define PICOSYSTEM_GAME_DEMO_H_

#include <stdbool.h>
#include <stdint.h>

#include "graphics.h"

#define PICOSYSTEM_GAME_TICK_INTERVAL_MS 16U
#define PICOSYSTEM_GAME_MAX_CATCH_UP     4U

struct picosystem_game_input {
	int8_t horizontal;
	int8_t vertical;
};

struct picosystem_game_demo_state {
	struct picosystem_graphics_stats graphics;
	uint32_t logic_tick_count;
	uint32_t presented_frame_count;
	uint32_t skipped_tick_count;
	uint32_t last_render_time_us;
	uint32_t max_dirty_render_time_us;
	int64_t start_uptime_ms;
	uint16_t sprite_x;
	uint16_t sprite_y;
	uint16_t presented_sprite_x;
	uint16_t presented_sprite_y;
	int8_t velocity_x;
	int8_t velocity_y;
	bool present_pending;
	bool ready;
};

int picosystem_game_demo_init(struct picosystem_game_demo_state *state);
int picosystem_game_demo_update(struct picosystem_game_demo_state *state,
				const struct picosystem_game_input *input);
int picosystem_game_demo_present(struct picosystem_game_demo_state *state);
int picosystem_game_demo_redraw(struct picosystem_game_demo_state *state);
void picosystem_game_demo_note_skipped_ticks(struct picosystem_game_demo_state *state,
					     uint32_t skipped_ticks);

#endif /* PICOSYSTEM_GAME_DEMO_H_ */
