/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "garden_world.h"

#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define GARDEN_HASH_VERSION           UINT32_C(1)
#define GARDEN_DEFAULT_RANDOM_SEED    UINT32_C(0x746f7921)
#define GARDEN_FNV1A_OFFSET_BASIS     UINT32_C(2166136261)
#define GARDEN_FNV1A_PRIME            UINT32_C(16777619)
#define GARDEN_INITIAL_ENERGY         38U
#define GARDEN_INITIAL_WATER          32U
#define GARDEN_MAX_STORED_ENERGY      1024U
#define GARDEN_MAX_STORED_WATER       512U
#define GARDEN_SEED_NODE_COUNT        4U
#define GARDEN_MINIMUM_PLANT_SPACING  3U
#define GARDEN_AUTO_MINIMUM_PLANTS    5U
#define GARDEN_AUTO_WATER_THRESHOLD   24U
#define GARDEN_AUTO_ACTION_ROW        PICOSYSTEM_GARDEN_CANOPY_ROWS
#define GARDEN_LIGHT_MINIMUM          24U
#define GARDEN_WATER_FLOW_LIMIT       12U
#define GARDEN_WATER_DIFFUSION_LIMIT  4U
#define GARDEN_PRUNE_DISTANCE_SQUARED 25U

struct garden_species_config {
	uint8_t growth_period;
	uint8_t growth_energy_cost;
	uint8_t growth_water_cost;
	uint8_t root_uptake;
	uint8_t leaf_interval;
	uint8_t branch_interval;
	uint8_t first_branch_depth;
	uint8_t maximum_shoot_depth;
	uint8_t maximum_root_depth;
	uint8_t flower_depth;
	uint8_t leaf_shade;
	int8_t horizontal_tendency;
};

static const struct garden_species_config species_configs[PICOSYSTEM_GARDEN_SPECIES_COUNT] = {
	[PICOSYSTEM_GARDEN_SPECIES_FLOWER] =
		{
			.growth_period = 2U,
			.growth_energy_cost = 9U,
			.growth_water_cost = 5U,
			.root_uptake = 3U,
			.leaf_interval = 2U,
			.branch_interval = 0U,
			.first_branch_depth = UINT8_MAX,
			.maximum_shoot_depth = 15U,
			.maximum_root_depth = 10U,
			.flower_depth = 12U,
			.leaf_shade = 26U,
			.horizontal_tendency = 0,
		},
	[PICOSYSTEM_GARDEN_SPECIES_SHRUB] =
		{
			.growth_period = 3U,
			.growth_energy_cost = 8U,
			.growth_water_cost = 5U,
			.root_uptake = 3U,
			.leaf_interval = 1U,
			.branch_interval = 3U,
			.first_branch_depth = 4U,
			.maximum_shoot_depth = 12U,
			.maximum_root_depth = 9U,
			.flower_depth = 10U,
			.leaf_shade = 38U,
			.horizontal_tendency = 1,
		},
	[PICOSYSTEM_GARDEN_SPECIES_GROUND_COVER] =
		{
			.growth_period = 2U,
			.growth_energy_cost = 7U,
			.growth_water_cost = 4U,
			.root_uptake = 2U,
			.leaf_interval = 1U,
			.branch_interval = 2U,
			.first_branch_depth = 3U,
			.maximum_shoot_depth = 9U,
			.maximum_root_depth = 7U,
			.flower_depth = 8U,
			.leaf_shade = 32U,
			.horizontal_tendency = 3,
		},
};

static const char *const species_names[PICOSYSTEM_GARDEN_SPECIES_COUNT] = {
	[PICOSYSTEM_GARDEN_SPECIES_FLOWER] = "flower",
	[PICOSYSTEM_GARDEN_SPECIES_SHRUB] = "shrub",
	[PICOSYSTEM_GARDEN_SPECIES_GROUND_COVER] = "ground-cover",
};

static const char *const tool_names[PICOSYSTEM_GARDEN_TOOL_COUNT] = {
	[PICOSYSTEM_GARDEN_TOOL_FLOWER_SEED] = "flower-seed",
	[PICOSYSTEM_GARDEN_TOOL_SHRUB_SEED] = "shrub-seed",
	[PICOSYSTEM_GARDEN_TOOL_GROUND_COVER_SEED] = "ground-cover-seed",
	[PICOSYSTEM_GARDEN_TOOL_WATER] = "water",
	[PICOSYSTEM_GARDEN_TOOL_PRUNE] = "prune",
};

static const int8_t shoot_steps[][2] = {
	{-5, -5}, {-3, -6}, {0, -7}, {3, -6}, {5, -5},
};

static const int8_t root_steps[][2] = {
	{-4, 5},
	{0, 6},
	{4, 5},
};

_Static_assert(PICOSYSTEM_GARDEN_MAX_PLANTS <= UINT8_MAX, "garden plant indexes must fit one byte");
_Static_assert(PICOSYSTEM_GARDEN_MAX_NODES < PICOSYSTEM_GARDEN_NODE_NONE,
	       "garden node indexes must not equal the empty sentinel");
_Static_assert(PICOSYSTEM_GARDEN_GRID_COLUMNS *PICOSYSTEM_GARDEN_CELL_PIXELS <= 240U,
	       "garden columns must fit the display");
_Static_assert(PICOSYSTEM_GARDEN_CURSOR_ROWS *PICOSYSTEM_GARDEN_CELL_PIXELS <= 240U,
	       "garden rows must fit the display");
_Static_assert(GARDEN_SEED_NODE_COUNT <= PICOSYSTEM_GARDEN_MAX_NODES,
	       "one seedling must fit the node pool");

static uint8_t saturating_add_u8(uint8_t value, uint8_t increment)
{
	return (increment > (uint8_t)(UINT8_MAX - value)) ? UINT8_MAX
							  : (uint8_t)(value + increment);
}

static uint16_t saturating_add_u16_limit(uint16_t value, uint16_t increment, uint16_t limit)
{
	return (increment > (uint16_t)(limit - value)) ? limit : (uint16_t)(value + increment);
}

static uint32_t random_next(uint32_t *state)
{
	uint32_t value = *state;
	value ^= value << 13U;
	value ^= value >> 17U;
	value ^= value << 5U;
	*state = value;
	return value;
}

static uint16_t soil_index(uint8_t column, uint8_t row)
{
	return (uint16_t)(((uint16_t)row * PICOSYSTEM_GARDEN_GRID_COLUMNS) + column);
}

static uint16_t light_index(uint8_t column, uint8_t row)
{
	return (uint16_t)(((uint16_t)row * PICOSYSTEM_GARDEN_GRID_COLUMNS) + column);
}

