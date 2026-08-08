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
#define PICOSYSTEM_DISPLAY_SPI_HZ DT_PROP(PICOSYSTEM_DISPLAY_NODE, mipi_max_frequency)
#define BACKLIGHT_DUTY_PERCENT    25U
#define CORNER_MARKER_SIZE        48U
#define ARROW_CENTER_X            (PICOSYSTEM_DISPLAY_WIDTH / 2U)
#define ARROW_TIP_Y               64U
#define ARROW_HEAD_BOTTOM_Y       112U
#define ARROW_SHAFT_HALF_WIDTH    8U
#define ARROW_SHAFT_BOTTOM_Y      184U
#define DISPLAY_CHUNK_HEIGHT      8U
#define FRAME_BYTES               (PICOSYSTEM_DISPLAY_WIDTH * PICOSYSTEM_DISPLAY_HEIGHT * 2U)

static const struct device *const display = DEVICE_DT_GET(PICOSYSTEM_DISPLAY_NODE);
static const struct pwm_dt_spec backlight = PWM_DT_SPEC_GET(PICOSYSTEM_BACKLIGHT_NODE);

enum rgb565_color {
	RGB565_BLACK = 0x0000U,
	RGB565_BLUE = 0x001fU,
	RGB565_DARK_GREY = 0x1082U,
	RGB565_GREEN = 0x07e0U,
	RGB565_RED = 0xf800U,
	RGB565_WHITE = 0xffffU,
	RGB565_YELLOW = 0xffe0U,
};

static uint16_t display_chunk[DISPLAY_CHUNK_HEIGHT][PICOSYSTEM_DISPLAY_WIDTH];

BUILD_ASSERT(PICOSYSTEM_DISPLAY_WIDTH == 240U);
BUILD_ASSERT(PICOSYSTEM_DISPLAY_HEIGHT == 240U);
BUILD_ASSERT(CORNER_MARKER_SIZE < (PICOSYSTEM_DISPLAY_WIDTH / 2U));
BUILD_ASSERT(ARROW_HEAD_BOTTOM_Y < ARROW_SHAFT_BOTTOM_Y);
BUILD_ASSERT(ARROW_SHAFT_BOTTOM_Y < PICOSYSTEM_DISPLAY_HEIGHT);
BUILD_ASSERT((PICOSYSTEM_DISPLAY_HEIGHT % DISPLAY_CHUNK_HEIGHT) == 0U);

static int set_backlight_percent(uint32_t percent)
{
	if (percent > 100U) {
		return -EINVAL;
	}

	const uint32_t pulse = (uint32_t)(((uint64_t)backlight.period * percent) / 100U);

	return pwm_set_pulse_dt(&backlight, pulse);
}

static uint16_t orientation_pattern_pixel(uint16_t x, uint16_t y)
{
	if ((x < CORNER_MARKER_SIZE) && (y < CORNER_MARKER_SIZE)) {
		return RGB565_RED;
	}

	if ((x >= (PICOSYSTEM_DISPLAY_WIDTH - CORNER_MARKER_SIZE)) && (y < CORNER_MARKER_SIZE)) {
		return RGB565_GREEN;
	}

	if ((x >= (PICOSYSTEM_DISPLAY_WIDTH - CORNER_MARKER_SIZE)) &&
	    (y >= (PICOSYSTEM_DISPLAY_HEIGHT - CORNER_MARKER_SIZE))) {
		return RGB565_BLUE;
	}

	if ((x < CORNER_MARKER_SIZE) && (y >= (PICOSYSTEM_DISPLAY_HEIGHT - CORNER_MARKER_SIZE))) {
		return RGB565_WHITE;
	}

	if ((y >= ARROW_TIP_Y) && (y < ARROW_HEAD_BOTTOM_Y)) {
		const uint16_t arrow_half_width = y - ARROW_TIP_Y;
		if ((x >= (ARROW_CENTER_X - arrow_half_width)) &&
		    (x <= (ARROW_CENTER_X + arrow_half_width))) {
			return RGB565_YELLOW;
		}
	}

	if ((y >= ARROW_HEAD_BOTTOM_Y) && (y < ARROW_SHAFT_BOTTOM_Y) &&
	    (x >= (ARROW_CENTER_X - ARROW_SHAFT_HALF_WIDTH)) &&
	    (x < (ARROW_CENTER_X + ARROW_SHAFT_HALF_WIDTH))) {
		return RGB565_YELLOW;
	}

	return RGB565_DARK_GREY;
}

static void prepare_orientation_chunk(uint16_t start_y)
{
	for (size_t row = 0; row < ARRAY_SIZE(display_chunk); ++row) {
		for (size_t x = 0; x < ARRAY_SIZE(display_chunk[row]); ++x) {
			display_chunk[row][x] =
				sys_cpu_to_be16(orientation_pattern_pixel(x, start_y + row));
		}
	}
}

static int write_orientation_pattern(void)
{
	struct display_buffer_descriptor descriptor = {
		.buf_size = sizeof(display_chunk),
		.width = ARRAY_SIZE(display_chunk[0]),
		.height = ARRAY_SIZE(display_chunk),
		.pitch = ARRAY_SIZE(display_chunk[0]),
		.frame_incomplete = true,
	};

	for (uint16_t y = 0; y < PICOSYSTEM_DISPLAY_HEIGHT; y += DISPLAY_CHUNK_HEIGHT) {
		prepare_orientation_chunk(y);
		descriptor.frame_incomplete =
			((y + DISPLAY_CHUNK_HEIGHT) < PICOSYSTEM_DISPLAY_HEIGHT);

		const int err = display_write(display, 0U, y, &descriptor, display_chunk);
		if (err != 0) {
			LOG_ERR("Display write failed at row %u (%d)", y, err);
			return err;
		}
	}

	return 0;
}

int picosystem_display_test_run(struct picosystem_display_test_result *result)
{
	if (result == NULL) {
		return -EINVAL;
	}

	*result = (struct picosystem_display_test_result){0};

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

	const uint32_t start_cycles = k_cycle_get_32();

	err = write_orientation_pattern();
	if (err != 0) {
		return err;
	}

	const uint32_t elapsed_cycles = k_cycle_get_32() - start_cycles;
	result->frame_time_us = MAX(k_cyc_to_us_floor32(elapsed_cycles), 1U);
	result->throughput_kib_per_second = (uint32_t)(((uint64_t)FRAME_BYTES * USEC_PER_SEC) /
						       ((uint64_t)result->frame_time_us * 1024U));

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

	LOG_INF("Orientation frame: %u us, %u KiB/s, SPI %u Hz, backlight %u%%",
		result->frame_time_us, result->throughput_kib_per_second, PICOSYSTEM_DISPLAY_SPI_HZ,
		BACKLIGHT_DUTY_PERCENT);
	return 0;
}
