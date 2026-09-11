/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "garden_world.h"

#include "garden_agent.h"
#include "garden_light.h"

#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define GARDEN_HASH_VERSION                      UINT32_C(4)
#define GARDEN_AGENT_MEMORY_HASH_TAG             UINT32_C(0x4d454d31)
#define GARDEN_DEFAULT_RANDOM_SEED               UINT32_C(0x746f7921)
#define GARDEN_FNV1A_OFFSET_BASIS                UINT32_C(2166136261)
#define GARDEN_FNV1A_PRIME                       UINT32_C(16777619)
#define GARDEN_INITIAL_ENERGY                    128U
#define GARDEN_INITIAL_WATER                     32U
#define GARDEN_MAX_STORED_ENERGY                 256U
#define GARDEN_MAX_STORED_WATER                  512U
#define GARDEN_SEED_NODE_COUNT                   4U
#define GARDEN_MINIMUM_PLANT_SPACING             3U
#define GARDEN_AUTO_MINIMUM_PLANTS               5U
#define GARDEN_AUTO_WATER_THRESHOLD              24U
#define GARDEN_AUTO_ACTION_ROW                   PICOSYSTEM_GARDEN_CANOPY_ROWS
#define GARDEN_WATER_FLOW_LIMIT                  12U
#define GARDEN_WATER_DIFFUSION_LIMIT             4U
#define GARDEN_PRUNE_DISTANCE_SQUARED            25U
#define GARDEN_ENERGY_MAINTENANCE_NODES_PER_UNIT 8U
#define GARDEN_WATER_MAINTENANCE_SHOOTS_PER_UNIT 8U
#define GARDEN_DECOMPOSITION_TIP_TICKS           48U
#define GARDEN_REPRODUCTION_COOLDOWN_TICKS       16U
#define GARDEN_REPRODUCTION_ENERGY_COST          48
#define GARDEN_REPRODUCTION_WATER_COST           24
#define GARDEN_REPRODUCTION_ENERGY_RESERVE       96
#define GARDEN_REPRODUCTION_WATER_RESERVE        32
#define GARDEN_REPRODUCTION_RESERVE_ENERGY_STEP  16
#define GARDEN_REPRODUCTION_RESERVE_WATER_STEP   4
#define GARDEN_OFFSPRING_INITIAL_ENERGY          64U
#define GARDEN_OFFSPRING_INITIAL_WATER           24U
#define GARDEN_SEED_MINIMUM_MOISTURE             12U
#define GARDEN_SEED_MINIMUM_LIGHT                80U
#define GARDEN_GENOME_TRAIT_COUNT                8U

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
_Static_assert(GARDEN_DECOMPOSITION_TIP_TICKS <= UINT8_MAX,
	       "decomposition countdown must fit one byte");
_Static_assert(PICOSYSTEM_GARDEN_MAX_SEEDS <= UINT8_MAX, "garden seed indexes must fit one byte");
_Static_assert(PICOSYSTEM_GARDEN_SEED_LIFETIME_TICKS <= UINT16_MAX,
	       "seed lifetime must fit its age counter");
_Static_assert(sizeof(struct picosystem_garden_genome) == GARDEN_GENOME_TRAIT_COUNT,
	       "garden genome must remain densely packed");
_Static_assert(sizeof(struct picosystem_garden_agent_telemetry) == 40U,
	       "garden agent telemetry layout changed");

static uint8_t saturating_add_u8(uint8_t value, uint8_t increment)
{
	return (increment > (uint8_t)(UINT8_MAX - value)) ? UINT8_MAX
							  : (uint8_t)(value + increment);
}

static uint16_t saturating_add_u16_limit(uint16_t value, uint16_t increment, uint16_t limit)
{
	return (increment > (uint16_t)(limit - value)) ? limit : (uint16_t)(value + increment);
}

static uint32_t saturating_add_u32(uint32_t value, uint32_t increment)
{
	return (increment > (UINT32_MAX - value)) ? UINT32_MAX : value + increment;
}

static bool plant_is_dead(const struct picosystem_garden_plant *plant)
{
	return (plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) != 0U;
}

static bool genome_trait_is_valid(int8_t trait)
{
	return (trait >= PICOSYSTEM_GARDEN_GENOME_TRAIT_MIN) &&
	       (trait <= PICOSYSTEM_GARDEN_GENOME_TRAIT_MAX);
}

static bool genome_is_valid(const struct picosystem_garden_genome *genome)
{
	return (genome != NULL) && genome_trait_is_valid(genome->growth_rate) &&
	       genome_trait_is_valid(genome->shoot_bias) &&
	       genome_trait_is_valid(genome->light_seeking) &&
	       genome_trait_is_valid(genome->water_seeking) &&
	       genome_trait_is_valid(genome->branching) && genome_trait_is_valid(genome->stature) &&
	       genome_trait_is_valid(genome->reserve_strategy) &&
	       genome_trait_is_valid(genome->dispersal);
}

static uint8_t adjusted_u8(uint8_t value, int8_t adjustment, uint8_t minimum, uint8_t maximum)
{
	int16_t adjusted = (int16_t)value + adjustment;
	if (adjusted < minimum) {
		adjusted = minimum;
	} else if (adjusted > maximum) {
		adjusted = maximum;
	}
	return (uint8_t)adjusted;
}