static uint8_t column_center_x(uint8_t column)
{
	return (uint8_t)(PICOSYSTEM_GARDEN_ORIGIN_X_PIXELS +
			 (column * PICOSYSTEM_GARDEN_CELL_PIXELS) +
			 (PICOSYSTEM_GARDEN_CELL_PIXELS / 2U));
}

static uint8_t cursor_row_center_y(uint8_t row)
{
	return (uint8_t)(PICOSYSTEM_GARDEN_CANOPY_TOP_PIXELS +
			 (row * PICOSYSTEM_GARDEN_CELL_PIXELS) +
			 (PICOSYSTEM_GARDEN_CELL_PIXELS / 2U));
}

static bool node_kind_is_valid(uint8_t kind)
{
	return kind < PICOSYSTEM_GARDEN_NODE_KIND_COUNT;
}

static bool world_is_valid(const struct picosystem_garden_world *world)
{
	if ((world == NULL) || (world->node_count > PICOSYSTEM_GARDEN_MAX_NODES) ||
	    (world->plant_count > PICOSYSTEM_GARDEN_MAX_PLANTS) ||
	    (world->cursor_column >= PICOSYSTEM_GARDEN_GRID_COLUMNS) ||
	    (world->cursor_row >= PICOSYSTEM_GARDEN_CURSOR_ROWS) ||
	    (world->selected_tool >= PICOSYSTEM_GARDEN_TOOL_COUNT) ||
	    (world->auto_target_tool >= PICOSYSTEM_GARDEN_TOOL_COUNT) ||
	    (world->auto_target_column >= PICOSYSTEM_GARDEN_GRID_COLUMNS) ||
	    (world->auto_target_row >= PICOSYSTEM_GARDEN_CURSOR_ROWS) ||
	    (world->previous_horizontal_input < -1) || (world->previous_horizontal_input > 1) ||
	    (world->previous_vertical_input < -1) || (world->previous_vertical_input > 1)) {
		return false;
	}

	uint16_t plant_node_counts[PICOSYSTEM_GARDEN_MAX_PLANTS] = {0};
	for (uint16_t index = 0U; index < world->node_count; ++index) {
		const struct picosystem_garden_node *const node = &world->nodes[index];
		if ((node->plant_index >= world->plant_count) || !node_kind_is_valid(node->kind) ||
		    ((node->parent_index != PICOSYSTEM_GARDEN_NODE_NONE) &&
		     (node->parent_index >= index))) {
			return false;
		}
		++plant_node_counts[node->plant_index];
	}

	for (uint8_t index = 0U; index < world->plant_count; ++index) {
		const struct picosystem_garden_plant *const plant = &world->plants[index];
		if ((plant->species_id >= PICOSYSTEM_GARDEN_SPECIES_COUNT) ||
		    (plant->base_column >= PICOSYSTEM_GARDEN_GRID_COLUMNS) ||
		    (plant->base_node_index >= world->node_count) ||
		    (plant->node_count != plant_node_counts[index]) ||
		    (plant->random_state == 0U)) {
			return false;
		}
	}
	return world->random_state != 0U;
}

static struct picosystem_garden_node *append_node(struct picosystem_garden_world *world,
						  uint8_t plant_index, uint16_t parent_index,
						  uint8_t x, uint8_t y,
						  enum picosystem_garden_node_kind kind,
						  uint8_t depth, uint8_t flags)
{
	if (world->node_count >= PICOSYSTEM_GARDEN_MAX_NODES) {
		return NULL;
	}

	const uint16_t index = world->node_count;
	struct picosystem_garden_node *const node = &world->nodes[index];
	*node = (struct picosystem_garden_node){
		.parent_index = parent_index,
		.x = x,
		.y = y,
		.plant_index = plant_index,
		.depth = depth,
		.growth_progress = (parent_index == PICOSYSTEM_GARDEN_NODE_NONE) ? UINT8_MAX : 0U,
		.kind = (uint8_t)kind,
		.flags = flags,
	};
	++world->node_count;
	++world->plants[plant_index].node_count;
	if (parent_index != PICOSYSTEM_GARDEN_NODE_NONE) {
		++world->nodes[parent_index].child_count;
	}
	return node;
}

static bool plant_spacing_is_available(const struct picosystem_garden_world *world, uint8_t column)
{
	for (uint8_t index = 0U; index < world->plant_count; ++index) {
		const uint8_t other = world->plants[index].base_column;
		const uint8_t distance =
			(column >= other) ? (uint8_t)(column - other) : (uint8_t)(other - column);
		if (distance < GARDEN_MINIMUM_PLANT_SPACING) {
			return false;
		}
	}
	return true;
}

static uint8_t pixel_to_column(uint8_t x)
{
	if (x <= PICOSYSTEM_GARDEN_ORIGIN_X_PIXELS) {
		return 0U;
	}
	uint8_t column =
		(uint8_t)((x - PICOSYSTEM_GARDEN_ORIGIN_X_PIXELS) / PICOSYSTEM_GARDEN_CELL_PIXELS);
	if (column >= PICOSYSTEM_GARDEN_GRID_COLUMNS) {
		column = PICOSYSTEM_GARDEN_GRID_COLUMNS - 1U;
	}
	return column;
}

static uint8_t pixel_to_canopy_row(uint8_t y)
{
	if (y <= PICOSYSTEM_GARDEN_CANOPY_TOP_PIXELS) {
		return 0U;
	}
	uint8_t row = (uint8_t)((y - PICOSYSTEM_GARDEN_CANOPY_TOP_PIXELS) /
				PICOSYSTEM_GARDEN_CELL_PIXELS);
	if (row >= PICOSYSTEM_GARDEN_CANOPY_ROWS) {
		row = PICOSYSTEM_GARDEN_CANOPY_ROWS - 1U;
	}
	return row;
}

static uint8_t pixel_to_soil_row(uint8_t y)
{
	if (y <= PICOSYSTEM_GARDEN_SOIL_TOP_PIXELS) {
		return 0U;
	}
	uint8_t row =
		(uint8_t)((y - PICOSYSTEM_GARDEN_SOIL_TOP_PIXELS) / PICOSYSTEM_GARDEN_CELL_PIXELS);
	if (row >= PICOSYSTEM_GARDEN_SOIL_ROWS) {
		row = PICOSYSTEM_GARDEN_SOIL_ROWS - 1U;
	}
	return row;
}

static void update_node_growth_progress(struct picosystem_garden_world *world)
{
	const uint8_t increment = (uint8_t)((UINT8_MAX + PICOSYSTEM_GARDEN_NODE_GROWTH_TICKS - 1U) /
					    PICOSYSTEM_GARDEN_NODE_GROWTH_TICKS);
	for (uint16_t index = 0U; index < world->node_count; ++index) {
		struct picosystem_garden_node *const node = &world->nodes[index];
		node->growth_progress = saturating_add_u8(node->growth_progress, increment);
	}
}

