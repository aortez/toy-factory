/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "garden_damage.h"

#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "game_world.h"
#include "garden_visual.h"
#include "portable_util.h"

_Static_assert((PICOSYSTEM_GRAPHICS_WIDTH % PICOSYSTEM_GARDEN_DAMAGE_TILE_PIXELS) == 0U,
	       "damage tiles must span the framebuffer width");
_Static_assert((PICOSYSTEM_GRAPHICS_HEIGHT % PICOSYSTEM_GARDEN_DAMAGE_TILE_PIXELS) == 0U,
	       "damage tiles must span the framebuffer height");
_Static_assert(PICOSYSTEM_GARDEN_DAMAGE_TILE_COLUMNS <= 32U,
	       "one damage row must fit a 32-bit mask");
_Static_assert(PICOSYSTEM_GARDEN_DAMAGE_TILE_ROWS <= UINT8_MAX,
	       "damage iterator rows must fit one byte");

static int validate_garden_snapshot(const struct picosystem_scene_snapshot *snapshot)
{
	if (snapshot == NULL) {
		return -EINVAL;
	}
	if (snapshot->scene_id != PICOSYSTEM_GAME_SCENE_GARDEN) {
		return -ENOTSUP;
	}

	const struct picosystem_scene_garden_payload *const garden = &snapshot->payload.garden;
	if ((snapshot->body_count != 0U) || (snapshot->static_segment_count != 0U) ||
	    (snapshot->distance_joint_count != 0U) || (snapshot->revolute_joint_count != 0U) ||
	    (snapshot->box_sensor_count != 0U) || (snapshot->rope_count != 0U) ||
	    (snapshot->granular_particle_count != 0U) ||
	    (garden->node_count > PICOSYSTEM_GARDEN_MAX_NODES) ||
	    (garden->plant_count > PICOSYSTEM_GARDEN_MAX_PLANTS) ||
	    (garden->seed_count > PICOSYSTEM_GARDEN_MAX_SEEDS) ||
	    (garden->cursor_column >= PICOSYSTEM_GARDEN_GRID_COLUMNS) ||
	    (garden->cursor_row >= PICOSYSTEM_GARDEN_CURSOR_ROWS) ||
	    (garden->selected_tool >= PICOSYSTEM_GARDEN_TOOL_COUNT) ||
	    (garden->auto_target_column >= PICOSYSTEM_GARDEN_GRID_COLUMNS) ||
	    (garden->auto_target_row >= PICOSYSTEM_GARDEN_CURSOR_ROWS) ||
	    (garden->auto_target_tool >= PICOSYSTEM_GARDEN_TOOL_COUNT) ||
	    (garden->auto_gardener_enabled > 1U) || (garden->auto_target_valid > 1U) ||
	    (garden->rain_rate > PICOSYSTEM_GARDEN_RAIN_MAX_RATE) ||
	    (garden->sun_strength < PICOSYSTEM_GARDEN_LIGHT_MINIMUM) ||
	    (garden->sun_ray_step_x_q4 < -PICOSYSTEM_GARDEN_SUN_MAX_RAY_STEP_X_Q4) ||
	    (garden->sun_ray_step_x_q4 > PICOSYSTEM_GARDEN_SUN_MAX_RAY_STEP_X_Q4)) {
		return -ERANGE;
	}

	for (uint16_t index = 0U; index < garden->node_count; ++index) {
		const struct picosystem_scene_garden_node *const node = &garden->nodes[index];
		if ((node->x >= PICOSYSTEM_GRAPHICS_WIDTH) ||
		    (node->y >= PICOSYSTEM_GRAPHICS_HEIGHT) ||
		    ((node->style & (uint8_t)~PICOSYSTEM_SCENE_GARDEN_STYLE_VALID_MASK) != 0U) ||
		    ((node->style & PICOSYSTEM_SCENE_GARDEN_STYLE_SPECIES_MASK) >=
		     PICOSYSTEM_GARDEN_SPECIES_COUNT) ||
		    ((node->parent_distance != 0U) && (node->parent_distance > index))) {
			return -ERANGE;
		}
	}
	for (uint8_t index = 0U; index < garden->seed_count; ++index) {
		const struct picosystem_scene_garden_seed *const seed = &garden->seeds[index];
		if ((seed->x >= PICOSYSTEM_GRAPHICS_WIDTH) ||
		    ((seed->style & (uint8_t)~PICOSYSTEM_SCENE_GARDEN_SEED_STYLE_VALID_MASK) !=
		     0U) ||
		    ((seed->style & PICOSYSTEM_SCENE_GARDEN_SEED_STYLE_SPECIES_MASK) >=
		     PICOSYSTEM_GARDEN_SPECIES_COUNT)) {
			return -ERANGE;
		}
	}
	return 0;
}

