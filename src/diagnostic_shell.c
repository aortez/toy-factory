/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "diagnostic_shell.h"

#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/retention/bootmode.h>
#include <zephyr/shell/shell.h>
#include <zephyr/shell/shell_string_conv.h>
#include <zephyr/sys/atomic.h>
#include <zephyr/sys/base64.h>
#include <zephyr/sys/reboot.h>
#include <zephyr/sys/util.h>

#include "core1_runtime.h"
#include "display_profile.h"
#include "display_sync.h"
#include "game_control.h"
#include "physics_chain_fixture.h"
#include "physics_profile.h"
#include "piezo.h"

#define BOOTLOADER_REBOOT_DELAY_MS 100

static struct picosystem_physics_profile_result profile_result;
static struct picosystem_display_profile_result display_profile_result;

struct named_button {
	const char *name;
	enum picosystem_button_index index;
};

struct named_led_mode {
	const char *name;
	enum picosystem_led_mode mode;
};

struct named_game_input {
	const char *name;
	struct picosystem_game_input input;
	bool remote_input_enabled;
};

static const struct named_button button_names[] = {
	{.name = "UP", .index = PICOSYSTEM_BUTTON_UP},
	{.name = "DOWN", .index = PICOSYSTEM_BUTTON_DOWN},
	{.name = "LEFT", .index = PICOSYSTEM_BUTTON_LEFT},
	{.name = "RIGHT", .index = PICOSYSTEM_BUTTON_RIGHT},
	{.name = "A", .index = PICOSYSTEM_BUTTON_A},
	{.name = "B", .index = PICOSYSTEM_BUTTON_B},
	{.name = "X", .index = PICOSYSTEM_BUTTON_X},
	{.name = "Y", .index = PICOSYSTEM_BUTTON_Y},
};

static const struct named_led_mode led_modes[] = {
	{.name = "auto", .mode = PICOSYSTEM_LED_MODE_AUTO},
	{.name = "off", .mode = PICOSYSTEM_LED_MODE_OFF},
	{.name = "red", .mode = PICOSYSTEM_LED_MODE_RED},
	{.name = "green", .mode = PICOSYSTEM_LED_MODE_GREEN},
	{.name = "blue", .mode = PICOSYSTEM_LED_MODE_BLUE},
	{.name = "white", .mode = PICOSYSTEM_LED_MODE_WHITE},
};

static const struct named_game_input game_inputs[] = {
	{.name = "physical", .input = {0}, .remote_input_enabled = false},
	{.name = "none", .input = {0}, .remote_input_enabled = true},
	{.name = "up", .input = {.vertical = -1}, .remote_input_enabled = true},
	{.name = "down", .input = {.vertical = 1}, .remote_input_enabled = true},
	{.name = "left", .input = {.horizontal = -1}, .remote_input_enabled = true},
	{.name = "right", .input = {.horizontal = 1}, .remote_input_enabled = true},
	{.name = "up-left",
	 .input = {.horizontal = -1, .vertical = -1},
	 .remote_input_enabled = true},
	{.name = "up-right",
	 .input = {.horizontal = 1, .vertical = -1},
	 .remote_input_enabled = true},
	{.name = "down-left",
	 .input = {.horizontal = -1, .vertical = 1},
	 .remote_input_enabled = true},
	{.name = "down-right",
	 .input = {.horizontal = 1, .vertical = 1},
	 .remote_input_enabled = true},
};

BUILD_ASSERT(ARRAY_SIZE(button_names) == PICOSYSTEM_BUTTON_COUNT);

K_MUTEX_DEFINE(snapshot_mutex);
K_MSGQ_DEFINE(tone_requests, sizeof(struct picosystem_tone_request), 1U, 4U);

static struct picosystem_diagnostic_snapshot latest_snapshot;
static bool snapshot_available;
static atomic_t selected_led_mode = ATOMIC_INIT(PICOSYSTEM_LED_MODE_AUTO);
static atomic_t redraw_requested;

static const char *led_mode_name(enum picosystem_led_mode mode)
{
	for (size_t i = 0U; i < ARRAY_SIZE(led_modes); ++i) {
		if (led_modes[i].mode == mode) {
			return led_modes[i].name;
		}
	}

	return "unknown";
}

static int read_snapshot(struct picosystem_diagnostic_snapshot *snapshot)
{
	if (snapshot == NULL) {
		return -EINVAL;
	}

	int err = k_mutex_lock(&snapshot_mutex, K_FOREVER);
	if (err != 0) {
		return err;
	}

	if (!snapshot_available) {
		err = -EAGAIN;
	} else {
		*snapshot = latest_snapshot;
	}

	k_mutex_unlock(&snapshot_mutex);
	return err;
}

static void print_buttons(const struct shell *shell, uint32_t buttons)
{
	shell_fprintf(shell, SHELL_NORMAL, "buttons: 0x%02x", buttons);

	if (buttons == 0U) {
		shell_print(shell, " (none)");
		return;
	}

	for (size_t i = 0U; i < ARRAY_SIZE(button_names); ++i) {
		if ((buttons & BIT(button_names[i].index)) != 0U) {
			shell_fprintf(shell, SHELL_NORMAL, " %s", button_names[i].name);
		}
	}

	shell_print(shell, "");
}

#if defined(CONFIG_TOY_FACTORY_CORE1_RUNTIME)
static int print_core1_status(const struct shell *shell)
{
	struct picosystem_core1_status status;
	const int err = picosystem_core1_get_status(&status);
	if (err != 0) {
		shell_error(shell, "Could not read core 1 status (%d)", err);
		return err;
	}

	shell_print(shell,
		    "core1: state=%s ready=%s core=%u requests=%u/%u heartbeat=%u "
		    "stack=%u/%u bytes scene=%u us strips=%u/%u progress=%s[%u]/%s error=%d",
		    picosystem_core1_state_name(status.state), status.ready ? "yes" : "no",
		    status.core_id, status.completed_sequence, status.requested_sequence,
		    status.heartbeat_count, status.stack_used_bytes, status.stack_size_bytes,
		    status.last_scene_raster_time_us, status.ready_strip_count,
		    status.scene_strip_count,
		    picosystem_scene_render_stage_name(status.scene_stage), status.scene_item_index,
		    picosystem_scene_render_primitive_name(status.scene_primitive), status.error);
	return 0;
}

static int cmd_core1_status(const struct shell *shell, size_t argc, char **argv)
{
	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	return print_core1_status(shell);
}

static int cmd_core1_ping(const struct shell *shell, size_t argc, char **argv)
{
	uint32_t challenge = 0x01234567U;
	if (argc == 2U) {
		int parse_err = 0;
		challenge = shell_strtoul(argv[1], 0, &parse_err);
		if (parse_err != 0) {
			shell_error(shell, "Invalid 32-bit challenge: %s", argv[1]);
			return -EINVAL;
		}
	}

	uint32_t response;
	const int err = picosystem_core1_ping(challenge, &response);
	if (err != 0) {
		shell_error(shell, "Core 1 ping failed (%d)", err);
		return err;
	}

	shell_print(shell, "challenge=%08x response=%08x", challenge, response);
	return 0;
}