static void move_water_between(uint8_t *source, uint8_t *destination, uint8_t limit,
			       uint8_t divisor)
{
	if ((*destination == UINT8_MAX) || (*source <= (uint16_t)*destination + 1U)) {
		return;
	}
	uint8_t transfer = (uint8_t)((*source - *destination) / divisor);
	if (transfer == 0U) {
		transfer = 1U;
	}
	if (transfer > limit) {
		transfer = limit;
	}
	const uint8_t capacity = (uint8_t)(UINT8_MAX - *destination);
	if (transfer > capacity) {
		transfer = capacity;
	}
	*source = (uint8_t)(*source - transfer);
	*destination = (uint8_t)(*destination + transfer);
}

static void update_moisture(struct picosystem_garden_world *world)
{
	for (uint8_t row = 0U; row < (PICOSYSTEM_GARDEN_SOIL_ROWS - 1U); ++row) {
		for (uint8_t column = 0U; column < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++column) {
			move_water_between(
				&world->moisture[soil_index(column, row)],
				&world->moisture[soil_index(column, (uint8_t)(row + 1U))],
				GARDEN_WATER_FLOW_LIMIT, 4U);
		}
	}

	const uint8_t first_column = (uint8_t)(world->ecology_tick_count & 1U);
	for (uint8_t row = 0U; row < PICOSYSTEM_GARDEN_SOIL_ROWS; ++row) {
		for (uint8_t column = first_column; column < (PICOSYSTEM_GARDEN_GRID_COLUMNS - 1U);
		     column = (uint8_t)(column + 2U)) {
			uint8_t *const left = &world->moisture[soil_index(column, row)];
			uint8_t *const right =
				&world->moisture[soil_index((uint8_t)(column + 1U), row)];
			if (*left >= *right) {
				move_water_between(left, right, GARDEN_WATER_DIFFUSION_LIMIT, 8U);
			} else {
				move_water_between(right, left, GARDEN_WATER_DIFFUSION_LIMIT, 8U);
			}
		}
	}

	if ((world->ecology_tick_count & 3U) == 0U) {
		for (uint8_t column = 0U; column < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++column) {
			uint8_t *const surface = &world->moisture[soil_index(column, 0U)];
			if (*surface > 0U) {
				--*surface;
			}
		}
	}
}

static void update_light(struct picosystem_garden_world *world)
{
	uint8_t shade[PICOSYSTEM_GARDEN_LIGHT_CELL_COUNT] = {0};
	for (uint16_t index = 0U; index < world->node_count; ++index) {
		const struct picosystem_garden_node *const node = &world->nodes[index];
		if ((node->kind != PICOSYSTEM_GARDEN_NODE_STEM) ||
		    ((node->flags & PICOSYSTEM_GARDEN_NODE_LEAF) == 0U) ||
		    (node->y >= PICOSYSTEM_GARDEN_SOIL_TOP_PIXELS)) {
			continue;
		}
		const uint8_t column = pixel_to_column(node->x);
		const uint8_t row = pixel_to_canopy_row(node->y);
		const struct garden_species_config *const species =
			&species_configs[world->plants[node->plant_index].species_id];
		shade[light_index(column, row)] =
			saturating_add_u8(shade[light_index(column, row)], species->leaf_shade);
		if (column > 0U) {
			shade[light_index((uint8_t)(column - 1U), row)] =
				saturating_add_u8(shade[light_index((uint8_t)(column - 1U), row)],
						  (uint8_t)(species->leaf_shade / 3U));
		}
		if ((column + 1U) < PICOSYSTEM_GARDEN_GRID_COLUMNS) {
			shade[light_index((uint8_t)(column + 1U), row)] =
				saturating_add_u8(shade[light_index((uint8_t)(column + 1U), row)],
						  (uint8_t)(species->leaf_shade / 3U));
		}
	}

	for (uint8_t column = 0U; column < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++column) {
		uint8_t intensity = UINT8_MAX;
		for (uint8_t row = 0U; row < PICOSYSTEM_GARDEN_CANOPY_ROWS; ++row) {
			const uint16_t index = light_index(column, row);
			world->light[index] = intensity;
			const uint8_t reduction = shade[index];
			intensity = (reduction >= (uint8_t)(intensity - GARDEN_LIGHT_MINIMUM))
					    ? GARDEN_LIGHT_MINIMUM
					    : (uint8_t)(intensity - reduction);
		}
	}
}

static void absorb_water_and_light(struct picosystem_garden_world *world)
{
	for (uint8_t plant_index = 0U; plant_index < world->plant_count; ++plant_index) {
		struct picosystem_garden_plant *const plant = &world->plants[plant_index];
		const struct garden_species_config *const species =
			&species_configs[plant->species_id];
		uint16_t gathered_energy = 0U;
		for (uint16_t node_index = 0U; node_index < world->node_count; ++node_index) {
			const struct picosystem_garden_node *const node = &world->nodes[node_index];
			if (node->plant_index != plant_index) {
				continue;
			}
			if (node->kind == PICOSYSTEM_GARDEN_NODE_ROOT) {
				const uint8_t column = pixel_to_column(node->x);
				const uint8_t row = pixel_to_soil_row(node->y);
				uint8_t *const moisture = &world->moisture[soil_index(column, row)];
				const uint8_t uptake = (*moisture >= species->root_uptake)
							       ? species->root_uptake
							       : *moisture;
				*moisture = (uint8_t)(*moisture - uptake);
				plant->stored_water = saturating_add_u16_limit(
					plant->stored_water, uptake, GARDEN_MAX_STORED_WATER);
			} else if ((node->flags & PICOSYSTEM_GARDEN_NODE_LEAF) != 0U) {
				const uint8_t column = pixel_to_column(node->x);
				const uint8_t row = pixel_to_canopy_row(node->y);
				gathered_energy =
					(uint16_t)(gathered_energy +
						   world->light[light_index(column, row)] / 64U);
			}
		}
		plant->stored_energy = saturating_add_u16_limit(
			plant->stored_energy, gathered_energy, GARDEN_MAX_STORED_ENERGY);
	}
}

static uint16_t find_next_tip(const struct picosystem_garden_world *world, uint8_t plant_index,
			      enum picosystem_garden_node_kind kind, uint16_t prior_index)
{
	if (world->node_count == 0U) {
		return PICOSYSTEM_GARDEN_NODE_NONE;
	}
	uint16_t start = 0U;
	if (prior_index < world->node_count) {
		start = (uint16_t)(prior_index + 1U);
		if (start == world->node_count) {
			start = 0U;
		}
	}
	for (uint16_t offset = 0U; offset < world->node_count; ++offset) {
		const uint16_t index = (uint16_t)((start + offset) % world->node_count);
		const struct picosystem_garden_node *const node = &world->nodes[index];
		if ((node->plant_index == plant_index) && (node->kind == kind) &&
		    ((node->flags & PICOSYSTEM_GARDEN_NODE_TIP) != 0U)) {
			return index;
		}
	}
	return PICOSYSTEM_GARDEN_NODE_NONE;
}

