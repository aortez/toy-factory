/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_GRAPHICS_H_
#define PICOSYSTEM_GRAPHICS_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define PICOSYSTEM_GRAPHICS_WIDTH  240U
#define PICOSYSTEM_GRAPHICS_HEIGHT 240U
#define PICOSYSTEM_GRAPHICS_FRAMEBUFFER_BYTES                                                      \
	(PICOSYSTEM_GRAPHICS_WIDTH * PICOSYSTEM_GRAPHICS_HEIGHT * 2U)

typedef uint16_t picosystem_color_t;

enum picosystem_color {
	PICOSYSTEM_COLOR_BLACK = 0x0000U,
	PICOSYSTEM_COLOR_DARK_BLUE = 0x0842U,
	PICOSYSTEM_COLOR_NAVY = 0x000fU,
	PICOSYSTEM_COLOR_BLUE = 0x001fU,
	PICOSYSTEM_COLOR_GREEN = 0x07e0U,
	PICOSYSTEM_COLOR_CYAN = 0x07ffU,
	PICOSYSTEM_COLOR_RED = 0xf800U,
	PICOSYSTEM_COLOR_MAGENTA = 0xf81fU,
	PICOSYSTEM_COLOR_YELLOW = 0xffe0U,
	PICOSYSTEM_COLOR_WHITE = 0xffffU,
};

struct picosystem_rect {
	uint16_t x;
	uint16_t y;
	uint16_t width;
	uint16_t height;
};

struct picosystem_mono_sprite {
	const uint8_t *data;
	size_t data_size;
	uint8_t width;
	uint8_t height;
	uint8_t stride_bytes;
};

struct picosystem_graphics_stats {
	int64_t last_present_start_uptime_ticks;
	uint32_t framebuffer_bytes;
	uint32_t transfer_buffer_bytes;
	uint32_t full_present_time_us;
	uint32_t full_present_throughput_kib_per_second;
	uint32_t last_present_time_us;
	uint32_t last_present_throughput_kib_per_second;
	uint32_t present_count;
	uint32_t full_present_count;
	uint16_t last_present_width;
	uint16_t last_present_height;
	bool ready;
};

typedef int (*picosystem_graphics_framebuffer_visitor)(size_t offset, const uint8_t *data,
						       size_t length, void *context);

/* Configure the panel while keeping both display output and backlight off. */
int picosystem_graphics_init(struct picosystem_graphics_stats *stats);

/* Enable panel output after the caller has presented the initial frame. */
int picosystem_graphics_enable_output(struct picosystem_graphics_stats *stats);

/* Present immediately; higher layers own any panel-synchronization policy. */
int picosystem_graphics_present_region(struct picosystem_graphics_stats *stats,
				       const struct picosystem_rect *region);
int picosystem_graphics_present_full(struct picosystem_graphics_stats *stats);

void picosystem_graphics_clear(picosystem_color_t color);
void picosystem_graphics_draw_pixel(int16_t x, int16_t y, picosystem_color_t color);
void picosystem_graphics_fill_rect(int16_t x, int16_t y, uint16_t width, uint16_t height,
				   picosystem_color_t color);
void picosystem_graphics_draw_rect(int16_t x, int16_t y, uint16_t width, uint16_t height,
				   picosystem_color_t color);
void picosystem_graphics_draw_line(int16_t start_x, int16_t start_y, int16_t end_x, int16_t end_y,
				   picosystem_color_t color);
void picosystem_graphics_fill_triangle(int16_t x0, int16_t y0, int16_t x1, int16_t y1, int16_t x2,
				       int16_t y2, picosystem_color_t color);
int picosystem_graphics_fill_circle(int16_t center_x, int16_t center_y, uint16_t radius,
				    picosystem_color_t color);
int picosystem_graphics_draw_mono_sprite(int16_t x, int16_t y,
					 const struct picosystem_mono_sprite *sprite,
					 picosystem_color_t color);
int picosystem_graphics_draw_text(int16_t x, int16_t y, const char *text, uint8_t scale,
				  picosystem_color_t color);

/* Visit the native RGB565 big-endian framebuffer. The caller serializes rendering. */
int picosystem_graphics_visit_framebuffer(size_t chunk_bytes,
					  picosystem_graphics_framebuffer_visitor visitor,
					  void *context);
int picosystem_graphics_framebuffer_crc32(uint32_t *crc);

#endif /* PICOSYSTEM_GRAPHICS_H_ */
