/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "graphics.h"

#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <zephyr/device.h>
#include <zephyr/drivers/display.h>
#include <zephyr/drivers/pwm.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/sys/crc.h>
#include <zephyr/sys/util.h>

LOG_MODULE_REGISTER(picosystem_graphics, LOG_LEVEL_INF);

#define PICOSYSTEM_DISPLAY_NODE   DT_CHOSEN(zephyr_display)
#define PICOSYSTEM_BACKLIGHT_NODE DT_NODELABEL(lcd_backlight)

#define DISPLAY_WIDTH          DT_PROP(PICOSYSTEM_DISPLAY_NODE, width)
#define DISPLAY_HEIGHT         DT_PROP(PICOSYSTEM_DISPLAY_NODE, height)
#define DISPLAY_SPI_HZ         DT_PROP(PICOSYSTEM_DISPLAY_NODE, mipi_max_frequency)
#define BACKLIGHT_DUTY_PERCENT 25U
#define TRANSFER_BUFFER_ROWS   8U
#define TRANSFER_BUFFER_PIXELS (DISPLAY_WIDTH * TRANSFER_BUFFER_ROWS)
#define FONT_WIDTH             3U
#define FONT_HEIGHT            5U
#define FONT_ADVANCE           (FONT_WIDTH + 1U)
#define FONT_LINE_ADVANCE      (FONT_HEIGHT + 1U)
#define FONT_MAX_SCALE         8U

static const struct device *const display = DEVICE_DT_GET(PICOSYSTEM_DISPLAY_NODE);
static const struct pwm_dt_spec backlight = PWM_DT_SPEC_GET(PICOSYSTEM_BACKLIGHT_NODE);

static uint16_t framebuffer[DISPLAY_WIDTH * DISPLAY_HEIGHT] __aligned(4);
static uint16_t transfer_buffer[TRANSFER_BUFFER_PIXELS] __aligned(4);
static bool graphics_initialized;

static const uint8_t digit_glyphs[10][FONT_HEIGHT] = {
	{0x7U, 0x5U, 0x5U, 0x5U, 0x7U}, {0x2U, 0x6U, 0x2U, 0x2U, 0x7U},
	{0x7U, 0x1U, 0x7U, 0x4U, 0x7U}, {0x7U, 0x1U, 0x7U, 0x1U, 0x7U},
	{0x5U, 0x5U, 0x7U, 0x1U, 0x1U}, {0x7U, 0x4U, 0x7U, 0x1U, 0x7U},
	{0x7U, 0x4U, 0x7U, 0x5U, 0x7U}, {0x7U, 0x1U, 0x2U, 0x2U, 0x2U},
	{0x7U, 0x5U, 0x7U, 0x5U, 0x7U}, {0x7U, 0x5U, 0x7U, 0x1U, 0x7U},
};