static void mark_pixel_bounds(struct picosystem_garden_damage_plan *plan, int32_t left, int32_t top,
			      int32_t right, int32_t bottom)
{
	if ((left > right) || (top > bottom) || (right < 0) || (bottom < 0) ||
	    (left >= PICOSYSTEM_GRAPHICS_WIDTH) || (top >= PICOSYSTEM_GRAPHICS_HEIGHT)) {
		return;
	}

	left = TOY_FACTORY_MAX(left, 0);
	top = TOY_FACTORY_MAX(top, 0);
	right = TOY_FACTORY_MIN(right, PICOSYSTEM_GRAPHICS_WIDTH - 1);
	bottom = TOY_FACTORY_MIN(bottom, PICOSYSTEM_GRAPHICS_HEIGHT - 1);
	const uint8_t first_column = (uint8_t)(left / PICOSYSTEM_GARDEN_DAMAGE_TILE_PIXELS);
	const uint8_t final_column = (uint8_t)(right / PICOSYSTEM_GARDEN_DAMAGE_TILE_PIXELS);
	const uint8_t first_row = (uint8_t)(top / PICOSYSTEM_GARDEN_DAMAGE_TILE_PIXELS);
	const uint8_t final_row = (uint8_t)(bottom / PICOSYSTEM_GARDEN_DAMAGE_TILE_PIXELS);

	for (uint8_t row = first_row; row <= final_row; ++row) {
		for (uint8_t column = first_column; column <= final_column; ++column) {
			const uint32_t bit = UINT32_C(1) << column;
			if ((plan->row_masks[row] & bit) == 0U) {
				plan->row_masks[row] |= bit;
				++plan->dirty_tile_count;
			}
		}
	}
}

static void mark_garden_cell(struct picosystem_garden_damage_plan *plan, uint8_t column,
			     uint8_t row)
{
	const int32_t left =
		PICOSYSTEM_GARDEN_ORIGIN_X_PIXELS + (column * PICOSYSTEM_GARDEN_CELL_PIXELS);
	const int32_t top =
		PICOSYSTEM_GARDEN_CANOPY_TOP_PIXELS + (row * PICOSYSTEM_GARDEN_CELL_PIXELS);
	mark_pixel_bounds(plan, left, top, left + PICOSYSTEM_GARDEN_CELL_PIXELS - 1,
			  top + PICOSYSTEM_GARDEN_CELL_PIXELS - 1);
}

static bool garden_nodes_match(const struct picosystem_scene_garden_payload *presented,
			       const struct picosystem_scene_garden_payload *current,
			       uint16_t index)
{
	if ((index >= presented->node_count) || (index >= current->node_count)) {
		return false;
	}
	const struct picosystem_scene_garden_node *const left = &presented->nodes[index];
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	if (presented->leaf_condition[index] != current->leaf_condition[index]) {
		return false;
	}
#endif
	const struct picosystem_scene_garden_node *const right = &current->nodes[index];
	if ((left->x != right->x) || (left->y != right->y) ||
	    (left->parent_distance != right->parent_distance) ||
	    (left->growth_progress != right->growth_progress) || (left->style != right->style)) {
		return false;
	}
	if (left->parent_distance == 0U) {
		return true;
	}

	const struct picosystem_scene_garden_node *const left_parent =
		&presented->nodes[index - left->parent_distance];
	const struct picosystem_scene_garden_node *const right_parent =
		&current->nodes[index - right->parent_distance];
	return (left_parent->x == right_parent->x) && (left_parent->y == right_parent->y);
}

static void mark_garden_node(struct picosystem_garden_damage_plan *plan,
			     const struct picosystem_scene_garden_payload *garden, uint16_t index)
{
	struct picosystem_rect bounds;
	if (picosystem_garden_node_visual_bounds(garden, index, &bounds)) {
		mark_pixel_bounds(plan, bounds.x, bounds.y, bounds.x + bounds.width - 1,
				  bounds.y + bounds.height - 1);
	}
}

static void mark_changed_moisture(struct picosystem_garden_damage_plan *plan,
				  const struct picosystem_scene_garden_payload *presented,
				  const struct picosystem_scene_garden_payload *current)
{
	for (uint8_t row = 0U; row < PICOSYSTEM_GARDEN_SOIL_ROWS; ++row) {
		for (uint8_t column = 0U; column < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++column) {
			const uint16_t index =
				(uint16_t)(((uint16_t)row * PICOSYSTEM_GARDEN_GRID_COLUMNS) +
					   column);
			if (picosystem_garden_moisture_band_for_value(presented->moisture[index]) ==
			    picosystem_garden_moisture_band_for_value(current->moisture[index])) {
				continue;
			}
			mark_garden_cell(plan, column,
					 (uint8_t)(row + PICOSYSTEM_GARDEN_CANOPY_ROWS));
		}
	}
}

