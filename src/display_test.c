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
#define DISPLAY_BUFFER_ROWS       8U
#define DISPLAY_BUFFER_PIXELS     (PICOSYSTEM_DISPLAY_WIDTH * DISPLAY_BUFFER_ROWS)
#define FRAME_BYTES               (PICOSYSTEM_DISPLAY_WIDTH * PICOSYSTEM_DISPLAY_HEIGHT * 2U)
#define SPRITE_SIZE               24U
#define SPRITE_BORDER_WIDTH       2U
#define SPRITE_MOVE_STEP          8U
#define SPRITE_START_X            ((PICOSYSTEM_DISPLAY_WIDTH - SPRITE_SIZE) / 2U)
#define SPRITE_START_Y            ((PICOSYSTEM_DISPLAY_HEIGHT - SPRITE_SIZE) / 2U)
#define PARTIAL_UPDATE_MAX_WIDTH  (SPRITE_SIZE + SPRITE_MOVE_STEP)
#define PARTIAL_UPDATE_MAX_HEIGHT (SPRITE_SIZE + SPRITE_MOVE_STEP)

static const struct device *const display = DEVICE_DT_GET(PICOSYSTEM_DISPLAY_NODE);
static const struct pwm_dt_spec backlight = PWM_DT_SPEC_GET(PICOSYSTEM_BACKLIGHT_NODE);

enum rgb565_color {
	RGB565_BLUE = 0x001fU,
	RGB565_DARK_GREY = 0x1082U,
	RGB565_GREEN = 0x07e0U,
	RGB565_MAGENTA = 0xf81fU,
	RGB565_RED = 0xf800U,
	RGB565_WHITE = 0xffffU,
	RGB565_YELLOW = 0xffe0U,
};

struct display_region {
	uint16_t x;
	uint16_t y;
	uint16_t width;
	uint16_t height;
};

static uint16_t display_buffer[DISPLAY_BUFFER_PIXELS];

BUILD_ASSERT(PICOSYSTEM_DISPLAY_WIDTH == 240U);
BUILD_ASSERT(PICOSYSTEM_DISPLAY_HEIGHT == 240U);
BUILD_ASSERT(CORNER_MARKER_SIZE < (PICOSYSTEM_DISPLAY_WIDTH / 2U));
BUILD_ASSERT(ARROW_HEAD_BOTTOM_Y < ARROW_SHAFT_BOTTOM_Y);
BUILD_ASSERT(ARROW_SHAFT_BOTTOM_Y < PICOSYSTEM_DISPLAY_HEIGHT);
BUILD_ASSERT((PICOSYSTEM_DISPLAY_HEIGHT % DISPLAY_BUFFER_ROWS) == 0U);
BUILD_ASSERT(SPRITE_SIZE <= PICOSYSTEM_DISPLAY_WIDTH);
BUILD_ASSERT(SPRITE_SIZE <= PICOSYSTEM_DISPLAY_HEIGHT);
BUILD_ASSERT(SPRITE_BORDER_WIDTH < (SPRITE_SIZE / 2U));
BUILD_ASSERT((PARTIAL_UPDATE_MAX_WIDTH * PARTIAL_UPDATE_MAX_HEIGHT) <= ARRAY_SIZE(display_buffer));

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

static uint16_t display_pattern_pixel(uint16_t x, uint16_t y, uint16_t sprite_x, uint16_t sprite_y)
{
	if ((x >= sprite_x) && (x < (sprite_x + SPRITE_SIZE)) && (y >= sprite_y) &&
	    (y < (sprite_y + SPRITE_SIZE))) {
		const uint16_t local_x = x - sprite_x;
		const uint16_t local_y = y - sprite_y;

		if ((local_x < SPRITE_BORDER_WIDTH) ||
		    (local_x >= (SPRITE_SIZE - SPRITE_BORDER_WIDTH)) ||
		    (local_y < SPRITE_BORDER_WIDTH) ||
		    (local_y >= (SPRITE_SIZE - SPRITE_BORDER_WIDTH))) {
			return RGB565_WHITE;
		}

		return RGB565_MAGENTA;
	}

	return orientation_pattern_pixel(x, y);
}

