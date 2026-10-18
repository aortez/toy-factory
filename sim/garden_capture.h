/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_CAPTURE_H_
#define TOY_FACTORY_GARDEN_CAPTURE_H_

#include "garden_world.h"

/* Shared production renderer, one owner per process (global raster). Never
 * advances the supplied world. Exclusively creates raw 240x240 RGB565BE output;
 * existing paths are refused, partial writes removed, CRC unchanged on error.
 * Caller must exclusively own the output pathname during the call.
 */
int toy_factory_garden_capture(const struct picosystem_garden_world *world, const char *path,
			       uint32_t *framebuffer_crc);

#endif
