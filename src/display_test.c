/*
 * Copyright (c) 2026 PicoSystem Playground contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stdint.h>

#include <zephyr/device.h>
#include <zephyr/drivers/display.h>
#include <zephyr/drivers/pwm.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/sys/util.h>

#include "display_test.h"

LOG_MODULE_REGISTER(picosystem_display_test, LOG_LEVEL_INF);

#define PICOSYSTEM_DISPLAY_NODE   DT_CHOSEN(zephyr_display)
#define PICOSYSTEM_BACKLIGHT_NODE DT_NODELABEL(lcd_backlight)

#define PICOSYSTEM_DISPLAY_WIDTH  DT_PROP(PICOSYSTEM_DISPLAY_NODE, width)
#define PICOSYSTEM_DISPLAY_HEIGHT DT_PROP(PICOSYSTEM_DISPLAY_NODE, height)
#define BACKLIGHT_DUTY_PERCENT    25U

static const struct device *const display = DEVICE_DT_GET(PICOSYSTEM_DISPLAY_NODE);
static const struct pwm_dt_spec backlight = PWM_DT_SPEC_GET(PICOSYSTEM_BACKLIGHT_NODE);

static const uint16_t color_bars_rgb565[] = {
	0xf800U, 0x07e0U, 0x001fU, 0xffffU, 0x0000U,
};

static uint16_t color_bar_line[PICOSYSTEM_DISPLAY_WIDTH];

BUILD_ASSERT(PICOSYSTEM_DISPLAY_WIDTH == 240U);
BUILD_ASSERT(PICOSYSTEM_DISPLAY_HEIGHT == 240U);
BUILD_ASSERT((PICOSYSTEM_DISPLAY_WIDTH % ARRAY_SIZE(color_bars_rgb565)) == 0U);

static int set_backlight_percent(uint32_t percent)
{
	if (percent > 100U) {
		return -EINVAL;
	}

	const uint32_t pulse = (uint32_t)(((uint64_t)backlight.period * percent) / 100U);

	return pwm_set_pulse_dt(&backlight, pulse);
}

static void prepare_color_bar_line(void)
{
	for (size_t x = 0; x < ARRAY_SIZE(color_bar_line); ++x) {
		const size_t color_index =
			(x * ARRAY_SIZE(color_bars_rgb565)) / ARRAY_SIZE(color_bar_line);
		color_bar_line[x] = sys_cpu_to_be16(color_bars_rgb565[color_index]);
	}
}

static int write_color_bars(void)
{
	struct display_buffer_descriptor descriptor = {
		.buf_size = sizeof(color_bar_line),
		.width = ARRAY_SIZE(color_bar_line),
		.height = 1U,
		.pitch = ARRAY_SIZE(color_bar_line),
		.frame_incomplete = true,
	};

	for (uint16_t y = 0; y < PICOSYSTEM_DISPLAY_HEIGHT; ++y) {
		descriptor.frame_incomplete = ((y + 1U) < PICOSYSTEM_DISPLAY_HEIGHT);

		const int err = display_write(display, 0U, y, &descriptor, color_bar_line);
		if (err != 0) {
			LOG_ERR("Display write failed at row %u (%d)", y, err);
			return err;
		}
	}

	return 0;
}

int picosystem_display_test_run(void)
{
	if (!pwm_is_ready_dt(&backlight)) {
		LOG_ERR("Backlight PWM controller is not ready");
		return -ENODEV;
	}

	int err = set_backlight_percent(0U);
	if (err != 0) {
		LOG_ERR("Failed to force the backlight off (%d)", err);
		return err;
	}

	if (!device_is_ready(display)) {
		LOG_ERR("Display device is not ready");
		return -ENODEV;
	}

	struct display_capabilities capabilities;
	display_get_capabilities(display, &capabilities);

	if ((capabilities.x_resolution != PICOSYSTEM_DISPLAY_WIDTH) ||
	    (capabilities.y_resolution != PICOSYSTEM_DISPLAY_HEIGHT)) {
		LOG_ERR("Unexpected display resolution: %ux%u", capabilities.x_resolution,
			capabilities.y_resolution);
		return -ENOTSUP;
	}

	if (capabilities.current_pixel_format != PIXEL_FORMAT_RGB_565X) {
		LOG_ERR("Unexpected display pixel format: 0x%x", capabilities.current_pixel_format);
		return -ENOTSUP;
	}

	err = display_set_pixel_format(display, PIXEL_FORMAT_RGB_565X);
	if (err != 0) {
		LOG_ERR("Failed to select RGB565X pixel format (%d)", err);
		return err;
	}

	prepare_color_bar_line();
	const int64_t start_time = k_uptime_get();

	err = write_color_bars();
	if (err != 0) {
		return err;
	}

	err = display_blanking_off(display);
	if (err != 0) {
		LOG_ERR("Failed to enable display output (%d)", err);
		return err;
	}

	err = set_backlight_percent(BACKLIGHT_DUTY_PERCENT);
	if (err != 0) {
		LOG_ERR("Failed to enable the backlight (%d)", err);
		return err;
	}

	LOG_INF("Display color bars ready in %lld ms at %u%% backlight",
		k_uptime_get() - start_time, BACKLIGHT_DUTY_PERCENT);
	return 0;
}