static int cmd_core1_raster(const struct shell *shell, size_t argc, char **argv)
{
	uint32_t frame_index = 0U;
	if (argc == 2U) {
		int parse_err = 0;
		frame_index = shell_strtoul(argv[1], 0, &parse_err);
		if (parse_err != 0) {
			shell_error(shell, "Invalid 32-bit frame index: %s", argv[1]);
			return -EINVAL;
		}
	}

	struct picosystem_game_control_state state;
	const struct picosystem_game_control_request request = {
		.operation = PICOSYSTEM_GAME_CONTROL_GET_STATE,
	};
	int err = picosystem_game_control_submit(&request, &state);
	if (err != 0) {
		shell_error(shell, "Could not query simulation state (%d)", err);
		return err;
	}
	if (!state.paused) {
		shell_error(shell, "Pause the simulation before verifying core 1 raster output");
		return -EBUSY;
	}

	struct picosystem_game_core1_raster_verification verification;
	err = picosystem_game_demo_verify_core1_raster(frame_index, &verification);
	if ((err == 0) || (err == -EILSEQ)) {
		shell_print(
			shell,
			"CORE1_RASTER_VERIFY frame=%u core0_crc32=%08x core1_crc32=%08x "
			"pixels_match=%s original_crc32=%08x restored_crc32=%08x "
			"framebuffer_restored=%s total_us=%u background_us=%u links_us=%u "
			"circles_us=%u boxes_us=%u",
			verification.frame_index, verification.core0_crc32,
			verification.core1_crc32, verification.pixels_match ? "yes" : "no",
			verification.original_crc32, verification.restored_crc32,
			verification.framebuffer_restored ? "yes" : "no",
			verification.timing.total_time_us,
			verification.timing.stage_time_us[PICOSYSTEM_DENSE_SCENE_STAGE_BACKGROUND],
			verification.timing.stage_time_us[PICOSYSTEM_DENSE_SCENE_STAGE_LINKS],
			verification.timing.stage_time_us[PICOSYSTEM_DENSE_SCENE_STAGE_CIRCLES],
			verification.timing.stage_time_us[PICOSYSTEM_DENSE_SCENE_STAGE_BOXES]);
	}
	if (err != 0) {
		shell_error(shell, "Core 1 raster verification failed (%d)", err);
	}
	return err;
}

static int cmd_core1_scene(const struct shell *shell, size_t argc, char **argv)
{
	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	struct picosystem_game_control_state state;
	const struct picosystem_game_control_request request = {
		.operation = PICOSYSTEM_GAME_CONTROL_GET_STATE,
	};
	int err = picosystem_game_control_submit(&request, &state);
	if (err != 0) {
		shell_error(shell, "Could not query simulation state (%d)", err);
		return err;
	}
	if (!state.paused) {
		shell_error(shell, "Pause the simulation before verifying core 1 scene output");
		return -EBUSY;
	}

	struct picosystem_game_core1_scene_verification verification;
	err = picosystem_game_demo_verify_core1_scene(&verification);
	if ((err == 0) || (err == -EILSEQ)) {
		shell_print(shell,
			    "CORE1_SCENE_VERIFY core0_crc32=%08x core1_crc32=%08x "
			    "pixels_match=%s restored_crc32=%08x framebuffer_restored=%s "
			    "raster_us=%u strips=%u",
			    verification.core0_crc32, verification.core1_crc32,
			    verification.pixels_match ? "yes" : "no", verification.restored_crc32,
			    verification.framebuffer_restored ? "yes" : "no",
			    verification.timing.raster_time_us, verification.timing.strip_count);
	}
	if (err != 0) {
		shell_error(shell, "Core 1 scene verification failed (%d)", err);
	}
	return err;
}
#endif

static int get_snapshot_or_report(const struct shell *shell,
				  struct picosystem_diagnostic_snapshot *snapshot)
{
	const int err = read_snapshot(snapshot);
	if (err == -EAGAIN) {
		shell_error(shell, "Application hardware is not ready yet");
		return err;
	}

	if (err != 0) {
		shell_error(shell, "Failed to read diagnostic snapshot (%d)", err);
	}

	return err;
}

static uint32_t measured_rate_tenths(uint32_t count, int64_t start_uptime_ms, int64_t now_ms)
{
	const int64_t elapsed_ms = MAX(now_ms - start_uptime_ms, INT64_C(1));
	const uint64_t scaled_count = (uint64_t)count * 10U * MSEC_PER_SEC;
	const uint64_t scaled_rate =
		(scaled_count + ((uint64_t)elapsed_ms / 2U)) / (uint64_t)elapsed_ms;

	return (uint32_t)MIN(scaled_rate, UINT32_MAX);
}

static const char *physics_shape_name(uint8_t shape)
{
	return (shape == PICOSYSTEM_PHYSICS_SHAPE_BOX) ? "box" : "circle";
}