static bool node_position_is_available(const struct picosystem_garden_world *world, uint8_t x,
				       uint8_t y, enum picosystem_garden_node_kind kind)
{
	for (uint16_t index = 0U; index < world->node_count; ++index) {
		const struct picosystem_garden_node *const node = &world->nodes[index];
		if (node->kind != kind) {
			continue;
		}
		const int16_t delta_x = (int16_t)x - node->x;
		const int16_t delta_y = (int16_t)y - node->y;
		if (((delta_x * delta_x) + (delta_y * delta_y)) < 9) {
			return false;
		}
	}
	return true;
}

static bool candidate_position(const struct picosystem_garden_node *parent, int8_t delta_x,
			       int8_t delta_y, enum picosystem_garden_node_kind kind, uint8_t *x,
			       uint8_t *y)
{
	const int16_t candidate_x = (int16_t)parent->x + delta_x;
	const int16_t candidate_y = (int16_t)parent->y + delta_y;
	const int16_t minimum_x = PICOSYSTEM_GARDEN_ORIGIN_X_PIXELS;
	const int16_t maximum_x = PICOSYSTEM_GARDEN_ORIGIN_X_PIXELS +
				  (PICOSYSTEM_GARDEN_GRID_COLUMNS * PICOSYSTEM_GARDEN_CELL_PIXELS) -
				  1U;
	const int16_t minimum_y = (kind == PICOSYSTEM_GARDEN_NODE_STEM)
					  ? PICOSYSTEM_GARDEN_CANOPY_TOP_PIXELS
					  : PICOSYSTEM_GARDEN_SOIL_TOP_PIXELS;
	const int16_t maximum_y =
		(kind == PICOSYSTEM_GARDEN_NODE_STEM)
			? PICOSYSTEM_GARDEN_SOIL_TOP_PIXELS
			: PICOSYSTEM_GARDEN_SOIL_TOP_PIXELS +
				  (PICOSYSTEM_GARDEN_SOIL_ROWS * PICOSYSTEM_GARDEN_CELL_PIXELS) -
				  1U;
	if ((candidate_x < minimum_x) || (candidate_x > maximum_x) || (candidate_y < minimum_y) ||
	    (candidate_y > maximum_y)) {
		return false;
	}
	*x = (uint8_t)candidate_x;
	*y = (uint8_t)candidate_y;
	return true;
}

static int8_t shoot_step_score(const struct picosystem_garden_world *world,
			       const struct picosystem_garden_plant *plant,
			       const struct picosystem_garden_node *parent, uint8_t step_index)
{
	uint8_t x;
	uint8_t y;
	if (!candidate_position(parent, shoot_steps[step_index][0], shoot_steps[step_index][1],
				PICOSYSTEM_GARDEN_NODE_STEM, &x, &y)) {
		return INT8_MIN;
	}
	const uint8_t light = world->light[light_index(pixel_to_column(x), pixel_to_canopy_row(y))];
	const int8_t centered_step = (int8_t)step_index - 2;
	const int32_t absolute_step = (centered_step < 0) ? -(int32_t)centered_step : centered_step;
	int32_t score = light / 8U;
	score += (int32_t)centered_step * plant->lean;
	score += absolute_step * species_configs[plant->species_id].horizontal_tendency;
	if ((parent->flags & PICOSYSTEM_GARDEN_NODE_PRUNED) != 0U) {
		score += absolute_step * 8;
	}
	if (score < INT8_MIN) {
		return INT8_MIN;
	}
	return (score > INT8_MAX) ? INT8_MAX : (int8_t)score;
}

static int grow_shoot(struct picosystem_garden_world *world, uint8_t plant_index)
{
	struct picosystem_garden_plant *const plant = &world->plants[plant_index];
	const struct garden_species_config *const species = &species_configs[plant->species_id];
	const uint16_t tip_index = find_next_tip(world, plant_index, PICOSYSTEM_GARDEN_NODE_STEM,
						 plant->last_shoot_tip_index);
	if (tip_index == PICOSYSTEM_GARDEN_NODE_NONE) {
		return -ENOENT;
	}
	struct picosystem_garden_node *const parent = &world->nodes[tip_index];
	const bool branch_pending = (parent->flags & PICOSYSTEM_GARDEN_NODE_BRANCH_PENDING) != 0U;
	plant->last_shoot_tip_index = tip_index;
	if (parent->depth >= species->maximum_shoot_depth) {
		parent->flags &= (uint8_t)~PICOSYSTEM_GARDEN_NODE_TIP;
		if ((parent->depth >= species->flower_depth) &&
		    ((parent->flags & PICOSYSTEM_GARDEN_NODE_FLOWER) == 0U)) {
			parent->flags |= PICOSYSTEM_GARDEN_NODE_FLOWER;
			++world->bloom_count;
		}
		return 0;
	}

	uint8_t preferred = 2U;
	int8_t best_score = INT8_MIN;
	const uint8_t random_offset = (uint8_t)(random_next(&plant->random_state) % 5U);
	for (uint8_t offset = 0U; offset < 5U; ++offset) {
		const uint8_t step = (uint8_t)((random_offset + offset) % 5U);
		const int8_t score = shoot_step_score(world, plant, parent, step);
		if (score > best_score) {
			best_score = score;
			preferred = step;
		}
	}
	if (branch_pending) {
		const uint8_t base_x = column_center_x(plant->base_column);
		preferred = (parent->x <= base_x) ? 4U : 0U;
	}

	for (uint8_t attempt = 0U; attempt < 5U; ++attempt) {
		const uint8_t step = (uint8_t)((preferred + attempt) % 5U);
		uint8_t x;
		uint8_t y;
		if (!candidate_position(parent, shoot_steps[step][0], shoot_steps[step][1],
					PICOSYSTEM_GARDEN_NODE_STEM, &x, &y) ||
		    !node_position_is_available(world, x, y, PICOSYSTEM_GARDEN_NODE_STEM)) {
			continue;
		}

		uint8_t flags = PICOSYSTEM_GARDEN_NODE_TIP;
		const uint8_t depth = (uint8_t)(parent->depth + 1U);
		if ((depth % species->leaf_interval) == 0U) {
			flags |= PICOSYSTEM_GARDEN_NODE_LEAF;
		}
		parent->flags &=
			(uint8_t) ~(PICOSYSTEM_GARDEN_NODE_TIP | PICOSYSTEM_GARDEN_NODE_PRUNED |
				    PICOSYSTEM_GARDEN_NODE_BRANCH_PENDING);
		const bool schedule_branch = !branch_pending && (species->branch_interval != 0U) &&
					     (depth >= species->first_branch_depth) &&
					     (((depth - species->first_branch_depth) %
					       species->branch_interval) == 0U) &&
					     (parent->child_count == 0U);
		if (append_node(world, plant_index, tip_index, x, y, PICOSYSTEM_GARDEN_NODE_STEM,
				depth, flags) == NULL) {
			return -ENOSPC;
		}
		if (schedule_branch) {
			parent->flags |=
				PICOSYSTEM_GARDEN_NODE_TIP | PICOSYSTEM_GARDEN_NODE_BRANCH_PENDING;
		}
		return 0;
	}
	parent->flags &= (uint8_t)~PICOSYSTEM_GARDEN_NODE_TIP;
	return -ENOSPC;
}