static void mark_changed_nodes(struct picosystem_garden_damage_plan *plan,
			       const struct picosystem_scene_garden_payload *presented,
			       const struct picosystem_scene_garden_payload *current)
{
	const uint16_t node_count = TOY_FACTORY_MAX(presented->node_count, current->node_count);
	for (uint16_t index = 0U; index < node_count; ++index) {
		if (garden_nodes_match(presented, current, index)) {
			continue;
		}
		if (index < presented->node_count) {
			mark_garden_node(plan, presented, index);
		}
		if (index < current->node_count) {
			mark_garden_node(plan, current, index);
		}
	}
}

static bool garden_seeds_match(const struct picosystem_scene_garden_payload *presented,
			       const struct picosystem_scene_garden_payload *current, uint8_t index)
{
	return (index < presented->seed_count) && (index < current->seed_count) &&
	       (presented->seeds[index].x == current->seeds[index].x) &&
	       (presented->seeds[index].style == current->seeds[index].style);
}

static void mark_garden_seed(struct picosystem_garden_damage_plan *plan,
			     const struct picosystem_scene_garden_seed *seed)
{
	struct picosystem_rect bounds;
	picosystem_garden_seed_visual_bounds(seed, &bounds);
	mark_pixel_bounds(plan, bounds.x, bounds.y, bounds.x + bounds.width - 1U,
			  bounds.y + bounds.height - 1U);
}

static void mark_changed_seeds(struct picosystem_garden_damage_plan *plan,
			       const struct picosystem_scene_garden_payload *presented,
			       const struct picosystem_scene_garden_payload *current)
{
	const uint8_t seed_count = TOY_FACTORY_MAX(presented->seed_count, current->seed_count);
	for (uint8_t index = 0U; index < seed_count; ++index) {
		if (garden_seeds_match(presented, current, index)) {
			continue;
		}
		if (index < presented->seed_count) {
			mark_garden_seed(plan, &presented->seeds[index]);
		}
		if (index < current->seed_count) {
			mark_garden_seed(plan, &current->seeds[index]);
		}
	}
}

static void mark_changed_sun(struct picosystem_garden_damage_plan *plan,
			     const struct picosystem_scene_garden_payload *presented,
			     const struct picosystem_scene_garden_payload *current)
{
	struct picosystem_rect presented_bounds;
	struct picosystem_rect current_bounds;
	const bool presented_visible =
		picosystem_garden_sun_visual_bounds(presented, &presented_bounds);
	const bool current_visible = picosystem_garden_sun_visual_bounds(current, &current_bounds);
	if ((!presented_visible && !current_visible) ||
	    (presented_visible && current_visible && (presented_bounds.x == current_bounds.x) &&
	     (presented_bounds.y == current_bounds.y))) {
		return;
	}
	if (presented_visible) {
		mark_pixel_bounds(plan, presented_bounds.x, presented_bounds.y,
				  presented_bounds.x + presented_bounds.width - 1U,
				  presented_bounds.y + presented_bounds.height - 1U);
	}
	if (current_visible) {
		mark_pixel_bounds(plan, current_bounds.x, current_bounds.y,
				  current_bounds.x + current_bounds.width - 1U,
				  current_bounds.y + current_bounds.height - 1U);
	}
}

static void mark_changed_cursor(struct picosystem_garden_damage_plan *plan,
				const struct picosystem_scene_garden_payload *presented,
				const struct picosystem_scene_garden_payload *current)
{
	if ((presented->cursor_column != current->cursor_column) ||
	    (presented->cursor_row != current->cursor_row) ||
	    (presented->selected_tool != current->selected_tool)) {
		mark_garden_cell(plan, presented->cursor_column, presented->cursor_row);
		mark_garden_cell(plan, current->cursor_column, current->cursor_row);
	}

	if ((presented->auto_target_valid == current->auto_target_valid) &&
	    ((current->auto_target_valid == 0U) ||
	     ((presented->auto_target_column == current->auto_target_column) &&
	      (presented->auto_target_row == current->auto_target_row)))) {
		return;
	}
	if (presented->auto_target_valid != 0U) {
		mark_garden_cell(plan, presented->auto_target_column, presented->auto_target_row);
	}
	if (current->auto_target_valid != 0U) {
		mark_garden_cell(plan, current->auto_target_column, current->auto_target_row);
	}
}