static int cmd_status(const struct shell *shell, size_t argc, char **argv)
{
	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	struct picosystem_diagnostic_snapshot snapshot;
	const int err = get_snapshot_or_report(shell, &snapshot);
	if (err != 0) {
		return err;
	}

	const int64_t now_ms = k_uptime_get();
	const int64_t battery_age_ms = MAX(now_ms - snapshot.battery_sample_uptime_ms, INT64_C(0));
	const int64_t metrics_time_ms = snapshot.snapshot_uptime_ms;
	const char *const usb_name = snapshot.power.usb_power_present ? "present" : "absent";
	const char *const charge_name = snapshot.power.charging ? "active" : "inactive";
	const uint32_t simulation_rate_tenths =
		measured_rate_tenths(snapshot.game.measured_logic_tick_count,
				     snapshot.game.start_uptime_ms, metrics_time_ms);
	const uint32_t frame_rate_tenths =
		measured_rate_tenths(snapshot.game.measured_presented_frame_count,
				     snapshot.game.start_uptime_ms, metrics_time_ms);

	shell_print(shell, "uptime: %lld ms", now_ms);
	print_buttons(shell, snapshot.buttons);
	shell_print(shell, "power: %s (usb=%s, charge=%s)",
		    picosystem_power_state_name(snapshot.power.state), usb_name, charge_name);
	shell_print(shell, "battery: %u mV (raw=%u, plausible=%s, age=%lld ms)",
		    snapshot.battery.millivolts, snapshot.battery.raw_average,
		    snapshot.battery.plausible ? "yes" : "no", battery_age_ms);
	shell_print(shell, "graphics: framebuffer=%u bytes, present=%u us/%ux%u (#%u)",
		    snapshot.game.graphics.framebuffer_bytes,
		    snapshot.game.graphics.last_present_time_us,
		    snapshot.game.graphics.last_present_width,
		    snapshot.game.graphics.last_present_height,
		    snapshot.game.graphics.present_count);
	shell_print(shell,
		    "simulation: ticks=%u, window=%u (%u.%u Hz), update=%u/%u/%u us "
		    "last/mean/max, physics=%u/%u/%u, snapshot=%u/%u/%u, "
		    "backlog=%u, "
		    "skipped=%u, over-budget=%u",
		    snapshot.game.logic_tick_count, snapshot.game.measured_logic_tick_count,
		    simulation_rate_tenths / 10U, simulation_rate_tenths % 10U,
		    snapshot.game.last_update_time_us, snapshot.game.mean_update_time_us,
		    snapshot.game.max_update_time_us, snapshot.game.last_physics_time_us,
		    snapshot.game.mean_physics_time_us, snapshot.game.max_physics_time_us,
		    snapshot.game.last_snapshot_time_us, snapshot.game.mean_snapshot_time_us,
		    snapshot.game.max_snapshot_time_us, snapshot.game.max_backlog_ticks,
		    snapshot.game.skipped_tick_count, snapshot.game.over_budget_tick_count);
	shell_print(shell,
		    "render: running=%s, frames=%u, window=%u (%u.%u fps), snapshots=%u "
		    "published/%u superseded, "
		    "age=%u us (dirty max=%u)",
		    snapshot.game.render_thread_running ? "yes" : "no",
		    snapshot.game.presented_frame_count,
		    snapshot.game.measured_presented_frame_count, frame_rate_tenths / 10U,
		    frame_rate_tenths % 10U, snapshot.game.published_snapshot_count,
		    snapshot.game.superseded_snapshot_count, snapshot.game.last_snapshot_age_us,
		    snapshot.game.max_dirty_snapshot_age_us);
	shell_print(shell,
		    "physics: bodies=%u, segments=%u, joints=%u distance/%u revolute/%u "
		    "prismatic, sensors=%u, contacts=%u, "
		    "candidates=%u/%u, "
		    "grid=%u/%u cells, solver=%u/%u, contact solver=%u visits, %u cached, "
		    "%u changed, "
		    "fallback=%s",
		    snapshot.game.body_count, snapshot.game.static_segment_count,
		    snapshot.game.distance_joint_count, snapshot.game.revolute_joint_count,
		    snapshot.game.prismatic_joint_count, snapshot.game.box_sensor_count,
		    snapshot.game.contact_count, snapshot.game.candidate_pair_count,
		    snapshot.game.possible_pair_count, snapshot.game.occupied_grid_cell_count,
		    PICOSYSTEM_PHYSICS_GRID_CELL_COUNT, snapshot.game.solver_iteration_count,
		    PICOSYSTEM_PHYSICS_SOLVER_ITERATIONS, snapshot.game.solver_contact_visit_count,
		    snapshot.game.solver_cached_contact_count,
		    snapshot.game.solver_changed_contact_count,
		    snapshot.game.broad_phase_fallback ? "yes" : "no");
	shell_print(shell,
		    "sleep: awake=%u, sleeping=%u, transitions=%u sleep/%u wake, "
		    "constraints skipped=%u contacts/%u joints",
		    snapshot.game.awake_body_count, snapshot.game.sleeping_body_count,
		    snapshot.game.body_sleep_transition_count,
		    snapshot.game.body_wake_transition_count, snapshot.game.sleeping_contact_count,
		    snapshot.game.sleeping_joint_count);
	shell_print(shell,
		    "powered: springs=%u, spring solver=%u visits/%u changed, "
		    "conveyors=%u contacts, %u visits/%u changed",
		    snapshot.game.spring_joint_count, snapshot.game.spring_solver_visit_count,
		    snapshot.game.spring_solver_changed_count, snapshot.game.conveyor_contact_count,
		    snapshot.game.conveyor_solver_visit_count,
		    snapshot.game.conveyor_solver_changed_count);
	shell_print(shell,
		    "events: active=%u, sensor overlaps=%u, emitted=%u (%u begin/%u stay/%u end), "
		    "sensor entries=%u",
		    snapshot.game.active_contact_pair_count, snapshot.game.sensor_overlap_count,
		    snapshot.game.contact_event_count, snapshot.game.contact_begin_event_count,
		    snapshot.game.contact_stay_event_count, snapshot.game.contact_end_event_count,
		    snapshot.game.sensor_entry_count);
	shell_print(
		shell,
		"focus #%u %s: simulation=(%u,%u), displayed=(%u,%u), "
		"velocity=(%d,%d) px/s, angle=%08x, angular=%d mrad/s, sleep=%s",
		snapshot.game.focus_body_id, physics_shape_name(snapshot.game.focus_shape),
		snapshot.game.focus_x, snapshot.game.focus_y, snapshot.game.presented_focus_x,
		snapshot.game.presented_focus_y, snapshot.game.focus_velocity_x_pixels_per_second,
		snapshot.game.focus_velocity_y_pixels_per_second, snapshot.game.focus_angle_turns,
		snapshot.game.focus_angular_velocity_milliradians_per_second,
		snapshot.game.focus_sleeping ? "yes" : "no");
	shell_print(shell, "main stack high-water: %u/%u bytes",
		    snapshot.runtime.main_stack_used_bytes, snapshot.runtime.main_stack_size_bytes);
	shell_print(shell, "render stack high-water: %u/%u bytes",
		    snapshot.game.render_stack_used_bytes, snapshot.game.render_stack_size_bytes);
	shell_print(shell, "led: %s", led_mode_name(picosystem_diagnostic_shell_led_mode()));
#if defined(CONFIG_TOY_FACTORY_CORE1_RUNTIME)
	return print_core1_status(shell);
#else
	return 0;
#endif
}

static int cmd_buttons(const struct shell *shell, size_t argc, char **argv)
{
	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	struct picosystem_diagnostic_snapshot snapshot;
	const int err = get_snapshot_or_report(shell, &snapshot);
	if (err != 0) {
		return err;
	}

	print_buttons(shell, snapshot.buttons);
	return 0;
}

static int cmd_led(const struct shell *shell, size_t argc, char **argv)
{
	ARG_UNUSED(argc);

	for (size_t i = 0U; i < ARRAY_SIZE(led_modes); ++i) {
		if (strcmp(argv[1], led_modes[i].name) == 0) {
			atomic_set(&selected_led_mode, led_modes[i].mode);
			shell_print(shell, "software LED mode: %s", led_modes[i].name);
			return 0;
		}
	}

	shell_error(shell, "Unknown LED mode '%s'", argv[1]);
	return -EINVAL;
}

static int parse_u32(const struct shell *shell, const char *name, const char *text, uint32_t *value)
{
	int err = 0;
	const unsigned long parsed = shell_strtoul(text, 10, &err);

	if ((err != 0) || (parsed > UINT32_MAX)) {
		shell_error(shell, "Invalid %s '%s'", name, text);
		return (err != 0) ? err : -ERANGE;
	}

	*value = (uint32_t)parsed;
	return 0;
}

static int cmd_tone(const struct shell *shell, size_t argc, char **argv)
{
	ARG_UNUSED(argc);

	struct picosystem_tone_request request;
	int err = parse_u32(shell, "frequency", argv[1], &request.frequency_hz);
	if (err != 0) {
		return err;
	}

	err = parse_u32(shell, "duration", argv[2], &request.duration_ms);
	if (err != 0) {
		return err;
	}

	err = picosystem_piezo_validate(request.frequency_hz, request.duration_ms);
	if (err != 0) {
		shell_error(shell, "Tone must be 100-4000 Hz and 1-1000 ms");
		return err;
	}

	err = k_msgq_put(&tone_requests, &request, K_NO_WAIT);
	if (err != 0) {
		shell_error(shell, "Tone request queue is busy (%d)", err);
		return err;
	}

	shell_print(shell, "queued tone: %u Hz for %u ms", request.frequency_hz,
		    request.duration_ms);
	return 0;
}

