/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "graphics_raster.h"

#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "portable_util.h"
#include "render_placement.h"

#define FONT_WIDTH              3U
#define FONT_HEIGHT             5U
#define FONT_ADVANCE            (FONT_WIDTH + 1U)
#define FONT_LINE_ADVANCE       (FONT_HEIGHT + 1U)
#define FONT_MAX_SCALE          8U
#define TRIANGLE_FAST_COORD_MIN (-4096)
#define TRIANGLE_FAST_COORD_MAX 4095

union graphics_framebuffer_storage {
	uint16_t pixels[PICOSYSTEM_GRAPHICS_WIDTH * PICOSYSTEM_GRAPHICS_HEIGHT];
	uint32_t pairs[(PICOSYSTEM_GRAPHICS_WIDTH * PICOSYSTEM_GRAPHICS_HEIGHT) / 2U];
};

static union graphics_framebuffer_storage framebuffer __attribute__((aligned(4)));

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

_Static_assert(sizeof(framebuffer.pixels) == PICOSYSTEM_GRAPHICS_FRAMEBUFFER_BYTES,
	       "framebuffer byte count must match the public graphics contract");
_Static_assert(TOY_FACTORY_ARRAY_SIZE(framebuffer.pixels) ==
		       (2U * TOY_FACTORY_ARRAY_SIZE(framebuffer.pairs)),
	       "paired framebuffer access must cover every pixel");
_Static_assert(2LL * (TRIANGLE_FAST_COORD_MAX - TRIANGLE_FAST_COORD_MIN) *
			       (TRIANGLE_FAST_COORD_MAX - TRIANGLE_FAST_COORD_MIN) <=
		       INT32_MAX,
	       "fast triangle edges must fit in 32 bits");

static PICOSYSTEM_RENDER_RAMFUNC uint16_t native_color(picosystem_color_t color)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
	return (uint16_t)((color << 8U) | (color >> 8U));
#elif __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
	return color;
#else
#error "unsupported byte order"
#endif
}

static PICOSYSTEM_RENDER_RAMFUNC const uint8_t *glyph_for_character(char character)
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

PICOSYSTEM_RENDER_RAMFUNC void picosystem_graphics_clear(picosystem_color_t color)
{
	const uint16_t converted = native_color(color);
	const uint32_t pair = ((uint32_t)converted << 16U) | converted;

	for (size_t i = 0U; i < TOY_FACTORY_ARRAY_SIZE(framebuffer.pairs); ++i) {
		framebuffer.pairs[i] = pair;
	}
}

static PICOSYSTEM_RENDER_RAMFUNC void draw_native_pixel(const struct picosystem_rect *clip,
							int32_t x, int32_t y, uint16_t converted)
{
	if ((x < 0) || (x >= PICOSYSTEM_GRAPHICS_WIDTH) || (y < 0) ||
	    (y >= PICOSYSTEM_GRAPHICS_HEIGHT)) {
		return;
	}
	if ((clip != NULL) && ((x < clip->x) || (x >= ((int32_t)clip->x + clip->width)) ||
			       (y < clip->y) || (y >= ((int32_t)clip->y + clip->height)))) {
		return;
	}

	framebuffer.pixels[((size_t)y * PICOSYSTEM_GRAPHICS_WIDTH) + (size_t)x] = converted;
}

PICOSYSTEM_RENDER_RAMFUNC void picosystem_graphics_draw_pixel(int16_t x, int16_t y,
							      picosystem_color_t color)
{
	picosystem_graphics_draw_pixel_clipped(NULL, x, y, color);
}

PICOSYSTEM_RENDER_RAMFUNC void
picosystem_graphics_draw_pixel_clipped(const struct picosystem_rect *clip, int16_t x, int16_t y,
				       picosystem_color_t color)
{
	draw_native_pixel(clip, x, y, native_color(color));
}

PICOSYSTEM_RENDER_RAMFUNC void picosystem_graphics_fill_rect(int16_t x, int16_t y, uint16_t width,
							     uint16_t height,
							     picosystem_color_t color)
{
	picosystem_graphics_fill_rect_clipped(NULL, x, y, width, height, color);
}