static int grow_root(struct picosystem_garden_world *world, uint8_t plant_index)
{
	struct picosystem_garden_plant *const plant = &world->plants[plant_index];
	const struct garden_species_config *const species = &species_configs[plant->species_id];
	const uint16_t tip_index = find_next_tip(world, plant_index, PICOSYSTEM_GARDEN_NODE_ROOT,
						 plant->last_root_tip_index);
	if (tip_index == PICOSYSTEM_GARDEN_NODE_NONE) {
		return -ENOENT;
	}
	struct picosystem_garden_node *const parent = &world->nodes[tip_index];
	plant->last_root_tip_index = tip_index;
	if (parent->depth >= species->maximum_root_depth) {
		parent->flags &= (uint8_t)~PICOSYSTEM_GARDEN_NODE_TIP;
		return 0;
	}

	uint8_t preferred = 1U;
	uint8_t best_moisture = 0U;
	const uint8_t random_offset = (uint8_t)(random_next(&plant->random_state) % 3U);
	for (uint8_t offset = 0U; offset < 3U; ++offset) {
		const uint8_t step = (uint8_t)((random_offset + offset) % 3U);
		uint8_t x;
		uint8_t y;
		if (!candidate_position(parent, root_steps[step][0], root_steps[step][1],
					PICOSYSTEM_GARDEN_NODE_ROOT, &x, &y)) {
			continue;
		}
		const uint8_t moisture =
			world->moisture[soil_index(pixel_to_column(x), pixel_to_soil_row(y))];
		if (moisture >= best_moisture) {
			best_moisture = moisture;
			preferred = step;
		}
	}

	for (uint8_t attempt = 0U; attempt < 3U; ++attempt) {
		const uint8_t step = (uint8_t)((preferred + attempt) % 3U);
		uint8_t x;
		uint8_t y;
		if (!candidate_position(parent, root_steps[step][0], root_steps[step][1],
					PICOSYSTEM_GARDEN_NODE_ROOT, &x, &y) ||
		    !node_position_is_available(world, x, y, PICOSYSTEM_GARDEN_NODE_ROOT)) {
			continue;
		}
		parent->flags &= (uint8_t)~PICOSYSTEM_GARDEN_NODE_TIP;
		if (append_node(world, plant_index, tip_index, x, y, PICOSYSTEM_GARDEN_NODE_ROOT,
				(uint8_t)(parent->depth + 1U),
				PICOSYSTEM_GARDEN_NODE_TIP) == NULL) {
			return -ENOSPC;
		}
		return 0;
	}
	parent->flags &= (uint8_t)~PICOSYSTEM_GARDEN_NODE_TIP;
	return -ENOSPC;
}

static void grow_plants(struct picosystem_garden_world *world)
{
	for (uint8_t index = 0U; index < world->plant_count; ++index) {
		struct picosystem_garden_plant *const plant = &world->plants[index];
		const struct garden_species_config *const species =
			&species_configs[plant->species_id];
		++plant->age_ecology_ticks;
		if (plant->growth_cooldown > 0U) {
			--plant->growth_cooldown;
			continue;
		}
		const uint8_t vigor_discount = (plant->vigor > 0) ? 1U : 0U;
		const uint8_t energy_cost = (uint8_t)(species->growth_energy_cost - vigor_discount);
		if ((plant->stored_energy < energy_cost) ||
		    (plant->stored_water < species->growth_water_cost) ||
		    (world->node_count >= PICOSYSTEM_GARDEN_MAX_NODES)) {
			continue;
		}

		int err;
		if ((plant->growth_phase & 1U) == 0U) {
			err = grow_shoot(world, index);
		} else {
			err = grow_root(world, index);
		}
		++plant->growth_phase;
		if ((err == 0) || (err == -ENOSPC)) {
			plant->stored_energy = (uint16_t)(plant->stored_energy - energy_cost);
			plant->stored_water =
				(uint16_t)(plant->stored_water - species->growth_water_cost);
			plant->growth_cooldown = (uint8_t)(species->growth_period - 1U);
		}
	}
}

static void update_moisture_total(struct picosystem_garden_world *world)
{
	uint32_t total = 0U;
	for (uint16_t index = 0U; index < PICOSYSTEM_GARDEN_SOIL_CELL_COUNT; ++index) {
		total += world->moisture[index];
	}
	world->moisture_total = (total > UINT16_MAX) ? UINT16_MAX : (uint16_t)total;
}

static int apply_tool(struct picosystem_garden_world *world, enum picosystem_garden_tool tool,
		      uint8_t column, uint8_t row, bool automatic)
{
	int err;
	switch (tool) {
	case PICOSYSTEM_GARDEN_TOOL_FLOWER_SEED:
	case PICOSYSTEM_GARDEN_TOOL_SHRUB_SEED:
	case PICOSYSTEM_GARDEN_TOOL_GROUND_COVER_SEED:
		err = picosystem_garden_world_plant_seed(
			world, (enum picosystem_garden_species_id)tool, column);
		break;
	case PICOSYSTEM_GARDEN_TOOL_WATER:
		err = picosystem_garden_world_water(world, column, 96U);
		break;
	case PICOSYSTEM_GARDEN_TOOL_PRUNE:
		err = picosystem_garden_world_prune(world, column, row);
		break;
	default:
		return -EINVAL;
	}
	if (err == 0) {
		if (automatic) {
			++world->auto_action_count;
		} else {
			++world->manual_action_count;
		}
	}
	return err;
}

static uint8_t find_auto_plant_column(const struct picosystem_garden_world *world)
{
	const uint8_t start = (uint8_t)(2U + ((world->auto_decision_count * 5U) %
					      (PICOSYSTEM_GARDEN_GRID_COLUMNS - 4U)));
	for (uint8_t offset = 0U; offset < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++offset) {
		const uint8_t column = (uint8_t)((start + offset) % PICOSYSTEM_GARDEN_GRID_COLUMNS);
		if (plant_spacing_is_available(world, column)) {
			return column;
		}
	}
	return UINT8_MAX;
}

