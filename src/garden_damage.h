/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_GARDEN_DAMAGE_H_
#define PICOSYSTEM_GARDEN_DAMAGE_H_

#include <stdint.h>

#include "scene_renderer.h"

#define PICOSYSTEM_GARDEN_DAMAGE_TILE_PIXELS 8U
#define PICOSYSTEM_GARDEN_DAMAGE_TILE_COLUMNS                                                      \
	(PICOSYSTEM_GRAPHICS_WIDTH / PICOSYSTEM_GARDEN_DAMAGE_TILE_PIXELS)
#define PICOSYSTEM_GARDEN_DAMAGE_TILE_ROWS                                                         \
	(PICOSYSTEM_GRAPHICS_HEIGHT / PICOSYSTEM_GARDEN_DAMAGE_TILE_PIXELS)

/* One 32-bit row covers all thirty 8 x 8 tiles without dynamic storage. */
struct picosystem_garden_damage_plan {
	uint32_t row_masks[PICOSYSTEM_GARDEN_DAMAGE_TILE_ROWS];
	uint16_t dirty_tile_count;
};

struct picosystem_garden_damage_iterator {
	uint8_t next_row;
	uint8_t next_column;
};

/* Compare the latest snapshot with the last snapshot that reached the panel. */
int picosystem_garden_damage_plan_build(const struct picosystem_scene_snapshot *presented,
					const struct picosystem_scene_snapshot *current,
					struct picosystem_garden_damage_plan *plan);

int picosystem_garden_damage_iterator_init(struct picosystem_garden_damage_iterator *iterator);

/* Return one for a region, zero at end, or a negative errno value on invalid input. */
int picosystem_garden_damage_next_region(const struct picosystem_garden_damage_plan *plan,
					 struct picosystem_garden_damage_iterator *iterator,
					 struct picosystem_rect *region);

#endif /* PICOSYSTEM_GARDEN_DAMAGE_H_ */