static uint8_t rounded_up_cost(uint16_t tissue_count, uint8_t tissue_per_unit)
{
	return (uint8_t)((tissue_count + tissue_per_unit - 1U) / tissue_per_unit);
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
	    (world->seed_count > PICOSYSTEM_GARDEN_MAX_SEEDS) ||
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
		    ((node->flags & (uint8_t)~PICOSYSTEM_GARDEN_NODE_VALID_FLAGS) != 0U) ||
		    (((node->flags & PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED) != 0U) &&
		     ((node->flags & PICOSYSTEM_GARDEN_NODE_FLOWER) == 0U)) ||
		    ((node->parent_index != PICOSYSTEM_GARDEN_NODE_NONE) &&
		     ((node->parent_index >= index) ||
		      (world->nodes[node->parent_index].plant_index != node->plant_index)))) {
			return false;
		}
		++plant_node_counts[node->plant_index];
	}

	for (uint8_t index = 0U; index < world->plant_count; ++index) {
		const struct picosystem_garden_plant *const plant = &world->plants[index];
		const bool dead = plant_is_dead(plant);
		if ((plant->species_id >= PICOSYSTEM_GARDEN_SPECIES_COUNT) ||
		    !genome_is_valid(&plant->genome) || (plant->lineage_id == 0U) ||
		    (plant->lineage_id > world->lineage_sequence) ||
		    ((plant->generation == 0U) != (plant->parent_lineage_id == 0U)) ||
		    (plant->generation > world->maximum_generation) ||
		    (plant->reproduction_cooldown > GARDEN_REPRODUCTION_COOLDOWN_TICKS) ||
		    (plant->base_column >= PICOSYSTEM_GARDEN_GRID_COLUMNS) ||
		    (plant->base_node_index >= world->node_count) ||
		    (world->nodes[plant->base_node_index].plant_index != index) ||
		    (world->nodes[plant->base_node_index].parent_index !=
		     PICOSYSTEM_GARDEN_NODE_NONE) ||
		    ((plant->last_shoot_tip_index != PICOSYSTEM_GARDEN_NODE_NONE) &&
		     ((plant->last_shoot_tip_index >= world->node_count) ||
		      (world->nodes[plant->last_shoot_tip_index].plant_index != index))) ||
		    ((plant->last_root_tip_index != PICOSYSTEM_GARDEN_NODE_NONE) &&
		     ((plant->last_root_tip_index >= world->node_count) ||
		      (world->nodes[plant->last_root_tip_index].plant_index != index))) ||
		    ((plant->flags & (uint8_t)~PICOSYSTEM_GARDEN_PLANT_VALID_FLAGS) != 0U) ||
		    (plant->stored_energy > GARDEN_MAX_STORED_ENERGY) ||
		    (plant->stored_water > GARDEN_MAX_STORED_WATER) ||
		    (dead && (plant->stress != PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD)) ||
		    (!dead && (plant->stress >= PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD)) ||
		    (plant->node_count == 0U) || (plant->node_count != plant_node_counts[index]) ||
		    (plant->random_state == 0U)) {
			return false;
		}
		for (uint8_t other = 0U; other < index; ++other) {
			if (world->plants[other].lineage_id == plant->lineage_id) {
				return false;
			}
		}
	}

	for (uint8_t index = 0U; index < world->seed_count; ++index) {
		const struct picosystem_garden_seed *const seed = &world->seeds[index];
		if (!genome_is_valid(&seed->genome) || (seed->parent_lineage_id == 0U) ||
		    (seed->parent_lineage_id > world->lineage_sequence) ||
		    (seed->generation == 0U) ||
		    (seed->age_ecology_ticks >= PICOSYSTEM_GARDEN_SEED_LIFETIME_TICKS) ||
		    (seed->column >= PICOSYSTEM_GARDEN_GRID_COLUMNS) ||
		    (seed->species_id >= PICOSYSTEM_GARDEN_SPECIES_COUNT) ||
		    (seed->visual_offset < PICOSYSTEM_GARDEN_GENOME_TRAIT_MIN) ||
		    (seed->visual_offset > PICOSYSTEM_GARDEN_GENOME_TRAIT_MAX)) {
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

static uint8_t plant_growth_period(const struct garden_species_config *species,
				   const struct picosystem_garden_genome *genome)
{
	return adjusted_u8(species->growth_period, (int8_t)-genome->growth_rate, 1U, 5U);
}

static uint8_t plant_branch_interval(const struct garden_species_config *species,
				     const struct picosystem_garden_genome *genome)
{
	if (species->branch_interval == 0U) {
		return 0U;
	}
	return adjusted_u8(species->branch_interval, (int8_t)-genome->branching, 1U, 6U);
}

static uint8_t plant_maximum_depth(const struct garden_species_config *species,
				   const struct picosystem_garden_genome *genome,
				   enum picosystem_garden_node_kind kind)
{
	if (kind == PICOSYSTEM_GARDEN_NODE_STEM) {
		return adjusted_u8(species->maximum_shoot_depth, genome->stature, 3U, 20U);
	}
	return adjusted_u8(species->maximum_root_depth, (int8_t)-genome->stature, 3U, 16U);
}

static int create_seedling(struct picosystem_garden_world *world,
			   enum picosystem_garden_species_id species_id, uint8_t column,
			   const struct picosystem_garden_genome *genome,
			   uint32_t parent_lineage_id, uint16_t generation, uint16_t initial_energy,
			   uint16_t initial_water, uint8_t *created_plant_index)
{
	if ((world == NULL) || !genome_is_valid(genome)) {
		return -EINVAL;
	}
	if ((species_id >= PICOSYSTEM_GARDEN_SPECIES_COUNT) ||
	    (column >= PICOSYSTEM_GARDEN_GRID_COLUMNS) ||
	    ((generation == 0U) != (parent_lineage_id == 0U)) ||
	    (parent_lineage_id > world->lineage_sequence) ||
	    (initial_energy > GARDEN_MAX_STORED_ENERGY) ||
	    (initial_water > GARDEN_MAX_STORED_WATER)) {
		return -ERANGE;
	}
	if ((world->plant_count >= PICOSYSTEM_GARDEN_MAX_PLANTS) ||
	    ((world->node_count + GARDEN_SEED_NODE_COUNT) > PICOSYSTEM_GARDEN_MAX_NODES)) {
		return -ENOSPC;
	}
	if (!plant_spacing_is_available(world, column)) {
		return -EEXIST;
	}
	if (world->lineage_sequence == UINT32_MAX) {
		return -EOVERFLOW;
	}

	const uint8_t plant_index = world->plant_count;
	struct picosystem_garden_plant *const plant = &world->plants[plant_index];
	uint32_t plant_seed = random_next(&world->random_state) ^ ((uint32_t)column << 16U) ^
			      ((uint32_t)species_id << 8U) ^ parent_lineage_id;
	if (plant_seed == 0U) {
		plant_seed = GARDEN_DEFAULT_RANDOM_SEED;
	}
	*plant = (struct picosystem_garden_plant){
		.random_state = plant_seed,
		.lineage_id = ++world->lineage_sequence,
		.parent_lineage_id = parent_lineage_id,
		.base_node_index = world->node_count,
		.last_shoot_tip_index = PICOSYSTEM_GARDEN_NODE_NONE,
		.last_root_tip_index = PICOSYSTEM_GARDEN_NODE_NONE,
		.stored_energy = initial_energy,
		.stored_water = initial_water,
		.generation = generation,
		.genome = *genome,
		.base_column = column,
		.species_id = (uint8_t)species_id,
		.lean = (int8_t)((int32_t)(random_next(&plant_seed) % 5U) - 2),
		.vigor = (int8_t)((int32_t)(random_next(&plant_seed) % 3U) - 1),
	};
	plant->random_state = plant_seed;
	++world->plant_count;
	if (generation > world->maximum_generation) {
		world->maximum_generation = generation;
	}

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
	if (created_plant_index != NULL) {
		*created_plant_index = plant_index;
	}
	return 0;
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
		if (plant_is_dead(&world->plants[node->plant_index])) {
			continue;
		}
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

static int update_light(struct picosystem_garden_world *world)
{
	uint8_t shade[PICOSYSTEM_GARDEN_LIGHT_CELL_COUNT] = {0};
	for (uint16_t index = 0U; index < world->node_count; ++index) {
		const struct picosystem_garden_node *const node = &world->nodes[index];
		const struct picosystem_garden_plant *const plant =
			&world->plants[node->plant_index];
		const uint8_t active_progress =
			plant_is_dead(plant) ? 1U : PICOSYSTEM_GARDEN_LEAF_ACTIVE_PROGRESS;
		if ((node->kind != PICOSYSTEM_GARDEN_NODE_STEM) ||
		    ((node->flags & PICOSYSTEM_GARDEN_NODE_LEAF) == 0U) ||
		    (node->growth_progress < active_progress) ||
		    (node->y >= PICOSYSTEM_GARDEN_SOIL_TOP_PIXELS)) {
			continue;
		}
		const uint8_t column = pixel_to_column(node->x);
		const uint8_t row = pixel_to_canopy_row(node->y);
		const struct garden_species_config *const species =
			&species_configs[plant->species_id];
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

	const struct picosystem_garden_sun sun =
		picosystem_garden_sun_at(world->ecology_tick_count);
	return picosystem_garden_light_solve(shade, &sun, world->light);
}

static void absorb_water_and_light(struct picosystem_garden_world *world)
{
	for (uint8_t plant_index = 0U; plant_index < world->plant_count; ++plant_index) {
		struct picosystem_garden_plant *const plant = &world->plants[plant_index];
		plant->last_energy_income = 0U;
		plant->last_water_income = 0U;
		if (plant_is_dead(plant)) {
			continue;
		}
		const struct garden_species_config *const species =
			&species_configs[plant->species_id];
		uint16_t gathered_energy = 0U;
		uint16_t gathered_water = 0U;
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
				gathered_water = (uint16_t)(gathered_water + uptake);
				plant->stored_water = saturating_add_u16_limit(
					plant->stored_water, uptake, GARDEN_MAX_STORED_WATER);
			} else if (((node->flags & PICOSYSTEM_GARDEN_NODE_LEAF) != 0U) &&
				   (node->growth_progress >=
				    PICOSYSTEM_GARDEN_LEAF_ACTIVE_PROGRESS)) {
				const uint8_t column = pixel_to_column(node->x);
				const uint8_t row = pixel_to_canopy_row(node->y);
				gathered_energy =
					(uint16_t)(gathered_energy +
						   world->light[light_index(column, row)] / 64U);
			}
		}
		plant->stored_energy = saturating_add_u16_limit(
			plant->stored_energy, gathered_energy, GARDEN_MAX_STORED_ENERGY);
		plant->last_energy_income =
			(gathered_energy > UINT8_MAX) ? UINT8_MAX : (uint8_t)gathered_energy;
		plant->last_water_income =
			(gathered_water > UINT8_MAX) ? UINT8_MAX : (uint8_t)gathered_water;
	}
}

static uint16_t plant_shoot_node_count(const struct picosystem_garden_world *world,
				       uint8_t plant_index)
{
	uint16_t count = 0U;
	for (uint16_t index = 0U; index < world->node_count; ++index) {
		const struct picosystem_garden_node *const node = &world->nodes[index];
		if ((node->plant_index == plant_index) &&
		    (node->kind == PICOSYSTEM_GARDEN_NODE_STEM)) {
			++count;
		}
	}
	return count;
}

static uint8_t plant_energy_maintenance_cost(const struct picosystem_garden_plant *plant)
{
	return rounded_up_cost(plant->node_count, GARDEN_ENERGY_MAINTENANCE_NODES_PER_UNIT);
}

static uint8_t plant_water_maintenance_cost(const struct picosystem_garden_world *world,
					    uint8_t plant_index)
{
	return rounded_up_cost(plant_shoot_node_count(world, plant_index),
			       GARDEN_WATER_MAINTENANCE_SHOOTS_PER_UNIT);
}

static bool debit_resource(uint16_t *stored, uint8_t cost)
{
	if (*stored < cost) {
		*stored = 0U;
		return false;
	}
	*stored = (uint16_t)(*stored - cost);
	return true;
}

static void mark_plant_dead(struct picosystem_garden_world *world, uint8_t plant_index)
{
	struct picosystem_garden_plant *const plant = &world->plants[plant_index];
	uint8_t maximum_depth = 0U;
	for (uint16_t index = 0U; index < world->node_count; ++index) {
		const struct picosystem_garden_node *const node = &world->nodes[index];
		if ((node->plant_index == plant_index) && (node->depth > maximum_depth)) {
			maximum_depth = node->depth;
		}
	}

	for (uint16_t index = 0U; index < world->node_count; ++index) {
		struct picosystem_garden_node *const node = &world->nodes[index];
		if (node->plant_index != plant_index) {
			continue;
		}
		node->flags &=
			(uint8_t) ~(PICOSYSTEM_GARDEN_NODE_TIP | PICOSYSTEM_GARDEN_NODE_PRUNED |
				    PICOSYSTEM_GARDEN_NODE_BRANCH_PENDING);
		const uint16_t countdown =
			GARDEN_DECOMPOSITION_TIP_TICKS + (uint16_t)(maximum_depth - node->depth);
		node->growth_progress = (countdown > UINT8_MAX) ? UINT8_MAX : (uint8_t)countdown;
	}

	plant->flags |= PICOSYSTEM_GARDEN_PLANT_DEAD;
	plant->stress = PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD;
	plant->stored_energy = 0U;
	plant->stored_water = 0U;
	plant->last_energy_income = 0U;
	plant->last_water_income = 0U;
	plant->growth_cooldown = 0U;
	plant->last_shoot_tip_index = PICOSYSTEM_GARDEN_NODE_NONE;
	plant->last_root_tip_index = PICOSYSTEM_GARDEN_NODE_NONE;
	world->death_count = saturating_add_u32(world->death_count, 1U);
}

static void update_plant_maintenance(struct picosystem_garden_world *world)
{
	if ((world->ecology_tick_count % PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR) != 0U) {
		return;
	}

	for (uint8_t plant_index = 0U; plant_index < world->plant_count; ++plant_index) {
		struct picosystem_garden_plant *const plant = &world->plants[plant_index];
		if (plant_is_dead(plant)) {
			continue;
		}

		plant->flags &= (uint8_t) ~(PICOSYSTEM_GARDEN_PLANT_ENERGY_SHORTAGE |
					    PICOSYSTEM_GARDEN_PLANT_WATER_SHORTAGE);
		const bool energy_available =
			debit_resource(&plant->stored_energy, plant_energy_maintenance_cost(plant));
		const bool water_available = debit_resource(
			&plant->stored_water, plant_water_maintenance_cost(world, plant_index));
		if (!energy_available) {
			plant->flags |= PICOSYSTEM_GARDEN_PLANT_ENERGY_SHORTAGE;
		}
		if (!water_available) {
			plant->flags |= PICOSYSTEM_GARDEN_PLANT_WATER_SHORTAGE;
		}

		if (energy_available && water_available) {
			if (plant->stress > 0U) {
				--plant->stress;
			}
			continue;
		}
		if (plant->stress < PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD) {
			++plant->stress;
		}
		if (plant->stress == PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD) {
			mark_plant_dead(world, plant_index);
		}
	}
}

static int reclaim_plant(struct picosystem_garden_world *world, uint8_t plant_index)
{
	if ((plant_index >= world->plant_count) || !plant_is_dead(&world->plants[plant_index])) {
		return -EINVAL;
	}

	const uint16_t old_node_count = world->node_count;
	const uint8_t old_plant_count = world->plant_count;
	const uint16_t reclaimed_node_count = world->plants[plant_index].node_count;
	uint8_t node_remap[PICOSYSTEM_GARDEN_MAX_NODES] = {0};
	uint16_t write_node = 0U;
	for (uint16_t read_node = 0U; read_node < old_node_count; ++read_node) {
		struct picosystem_garden_node node = world->nodes[read_node];
		if (node.plant_index == plant_index) {
			continue;
		}
		if (write_node > UINT8_MAX) {
			return -ERANGE;
		}
		node_remap[read_node] = (uint8_t)write_node;
		if (node.parent_index != PICOSYSTEM_GARDEN_NODE_NONE) {
			node.parent_index = node_remap[node.parent_index];
		}
		if (node.plant_index > plant_index) {
			--node.plant_index;
		}
		world->nodes[write_node] = node;
		++write_node;
	}
	if ((old_node_count - write_node) != reclaimed_node_count) {
		return -EINVAL;
	}
	memset(&world->nodes[write_node], 0,
	       (old_node_count - write_node) * sizeof(world->nodes[0]));

	uint8_t write_plant = 0U;
	for (uint8_t read_plant = 0U; read_plant < old_plant_count; ++read_plant) {
		if (read_plant == plant_index) {
			continue;
		}
		struct picosystem_garden_plant plant = world->plants[read_plant];
		plant.base_node_index = node_remap[plant.base_node_index];
		if (plant.last_shoot_tip_index != PICOSYSTEM_GARDEN_NODE_NONE) {
			plant.last_shoot_tip_index = node_remap[plant.last_shoot_tip_index];
		}
		if (plant.last_root_tip_index != PICOSYSTEM_GARDEN_NODE_NONE) {
			plant.last_root_tip_index = node_remap[plant.last_root_tip_index];
		}
		world->plants[write_plant] = plant;
		++write_plant;
	}
	memset(&world->plants[write_plant], 0,
	       (old_plant_count - write_plant) * sizeof(world->plants[0]));
	world->node_count = write_node;
	world->plant_count = write_plant;
	world->reclaimed_plant_count = saturating_add_u32(world->reclaimed_plant_count, 1U);
	world->reclaimed_node_count =
		saturating_add_u32(world->reclaimed_node_count, reclaimed_node_count);
	return 0;
}

static int update_decomposition(struct picosystem_garden_world *world)
{
	for (uint16_t node_index = 0U; node_index < world->node_count; ++node_index) {
		struct picosystem_garden_node *const node = &world->nodes[node_index];
		if (plant_is_dead(&world->plants[node->plant_index]) &&
		    (node->growth_progress > 0U)) {
			--node->growth_progress;
		}
	}

	uint8_t plant_index = 0U;
	while (plant_index < world->plant_count) {
		if (!plant_is_dead(&world->plants[plant_index])) {
			++plant_index;
			continue;
		}
		bool visible_tissue = false;
		for (uint16_t node_index = 0U; node_index < world->node_count; ++node_index) {
			const struct picosystem_garden_node *const node = &world->nodes[node_index];
			if ((node->plant_index == plant_index) && (node->growth_progress > 0U)) {
				visible_tissue = true;
				break;
			}
		}
		if (visible_tissue) {
			++plant_index;
			continue;
		}
		const int err = reclaim_plant(world, plant_index);
		if (err != 0) {
			return err;
		}
	}
	return 0;
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

static void inspect_candidate_neighborhood(const struct picosystem_garden_world *world,
					   uint8_t plant_index,
					   enum picosystem_garden_node_kind kind,
					   struct picosystem_garden_agent_candidate *candidate)
{
	uint32_t minimum_distance_squared = UINT32_MAX;
	for (uint16_t index = 0U; index < world->node_count; ++index) {
		const struct picosystem_garden_node *const node = &world->nodes[index];
		if (node->kind != kind) {
			continue;
		}
		const int16_t delta_x = (int16_t)candidate->x - node->x;
		const int16_t delta_y = (int16_t)candidate->y - node->y;
		const uint32_t distance_squared =
			(uint32_t)((delta_x * delta_x) + (delta_y * delta_y));
		if (distance_squared < minimum_distance_squared) {
			minimum_distance_squared = distance_squared;
		}
		if (distance_squared >= 9U) {
			continue;
		}
		candidate->flags |= (node->plant_index == plant_index)
					    ? PICOSYSTEM_GARDEN_AGENT_CANDIDATE_OWN_NEAR
					    : PICOSYSTEM_GARDEN_AGENT_CANDIDATE_FOREIGN_NEAR;
	}

	if (minimum_distance_squared >= 9U) {
		candidate->flags |= PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE;
	}
	candidate->clearance_squared = (minimum_distance_squared > UINT8_MAX)
					       ? UINT8_MAX
					       : (uint8_t)minimum_distance_squared;
}

static void build_agent_observation(const struct picosystem_garden_world *world,
				    uint8_t plant_index, uint16_t tip_index,
				    uint32_t decision_nonce,
				    struct picosystem_garden_agent_observation *observation)
{
	const struct picosystem_garden_plant *const plant = &world->plants[plant_index];
	const struct garden_species_config *const species = &species_configs[plant->species_id];
	const struct picosystem_garden_node *const tip = &world->nodes[tip_index];
	const struct picosystem_garden_sun sun =
		picosystem_garden_sun_at(world->ecology_tick_count);
	*observation = (struct picosystem_garden_agent_observation){
		.decision_nonce = decision_nonce,
		.tip_index = tip_index,
		.stored_energy = plant->stored_energy,
		.stored_water = plant->stored_water,
		.age_ecology_ticks = plant->age_ecology_ticks,
		.plant_node_count = plant->node_count,
		.version = PICOSYSTEM_GARDEN_AGENT_OBSERVATION_VERSION,
		.plant_index = plant_index,
		.species_id = plant->species_id,
		.tissue_kind = tip->kind,
		.depth = tip->depth,
		.tip_x = tip->x,
		.tip_y = tip->y,
		.tip_light = (tip->kind == PICOSYSTEM_GARDEN_NODE_STEM)
				     ? world->light[light_index(pixel_to_column(tip->x),
								pixel_to_canopy_row(tip->y))]
				     : 0U,
		.tip_moisture = (tip->kind == PICOSYSTEM_GARDEN_NODE_ROOT)
					? world->moisture[soil_index(pixel_to_column(tip->x),
								     pixel_to_soil_row(tip->y))]
					: 0U,
		.base_x = column_center_x(plant->base_column),
		.maximum_depth = plant_maximum_depth(species, &plant->genome,
						     (enum picosystem_garden_node_kind)tip->kind),
		.flower_depth = species->flower_depth,
		.growth_phase = plant->growth_phase,
		.growth_cooldown = plant->growth_cooldown,
		.tip_flags = tip->flags,
		.lean = plant->lean,
		.vigor = plant->vigor,
		.horizontal_tendency = species->horizontal_tendency,
		.candidate_count = (tip->kind == PICOSYSTEM_GARDEN_NODE_STEM) ? 5U : 3U,
		.sun_phase = sun.phase,
		.sun_strength = sun.strength,
		.sun_ray_step_x_q4 = sun.ray_step_x_q4,
		.stress = plant->stress,
		.maintenance_phase = (uint8_t)(world->ecology_tick_count %
					       PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR),
		.last_energy_income = plant->last_energy_income,
		.last_water_income = plant->last_water_income,
		.plant_flags = plant->flags,
		.genome = plant->genome,
	};

	if (tip->parent_index != PICOSYSTEM_GARDEN_NODE_NONE) {
		const struct picosystem_garden_node *const parent =
			&world->nodes[tip->parent_index];
		observation->parent_delta_x = (int16_t)tip->x - parent->x;
		observation->parent_delta_y = (int16_t)tip->y - parent->y;
	}

	for (uint16_t index = 0U; index < world->node_count; ++index) {
		const struct picosystem_garden_node *const node = &world->nodes[index];
		if (node->plant_index != plant_index) {
			continue;
		}
		if (node->kind == PICOSYSTEM_GARDEN_NODE_STEM) {
			++observation->shoot_node_count;
		} else {
			++observation->root_node_count;
		}
		if ((node->flags & PICOSYSTEM_GARDEN_NODE_LEAF) != 0U) {
			++observation->leaf_node_count;
		}
		if ((node->flags & PICOSYSTEM_GARDEN_NODE_TIP) != 0U) {
			++observation->active_tip_count;
		}
	}

	const int8_t(*steps)[2] =
		(tip->kind == PICOSYSTEM_GARDEN_NODE_STEM) ? shoot_steps : root_steps;
	for (uint8_t index = 0U; index < observation->candidate_count; ++index) {
		struct picosystem_garden_agent_candidate *const candidate =
			&observation->candidates[index];
		candidate->delta_x = steps[index][0];
		candidate->delta_y = steps[index][1];
		if (!candidate_position(tip, candidate->delta_x, candidate->delta_y, tip->kind,
					&candidate->x, &candidate->y)) {
			continue;
		}
		candidate->flags = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS;
		if (tip->kind == PICOSYSTEM_GARDEN_NODE_STEM) {
			candidate->light = world->light[light_index(
				pixel_to_column(candidate->x), pixel_to_canopy_row(candidate->y))];
		} else {
			candidate->moisture = world->moisture[soil_index(
				pixel_to_column(candidate->x), pixel_to_soil_row(candidate->y))];
		}
		inspect_candidate_neighborhood(world, plant_index, tip->kind, candidate);
	}
	observation->maintenance_energy_cost = plant_energy_maintenance_cost(plant);
	observation->maintenance_water_cost = plant_water_maintenance_cost(world, plant_index);
}

int picosystem_garden_agent_observe_tip(const struct picosystem_garden_world *world,
					uint8_t plant_index, uint16_t tip_index,
					uint32_t decision_nonce,
					struct picosystem_garden_agent_observation *observation)
{
	if (observation == NULL) {
		return -EINVAL;
	}
	*observation = (struct picosystem_garden_agent_observation){0};
	if (!world_is_valid(world)) {
		return -EINVAL;
	}
	if ((plant_index >= world->plant_count) || (tip_index >= world->node_count)) {
		return -ERANGE;
	}
	const struct picosystem_garden_node *const tip = &world->nodes[tip_index];
	if ((tip->plant_index != plant_index) ||
	    ((tip->flags & PICOSYSTEM_GARDEN_NODE_TIP) == 0U)) {
		return -ENOENT;
	}

	build_agent_observation(world, plant_index, tip_index, decision_nonce, observation);
	return 0;
}

static bool proposal_is_valid(const struct picosystem_garden_agent_observation *observation,
			      const struct picosystem_garden_agent_proposal *proposal)
{
	if ((proposal->tip_index != observation->tip_index) ||
	    (proposal->action >= PICOSYSTEM_GARDEN_AGENT_ACTION_COUNT)) {
		return false;
	}
	if (proposal->action != PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND) {
		return proposal->candidate_count == 0U;
	}
	if (proposal->candidate_count != observation->candidate_count) {
		return false;
	}

	uint8_t visited = 0U;
	for (uint8_t index = 0U; index < proposal->candidate_count; ++index) {
		const uint8_t candidate_index = proposal->candidate_order[index];
		if ((candidate_index >= observation->candidate_count) ||
		    ((visited & (uint8_t)(1U << candidate_index)) != 0U)) {
			return false;
		}
		visited |= (uint8_t)(1U << candidate_index);
	}
	return true;
}

static int finish_tip(struct picosystem_garden_world *world, uint16_t tip_index)
{
	struct picosystem_garden_node *const tip = &world->nodes[tip_index];
	tip->flags &= (uint8_t)~PICOSYSTEM_GARDEN_NODE_TIP;
	const struct picosystem_garden_plant *const plant = &world->plants[tip->plant_index];
	const struct garden_species_config *const species = &species_configs[plant->species_id];
	if ((tip->kind == PICOSYSTEM_GARDEN_NODE_STEM) && (tip->depth >= species->flower_depth) &&
	    ((tip->flags & PICOSYSTEM_GARDEN_NODE_FLOWER) == 0U)) {
		tip->flags |= PICOSYSTEM_GARDEN_NODE_FLOWER;
		++world->bloom_count;
	}
	return 0;
}

static int extend_tip(struct picosystem_garden_world *world, uint8_t plant_index,
		      const struct picosystem_garden_agent_observation *observation,
		      const struct picosystem_garden_agent_proposal *proposal)
{
	struct picosystem_garden_node *const parent = &world->nodes[observation->tip_index];
	const struct garden_species_config *const species =
		&species_configs[world->plants[plant_index].species_id];
	const uint8_t branch_interval =
		plant_branch_interval(species, &world->plants[plant_index].genome);
	const bool branch_pending = (parent->flags & PICOSYSTEM_GARDEN_NODE_BRANCH_PENDING) != 0U;
	for (uint8_t attempt = 0U; attempt < proposal->candidate_count; ++attempt) {
		const struct picosystem_garden_agent_candidate *const candidate =
			&observation->candidates[proposal->candidate_order[attempt]];
		if ((candidate->flags & PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE) == 0U) {
			continue;
		}

		const uint8_t depth = (uint8_t)(parent->depth + 1U);
		uint8_t flags = PICOSYSTEM_GARDEN_NODE_TIP;
		if ((parent->kind == PICOSYSTEM_GARDEN_NODE_STEM) &&
		    ((depth % species->leaf_interval) == 0U)) {
			flags |= PICOSYSTEM_GARDEN_NODE_LEAF;
		}
		if (parent->kind == PICOSYSTEM_GARDEN_NODE_STEM) {
			parent->flags &= (uint8_t) ~(PICOSYSTEM_GARDEN_NODE_TIP |
						     PICOSYSTEM_GARDEN_NODE_PRUNED |
						     PICOSYSTEM_GARDEN_NODE_BRANCH_PENDING);
		} else {
			parent->flags &= (uint8_t)~PICOSYSTEM_GARDEN_NODE_TIP;
		}

		const bool schedule_branch =
			(parent->kind == PICOSYSTEM_GARDEN_NODE_STEM) && !branch_pending &&
			(branch_interval != 0U) && (depth >= species->first_branch_depth) &&
			(((depth - species->first_branch_depth) % branch_interval) == 0U) &&
			(parent->child_count == 0U);
		if (append_node(world, plant_index, observation->tip_index, candidate->x,
				candidate->y, (enum picosystem_garden_node_kind)parent->kind, depth,
				flags) == NULL) {
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

static int execute_agent_decision(struct picosystem_garden_world *world, uint8_t plant_index,
				  const struct picosystem_garden_agent_observation *observation,
				  const struct picosystem_garden_agent_decision *decision)
{
	if (decision->proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT) {
		return -EAGAIN;
	}
	if (decision->proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP) {
		return finish_tip(world, observation->tip_index);
	}
	return extend_tip(world, plant_index, observation, &decision->proposal);
}

static void update_agent_telemetry(struct picosystem_garden_agent_telemetry *telemetry,
				   const struct picosystem_garden_agent_observation *observation,
				   const struct picosystem_garden_agent_decision *decision)
{
	telemetry->decision_count = saturating_add_u32(telemetry->decision_count, 1U);
	if (decision->proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND) {
		telemetry->extend_count = saturating_add_u32(telemetry->extend_count, 1U);
		if (observation->tissue_kind == PICOSYSTEM_GARDEN_NODE_ROOT) {
			telemetry->root_extend_count =
				saturating_add_u32(telemetry->root_extend_count, 1U);
		} else {
			telemetry->shoot_extend_count =
				saturating_add_u32(telemetry->shoot_extend_count, 1U);
		}
	} else if (decision->proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT) {
		telemetry->wait_count = saturating_add_u32(telemetry->wait_count, 1U);
	} else {
		telemetry->finish_count = saturating_add_u32(telemetry->finish_count, 1U);
	}
	if (observation->tissue_kind == PICOSYSTEM_GARDEN_NODE_ROOT) {
		telemetry->root_decision_count =
			saturating_add_u32(telemetry->root_decision_count, 1U);
	} else {
		telemetry->shoot_decision_count =
			saturating_add_u32(telemetry->shoot_decision_count, 1U);
	}
	telemetry->last_priority = decision->proposal.priority;
	telemetry->last_tip_x = observation->tip_x;
	telemetry->last_tip_y = observation->tip_y;
	telemetry->last_tip_depth = observation->depth;
	telemetry->last_tissue_kind = observation->tissue_kind;
	telemetry->last_action = decision->proposal.action;
}

static void record_agent_decision(struct picosystem_garden_world *world, uint8_t plant_index,
				  const struct picosystem_garden_agent_observation *observation,
				  const struct picosystem_garden_agent_decision *decision)
{
	update_agent_telemetry(&world->plants[plant_index].agent_telemetry, observation, decision);
	update_agent_telemetry(&world->agent_telemetry, observation, decision);
}

static int grow_phased_tip(struct picosystem_garden_world *world, uint8_t plant_index,
			   enum picosystem_garden_node_kind kind,
			   const struct picosystem_garden_agent_policy *policy, bool *advance_phase)
{
	*advance_phase = false;
	struct picosystem_garden_plant *const plant = &world->plants[plant_index];
	uint16_t *const previous_tip = (kind == PICOSYSTEM_GARDEN_NODE_STEM)
					       ? &plant->last_shoot_tip_index
					       : &plant->last_root_tip_index;
	const uint16_t tip_index = find_next_tip(world, plant_index, kind, *previous_tip);
	if (tip_index == PICOSYSTEM_GARDEN_NODE_NONE) {
		*advance_phase = true;
		return -ENOENT;
	}

	struct picosystem_garden_agent_observation observation;
	build_agent_observation(world, plant_index, tip_index, 0U, &observation);
	uint32_t next_random_state = plant->random_state;
	if (observation.depth < observation.maximum_depth) {
		observation.decision_nonce = random_next(&next_random_state);
	}
	const struct picosystem_garden_agent_memory current_memory = plant->agent_memory;
	struct picosystem_garden_agent_decision decision;
	int err = picosystem_garden_agent_decide(policy, &observation, &current_memory, &decision);
	if (err != 0) {
		return err;
	}
	if (!proposal_is_valid(&observation, &decision.proposal)) {
		return -ERANGE;
	}

	/* Policy output is transactional: only a valid decision advances private state. */
	*advance_phase = true;
	*previous_tip = tip_index;
	plant->random_state = next_random_state;
	plant->agent_memory = decision.next_memory;
	record_agent_decision(world, plant_index, &observation, &decision);
	return execute_agent_decision(world, plant_index, &observation, &decision);
}

static int grow_best_tip(struct picosystem_garden_world *world, uint8_t plant_index,
			 const struct picosystem_garden_agent_policy *policy, bool *advance_phase)
{
	*advance_phase = false;
	if (world->node_count == 0U) {
		*advance_phase = true;
		return -ENOENT;
	}

	struct picosystem_garden_plant *const plant = &world->plants[plant_index];
	const struct picosystem_garden_agent_memory current_memory = plant->agent_memory;
	uint32_t next_random_state = plant->random_state;
	const uint32_t decision_nonce = random_next(&next_random_state);
	const uint16_t start = (uint16_t)(plant->growth_phase % world->node_count);
	struct picosystem_garden_agent_observation best_observation;
	struct picosystem_garden_agent_decision best_decision;
	bool found_tip = false;

	for (uint16_t offset = 0U; offset < world->node_count; ++offset) {
		const uint16_t tip_index = (uint16_t)((start + offset) % world->node_count);
		const struct picosystem_garden_node *const tip = &world->nodes[tip_index];
		if ((tip->plant_index != plant_index) ||
		    ((tip->flags & PICOSYSTEM_GARDEN_NODE_TIP) == 0U)) {
			continue;
		}

		struct picosystem_garden_agent_observation observation;
		build_agent_observation(world, plant_index, tip_index, decision_nonce,
					&observation);
		struct picosystem_garden_agent_decision decision;
		const int err = picosystem_garden_agent_decide(policy, &observation,
							       &current_memory, &decision);
		if (err != 0) {
			return err;
		}
		if (!proposal_is_valid(&observation, &decision.proposal)) {
			return -ERANGE;
		}
		if (!found_tip || (decision.proposal.priority > best_decision.proposal.priority)) {
			best_observation = observation;
			best_decision = decision;
			found_tip = true;
		}
	}

	if (!found_tip) {
		*advance_phase = true;
		return -ENOENT;
	}

	/* Every bid saw one immutable snapshot; only the winner advances private state. */
	*advance_phase = true;
	if (best_observation.tissue_kind == PICOSYSTEM_GARDEN_NODE_STEM) {
		plant->last_shoot_tip_index = best_observation.tip_index;
	} else {
		plant->last_root_tip_index = best_observation.tip_index;
	}
	plant->random_state = next_random_state;
	plant->agent_memory = best_decision.next_memory;
	record_agent_decision(world, plant_index, &best_observation, &best_decision);
	return execute_agent_decision(world, plant_index, &best_observation, &best_decision);
}

static enum picosystem_garden_node_kind
plant_growth_kind(const struct picosystem_garden_plant *plant)
{
	const uint8_t phase = plant->growth_phase;
	if (plant->genome.shoot_bias <= -2) {
		return ((phase % 4U) == 0U) ? PICOSYSTEM_GARDEN_NODE_STEM
					    : PICOSYSTEM_GARDEN_NODE_ROOT;
	}
	if (plant->genome.shoot_bias == -1) {
		return ((phase % 3U) == 0U) ? PICOSYSTEM_GARDEN_NODE_STEM
					    : PICOSYSTEM_GARDEN_NODE_ROOT;
	}
	if (plant->genome.shoot_bias == 0) {
		return ((phase & 1U) == 0U) ? PICOSYSTEM_GARDEN_NODE_STEM
					    : PICOSYSTEM_GARDEN_NODE_ROOT;
	}
	if (plant->genome.shoot_bias == 1) {
		return ((phase % 3U) == 2U) ? PICOSYSTEM_GARDEN_NODE_ROOT
					    : PICOSYSTEM_GARDEN_NODE_STEM;
	}
	return ((phase % 4U) == 3U) ? PICOSYSTEM_GARDEN_NODE_ROOT : PICOSYSTEM_GARDEN_NODE_STEM;
}

static int grow_plants(struct picosystem_garden_world *world,
		       const struct picosystem_garden_agent_policy *policy)
{
	for (uint8_t index = 0U; index < world->plant_count; ++index) {
		struct picosystem_garden_plant *const plant = &world->plants[index];
		if (plant_is_dead(plant)) {
			continue;
		}
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

		bool advance_phase;
		int err;
		if (policy->arbitration == PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS) {
			err = grow_best_tip(world, index, policy, &advance_phase);
		} else {
			const enum picosystem_garden_node_kind kind = plant_growth_kind(plant);
			err = grow_phased_tip(world, index, kind, policy, &advance_phase);
		}
		if (!advance_phase && (err != 0)) {
			return err;
		}
		if (advance_phase) {
			++plant->growth_phase;
		}
		if ((err == 0) || (err == -ENOSPC)) {
			plant->stored_energy = (uint16_t)(plant->stored_energy - energy_cost);
			plant->stored_water =
				(uint16_t)(plant->stored_water - species->growth_water_cost);
			plant->growth_cooldown =
				(uint8_t)(plant_growth_period(species, &plant->genome) - 1U);
		}
	}
	return 0;
}

static int8_t mutated_trait(int8_t value, bool increase)
{
	if (increase) {
		return (value < PICOSYSTEM_GARDEN_GENOME_TRAIT_MAX) ? (int8_t)(value + 1)
								    : (int8_t)(value - 1);
	}
	return (value > PICOSYSTEM_GARDEN_GENOME_TRAIT_MIN) ? (int8_t)(value - 1)
							    : (int8_t)(value + 1);
}

static bool mutate_genome(struct picosystem_garden_genome *genome, uint32_t *random_state)
{
	const uint32_t mutation = random_next(random_state);
	if ((mutation & 3U) == 0U) {
		return false;
	}
	const uint8_t trait = (uint8_t)((mutation >> 2U) % GARDEN_GENOME_TRAIT_COUNT);
	const bool increase = ((mutation >> 5U) & 1U) != 0U;
	switch (trait) {
	case 0U:
		genome->growth_rate = mutated_trait(genome->growth_rate, increase);
		break;
	case 1U:
		genome->shoot_bias = mutated_trait(genome->shoot_bias, increase);
		break;
	case 2U:
		genome->light_seeking = mutated_trait(genome->light_seeking, increase);
		break;
	case 3U:
		genome->water_seeking = mutated_trait(genome->water_seeking, increase);
		break;
	case 4U:
		genome->branching = mutated_trait(genome->branching, increase);
		break;
	case 5U:
		genome->stature = mutated_trait(genome->stature, increase);
		break;
	case 6U:
		genome->reserve_strategy = mutated_trait(genome->reserve_strategy, increase);
		break;
	case 7U:
		genome->dispersal = mutated_trait(genome->dispersal, increase);
		break;
	default:
		return false;
	}
	return true;
}

static uint16_t unseeded_flower_index(const struct picosystem_garden_world *world,
				      uint8_t plant_index)
{
	for (uint16_t index = 0U; index < world->node_count; ++index) {
		const struct picosystem_garden_node *const node = &world->nodes[index];
		const uint8_t required = PICOSYSTEM_GARDEN_NODE_FLOWER;
		if ((node->plant_index == plant_index) && ((node->flags & required) == required) &&
		    ((node->flags & PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED) == 0U) &&
		    (node->growth_progress >= PICOSYSTEM_GARDEN_LEAF_ACTIVE_PROGRESS)) {
			return index;
		}
	}
	return PICOSYSTEM_GARDEN_NODE_NONE;
}

static uint8_t dispersed_seed_column(const struct picosystem_garden_plant *plant, uint32_t random)
{
	const int32_t distance = 5 + plant->genome.dispersal + (int32_t)((random >> 1U) % 3U);
	const int32_t direction = ((random & 1U) != 0U) ? 1 : -1;
	int32_t column = (int32_t)plant->base_column + (direction * distance);
	if ((column < 0) || (column >= (int32_t)PICOSYSTEM_GARDEN_GRID_COLUMNS)) {
		column = (int32_t)plant->base_column - (direction * distance);
	}
	if (column < 0) {
		column = 0;
	} else if (column >= (int16_t)PICOSYSTEM_GARDEN_GRID_COLUMNS) {
		column = PICOSYSTEM_GARDEN_GRID_COLUMNS - 1U;
	}
	return (uint8_t)column;
}

static bool plant_can_reproduce(const struct picosystem_garden_world *world, uint8_t plant_index,
				uint8_t sun_strength)
{
	const struct picosystem_garden_plant *const plant = &world->plants[plant_index];
	if (plant_is_dead(plant) || (plant->stress != 0U) ||
	    (sun_strength <= PICOSYSTEM_GARDEN_LIGHT_MINIMUM) ||
	    (plant->generation == UINT16_MAX)) {
		return false;
	}
	const int32_t energy_reserve =
		GARDEN_REPRODUCTION_ENERGY_RESERVE +
		((int32_t)plant->genome.reserve_strategy * GARDEN_REPRODUCTION_RESERVE_ENERGY_STEP);
	const int32_t water_reserve =
		GARDEN_REPRODUCTION_WATER_RESERVE +
		((int32_t)plant->genome.reserve_strategy * GARDEN_REPRODUCTION_RESERVE_WATER_STEP);
	const int32_t reserve_periods = PICOSYSTEM_GARDEN_NIGHT_RESERVE_PERIODS +
					((int32_t)plant->genome.reserve_strategy *
					 PICOSYSTEM_GARDEN_RESERVE_TRAIT_PERIOD_STEP);
	const int32_t maintenance_energy_reserve =
		(int32_t)plant_energy_maintenance_cost(plant) * reserve_periods;
	const int32_t maintenance_water_reserve =
		(int32_t)plant_water_maintenance_cost(world, plant_index) * reserve_periods;
	const int32_t retained_energy = (energy_reserve > maintenance_energy_reserve)
						? energy_reserve
						: maintenance_energy_reserve;
	const int32_t retained_water = (water_reserve > maintenance_water_reserve)
					       ? water_reserve
					       : maintenance_water_reserve;
	return ((int32_t)plant->stored_energy >=
		(GARDEN_REPRODUCTION_ENERGY_COST + retained_energy)) &&
	       ((int32_t)plant->stored_water >= (GARDEN_REPRODUCTION_WATER_COST + retained_water));
}

static void update_reproduction(struct picosystem_garden_world *world)
{
	const struct picosystem_garden_sun sun =
		picosystem_garden_sun_at(world->ecology_tick_count);
	const uint8_t plant_count = world->plant_count;
	for (uint8_t plant_index = 0U; plant_index < plant_count; ++plant_index) {
		struct picosystem_garden_plant *const plant = &world->plants[plant_index];
		if (plant->reproduction_cooldown > 0U) {
			--plant->reproduction_cooldown;
		}
		if ((plant->reproduction_cooldown != 0U) ||
		    ((world->ecology_tick_count % PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR) !=
		     0U) ||
		    (world->seed_count >= PICOSYSTEM_GARDEN_MAX_SEEDS) ||
		    !plant_can_reproduce(world, plant_index, sun.strength)) {
			continue;
		}

		const uint16_t flower_index = unseeded_flower_index(world, plant_index);
		if (flower_index == PICOSYSTEM_GARDEN_NODE_NONE) {
			continue;
		}
		const uint32_t dispersal_random = random_next(&plant->random_state);
		struct picosystem_garden_seed *const seed = &world->seeds[world->seed_count];
		*seed = (struct picosystem_garden_seed){
			.genome = plant->genome,
			.parent_lineage_id = plant->lineage_id,
			.generation = (uint16_t)(plant->generation + 1U),
			.column = dispersed_seed_column(plant, dispersal_random),
			.species_id = plant->species_id,
			.visual_offset = (int8_t)((int32_t)((dispersal_random >> 8U) % 5U) - 2),
		};
		if (mutate_genome(&seed->genome, &plant->random_state)) {
			world->mutation_count = saturating_add_u32(world->mutation_count, 1U);
		}
		++world->seed_count;
		world->nodes[flower_index].flags |= PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED;
		plant->stored_energy =
			(uint16_t)(plant->stored_energy - GARDEN_REPRODUCTION_ENERGY_COST);
		plant->stored_water =
			(uint16_t)(plant->stored_water - GARDEN_REPRODUCTION_WATER_COST);
		plant->reproduction_cooldown = GARDEN_REPRODUCTION_COOLDOWN_TICKS;
		world->seed_creation_count = saturating_add_u32(world->seed_creation_count, 1U);
	}
}

static void remove_seed(struct picosystem_garden_world *world, uint8_t seed_index)
{
	const uint8_t following_count = (uint8_t)(world->seed_count - seed_index - 1U);
	if (following_count > 0U) {
		memmove(&world->seeds[seed_index], &world->seeds[seed_index + 1U],
			following_count * sizeof(world->seeds[0]));
	}
	--world->seed_count;
	memset(&world->seeds[world->seed_count], 0, sizeof(world->seeds[0]));
}

static void record_parent_offspring(struct picosystem_garden_world *world,
				    uint32_t parent_lineage_id)
{
	for (uint8_t index = 0U; index < world->plant_count; ++index) {
		struct picosystem_garden_plant *const plant = &world->plants[index];
		if (plant->lineage_id == parent_lineage_id) {
			plant->offspring_count =
				saturating_add_u16_limit(plant->offspring_count, 1U, UINT16_MAX);
			return;
		}
	}
}

static uint8_t seed_germination_blockers(const struct picosystem_garden_world *world,
					 const struct picosystem_garden_seed *seed)
{
	uint8_t blockers = 0U;
	if (seed->age_ecology_ticks < PICOSYSTEM_GARDEN_SEED_DORMANCY_TICKS) {
		blockers |= PICOSYSTEM_GARDEN_SEED_BLOCKED_DORMANT;
	}
	if (world->moisture[soil_index(seed->column, 0U)] < GARDEN_SEED_MINIMUM_MOISTURE) {
		blockers |= PICOSYSTEM_GARDEN_SEED_BLOCKED_MOISTURE;
	}
	if (world->light[light_index(seed->column, PICOSYSTEM_GARDEN_CANOPY_ROWS - 1U)] <
	    GARDEN_SEED_MINIMUM_LIGHT) {
		blockers |= PICOSYSTEM_GARDEN_SEED_BLOCKED_LIGHT;
	}
	if (world->plant_count >= PICOSYSTEM_GARDEN_MAX_PLANTS) {
		blockers |= PICOSYSTEM_GARDEN_SEED_BLOCKED_PLANT_CAPACITY;
	}
	if ((world->node_count + GARDEN_SEED_NODE_COUNT) > PICOSYSTEM_GARDEN_MAX_NODES) {
		blockers |= PICOSYSTEM_GARDEN_SEED_BLOCKED_NODE_CAPACITY;
	}
	if (!plant_spacing_is_available(world, seed->column)) {
		blockers |= PICOSYSTEM_GARDEN_SEED_BLOCKED_SPACING;
	}
	return blockers;
}

static bool seed_can_germinate(const struct picosystem_garden_world *world,
			       const struct picosystem_garden_seed *seed)
{
	return seed_germination_blockers(world, seed) == 0U;
}

static int update_seed_bank(struct picosystem_garden_world *world)
{
	uint8_t seed_index = 0U;
	while (seed_index < world->seed_count) {
		struct picosystem_garden_seed *const seed = &world->seeds[seed_index];
		++seed->age_ecology_ticks;
		if (seed->age_ecology_ticks >= PICOSYSTEM_GARDEN_SEED_LIFETIME_TICKS) {
			remove_seed(world, seed_index);
			world->seed_expiration_count =
				saturating_add_u32(world->seed_expiration_count, 1U);
			continue;
		}
		if (!seed_can_germinate(world, seed)) {
			++seed_index;
			continue;
		}

		const struct picosystem_garden_seed germinating_seed = *seed;
		const int err = create_seedling(
			world, (enum picosystem_garden_species_id)germinating_seed.species_id,
			germinating_seed.column, &germinating_seed.genome,
			germinating_seed.parent_lineage_id, germinating_seed.generation,
			GARDEN_OFFSPRING_INITIAL_ENERGY, GARDEN_OFFSPRING_INITIAL_WATER, NULL);
		if (err != 0) {
			return err;
		}
		uint8_t *const moisture = &world->moisture[soil_index(germinating_seed.column, 0U)];
		*moisture = (uint8_t)(*moisture - GARDEN_SEED_MINIMUM_MOISTURE);
		record_parent_offspring(world, germinating_seed.parent_lineage_id);
		remove_seed(world, seed_index);
		world->germination_count = saturating_add_u32(world->germination_count, 1U);
	}
	return 0;
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
		if (plant_is_dead(&world->plants[index])) {
			continue;
		}
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

static uint8_t available_seed_index(const struct picosystem_garden_world *world)
{
	for (uint8_t offset = 0U; offset < world->seed_count; ++offset) {
		const uint8_t index =
			(uint8_t)((world->auto_decision_count + offset) % world->seed_count);
		if (plant_spacing_is_available(world, world->seeds[index].column)) {
			return index;
		}
	}
	return UINT8_MAX;
}

static void choose_auto_target(struct picosystem_garden_world *world)
{
	++world->auto_decision_count;
	if (picosystem_garden_world_living_plant_count(world) < GARDEN_AUTO_MINIMUM_PLANTS) {
		const uint8_t seed_index = available_seed_index(world);
		if (seed_index != UINT8_MAX) {
			world->auto_target_column = world->seeds[seed_index].column;
			world->auto_target_row = GARDEN_AUTO_ACTION_ROW;
			world->auto_target_tool = PICOSYSTEM_GARDEN_TOOL_WATER;
			world->auto_target_valid = true;
			return;
		}
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
	const struct picosystem_garden_genome genome = {0};
	return create_seedling(world, species_id, column, &genome, 0U, 0U, GARDEN_INITIAL_ENERGY,
			       GARDEN_INITIAL_WATER, NULL);
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
	return picosystem_garden_world_step_with_policy(world,
							picosystem_garden_agent_adaptive_policy());
}

int picosystem_garden_world_step_input(struct picosystem_garden_world *world, int8_t horizontal,
				       int8_t vertical)
{
	return picosystem_garden_world_step_input_with_policy(
		world, horizontal, vertical, picosystem_garden_agent_adaptive_policy());
}

int picosystem_garden_world_step_with_policy(struct picosystem_garden_world *world,
					     const struct picosystem_garden_agent_policy *policy)
{
	return picosystem_garden_world_step_input_with_policy(world, 0, 0, policy);
}

int picosystem_garden_world_step_input_with_policy(
	struct picosystem_garden_world *world, int8_t horizontal, int8_t vertical,
	const struct picosystem_garden_agent_policy *policy)
{
	if ((policy == NULL) || (policy->decide == NULL) ||
	    ((uint32_t)policy->arbitration >= PICOSYSTEM_GARDEN_AGENT_ARBITRATION_COUNT) ||
	    !world_is_valid(world)) {
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
	int err = update_light(world);
	if (err != 0) {
		return err;
	}
	absorb_water_and_light(world);
	err = update_decomposition(world);
	if (err != 0) {
		return err;
	}
	update_plant_maintenance(world);
	err = update_seed_bank(world);
	if (err != 0) {
		return err;
	}
	err = grow_plants(world, policy);
	if (err != 0) {
		return err;
	}
	update_reproduction(world);
	err = update_light(world);
	if (err != 0) {
		return err;
	}
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

const struct picosystem_garden_seed *
picosystem_garden_world_seed_at(const struct picosystem_garden_world *world, size_t index)
{
	return ((world != NULL) && (index < world->seed_count)) ? &world->seeds[index] : NULL;
}

int picosystem_garden_world_seed_germination_blockers(const struct picosystem_garden_world *world,
						      size_t seed_index, uint8_t *blockers)
{
	if ((blockers == NULL) || !world_is_valid(world)) {
		return -EINVAL;
	}
	if (seed_index >= world->seed_count) {
		return -ERANGE;
	}
	*blockers = seed_germination_blockers(world, &world->seeds[seed_index]);
	return 0;
}

uint8_t picosystem_garden_world_living_plant_count(const struct picosystem_garden_world *world)
{
	if ((world == NULL) || (world->plant_count > PICOSYSTEM_GARDEN_MAX_PLANTS)) {
		return 0U;
	}
	uint8_t count = 0U;
	for (uint8_t index = 0U; index < world->plant_count; ++index) {
		if (!plant_is_dead(&world->plants[index])) {
			++count;
		}
	}
	return count;
}

uint8_t picosystem_garden_world_dead_plant_count(const struct picosystem_garden_world *world)
{
	if ((world == NULL) || (world->plant_count > PICOSYSTEM_GARDEN_MAX_PLANTS)) {
		return 0U;
	}
	return (uint8_t)(world->plant_count - picosystem_garden_world_living_plant_count(world));
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

static uint32_t fnv1a_genome(uint32_t hash, const struct picosystem_garden_genome *genome)
{
	hash = fnv1a_byte(hash, (uint8_t)genome->growth_rate);
	hash = fnv1a_byte(hash, (uint8_t)genome->shoot_bias);
	hash = fnv1a_byte(hash, (uint8_t)genome->light_seeking);
	hash = fnv1a_byte(hash, (uint8_t)genome->water_seeking);
	hash = fnv1a_byte(hash, (uint8_t)genome->branching);
	hash = fnv1a_byte(hash, (uint8_t)genome->stature);
	hash = fnv1a_byte(hash, (uint8_t)genome->reserve_strategy);
	return fnv1a_byte(hash, (uint8_t)genome->dispersal);
}

static bool agent_memory_is_zero(const struct picosystem_garden_agent_memory *memory)
{
	for (uint8_t index = 0U; index < PICOSYSTEM_GARDEN_AGENT_MEMORY_WIDTH; ++index) {
		if (memory->hidden[index] != 0) {
			return false;
		}
	}
	return true;
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
	hash = fnv1a_u32(hash, world->death_count);
	hash = fnv1a_u32(hash, world->reclaimed_plant_count);
	hash = fnv1a_u32(hash, world->reclaimed_node_count);
	hash = fnv1a_u32(hash, world->seed_creation_count);
	hash = fnv1a_u32(hash, world->germination_count);
	hash = fnv1a_u32(hash, world->seed_expiration_count);
	hash = fnv1a_u32(hash, world->mutation_count);
	hash = fnv1a_u32(hash, world->lineage_sequence);
	hash = fnv1a_u16(hash, world->node_count);
	hash = fnv1a_u16(hash, world->moisture_total);
	hash = fnv1a_u16(hash, world->maximum_generation);
	hash = fnv1a_byte(hash, world->plant_count);
	hash = fnv1a_byte(hash, world->seed_count);
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
		hash = fnv1a_u32(hash, plant->lineage_id);
		hash = fnv1a_u32(hash, plant->parent_lineage_id);
		hash = fnv1a_u16(hash, plant->base_node_index);
		hash = fnv1a_u16(hash, plant->last_shoot_tip_index);
		hash = fnv1a_u16(hash, plant->last_root_tip_index);
		hash = fnv1a_u16(hash, plant->stored_energy);
		hash = fnv1a_u16(hash, plant->stored_water);
		hash = fnv1a_u16(hash, plant->age_ecology_ticks);
		hash = fnv1a_u16(hash, plant->node_count);
		hash = fnv1a_u16(hash, plant->offspring_count);
		hash = fnv1a_u16(hash, plant->generation);
		hash = fnv1a_genome(hash, &plant->genome);
		hash = fnv1a_byte(hash, plant->base_column);
		hash = fnv1a_byte(hash, plant->growth_cooldown);
		hash = fnv1a_byte(hash, plant->reproduction_cooldown);
		hash = fnv1a_byte(hash, plant->growth_phase);
		hash = fnv1a_byte(hash, plant->species_id);
		hash = fnv1a_byte(hash, (uint8_t)plant->lean);
		hash = fnv1a_byte(hash, (uint8_t)plant->vigor);
		hash = fnv1a_byte(hash, plant->stress);
		hash = fnv1a_byte(hash, plant->flags);
		hash = fnv1a_byte(hash, plant->last_energy_income);
		hash = fnv1a_byte(hash, plant->last_water_income);
	}
	for (uint8_t index = 0U; index < world->seed_count; ++index) {
		const struct picosystem_garden_seed *const seed = &world->seeds[index];
		hash = fnv1a_genome(hash, &seed->genome);
		hash = fnv1a_u32(hash, seed->parent_lineage_id);
		hash = fnv1a_u16(hash, seed->age_ecology_ticks);
		hash = fnv1a_u16(hash, seed->generation);
		hash = fnv1a_byte(hash, seed->column);
		hash = fnv1a_byte(hash, seed->species_id);
		hash = fnv1a_byte(hash, (uint8_t)seed->visual_offset);
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

	bool has_agent_memory = false;
	for (uint8_t plant_index = 0U; plant_index < world->plant_count; ++plant_index) {
		if (!agent_memory_is_zero(&world->plants[plant_index].agent_memory)) {
			has_agent_memory = true;
			break;
		}
	}
	/* Preserve established baseline hashes while extending nonzero policy state. */
	if (has_agent_memory) {
		hash = fnv1a_u32(hash, GARDEN_AGENT_MEMORY_HASH_TAG);
		for (uint8_t plant_index = 0U; plant_index < world->plant_count; ++plant_index) {
			const struct picosystem_garden_agent_memory *const memory =
				&world->plants[plant_index].agent_memory;
			for (uint8_t memory_index = 0U;
			     memory_index < PICOSYSTEM_GARDEN_AGENT_MEMORY_WIDTH; ++memory_index) {
				hash = fnv1a_byte(hash, (uint8_t)memory->hidden[memory_index]);
			}
		}
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