static uint8_t driest_plant_index(const struct picosystem_garden_world *world)
{
	uint8_t selected = UINT8_MAX;
	uint16_t least_water = UINT16_MAX;
	for (uint8_t offset = 0U; offset < world->plant_count; ++offset) {
		const uint8_t index =
			(uint8_t)((world->auto_decision_count + offset) % world->plant_count);
		if (world->plants[index].stored_water < least_water) {
			least_water = world->plants[index].stored_water;
			selected = index;
		}
	}
	return selected;
}

static uint16_t crowded_tip_index(const struct picosystem_garden_world *world)
{
	for (uint16_t offset = 0U; offset < world->node_count; ++offset) {
		const uint16_t index =
			(uint16_t)((world->auto_decision_count + offset) % world->node_count);
		const struct picosystem_garden_node *const node = &world->nodes[index];
		if ((node->kind == PICOSYSTEM_GARDEN_NODE_STEM) &&
		    ((node->flags & PICOSYSTEM_GARDEN_NODE_TIP) != 0U) && (node->depth >= 7U)) {
			const uint8_t light = world->light[light_index(
				pixel_to_column(node->x), pixel_to_canopy_row(node->y))];
			if (light < 112U) {
				return index;
			}
		}
	}
	return PICOSYSTEM_GARDEN_NODE_NONE;
}

static void choose_auto_target(struct picosystem_garden_world *world)
{
	++world->auto_decision_count;
	if (world->plant_count < GARDEN_AUTO_MINIMUM_PLANTS) {
		const uint8_t column = find_auto_plant_column(world);
		if (column != UINT8_MAX) {
			world->auto_target_column = column;
			world->auto_target_row = GARDEN_AUTO_ACTION_ROW;
			world->auto_target_tool =
				(uint8_t)(world->plant_count % PICOSYSTEM_GARDEN_SPECIES_COUNT);
			world->auto_target_valid = true;
			return;
		}
	}

	if (((world->auto_decision_count % 7U) == 0U) && (world->node_count > 0U)) {
		const uint16_t tip = crowded_tip_index(world);
		if (tip != PICOSYSTEM_GARDEN_NODE_NONE) {
			world->auto_target_column = pixel_to_column(world->nodes[tip].x);
			world->auto_target_row = pixel_to_canopy_row(world->nodes[tip].y);
			world->auto_target_tool = PICOSYSTEM_GARDEN_TOOL_PRUNE;
			world->auto_target_valid = true;
			return;
		}
	}

	if (world->plant_count > 0U) {
		const uint8_t plant_index = driest_plant_index(world);
		if ((plant_index != UINT8_MAX) &&
		    ((world->plants[plant_index].stored_water < GARDEN_AUTO_WATER_THRESHOLD) ||
		     ((world->auto_decision_count & 1U) == 0U))) {
			world->auto_target_column = world->plants[plant_index].base_column;
			world->auto_target_row = GARDEN_AUTO_ACTION_ROW;
			world->auto_target_tool = PICOSYSTEM_GARDEN_TOOL_WATER;
			world->auto_target_valid = true;
		}
	}
}

static void update_auto_gardener(struct picosystem_garden_world *world)
{
	if (!world->auto_gardener_enabled ||
	    ((world->logic_tick_count % PICOSYSTEM_GARDEN_AUTO_CURSOR_TICK_DIVISOR) != 0U)) {
		return;
	}
	if (!world->auto_target_valid) {
		choose_auto_target(world);
		return;
	}

	if (world->cursor_column < world->auto_target_column) {
		++world->cursor_column;
		return;
	}
	if (world->cursor_column > world->auto_target_column) {
		--world->cursor_column;
		return;
	}
	if (world->cursor_row < world->auto_target_row) {
		++world->cursor_row;
		return;
	}
	if (world->cursor_row > world->auto_target_row) {
		--world->cursor_row;
		return;
	}

	world->selected_tool = world->auto_target_tool;
	(void)apply_tool(world, (enum picosystem_garden_tool)world->auto_target_tool,
			 world->auto_target_column, world->auto_target_row, true);
	world->auto_target_valid = false;
}

static int update_cursor_input(struct picosystem_garden_world *world, int8_t horizontal,
			       int8_t vertical)
{
	if ((horizontal < -1) || (horizontal > 1) || (vertical < -1) || (vertical > 1)) {
		return -ERANGE;
	}
	const bool active = (horizontal != 0) || (vertical != 0);
	const bool changed = (horizontal != world->previous_horizontal_input) ||
			     (vertical != world->previous_vertical_input);
	world->previous_horizontal_input = horizontal;
	world->previous_vertical_input = vertical;
	if (!active) {
		world->cursor_repeat_ticks = 0U;
		return 0;
	}
	if (changed) {
		world->cursor_repeat_ticks = PICOSYSTEM_GARDEN_CURSOR_REPEAT_DELAY_TICKS;
		return picosystem_garden_world_move_cursor(world, horizontal, vertical);
	}
	if (world->cursor_repeat_ticks > 0U) {
		--world->cursor_repeat_ticks;
		return 0;
	}
	world->cursor_repeat_ticks = PICOSYSTEM_GARDEN_CURSOR_REPEAT_RATE_TICKS;
	return picosystem_garden_world_move_cursor(world, horizontal, vertical);
}

int picosystem_garden_world_reset(struct picosystem_garden_world *world, uint32_t random_seed)
{
	if (world == NULL) {
		return -EINVAL;
	}
	memset(world, 0, sizeof(*world));
	world->random_state = (random_seed == 0U) ? GARDEN_DEFAULT_RANDOM_SEED : random_seed;
	world->cursor_column = PICOSYSTEM_GARDEN_GRID_COLUMNS / 2U;
	world->cursor_row = PICOSYSTEM_GARDEN_CANOPY_ROWS;
	world->selected_tool = PICOSYSTEM_GARDEN_TOOL_FLOWER_SEED;
	world->auto_target_column = world->cursor_column;
	world->auto_target_row = world->cursor_row;
	world->auto_target_tool = world->selected_tool;
	memset(world->light, UINT8_MAX, sizeof(world->light));
	return 0;
}

int picosystem_garden_world_plant_seed(struct picosystem_garden_world *world,
				       enum picosystem_garden_species_id species_id, uint8_t column)
{
	if (!world_is_valid(world)) {
		return -EINVAL;
	}
	if ((species_id >= PICOSYSTEM_GARDEN_SPECIES_COUNT) ||
	    (column >= PICOSYSTEM_GARDEN_GRID_COLUMNS)) {
		return -ERANGE;
	}
	if (world->plant_count >= PICOSYSTEM_GARDEN_MAX_PLANTS) {
		return -ENOSPC;
	}
	if ((world->node_count + GARDEN_SEED_NODE_COUNT) > PICOSYSTEM_GARDEN_MAX_NODES) {
		return -ENOSPC;
	}
	if (!plant_spacing_is_available(world, column)) {
		return -EEXIST;
	}