static const uint8_t letter_glyphs[26][FONT_HEIGHT] = {
	{0x2U, 0x5U, 0x7U, 0x5U, 0x5U}, /* A */
	{0x6U, 0x5U, 0x6U, 0x5U, 0x6U}, /* B */
	{0x3U, 0x4U, 0x4U, 0x4U, 0x3U}, /* C */
	{0x6U, 0x5U, 0x5U, 0x5U, 0x6U}, /* D */
	{0x7U, 0x4U, 0x6U, 0x4U, 0x7U}, /* E */
	{0x7U, 0x4U, 0x6U, 0x4U, 0x4U}, /* F */
	{0x3U, 0x4U, 0x5U, 0x5U, 0x3U}, /* G */
	{0x5U, 0x5U, 0x7U, 0x5U, 0x5U}, /* H */
	{0x7U, 0x2U, 0x2U, 0x2U, 0x7U}, /* I */
	{0x1U, 0x1U, 0x1U, 0x5U, 0x2U}, /* J */
	{0x5U, 0x5U, 0x6U, 0x5U, 0x5U}, /* K */
	{0x4U, 0x4U, 0x4U, 0x4U, 0x7U}, /* L */
	{0x5U, 0x7U, 0x7U, 0x5U, 0x5U}, /* M */
	{0x5U, 0x7U, 0x7U, 0x7U, 0x5U}, /* N */
	{0x2U, 0x5U, 0x5U, 0x5U, 0x2U}, /* O */
	{0x6U, 0x5U, 0x6U, 0x4U, 0x4U}, /* P */
	{0x2U, 0x5U, 0x5U, 0x3U, 0x1U}, /* Q */
	{0x6U, 0x5U, 0x6U, 0x5U, 0x5U}, /* R */
	{0x3U, 0x4U, 0x2U, 0x1U, 0x6U}, /* S */
	{0x7U, 0x2U, 0x2U, 0x2U, 0x2U}, /* T */
	{0x5U, 0x5U, 0x5U, 0x5U, 0x7U}, /* U */
	{0x5U, 0x5U, 0x5U, 0x5U, 0x2U}, /* V */
	{0x5U, 0x5U, 0x7U, 0x7U, 0x5U}, /* W */
	{0x5U, 0x5U, 0x2U, 0x5U, 0x5U}, /* X */
	{0x5U, 0x5U, 0x2U, 0x2U, 0x2U}, /* Y */
	{0x7U, 0x1U, 0x2U, 0x4U, 0x7U}, /* Z */
};

static const uint8_t blank_glyph[FONT_HEIGHT] = {0U, 0U, 0U, 0U, 0U};
static const uint8_t dash_glyph[FONT_HEIGHT] = {0U, 0U, 0x7U, 0U, 0U};
static const uint8_t dot_glyph[FONT_HEIGHT] = {0U, 0U, 0U, 0U, 0x2U};
static const uint8_t colon_glyph[FONT_HEIGHT] = {0U, 0x2U, 0U, 0x2U, 0U};
static const uint8_t slash_glyph[FONT_HEIGHT] = {0x1U, 0x1U, 0x2U, 0x4U, 0x4U};
static const uint8_t unknown_glyph[FONT_HEIGHT] = {0x6U, 0x1U, 0x2U, 0U, 0x2U};

BUILD_ASSERT(DISPLAY_WIDTH == PICOSYSTEM_GRAPHICS_WIDTH);
BUILD_ASSERT(DISPLAY_HEIGHT == PICOSYSTEM_GRAPHICS_HEIGHT);
BUILD_ASSERT(sizeof(framebuffer) == PICOSYSTEM_GRAPHICS_FRAMEBUFFER_BYTES);
BUILD_ASSERT((DISPLAY_HEIGHT % TRANSFER_BUFFER_ROWS) == 0U);
BUILD_ASSERT(sizeof(framebuffer) <= UINT32_MAX);
BUILD_ASSERT(sizeof(transfer_buffer) <= UINT32_MAX);

static int set_backlight_percent(uint32_t percent)
{
	if (percent > 100U) {
		return -EINVAL;
	}

	const uint32_t pulse = (uint32_t)(((uint64_t)backlight.period * percent) / 100U);

	return pwm_set_pulse_dt(&backlight, pulse);
}

static bool region_is_valid(const struct picosystem_rect *region)
{
	if ((region == NULL) || (region->width == 0U) || (region->height == 0U)) {
		return false;
	}

	return (region->x < DISPLAY_WIDTH) && (region->y < DISPLAY_HEIGHT) &&
	       (region->width <= (DISPLAY_WIDTH - region->x)) &&
	       (region->height <= (DISPLAY_HEIGHT - region->y));
}

static uint32_t throughput_kib_per_second(size_t byte_count, uint32_t elapsed_us)
{
	return (uint32_t)(((uint64_t)byte_count * USEC_PER_SEC) /
			  ((uint64_t)MAX(elapsed_us, 1U) * 1024U));
}