PICOSYSTEM_RENDER_RAMFUNC void
picosystem_graphics_fill_rect_clipped(const struct picosystem_rect *clip, int16_t x, int16_t y,
				      uint16_t width, uint16_t height, picosystem_color_t color)
{
	int32_t left = TOY_FACTORY_MAX((int32_t)x, 0);
	int32_t top = TOY_FACTORY_MAX((int32_t)y, 0);
	int32_t right = TOY_FACTORY_MIN((int32_t)x + width, PICOSYSTEM_GRAPHICS_WIDTH);
	int32_t bottom = TOY_FACTORY_MIN((int32_t)y + height, PICOSYSTEM_GRAPHICS_HEIGHT);
	if (clip != NULL) {
		left = TOY_FACTORY_MAX(left, clip->x);
		top = TOY_FACTORY_MAX(top, clip->y);
		right = TOY_FACTORY_MIN(right, (int32_t)clip->x + clip->width);
		bottom = TOY_FACTORY_MIN(bottom, (int32_t)clip->y + clip->height);
	}

	if ((left >= right) || (top >= bottom)) {
		return;
	}

	const uint16_t converted = native_color(color);
	for (int32_t row = top; row < bottom; ++row) {
		const size_t row_start = (size_t)row * PICOSYSTEM_GRAPHICS_WIDTH;
		for (int32_t column = left; column < right; ++column) {
			framebuffer.pixels[row_start + (size_t)column] = converted;
		}
	}
}