static int cmd_display_stats(const struct shell *shell, size_t argc, char **argv)
{
	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	struct picosystem_diagnostic_snapshot snapshot;
	const int err = get_snapshot_or_report(shell, &snapshot);
	if (err != 0) {
		return err;
	}

	const struct picosystem_game_demo_stats *const game = &snapshot.game;
	const struct picosystem_graphics_stats *const graphics = &game->graphics;
	const int64_t metrics_time_ms = snapshot.snapshot_uptime_ms;
	const uint32_t simulation_rate_tenths = measured_rate_tenths(
		game->measured_logic_tick_count, game->start_uptime_ms, metrics_time_ms);
	const uint32_t frame_rate_tenths = measured_rate_tenths(
		game->measured_presented_frame_count, game->start_uptime_ms, metrics_time_ms);

	shell_print(shell, "buffers: framebuffer=%u bytes, transfer=%u bytes",
		    graphics->framebuffer_bytes, graphics->transfer_buffer_bytes);
	shell_print(shell, "full #%u: %u us, %u KiB/s", graphics->full_present_count,
		    graphics->full_present_time_us,
		    graphics->full_present_throughput_kib_per_second);
	shell_print(shell, "last #%u: %ux%u, %u us, %u KiB/s", graphics->present_count,
		    graphics->last_present_width, graphics->last_present_height,
		    graphics->last_present_time_us,
		    graphics->last_present_throughput_kib_per_second);
	shell_print(shell,
		    "simulation: ticks=%u, window=%u (%u.%u Hz), update=%u/%u/%u us "
		    "last/mean/max, physics=%u/%u/%u, snapshot=%u/%u/%u, "
		    "backlog=%u, "
		    "skipped=%u, over-budget=%u",
		    game->logic_tick_count, game->measured_logic_tick_count,
		    simulation_rate_tenths / 10U, simulation_rate_tenths % 10U,
		    game->last_update_time_us, game->mean_update_time_us, game->max_update_time_us,
		    game->last_physics_time_us, game->mean_physics_time_us,
		    game->max_physics_time_us, game->last_snapshot_time_us,
		    game->mean_snapshot_time_us, game->max_snapshot_time_us,
		    game->max_backlog_ticks, game->skipped_tick_count,
		    game->over_budget_tick_count);
	shell_print(shell,
		    "renderer: running=%s, mode=%s, frames=%u, window=%u (%u.%u fps), "
		    "wall=%u us, full=%u, error=%d",
		    game->render_thread_running ? "yes" : "no",
		    game->full_frame_renderer_enabled ? "full-frame" : "damage-region",
		    game->presented_frame_count, game->measured_presented_frame_count,
		    frame_rate_tenths / 10U, frame_rate_tenths % 10U, game->last_render_time_us,
		    game->full_redraw_count, game->render_error);
	shell_print(shell,
		    "raster: core=%u, available=%s, %u us (max=%u), core1 frames=%u; "
		    "present=%u regions/%u pixels/%u us",
		    game->last_raster_on_core1 ? 1U : 0U,
		    game->core1_renderer_available ? "yes" : "no", game->last_raster_time_us,
		    game->maximum_raster_time_us, game->core1_raster_frame_count,
		    game->last_dirty_region_count, game->last_dirty_pixel_count,
		    game->last_dirty_present_time_us);
	shell_print(shell, "snapshots: published=%u, superseded=%u, age=%u us (dirty max=%u us)",
		    game->published_snapshot_count, game->superseded_snapshot_count,
		    game->last_snapshot_age_us, game->max_dirty_snapshot_age_us);
	shell_print(shell,
		    "physics: bodies=%u, segments=%u, joints=%u distance/%u revolute/%u "
		    "prismatic, sensors=%u, contacts=%u, "
		    "candidates=%u/%u, "
		    "grid=%u/%u cells, solver=%u/%u, contact solver=%u visits, %u cached, "
		    "%u changed, "
		    "fallback=%s",
		    game->body_count, game->static_segment_count, game->distance_joint_count,
		    game->revolute_joint_count, game->prismatic_joint_count, game->box_sensor_count,
		    game->contact_count, game->candidate_pair_count, game->possible_pair_count,
		    game->occupied_grid_cell_count, PICOSYSTEM_PHYSICS_GRID_CELL_COUNT,
		    game->solver_iteration_count, PICOSYSTEM_PHYSICS_SOLVER_ITERATIONS,
		    game->solver_contact_visit_count, game->solver_cached_contact_count,
		    game->solver_changed_contact_count, game->broad_phase_fallback ? "yes" : "no");
	shell_print(shell,
		    "sleep: awake=%u, sleeping=%u, transitions=%u sleep/%u wake, "
		    "constraints skipped=%u contacts/%u joints",
		    game->awake_body_count, game->sleeping_body_count,
		    game->body_sleep_transition_count, game->body_wake_transition_count,
		    game->sleeping_contact_count, game->sleeping_joint_count);
	shell_print(shell,
		    "powered: springs=%u, spring solver=%u visits/%u changed, "
		    "conveyors=%u contacts, %u visits/%u changed",
		    game->spring_joint_count, game->spring_solver_visit_count,
		    game->spring_solver_changed_count, game->conveyor_contact_count,
		    game->conveyor_solver_visit_count, game->conveyor_solver_changed_count);
	shell_print(shell,
		    "events: active=%u, sensor overlaps=%u, emitted=%u (%u begin/%u stay/%u end), "
		    "sensor entries=%u",
		    game->active_contact_pair_count, game->sensor_overlap_count,
		    game->contact_event_count, game->contact_begin_event_count,
		    game->contact_stay_event_count, game->contact_end_event_count,
		    game->sensor_entry_count);
	shell_print(shell,
		    "focus #%u %s: simulation=(%u,%u), displayed=(%u,%u), "
		    "velocity=(%d,%d) px/s, angle=%08x, angular=%d mrad/s, sleep=%s",
		    game->focus_body_id, physics_shape_name(game->focus_shape), game->focus_x,
		    game->focus_y, game->presented_focus_x, game->presented_focus_y,
		    game->focus_velocity_x_pixels_per_second,
		    game->focus_velocity_y_pixels_per_second, game->focus_angle_turns,
		    game->focus_angular_velocity_milliradians_per_second,
		    game->focus_sleeping ? "yes" : "no");
	shell_print(shell, "main stack high-water: %u/%u bytes",
		    snapshot.runtime.main_stack_used_bytes, snapshot.runtime.main_stack_size_bytes);
	shell_print(shell, "render stack high-water: %u/%u bytes", game->render_stack_used_bytes,
		    game->render_stack_size_bytes);
	return 0;
}

static void print_timing_range(const struct shell *shell, const char *name, uint32_t samples,
			       uint32_t mean_us, uint32_t min_us, uint32_t max_us)
{
	if (samples == 0U) {
		shell_print(shell, "%s: no samples", name);
		return;
	}

	shell_print(shell, "%s: mean=%u us, min=%u us, max=%u us, jitter=%u us (#%u)", name,
		    mean_us, min_us, max_us, max_us - min_us, samples);
}

static int cmd_display_sync(const struct shell *shell, size_t argc, char **argv)
{
	if (argc == 2U) {
		bool enabled;
		if (strcmp(argv[1], "on") == 0) {
			enabled = true;
		} else if (strcmp(argv[1], "off") == 0) {
			enabled = false;
		} else {
			shell_error(shell, "Expected 'on' or 'off'");
			return -EINVAL;
		}

		const int set_err = picosystem_display_sync_set_enabled(enabled);
		if (set_err != 0) {
			shell_error(shell, "Failed to %s display synchronization (%d)",
				    enabled ? "enable" : "disable", set_err);
			return set_err;
		}
	}

	struct picosystem_display_sync_stats stats;
	const int err = picosystem_display_sync_get_stats(&stats);
	if (err != 0) {
		shell_error(shell, "Display TE measurement is unavailable (%d)", err);
		return err;
	}

	const uint32_t frequency_millihz =
		(stats.period_mean_us == 0U)
			? 0U
			: (uint32_t)(UINT64_C(1000000000) / stats.period_mean_us);

	shell_print(shell, "TE: panel=%s, GP8=%s, polarity=active-high blanking",
		    stats.panel_te_enabled ? "enabled" : "disabled",
		    stats.signal_high ? "high" : "low");
	shell_print(shell, "edges: rising=%u, falling=%u, read-errors=%u, last=%u us ago",
		    stats.rising_edges, stats.falling_edges, stats.gpio_read_errors,
		    stats.last_edge_age_us);
	if (frequency_millihz != 0U) {
		shell_print(shell, "frequency: %u.%03u Hz", frequency_millihz / 1000U,
			    frequency_millihz % 1000U);
	}
	print_timing_range(shell, "period", stats.period_samples, stats.period_mean_us,
			   stats.period_min_us, stats.period_max_us);
	print_timing_range(shell, "high", stats.high_samples, stats.high_mean_us, stats.high_min_us,
			   stats.high_max_us);
	print_timing_range(shell, "low", stats.low_samples, stats.low_mean_us, stats.low_min_us,
			   stats.low_max_us);
	shell_print(shell,
		    "presentation sync: requested=%s, signal=%s, synchronized=%u, bypassed=%u, "
		    "timeouts=%u, wait=%u us (max=%u us)",
		    stats.synchronization_requested ? "on" : "off",
		    stats.signal_qualified ? "qualified" : "unqualified",
		    stats.synchronized_presents, stats.bypassed_presents, stats.timed_out_presents,
		    stats.last_wait_us, stats.max_wait_us);
	return 0;
}

