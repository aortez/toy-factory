/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_GAME_DEMO_H_
#define PICOSYSTEM_GAME_DEMO_H_

#include <stdbool.h>
#include <stdint.h>

#if defined(CONFIG_TOY_FACTORY_CORE1_RUNTIME)
#include "core1_runtime.h"
#endif
#include "display_profile.h"
#include "game_world.h"
#include "graphics.h"

#define PICOSYSTEM_GAME_MAX_CATCH_UP              4U
#define PICOSYSTEM_GAME_FRAMEBUFFER_CHUNK_BYTES   384U
#define PICOSYSTEM_GAME_REALTIME_SNAPSHOT_RATE_HZ 30U

/* Main-thread-owned world plus scheduling and publication metrics. */
struct picosystem_game_demo_state {
	struct picosystem_game_world world;
	uint32_t skipped_tick_count;
	uint32_t over_budget_tick_count;
	uint32_t last_update_time_us;
	uint32_t max_update_time_us;
	uint32_t last_physics_time_us;
	uint32_t max_physics_time_us;
	uint32_t last_snapshot_time_us;
	uint32_t max_snapshot_time_us;
	uint64_t total_physics_time_us;
	uint64_t total_snapshot_time_us;
	uint32_t measured_update_count;
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
	uint32_t mean_update_time_us;
	uint32_t max_update_time_us;
	uint32_t last_physics_time_us;
	uint32_t mean_physics_time_us;
	uint32_t max_physics_time_us;
	uint32_t last_snapshot_time_us;
	uint32_t mean_snapshot_time_us;
	uint32_t max_snapshot_time_us;
	uint32_t max_backlog_ticks;
	uint32_t published_snapshot_count;
	uint32_t superseded_snapshot_count;
	uint32_t presented_snapshot_sequence;
	uint32_t presented_frame_count;
	uint32_t measured_presented_frame_count;
	uint32_t full_redraw_count;
	uint32_t last_render_time_us;
	uint32_t last_raster_time_us;
	uint32_t maximum_raster_time_us;
	uint32_t core1_raster_frame_count;
	uint32_t max_dirty_render_time_us;
	uint32_t last_dirty_present_time_us;
	uint32_t last_dirty_pixel_count;
	uint16_t last_dirty_region_count;
	uint32_t last_snapshot_age_us;
	uint32_t max_dirty_snapshot_age_us;
	uint32_t render_stack_size_bytes;
	uint32_t render_stack_used_bytes;
	uint32_t candidate_pair_count;
	uint32_t possible_pair_count;
	uint32_t active_contact_pair_count;
	uint32_t sensor_overlap_count;
	uint32_t contact_begin_event_count;
	uint32_t contact_stay_event_count;
	uint32_t contact_end_event_count;
	uint32_t sensor_entry_count;
	uint32_t solver_contact_visit_count;
	uint32_t solver_cached_contact_count;
	uint32_t solver_changed_contact_count;
	uint32_t awake_body_count;
	uint32_t sleeping_body_count;
	uint32_t body_sleep_transition_count;
	uint32_t body_wake_transition_count;
	uint32_t sleeping_contact_count;
	uint32_t sleeping_joint_count;
	uint32_t spring_joint_count;
	uint32_t spring_solver_visit_count;
	uint32_t spring_solver_changed_count;
	uint32_t conveyor_contact_count;
	uint32_t conveyor_solver_visit_count;
	uint32_t conveyor_solver_changed_count;
	uint32_t rope_particle_count;
	uint32_t rope_constraint_visit_count;
	uint32_t rope_constraint_changed_count;
	uint32_t rope_body_correction_visit_count;
	uint32_t rope_body_correction_changed_count;
	uint32_t rope_body_velocity_visit_count;
	uint32_t rope_body_velocity_changed_count;
	uint32_t rope_collision_possible_pair_count;
	uint32_t rope_collision_candidate_pair_count;
	uint32_t rope_collision_contact_count;
	uint32_t rope_collision_position_changed_count;
	uint32_t rope_collision_velocity_changed_count;
	uint32_t focus_angle_turns;
	int32_t focus_angular_velocity_milliradians_per_second;
	uint16_t body_count;
	uint16_t static_segment_count;
	uint16_t distance_joint_count;
	uint16_t revolute_joint_count;
	uint16_t prismatic_joint_count;
	uint16_t box_sensor_count;
	uint16_t rope_count;
	uint16_t contact_count;
	uint16_t contact_event_count;
	uint16_t occupied_grid_cell_count;
	uint16_t focus_body_id;
	uint16_t focus_x;
	uint16_t focus_y;
	uint16_t presented_focus_x;
	uint16_t presented_focus_y;
	int16_t focus_velocity_x_pixels_per_second;
	int16_t focus_velocity_y_pixels_per_second;
	uint8_t focus_shape;
	uint8_t solver_iteration_count;
	bool focus_sleeping;
	bool broad_phase_fallback;
	int64_t start_uptime_ms;
	int render_error;
	bool last_raster_on_core1;
	bool core1_renderer_available;
	bool full_frame_renderer_enabled;
	bool render_thread_running;
};