PICOSYSTEM_RENDER_RAMFUNC void picosystem_graphics_draw_rect(int16_t x, int16_t y, uint16_t width,
							     uint16_t height,
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

PICOSYSTEM_RENDER_RAMFUNC void picosystem_graphics_draw_line(int16_t start_x, int16_t start_y,
							     int16_t end_x, int16_t end_y,
							     picosystem_color_t color)
{
	picosystem_graphics_draw_line_clipped(NULL, start_x, start_y, end_x, end_y, color);
}

PICOSYSTEM_RENDER_RAMFUNC void
picosystem_graphics_draw_line_clipped(const struct picosystem_rect *clip, int16_t start_x,
				      int16_t start_y, int16_t end_x, int16_t end_y,
				      picosystem_color_t color)
{
	int32_t x = start_x;
	int32_t y = start_y;
	const int32_t delta_x = (end_x >= start_x) ? end_x - start_x : start_x - end_x;
	const int32_t delta_y = (end_y >= start_y) ? start_y - end_y : end_y - start_y;
	const int32_t step_x = (start_x < end_x) ? 1 : -1;
	const int32_t step_y = (start_y < end_y) ? 1 : -1;
	int32_t error = delta_x + delta_y;
	const uint16_t converted = native_color(color);

	while (true) {
		draw_native_pixel(clip, x, y, converted);
		if ((x == end_x) && (y == end_y)) {
			break;
		}

		const int32_t doubled_error = 2 * error;
		if (doubled_error >= delta_y) {
			error += delta_y;
			x += step_x;
		}
		if (doubled_error <= delta_x) {
			error += delta_x;
			y += step_y;
		}
	}
}

static PICOSYSTEM_RENDER_RAMFUNC int64_t triangle_edge_wide(int16_t start_x, int16_t start_y,
							    int16_t end_x, int16_t end_y,
							    int32_t point_x, int32_t point_y)
{
	return ((int64_t)end_x - start_x) * (point_y - start_y) -
	       ((int64_t)end_y - start_y) * (point_x - start_x);
}

static PICOSYSTEM_RENDER_RAMFUNC int32_t triangle_edge_fast(int16_t start_x, int16_t start_y,
							    int16_t end_x, int16_t end_y,
							    int32_t point_x, int32_t point_y)
{
	return ((int32_t)end_x - start_x) * (point_y - start_y) -
	       ((int32_t)end_y - start_y) * (point_x - start_x);
}

static PICOSYSTEM_RENDER_RAMFUNC bool
triangle_supports_fast_edges(int16_t x0, int16_t y0, int16_t x1, int16_t y1, int16_t x2, int16_t y2)
{
	return (x0 >= TRIANGLE_FAST_COORD_MIN) && (x0 <= TRIANGLE_FAST_COORD_MAX) &&
	       (y0 >= TRIANGLE_FAST_COORD_MIN) && (y0 <= TRIANGLE_FAST_COORD_MAX) &&
	       (x1 >= TRIANGLE_FAST_COORD_MIN) && (x1 <= TRIANGLE_FAST_COORD_MAX) &&
	       (y1 >= TRIANGLE_FAST_COORD_MIN) && (y1 <= TRIANGLE_FAST_COORD_MAX) &&
	       (x2 >= TRIANGLE_FAST_COORD_MIN) && (x2 <= TRIANGLE_FAST_COORD_MAX) &&
	       (y2 >= TRIANGLE_FAST_COORD_MIN) && (y2 <= TRIANGLE_FAST_COORD_MAX);
}

static PICOSYSTEM_RENDER_RAMFUNC void fill_triangle_fast(int16_t x0, int16_t y0, int16_t x1,
							 int16_t y1, int16_t x2, int16_t y2,
							 int32_t left, int32_t top, int32_t right,
							 int32_t bottom, uint16_t converted)
{
	const int32_t area = triangle_edge_fast(x0, y0, x1, y1, x2, y2);
	if (area == 0) {
		return;
	}

	const bool positive = area > 0;
	int32_t row_edge_0 = triangle_edge_fast(x0, y0, x1, y1, left, top);
	int32_t row_edge_1 = triangle_edge_fast(x1, y1, x2, y2, left, top);
	int32_t row_edge_2 = triangle_edge_fast(x2, y2, x0, y0, left, top);
	const int32_t x_step_0 = -((int32_t)y1 - y0);
	const int32_t x_step_1 = -((int32_t)y2 - y1);
	const int32_t x_step_2 = -((int32_t)y0 - y2);
	const int32_t y_step_0 = (int32_t)x1 - x0;
	const int32_t y_step_1 = (int32_t)x2 - x1;
	const int32_t y_step_2 = (int32_t)x0 - x2;
	for (int32_t y = top; y <= bottom; ++y) {
		const size_t row_start = (size_t)y * PICOSYSTEM_GRAPHICS_WIDTH;
		int32_t edge_0 = row_edge_0;
		int32_t edge_1 = row_edge_1;
		int32_t edge_2 = row_edge_2;
		for (int32_t x = left; x <= right; ++x) {
			if (positive ? ((edge_0 >= 0) && (edge_1 >= 0) && (edge_2 >= 0))
				     : ((edge_0 <= 0) && (edge_1 <= 0) && (edge_2 <= 0))) {
				framebuffer.pixels[row_start + (size_t)x] = converted;
			}
			edge_0 += x_step_0;
			edge_1 += x_step_1;
			edge_2 += x_step_2;
		}
		row_edge_0 += y_step_0;
		row_edge_1 += y_step_1;
		row_edge_2 += y_step_2;
	}
}

static PICOSYSTEM_RENDER_RAMFUNC void fill_triangle_wide(int16_t x0, int16_t y0, int16_t x1,
							 int16_t y1, int16_t x2, int16_t y2,
							 int32_t left, int32_t top, int32_t right,
							 int32_t bottom, uint16_t converted)
{
	const int64_t area = triangle_edge_wide(x0, y0, x1, y1, x2, y2);
	if (area == 0) {
		return;
	}

	const bool positive = area > 0;
	int64_t row_edge_0 = triangle_edge_wide(x0, y0, x1, y1, left, top);
	int64_t row_edge_1 = triangle_edge_wide(x1, y1, x2, y2, left, top);
	int64_t row_edge_2 = triangle_edge_wide(x2, y2, x0, y0, left, top);
	const int32_t x_step_0 = -((int32_t)y1 - y0);
	const int32_t x_step_1 = -((int32_t)y2 - y1);
	const int32_t x_step_2 = -((int32_t)y0 - y2);
	const int32_t y_step_0 = (int32_t)x1 - x0;
	const int32_t y_step_1 = (int32_t)x2 - x1;
	const int32_t y_step_2 = (int32_t)x0 - x2;
	for (int32_t y = top; y <= bottom; ++y) {
		const size_t row_start = (size_t)y * PICOSYSTEM_GRAPHICS_WIDTH;
		int64_t edge_0 = row_edge_0;
		int64_t edge_1 = row_edge_1;
		int64_t edge_2 = row_edge_2;
		for (int32_t x = left; x <= right; ++x) {
			if (positive ? ((edge_0 >= 0) && (edge_1 >= 0) && (edge_2 >= 0))
				     : ((edge_0 <= 0) && (edge_1 <= 0) && (edge_2 <= 0))) {
				framebuffer.pixels[row_start + (size_t)x] = converted;
			}
			edge_0 += x_step_0;
			edge_1 += x_step_1;
			edge_2 += x_step_2;
		}
		row_edge_0 += y_step_0;
		row_edge_1 += y_step_1;
		row_edge_2 += y_step_2;
	}
}

PICOSYSTEM_RENDER_RAMFUNC void picosystem_graphics_fill_triangle(int16_t x0, int16_t y0, int16_t x1,
								 int16_t y1, int16_t x2, int16_t y2,
								 picosystem_color_t color)
{
	picosystem_graphics_fill_triangle_clipped(NULL, x0, y0, x1, y1, x2, y2, color);
}

PICOSYSTEM_RENDER_RAMFUNC void
picosystem_graphics_fill_triangle_clipped(const struct picosystem_rect *clip, int16_t x0,
					  int16_t y0, int16_t x1, int16_t y1, int16_t x2,
					  int16_t y2, picosystem_color_t color)
{
	int32_t left = TOY_FACTORY_MAX(TOY_FACTORY_MIN(x0, TOY_FACTORY_MIN(x1, x2)), 0);
	int32_t top = TOY_FACTORY_MAX(TOY_FACTORY_MIN(y0, TOY_FACTORY_MIN(y1, y2)), 0);
	int32_t right = TOY_FACTORY_MIN(TOY_FACTORY_MAX(x0, TOY_FACTORY_MAX(x1, x2)),
					PICOSYSTEM_GRAPHICS_WIDTH - 1);
	int32_t bottom = TOY_FACTORY_MIN(TOY_FACTORY_MAX(y0, TOY_FACTORY_MAX(y1, y2)),
					 PICOSYSTEM_GRAPHICS_HEIGHT - 1);
	if (clip != NULL) {
		left = TOY_FACTORY_MAX(left, clip->x);
		top = TOY_FACTORY_MAX(top, clip->y);
		right = TOY_FACTORY_MIN(right, (int32_t)clip->x + clip->width - 1);
		bottom = TOY_FACTORY_MIN(bottom, (int32_t)clip->y + clip->height - 1);
	}
	if ((left > right) || (top > bottom)) {
		return;
	}

	const uint16_t converted = native_color(color);
	if (triangle_supports_fast_edges(x0, y0, x1, y1, x2, y2)) {
		fill_triangle_fast(x0, y0, x1, y1, x2, y2, left, top, right, bottom, converted);
	} else {
		fill_triangle_wide(x0, y0, x1, y1, x2, y2, left, top, right, bottom, converted);
	}
}

static PICOSYSTEM_RENDER_RAMFUNC void fill_circle_span(const struct picosystem_rect *clip,
						       int32_t left, int32_t right, int32_t y,
						       picosystem_color_t color)
{
	if ((y < 0) || (y >= PICOSYSTEM_GRAPHICS_HEIGHT) || (right < 0) ||
	    (left >= PICOSYSTEM_GRAPHICS_WIDTH)) {
		return;
	}

	left = TOY_FACTORY_MAX(left, 0);
	right = TOY_FACTORY_MIN(right, PICOSYSTEM_GRAPHICS_WIDTH - 1);
	picosystem_graphics_fill_rect_clipped(clip, (int16_t)left, (int16_t)y,
					      (uint16_t)(right - left + 1), 1U, color);
}

PICOSYSTEM_RENDER_RAMFUNC int picosystem_graphics_fill_circle(int16_t center_x, int16_t center_y,
							      uint16_t radius,
							      picosystem_color_t color)
{
	return picosystem_graphics_fill_circle_clipped(NULL, center_x, center_y, radius, color);
}

PICOSYSTEM_RENDER_RAMFUNC int
picosystem_graphics_fill_circle_clipped(const struct picosystem_rect *clip, int16_t center_x,
					int16_t center_y, uint16_t radius, picosystem_color_t color)
{
	if (radius > TOY_FACTORY_MAX(PICOSYSTEM_GRAPHICS_WIDTH, PICOSYSTEM_GRAPHICS_HEIGHT)) {
		return -ERANGE;
	}
	if (radius == 2U) {
		/* The generic midpoint loop reaches this exact five-span footprint after
		 * eight writes, including three overlapping spans. Granular scenes use
		 * radius two for every grain, so emit only the final visible union.
		 */
		fill_circle_span(clip, (int32_t)center_x - 1, (int32_t)center_x + 1,
				 (int32_t)center_y - 2, color);
		fill_circle_span(clip, (int32_t)center_x - 2, (int32_t)center_x + 2,
				 (int32_t)center_y - 1, color);
		fill_circle_span(clip, (int32_t)center_x - 2, (int32_t)center_x + 2, center_y,
				 color);
		fill_circle_span(clip, (int32_t)center_x - 2, (int32_t)center_x + 2,
				 (int32_t)center_y + 1, color);
		fill_circle_span(clip, (int32_t)center_x - 1, (int32_t)center_x + 1,
				 (int32_t)center_y + 2, color);
		return 0;
	}
	int32_t x = radius;
	int32_t y = 0;
	int32_t decision = 1 - x;

	while (y <= x) {
		fill_circle_span(clip, (int32_t)center_x - x, (int32_t)center_x + x,
				 (int32_t)center_y + y, color);
		fill_circle_span(clip, (int32_t)center_x - x, (int32_t)center_x + x,
				 (int32_t)center_y - y, color);
		fill_circle_span(clip, (int32_t)center_x - y, (int32_t)center_x + y,
				 (int32_t)center_y + x, color);
		fill_circle_span(clip, (int32_t)center_x - y, (int32_t)center_x + y,
				 (int32_t)center_y - x, color);

		++y;
		if (decision <= 0) {
			decision += (2 * y) + 1;
		} else {
			--x;
			decision += (2 * (y - x)) + 1;
		}
	}

	return 0;
}

uint16_t *picosystem_graphics_raster_pixels(void)
{
	return framebuffer.pixels;
}

const uint8_t *picosystem_graphics_raster_bytes(void)
{
	return (const uint8_t *)framebuffer.pixels;
}

size_t picosystem_graphics_raster_byte_count(void)
{
	return sizeof(framebuffer.pixels);
}

uint32_t picosystem_graphics_raster_crc32(void)
{
	const uint8_t *const bytes = picosystem_graphics_raster_bytes();
	uint32_t crc = UINT32_MAX;

	for (size_t index = 0U; index < sizeof(framebuffer.pixels); ++index) {
		crc ^= bytes[index];
		for (uint8_t bit = 0U; bit < 8U; ++bit) {
			const uint32_t mask = (uint32_t) - (int32_t)(crc & UINT32_C(1));
			crc = (crc >> 1U) ^ (UINT32_C(0xedb88320) & mask);
		}
	}

	return ~crc;
}

PICOSYSTEM_RENDER_RAMFUNC int picosystem_graphics_draw_mono_sprite(
	int16_t x, int16_t y, const struct picosystem_mono_sprite *sprite, picosystem_color_t color)
{
	if ((sprite == NULL) || (sprite->data == NULL) || (sprite->width == 0U) ||
	    (sprite->height == 0U) ||
	    (sprite->stride_bytes < TOY_FACTORY_DIV_ROUND_UP(sprite->width, 8U))) {
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
			const uint8_t mask = TOY_FACTORY_BIT(7U - (column % 8U));
			if ((sprite->data[byte_index] & mask) != 0U) {
				picosystem_graphics_draw_pixel(x + column, y + row, color);
			}
		}
	}

	return 0;
}

