/*
 * Copyright (c) 2026 PicoSystem Playground contributors
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
#include <zephyr/sys/reboot.h>
#include <zephyr/sys/util.h>

#include "display_sync.h"
#include "piezo.h"

#define BOOTLOADER_REBOOT_DELAY_MS 100

struct named_button {
	const char *name;
	enum picosystem_button_index index;
};

struct named_led_mode {
	const char *name;
	enum picosystem_led_mode mode;
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

BUILD_ASSERT(ARRAY_SIZE(button_names) == PICOSYSTEM_BUTTON_COUNT);

K_MUTEX_DEFINE(snapshot_mutex);
K_MSGQ_DEFINE(tone_requests, sizeof(struct picosystem_tone_request), 1U, 4U);

static struct picosystem_diagnostic_snapshot latest_snapshot;
static bool snapshot_available;
static atomic_t selected_led_mode = ATOMIC_INIT(PICOSYSTEM_LED_MODE_AUTO);

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

static uint32_t game_frame_rate_tenths(const struct picosystem_game_demo_state *game,
				       int64_t now_ms)
{
	const int64_t elapsed_ms = MAX(now_ms - game->start_uptime_ms, INT64_C(1));
	const uint64_t scaled_rate =
		((uint64_t)game->presented_frame_count * 10U * MSEC_PER_SEC) / elapsed_ms;

	return (uint32_t)MIN(scaled_rate, UINT32_MAX);
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
	const char *const usb_name = snapshot.power.usb_power_present ? "present" : "absent";
	const char *const charge_name = snapshot.power.charging ? "active" : "inactive";
	const uint32_t frame_rate_tenths = game_frame_rate_tenths(&snapshot.game, now_ms);

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
		    "game: ticks=%u, frames=%u (%u.%u fps), skipped=%u, sprite=(%u,%u) "
		    "velocity=(%d,%d)",
		    snapshot.game.logic_tick_count, snapshot.game.presented_frame_count,
		    frame_rate_tenths / 10U, frame_rate_tenths % 10U,
		    snapshot.game.skipped_tick_count, snapshot.game.sprite_x,
		    snapshot.game.sprite_y, snapshot.game.velocity_x, snapshot.game.velocity_y);
	shell_print(shell, "main stack high-water: %u/%u bytes",
		    snapshot.runtime.main_stack_used_bytes, snapshot.runtime.main_stack_size_bytes);
	shell_print(shell, "led: %s", led_mode_name(picosystem_diagnostic_shell_led_mode()));
	return 0;
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

	const struct picosystem_game_demo_state *const game = &snapshot.game;
	const struct picosystem_graphics_stats *const graphics = &game->graphics;
	const uint32_t frame_rate_tenths = game_frame_rate_tenths(game, k_uptime_get());

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
		    "game: ticks=%u, frames=%u (%u.%u fps), skipped=%u, render=%u us "
		    "(dirty max=%u us)",
		    game->logic_tick_count, game->presented_frame_count, frame_rate_tenths / 10U,
		    frame_rate_tenths % 10U, game->skipped_tick_count, game->last_render_time_us,
		    game->max_dirty_render_time_us);
	shell_print(shell, "sprite: (%u,%u), velocity=(%d,%d)", game->sprite_x, game->sprite_y,
		    game->velocity_x, game->velocity_y);
	shell_print(shell, "main stack high-water: %u/%u bytes",
		    snapshot.runtime.main_stack_used_bytes, snapshot.runtime.main_stack_size_bytes);
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
	SHELL_CMD_ARG(stats, NULL, "Show framebuffer, timing, and game-loop metrics.",
		      cmd_display_stats, 1, 0),
	SHELL_CMD_ARG(sync, NULL,
		      SHELL_HELP("Show or control LCD tearing-effect synchronization.", "[on|off]"),
		      cmd_display_sync, 1, 1),
	SHELL_SUBCMD_SET_END);

SHELL_STATIC_SUBCMD_SET_CREATE(reboot_commands,
			       SHELL_CMD_ARG(bootloader, NULL,
					     "Reboot into the RP2040 ROM USB bootloader.",
					     cmd_reboot_bootloader, 1, 0),
			       SHELL_SUBCMD_SET_END);

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
	SHELL_CMD(display, &display_commands, "Display diagnostic commands.", NULL),
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