struct framebuffer_shell_capture {
	const struct shell *shell;
};

static uint8_t
	framebuffer_base64_buffer[((PICOSYSTEM_GAME_FRAMEBUFFER_CHUNK_BYTES + 2U) / 3U * 4U) + 1U];

static int emit_framebuffer_chunk(size_t offset, const uint8_t *data, size_t length, void *context)
{
	if ((data == NULL) || (context == NULL) ||
	    (length > PICOSYSTEM_GAME_FRAMEBUFFER_CHUNK_BYTES)) {
		return -EINVAL;
	}

	struct framebuffer_shell_capture *const capture = context;
	size_t encoded_length;
	const int err = base64_encode(framebuffer_base64_buffer, sizeof(framebuffer_base64_buffer),
				      &encoded_length, data, length);
	if (err != 0) {
		return err;
	}

	shell_print(capture->shell, "FRAMEBUFFER_DATA offset=%u data=%.*s", (uint32_t)offset,
		    (int)encoded_length, (const char *)framebuffer_base64_buffer);
	return 0;
}

static int cmd_display_checksum(const struct shell *shell, size_t argc, char **argv)
{
	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	struct picosystem_game_framebuffer_capture capture;
	const int err = picosystem_game_demo_capture_framebuffer(NULL, NULL, &capture);
	if (err != 0) {
		shell_error(shell, "Failed to checksum the presented framebuffer (%d)", err);
		return err;
	}

	shell_print(shell, "width=%u height=%u format=rgb565be bytes=%u sequence=%u crc32=%08x",
		    capture.width, capture.height, capture.byte_count,
		    capture.presented_snapshot_sequence, capture.crc32);
	return 0;
}

static int cmd_display_capture(const struct shell *shell, size_t argc, char **argv)
{
	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	shell_print(shell, "FRAMEBUFFER_BEGIN width=%u height=%u format=rgb565be bytes=%u",
		    PICOSYSTEM_GRAPHICS_WIDTH, PICOSYSTEM_GRAPHICS_HEIGHT,
		    PICOSYSTEM_GRAPHICS_FRAMEBUFFER_BYTES);
	struct framebuffer_shell_capture shell_capture = {.shell = shell};
	struct picosystem_game_framebuffer_capture capture;
	const int err = picosystem_game_demo_capture_framebuffer(emit_framebuffer_chunk,
								 &shell_capture, &capture);
	if (err != 0) {
		shell_error(shell, "Failed to capture the presented framebuffer (%d)", err);
		return err;
	}

	shell_print(shell, "FRAMEBUFFER_END sequence=%u crc32=%08x",
		    capture.presented_snapshot_sequence, capture.crc32);
	return 0;
}

static void print_game_control_state(const struct shell *shell,
				     const struct picosystem_game_control_state *state)
{
	shell_print(shell, "mode=%s tick=%u hash=%08x", state->paused ? "paused" : "running",
		    state->logic_tick_count, state->state_hash);
	shell_print(shell, "input_source=%s input_x=%d input_y=%d",
		    state->remote_input_enabled ? "remote" : "physical", state->input.horizontal,
		    state->input.vertical);
	shell_print(shell,
		    "focus_id=%u focus_shape=%s focus_x_q16=%d focus_y_q16=%d "
		    "velocity_x_q16_per_tick=%d velocity_y_q16_per_tick=%d",
		    state->focus_body_id, physics_shape_name(state->focus_shape),
		    state->focus_x_fixed, state->focus_y_fixed,
		    state->focus_velocity_x_fixed_per_tick, state->focus_velocity_y_fixed_per_tick);
	shell_print(shell, "angle_turns=%08x angular_velocity_q16_per_tick=%d",
		    state->focus_angle_turns, state->focus_angular_velocity_fixed_per_tick);
	shell_print(shell, "published_snapshot=%u presented_snapshot=%u",
		    state->published_snapshot_sequence, state->presented_snapshot_sequence);
}

static int submit_game_control(const struct shell *shell,
			       const struct picosystem_game_control_request *request)
{
	struct picosystem_game_control_state state;
	const int err = picosystem_game_control_submit(request, &state);
	if (err == -EBUSY) {
		if (request->operation == PICOSYSTEM_GAME_CONTROL_RESET) {
			shell_error(shell, "Pause the simulation before resetting");
		} else {
			shell_error(shell, "Pause the simulation before stepping");
		}
		return err;
	}
	if (err != 0) {
		shell_error(shell, "Game-control request failed (%d)", err);
		return err;
	}

	print_game_control_state(shell, &state);
	return 0;
}

static int cmd_game_pause(const struct shell *shell, size_t argc, char **argv)
{
	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	const struct picosystem_game_control_request request = {
		.operation = PICOSYSTEM_GAME_CONTROL_PAUSE,
	};
	return submit_game_control(shell, &request);
}

static int cmd_game_run(const struct shell *shell, size_t argc, char **argv)
{
	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	const struct picosystem_game_control_request request = {
		.operation = PICOSYSTEM_GAME_CONTROL_RUN,
	};
	return submit_game_control(shell, &request);
}

static int cmd_game_reset(const struct shell *shell, size_t argc, char **argv)
{
	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	const struct picosystem_game_control_request request = {
		.operation = PICOSYSTEM_GAME_CONTROL_RESET,
	};
	return submit_game_control(shell, &request);
}

static int cmd_game_step(const struct shell *shell, size_t argc, char **argv)
{
	uint32_t step_count = 1U;
	if (argc == 2U) {
		const int err = parse_u32(shell, "step count", argv[1], &step_count);
		if (err != 0) {
			return err;
		}
	}
	if ((step_count == 0U) || (step_count > PICOSYSTEM_GAME_CONTROL_MAX_STEPS)) {
		shell_error(shell, "Step count must be 1-%u", PICOSYSTEM_GAME_CONTROL_MAX_STEPS);
		return -ERANGE;
	}

	const struct picosystem_game_control_request request = {
		.step_count = step_count,
		.operation = PICOSYSTEM_GAME_CONTROL_STEP,
	};
	return submit_game_control(shell, &request);
}

static int cmd_game_input(const struct shell *shell, size_t argc, char **argv)
{
	ARG_UNUSED(argc);

	for (size_t i = 0U; i < ARRAY_SIZE(game_inputs); ++i) {
		if (strcmp(argv[1], game_inputs[i].name) != 0) {
			continue;
		}

		const struct picosystem_game_control_request request = {
			.input = game_inputs[i].input,
			.operation = PICOSYSTEM_GAME_CONTROL_SET_INPUT,
			.remote_input_enabled = game_inputs[i].remote_input_enabled,
		};
		return submit_game_control(shell, &request);
	}

	shell_error(shell, "Unknown input '%s'", argv[1]);
	return -EINVAL;
}

static int cmd_game_state(const struct shell *shell, size_t argc, char **argv)
{
	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	const struct picosystem_game_control_request request = {
		.operation = PICOSYSTEM_GAME_CONTROL_GET_STATE,
	};
	return submit_game_control(shell, &request);
}

static int cmd_game_redraw(const struct shell *shell, size_t argc, char **argv)
{
	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	atomic_set(&redraw_requested, 1);
	shell_print(shell, "queued asynchronous full redraw");
	return 0;
}

static uint32_t profile_cycles_to_microseconds(uint32_t cycles, uint32_t clock_frequency_hz)
{
	return (uint32_t)((((uint64_t)cycles * 1000000U) + (clock_frequency_hz / 2U)) /
			  clock_frequency_hz);
}