static void record_present_stats(struct picosystem_graphics_stats *stats, uint16_t width,
				 uint16_t height, size_t byte_count, uint32_t start_cycles)
{
	const uint32_t elapsed_cycles = k_cycle_get_32() - start_cycles;
	const uint32_t elapsed_us = MAX(k_cyc_to_us_floor32(elapsed_cycles), 1U);

	stats->last_present_time_us = elapsed_us;
	stats->last_present_throughput_kib_per_second =
		throughput_kib_per_second(byte_count, elapsed_us);
	stats->last_present_width = width;
	stats->last_present_height = height;
	if (stats->present_count < UINT32_MAX) {
		++stats->present_count;
	}

	if ((width == DISPLAY_WIDTH) && (height == DISPLAY_HEIGHT)) {
		stats->full_present_time_us = elapsed_us;
		stats->full_present_throughput_kib_per_second =
			throughput_kib_per_second(byte_count, elapsed_us);
		if (stats->full_present_count < UINT32_MAX) {
			++stats->full_present_count;
		}
	}
}

static uint16_t native_color(picosystem_color_t color)
{
	return sys_cpu_to_be16(color);
}

static const uint8_t *glyph_for_character(char character)
{
	if ((character >= '0') && (character <= '9')) {
		return digit_glyphs[character - '0'];
	}

	if ((character >= 'a') && (character <= 'z')) {
		character = (char)(character - ('a' - 'A'));
	}

	if ((character >= 'A') && (character <= 'Z')) {
		return letter_glyphs[character - 'A'];
	}

	switch (character) {
	case ' ':
		return blank_glyph;
	case '-':
		return dash_glyph;
	case '.':
		return dot_glyph;
	case ':':
		return colon_glyph;
	case '/':
		return slash_glyph;
	default:
		return unknown_glyph;
	}
}

