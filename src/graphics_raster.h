/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef TOY_FACTORY_GRAPHICS_RASTER_H_
#define TOY_FACTORY_GRAPHICS_RASTER_H_

#include <stddef.h>
#include <stdint.h>

#include "graphics.h"

/* Internal access for display transports and host presentation frontends. */
uint16_t *picosystem_graphics_raster_pixels(void);
const uint8_t *picosystem_graphics_raster_bytes(void);
size_t picosystem_graphics_raster_byte_count(void);
uint32_t picosystem_graphics_raster_crc32(void);

#if defined(TOY_FACTORY_RASTER_WORK_COUNTERS)
/* Host-only counters. Pixel writes count logical framebuffer pixels, including packed clears. */
struct picosystem_graphics_raster_work {
	uint64_t pixel_write_count;
	uint32_t clear_call_count;
	uint32_t draw_pixel_call_count;
	uint32_t fill_rect_call_count;
	uint32_t draw_rect_call_count;
	uint32_t draw_line_call_count;
	uint32_t fill_triangle_call_count;
	uint32_t fill_circle_call_count;
	uint32_t draw_mono_sprite_call_count;
	uint32_t draw_text_call_count;
};

void picosystem_graphics_raster_work_begin(void);
int picosystem_graphics_raster_work_end(struct picosystem_graphics_raster_work *work);
#endif

#endif /* TOY_FACTORY_GRAPHICS_RASTER_H_ */
