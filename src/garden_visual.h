/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_GARDEN_VISUAL_H_
#define PICOSYSTEM_GARDEN_VISUAL_H_

#include <stdbool.h>
#include <stdint.h>

#include "garden_light.h"
#include "scene_renderer.h"

#define PICOSYSTEM_GARDEN_LEAF_VISIBLE_PROGRESS 96U
#define PICOSYSTEM_GARDEN_SUN_RADIUS_PIXELS     4U

enum picosystem_garden_moisture_band {
	PICOSYSTEM_GARDEN_MOISTURE_DRY,
	PICOSYSTEM_GARDEN_MOISTURE_DAMP,
	PICOSYSTEM_GARDEN_MOISTURE_MOIST,
	PICOSYSTEM_GARDEN_MOISTURE_WET,
	PICOSYSTEM_GARDEN_MOISTURE_SATURATED,
};

/* Keep simulation moisture precise while exposing its coarser rendered appearance. */
static inline enum picosystem_garden_moisture_band
picosystem_garden_moisture_band_for_value(uint8_t moisture)
{
	if (moisture >= 192U) {
		return PICOSYSTEM_GARDEN_MOISTURE_SATURATED;
	}
	if (moisture >= 112U) {
		return PICOSYSTEM_GARDEN_MOISTURE_WET;
	}
	if (moisture >= 48U) {
		return PICOSYSTEM_GARDEN_MOISTURE_MOIST;
	}
	return (moisture >= 12U) ? PICOSYSTEM_GARDEN_MOISTURE_DAMP : PICOSYSTEM_GARDEN_MOISTURE_DRY;
}

/* Map the simulated daylight arc to a small background indicator. */
static inline bool
picosystem_garden_sun_visual_center(const struct picosystem_scene_garden_payload *garden,
				    int16_t *center_x, int16_t *center_y)
{
	if ((garden->sun_strength <= PICOSYSTEM_GARDEN_LIGHT_MINIMUM) ||
	    (garden->sun_phase > PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE)) {
		return false;
	}

	const uint8_t height =
		(garden->sun_phase <= PICOSYSTEM_GARDEN_SUN_NOON_PHASE)
			? garden->sun_phase
			: (uint8_t)(PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE - garden->sun_phase);
	const uint16_t horizontal_range =
		(PICOSYSTEM_GARDEN_GRID_COLUMNS * PICOSYSTEM_GARDEN_CELL_PIXELS) -
		(2U * PICOSYSTEM_GARDEN_SUN_RADIUS_PIXELS) - 1U;
	*center_x =
		(int16_t)(PICOSYSTEM_GARDEN_ORIGIN_X_PIXELS + PICOSYSTEM_GARDEN_SUN_RADIUS_PIXELS +
			  (((uint16_t)garden->sun_phase * horizontal_range) /
			   PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE));
	*center_y = (int16_t)(PICOSYSTEM_GARDEN_CANOPY_TOP_PIXELS + 20U - (height / 4U));
	return true;
}

static inline bool
picosystem_garden_sun_visual_bounds(const struct picosystem_scene_garden_payload *garden,
				    struct picosystem_rect *bounds)
{
	int16_t center_x;
	int16_t center_y;
	if (!picosystem_garden_sun_visual_center(garden, &center_x, &center_y)) {
		return false;
	}
	*bounds = (struct picosystem_rect){
		.x = (uint16_t)(center_x - PICOSYSTEM_GARDEN_SUN_RADIUS_PIXELS),
		.y = (uint16_t)(center_y - PICOSYSTEM_GARDEN_SUN_RADIUS_PIXELS),
		.width = (2U * PICOSYSTEM_GARDEN_SUN_RADIUS_PIXELS) + 1U,
		.height = (2U * PICOSYSTEM_GARDEN_SUN_RADIUS_PIXELS) + 1U,
	};
	return true;
}

/* Return conservative bounds covering every pixel this node can currently draw. */
static inline bool
picosystem_garden_node_visual_bounds(const struct picosystem_scene_garden_payload *garden,
				     uint16_t index, struct picosystem_rect *bounds)
{
	const struct picosystem_scene_garden_node *const node = &garden->nodes[index];
	int32_t left = node->x;
	int32_t right = node->x;
	int32_t top = node->y;
	int32_t bottom = node->y;
	bool visible = false;

	if (node->parent_distance != 0U) {
		const struct picosystem_scene_garden_node *const parent =
			&garden->nodes[index - node->parent_distance];
		left = (left < parent->x) ? left : parent->x;
		right = (right > parent->x) ? right : parent->x;
		top = (top < parent->y) ? top : parent->y;
		bottom = (bottom > parent->y) ? bottom : parent->y;
		visible = true;
	}

	int32_t margin = 0;
	if (((node->style & PICOSYSTEM_SCENE_GARDEN_STYLE_LEAF) != 0U) &&
	    (node->growth_progress >= PICOSYSTEM_GARDEN_LEAF_VISIBLE_PROGRESS)) {
		margin = 3;
	}
	if ((node->style & PICOSYSTEM_SCENE_GARDEN_STYLE_FLOWER) != 0U) {
		margin = 3;
	}
	if ((node->style & PICOSYSTEM_SCENE_GARDEN_STYLE_PRUNED) != 0U) {
		margin = (margin > 2) ? margin : 2;
	}
	if (margin != 0) {
		visible = true;
		left -= margin;
		right += margin;
		top -= margin;
		bottom += margin;
	}
	if (!visible || (right < 0) || (bottom < 0) || (left >= PICOSYSTEM_GRAPHICS_WIDTH) ||
	    (top >= PICOSYSTEM_GRAPHICS_HEIGHT)) {
		return false;
	}

	left = (left > 0) ? left : 0;
	top = (top > 0) ? top : 0;
	right = (right < (PICOSYSTEM_GRAPHICS_WIDTH - 1)) ? right : (PICOSYSTEM_GRAPHICS_WIDTH - 1);
	bottom = (bottom < (PICOSYSTEM_GRAPHICS_HEIGHT - 1)) ? bottom
							     : (PICOSYSTEM_GRAPHICS_HEIGHT - 1);
	*bounds = (struct picosystem_rect){
		.x = (uint16_t)left,
		.y = (uint16_t)top,
		.width = (uint16_t)(right - left + 1),
		.height = (uint16_t)(bottom - top + 1),
	};
	return true;
}

#endif /* PICOSYSTEM_GARDEN_VISUAL_H_ */