int picosystem_graphics_init(struct picosystem_graphics_stats *stats)
{
	if (stats == NULL) {
		return -EINVAL;
	}

	*stats = (struct picosystem_graphics_stats){
		.framebuffer_bytes = sizeof(framebuffer),
		.transfer_buffer_bytes = sizeof(transfer_buffer),
	};
	graphics_initialized = false;

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

	if ((capabilities.x_resolution != DISPLAY_WIDTH) ||
	    (capabilities.y_resolution != DISPLAY_HEIGHT)) {
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

	err = display_blanking_on(display);
	if (err != 0) {
		LOG_ERR("Failed to blank display output (%d)", err);
		return err;
	}

	graphics_initialized = true;
	LOG_INF("Framebuffer ready: %u bytes plus %u-byte transfer buffer, SPI %u Hz",
		stats->framebuffer_bytes, stats->transfer_buffer_bytes, DISPLAY_SPI_HZ);
	return 0;
}

int picosystem_graphics_enable_output(struct picosystem_graphics_stats *stats)
{
	if ((stats == NULL) || !graphics_initialized) {
		return -EINVAL;
	}

	int err = display_blanking_off(display);
	if (err != 0) {
		LOG_ERR("Failed to enable display output (%d)", err);
		return err;
	}

	err = set_backlight_percent(BACKLIGHT_DUTY_PERCENT);
	if (err != 0) {
		LOG_ERR("Failed to enable the backlight (%d)", err);
		const int blank_err = display_blanking_on(display);
		if (blank_err != 0) {
			LOG_ERR("Failed to re-blank display after backlight error (%d)", blank_err);
		}
		return err;
	}

	stats->ready = true;
	return 0;
}

int picosystem_graphics_present_region(struct picosystem_graphics_stats *stats,
				       const struct picosystem_rect *region)
{
	if ((stats == NULL) || !graphics_initialized || !region_is_valid(region)) {
		return -EINVAL;
	}

	const uint16_t rows_per_write = TRANSFER_BUFFER_PIXELS / region->width;
	stats->last_present_start_uptime_ticks = k_uptime_ticks();
	const uint32_t start_cycles = k_cycle_get_32();

	for (uint16_t row_offset = 0U; row_offset < region->height;) {
		const uint16_t write_rows = MIN(rows_per_write, region->height - row_offset);

		for (uint16_t row = 0U; row < write_rows; ++row) {
			const size_t source_index =
				((size_t)(region->y + row_offset + row) * DISPLAY_WIDTH) +
				region->x;
			const size_t destination_index = (size_t)row * region->width;

			memcpy(&transfer_buffer[destination_index], &framebuffer[source_index],
			       (size_t)region->width * sizeof(framebuffer[0]));
		}

		const size_t pixel_count = (size_t)region->width * write_rows;
		const struct display_buffer_descriptor descriptor = {
			.buf_size = pixel_count * sizeof(transfer_buffer[0]),
			.width = region->width,
			.height = write_rows,
			.pitch = region->width,
			.frame_incomplete = ((row_offset + write_rows) < region->height),
		};

		const int err = display_write(display, region->x, region->y + row_offset,
					      &descriptor, transfer_buffer);
		if (err != 0) {
			LOG_ERR("Display write failed for %ux%u at (%u,%u) (%d)", region->width,
				region->height, region->x, region->y, err);
			return err;
		}

		row_offset += write_rows;
	}

	const size_t byte_count = (size_t)region->width * region->height * sizeof(framebuffer[0]);

	record_present_stats(stats, region->width, region->height, byte_count, start_cycles);
	return 0;
}

int picosystem_graphics_present_full(struct picosystem_graphics_stats *stats)
{
	if ((stats == NULL) || !graphics_initialized) {
		return -EINVAL;
	}

	const struct display_buffer_descriptor descriptor = {
		.buf_size = sizeof(framebuffer),
		.width = DISPLAY_WIDTH,
		.height = DISPLAY_HEIGHT,
		.pitch = DISPLAY_WIDTH,
		.frame_incomplete = false,
	};
	stats->last_present_start_uptime_ticks = k_uptime_ticks();
	const uint32_t start_cycles = k_cycle_get_32();

	/* Full frames are contiguous and already stored in the panel's RGB565X byte order. */
	const int err = display_write(display, 0U, 0U, &descriptor, framebuffer);
	if (err != 0) {
		LOG_ERR("Full-frame display write failed (%d)", err);
		return err;
	}

	record_present_stats(stats, DISPLAY_WIDTH, DISPLAY_HEIGHT, sizeof(framebuffer),
			     start_cycles);
	return 0;
}

void picosystem_graphics_clear(picosystem_color_t color)
{
	const uint16_t converted = native_color(color);

	for (size_t i = 0U; i < ARRAY_SIZE(framebuffer); ++i) {
		framebuffer[i] = converted;
	}
}

void picosystem_graphics_draw_pixel(int16_t x, int16_t y, picosystem_color_t color)
{
	if ((x < 0) || (x >= DISPLAY_WIDTH) || (y < 0) || (y >= DISPLAY_HEIGHT)) {
		return;
	}

	framebuffer[((size_t)y * DISPLAY_WIDTH) + (size_t)x] = native_color(color);
}

void picosystem_graphics_fill_rect(int16_t x, int16_t y, uint16_t width, uint16_t height,
				   picosystem_color_t color)
{
	const int32_t left = MAX((int32_t)x, 0);
	const int32_t top = MAX((int32_t)y, 0);
	const int32_t right = MIN((int32_t)x + width, DISPLAY_WIDTH);
	const int32_t bottom = MIN((int32_t)y + height, DISPLAY_HEIGHT);

	if ((left >= right) || (top >= bottom)) {
		return;
	}

	const uint16_t converted = native_color(color);
	for (int32_t row = top; row < bottom; ++row) {
		const size_t row_start = (size_t)row * DISPLAY_WIDTH;
		for (int32_t column = left; column < right; ++column) {
			framebuffer[row_start + (size_t)column] = converted;
		}
	}
}

void picosystem_graphics_draw_rect(int16_t x, int16_t y, uint16_t width, uint16_t height,
				   picosystem_color_t color)
{
	if ((width == 0U) || (height == 0U)) {
		return;
	}

	picosystem_graphics_fill_rect(x, y, width, 1U, color);
	if (height > 1U) {
		picosystem_graphics_fill_rect(x, y + height - 1, width, 1U, color);
	}
	if (height > 2U) {
		picosystem_graphics_fill_rect(x, y + 1, 1U, height - 2U, color);
		if (width > 1U) {
			picosystem_graphics_fill_rect(x + width - 1, y + 1, 1U, height - 2U, color);
		}
	}
}

int picosystem_graphics_draw_mono_sprite(int16_t x, int16_t y,
					 const struct picosystem_mono_sprite *sprite,
					 picosystem_color_t color)
{
	if ((sprite == NULL) || (sprite->data == NULL) || (sprite->width == 0U) ||
	    (sprite->height == 0U) || (sprite->stride_bytes < DIV_ROUND_UP(sprite->width, 8U))) {
		return -EINVAL;
	}

	const size_t required_size = (size_t)sprite->stride_bytes * sprite->height;
	if (required_size > sprite->data_size) {
		return -EMSGSIZE;
	}

	for (uint8_t row = 0U; row < sprite->height; ++row) {
		for (uint8_t column = 0U; column < sprite->width; ++column) {
			const size_t byte_index =
				((size_t)row * sprite->stride_bytes) + (column / 8U);
			const uint8_t mask = BIT(7U - (column % 8U));
			if ((sprite->data[byte_index] & mask) != 0U) {
				picosystem_graphics_draw_pixel(x + column, y + row, color);
			}
		}
	}

	return 0;
}

int picosystem_graphics_draw_text(int16_t x, int16_t y, const char *text, uint8_t scale,
				  picosystem_color_t color)
{
	if ((text == NULL) || (scale == 0U) || (scale > FONT_MAX_SCALE)) {
		return -EINVAL;
	}

	const int32_t origin_x = x;
	int32_t cursor_x = x;
	int32_t cursor_y = y;

	for (const char *character = text; *character != '\0'; ++character) {
		if (cursor_x >= DISPLAY_WIDTH) {
			break;
		}

		if (*character == '\n') {
			cursor_x = origin_x;
			cursor_y += FONT_LINE_ADVANCE * scale;
			if (cursor_y >= DISPLAY_HEIGHT) {
				break;
			}
			continue;
		}

		const uint8_t *const glyph = glyph_for_character(*character);
		for (uint8_t row = 0U; row < FONT_HEIGHT; ++row) {
			for (uint8_t column = 0U; column < FONT_WIDTH; ++column) {
				const uint8_t mask = BIT(FONT_WIDTH - column - 1U);
				if ((glyph[row] & mask) == 0U) {
					continue;
				}

				const int32_t pixel_x = cursor_x + ((int32_t)column * scale);
				const int32_t pixel_y = cursor_y + ((int32_t)row * scale);
				picosystem_graphics_fill_rect((int16_t)pixel_x, (int16_t)pixel_y,
							      scale, scale, color);
			}
		}

		cursor_x += FONT_ADVANCE * scale;
		if (cursor_x >= DISPLAY_WIDTH) {
			break;
		}
	}

	return 0;
}

int picosystem_graphics_visit_framebuffer(size_t chunk_bytes,
					  picosystem_graphics_framebuffer_visitor visitor,
					  void *context)
{
	if (!graphics_initialized || (chunk_bytes == 0U) || (visitor == NULL)) {
		return -EINVAL;
	}

	const uint8_t *const bytes = (const uint8_t *)framebuffer;
	for (size_t offset = 0U; offset < sizeof(framebuffer); offset += chunk_bytes) {
		const size_t length = MIN(chunk_bytes, sizeof(framebuffer) - offset);
		const int err = visitor(offset, &bytes[offset], length, context);
		if (err != 0) {
			return err;
		}
	}

	return 0;
}

int picosystem_graphics_framebuffer_crc32(uint32_t *crc)
{
	if (!graphics_initialized || (crc == NULL)) {
		return -EINVAL;
	}

	*crc = crc32_ieee((const uint8_t *)framebuffer, sizeof(framebuffer));
	return 0;
}