	const uint8_t plant_index = world->plant_count;
	struct picosystem_garden_plant *const plant = &world->plants[plant_index];
	uint32_t plant_seed = random_next(&world->random_state) ^ ((uint32_t)column << 16U) ^
			      ((uint32_t)species_id << 8U);
	if (plant_seed == 0U) {
		plant_seed = GARDEN_DEFAULT_RANDOM_SEED;
	}
	*plant = (struct picosystem_garden_plant){
		.random_state = plant_seed,
		.base_node_index = world->node_count,
		.last_shoot_tip_index = PICOSYSTEM_GARDEN_NODE_NONE,
		.last_root_tip_index = PICOSYSTEM_GARDEN_NODE_NONE,
		.stored_energy = GARDEN_INITIAL_ENERGY,
		.stored_water = GARDEN_INITIAL_WATER,
		.node_count = 0U,
		.base_column = column,
		.species_id = (uint8_t)species_id,
		.lean = (int8_t)((int32_t)(random_next(&plant_seed) % 5U) - 2),
		.vigor = (int8_t)((int32_t)(random_next(&plant_seed) % 3U) - 1),
	};
	plant->random_state = plant_seed;
	++world->plant_count;

	const uint8_t x = column_center_x(column);
	const uint8_t soil_y = PICOSYSTEM_GARDEN_SOIL_TOP_PIXELS;
	const uint16_t base_index = world->node_count;
	(void)append_node(world, plant_index, PICOSYSTEM_GARDEN_NODE_NONE, x, soil_y,
			  PICOSYSTEM_GARDEN_NODE_STEM, 0U, 0U);
	(void)append_node(world, plant_index, base_index, x, (uint8_t)(soil_y - 6U),
			  PICOSYSTEM_GARDEN_NODE_STEM, 1U,
			  PICOSYSTEM_GARDEN_NODE_TIP | PICOSYSTEM_GARDEN_NODE_LEAF);
	(void)append_node(world, plant_index, base_index, (uint8_t)(x - 3U), (uint8_t)(soil_y + 5U),
			  PICOSYSTEM_GARDEN_NODE_ROOT, 1U, PICOSYSTEM_GARDEN_NODE_TIP);
	(void)append_node(world, plant_index, base_index, (uint8_t)(x + 3U), (uint8_t)(soil_y + 5U),
			  PICOSYSTEM_GARDEN_NODE_ROOT, 1U, PICOSYSTEM_GARDEN_NODE_TIP);
	return 0;
}

int picosystem_garden_world_water(struct picosystem_garden_world *world, uint8_t column,
				  uint8_t amount)
{
	if (!world_is_valid(world)) {
		return -EINVAL;
	}
	if ((column >= PICOSYSTEM_GARDEN_GRID_COLUMNS) || (amount == 0U)) {
		return -ERANGE;
	}
	for (uint8_t row = 0U; row < 2U; ++row) {
		for (int8_t offset = -1; offset <= 1; ++offset) {
			const int16_t target = (int16_t)column + offset;
			if ((target < 0) || (target >= (int16_t)PICOSYSTEM_GARDEN_GRID_COLUMNS)) {
				continue;
			}
			const uint8_t deposit = (offset == 0) ? amount : (uint8_t)(amount / 2U);
			uint8_t *const cell = &world->moisture[soil_index((uint8_t)target, row)];
			*cell = saturating_add_u8(*cell, deposit);
		}
	}
	update_moisture_total(world);
	return 0;
}

int picosystem_garden_world_prune(struct picosystem_garden_world *world, uint8_t column,
				  uint8_t row)
{
	if (!world_is_valid(world)) {
		return -EINVAL;
	}
	if ((column >= PICOSYSTEM_GARDEN_GRID_COLUMNS) || (row >= PICOSYSTEM_GARDEN_CURSOR_ROWS)) {
		return -ERANGE;
	}
	const int16_t target_x = column_center_x(column);
	const int16_t target_y = cursor_row_center_y(row);
	uint16_t best_index = PICOSYSTEM_GARDEN_NODE_NONE;
	uint32_t best_distance = UINT32_MAX;
	for (uint16_t index = 0U; index < world->node_count; ++index) {
		const struct picosystem_garden_node *const node = &world->nodes[index];
		if ((node->kind != PICOSYSTEM_GARDEN_NODE_STEM) ||
		    ((node->flags & PICOSYSTEM_GARDEN_NODE_TIP) == 0U)) {
			continue;
		}
		const int16_t delta_x = target_x - node->x;
		const int16_t delta_y = target_y - node->y;
		const uint32_t distance = (uint32_t)((delta_x * delta_x) + (delta_y * delta_y));
		if (distance < best_distance) {
			best_distance = distance;
			best_index = index;
		}
	}
	if ((best_index == PICOSYSTEM_GARDEN_NODE_NONE) ||
	    (best_distance > GARDEN_PRUNE_DISTANCE_SQUARED)) {
		return -ENOENT;
	}
	world->nodes[best_index].flags |= PICOSYSTEM_GARDEN_NODE_PRUNED;
	return 0;
}

int picosystem_garden_world_move_cursor(struct picosystem_garden_world *world, int8_t horizontal,
					int8_t vertical)
{
	if (!world_is_valid(world)) {
		return -EINVAL;
	}
	if ((horizontal < -1) || (horizontal > 1) || (vertical < -1) || (vertical > 1)) {
		return -ERANGE;
	}
	const int16_t column = (int16_t)world->cursor_column + horizontal;
	const int16_t row = (int16_t)world->cursor_row + vertical;
	if (column < 0) {
		world->cursor_column = 0U;
	} else if (column >= (int16_t)PICOSYSTEM_GARDEN_GRID_COLUMNS) {
		world->cursor_column = PICOSYSTEM_GARDEN_GRID_COLUMNS - 1U;
	} else {
		world->cursor_column = (uint8_t)column;
	}
	if (row < 0) {
		world->cursor_row = 0U;
	} else if (row >= (int16_t)PICOSYSTEM_GARDEN_CURSOR_ROWS) {
		world->cursor_row = PICOSYSTEM_GARDEN_CURSOR_ROWS - 1U;
	} else {
		world->cursor_row = (uint8_t)row;
	}
	return 0;
}

int picosystem_garden_world_cycle_tool(struct picosystem_garden_world *world)
{
	if (!world_is_valid(world)) {
		return -EINVAL;
	}
	world->selected_tool =
		(uint8_t)((world->selected_tool + 1U) % PICOSYSTEM_GARDEN_TOOL_COUNT);
	return 0;
}

