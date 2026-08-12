/*
 * Copyright (c) 2026 PicoSystem Playground contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_DIAGNOSTIC_SHELL_H
#define PICOSYSTEM_DIAGNOSTIC_SHELL_H

#include <stdbool.h>
#include <stdint.h>

#include "battery.h"
#include "game_demo.h"
#include "power_status.h"

enum picosystem_button_index {
	PICOSYSTEM_BUTTON_UP,
	PICOSYSTEM_BUTTON_DOWN,
	PICOSYSTEM_BUTTON_LEFT,
	PICOSYSTEM_BUTTON_RIGHT,
	PICOSYSTEM_BUTTON_A,
	PICOSYSTEM_BUTTON_B,
	PICOSYSTEM_BUTTON_X,
	PICOSYSTEM_BUTTON_Y,
	PICOSYSTEM_BUTTON_COUNT,
};

enum picosystem_led_mode {
	PICOSYSTEM_LED_MODE_AUTO,
	PICOSYSTEM_LED_MODE_OFF,
	PICOSYSTEM_LED_MODE_RED,
	PICOSYSTEM_LED_MODE_GREEN,
	PICOSYSTEM_LED_MODE_BLUE,
	PICOSYSTEM_LED_MODE_WHITE,
};

struct picosystem_runtime_metrics {
	uint32_t main_stack_size_bytes;
	uint32_t main_stack_used_bytes;
};

struct picosystem_diagnostic_snapshot {
	struct picosystem_battery_sample battery;
	struct picosystem_power_status power;
	struct picosystem_game_demo_state game;
	struct picosystem_runtime_metrics runtime;
	int64_t battery_sample_uptime_ms;
	uint32_t buttons;
};

struct picosystem_tone_request {
	uint32_t frequency_hz;
	uint32_t duration_ms;
};

/* Publish a coherent hardware snapshot for shell readers. */
int picosystem_diagnostic_shell_publish(const struct picosystem_diagnostic_snapshot *snapshot);

/* Return the software RGB mode selected through the shell. */
enum picosystem_led_mode picosystem_diagnostic_shell_led_mode(void);

/* Take the next shell tone request without waiting. */
int picosystem_diagnostic_shell_take_tone(struct picosystem_tone_request *request);

#endif /* PICOSYSTEM_DIAGNOSTIC_SHELL_H */