struct picosystem_game_framebuffer_capture {
	uint32_t byte_count;
	uint32_t crc32;
	uint32_t presented_snapshot_sequence;
	uint16_t width;
	uint16_t height;
};

#if defined(CONFIG_TOY_FACTORY_CORE1_RUNTIME)
struct picosystem_game_core1_raster_verification {
	struct picosystem_core1_dense_result timing;
	uint32_t frame_index;
	uint32_t original_crc32;
	uint32_t core0_crc32;
	uint32_t core1_crc32;
	uint32_t restored_crc32;
	bool pixels_match;
	bool framebuffer_restored;
};

struct picosystem_game_core1_scene_verification {
	struct picosystem_core1_scene_result timing;
	uint32_t core0_crc32;
	uint32_t core1_crc32;
	uint32_t restored_crc32;
	bool pixels_match;
	bool framebuffer_restored;
};
#endif

/* Initialize graphics, publish the initial state, and start the renderer. */
int picosystem_game_demo_init(struct picosystem_game_demo_state *state);

/* Start the measured simulation interval after board initialization is complete. */
int picosystem_game_demo_start_simulation(struct picosystem_game_demo_state *state);

/* Begin a new performance-rate window without changing authoritative state. */
int picosystem_game_demo_restart_measurement(struct picosystem_game_demo_state *state);

/* Restore the playable scene while preserving renderer sequence monotonicity. */
int picosystem_game_demo_reset(struct picosystem_game_demo_state *state);

/* Advance one authoritative 60 Hz simulation step and publish its newest state. */
int picosystem_game_demo_update(struct picosystem_game_demo_state *state,
				const struct picosystem_game_input *input);

/* Advance authoritative state while publishing at the bounded real-time snapshot cadence. */
int picosystem_game_demo_update_realtime(struct picosystem_game_demo_state *state,
					 const struct picosystem_game_input *input);

/* Publish the current authoritative state without advancing it. */
int picosystem_game_demo_publish_current(struct picosystem_game_demo_state *state);

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

#if defined(CONFIG_TOY_FACTORY_CORE1_RUNTIME)
/* Compare core-0 and core-1 raster output, then restore the currently presented game frame. */
int picosystem_game_demo_verify_core1_raster(
	uint32_t frame_index, struct picosystem_game_core1_raster_verification *verification);

/* Compare the current live-scene raster on both cores without changing the visible scene. */
int picosystem_game_demo_verify_core1_scene(
	struct picosystem_game_core1_scene_verification *verification);
#endif

/* Profile destructive display workloads, then restore the coherent presented game frame. */
int picosystem_game_demo_profile_display(uint32_t measured_sample_count,
					 struct picosystem_display_profile_result *result);

/* Return a fatal renderer error, or zero while the worker remains healthy. */
int picosystem_game_demo_renderer_error(void);

#endif /* PICOSYSTEM_GAME_DEMO_H_ */