static void print_display_profile_result(const struct shell *shell,
					 const struct picosystem_display_profile_result *result)
{
	shell_print(shell,
		    "DISPLAY_PROFILE_BEGIN schema=%u samples=%u warmup=%u clock_hz=%u "
		    "configured_spi_hz=%u width=%u height=%u bpp=%u transport=%s cases=%u",
		    result->schema_version, result->measured_sample_count,
		    result->warmup_sample_count, result->clock_frequency_hz,
		    result->configured_spi_frequency_hz, result->width, result->height,
		    result->bytes_per_pixel, picosystem_graphics_transport_name(result->transport),
		    PICOSYSTEM_DISPLAY_PROFILE_CASE_COUNT);

	for (size_t case_index = 0U; case_index < PICOSYSTEM_DISPLAY_PROFILE_CASE_COUNT;
	     ++case_index) {
		const struct picosystem_display_profile_case_result *const case_result =
			&result->cases[case_index];
		const char *const case_name = picosystem_display_profile_case_name(case_index);
		shell_print(shell,
			    "DISPLAY_PROFILE_CASE name=%s coverage=%u payload_bytes=%u regions=%u "
			    "writes=%u synchronized=%u crc32=%08x",
			    case_name, case_result->coverage_percent, case_result->payload_bytes,
			    case_result->region_count, case_result->display_write_count,
			    case_result->synchronized_wait_count, case_result->framebuffer_crc32);

		for (size_t stage = 0U; stage < PICOSYSTEM_DISPLAY_PROFILE_STAGE_COUNT; ++stage) {
			const struct picosystem_display_profile_stage_summary *const summary =
				&case_result->stages[stage];
			shell_print(shell,
				    "DISPLAY_PROFILE_STAGE name=%s stage=%s samples=%u mean_us=%u "
				    "min_us=%u p50_us=%u p95_us=%u p99_us=%u max_us=%u",
				    case_name, picosystem_display_profile_stage_name(stage),
				    summary->sample_count,
				    profile_cycles_to_microseconds(summary->mean_cycles,
								   result->clock_frequency_hz),
				    profile_cycles_to_microseconds(summary->minimum_cycles,
								   result->clock_frequency_hz),
				    profile_cycles_to_microseconds(summary->percentile_50_cycles,
								   result->clock_frequency_hz),
				    profile_cycles_to_microseconds(summary->percentile_95_cycles,
								   result->clock_frequency_hz),
				    profile_cycles_to_microseconds(summary->percentile_99_cycles,
								   result->clock_frequency_hz),
				    profile_cycles_to_microseconds(summary->maximum_cycles,
								   result->clock_frequency_hz));
		}
	}

	for (size_t stage = 0U; stage < PICOSYSTEM_DISPLAY_PROFILE_DENSE_STAGE_COUNT; ++stage) {
		const struct picosystem_display_profile_stage_summary *const summary =
			&result->dense_stages[stage];
		shell_print(shell,
			    "DISPLAY_PROFILE_DENSE_STAGE stage=%s samples=%u mean_us=%u min_us=%u "
			    "p50_us=%u p95_us=%u p99_us=%u max_us=%u",
			    picosystem_display_profile_dense_stage_name(stage),
			    summary->sample_count,
			    profile_cycles_to_microseconds(summary->mean_cycles,
							   result->clock_frequency_hz),
			    profile_cycles_to_microseconds(summary->minimum_cycles,
							   result->clock_frequency_hz),
			    profile_cycles_to_microseconds(summary->percentile_50_cycles,
							   result->clock_frequency_hz),
			    profile_cycles_to_microseconds(summary->percentile_95_cycles,
							   result->clock_frequency_hz),
			    profile_cycles_to_microseconds(summary->percentile_99_cycles,
							   result->clock_frequency_hz),
			    profile_cycles_to_microseconds(summary->maximum_cycles,
							   result->clock_frequency_hz));
	}

	shell_print(shell,
		    "DISPLAY_PROFILE_VERIFY original_crc32=%08x restored_crc32=%08x "
		    "framebuffer_restored=%s",
		    result->original_framebuffer_crc32, result->restored_framebuffer_crc32,
		    result->framebuffer_restored ? "yes" : "no");
}

static int cmd_display_profile(const struct shell *shell, size_t argc, char **argv)
{
	uint32_t measured_sample_count = PICOSYSTEM_DISPLAY_PROFILE_DEFAULT_SAMPLES;
	if (argc == 2U) {
		const int parse_err =
			parse_u32(shell, "measured sample count", argv[1], &measured_sample_count);
		if (parse_err != 0) {
			return parse_err;
		}
	}
	if ((measured_sample_count == 0U) ||
	    (measured_sample_count > PICOSYSTEM_DISPLAY_PROFILE_MAX_SAMPLES)) {
		shell_error(shell, "Measured sample count must be 1-%u",
			    PICOSYSTEM_DISPLAY_PROFILE_MAX_SAMPLES);
		return -ERANGE;
	}

	struct picosystem_game_control_state state;
	const struct picosystem_game_control_request request = {
		.operation = PICOSYSTEM_GAME_CONTROL_GET_STATE,
	};
	int err = picosystem_game_control_submit(&request, &state);
	if (err != 0) {
		shell_error(shell, "Could not query simulation state (%d)", err);
		return err;
	}
	if (!state.paused) {
		shell_error(shell, "Pause the simulation before profiling the display");
		return -EBUSY;
	}

	err = picosystem_game_demo_profile_display(measured_sample_count, &display_profile_result);
	if ((err == 0) || (err == -EILSEQ)) {
		print_display_profile_result(shell, &display_profile_result);
		size_t unused_stack_bytes;
		const int stack_err =
			k_thread_stack_space_get(k_current_get(), &unused_stack_bytes);
		if (stack_err == 0) {
			shell_print(shell,
				    "DISPLAY_PROFILE_RESOURCE shell_stack_used_bytes=%u "
				    "shell_stack_size_bytes=%u",
				    CONFIG_SHELL_STACK_SIZE - (uint32_t)unused_stack_bytes,
				    CONFIG_SHELL_STACK_SIZE);
		} else if (err == 0) {
			err = stack_err;
		}
		shell_print(shell, "DISPLAY_PROFILE_END status=%s", (err == 0) ? "ok" : "failed");
	}
	if (err != 0) {
		shell_error(shell, "Display profile failed (%d)", err);
	}
	return err;
}