int picosystem_garden_world_use_tool(struct picosystem_garden_world *world)
{
	if (!world_is_valid(world)) {
		return -EINVAL;
	}
	return apply_tool(world, (enum picosystem_garden_tool)world->selected_tool,
			  world->cursor_column, world->cursor_row, false);
}

int picosystem_garden_world_set_auto_gardener(struct picosystem_garden_world *world, bool enabled)
{
	if (!world_is_valid(world)) {
		return -EINVAL;
	}
	world->auto_gardener_enabled = enabled;
	world->auto_target_valid = false;
	return 0;
}

int picosystem_garden_world_step(struct picosystem_garden_world *world)
{
	return picosystem_garden_world_step_input(world, 0, 0);
}

int picosystem_garden_world_step_input(struct picosystem_garden_world *world, int8_t horizontal,
				       int8_t vertical)
{
	if (!world_is_valid(world)) {
		return -EINVAL;
	}
	const int input_err = update_cursor_input(world, horizontal, vertical);
	if (input_err != 0) {
		return input_err;
	}
	++world->logic_tick_count;
	update_node_growth_progress(world);
	update_auto_gardener(world);
	if ((world->logic_tick_count % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) != 0U) {
		return 0;
	}

	++world->ecology_tick_count;
	update_moisture(world);
	update_light(world);
	absorb_water_and_light(world);
	grow_plants(world);
	update_light(world);
	update_moisture_total(world);
	return 0;
}

const struct picosystem_garden_node *
picosystem_garden_world_node_at(const struct picosystem_garden_world *world, size_t index)
{
	return ((world != NULL) && (index < world->node_count)) ? &world->nodes[index] : NULL;
}

const struct picosystem_garden_plant *
picosystem_garden_world_plant_at(const struct picosystem_garden_world *world, size_t index)
{
	return ((world != NULL) && (index < world->plant_count)) ? &world->plants[index] : NULL;
}

static uint32_t fnv1a_byte(uint32_t hash, uint8_t value)
{
	return (hash ^ value) * GARDEN_FNV1A_PRIME;
}

static uint32_t fnv1a_u16(uint32_t hash, uint16_t value)
{
	hash = fnv1a_byte(hash, (uint8_t)value);
	return fnv1a_byte(hash, (uint8_t)(value >> 8U));
}

static uint32_t fnv1a_u32(uint32_t hash, uint32_t value)
{
	hash = fnv1a_u16(hash, (uint16_t)value);
	return fnv1a_u16(hash, (uint16_t)(value >> 16U));
}

uint32_t picosystem_garden_world_hash(const struct picosystem_garden_world *world)
{
	if (!world_is_valid(world)) {
		return 0U;
	}
	uint32_t hash = GARDEN_FNV1A_OFFSET_BASIS;
	hash = fnv1a_u32(hash, GARDEN_HASH_VERSION);
	hash = fnv1a_u32(hash, world->random_state);
	hash = fnv1a_u32(hash, world->logic_tick_count);
	hash = fnv1a_u32(hash, world->ecology_tick_count);
	hash = fnv1a_u32(hash, world->manual_action_count);
	hash = fnv1a_u32(hash, world->auto_decision_count);
	hash = fnv1a_u32(hash, world->auto_action_count);
	hash = fnv1a_u32(hash, world->bloom_count);
	hash = fnv1a_u16(hash, world->node_count);
	hash = fnv1a_u16(hash, world->moisture_total);
	hash = fnv1a_byte(hash, world->plant_count);
	hash = fnv1a_byte(hash, world->cursor_column);
	hash = fnv1a_byte(hash, world->cursor_row);
	hash = fnv1a_byte(hash, world->selected_tool);
	hash = fnv1a_byte(hash, world->auto_target_column);
	hash = fnv1a_byte(hash, world->auto_target_row);
	hash = fnv1a_byte(hash, world->auto_target_tool);
	hash = fnv1a_byte(hash, world->cursor_repeat_ticks);
	hash = fnv1a_byte(hash, (uint8_t)world->previous_horizontal_input);
	hash = fnv1a_byte(hash, (uint8_t)world->previous_vertical_input);
	hash = fnv1a_byte(hash, world->auto_gardener_enabled ? 1U : 0U);
	hash = fnv1a_byte(hash, world->auto_target_valid ? 1U : 0U);
	for (uint16_t index = 0U; index < PICOSYSTEM_GARDEN_SOIL_CELL_COUNT; ++index) {
		hash = fnv1a_byte(hash, world->moisture[index]);
	}
	for (uint16_t index = 0U; index < PICOSYSTEM_GARDEN_LIGHT_CELL_COUNT; ++index) {
		hash = fnv1a_byte(hash, world->light[index]);
	}
	for (uint8_t index = 0U; index < world->plant_count; ++index) {
		const struct picosystem_garden_plant *const plant = &world->plants[index];
		hash = fnv1a_u32(hash, plant->random_state);
		hash = fnv1a_u16(hash, plant->base_node_index);
		hash = fnv1a_u16(hash, plant->last_shoot_tip_index);
		hash = fnv1a_u16(hash, plant->last_root_tip_index);
		hash = fnv1a_u16(hash, plant->stored_energy);
		hash = fnv1a_u16(hash, plant->stored_water);
		hash = fnv1a_u16(hash, plant->age_ecology_ticks);
		hash = fnv1a_u16(hash, plant->node_count);
		hash = fnv1a_byte(hash, plant->base_column);
		hash = fnv1a_byte(hash, plant->growth_cooldown);
		hash = fnv1a_byte(hash, plant->growth_phase);
		hash = fnv1a_byte(hash, plant->species_id);
		hash = fnv1a_byte(hash, (uint8_t)plant->lean);
		hash = fnv1a_byte(hash, (uint8_t)plant->vigor);
	}
	for (uint16_t index = 0U; index < world->node_count; ++index) {
		const struct picosystem_garden_node *const node = &world->nodes[index];
		hash = fnv1a_u16(hash, node->parent_index);
		hash = fnv1a_byte(hash, node->x);
		hash = fnv1a_byte(hash, node->y);
		hash = fnv1a_byte(hash, node->plant_index);
		hash = fnv1a_byte(hash, node->depth);
		hash = fnv1a_byte(hash, node->growth_progress);
		hash = fnv1a_byte(hash, node->child_count);
		hash = fnv1a_byte(hash, node->kind);
		hash = fnv1a_byte(hash, node->flags);
	}
	return hash;
}

const char *picosystem_garden_species_name(enum picosystem_garden_species_id species_id)
{
	return (species_id < PICOSYSTEM_GARDEN_SPECIES_COUNT) ? species_names[species_id]
							      : "unknown";
}

const char *picosystem_garden_tool_name(enum picosystem_garden_tool tool)
{
	return (tool < PICOSYSTEM_GARDEN_TOOL_COUNT) ? tool_names[tool] : "unknown";
}