PICOSYSTEM_RENDER_RAMFUNC int picosystem_graphics_draw_text(int16_t x, int16_t y, const char *text,
							    uint8_t scale, picosystem_color_t color)
{
	return picosystem_graphics_draw_text_clipped(NULL, x, y, text, scale, color);
}

PICOSYSTEM_RENDER_RAMFUNC int
picosystem_graphics_draw_text_clipped(const struct picosystem_rect *clip, int16_t x, int16_t y,
				      const char *text, uint8_t scale, picosystem_color_t color)
{
	if ((text == NULL) || (scale == 0U) || (scale > FONT_MAX_SCALE)) {
		return -EINVAL;
	}

	const int32_t origin_x = x;
	int32_t cursor_x = x;
	int32_t cursor_y = y;

	for (const char *character = text; *character != '\0'; ++character) {
		if (cursor_x >= PICOSYSTEM_GRAPHICS_WIDTH) {
			break;
		}

		if (*character == '\n') {
			cursor_x = origin_x;
			cursor_y += FONT_LINE_ADVANCE * scale;
			if (cursor_y >= PICOSYSTEM_GRAPHICS_HEIGHT) {
				break;
			}
			continue;
		}

		const uint8_t *const glyph = glyph_for_character(*character);
		for (uint8_t row = 0U; row < FONT_HEIGHT; ++row) {
			for (uint8_t column = 0U; column < FONT_WIDTH; ++column) {
				const uint8_t mask = TOY_FACTORY_BIT(FONT_WIDTH - column - 1U);
				if ((glyph[row] & mask) == 0U) {
					continue;
				}

				const int32_t pixel_x = cursor_x + ((int32_t)column * scale);
				const int32_t pixel_y = cursor_y + ((int32_t)row * scale);
				picosystem_graphics_fill_rect_clipped(clip, (int16_t)pixel_x,
								      (int16_t)pixel_y, scale,
								      scale, color);
			}
		}

		cursor_x += FONT_ADVANCE * scale;
		if (cursor_x >= PICOSYSTEM_GRAPHICS_WIDTH) {
			break;
		}
	}

	return 0;
}