static void print_profile_result(const struct shell *shell,
				 const struct picosystem_physics_profile_result *result)
{
	shell_print(
		shell,
		"PROFILE_BEGIN schema=%u fixture=%s chain_links=%u ticks=%u warmup=%u "
		"clock_hz=%u "
		"histogram_fine_bin_us=%u histogram_fine_bins=%u "
		"histogram_coarse_bin_us=%u histogram_coarse_bins=%u clock_delta_cycles=%u",
		result->schema_version, picosystem_physics_profile_fixture_name(result->fixture),
		result->chain_link_count, result->measured_tick_count, result->warmup_tick_count,
		result->clock_frequency_hz, PICOSYSTEM_PHYSICS_PROFILE_HISTOGRAM_FINE_BIN_US,
		PICOSYSTEM_PHYSICS_PROFILE_HISTOGRAM_FINE_BIN_COUNT,
		PICOSYSTEM_PHYSICS_PROFILE_HISTOGRAM_COARSE_BIN_US,
		PICOSYSTEM_PHYSICS_PROFILE_HISTOGRAM_COARSE_BIN_COUNT,
		result->back_to_back_clock_delta_cycles);

	for (size_t mode = 0U; mode < PICOSYSTEM_PHYSICS_PROFILE_MODE_COUNT; ++mode) {
		const struct picosystem_physics_profile_mode_result *const mode_result =
			&result->modes[mode];
		const char *const mode_name = picosystem_physics_profile_mode_name(mode);
		shell_print(shell,
			    "PROFILE_MODE mode=%s hash=%08x clock_reads_min=%u clock_reads_max=%u "
			    "max_revolute_anchor_error_q16=%u "
			    "max_revolute_limit_violation_q16=%u "
			    "max_prismatic_lateral_error_q16=%u "
			    "max_prismatic_angular_error_q16=%u "
			    "max_prismatic_limit_violation_q16=%u",
			    mode_name, mode_result->final_hash,
			    mode_result->minimum_clock_reads_per_step,
			    mode_result->maximum_clock_reads_per_step,
			    mode_result->maximum_revolute_anchor_error_q16,
			    mode_result->maximum_revolute_limit_violation_q16,
			    mode_result->maximum_prismatic_lateral_error_q16,
			    mode_result->maximum_prismatic_angular_error_q16,
			    mode_result->maximum_prismatic_limit_violation_q16);

		for (size_t stage = 0U; stage < PICOSYSTEM_PHYSICS_PROFILE_STAGE_COUNT; ++stage) {
			const struct picosystem_physics_profile_stage_summary *const summary =
				&mode_result->stages[stage];
			shell_print(
				shell,
				"PROFILE_STAGE mode=%s stage=%s samples=%u mean_us=%u min_us=%u "
				"p50_us=%u p95_us=%u p99_us=%u max_us=%u budget_violations=%u",
				mode_name, picosystem_physics_profile_stage_name(stage),
				summary->sample_count,
				profile_cycles_to_microseconds(summary->mean_cycles,
							       result->clock_frequency_hz),
				profile_cycles_to_microseconds(summary->minimum_cycles,
							       result->clock_frequency_hz),
				profile_cycles_to_microseconds(summary->percentile_50_cycles,
							       result->clock_frequency_hz),
				profile_cycles_to_microseconds(summary->percentile_95_cycles,
							       result->clock_frequency_hz),
				profile_cycles_to_microseconds(summary->percentile_99_cycles,
							       result->clock_frequency_hz),
				profile_cycles_to_microseconds(summary->maximum_cycles,
							       result->clock_frequency_hz),
				summary->budget_violation_count);
		}

		for (size_t metric = 0U; metric < PICOSYSTEM_PHYSICS_PROFILE_WORK_METRIC_COUNT;
		     ++metric) {
			const struct picosystem_physics_profile_work_summary *const summary =
				&mode_result->work[metric];
			shell_print(shell, "PROFILE_WORK mode=%s metric=%s total=%llu max=%u",
				    mode_name, picosystem_physics_profile_work_name(metric),
				    (unsigned long long)summary->total, summary->maximum);
		}
	}
}

static int run_physics_profile(const struct shell *shell, uint16_t chain_link_count,
			       bool neutral_fixture, uint32_t measured_tick_count)
{
	struct picosystem_game_control_state state;
	const struct picosystem_game_control_request request = {
		.operation = PICOSYSTEM_GAME_CONTROL_GET_STATE,
	};
	int err = picosystem_game_control_submit(&request, &state);
	if (err != 0) {
		shell_error(shell, "Could not query simulation state (%d)", err);
		return err;
	}
	if (!state.paused) {
		shell_error(shell, "Pause the simulation before profiling");
		return -EBUSY;
	}

	if (neutral_fixture) {
		shell_print(
			shell,
			"Running neutral-settle grid/reference replay for %u measured ticks per "
			"mode",
			measured_tick_count);
		err = picosystem_physics_profile_compare_neutral(measured_tick_count,
								 &profile_result);
	} else if (chain_link_count == 0U) {
		shell_print(
			shell,
			"Running canonical grid/reference replay for %u measured ticks per mode",
			measured_tick_count);
		err = picosystem_physics_profile_compare(measured_tick_count, &profile_result);
	} else {
		shell_print(shell,
			    "Running %u-link chain grid/reference replay for %u measured ticks per "
			    "mode",
			    chain_link_count, measured_tick_count);
		err = picosystem_physics_profile_compare_chain(
			chain_link_count, measured_tick_count, &profile_result);
	}
	if ((err == 0) || (err == -EILSEQ)) {
		print_profile_result(shell, &profile_result);
		size_t unused_stack_bytes;
		const int stack_err =
			k_thread_stack_space_get(k_current_get(), &unused_stack_bytes);
		if (stack_err == 0) {
			shell_print(shell,
				    "PROFILE_RESOURCE shell_stack_used_bytes=%u "
				    "shell_stack_size_bytes=%u",
				    CONFIG_SHELL_STACK_SIZE - (uint32_t)unused_stack_bytes,
				    CONFIG_SHELL_STACK_SIZE);
		} else if (err == 0) {
			err = stack_err;
		}
		shell_print(shell, "PROFILE_END hashes_match=%s states_match=%s",
			    profile_result.hashes_match ? "yes" : "no",
			    profile_result.states_match ? "yes" : "no");
	}
	if (err != 0) {
		shell_error(shell, "Physics profile comparison failed (%d)", err);
	}
	return err;
}

static int cmd_profile_compare(const struct shell *shell, size_t argc, char **argv)
{
	uint32_t measured_tick_count = PICOSYSTEM_PHYSICS_PROFILE_DEFAULT_TICKS;
	if (argc == 2U) {
		const int parse_err =
			parse_u32(shell, "measured tick count", argv[1], &measured_tick_count);
		if (parse_err != 0) {
			return parse_err;
		}
	}
	if ((measured_tick_count == 0U) ||
	    (measured_tick_count > PICOSYSTEM_PHYSICS_PROFILE_MAX_TICKS)) {
		shell_error(shell, "Measured tick count must be 1-%u",
			    PICOSYSTEM_PHYSICS_PROFILE_MAX_TICKS);
		return -ERANGE;
	}

	return run_physics_profile(shell, 0U, false, measured_tick_count);
}

static int cmd_profile_sleep(const struct shell *shell, size_t argc, char **argv)
{
	uint32_t measured_tick_count = PICOSYSTEM_PHYSICS_PROFILE_DEFAULT_TICKS;
	if (argc == 2U) {
		const int parse_err =
			parse_u32(shell, "measured tick count", argv[1], &measured_tick_count);
		if (parse_err != 0) {
			return parse_err;
		}
	}
	if ((measured_tick_count == 0U) ||
	    (measured_tick_count > PICOSYSTEM_PHYSICS_PROFILE_MAX_TICKS)) {
		shell_error(shell, "Measured tick count must be 1-%u",
			    PICOSYSTEM_PHYSICS_PROFILE_MAX_TICKS);
		return -ERANGE;
	}

	return run_physics_profile(shell, 0U, true, measured_tick_count);
}

static int cmd_profile_chain(const struct shell *shell, size_t argc, char **argv)
{
	uint32_t link_count;
	int err = parse_u32(shell, "chain link count", argv[1], &link_count);
	if (err != 0) {
		return err;
	}
	if ((link_count < PICOSYSTEM_PHYSICS_CHAIN_FIXTURE_MIN_LINKS) ||
	    (link_count > PICOSYSTEM_PHYSICS_CHAIN_FIXTURE_MAX_LINKS)) {
		shell_error(shell, "Chain link count must be %u-%u",
			    PICOSYSTEM_PHYSICS_CHAIN_FIXTURE_MIN_LINKS,
			    PICOSYSTEM_PHYSICS_CHAIN_FIXTURE_MAX_LINKS);
		return -ERANGE;
	}

	uint32_t measured_tick_count = PICOSYSTEM_PHYSICS_PROFILE_DEFAULT_TICKS;
	if (argc == 3U) {
		err = parse_u32(shell, "measured tick count", argv[2], &measured_tick_count);
		if (err != 0) {
			return err;
		}
	}
	if ((measured_tick_count == 0U) ||
	    (measured_tick_count > PICOSYSTEM_PHYSICS_PROFILE_MAX_TICKS)) {
		shell_error(shell, "Measured tick count must be 1-%u",
			    PICOSYSTEM_PHYSICS_PROFILE_MAX_TICKS);
		return -ERANGE;
	}

	return run_physics_profile(shell, (uint16_t)link_count, false, measured_tick_count);
}

