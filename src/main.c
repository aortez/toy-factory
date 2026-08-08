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

#include "battery.h"
#include "diagnostic_shell.h"
#include "display_test.h"
#include "piezo.h"
#include "power_status.h"

LOG_MODULE_REGISTER(picosystem_playground, LOG_LEVEL_INF);

#define DISPLAY_MOVE_REPEAT_MS  100
#define PIEZO_TEST_FREQUENCY_HZ 440U
#define PIEZO_TEST_DURATION_MS  180U
#define STATUS_LOG_INTERVAL_MS  30000

#define DPAD_BUTTON_MASK                                                                           \
	(BIT(PICOSYSTEM_BUTTON_UP) | BIT(PICOSYSTEM_BUTTON_DOWN) | BIT(PICOSYSTEM_BUTTON_LEFT) |   \
	 BIT(PICOSYSTEM_BUTTON_RIGHT))

struct named_gpio {
	const char *name;
	struct gpio_dt_spec gpio;
};

static const struct named_gpio buttons[PICOSYSTEM_BUTTON_COUNT] = {
	[PICOSYSTEM_BUTTON_UP] = {.name = "UP",
				  .gpio = GPIO_DT_SPEC_GET(DT_NODELABEL(button_up), gpios)},
	[PICOSYSTEM_BUTTON_DOWN] =
		{
			.name = "DOWN",
			.gpio = GPIO_DT_SPEC_GET(DT_NODELABEL(button_down), gpios),
		},
	[PICOSYSTEM_BUTTON_LEFT] =
		{
			.name = "LEFT",
			.gpio = GPIO_DT_SPEC_GET(DT_NODELABEL(button_left), gpios),
		},
	[PICOSYSTEM_BUTTON_RIGHT] =
		{
			.name = "RIGHT",
			.gpio = GPIO_DT_SPEC_GET(DT_NODELABEL(button_right), gpios),
		},
	[PICOSYSTEM_BUTTON_A] = {.name = "A",
				 .gpio = GPIO_DT_SPEC_GET(DT_NODELABEL(button_a), gpios)},
	[PICOSYSTEM_BUTTON_B] = {.name = "B",
				 .gpio = GPIO_DT_SPEC_GET(DT_NODELABEL(button_b), gpios)},
	[PICOSYSTEM_BUTTON_X] = {.name = "X",
				 .gpio = GPIO_DT_SPEC_GET(DT_NODELABEL(button_x), gpios)},
	[PICOSYSTEM_BUTTON_Y] = {.name = "Y",
				 .gpio = GPIO_DT_SPEC_GET(DT_NODELABEL(button_y), gpios)},
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

static int read_and_log_battery(struct picosystem_battery_sample *sample)
{
	const int err = picosystem_battery_read(sample);
	if (err != 0) {
		LOG_ERR("Battery voltage read failed (%d)", err);
		return err;
	}

	if (!sample->plausible) {
		LOG_WRN("Battery voltage outside plausible LiPo range: %u mV (raw mean %u)",
			sample->millivolts, sample->raw_average);
		return 0;
	}

	LOG_INF("battery: %u mV (raw mean %u)", sample->millivolts, sample->raw_average);
	return 0;
}

static void log_power_status(const struct picosystem_power_status *status)
{
	const char *const state_name = picosystem_power_state_name(status->state);
	const char *const usb_name = status->usb_power_present ? "present" : "absent";
	const char *const charge_name = status->charging ? "active" : "inactive";

	if (status->state == PICOSYSTEM_POWER_STATE_CHARGE_WITHOUT_USB) {
		LOG_WRN("power: %s (usb=%s, charge=%s)", state_name, usb_name, charge_name);
		return;
	}

	LOG_INF("power: %s (usb=%s, charge=%s)", state_name, usb_name, charge_name);
}

static bool power_status_equal(const struct picosystem_power_status *left,
			       const struct picosystem_power_status *right)
{
	return (left->usb_power_present == right->usb_power_present) &&
	       (left->charging == right->charging);
}

static void apply_led_mode(enum picosystem_led_mode mode, bool *red, bool *green, bool *blue)
{
	switch (mode) {
	case PICOSYSTEM_LED_MODE_OFF:
		*red = false;
		*green = false;
		*blue = false;
		break;
	case PICOSYSTEM_LED_MODE_RED:
		*red = true;
		*green = false;
		*blue = false;
		break;
	case PICOSYSTEM_LED_MODE_GREEN:
		*red = false;
		*green = true;
		*blue = false;
		break;
	case PICOSYSTEM_LED_MODE_BLUE:
		*red = false;
		*green = false;
		*blue = true;
		break;
	case PICOSYSTEM_LED_MODE_WHITE:
		*red = true;
		*green = true;
		*blue = true;
		break;
	case PICOSYSTEM_LED_MODE_AUTO:
	default:
		break;
	}
}

static int publish_diagnostic_snapshot(const struct picosystem_battery_sample *battery,
				       int64_t battery_sample_uptime_ms,
				       const struct picosystem_power_status *power,
				       const struct picosystem_display_test_state *display,
				       uint32_t buttons_state)
{
	const struct picosystem_diagnostic_snapshot snapshot = {
		.battery = *battery,
		.power = *power,
		.display = *display,
		.battery_sample_uptime_ms = battery_sample_uptime_ms,
		.buttons = buttons_state,
	};

	return picosystem_diagnostic_shell_publish(&snapshot);
}

int main(void)
{
	struct picosystem_battery_sample battery_sample;
	struct picosystem_display_test_state display_state;
	struct picosystem_power_status power_status;

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

	err = picosystem_piezo_init();
	if (err != 0) {
		LOG_ERR("Piezo initialization failed (%d)", err);
		return err;
	}

	err = picosystem_battery_init();
	if (err != 0) {
		LOG_ERR("Battery ADC initialization failed (%d)", err);
		return err;
	}

	err = picosystem_power_status_init();
	if (err != 0) {
		LOG_ERR("Power-status initialization failed (%d)", err);
		return err;
	}

	err = run_led_self_test();
	if (err != 0) {
		LOG_ERR("RGB LED self-test failed (%d)", err);
		return err;
	}

	err = picosystem_display_test_run(&display_state);
	if (err != 0) {
		LOG_ERR("Display smoke test failed (%d)", err);
		const int led_err = set_rgb(true, false, false);
		if (led_err != 0) {
			LOG_ERR("Failed to indicate display error on RGB LED (%d)", led_err);
		}
		return err;
	}

	err = read_and_log_battery(&battery_sample);
	if (err != 0) {
		return err;
	}
	int64_t battery_sample_uptime_ms = k_uptime_get();

	err = picosystem_power_status_read(&power_status);
	if (err != 0) {
		LOG_ERR("Power-status read failed (%d)", err);
		return err;
	}
	log_power_status(&power_status);

	LOG_INF("PicoSystem GPIO bring-up ready");
	LOG_INF("D-pad moves the marker; A forces a full redraw for comparison");
	LOG_INF("B plays a short 440 Hz piezo tone");
	LOG_INF("A=red, B=green, X=blue, Y=white on the RGB LED");
	LOG_INF("GP2 remains an input; the automatic red charge indicator is enabled");
	LOG_INF("USB diagnostics ready; enter 'picosystem -h'");

	uint32_t previous_state = 0U;
	err = publish_diagnostic_snapshot(&battery_sample, battery_sample_uptime_ms, &power_status,
					  &display_state, previous_state);
	if (err != 0) {
		LOG_ERR("Failed to publish initial diagnostic snapshot (%d)", err);
		return err;
	}

	int64_t next_status_time = k_uptime_get() + STATUS_LOG_INTERVAL_MS;
	int64_t next_move_time = 0;

	while (true) {
		uint32_t state;
		struct picosystem_power_status next_power_status;

		err = read_buttons(&state);
		if (err != 0) {
			return err;
		}

		err = picosystem_power_status_read(&next_power_status);
		if (err != 0) {
			LOG_ERR("Power-status read failed (%d)", err);
			return err;
		}

		if (!power_status_equal(&power_status, &next_power_status)) {
			log_power_status(&next_power_status);
		}
		power_status = next_power_status;

		const int64_t now = k_uptime_get();
		const uint32_t pressed = state & ~previous_state;
		const bool dpad_changed = ((state ^ previous_state) & DPAD_BUTTON_MASK) != 0U;
		const uint32_t dpad_state = state & DPAD_BUTTON_MASK;

		log_button_changes(previous_state, state);

		if (dpad_state == 0U) {
			next_move_time = now;
		} else if (dpad_changed || (now >= next_move_time)) {
			int8_t horizontal = 0;
			int8_t vertical = 0;

			if ((state & BIT(PICOSYSTEM_BUTTON_LEFT)) != 0U) {
				--horizontal;
			}
			if ((state & BIT(PICOSYSTEM_BUTTON_RIGHT)) != 0U) {
				++horizontal;
			}
			if ((state & BIT(PICOSYSTEM_BUTTON_UP)) != 0U) {
				--vertical;
			}
			if ((state & BIT(PICOSYSTEM_BUTTON_DOWN)) != 0U) {
				++vertical;
			}

			err = picosystem_display_test_move(&display_state, horizontal, vertical);
			if (err != 0) {
				LOG_ERR("Partial display update failed (%d)", err);
				return err;
			}

			next_move_time = now + DISPLAY_MOVE_REPEAT_MS;
		}

		if ((pressed & BIT(PICOSYSTEM_BUTTON_A)) != 0U) {
			err = picosystem_display_test_redraw(&display_state);
			if (err != 0) {
				LOG_ERR("Full display redraw failed (%d)", err);
				return err;
			}
		}

		if ((pressed & BIT(PICOSYSTEM_BUTTON_B)) != 0U) {
			err = picosystem_piezo_play(PIEZO_TEST_FREQUENCY_HZ,
						    PIEZO_TEST_DURATION_MS);
			if (err != 0) {
				LOG_ERR("Piezo tone test failed (%d)", err);
				return err;
			}
		}

		struct picosystem_tone_request tone_request;
		err = picosystem_diagnostic_shell_take_tone(&tone_request);
		if (err == 0) {
			err = picosystem_piezo_play(tone_request.frequency_hz,
						    tone_request.duration_ms);
			if (err != 0) {
				LOG_ERR("Shell piezo tone failed (%d)", err);
				return err;
			}
		} else if (err != -ENOMSG) {
			LOG_ERR("Failed to take shell tone request (%d)", err);
			return err;
		}

		previous_state = state;

		const bool y_pressed = (state & BIT(PICOSYSTEM_BUTTON_Y)) != 0U;
		bool red = y_pressed || ((state & BIT(PICOSYSTEM_BUTTON_A)) != 0U);
		bool green = y_pressed || ((state & BIT(PICOSYSTEM_BUTTON_B)) != 0U);
		bool blue = y_pressed || ((state & BIT(PICOSYSTEM_BUTTON_X)) != 0U);

		if ((state & (BIT(PICOSYSTEM_BUTTON_A) | BIT(PICOSYSTEM_BUTTON_B) |
			      BIT(PICOSYSTEM_BUTTON_X) | BIT(PICOSYSTEM_BUTTON_Y))) == 0U) {
			blue = ((k_uptime_get() / 500) & 1) != 0;
		}

		apply_led_mode(picosystem_diagnostic_shell_led_mode(), &red, &green, &blue);

		err = set_rgb(red, green, blue);
		if (err != 0) {
			LOG_ERR("Failed to update RGB LED (%d)", err);
			return err;
		}

		if (now >= next_status_time) {
			err = read_and_log_battery(&battery_sample);
			if (err != 0) {
				return err;
			}
			battery_sample_uptime_ms = k_uptime_get();

			LOG_INF("alive: uptime=%lld ms, buttons=0x%02x, power=%s, full=%u us, "
				"partial=%u us/%ux%u (#%u)",
				now, state, picosystem_power_state_name(power_status.state),
				display_state.full_frame_time_us,
				display_state.last_partial_time_us,
				display_state.last_partial_width, display_state.last_partial_height,
				display_state.partial_update_count);
			next_status_time = now + STATUS_LOG_INTERVAL_MS;
		}

		err = publish_diagnostic_snapshot(&battery_sample, battery_sample_uptime_ms,
						  &power_status, &display_state, state);
		if (err != 0) {
			LOG_ERR("Failed to publish diagnostic snapshot (%d)", err);
			return err;
		}

		k_msleep(20);
	}

	return 0;
}
