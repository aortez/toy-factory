/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_GAME_DEMO_H_
#define PICOSYSTEM_GAME_DEMO_H_

#include <stdbool.h>
#include <stdint.h>

#include "game_world.h"
#include "graphics.h"

#define PICOSYSTEM_GAME_MAX_CATCH_UP            4U
#define PICOSYSTEM_GAME_FRAMEBUFFER_CHUNK_BYTES 384U

/* Main-thread-owned world plus scheduling and publication metrics. */
struct picosystem_game_demo_state {
	struct picosystem_game_world world;
	uint32_t skipped_tick_count;
	uint32_t over_budget_tick_count;
	uint32_t last_update_time_us;
	uint32_t max_update_time_us;
	uint32_t max_backlog_ticks;
	uint32_t redraw_request_sequence;
	uint32_t snapshot_sequence;
	uint32_t measurement_start_logic_tick_count;
	uint32_t measurement_start_presented_frame_count;
	int64_t start_uptime_ms;
	bool ready;
};

/* Coherent diagnostic copy assembled by the main thread. */
struct picosystem_game_demo_stats {
	struct picosystem_graphics_stats graphics;
	uint32_t logic_tick_count;
	uint32_t measured_logic_tick_count;
	uint32_t skipped_tick_count;
	uint32_t over_budget_tick_count;
	uint32_t last_update_time_us;
	uint32_t max_update_time_us;
	uint32_t max_backlog_ticks;
	uint32_t published_snapshot_count;
	uint32_t superseded_snapshot_count;
	uint32_t presented_snapshot_sequence;
	uint32_t presented_frame_count;
	uint32_t measured_presented_frame_count;
	uint32_t full_redraw_count;
	uint32_t last_render_time_us;
	uint32_t max_dirty_render_time_us;
	uint32_t last_snapshot_age_us;
	uint32_t max_dirty_snapshot_age_us;
	uint32_t render_stack_size_bytes;
	uint32_t render_stack_used_bytes;
	uint32_t candidate_pair_count;
	uint16_t body_count;
	uint16_t static_segment_count;
	uint16_t contact_count;
	uint16_t focus_body_id;
	uint16_t focus_x;
	uint16_t focus_y;
	uint16_t presented_focus_x;
	uint16_t presented_focus_y;
	int16_t focus_velocity_x_pixels_per_second;
	int16_t focus_velocity_y_pixels_per_second;
	int64_t start_uptime_ms;
	int render_error;
	bool render_thread_running;
};

struct picosystem_game_framebuffer_capture {
	uint32_t byte_count;
	uint32_t crc32;
	uint32_t presented_snapshot_sequence;
	uint16_t width;
	uint16_t height;
};

/* Initialize graphics, publish the initial state, and start the renderer. */
int picosystem_game_demo_init(struct picosystem_game_demo_state *state);

/* Start the measured simulation interval after board initialization is complete. */
int picosystem_game_demo_start_simulation(struct picosystem_game_demo_state *state);

/* Begin a new performance-rate window without changing authoritative state. */
int picosystem_game_demo_restart_measurement(struct picosystem_game_demo_state *state);

/* Restore canonical tick-zero state while preserving renderer sequence monotonicity. */
int picosystem_game_demo_reset(struct picosystem_game_demo_state *state);

/* Advance one authoritative 120 Hz simulation step and publish its newest state. */
int picosystem_game_demo_update(struct picosystem_game_demo_state *state,
				const struct picosystem_game_input *input);

/* Request a renderer-owned full redraw without blocking the simulation. */
int picosystem_game_demo_request_redraw(struct picosystem_game_demo_state *state);

/* Record scheduler pressure without changing the simulation state. */
void picosystem_game_demo_note_backlog(struct picosystem_game_demo_state *state,
				       uint32_t backlog_ticks);
void picosystem_game_demo_note_skipped_ticks(struct picosystem_game_demo_state *state,
					     uint32_t skipped_ticks);

/* Merge main-owned simulation and renderer-owned metrics into one snapshot. */
int picosystem_game_demo_get_stats(const struct picosystem_game_demo_state *state,
				   struct picosystem_game_demo_stats *stats);

/* Hash only deterministic authoritative state, excluding clocks and performance metrics. */
uint32_t picosystem_game_demo_state_hash(const struct picosystem_game_demo_state *state);

/* Visit one coherent, fully presented framebuffer without allocating a second frame. */
int picosystem_game_demo_capture_framebuffer(picosystem_graphics_framebuffer_visitor visitor,
					     void *context,
					     struct picosystem_game_framebuffer_capture *capture);

/* Return a fatal renderer error, or zero while the worker remains healthy. */
int picosystem_game_demo_renderer_error(void);

#endif /* PICOSYSTEM_GAME_DEMO_H_ */
