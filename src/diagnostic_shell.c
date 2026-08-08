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

	shell_print(shell, "uptime: %lld ms", now_ms);
	print_buttons(shell, snapshot.buttons);
	shell_print(shell, "power: %s (usb=%s, charge=%s)",
		    picosystem_power_state_name(snapshot.power.state), usb_name, charge_name);
	shell_print(shell, "battery: %u mV (raw=%u, plausible=%s, age=%lld ms)",
		    snapshot.battery.millivolts, snapshot.battery.raw_average,
		    snapshot.battery.plausible ? "yes" : "no", battery_age_ms);
	shell_print(shell, "display: full=%u us/%u KiB/s, sprite=(%u,%u)",
		    snapshot.display.full_frame_time_us,
		    snapshot.display.full_frame_throughput_kib_per_second,
		    snapshot.display.sprite_x, snapshot.display.sprite_y);
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

	shell_print(shell, "full: %u us, %u KiB/s", snapshot.display.full_frame_time_us,
		    snapshot.display.full_frame_throughput_kib_per_second);
	if (snapshot.display.partial_update_count == 0U) {
		shell_print(shell, "partial: none");
	} else {
		shell_print(
			shell, "partial #%u: %ux%u, %u us, %u KiB/s",
			snapshot.display.partial_update_count, snapshot.display.last_partial_width,
			snapshot.display.last_partial_height, snapshot.display.last_partial_time_us,
			snapshot.display.last_partial_throughput_kib_per_second);
	}
	shell_print(shell, "sprite: (%u,%u)", snapshot.display.sprite_x, snapshot.display.sprite_y);
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

SHELL_STATIC_SUBCMD_SET_CREATE(display_commands,
			       SHELL_CMD_ARG(stats, NULL,
					     "Show display timing and sprite position.",
					     cmd_display_stats, 1, 0),
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