static uint32_t throughput_kib_per_second(size_t byte_count, uint32_t elapsed_us)
{
	return (uint32_t)(((uint64_t)byte_count * USEC_PER_SEC) /
			  ((uint64_t)MAX(elapsed_us, 1U) * 1024U));
}

static void prepare_region(const struct display_region *region, uint16_t sprite_x,
			   uint16_t sprite_y)
{
	for (size_t row = 0; row < region->height; ++row) {
		for (size_t column = 0; column < region->width; ++column) {
			const uint16_t x = region->x + (uint16_t)column;
			const uint16_t y = region->y + (uint16_t)row;
			const size_t index = (row * region->width) + column;

			display_buffer[index] =
				sys_cpu_to_be16(display_pattern_pixel(x, y, sprite_x, sprite_y));
		}
	}
}

static int write_region(const struct display_region *region, uint16_t sprite_x, uint16_t sprite_y,
			bool frame_incomplete)
{
	if (region == NULL) {
		return -EINVAL;
	}

	if ((region->width == 0U) || (region->height == 0U) ||
	    (region->width > PICOSYSTEM_DISPLAY_WIDTH) ||
	    (region->height > PICOSYSTEM_DISPLAY_HEIGHT) ||
	    (region->x > (PICOSYSTEM_DISPLAY_WIDTH - region->width)) ||
	    (region->y > (PICOSYSTEM_DISPLAY_HEIGHT - region->height))) {
		return -EINVAL;
	}

	const size_t pixel_count = (size_t)region->width * region->height;
	if (pixel_count > ARRAY_SIZE(display_buffer)) {
		return -EINVAL;
	}

	prepare_region(region, sprite_x, sprite_y);

	const struct display_buffer_descriptor descriptor = {
		.buf_size = pixel_count * sizeof(display_buffer[0]),
		.width = region->width,
		.height = region->height,
		.pitch = region->width,
		.frame_incomplete = frame_incomplete,
	};

	const int err = display_write(display, region->x, region->y, &descriptor, display_buffer);
	if (err != 0) {
		LOG_ERR("Display write failed for %ux%u at (%u,%u) (%d)", region->width,
			region->height, region->x, region->y, err);
		return err;
	}

	return 0;
}

static int write_full_pattern(const struct picosystem_display_test_state *state,
			      uint32_t *elapsed_us)
{
	if ((state == NULL) || (elapsed_us == NULL)) {
		return -EINVAL;
	}

	const uint32_t start_cycles = k_cycle_get_32();

	for (uint16_t y = 0; y < PICOSYSTEM_DISPLAY_HEIGHT; y += DISPLAY_BUFFER_ROWS) {
		const struct display_region region = {
			.x = 0U,
			.y = y,
			.width = PICOSYSTEM_DISPLAY_WIDTH,
			.height = DISPLAY_BUFFER_ROWS,
		};
		const bool frame_incomplete =
			((y + DISPLAY_BUFFER_ROWS) < PICOSYSTEM_DISPLAY_HEIGHT);

		const int err =
			write_region(&region, state->sprite_x, state->sprite_y, frame_incomplete);
		if (err != 0) {
			return err;
		}
	}

	const uint32_t elapsed_cycles = k_cycle_get_32() - start_cycles;
	*elapsed_us = MAX(k_cyc_to_us_floor32(elapsed_cycles), 1U);
	return 0;
}

static uint16_t moved_coordinate(uint16_t current, int8_t direction, uint16_t maximum)
{
	const int32_t requested =
		(int32_t)current + ((int32_t)direction * (int32_t)SPRITE_MOVE_STEP);

	return (uint16_t)CLAMP(requested, 0, maximum);
}