int picosystem_garden_damage_plan_build(const struct picosystem_scene_snapshot *presented,
					const struct picosystem_scene_snapshot *current,
					struct picosystem_garden_damage_plan *plan)
{
	if (plan == NULL) {
		return -EINVAL;
	}
	*plan = (struct picosystem_garden_damage_plan){0};

	int err = validate_garden_snapshot(presented);
	if (err == 0) {
		err = validate_garden_snapshot(current);
	}
	if (err != 0) {
		return err;
	}

	const struct picosystem_scene_garden_payload *const presented_garden =
		&presented->payload.garden;
	const struct picosystem_scene_garden_payload *const current_garden =
		&current->payload.garden;
	mark_changed_moisture(plan, presented_garden, current_garden);
	mark_changed_nodes(plan, presented_garden, current_garden);
	mark_changed_seeds(plan, presented_garden, current_garden);
	mark_changed_sun(plan, presented_garden, current_garden);
	mark_changed_cursor(plan, presented_garden, current_garden);

	if ((presented->sensor_entry_count % 100U) != (current->sensor_entry_count % 100U)) {
		/* The Fxx counter occupies the first two tiles of the second tile row. */
		mark_pixel_bounds(plan, 0, 8, 15, 15);
	}
	if (presented_garden->auto_gardener_enabled != current_garden->auto_gardener_enabled) {
		/* The AUTO indicator occupies two tiles at the right of the header. */
		mark_pixel_bounds(plan, 208, 8, 223, 15);
	}
	if ((presented_garden->rain_rate != 0U) != (current_garden->rain_rate != 0U)) {
		mark_pixel_bounds(plan, 176, 8, 191, 15);
	}
	return 0;
}

int picosystem_garden_damage_iterator_init(struct picosystem_garden_damage_iterator *iterator)
{
	if (iterator == NULL) {
		return -EINVAL;
	}
	*iterator = (struct picosystem_garden_damage_iterator){0};
	return 0;
}

int picosystem_garden_damage_next_region(const struct picosystem_garden_damage_plan *plan,
					 struct picosystem_garden_damage_iterator *iterator,
					 struct picosystem_rect *region)
{
	if ((plan == NULL) || (iterator == NULL) || (region == NULL) ||
	    (iterator->next_row > PICOSYSTEM_GARDEN_DAMAGE_TILE_ROWS) ||
	    (iterator->next_column > PICOSYSTEM_GARDEN_DAMAGE_TILE_COLUMNS)) {
		return -EINVAL;
	}

	while (iterator->next_row < PICOSYSTEM_GARDEN_DAMAGE_TILE_ROWS) {
		const uint8_t row = iterator->next_row;
		const uint32_t mask = plan->row_masks[row];
		if ((iterator->next_column == 0U) && (row > 0U) &&
		    (mask == plan->row_masks[row - 1U])) {
			++iterator->next_row;
			continue;
		}

		uint8_t first_column = iterator->next_column;
		while ((first_column < PICOSYSTEM_GARDEN_DAMAGE_TILE_COLUMNS) &&
		       ((mask & (UINT32_C(1) << first_column)) == 0U)) {
			++first_column;
		}
		if (first_column >= PICOSYSTEM_GARDEN_DAMAGE_TILE_COLUMNS) {
			++iterator->next_row;
			iterator->next_column = 0U;
			continue;
		}

		uint8_t end_column = (uint8_t)(first_column + 1U);
		while ((end_column < PICOSYSTEM_GARDEN_DAMAGE_TILE_COLUMNS) &&
		       ((mask & (UINT32_C(1) << end_column)) != 0U)) {
			++end_column;
		}
		uint8_t end_row = (uint8_t)(row + 1U);
		while ((end_row < PICOSYSTEM_GARDEN_DAMAGE_TILE_ROWS) &&
		       (plan->row_masks[end_row] == mask)) {
			++end_row;
		}

		*region = (struct picosystem_rect){
			.x = (uint16_t)(first_column * PICOSYSTEM_GARDEN_DAMAGE_TILE_PIXELS),
			.y = (uint16_t)(row * PICOSYSTEM_GARDEN_DAMAGE_TILE_PIXELS),
			.width = (uint16_t)((end_column - first_column) *
					    PICOSYSTEM_GARDEN_DAMAGE_TILE_PIXELS),
			.height =
				(uint16_t)((end_row - row) * PICOSYSTEM_GARDEN_DAMAGE_TILE_PIXELS),
		};
		iterator->next_column = end_column;
		if (iterator->next_column >= PICOSYSTEM_GARDEN_DAMAGE_TILE_COLUMNS) {
			++iterator->next_row;
			iterator->next_column = 0U;
		}
		return 1;
	}

	return 0;
}