static int cmd_reboot_bootloader(const struct shell *shell, size_t argc, char **argv)
{
	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	const int err = bootmode_set(BOOT_MODE_TYPE_BOOTLOADER);
	if (err != 0) {
		shell_error(shell, "Failed to select the ROM bootloader (%d)", err);
		return err;
	}

	shell_print(shell, "Rebooting into the RP2040 ROM USB bootloader");
	/* Give the USB shell backend time to transmit the notice before reset. */
	k_msleep(BOOTLOADER_REBOOT_DELAY_MS);
	sys_reboot(SYS_REBOOT_COLD);
}

SHELL_STATIC_SUBCMD_SET_CREATE(
	display_commands,
	SHELL_CMD_ARG(capture, NULL, "Stream the coherent RGB565 framebuffer.", cmd_display_capture,
		      1, 0),
	SHELL_CMD_ARG(checksum, NULL, "Checksum the coherent presented framebuffer.",
		      cmd_display_checksum, 1, 0),
	SHELL_CMD_ARG(profile, NULL,
		      SHELL_HELP("Profile dense display workloads.",
				 "[samples] (default 16, maximum 64; simulation must be paused)"),
		      cmd_display_profile, 1, 1),
	SHELL_CMD_ARG(stats, NULL, "Show framebuffer, timing, and game-loop metrics.",
		      cmd_display_stats, 1, 0),
	SHELL_CMD_ARG(sync, NULL,
		      SHELL_HELP("Show or control LCD tearing-effect synchronization.", "[on|off]"),
		      cmd_display_sync, 1, 1),
	SHELL_SUBCMD_SET_END);

SHELL_STATIC_SUBCMD_SET_CREATE(
	game_commands,
	SHELL_CMD_ARG(input, NULL,
		      SHELL_HELP("Select physical or injected input.",
				 "<physical|none|up|down|left|right|"
				 "up-left|up-right|down-left|down-right>"),
		      cmd_game_input, 2, 0),
	SHELL_CMD_ARG(pause, NULL, "Pause at the next tick boundary.", cmd_game_pause, 1, 0),
	SHELL_CMD_ARG(reset, NULL, "Restore canonical tick-zero state while paused.",
		      cmd_game_reset, 1, 0),
	SHELL_CMD_ARG(stats, NULL, "Show simulation, snapshot, and renderer metrics.",
		      cmd_display_stats, 1, 0),
	SHELL_CMD_ARG(state, NULL, "Show exact authoritative state.", cmd_game_state, 1, 0),
	SHELL_CMD_ARG(step, NULL,
		      SHELL_HELP("Advance a paused simulation exactly.",
				 "[count] (default 1, maximum 120)"),
		      cmd_game_step, 1, 1),
	SHELL_CMD_ARG(run, NULL, "Resume real-time 120 Hz scheduling.", cmd_game_run, 1, 0),
	SHELL_CMD_ARG(redraw, NULL, "Queue a renderer-owned full redraw.", cmd_game_redraw, 1, 0),
	SHELL_SUBCMD_SET_END);

SHELL_STATIC_SUBCMD_SET_CREATE(reboot_commands,
			       SHELL_CMD_ARG(bootloader, NULL,
					     "Reboot into the RP2040 ROM USB bootloader.",
					     cmd_reboot_bootloader, 1, 0),
			       SHELL_SUBCMD_SET_END);

SHELL_STATIC_SUBCMD_SET_CREATE(
	profile_commands,
	SHELL_CMD_ARG(chain, NULL,
		      SHELL_HELP("Compare a deterministic revolute-chain fixture.",
				 "<links> [ticks] (links 1-8, default 2000 ticks; simulation must "
				 "be paused)"),
		      cmd_profile_chain, 2, 1),
	SHELL_CMD_ARG(
		compare, NULL,
		SHELL_HELP("Compare isolated grid and brute-force physics replays.",
			   "[ticks] (default 2000, maximum 10000; simulation must be paused)"),
		cmd_profile_compare, 1, 1),
	SHELL_CMD_ARG(
		sleep, NULL,
		SHELL_HELP("Compare the canonical world settling under neutral input.",
			   "[ticks] (default 2000, maximum 10000; simulation must be paused)"),
		cmd_profile_sleep, 1, 1),
	SHELL_SUBCMD_SET_END);

#if defined(CONFIG_TOY_FACTORY_CORE1_RUNTIME)
SHELL_STATIC_SUBCMD_SET_CREATE(
	core1_commands,
	SHELL_CMD_ARG(ping, NULL, SHELL_HELP("Run a shared-memory round trip.", "[challenge]"),
		      cmd_core1_ping, 1, 1),
	SHELL_CMD_ARG(raster, NULL,
		      SHELL_HELP("Compare deterministic core-0/core-1 raster output.",
				 "[frame] (simulation must be paused)"),
		      cmd_core1_raster, 1, 1),
	SHELL_CMD_ARG(scene, NULL, "Compare the current live scene raster on core 0 and core 1.",
		      cmd_core1_scene, 1, 0),
	SHELL_CMD_ARG(status, NULL, "Show auxiliary-core protocol and stack health.",
		      cmd_core1_status, 1, 0),
	SHELL_SUBCMD_SET_END);
#endif

SHELL_STATIC_SUBCMD_SET_CREATE(
	picosystem_commands,
	SHELL_CMD_ARG(status, NULL, "Show a coherent board-state snapshot.", cmd_status, 1, 0),
	SHELL_CMD_ARG(buttons, NULL, "Show the currently pressed buttons.", cmd_buttons, 1, 0),
	SHELL_CMD_ARG(led, NULL,
		      SHELL_HELP("Override the software RGB output.",
				 "<auto|off|red|green|blue|white>\n"
				 "The independent hardware charge indicator remains active."),
		      cmd_led, 2, 0),
	SHELL_CMD_ARG(tone, NULL,
		      SHELL_HELP("Queue a bounded piezo tone.",
				 "<frequency_hz> <duration_ms>\n"
				 "Frequency: 100-4000 Hz; duration: 1-1000 ms."),
		      cmd_tone, 3, 0),
#if defined(CONFIG_TOY_FACTORY_CORE1_RUNTIME)
	SHELL_CMD(core1, &core1_commands, "RP2040 auxiliary-core diagnostics.", NULL),
#endif
	SHELL_CMD(display, &display_commands, "Display diagnostic commands.", NULL),
	SHELL_CMD(game, &game_commands, "Game-loop diagnostic commands.", NULL),
	SHELL_CMD(profile, &profile_commands, "Physics profiling commands.", NULL),
	SHELL_CMD(reboot, &reboot_commands, "Reboot commands.", NULL), SHELL_SUBCMD_SET_END);

SHELL_CMD_REGISTER(picosystem, &picosystem_commands, "PicoSystem diagnostics.", NULL);

int picosystem_diagnostic_shell_publish(const struct picosystem_diagnostic_snapshot *snapshot)
{
	if (snapshot == NULL) {
		return -EINVAL;
	}

	const int err = k_mutex_lock(&snapshot_mutex, K_FOREVER);
	if (err != 0) {
		return err;
	}

	latest_snapshot = *snapshot;
	snapshot_available = true;
	k_mutex_unlock(&snapshot_mutex);
	return 0;
}

enum picosystem_led_mode picosystem_diagnostic_shell_led_mode(void)
{
	return (enum picosystem_led_mode)atomic_get(&selected_led_mode);
}

int picosystem_diagnostic_shell_take_tone(struct picosystem_tone_request *request)
{
	if (request == NULL) {
		return -EINVAL;
	}

	return k_msgq_get(&tone_requests, request, K_NO_WAIT);
}

bool picosystem_diagnostic_shell_take_redraw(void)
{
	return atomic_set(&redraw_requested, 0) != 0;
}
