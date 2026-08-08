/*
 * Copyright (c) 2026 PicoSystem Playground contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stdbool.h>
#include <stdint.h>

#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/util.h>

#include "display_test.h"

LOG_MODULE_REGISTER(picosystem_playground, LOG_LEVEL_INF);

enum button_index {
	BUTTON_UP,
	BUTTON_DOWN,
	BUTTON_LEFT,
	BUTTON_RIGHT,
	BUTTON_A,
	BUTTON_B,
	BUTTON_X,
	BUTTON_Y,
	BUTTON_COUNT,
};

struct named_gpio {
	const char *name;
	struct gpio_dt_spec gpio;
};

static const struct named_gpio buttons[BUTTON_COUNT] = {
	[BUTTON_UP] = {.name = "UP", .gpio = GPIO_DT_SPEC_GET(DT_NODELABEL(button_up), gpios)},
	[BUTTON_DOWN] =
		{
			.name = "DOWN",
			.gpio = GPIO_DT_SPEC_GET(DT_NODELABEL(button_down), gpios),
		},
	[BUTTON_LEFT] =
		{
			.name = "LEFT",
			.gpio = GPIO_DT_SPEC_GET(DT_NODELABEL(button_left), gpios),
		},
	[BUTTON_RIGHT] =
		{
			.name = "RIGHT",
			.gpio = GPIO_DT_SPEC_GET(DT_NODELABEL(button_right), gpios),
		},
	[BUTTON_A] = {.name = "A", .gpio = GPIO_DT_SPEC_GET(DT_NODELABEL(button_a), gpios)},
	[BUTTON_B] = {.name = "B", .gpio = GPIO_DT_SPEC_GET(DT_NODELABEL(button_b), gpios)},
	[BUTTON_X] = {.name = "X", .gpio = GPIO_DT_SPEC_GET(DT_NODELABEL(button_x), gpios)},
	[BUTTON_Y] = {.name = "Y", .gpio = GPIO_DT_SPEC_GET(DT_NODELABEL(button_y), gpios)},
};

static const struct gpio_dt_spec led_red = GPIO_DT_SPEC_GET(DT_NODELABEL(led_red), gpios);
static const struct gpio_dt_spec led_green = GPIO_DT_SPEC_GET(DT_NODELABEL(led_green), gpios);
static const struct gpio_dt_spec led_blue = GPIO_DT_SPEC_GET(DT_NODELABEL(led_blue), gpios);

static int configure_input(const struct named_gpio *input)
{
	if (!gpio_is_ready_dt(&input->gpio)) {
		LOG_ERR("%s GPIO controller is not ready", input->name);
		return -ENODEV;
	}

	const int err = gpio_pin_configure_dt(&input->gpio, GPIO_INPUT);
	if (err != 0) {
		LOG_ERR("Failed to configure %s button (%d)", input->name, err);
		return err;
	}

	return 0;
}

static int configure_output(const char *name, const struct gpio_dt_spec *output)
{
	if (!gpio_is_ready_dt(output)) {
		LOG_ERR("%s GPIO controller is not ready", name);
		return -ENODEV;
	}

	const int err = gpio_pin_configure_dt(output, GPIO_OUTPUT_INACTIVE);
	if (err != 0) {
		LOG_ERR("Failed to configure %s output (%d)", name, err);
		return err;
	}

	return 0;
}

static int set_rgb(bool red, bool green, bool blue)
{
	int err = gpio_pin_set_dt(&led_red, red);
	if (err != 0) {
		return err;
	}

	err = gpio_pin_set_dt(&led_green, green);
	if (err != 0) {
		return err;
	}

	return gpio_pin_set_dt(&led_blue, blue);
}

static int run_led_self_test(void)
{
	static const bool colors[][3] = {
		{true, false, false},
		{false, true, false},
		{false, false, true},
		{false, false, false},
	};

	for (size_t i = 0; i < ARRAY_SIZE(colors); ++i) {
		const int err = set_rgb(colors[i][0], colors[i][1], colors[i][2]);
		if (err != 0) {
			return err;
		}
		k_msleep(200);
	}

	return 0;
}

static int read_buttons(uint32_t *state)
{
	uint32_t next_state = 0U;

	for (size_t i = 0; i < ARRAY_SIZE(buttons); ++i) {
		const int value = gpio_pin_get_dt(&buttons[i].gpio);
		if (value < 0) {
			LOG_ERR("Failed to read %s button (%d)", buttons[i].name, value);
			return value;
		}

		if (value != 0) {
			next_state |= BIT(i);
		}
	}

	*state = next_state;
	return 0;
}

static void log_button_changes(uint32_t previous_state, uint32_t state)
{
	const uint32_t changes = previous_state ^ state;

	for (size_t i = 0; i < ARRAY_SIZE(buttons); ++i) {
		if ((changes & BIT(i)) != 0U) {
			const bool pressed = (state & BIT(i)) != 0U;
			LOG_INF("%s %s", buttons[i].name, pressed ? "pressed" : "released");
		}
	}
}

int main(void)
{
	struct picosystem_display_test_result display_result;

	for (size_t i = 0; i < ARRAY_SIZE(buttons); ++i) {
		const int err = configure_input(&buttons[i]);
		if (err != 0) {
			return err;
		}
	}

	int err = configure_output("red LED", &led_red);
	if (err != 0) {
		return err;
	}

	err = configure_output("green LED", &led_green);
	if (err != 0) {
		return err;
	}

	err = configure_output("blue LED", &led_blue);
	if (err != 0) {
		return err;
	}

	err = run_led_self_test();
	if (err != 0) {
		LOG_ERR("RGB LED self-test failed (%d)", err);
		return err;
	}

	err = picosystem_display_test_run(&display_result);
	if (err != 0) {
		LOG_ERR("Display smoke test failed (%d)", err);
		const int led_err = set_rgb(true, false, false);
		if (led_err != 0) {
			LOG_ERR("Failed to indicate display error on RGB LED (%d)", led_err);
		}
		return err;
	}

	LOG_INF("PicoSystem GPIO bring-up ready");
	LOG_INF("A=red, B=green, X=blue, Y=white; D-pad events are logged");

	uint32_t previous_state = 0U;
	int64_t next_status_time = k_uptime_get() + 5000;

	while (true) {
		uint32_t state;

		err = read_buttons(&state);
		if (err != 0) {
			return err;
		}

		log_button_changes(previous_state, state);
		previous_state = state;

		const bool y_pressed = (state & BIT(BUTTON_Y)) != 0U;
		const bool red = y_pressed || ((state & BIT(BUTTON_A)) != 0U);
		const bool green = y_pressed || ((state & BIT(BUTTON_B)) != 0U);
		bool blue = y_pressed || ((state & BIT(BUTTON_X)) != 0U);

		if ((state & (BIT(BUTTON_A) | BIT(BUTTON_B) | BIT(BUTTON_X) | BIT(BUTTON_Y))) ==
		    0U) {
			blue = ((k_uptime_get() / 500) & 1) != 0;
		}

		err = set_rgb(red, green, blue);
		if (err != 0) {
			LOG_ERR("Failed to update RGB LED (%d)", err);
			return err;
		}

		const int64_t now = k_uptime_get();
		if (now >= next_status_time) {
			LOG_INF("alive: uptime=%lld ms, buttons=0x%02x, display=%u us", now, state,
				display_result.frame_time_us);
			next_status_time = now + 5000;
		}

		k_msleep(20);
	}

	return 0;
}
