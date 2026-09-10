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

#endif /* TOY_FACTORY_GRAPHICS_RASTER_H_ */