static struct display_region movement_region(uint16_t old_x, uint16_t old_y, uint16_t new_x,
					     uint16_t new_y)
{
	const uint16_t x = MIN(old_x, new_x);
	const uint16_t y = MIN(old_y, new_y);
	const uint16_t right = MAX(old_x, new_x) + SPRITE_SIZE;
	const uint16_t bottom = MAX(old_y, new_y) + SPRITE_SIZE;

	return (struct display_region){
		.x = x,
		.y = y,
		.width = right - x,
		.height = bottom - y,
	};
}

int picosystem_display_test_run(struct picosystem_display_test_state *state)
{
	if (state == NULL) {
		return -EINVAL;
	}

	*state = (struct picosystem_display_test_state){
		.sprite_x = SPRITE_START_X,
		.sprite_y = SPRITE_START_Y,
	};

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

	err = write_full_pattern(state, &state->full_frame_time_us);
	if (err != 0) {
		return err;
	}

	state->full_frame_throughput_kib_per_second =
		throughput_kib_per_second(FRAME_BYTES, state->full_frame_time_us);

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

	state->ready = true;
	LOG_INF("Demo frame: %u us, %u KiB/s, SPI %u Hz, backlight %u%%", state->full_frame_time_us,
		state->full_frame_throughput_kib_per_second, PICOSYSTEM_DISPLAY_SPI_HZ,
		BACKLIGHT_DUTY_PERCENT);
	return 0;
}

int picosystem_display_test_move(struct picosystem_display_test_state *state, int8_t horizontal,
				 int8_t vertical)
{
	if ((state == NULL) || !state->ready) {
		return -EINVAL;
	}

	if ((horizontal < -1) || (horizontal > 1) || (vertical < -1) || (vertical > 1)) {
		return -EINVAL;
	}

	const uint16_t new_x = moved_coordinate(state->sprite_x, horizontal,
						PICOSYSTEM_DISPLAY_WIDTH - SPRITE_SIZE);
	const uint16_t new_y = moved_coordinate(state->sprite_y, vertical,
						PICOSYSTEM_DISPLAY_HEIGHT - SPRITE_SIZE);

	if ((new_x == state->sprite_x) && (new_y == state->sprite_y)) {
		return 0;
	}

	const struct display_region region =
		movement_region(state->sprite_x, state->sprite_y, new_x, new_y);
	const size_t byte_count = (size_t)region.width * region.height * sizeof(display_buffer[0]);
	const uint32_t start_cycles = k_cycle_get_32();

	const int err = write_region(&region, new_x, new_y, false);
	if (err != 0) {
		return err;
	}

	const uint32_t elapsed_cycles = k_cycle_get_32() - start_cycles;
	const uint32_t elapsed_us = MAX(k_cyc_to_us_floor32(elapsed_cycles), 1U);

	state->sprite_x = new_x;
	state->sprite_y = new_y;
	state->last_partial_time_us = elapsed_us;
	state->last_partial_throughput_kib_per_second =
		throughput_kib_per_second(byte_count, elapsed_us);
	state->last_partial_width = region.width;
	state->last_partial_height = region.height;
	++state->partial_update_count;

	LOG_INF("Partial #%u: %ux%u at (%u,%u), %u us, %u KiB/s", state->partial_update_count,
		region.width, region.height, region.x, region.y, state->last_partial_time_us,
		state->last_partial_throughput_kib_per_second);
	return 0;
}

int picosystem_display_test_redraw(struct picosystem_display_test_state *state)
{
	if ((state == NULL) || !state->ready) {
		return -EINVAL;
	}

	uint32_t elapsed_us;
	const int err = write_full_pattern(state, &elapsed_us);
	if (err != 0) {
		return err;
	}

	state->full_frame_time_us = elapsed_us;
	state->full_frame_throughput_kib_per_second =
		throughput_kib_per_second(FRAME_BYTES, elapsed_us);

	LOG_INF("Full redraw: %u us, %u KiB/s", state->full_frame_time_us,
		state->full_frame_throughput_kib_per_second);
	return 0;
}
