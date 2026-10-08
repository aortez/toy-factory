/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "garden_world.h"

#include "garden_agent.h"
#include "garden_dispersal.h"
#include "garden_light.h"
#include "garden_leaf.h"
#if defined(TOY_FACTORY_GARDEN_SOIL_WICKING)
#include "garden_wicking.h"
#endif
#if defined(TOY_FACTORY_GARDEN_LATE_UPTAKE_LIMIT)
#include "garden_uptake_limit.h"
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_RESERVE)
#include "garden_seed_reserve.h"
#endif

#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

struct picosystem_garden_water_audit;
struct picosystem_garden_seed_audit;
struct picosystem_garden_death_audit;
struct picosystem_garden_reproduction_audit;
struct picosystem_garden_flower_audit;
struct picosystem_garden_landing_cache;
struct picosystem_garden_resource_audit;
struct picosystem_garden_uptake_audit;

struct garden_step_audits {
	struct picosystem_garden_water_audit *water;
	struct picosystem_garden_seed_audit *seed;
	struct picosystem_garden_death_audit *death;
	struct picosystem_garden_reproduction_audit *reproduction;
	struct picosystem_garden_flower_audit *flower;
	struct picosystem_garden_landing_cache *landing;
	struct picosystem_garden_resource_audit *resources;
	struct picosystem_garden_uptake_audit *uptake;
};
#if !defined(__ZEPHYR__)
#include "garden_death_audit.h"
#include "garden_seed_audit.h"
#include "garden_reproduction_audit.h"
#include "garden_flower_audit.h"
#include "garden_landing_internal.h"
#include "garden_uptake_audit.h"

static void audit_resource_stage(const struct picosystem_garden_world *world,
				 struct picosystem_garden_resource_audit *audit,
				 enum picosystem_garden_resource_stage stage)
{
	if (audit == NULL) {
		return;
	}
	audit->stages[stage].count = world->plant_count;
	for (uint8_t i = 0U; i < world->plant_count; ++i) {
		const struct picosystem_garden_plant *const p = &world->plants[i];
		audit->stages[stage].plants[i] =
			(struct picosystem_garden_resource_plant){.lineage_id = p->lineage_id,
								  .energy = p->stored_energy,
								  .water = p->stored_water,
								  .nodes = p->node_count,
								  .stress = p->stress,
								  .flags = p->flags};
	}
}
#define AUDIT_RESOURCE(stage)                                                                      \
	audit_resource_stage(world, audits ? audits->resources : NULL,                             \
			     PICOSYSTEM_GARDEN_RESOURCE_##stage)
#else
#define AUDIT_RESOURCE(stage)                                                                      \
	do {                                                                                       \
	} while (0)
#endif

#if !defined(__ZEPHYR__)

static void audit_seed_stage(const struct picosystem_garden_world *world,
			     struct picosystem_garden_seed_audit *audit,
			     enum picosystem_garden_seed_stage stage)
{
	if (audit == NULL) {
		return;
	}
	audit->ecology_step = true;
	audit->stages[stage] = (struct picosystem_garden_seed_inventory){
		.nodes = world->node_count,
		.plants = world->plant_count,
		.seeds = world->seed_count,
	};
}
#define AUDIT_SEED(stage) audit_seed_stage(world, seed_audit, PICOSYSTEM_GARDEN_SEED_##stage)
#else
#define AUDIT_SEED(stage)                                                                          \
	do {                                                                                       \
	} while (0)
#endif

#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
#include "garden_water_audit.h"

static void audit_water(const struct picosystem_garden_world *world,
			struct picosystem_garden_water_audit *audit,
			enum picosystem_garden_water_stage stage)
{
	if (audit == NULL) {
		return;
	}
	struct picosystem_garden_water_inventory *const inventory = &audit->stages[stage];
	for (uint16_t i = 0U; i < PICOSYSTEM_GARDEN_SOIL_CELL_COUNT; ++i) {
		inventory->soil += world->moisture[i];
	}
	for (uint8_t i = 0U; i < world->plant_count; ++i) {
		inventory->plants += world->plants[i].stored_water;
	}
	audit->ecology_step = true;
}
#define AUDIT_WATER(stage) audit_water(world, water_audit, PICOSYSTEM_GARDEN_WATER_##stage)
#else
#define AUDIT_WATER(stage)                                                                         \
	do {                                                                                       \
	} while (0)
#endif

#define GARDEN_HASH_VERSION                      UINT32_C(6)
#define GARDEN_AGENT_MEMORY_HASH_TAG             UINT32_C(0x4d454d31)
#define GARDEN_WEATHER_HASH_TAG                  UINT32_C(0x5241494e)
#define GARDEN_LONG_AGE_HASH_TAG                 UINT32_C(0x41474531)
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

static uint8_t plant_capacity(const struct picosystem_garden_world *world)
{
#if defined(TOY_FACTORY_GARDEN_PLANT_SLOTS)
	return picosystem_garden_plant_slots_limit(world->plant_slots_sixteen,
						   world->logic_tick_count);
#else
	(void)world;
	return PICOSYSTEM_GARDEN_MAX_PLANTS;
#endif
}

static bool world_is_valid(const struct picosystem_garden_world *world)
{
	if ((world == NULL) || (world->node_count > PICOSYSTEM_GARDEN_MAX_NODES) ||
	    (world->plant_count > plant_capacity(world)) ||
	    (world->seed_count > PICOSYSTEM_GARDEN_MAX_SEEDS) ||
	    (world->climate_mode >= PICOSYSTEM_GARDEN_CLIMATE_COUNT) ||
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
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
		if (((node->flags & PICOSYSTEM_GARDEN_NODE_LEAF) == 0U) &&
		    world->leaf_condition[index]) {
			return false;
		}
#endif
	}

	for (uint8_t index = 0U; index < world->plant_count; ++index) {
		const struct picosystem_garden_plant *const plant = &world->plants[index];
		const bool dead = plant_is_dead(plant);
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
		if ((plant->leaf_energy_remainder == UINT8_MAX) ||
		    (dead && (plant->leaf_energy_remainder != 0U))) {
			return false;
		}
#endif
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
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	world->leaf_condition[index] = (flags & PICOSYSTEM_GARDEN_NODE_LEAF) ? UINT8_MAX : 0U;
#endif
	++world->plants[plant_index].node_count;
	if (parent_index != PICOSYSTEM_GARDEN_NODE_NONE) {
		++world->nodes[parent_index].child_count;
	}
	return node;
}

static bool plant_spacing_is_available(const struct picosystem_garden_world *world, uint8_t column)
{
#if defined(TOY_FACTORY_GARDEN_SEED_SPACING)
	const uint8_t minimum = picosystem_garden_seed_spacing_minimum(world->seed_spacing_two,
								       world->logic_tick_count);
#else
	const uint8_t minimum = GARDEN_MINIMUM_PLANT_SPACING;
#endif
	for (uint8_t index = 0U; index < world->plant_count; ++index) {
		const uint8_t other = world->plants[index].base_column;
		const uint8_t distance =
			(column >= other) ? (uint8_t)(column - other) : (uint8_t)(other - column);
		if (distance < minimum) {
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
	if ((world->plant_count >= plant_capacity(world)) ||
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

uint8_t picosystem_garden_rain_at(uint32_t weather_seed, uint32_t ecology_tick)
{
	if (weather_seed == 0U) {
		return 0U;
	}
	/* Counter-based weather cannot change when a policy consumes more randomness. */
	uint32_t bits = weather_seed ^ (ecology_tick / PICOSYSTEM_GARDEN_RAIN_WINDOW_TICKS);
	bits ^= UINT32_C(0x7261696e);
	bits ^= bits >> 16U;
	bits *= UINT32_C(0x7feb352d);
	bits ^= bits >> 15U;
	bits *= UINT32_C(0x846ca68b);
	bits ^= bits >> 16U;
	/* One 4--8 second shower per 32 second window, with dry margins. */
	const uint32_t start = 8U + (bits % 81U);
	const uint32_t duration = 16U + ((bits >> 8U) % 17U);
	const uint32_t phase = ecology_tick % PICOSYSTEM_GARDEN_RAIN_WINDOW_TICKS;
	return ((phase >= start) && (phase < (start + duration)))
		       ? (uint8_t)(2U + ((bits >> 16U) % 3U))
		       : 0U;
}

struct picosystem_garden_climate
picosystem_garden_world_climate(const struct picosystem_garden_world *world)
{
	struct picosystem_garden_climate climate =
		picosystem_garden_climate_at(world->weather_seed, world->ecology_tick_count);
	if ((world->climate_mode & PICOSYSTEM_GARDEN_CLIMATE_WINTER) == 0U) {
		climate.light_percent = 100U;
		climate.cold = false;
	}
	if ((world->climate_mode & PICOSYSTEM_GARDEN_CLIMATE_DROUGHT) == 0U) {
		climate.drought = false;
	}
	return climate;
}

uint8_t picosystem_garden_world_rain(const struct picosystem_garden_world *world)
{
	if (picosystem_garden_world_climate(world).drought) {
		return 0U;
	}
	return picosystem_garden_rain_at(world->weather_seed, world->ecology_tick_count);
}

static void update_rain(struct picosystem_garden_world *world)
{
	const uint8_t rate = picosystem_garden_world_rain(world);
	if (rate == 0U) {
		return;
	}
	uint32_t deposited = 0U;
	for (uint8_t column = 0U; column < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++column) {
		uint8_t *const surface = &world->moisture[soil_index(column, 0U)];
		const uint8_t next = saturating_add_u8(*surface, rate);
		deposited += (uint32_t)(next - *surface);
		*surface = next;
	}
	world->rain_deposited = saturating_add_u32(world->rain_deposited, deposited);
	world->rain_runoff = saturating_add_u32(
		world->rain_runoff, ((uint32_t)rate * PICOSYSTEM_GARDEN_GRID_COLUMNS) - deposited);
}

static int update_moisture(struct picosystem_garden_world *world)
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

#if defined(TOY_FACTORY_GARDEN_SOIL_WICKING)
	const int moved = picosystem_garden_wicking_step(world->moisture, sizeof(world->moisture),
							 world->logic_tick_count);
	if (moved < 0) {
		return moved;
	}
#endif
	if ((world->ecology_tick_count & 3U) == 0U) {
		for (uint8_t column = 0U; column < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++column) {
			uint8_t *const surface = &world->moisture[soil_index(column, 0U)];
			if (*surface > 0U) {
				--*surface;
			}
		}
	}
	return 0;
}

#if defined(TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE)
static uint32_t drain_bottom(struct picosystem_garden_world *world)
{
	if ((world->ecology_tick_count % PICOSYSTEM_GARDEN_DRAINAGE_PERIOD) != 0U) {
		return 0U;
	}
	uint32_t drained = 0U;
	for (uint8_t column = 0U; column < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++column) {
		uint8_t *const cell =
			&world->moisture[soil_index(column, PICOSYSTEM_GARDEN_SOIL_ROWS - 1U)];
		if (*cell != 0U) {
			--*cell;
			++drained;
		}
	}
	return drained;
}
#endif

#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
static bool mature_leaf(const struct picosystem_garden_node *node)
{
	return (node->kind == PICOSYSTEM_GARDEN_NODE_STEM) &&
	       ((node->flags & PICOSYSTEM_GARDEN_NODE_LEAF) != 0U) &&
	       (node->growth_progress >= PICOSYSTEM_GARDEN_LEAF_ACTIVE_PROGRESS);
}

static void wear_leaves(struct picosystem_garden_world *world)
{
	if ((world->ecology_tick_count % PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR) != 0U) {
		return;
	}
	for (uint16_t index = 0U; index < world->node_count; ++index) {
		const struct picosystem_garden_node *node = &world->nodes[index];
		struct picosystem_garden_plant *plant = &world->plants[node->plant_index];
		if (plant_is_dead(plant) || !mature_leaf(node) || !world->leaf_condition[index]) {
			continue;
		}
		--world->leaf_condition[index];
		plant->leaf_telemetry.worn = saturating_add_u32(plant->leaf_telemetry.worn, 1U);
		world->leaf_telemetry.worn = saturating_add_u32(world->leaf_telemetry.worn, 1U);
	}
}
#endif

static int update_light_observed(struct picosystem_garden_world *world,
				 struct picosystem_garden_uptake_audit *audit)
{
#if defined(__ZEPHYR__)
	(void)audit;
#endif
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
		uint8_t center_shade = species->leaf_shade;
		uint8_t neighbor_shade = (uint8_t)(species->leaf_shade / 3U);
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
		center_shade = (uint8_t)(center_shade * world->leaf_condition[index] / UINT8_MAX);
		neighbor_shade =
			(uint8_t)(neighbor_shade * world->leaf_condition[index] / UINT8_MAX);
#endif
#if !defined(__ZEPHYR__)
		if (audit != NULL) {
			audit->sources[audit->source_count++] =
				(struct picosystem_garden_shade_source){
					.lineage = plant->lineage_id,
					.node = index,
					.column = column,
					.row = row,
					.center = center_shade,
					.neighbor = neighbor_shade,
					.dead = plant_is_dead(plant)};
		}
#endif
		shade[light_index(column, row)] =
			saturating_add_u8(shade[light_index(column, row)], center_shade);
		if (column > 0U) {
			shade[light_index((uint8_t)(column - 1U), row)] = saturating_add_u8(
				shade[light_index((uint8_t)(column - 1U), row)], neighbor_shade);
		}
		if ((column + 1U) < PICOSYSTEM_GARDEN_GRID_COLUMNS) {
			shade[light_index((uint8_t)(column + 1U), row)] = saturating_add_u8(
				shade[light_index((uint8_t)(column + 1U), row)], neighbor_shade);
		}
	}

	const struct picosystem_garden_sun sun = picosystem_garden_world_sun(world);
#if defined(TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION)
	if (picosystem_garden_canopy_transmission_active(world->canopy_transmission_enabled,
							 world->logic_tick_count)) {
		return picosystem_garden_light_solve_transmission(shade, &sun, world->light);
	}
#endif
	return picosystem_garden_light_solve(shade, &sun, world->light);
}

static int update_light(struct picosystem_garden_world *world)
{
	return update_light_observed(world, NULL);
}

static void absorb_water_and_light(struct picosystem_garden_world *world,
				   struct picosystem_garden_death_audit *death_audit,
				   struct picosystem_garden_uptake_audit *audit)
{
	(void)death_audit;
#if defined(__ZEPHYR__)
	(void)audit;
#else
	if (audit != NULL) {
		audit->ecology_step = true;
		audit->tick = world->logic_tick_count;
		audit->sun = picosystem_garden_world_sun(world);
		memcpy(audit->soil_before, world->moisture, sizeof(audit->soil_before));
		memcpy(audit->light, world->light, sizeof(audit->light));
	}
#endif
	for (uint8_t plant_index = 0U; plant_index < world->plant_count; ++plant_index) {
		struct picosystem_garden_plant *const plant = &world->plants[plant_index];
		plant->last_energy_income = 0U;
		plant->last_water_income = 0U;
		if (plant_is_dead(plant)) {
			continue;
		}
		const struct garden_species_config *const species =
			&species_configs[plant->species_id];
		const uint16_t energy_before = plant->stored_energy;
		const uint16_t water_before = plant->stored_water;
		(void)energy_before;
		(void)water_before;
		uint16_t gathered_energy = 0U;
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
		uint32_t energy_numerator = plant->leaf_energy_remainder;
#endif
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
				uint8_t uptake = (*moisture >= species->root_uptake)
							 ? species->root_uptake
							 : *moisture;
#if defined(TOY_FACTORY_GARDEN_WATER_HEADROOM)
				/* Storage is updated per root; leave surplus in this soil cell.
				 * Do not skip leaves or reserve capacity for later upkeep.
				 */
				const uint16_t headroom =
					(uint16_t)(GARDEN_MAX_STORED_WATER - plant->stored_water);
				if (uptake > headroom) {
					uptake = (uint8_t)headroom;
				}
#endif
#if defined(TOY_FACTORY_GARDEN_LATE_UPTAKE_LIMIT)
				_Static_assert(GARDEN_MAX_STORED_WATER ==
						       PICOSYSTEM_GARDEN_UPTAKE_LIMIT_CAPACITY,
					       "late uptake limit must match plant storage");
				uptake = picosystem_garden_uptake_limit(uptake, plant->stored_water,
									world->logic_tick_count);
#endif
#if !defined(__ZEPHYR__)
				if (audit != NULL) {
					audit->roots[audit->root_count++] =
						(struct picosystem_garden_root_uptake){
							.lineage = plant->lineage_id,
							.node = node_index,
							.slot = plant_index,
							.column = column,
							.row = row,
							.limit = species->root_uptake,
							.before = *moisture,
							.taken = uptake,
							.after = (uint8_t)(*moisture - uptake),
							.stored_before = plant->stored_water,
							.stored_after = saturating_add_u16_limit(
								plant->stored_water, uptake,
								GARDEN_MAX_STORED_WATER)};
				}
#endif
				*moisture = (uint8_t)(*moisture - uptake);
				gathered_water = (uint16_t)(gathered_water + uptake);
				plant->stored_water = saturating_add_u16_limit(
					plant->stored_water, uptake, GARDEN_MAX_STORED_WATER);
			} else if (((node->flags & PICOSYSTEM_GARDEN_NODE_LEAF) != 0U) &&
				   (node->growth_progress >=
				    PICOSYSTEM_GARDEN_LEAF_ACTIVE_PROGRESS)) {
				const uint8_t column = pixel_to_column(node->x);
				const uint8_t row = pixel_to_canopy_row(node->y);
#if !defined(__ZEPHYR__)
				if (audit != NULL) {
					const uint8_t light =
						world->light[light_index(column, row)];
					audit->leaves[audit->leaf_count++] =
						(struct picosystem_garden_leaf_uptake){
							.lineage = plant->lineage_id,
							.node = node_index,
							.column = column,
							.row = row,
							.light = light,
							.income = (uint8_t)(light / 64U)};
				}
#endif
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
				energy_numerator += (world->light[light_index(column, row)] / 64U) *
						    world->leaf_condition[node_index];
#else
				gathered_energy =
					(uint16_t)(gathered_energy +
						   world->light[light_index(column, row)] / 64U);
#endif
			}
		}
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
		gathered_energy = (uint16_t)(energy_numerator / UINT8_MAX);
		plant->leaf_energy_remainder = (uint8_t)(energy_numerator % UINT8_MAX);
#endif
		plant->stored_energy = saturating_add_u16_limit(
			plant->stored_energy, gathered_energy, GARDEN_MAX_STORED_ENERGY);
		plant->last_energy_income =
			(gathered_energy > UINT8_MAX) ? UINT8_MAX : (uint8_t)gathered_energy;
		plant->last_water_income =
			(gathered_water > UINT8_MAX) ? UINT8_MAX : (uint8_t)gathered_water;
#if !defined(__ZEPHYR__)
		if (death_audit != NULL) {
			/* At most one entry per existing living plant. Reclamation can move
			 * slots before maintenance, so resolve later by immutable lineage ID.
			 */
			death_audit->events[death_audit->count++] =
				(struct picosystem_garden_death_event){
					.lineage_id = plant->lineage_id,
					.stress_before = plant->stress,
					.energy = {.before = energy_before,
						   .income = gathered_energy,
						   .overflow = (uint16_t)(energy_before +
									  gathered_energy -
									  plant->stored_energy)},
					.water = {.before = water_before,
						  .income = gathered_water,
						  .overflow =
							  (uint16_t)(water_before + gathered_water -
								     plant->stored_water)},
				};
		}
#endif
	}
#if !defined(__ZEPHYR__)
	if (audit != NULL) {
		memcpy(audit->soil_after, world->moisture, sizeof(audit->soil_after));
	}
#endif
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

#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
int picosystem_garden_leaf_observe(const struct picosystem_garden_world *world, uint8_t plant_index,
				   struct picosystem_garden_leaf_observation *observation)
{
	if ((observation == NULL) || !world_is_valid(world) ||
	    (plant_index >= world->plant_count)) {
		return -EINVAL;
	}
	const struct picosystem_garden_plant *plant = &world->plants[plant_index];
	if (plant_is_dead(plant)) {
		return -ENOENT;
	}
	uint16_t count = 0U;
	for (uint16_t index = 0U; index < world->node_count; ++index) {
		if ((world->nodes[index].plant_index == plant_index) &&
		    mature_leaf(&world->nodes[index])) {
			++count;
		}
	}
	if (count == 0U) {
		return -ENOENT;
	}
	uint16_t selected =
		(uint16_t)(((world->ecology_tick_count % count) + (plant->lineage_id % count)) %
			   count);
	for (uint16_t index = 0U; index < world->node_count; ++index) {
		const struct picosystem_garden_node *node = &world->nodes[index];
		if ((node->plant_index != plant_index) || !mature_leaf(node)) {
			continue;
		}
		if (selected != 0U) {
			--selected;
			continue;
		}
		const struct picosystem_garden_node *base = &world->nodes[plant->base_node_index];
		*observation = (struct picosystem_garden_leaf_observation){
			.node_index = index,
			.plant_index = plant_index,
			.stored_energy = plant->stored_energy,
			.stored_water = plant->stored_water,
			.mature_leaf_count = count,
			.base_delta_x = (int16_t)((int)node->x - base->x),
			.base_delta_y = (int16_t)((int)node->y - base->y),
			.condition = world->leaf_condition[index],
			.light = world->light[light_index(pixel_to_column(node->x),
							  pixel_to_canopy_row(node->y))],
			.maintenance_energy = plant_energy_maintenance_cost(plant),
			.maintenance_water = plant_water_maintenance_cost(world, plant_index),
			.renewal_energy = PICOSYSTEM_GARDEN_LEAF_RENEW_ENERGY,
			.renewal_water = PICOSYSTEM_GARDEN_LEAF_RENEW_WATER,
		};
		return 0;
	}
	return -ENOENT;
}

#if defined(TOY_FACTORY_GARDEN_DARK_GUARD)
static bool dark_expense_denied(struct picosystem_garden_world *world, uint8_t plant_index,
				enum picosystem_garden_expense_kind kind, uint16_t node_index,
				uint8_t energy_cost, uint8_t water_cost, uint16_t nodes_after)
{
	_Static_assert(PICOSYSTEM_GARDEN_DARK_EVENTS >= PICOSYSTEM_GARDEN_MAX_PLANTS * 3U,
		       "Every plant can propose renewal, growth and a seed in one step");
	_Static_assert(GARDEN_MAX_STORED_ENERGY == 256U &&
			       GARDEN_ENERGY_MAINTENANCE_NODES_PER_UNIT == 8U,
		       "Revisit the host dark-budget resource constants");
	struct picosystem_garden_dark_audit *const audit = &world->dark_guard;
	if (audit->count >= PICOSYSTEM_GARDEN_DARK_EVENTS) {
		audit->overflow = true;
		return true; /* Fail closed if a future caller breaks the bounded event contract. */
	}
	const struct picosystem_garden_plant *const plant = &world->plants[plant_index];
	const uint8_t phase = picosystem_garden_sun_at(world->ecology_tick_count).phase;
	struct picosystem_garden_dark_event *const event = &audit->events[audit->count++];
	*event = (struct picosystem_garden_dark_event){
		.lineage_id = plant->lineage_id,
		.node_index = node_index,
		.nodes_before = plant->node_count,
		.nodes_after = nodes_after,
		.energy = plant->stored_energy,
		.water = plant->stored_water,
		.kind = (uint8_t)kind,
		.energy_cost = energy_cost,
		.water_cost = water_cost,
		.stress = plant->stress,
	};
	event->invalid =
		(energy_cost > plant->stored_energy) || (water_cost > plant->stored_water) ||
		(picosystem_garden_dark_project(plant->stored_energy, plant->node_count,
						plant->stress, phase, &event->before) != 0) ||
		(picosystem_garden_dark_project((uint16_t)(plant->stored_energy - energy_cost),
						nodes_after, plant->stress, phase,
						&event->after) != 0);
	event->denied =
		event->invalid || (event->after.supported && (event->after.death_step != 0U));
	audit->evaluated[kind] = saturating_add_u32(audit->evaluated[kind], 1U);
	if (event->denied) {
		audit->denied[kind] = saturating_add_u32(audit->denied[kind], 1U);
	}
	return event->denied;
}
#endif

int picosystem_garden_leaf_renew(struct picosystem_garden_world *world, uint8_t plant_index,
				 uint16_t node_index)
{
	if (!world_is_valid(world) || (plant_index >= world->plant_count) ||
	    (node_index >= world->node_count)) {
		return -EINVAL;
	}
	struct picosystem_garden_plant *plant = &world->plants[plant_index];
	const struct picosystem_garden_node *node = &world->nodes[node_index];
	if (plant_is_dead(plant) || (node->plant_index != plant_index) || !mature_leaf(node)) {
		return -EINVAL;
	}
	if (world->leaf_condition[node_index] == UINT8_MAX) {
		return -EALREADY;
	}
	if ((plant->stored_energy < PICOSYSTEM_GARDEN_LEAF_RENEW_ENERGY) ||
	    (plant->stored_water < PICOSYSTEM_GARDEN_LEAF_RENEW_WATER)) {
		return -EAGAIN;
	}
#if defined(TOY_FACTORY_GARDEN_DARK_GUARD)
	if (dark_expense_denied(world, plant_index, PICOSYSTEM_GARDEN_EXPENSE_RENEWAL, node_index,
				PICOSYSTEM_GARDEN_LEAF_RENEW_ENERGY,
				PICOSYSTEM_GARDEN_LEAF_RENEW_WATER, plant->node_count)) {
		return -EAGAIN;
	}
#endif
	const uint32_t restored = UINT8_MAX - world->leaf_condition[node_index];
	plant->stored_energy -= PICOSYSTEM_GARDEN_LEAF_RENEW_ENERGY;
	plant->stored_water -= PICOSYSTEM_GARDEN_LEAF_RENEW_WATER;
	world->leaf_condition[node_index] = UINT8_MAX;
	plant->leaf_telemetry.renewals = saturating_add_u32(plant->leaf_telemetry.renewals, 1U);
	world->leaf_telemetry.renewals = saturating_add_u32(world->leaf_telemetry.renewals, 1U);
	plant->leaf_telemetry.restored =
		saturating_add_u32(plant->leaf_telemetry.restored, restored);
	world->leaf_telemetry.restored =
		saturating_add_u32(world->leaf_telemetry.restored, restored);
	return 0;
}

/* A renewal has fixed precedence. A leaf WAIT yields to the legacy growth bid. */
static int propose_leaf(struct picosystem_garden_world *world, uint8_t plant_index,
			const struct picosystem_garden_leaf_policy *policy,
			struct picosystem_garden_leaf_decision *decision)
{
	if (policy == NULL) {
		return -ENOENT;
	}
	if (policy->decide == NULL) {
		return -EINVAL;
	}
	struct picosystem_garden_leaf_observation observation;
	int err = picosystem_garden_leaf_observe(world, plant_index, &observation);
	if (err != 0) {
		return err;
	}
	struct picosystem_garden_plant *plant = &world->plants[plant_index];
	const struct picosystem_garden_agent_memory memory = plant->agent_memory;
	*decision = (struct picosystem_garden_leaf_decision){.node_index = observation.node_index,
							     .next_memory = memory};
	err = policy->decide(&observation, &memory, decision, policy->context);
	if (err != 0) {
		return err;
	}
	if ((decision->node_index != observation.node_index) ||
	    (decision->action > PICOSYSTEM_GARDEN_LEAF_RENEW)) {
		return -ERANGE;
	}
	plant->leaf_telemetry.observations =
		saturating_add_u32(plant->leaf_telemetry.observations, 1U);
	world->leaf_telemetry.observations =
		saturating_add_u32(world->leaf_telemetry.observations, 1U);
	if (decision->action == PICOSYSTEM_GARDEN_LEAF_WAIT) {
		return 0;
	}
	plant->leaf_telemetry.proposals = saturating_add_u32(plant->leaf_telemetry.proposals, 1U);
	world->leaf_telemetry.proposals = saturating_add_u32(world->leaf_telemetry.proposals, 1U);
	err = picosystem_garden_leaf_renew(world, plant_index, decision->node_index);
	if ((err == -EAGAIN) || (err == -EALREADY)) {
		/* Rejected renewal neither commits memory nor blocks a valid growth bid. */
		return -ENOENT;
	}
	if (err == 0) {
		plant->agent_memory = decision->next_memory;
		return 1;
	}
	return err;
}
#endif

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
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	plant->leaf_energy_remainder = 0U;
#endif
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

static void update_plant_maintenance(struct picosystem_garden_world *world,
				     struct picosystem_garden_death_audit *death_audit)
{
	(void)death_audit;
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
#if !defined(__ZEPHYR__)
			if (death_audit != NULL) {
				for (uint8_t index = 0U; index < death_audit->count; ++index) {
					struct picosystem_garden_death_event *const event =
						&death_audit->events[index];
					if (event->lineage_id != plant->lineage_id) {
						continue;
					}
					event->energy.upkeep_due =
						plant_energy_maintenance_cost(plant);
					event->water.upkeep_due =
						plant_water_maintenance_cost(world, plant_index);
					event->energy.discarded = plant->stored_energy;
					event->water.discarded = plant->stored_water;
					event->energy.upkeep_paid =
						(uint16_t)(event->energy.before +
							   event->energy.income -
							   event->energy.overflow -
							   plant->stored_energy);
					event->water.upkeep_paid =
						(uint16_t)(event->water.before +
							   event->water.income -
							   event->water.overflow -
							   plant->stored_water);
					event->flags = plant->flags | PICOSYSTEM_GARDEN_PLANT_DEAD;
					break;
				}
			}
#endif
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
	/* Preserve the device's 256-byte scratch space; the larger pool is host-only. */
#if defined(TOY_FACTORY_GARDEN_LARGE_POOL)
	typedef uint16_t remap_index_t;
#else
	typedef uint8_t remap_index_t;
	_Static_assert(PICOSYSTEM_GARDEN_MAX_NODES <= UINT8_MAX + 1U,
		       "one-byte remap cannot represent a larger node pool");
#endif
	remap_index_t node_remap[PICOSYSTEM_GARDEN_MAX_NODES] = {0};
	uint16_t write_node = 0U;
	for (uint16_t read_node = 0U; read_node < old_node_count; ++read_node) {
		struct picosystem_garden_node node = world->nodes[read_node];
		if (node.plant_index == plant_index) {
			continue;
		}
		node_remap[read_node] = (remap_index_t)write_node;
		if (node.parent_index != PICOSYSTEM_GARDEN_NODE_NONE) {
			node.parent_index = node_remap[node.parent_index];
		}
		if (node.plant_index > plant_index) {
			--node.plant_index;
		}
		world->nodes[write_node] = node;
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
		world->leaf_condition[write_node] = world->leaf_condition[read_node];
#endif
		++write_node;
	}
	if ((old_node_count - write_node) != reclaimed_node_count) {
		return -EINVAL;
	}
	memset(&world->nodes[write_node], 0,
	       (old_node_count - write_node) * sizeof(world->nodes[0]));
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	memset(&world->leaf_condition[write_node], 0, old_node_count - write_node);
#endif

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

#if !defined(__ZEPHYR__)
int picosystem_garden_world_experimental_kill_patch(struct picosystem_garden_world *world,
						    uint8_t first_column, uint8_t last_column)
{
	if (!world_is_valid(world) || (first_column > last_column) ||
	    (last_column >= PICOSYSTEM_GARDEN_GRID_COLUMNS)) {
		return -EINVAL;
	}
	/* Host-only transaction; never add this world-sized stack copy to the firmware. */
	struct picosystem_garden_world candidate = *world;
	bool changed = false;
	for (uint8_t index = 0U; index < candidate.plant_count; ++index) {
		struct picosystem_garden_plant *plant = &candidate.plants[index];
		if (plant_is_dead(plant) || (plant->base_column < first_column) ||
		    (plant->base_column > last_column)) {
			continue;
		}
		plant->flags &= (uint8_t) ~(PICOSYSTEM_GARDEN_PLANT_ENERGY_SHORTAGE |
					    PICOSYSTEM_GARDEN_PLANT_WATER_SHORTAGE);
		mark_plant_dead(&candidate, index);
		changed = true;
	}
	if (!changed) {
		return 0;
	}
	const int err = update_light(&candidate);
	if ((err != 0) || !world_is_valid(&candidate)) {
		return err != 0 ? err : -EINVAL;
	}
	*world = candidate;
	return 0;
}
#endif

#if !defined(__ZEPHYR__)
int picosystem_garden_world_experimental_clear(struct picosystem_garden_world *world,
					       uint32_t lineage_id)
{
	if (!world_is_valid(world) || (lineage_id == 0U)) {
		return -EINVAL;
	}
	uint8_t target = 0U;
	while ((target < world->plant_count) && (world->plants[target].lineage_id != lineage_id)) {
		++target;
	}
	if (target == world->plant_count) {
		return -ENOENT;
	}
	if (plant_is_dead(&world->plants[target])) {
		return -EINVAL;
	}
	/* This host-only transaction deliberately avoids a device-sized stack contract. */
	struct picosystem_garden_world candidate = *world;
	candidate.plants[target].flags |= PICOSYSTEM_GARDEN_PLANT_DEAD;
	int err = reclaim_plant(&candidate, target);
	if (err != 0) {
		return err;
	}
	/* A recorded external export is neither starvation nor natural decomposition. */
	candidate.reclaimed_plant_count = world->reclaimed_plant_count;
	candidate.reclaimed_node_count = world->reclaimed_node_count;
	err = update_light(&candidate);
	if ((err != 0) || !world_is_valid(&candidate)) {
		return err != 0 ? err : -EINVAL;
	}
	*world = candidate;
	return 0;
}
#endif

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
	const struct picosystem_garden_sun sun = picosystem_garden_world_sun(world);
	*observation = (struct picosystem_garden_agent_observation){
		.decision_nonce = decision_nonce,
		.tip_index = tip_index,
		.stored_energy = plant->stored_energy,
		.stored_water = plant->stored_water,
		.age_ecology_ticks = (plant->age_ecology_ticks > UINT16_MAX)
					     ? UINT16_MAX
					     : (uint16_t)plant->age_ecology_ticks,
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

#if defined(TOY_FACTORY_GARDEN_DARK_GUARD)
static int check_growth_expense(struct picosystem_garden_world *world, uint8_t plant_index,
				const struct picosystem_garden_agent_observation *observation,
				const struct picosystem_garden_agent_decision *decision)
{
#if defined(TOY_FACTORY_GARDEN_FULL_POOL)
	if ((world->node_count >= PICOSYSTEM_GARDEN_MAX_NODES) &&
	    picosystem_garden_full_pool_active(world->full_pool.enabled, world->logic_tick_count)) {
		bool allocates = false;
		if (decision->proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND) {
			for (uint8_t i = 0U; i < decision->proposal.candidate_count; ++i) {
				const uint8_t candidate = decision->proposal.candidate_order[i];
				allocates |= (observation->candidates[candidate].flags &
					      PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE) != 0U;
			}
		}
		/* Refuse allocation before any guard expense or private-state commit. */
		const int err = picosystem_garden_full_pool_check(
			&world->full_pool, world->plants[plant_index].lineage_id,
			observation->tip_index, decision->proposal.action, allocates);
		if (err != 0) {
			return err;
		}
	}
#endif
	if (decision->proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT) {
		return 0;
	}
	const struct picosystem_garden_plant *const plant = &world->plants[plant_index];
	const struct garden_species_config *const species = &species_configs[plant->species_id];
	uint16_t nodes_after = plant->node_count;
	if (decision->proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND) {
		for (uint8_t i = 0U; i < decision->proposal.candidate_count; ++i) {
			const uint8_t candidate = decision->proposal.candidate_order[i];
			if ((observation->candidates[candidate].flags &
			     PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE) != 0U) {
				++nodes_after;
				break;
			}
		}
	}
	const uint8_t energy_cost = (uint8_t)(species->growth_energy_cost - (plant->vigor > 0));
	if (dark_expense_denied(world, plant_index, PICOSYSTEM_GARDEN_EXPENSE_GROWTH,
				observation->tip_index, energy_cost, species->growth_water_cost,
				nodes_after)) {
		return -ECANCELED;
	}
#if defined(TOY_FACTORY_GARDEN_NIGHT_CAPACITY)
	const int capacity_err = picosystem_garden_night_check(
		&world->night_capacity, &world->dark_guard.events[world->dark_guard.count - 1U],
		(uint8_t)(world->dark_guard.count - 1U));
	if (capacity_err != 0) {
		return capacity_err;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_DAWN_FINISH)
	return picosystem_garden_dawn_finish_check(
		&world->dawn_finish, world->logic_tick_count,
		&world->dark_guard.events[world->dark_guard.count - 1U], observation,
		decision->proposal.action);
#elif defined(TOY_FACTORY_GARDEN_PURCHASE_VETO)
	return picosystem_garden_purchase_check(
		&world->purchase_veto, world->logic_tick_count,
		&world->dark_guard.events[world->dark_guard.count - 1U], decision->proposal.action);
#else
	return 0;
#endif
}
#endif

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
#if defined(TOY_FACTORY_GARDEN_DARK_GUARD)
	err = check_growth_expense(world, plant_index, &observation, &decision);
	if (err != 0) {
		return err;
	}
#endif
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
#if !defined(__ZEPHYR__)
	bool found_eligible = false;
#endif

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
		bool replace = !found_tip ||
			       (decision.proposal.priority > best_decision.proposal.priority);
#if !defined(__ZEPHYR__)
		bool eligible = true;
		if (policy->eligible != NULL) {
			const int eligibility_err = policy->eligible(
				&observation, &decision, &eligible, policy->eligibility_context);
			if (eligibility_err != 0) {
				return (eligibility_err < 0) ? eligibility_err : -EINVAL;
			}
		}
		if (found_tip && (eligible != found_eligible)) {
			replace = eligible;
		}
#endif
		if (replace) {
			best_observation = observation;
			best_decision = decision;
			found_tip = true;
#if !defined(__ZEPHYR__)
			found_eligible = eligible;
#endif
		}
	}

	if (!found_tip) {
		*advance_phase = true;
		return -ENOENT;
	}

	/* Every bid saw one immutable snapshot; only the winner advances private state. */
#if !defined(__ZEPHYR__)
	if (!found_eligible) {
		best_decision.proposal.action = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT;
		best_decision.proposal.candidate_count = 0U;
		memset(best_decision.proposal.candidate_order,
		       PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE,
		       sizeof(best_decision.proposal.candidate_order));
	}
#endif
#if defined(TOY_FACTORY_GARDEN_DARK_GUARD)
	const int expense_err =
		check_growth_expense(world, plant_index, &best_observation, &best_decision);
	if (expense_err != 0) {
		return expense_err;
	}
#endif
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
		plant->age_ecology_ticks = saturating_add_u32(plant->age_ecology_ticks, 1U);
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
		struct picosystem_garden_leaf_decision leaf_decision;
		const int leaf_result =
			propose_leaf(world, index, policy->leaf_policy, &leaf_decision);
		if ((leaf_result < 0) && (leaf_result != -ENOENT)) {
			return leaf_result;
		}
		if (plant->growth_cooldown > 0U) {
			--plant->growth_cooldown;
			if (leaf_result == 0) {
				plant->agent_memory = leaf_decision.next_memory;
			}
			continue;
		}
		if (leaf_result == 1) {
			continue;
		}
#else
		if (plant->growth_cooldown > 0U) {
			--plant->growth_cooldown;
			continue;
		}
#endif
		const uint8_t vigor_discount = (plant->vigor > 0) ? 1U : 0U;
		const uint8_t energy_cost = (uint8_t)(species->growth_energy_cost - vigor_discount);
		bool node_gate = world->node_count >= PICOSYSTEM_GARDEN_MAX_NODES;
#if defined(TOY_FACTORY_GARDEN_FULL_POOL)
		if (picosystem_garden_full_pool_active(world->full_pool.enabled,
						       world->logic_tick_count)) {
			node_gate = false; /* Selected allocations are refused transactionally. */
		}
#endif
		if ((plant->stored_energy < energy_cost) ||
		    (plant->stored_water < species->growth_water_cost) || node_gate) {
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
			if (leaf_result == 0) {
				plant->agent_memory = leaf_decision.next_memory;
			}
#endif
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
#if defined(TOY_FACTORY_GARDEN_DARK_GUARD)
		if (!advance_phase && (err == -ECANCELED)) {
			continue; /* A denied winner commits no private state and is retried
				     normally. */
		}
#endif
		if (!advance_phase && (err != 0)) {
			return err;
		}
		if (advance_phase) {
			++plant->growth_phase;
		}
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
		if ((err == -ENOENT) && (leaf_result == 0)) {
			plant->agent_memory = leaf_decision.next_memory;
		}
#endif
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

static bool flower_is_ready(const struct picosystem_garden_node *node)
{
	return ((node->flags & PICOSYSTEM_GARDEN_NODE_FLOWER) != 0U) &&
	       ((node->flags & PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED) == 0U) &&
	       (node->growth_progress >= PICOSYSTEM_GARDEN_LEAF_ACTIVE_PROGRESS);
}

static uint16_t unseeded_flower_index(const struct picosystem_garden_world *world,
				      uint8_t plant_index)
{
	for (uint16_t index = 0U; index < world->node_count; ++index) {
		const struct picosystem_garden_node *const node = &world->nodes[index];
		if ((node->plant_index == plant_index) && flower_is_ready(node)) {
			return index;
		}
	}
	return PICOSYSTEM_GARDEN_NODE_NONE;
}

static uint8_t seed_origin_column(const struct picosystem_garden_world *world, uint8_t plant_index,
				  uint16_t flower_index)
{
#if defined(TOY_FACTORY_GARDEN_FLOWER_DISPERSAL)
	(void)plant_index;
	return pixel_to_column(world->nodes[flower_index].x);
#else
	(void)flower_index;
	return world->plants[plant_index].base_column;
#endif
}

static uint8_t dispersed_seed_column(const struct picosystem_garden_plant *plant, uint8_t origin,
				     uint32_t random, uint32_t tick)
{
	return picosystem_garden_dispersed_column_at(origin, plant->genome.dispersal, random, tick);
}

#if !defined(__ZEPHYR__)
static uint32_t dispersal_columns(const struct picosystem_garden_plant *plant, uint8_t origin,
				  uint32_t tick)
{
	uint32_t columns = 0U;
	for (uint32_t choice = 0U; choice < picosystem_garden_dispersal_choices_at(tick);
	     ++choice) {
		columns |= UINT32_C(1) << dispersed_seed_column(plant, origin, choice, tick);
	}
	return columns;
}

static void audit_flower_purchase(const struct picosystem_garden_world *world, uint8_t plant_index,
				  uint16_t selected_flower, uint32_t random,
				  struct picosystem_garden_flower_audit *audit)
{
	if (audit == NULL) {
		return;
	}
	const struct picosystem_garden_plant *const plant = &world->plants[plant_index];
	const uint8_t origin = seed_origin_column(world, plant_index, selected_flower);
	struct picosystem_garden_flower_purchase *const purchase =
		&audit->purchases[audit->count++];
	*purchase = (struct picosystem_garden_flower_purchase){
		.lineage = plant->lineage_id,
		.columns = dispersal_columns(plant, origin, world->logic_tick_count),
		.flower_offset = audit->flower_count,
		.selected_flower = selected_flower,
		.base_column = plant->base_column,
		.origin = origin,
		.species = plant->species_id,
		.dispersal = plant->genome.dispersal,
		.choice = (uint8_t)(random % picosystem_garden_dispersal_choices_at(
						     world->logic_tick_count)),
		.landed_column =
			dispersed_seed_column(plant, origin, random, world->logic_tick_count),
	};
	for (uint16_t index = 0U; index < world->node_count; ++index) {
		const struct picosystem_garden_node *const node = &world->nodes[index];
		if ((node->plant_index != plant_index) || !flower_is_ready(node)) {
			continue;
		}
		audit->flowers[audit->flower_count++] = (struct picosystem_garden_flower_reach){
			.columns = dispersal_columns(plant, pixel_to_column(node->x),
						     world->logic_tick_count),
			.node_index = index,
			.x = node->x,
			.y = node->y,
		};
		++purchase->flower_count;
	}
}
#endif

#if defined(TOY_FACTORY_GARDEN_SEED_RESERVE)
int picosystem_garden_seed_reserve_forecast(
	uint16_t energy, uint8_t income, uint16_t nodes, uint8_t sun_phase,
	struct picosystem_garden_seed_reserve_forecast *forecast)
{
	if ((forecast == NULL) || (energy > GARDEN_MAX_STORED_ENERGY) || (nodes == 0U) ||
	    (nodes > PICOSYSTEM_GARDEN_MAX_NODES)) {
		return -EINVAL;
	}
	_Static_assert(PICOSYSTEM_GARDEN_SUN_INITIAL_PHASE %
				       PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR ==
			       0U,
		       "Upkeep aligns with sun phase");
	struct picosystem_garden_seed_reserve_forecast result = {
		.after_seed = (int32_t)energy - GARDEN_REPRODUCTION_ENERGY_COST,
		.maintenance_cost =
			rounded_up_cost(nodes, GARDEN_ENERGY_MAINTENANCE_NODES_PER_UNIT),
	};
	/* Sunset's payment is included in the forecast below. The remaining 31
	 * payments exclude dawn: neither dawn income nor a stress grace period is
	 * credited. This is deliberately not a whole-plant survival guarantee.
	 */
	result.night_upkeep = (uint16_t)(((PICOSYSTEM_GARDEN_SUN_CYCLE_TICKS -
					   PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE - 1U) /
					  PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR) *
					 result.maintenance_cost);
	int32_t projected = result.after_seed;
	bool funded = projected >= (int32_t)result.maintenance_cost;
	for (uint16_t phase = (uint16_t)sun_phase + 1U; phase <= PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE;
	     ++phase) {
		if (phase < PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE) {
			projected += (int32_t)(income / 2U);
			if (projected > (int32_t)GARDEN_MAX_STORED_ENERGY) {
				projected = GARDEN_MAX_STORED_ENERGY;
			}
		}
		if ((phase % PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR) == 0U) {
			projected -= result.maintenance_cost;
			funded &= projected >= 0;
		}
	}
	result.projected_sunset = projected;
	result.allowed = (sun_phase > 0U) && (sun_phase < PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE) &&
			 funded && (projected >= (int32_t)result.night_upkeep);
	*forecast = result;
	return 0;
}
#endif

struct reproduction_resources {
	int32_t energy_required;
	int32_t water_required;
};

static struct reproduction_resources
reproduction_resources(const struct picosystem_garden_world *world, uint8_t plant_index)
{
	const struct picosystem_garden_plant *const plant = &world->plants[plant_index];
	const int32_t energy_reserve =
		GARDEN_REPRODUCTION_ENERGY_RESERVE +
		((int32_t)plant->genome.reserve_strategy * GARDEN_REPRODUCTION_RESERVE_ENERGY_STEP);
	const int32_t water_reserve =
		GARDEN_REPRODUCTION_WATER_RESERVE +
		((int32_t)plant->genome.reserve_strategy * GARDEN_REPRODUCTION_RESERVE_WATER_STEP);
	const int32_t reserve_periods = PICOSYSTEM_GARDEN_NIGHT_RESERVE_PERIODS +
					((int32_t)plant->genome.reserve_strategy *
					 PICOSYSTEM_GARDEN_RESERVE_TRAIT_PERIOD_STEP);
	const int32_t energy_upkeep = plant_energy_maintenance_cost(plant);
	const int32_t water_upkeep = plant_water_maintenance_cost(world, plant_index);
	const int32_t maintenance_energy_reserve = energy_upkeep * reserve_periods;
	const int32_t maintenance_water_reserve = water_upkeep * reserve_periods;
	int32_t retained_energy = (energy_reserve > maintenance_energy_reserve)
					  ? energy_reserve
					  : maintenance_energy_reserve;
	int32_t retained_water = (water_reserve > maintenance_water_reserve)
					 ? water_reserve
					 : maintenance_water_reserve;
	/* Uptake caps stores before upkeep runs. Leave that debit and the seed cost
	 * outside the reserve so a full, mature plant can still afford reproduction.
	 * This bounds the safety margin; it does not guarantee survival next night.
	 */
	const int32_t maximum_energy_reserve =
		(int32_t)GARDEN_MAX_STORED_ENERGY - energy_upkeep - GARDEN_REPRODUCTION_ENERGY_COST;
	const int32_t maximum_water_reserve =
		(int32_t)GARDEN_MAX_STORED_WATER - water_upkeep - GARDEN_REPRODUCTION_WATER_COST;
	if (retained_energy > maximum_energy_reserve) {
		retained_energy = maximum_energy_reserve;
	}
	if (retained_water > maximum_water_reserve) {
		retained_water = maximum_water_reserve;
	}
	return (struct reproduction_resources){
		.energy_required = GARDEN_REPRODUCTION_ENERGY_COST + retained_energy,
		.water_required = GARDEN_REPRODUCTION_WATER_COST + retained_water,
	};
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
	const struct reproduction_resources resources = reproduction_resources(world, plant_index);
#if defined(TOY_FACTORY_GARDEN_SEED_RESERVE)
	struct picosystem_garden_seed_reserve_forecast forecast;
	if ((picosystem_garden_seed_reserve_forecast(
		     plant->stored_energy, plant->last_energy_income, plant->node_count,
		     picosystem_garden_sun_at(world->ecology_tick_count).phase, &forecast) != 0) ||
	    !forecast.allowed) {
		return false;
	}
#endif
	return ((int32_t)plant->stored_energy >= resources.energy_required) &&
	       ((int32_t)plant->stored_water >= resources.water_required);
}

#if !defined(__ZEPHYR__)
static struct picosystem_garden_reproduction_visit *
audit_reproduction_visit(const struct picosystem_garden_world *world, uint8_t plant_index,
			 uint8_t sun_strength, struct picosystem_garden_reproduction_audit *audit)
{
	if (audit == NULL) {
		return NULL;
	}
	const struct picosystem_garden_plant *const plant = &world->plants[plant_index];
	const struct reproduction_resources resources = reproduction_resources(world, plant_index);
	/* One visit per plant; world validation bounds plant_count by this capacity. */
	struct picosystem_garden_reproduction_visit *const visit = &audit->visits[audit->count++];
	*visit = (struct picosystem_garden_reproduction_visit){
		.lineage = plant->lineage_id,
		.energy = plant->stored_energy,
		.water = plant->stored_water,
		.energy_required = resources.energy_required,
		.water_required = resources.water_required,
		.flower_index = unseeded_flower_index(world, plant_index),
		.cooldown = plant->reproduction_cooldown,
		.seed_count = world->seed_count,
		.stress = plant->stress,
		.sun_strength = sun_strength,
	};
	const bool blocked[] = {
		plant->reproduction_cooldown != 0U,
		(world->ecology_tick_count % PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR) != 0U,
		world->seed_count >= PICOSYSTEM_GARDEN_MAX_SEEDS,
		plant_is_dead(plant),
		plant->stress != 0U,
		sun_strength <= PICOSYSTEM_GARDEN_LIGHT_MINIMUM,
		plant->generation == UINT16_MAX,
		(int32_t)plant->stored_energy < resources.energy_required,
		(int32_t)plant->stored_water < resources.water_required,
		visit->flower_index == PICOSYSTEM_GARDEN_NODE_NONE,
	};
	_Static_assert(PICOSYSTEM_GARDEN_REPRODUCTION_FLOWER == (1U << 9U),
		       "Keep ordinary blocker order synchronized");
	for (size_t i = 0U; i < sizeof(blocked) / sizeof(blocked[0]); ++i) {
		if (blocked[i]) {
			visit->blockers |= (uint16_t)(1U << i);
		}
	}
	for (uint16_t i = 0U; i < world->node_count; ++i) {
		const struct picosystem_garden_node *const node = &world->nodes[i];
		if ((node->plant_index != plant_index) ||
		    ((node->flags & PICOSYSTEM_GARDEN_NODE_FLOWER) == 0U)) {
			continue;
		}
		if (node->growth_progress < PICOSYSTEM_GARDEN_LEAF_ACTIVE_PROGRESS) {
			++visit->immature_flowers;
		} else if ((node->flags & PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED) != 0U) {
			++visit->spent_flowers;
		} else {
			++visit->ready_flowers;
		}
	}
	return visit;
}
#endif

#if defined(TOY_FACTORY_GARDEN_FOCAL_SEED_VETO)
static bool focal_seed_purchase_vetoed(const struct picosystem_garden_world *world,
				       uint8_t plant_index)
{
	/* Fixed causal probe, not a reproductive policy: founder 2, second daylight.
	 * Dawn clears these flags. Living flower nodes are never individually reclaimed,
	 * so their spent flags count successful purchases without adding world state.
	 */
	_Static_assert((PICOSYSTEM_GARDEN_SUN_CYCLE_TICKS == 256U) &&
			       (PICOSYSTEM_GARDEN_SUN_INITIAL_PHASE == 64U) &&
			       (PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE == 128U) &&
			       (PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR == 15U),
		       "Revisit the fixed second-daylight probe if the clock changes");
	const struct picosystem_garden_plant *const plant = &world->plants[plant_index];
	if ((world->logic_tick_count < 2880U) || (world->logic_tick_count >= 4800U) ||
	    (plant->lineage_id != 2U) || (plant->parent_lineage_id != 0U) ||
	    (plant->generation != 0U)) {
		return false;
	}
	uint16_t purchases = 0U;
	for (uint16_t i = 0U; i < world->node_count; ++i) {
		if ((world->nodes[i].plant_index == plant_index) &&
		    ((world->nodes[i].flags & PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED) != 0U)) {
			++purchases;
		}
	}
	return purchases >= 3U;
}
#endif

#if !defined(__ZEPHYR__)
static uint8_t replacement_seed_index(const struct picosystem_garden_world *world,
				      uint8_t plant_index, uint16_t flower_index)
{
	if ((world->plant_count >= PICOSYSTEM_GARDEN_MAX_PLANTS) ||
	    (world->node_count + 4U > PICOSYSTEM_GARDEN_MAX_NODES)) {
		return UINT8_MAX;
	}
	const struct picosystem_garden_plant *const parent = &world->plants[plant_index];
	const uint8_t origin = seed_origin_column(world, plant_index, flower_index);
	bool clear = false;
	for (uint8_t choice = 0U;
	     choice < picosystem_garden_dispersal_choices_at(world->logic_tick_count); ++choice) {
		clear |= plant_spacing_is_available(
			world,
			dispersed_seed_column(parent, origin, choice, world->logic_tick_count));
	}
	if (!clear) {
		return UINT8_MAX;
	}
	uint8_t selected = UINT8_MAX;
	for (uint8_t i = 0U; i < world->seed_count; ++i) {
		const struct picosystem_garden_seed *const seed = &world->seeds[i];
		if ((seed->parent_lineage_id == parent->lineage_id) &&
		    !plant_spacing_is_available(world, seed->column) &&
		    ((selected == UINT8_MAX) ||
		     (seed->age_ecology_ticks > world->seeds[selected].age_ecology_ticks))) {
			selected = i;
		}
	}
	return selected;
}
#endif

static int update_reproduction(struct picosystem_garden_world *world,
			       struct picosystem_garden_reproduction_audit *audit,
			       struct picosystem_garden_flower_audit *flower_audit,
			       struct picosystem_garden_seed_audit *seed_audit,
			       const struct picosystem_garden_agent_policy *policy)
{
	(void)audit;
	(void)flower_audit;
	(void)seed_audit;
	(void)policy;
#if !defined(__ZEPHYR__)
	uint8_t rotation = 0U;
	uint8_t ordered[PICOSYSTEM_GARDEN_MAX_PLANTS];
	const bool custom_order = (policy != NULL) && (policy->reproduction_order != NULL);
	if (custom_order) {
		if (policy->reproduction_purchase_order ||
		    (policy->reproduction_rotation_after != 0U) ||
		    (policy->seed_replacement_after != 0U)) {
			return -ERANGE;
		}
#if defined(TOY_FACTORY_GARDEN_SEED_ORDER)
		if (world->seed_order_rotating) {
			return -ENOTSUP;
		}
#endif
		/* Sentinel initialization also catches callbacks that leave holes. */
		memset(ordered, UINT8_MAX, sizeof(ordered));
		const int err = policy->reproduction_order(world, ordered, sizeof(ordered),
							   policy->reproduction_order_context);
		if (err != 0) {
			return err;
		}
		_Static_assert(PICOSYSTEM_GARDEN_MAX_PLANTS <= 32U, "Order validation bitset");
		uint32_t seen = 0U;
		for (uint8_t i = 0U; i < world->plant_count; ++i) {
			if ((ordered[i] >= world->plant_count) ||
			    ((seen & (UINT32_C(1) << ordered[i])) != 0U)) {
				return -ERANGE;
			}
			seen |= UINT32_C(1) << ordered[i];
		}
	}
	if ((policy != NULL) && policy->reproduction_purchase_order) {
		if ((policy->reproduction_rotation_after != 0U) ||
		    (policy->seed_replacement_after != 0U) ||
		    (policy->reproduction_after_lineage > world->lineage_sequence)) {
			return -ERANGE;
		}
#if defined(TOY_FACTORY_GARDEN_SEED_ORDER)
		if (world->seed_order_rotating) {
			return -ENOTSUP;
		}
#endif
		uint8_t first = UINT8_MAX;
		uint8_t successor = UINT8_MAX;
		for (uint8_t i = 0U; i < world->plant_count; ++i) {
			const struct picosystem_garden_plant *const plant = &world->plants[i];
			if (plant_is_dead(plant)) {
				continue;
			}
			if ((first == UINT8_MAX) ||
			    (plant->lineage_id < world->plants[first].lineage_id)) {
				first = i;
			}
			if ((plant->lineage_id > policy->reproduction_after_lineage) &&
			    ((successor == UINT8_MAX) ||
			     (plant->lineage_id < world->plants[successor].lineage_id))) {
				successor = i;
			}
		}
		rotation = successor != UINT8_MAX ? successor : first != UINT8_MAX ? first : 0U;
	}
	if ((policy != NULL) && (policy->reproduction_rotation_after != 0U)) {
		const uint32_t after = policy->reproduction_rotation_after;
		const uint32_t period = PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR *
					PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR;
		if (after % period != 0U) {
			return -ERANGE;
		}
#if defined(TOY_FACTORY_GARDEN_SEED_ORDER)
		if (world->seed_order_rotating) {
			return -ENOTSUP;
		}
#endif
		if ((world->logic_tick_count > after) && (world->logic_tick_count % period == 0U) &&
		    (world->plant_count != 0U)) {
			rotation = (uint8_t)(((world->logic_tick_count - after) / period) %
					     world->plant_count);
		}
	}
	if (audit != NULL) {
		audit->ecology_step = true;
	}
#endif
	const struct picosystem_garden_sun sun = picosystem_garden_world_sun(world);
	if (sun.phase == 0U) {
		/* A living flower can fund one seed each day without another growth tip.
		 * Reuse its existing spent flag; renewal never bypasses the seed debit,
		 * per-plant cooldown, daylight, stress, or seed-bank capacity checks.
		 */
		for (uint16_t index = 0U; index < world->node_count; ++index) {
			struct picosystem_garden_node *const node = &world->nodes[index];
			if (!plant_is_dead(&world->plants[node->plant_index])) {
				node->flags &= (uint8_t)~PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED;
			}
		}
	}
	const uint8_t plant_count = world->plant_count;
	for (uint8_t visit = 0U; visit < plant_count; ++visit) {
		uint8_t plant_index = visit;
#if !defined(__ZEPHYR__)
		if (custom_order) {
			plant_index = ordered[visit];
		} else if (rotation != 0U) {
			plant_index = (uint8_t)((rotation + visit) % plant_count);
		}
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_ORDER)
		if (world->seed_order_rotating) {
			const uint8_t start = picosystem_garden_seed_order_start(
				world->logic_tick_count, plant_count);
			plant_index = (uint8_t)((start + visit) % plant_count);
		}
#endif
		struct picosystem_garden_plant *const plant = &world->plants[plant_index];
		if (plant->reproduction_cooldown > 0U) {
			--plant->reproduction_cooldown;
		}
#if !defined(__ZEPHYR__)
		struct picosystem_garden_reproduction_visit *const receipt =
			audit_reproduction_visit(world, plant_index, sun.strength, audit);
		const bool may_replace = (policy->seed_replacement_after != 0U) &&
					 (world->logic_tick_count > policy->seed_replacement_after);
#else
		const bool may_replace = false;
#endif
		if ((plant->reproduction_cooldown != 0U) ||
		    ((world->ecology_tick_count % PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR) !=
		     0U) ||
		    ((world->seed_count >= PICOSYSTEM_GARDEN_MAX_SEEDS) && !may_replace) ||
		    !plant_can_reproduce(world, plant_index, sun.strength)) {
			continue;
		}

		const uint16_t flower_index = unseeded_flower_index(world, plant_index);
		if (flower_index == PICOSYSTEM_GARDEN_NODE_NONE) {
			continue;
		}
		uint8_t seed_index = world->seed_count;
#if !defined(__ZEPHYR__)
		if (seed_index == PICOSYSTEM_GARDEN_MAX_SEEDS) {
			seed_index = replacement_seed_index(world, plant_index, flower_index);
			if (seed_index == UINT8_MAX) {
				continue;
			}
		}
#endif
#if defined(TOY_FACTORY_GARDEN_FOCAL_SEED_VETO)
		if (focal_seed_purchase_vetoed(world, plant_index)) {
			continue;
		}
#endif
#if defined(TOY_FACTORY_GARDEN_DARK_GUARD)
		if (dark_expense_denied(world, plant_index, PICOSYSTEM_GARDEN_EXPENSE_SEED,
					flower_index, GARDEN_REPRODUCTION_ENERGY_COST,
					GARDEN_REPRODUCTION_WATER_COST, plant->node_count)) {
			continue;
		}
#endif
		uint32_t next_random_state = plant->random_state;
		const uint32_t dispersal_random = random_next(&next_random_state);
#if !defined(__ZEPHYR__)
		audit_flower_purchase(world, plant_index, flower_index, dispersal_random,
				      flower_audit);
#endif
		const uint8_t origin = seed_origin_column(world, plant_index, flower_index);
		uint8_t column = dispersed_seed_column(plant, origin, dispersal_random,
						       world->logic_tick_count);
#if !defined(__ZEPHYR__)
		if (policy->place_seed != NULL) {
			struct picosystem_garden_seed_placement observation = {
				.parent = plant->lineage_id,
				.random = dispersal_random,
				.logic_tick = world->logic_tick_count,
				.origin = origin,
				.dispersal = plant->genome.dispersal};
			const uint8_t choices =
				picosystem_garden_dispersal_choices_at(world->logic_tick_count);
			for (uint8_t c = 0U; c < choices; ++c) {
				observation.columns[c] = dispersed_seed_column(
					plant, origin, c, world->logic_tick_count);
				if (!plant_spacing_is_available(world, observation.columns[c])) {
					observation.blocked_choices |= (uint16_t)(1U << c);
				}
			}
			uint8_t choice = (uint8_t)(dispersal_random % choices);
			const int err = policy->place_seed(&observation, &choice,
							   policy->placement_context);
			if (err != 0) {
				return err;
			}
			if (choice >= choices) {
				return -ERANGE;
			}
			column = observation.columns[choice];
		}
		if (seed_index < world->seed_count) {
			if (!plant_spacing_is_available(world, column) ||
			    ((seed_audit != NULL) &&
			     (seed_audit->replacement_count >= PICOSYSTEM_GARDEN_MAX_PLANTS))) {
				return -ERANGE;
			}
			if (seed_audit != NULL) {
				seed_audit->replacements[seed_audit->replacement_count++] =
					(struct picosystem_garden_seed_replacement){
						.previous = world->seeds[seed_index],
						.new_column = column};
			}
		}
#endif
		struct picosystem_garden_seed *const seed = &world->seeds[seed_index];
		*seed = (struct picosystem_garden_seed){
			.genome = plant->genome,
			.parent_lineage_id = plant->lineage_id,
			.generation = (uint16_t)(plant->generation + 1U),
			.column = column,
			.species_id = plant->species_id,
			.visual_offset = (int8_t)((int32_t)((dispersal_random >> 8U) % 5U) - 2),
		};
		if (mutate_genome(&seed->genome, &next_random_state)) {
			world->mutation_count = saturating_add_u32(world->mutation_count, 1U);
		}
		plant->random_state = next_random_state;
		if (seed_index == world->seed_count) {
			++world->seed_count;
		}
		world->nodes[flower_index].flags |= PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED;
		plant->stored_energy =
			(uint16_t)(plant->stored_energy - GARDEN_REPRODUCTION_ENERGY_COST);
		plant->stored_water =
			(uint16_t)(plant->stored_water - GARDEN_REPRODUCTION_WATER_COST);
		plant->reproduction_cooldown = GARDEN_REPRODUCTION_COOLDOWN_TICKS;
		world->seed_creation_count = saturating_add_u32(world->seed_creation_count, 1U);
#if !defined(__ZEPHYR__)
		if (receipt != NULL) {
			receipt->produced = true;
		}
#endif
	}
	return 0;
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

#if defined(TOY_FACTORY_GARDEN_WET_GERMINATION)
int picosystem_garden_world_enable_wet_germination(struct picosystem_garden_world *world)
{
	if (!world_is_valid(world) || world->auto_gardener_enabled ||
	    world->wet_germination_enabled ||
	    ((world->logic_tick_count % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) != 0U)) {
		return -EINVAL;
	}
	world->wet_germination_enabled = true;
	return 0;
}
#endif

static uint8_t seed_germination_blockers(const struct picosystem_garden_world *world,
					 const struct picosystem_garden_seed *seed)
{
	uint8_t blockers = 0U;
	if (picosystem_garden_world_climate(world).cold) {
		blockers |= PICOSYSTEM_GARDEN_SEED_BLOCKED_COLD;
	}
	if (seed->age_ecology_ticks < PICOSYSTEM_GARDEN_SEED_DORMANCY_TICKS) {
		blockers |= PICOSYSTEM_GARDEN_SEED_BLOCKED_DORMANT;
	}
	if (world->moisture[soil_index(seed->column, 0U)] < GARDEN_SEED_MINIMUM_MOISTURE) {
		blockers |= PICOSYSTEM_GARDEN_SEED_BLOCKED_MOISTURE;
	}
	bool light_required = true;
#if defined(TOY_FACTORY_GARDEN_WET_GERMINATION)
	light_required = !world->wet_germination_enabled;
#endif
	if (light_required &&
	    (world->light[light_index(seed->column, PICOSYSTEM_GARDEN_CANOPY_ROWS - 1U)] <
	     GARDEN_SEED_MINIMUM_LIGHT)) {
		blockers |= PICOSYSTEM_GARDEN_SEED_BLOCKED_LIGHT;
	}
	if (world->plant_count >= plant_capacity(world)) {
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

#if !defined(__ZEPHYR__)
static void audit_seed_sites(const struct picosystem_garden_world *world, uint8_t *sites)
{
	for (uint8_t column = 0U; column < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++column) {
		const struct picosystem_garden_seed seed = {
			.column = column,
			.age_ecology_ticks = PICOSYSTEM_GARDEN_SEED_DORMANCY_TICKS,
		};
		sites[column] = seed_germination_blockers(world, &seed);
	}
}
#endif

static int update_seed_bank(struct picosystem_garden_world *world,
			    struct picosystem_garden_seed_audit *seed_audit)
{
	(void)seed_audit;
#if !defined(__ZEPHYR__)
	if (seed_audit != NULL) {
		struct picosystem_garden_seed_sites sites;
		const int err = picosystem_garden_world_seed_sites(world, &sites);
		if (err != 0) {
			return err;
		}
		memcpy(seed_audit->sites_before, sites.blockers, sizeof(sites.blockers));
		for (uint8_t index = 0U; index < world->plant_count; ++index) {
			seed_audit->dispersal_columns[world->plants[index].species_id] |=
				sites.dispersal_columns[index];
		}
	}
#endif
	uint8_t seed_index = 0U;
	while (seed_index < world->seed_count) {
		struct picosystem_garden_seed *const seed = &world->seeds[seed_index];
		++seed->age_ecology_ticks;
#if !defined(__ZEPHYR__)
		struct picosystem_garden_seed_attempt *attempt = NULL;
		if (seed_audit != NULL) {
			/* The bank only shrinks here; reproduction runs after this loop. */
			if (seed_audit->count >= PICOSYSTEM_GARDEN_MAX_SEEDS) {
				return -EFAULT;
			}
			attempt = &seed_audit->attempts[seed_audit->count++];
			*attempt = (struct picosystem_garden_seed_attempt){
				.parent = seed->parent_lineage_id,
				.age = seed->age_ecology_ticks,
				.generation = seed->generation,
				.nodes = world->node_count,
				.plants = world->plant_count,
				.column = seed->column,
				.species = seed->species_id,
			};
		}
#endif
		if (seed->age_ecology_ticks >= PICOSYSTEM_GARDEN_SEED_LIFETIME_TICKS) {
#if !defined(__ZEPHYR__)
			if (attempt != NULL) {
				attempt->outcome = PICOSYSTEM_GARDEN_SEED_EXPIRED;
			}
#endif
			remove_seed(world, seed_index);
			world->seed_expiration_count =
				saturating_add_u32(world->seed_expiration_count, 1U);
			continue;
		}
		const uint8_t blockers = seed_germination_blockers(world, seed);
#if !defined(__ZEPHYR__)
		if (attempt != NULL) {
			attempt->blockers = blockers;
			attempt->moisture = world->moisture[soil_index(seed->column, 0U)];
			attempt->light = world->light[light_index(
				seed->column, PICOSYSTEM_GARDEN_CANOPY_ROWS - 1U)];
			audit_seed_sites(world, attempt->sites);
		}
#endif
		if (blockers != 0U) {
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
#if !defined(__ZEPHYR__)
		if (attempt != NULL) {
			attempt->outcome = PICOSYSTEM_GARDEN_SEED_GERMINATED;
			attempt->child = world->lineage_sequence;
		}
#endif
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

int picosystem_garden_world_set_weather(struct picosystem_garden_world *world,
					uint32_t weather_seed)
{
	if (!world_is_valid(world)) {
		return -EINVAL;
	}
	world->weather_seed = weather_seed;
	return update_light(world);
}

int picosystem_garden_world_set_climate(struct picosystem_garden_world *world,
					enum picosystem_garden_climate_mode mode)
{
	if (!world_is_valid(world) || (mode < PICOSYSTEM_GARDEN_CLIMATE_STEADY) ||
	    (mode >= PICOSYSTEM_GARDEN_CLIMATE_COUNT) ||
	    ((world->logic_tick_count % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) != 0U)) {
		return -EINVAL;
	}
	world->climate_mode = (uint8_t)mode;
	return update_light(world);
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

static int step_input_with_policy(struct picosystem_garden_world *world, int8_t horizontal,
				  int8_t vertical,
				  const struct picosystem_garden_agent_policy *policy,
				  const struct garden_step_audits *audits)
{
	struct picosystem_garden_water_audit *const water_audit = audits ? audits->water : NULL;
	struct picosystem_garden_seed_audit *const seed_audit = audits ? audits->seed : NULL;
	struct picosystem_garden_death_audit *const death_audit = audits ? audits->death : NULL;
	struct picosystem_garden_reproduction_audit *const reproduction_audit =
		audits ? audits->reproduction : NULL;
	struct picosystem_garden_flower_audit *const flower_audit = audits ? audits->flower : NULL;
	(void)water_audit;
	(void)seed_audit;
	if ((policy == NULL) || (policy->decide == NULL) ||
	    ((uint32_t)policy->arbitration >= PICOSYSTEM_GARDEN_AGENT_ARBITRATION_COUNT) ||
	    !world_is_valid(world)) {
		return -EINVAL;
	}
#if !defined(__ZEPHYR__)
	if (policy->seed_replacement_after != 0U) {
		if ((policy->place_seed == NULL) || world->auto_gardener_enabled ||
		    (policy->seed_replacement_after %
			     (PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR *
			      PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR) !=
		     0U)) {
			return -EINVAL;
		}
#if defined(TOY_FACTORY_GARDEN_WIDE_DISPERSAL) || defined(TOY_FACTORY_GARDEN_FLOWER_DISPERSAL) ||  \
	defined(TOY_FACTORY_GARDEN_WATER_HEADROOM) ||                                              \
	defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE) || defined(TOY_FACTORY_GARDEN_LARGE_POOL) ||  \
	defined(TOY_FACTORY_GARDEN_SEASONAL_SEED_BANK)
		return -ENOTSUP;
#endif
	}
	/* The placement observation describes ordinary base-origin dispersal only. */
#if defined(TOY_FACTORY_GARDEN_WIDE_DISPERSAL) || defined(TOY_FACTORY_GARDEN_FLOWER_DISPERSAL)
	if (policy->place_seed != NULL) {
		return -ENOTSUP;
	}
#endif
	if ((policy->eligible != NULL) &&
	    (policy->arbitration != PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS)) {
		return -EINVAL;
	}
#endif
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
#if !defined(__ZEPHYR__)
	if (death_audit != NULL) {
		death_audit->ecology_step = true;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_FULL_POOL)
	world->full_pool.count = 0U;
	world->full_pool.overflow = false;
#endif
#if defined(TOY_FACTORY_GARDEN_NIGHT_CAPACITY)
	world->night_capacity.count = 0U;
	world->night_capacity.overflow = false;
#endif
#if defined(TOY_FACTORY_GARDEN_DARK_GUARD)
	world->dark_guard.count = 0U;
	world->dark_guard.overflow = false;
#endif
	AUDIT_SEED(START);
	AUDIT_WATER(START);
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	wear_leaves(world);
#endif
	update_rain(world);
	AUDIT_WATER(RAIN);
	int err = update_moisture(world);
	if (err != 0) {
		return err;
	}
#if defined(TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE)
	const uint32_t drained = drain_bottom(world);
	if (water_audit != NULL) {
		water_audit->drainage = drained;
	}
#endif
	AUDIT_WATER(TRANSPORT);
	err = update_light_observed(world, audits ? audits->uptake : NULL);
	if (err != 0) {
		return err;
	}
	absorb_water_and_light(world, death_audit, audits ? audits->uptake : NULL);
	AUDIT_RESOURCE(UPTAKE);
	AUDIT_WATER(UPTAKE);
	err = update_decomposition(world);
	if (err != 0) {
		return err;
	}
	AUDIT_WATER(DECOMPOSITION);
	update_plant_maintenance(world, death_audit);
	AUDIT_RESOURCE(MAINTENANCE);
	AUDIT_WATER(MAINTENANCE);
	AUDIT_SEED(BEFORE_CHECKS);
	err = update_seed_bank(world, seed_audit);
	if (err != 0) {
		return err;
	}
	AUDIT_WATER(GERMINATION);
	AUDIT_SEED(AFTER_CHECKS);
	AUDIT_RESOURCE(GERMINATION);
#if !defined(__ZEPHYR__)
	if ((audits != NULL) && (audits->landing != NULL)) {
		err = picosystem_garden_landing_capture(world, false, audits->landing);
		if (err != 0) {
			return err;
		}
	}
#endif
	err = grow_plants(world, policy);
	if (err != 0) {
		return err;
	}
	AUDIT_WATER(GROWTH);
	AUDIT_SEED(AFTER_GROWTH);
	AUDIT_RESOURCE(GROWTH);
	err = update_reproduction(world, reproduction_audit, flower_audit, seed_audit, policy);
	if (err != 0) {
		return err;
	}
	AUDIT_RESOURCE(REPRODUCTION);
	AUDIT_SEED(AFTER_REPRODUCTION);
	AUDIT_WATER(REPRODUCTION);
	err = update_light(world);
	if (err != 0) {
		return err;
	}
	update_moisture_total(world);
	return 0;
}

int picosystem_garden_world_step_input_with_policy(
	struct picosystem_garden_world *world, int8_t horizontal, int8_t vertical,
	const struct picosystem_garden_agent_policy *policy)
{
	return step_input_with_policy(world, horizontal, vertical, policy, NULL);
}

#if !defined(__ZEPHYR__)
int picosystem_garden_landing_reset(const struct picosystem_garden_world *world,
				    struct picosystem_garden_landing_cache *cache)
{
	if ((cache == NULL) || !world_is_valid(world) || world->auto_gardener_enabled ||
	    (world->logic_tick_count != 0U) || (world->ecology_tick_count != 0U)) {
		return -EINVAL;
	}
#if defined(TOY_FACTORY_GARDEN_COMBINED_EXPERIMENT) ||                                             \
	defined(TOY_FACTORY_GARDEN_WATER_HEADROOM) ||                                              \
	defined(TOY_FACTORY_GARDEN_SEASONAL_SEED_BANK)
	return -ENOTSUP;
#else
	return picosystem_garden_landing_capture(world, true, cache);
#endif
}

static void compact_death_receipts(struct picosystem_garden_death_audit *result)
{
	/* Only deaths escape the private per-living-plant uptake scratch space. */
	uint8_t count = 0U;
	for (uint8_t index = 0U; index < result->count; ++index) {
		if ((result->events[index].flags & PICOSYSTEM_GARDEN_PLANT_DEAD) != 0U) {
			result->events[count++] = result->events[index];
		}
	}
	memset(&result->events[count], 0,
	       (PICOSYSTEM_GARDEN_MAX_PLANTS - count) * sizeof(result->events[0]));
	result->count = count;
}

static int step_landing(struct picosystem_garden_world *world,
			const struct picosystem_garden_agent_policy *policy,
			struct picosystem_garden_landing_cache *cache,
			struct picosystem_garden_death_audit *audit,
			struct picosystem_garden_seed_audit *seed_audit,
			struct picosystem_garden_resource_audit *resource_audit,
			struct picosystem_garden_reproduction_audit *reproduction_audit,
			struct picosystem_garden_uptake_audit *uptake_audit)
{
	if (!world_is_valid(world) || world->auto_gardener_enabled ||
	    !picosystem_garden_landing_cache_is_valid(cache) ||
	    (cache->ecology_tick != world->ecology_tick_count) ||
	    (world->logic_tick_count == UINT32_MAX) ||
	    (world->logic_tick_count / PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR !=
	     world->ecology_tick_count)) {
		return -EINVAL;
	}
#if defined(TOY_FACTORY_GARDEN_COMBINED_EXPERIMENT) ||                                             \
	defined(TOY_FACTORY_GARDEN_WATER_HEADROOM) ||                                              \
	defined(TOY_FACTORY_GARDEN_SEASONAL_SEED_BANK)
	(void)policy;
	(void)audit;
	(void)seed_audit;
	(void)resource_audit;
	(void)reproduction_audit;
	(void)uptake_audit;
	return -ENOTSUP;
#else
	/* Publish before callbacks, but do not retain a sample from a failed step. */
	const struct picosystem_garden_landing_cache before = *cache;
	struct picosystem_garden_death_audit deaths = {0};
	struct picosystem_garden_seed_audit seeds = {0};
	struct picosystem_garden_resource_audit resources = {0};
	struct picosystem_garden_reproduction_audit reproduction = {0};
	struct picosystem_garden_uptake_audit uptake;
	if (uptake_audit != NULL) {
		memset(&uptake, 0, sizeof(uptake));
	}
	const struct garden_step_audits audits = {
		.landing = cache,
		.death = (audit != NULL) ? &deaths : NULL,
		.seed = (seed_audit != NULL) ? &seeds : NULL,
		.resources = (resource_audit != NULL) ? &resources : NULL,
		.reproduction = (reproduction_audit != NULL) ? &reproduction : NULL,
		.uptake = (uptake_audit != NULL) ? &uptake : NULL};
	const int err = step_input_with_policy(world, 0, 0, policy, &audits);
	if (err != 0) {
		*cache = before;
	} else if (audit != NULL) {
		if (resource_audit != NULL) {
			resources.uptake = deaths;
			*resource_audit = resources;
		}
		compact_death_receipts(&deaths);
		*audit = deaths;
	}
	if ((err == 0) && (seed_audit != NULL)) {
		*seed_audit = seeds;
	}
	if ((err == 0) && (reproduction_audit != NULL)) {
		*reproduction_audit = reproduction;
	}
	if ((err == 0) && (uptake_audit != NULL)) {
		*uptake_audit = uptake;
	}
	return err;
#endif
}

int picosystem_garden_world_step_landing(struct picosystem_garden_world *world,
					 const struct picosystem_garden_agent_policy *policy,
					 struct picosystem_garden_landing_cache *cache)
{
	return step_landing(world, policy, cache, NULL, NULL, NULL, NULL, NULL);
}

int picosystem_garden_world_step_landing_death_audit(
	struct picosystem_garden_world *world, const struct picosystem_garden_agent_policy *policy,
	struct picosystem_garden_landing_cache *cache, struct picosystem_garden_death_audit *audit)
{
	if (audit == NULL) {
		return -EINVAL;
	}
	return step_landing(world, policy, cache, audit, NULL, NULL, NULL, NULL);
}

int picosystem_garden_world_step_landing_audits(struct picosystem_garden_world *world,
						const struct picosystem_garden_agent_policy *policy,
						struct picosystem_garden_landing_cache *cache,
						struct picosystem_garden_death_audit *deaths,
						struct picosystem_garden_seed_audit *seeds)
{
	return ((deaths == NULL) || (seeds == NULL))
		       ? -EINVAL
		       : step_landing(world, policy, cache, deaths, seeds, NULL, NULL, NULL);
}

int picosystem_garden_world_step_landing_resources(
	struct picosystem_garden_world *world, const struct picosystem_garden_agent_policy *policy,
	struct picosystem_garden_landing_cache *cache, struct picosystem_garden_death_audit *deaths,
	struct picosystem_garden_seed_audit *seeds,
	struct picosystem_garden_resource_audit *resources)
{
	return ((deaths == NULL) || (seeds == NULL) || (resources == NULL))
		       ? -EINVAL
		       : step_landing(world, policy, cache, deaths, seeds, resources, NULL, NULL);
}

int picosystem_garden_world_step_landing_reproduction(
	struct picosystem_garden_world *world, const struct picosystem_garden_agent_policy *policy,
	struct picosystem_garden_landing_cache *cache, struct picosystem_garden_death_audit *deaths,
	struct picosystem_garden_seed_audit *seeds,
	struct picosystem_garden_resource_audit *resources,
	struct picosystem_garden_reproduction_audit *reproduction)
{
	if ((world == NULL) || (deaths == NULL) || (seeds == NULL) || (resources == NULL) ||
	    (reproduction == NULL)) {
		return -EINVAL;
	}
#if defined(TOY_FACTORY_GARDEN_SEED_RESERVE) || defined(TOY_FACTORY_GARDEN_FOCAL_SEED_VETO) ||     \
	defined(TOY_FACTORY_GARDEN_DARK_GUARD) || defined(TOY_FACTORY_GARDEN_SEED_ORDER)
	(void)policy;
	(void)cache;
	return -ENOTSUP;
#else
	return step_landing(world, policy, cache, deaths, seeds, resources, reproduction, NULL);
#endif
}

int picosystem_garden_world_step_landing_uptake(
	struct picosystem_garden_world *world, const struct picosystem_garden_agent_policy *policy,
	struct picosystem_garden_landing_cache *cache, struct picosystem_garden_death_audit *deaths,
	struct picosystem_garden_seed_audit *seeds,
	struct picosystem_garden_resource_audit *resources,
	struct picosystem_garden_reproduction_audit *reproduction,
	struct picosystem_garden_uptake_audit *uptake)
{
	if ((world == NULL) || (deaths == NULL) || (seeds == NULL) || (resources == NULL) ||
	    (reproduction == NULL) || (uptake == NULL)) {
		return -EINVAL;
	}
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE) ||                                                \
	defined(TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION) ||                                         \
	defined(TOY_FACTORY_GARDEN_WATER_HEADROOM) || defined(TOY_FACTORY_GARDEN_SEED_RESERVE) ||  \
	defined(TOY_FACTORY_GARDEN_FOCAL_SEED_VETO) || defined(TOY_FACTORY_GARDEN_DARK_GUARD) ||   \
	defined(TOY_FACTORY_GARDEN_SEED_ORDER)
	(void)policy;
	(void)cache;
	return -ENOTSUP;
#else
	return step_landing(world, policy, cache, deaths, seeds, resources, reproduction, uptake);
#endif
}

int picosystem_garden_world_step_death_audit(struct picosystem_garden_world *world,
					     const struct picosystem_garden_agent_policy *policy,
					     struct picosystem_garden_death_audit *audit)
{
	if ((audit == NULL) || (world == NULL) || world->auto_gardener_enabled) {
		return -EINVAL;
	}
	struct picosystem_garden_death_audit result = {0};
	const struct garden_step_audits audits = {.death = &result};
	const int err = step_input_with_policy(world, 0, 0, policy, &audits);
	if (err == 0) {
		compact_death_receipts(&result);
		*audit = result;
	}
	return err;
}
#endif

#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
int picosystem_garden_world_step_water_audit(struct picosystem_garden_world *world,
					     const struct picosystem_garden_agent_policy *policy,
					     struct picosystem_garden_water_audit *audit)
{
	if ((audit == NULL) || (world == NULL) || world->auto_gardener_enabled) {
		return -EINVAL;
	}
	struct picosystem_garden_water_audit result = {0};
	const struct garden_step_audits audits = {.water = &result};
	const int err = step_input_with_policy(world, 0, 0, policy, &audits);
	if (err == 0) {
		*audit = result;
	}
	return err;
}

#endif

#if !defined(__ZEPHYR__)
int picosystem_garden_world_step_seed_audit(struct picosystem_garden_world *world,
					    const struct picosystem_garden_agent_policy *policy,
					    struct picosystem_garden_seed_audit *audit)
{
	if ((audit == NULL) || (world == NULL) || world->auto_gardener_enabled) {
		return -EINVAL;
	}
	struct picosystem_garden_seed_audit result = {0};
	const struct garden_step_audits audits = {.seed = &result};
	const int err = step_input_with_policy(world, 0, 0, policy, &audits);
	if (err == 0) {
		*audit = result;
	}
	return err;
}

int picosystem_garden_world_step_reproduction_audit(
	struct picosystem_garden_world *world, const struct picosystem_garden_agent_policy *policy,
	struct picosystem_garden_reproduction_audit *audit)
{
	if ((audit == NULL) || (world == NULL) || world->auto_gardener_enabled) {
		return -EINVAL;
	}
#if defined(TOY_FACTORY_GARDEN_SEED_RESERVE) || defined(TOY_FACTORY_GARDEN_FOCAL_SEED_VETO) ||     \
	defined(TOY_FACTORY_GARDEN_DARK_GUARD) || defined(TOY_FACTORY_GARDEN_SEED_ORDER)
	(void)policy;
	return -ENOTSUP;
#else
	struct picosystem_garden_reproduction_audit result = {0};
	const struct garden_step_audits audits = {.reproduction = &result};
	const int err = step_input_with_policy(world, 0, 0, policy, &audits);
	if (err == 0) {
		*audit = result;
	}
	return err;
#endif
}

int picosystem_garden_world_step_flower_audit(struct picosystem_garden_world *world,
					      const struct picosystem_garden_agent_policy *policy,
					      struct picosystem_garden_flower_audit *audit)
{
	if ((audit == NULL) || (world == NULL) || world->auto_gardener_enabled) {
		return -EINVAL;
	}
#if defined(TOY_FACTORY_GARDEN_COMBINED_EXPERIMENT) ||                                             \
	defined(TOY_FACTORY_GARDEN_WATER_HEADROOM) ||                                              \
	defined(TOY_FACTORY_GARDEN_SEASONAL_SEED_BANK)
	(void)policy;
	return -ENOTSUP;
#else
	struct picosystem_garden_flower_audit result = {0};
	const struct garden_step_audits audits = {.reproduction = &result.production,
						  .flower = &result};
	const int err = step_input_with_policy(world, 0, 0, policy, &audits);
	if (err == 0) {
		if (result.count > 0U) {
			uint8_t blockers[PICOSYSTEM_GARDEN_GRID_COLUMNS];
			audit_seed_sites(world, blockers);
			for (uint8_t column = 0U; column < PICOSYSTEM_GARDEN_GRID_COLUMNS;
			     ++column) {
				result.sites[column] = (struct picosystem_garden_flower_site){
					.moisture = world->moisture[soil_index(column, 0U)],
					.light = world->light[light_index(
						column, PICOSYSTEM_GARDEN_CANOPY_ROWS - 1U)],
					.blockers = blockers[column],
				};
			}
		}
		*audit = result;
	}
	return err;
#endif
}
#endif

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

int picosystem_garden_world_seed_sites(const struct picosystem_garden_world *world,
				       struct picosystem_garden_seed_sites *sites)
{
	_Static_assert(PICOSYSTEM_GARDEN_GRID_COLUMNS <= 32U,
		       "dispersal columns must fit a bit set");
	if ((sites == NULL) || !world_is_valid(world)) {
		return -EINVAL;
	}
	struct picosystem_garden_seed_sites result = {0};
	for (uint8_t column = 0U; column < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++column) {
		const struct picosystem_garden_seed seed = {
			.column = column,
			.age_ecology_ticks = PICOSYSTEM_GARDEN_SEED_DORMANCY_TICKS,
		};
		result.blockers[column] = seed_germination_blockers(world, &seed);
	}
	for (uint8_t index = 0U; index < world->plant_count; ++index) {
		if (plant_is_dead(&world->plants[index])) {
			continue;
		}
		uint16_t flower_index = PICOSYSTEM_GARDEN_NODE_NONE;
#if defined(TOY_FACTORY_GARDEN_FLOWER_DISPERSAL)
		flower_index = unseeded_flower_index(world, index);
		if (flower_index == PICOSYSTEM_GARDEN_NODE_NONE) {
			continue;
		}
#endif
		const uint8_t origin = seed_origin_column(world, index, flower_index);
		/* The placement helper uses one direction bit and a fixed distance range.
		 * Enumerate their support, not probabilities or the parent's next RNG draw.
		 */
		for (uint32_t choice = 0U;
		     choice < picosystem_garden_dispersal_choices_at(world->logic_tick_count);
		     ++choice) {
			const uint8_t column = dispersed_seed_column(
				&world->plants[index], origin, choice, world->logic_tick_count);
			result.dispersal_columns[index] |= UINT32_C(1) << column;
		}
	}
	*sites = result;
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
	hash = fnv1a_u32(hash, PICOSYSTEM_GARDEN_SEED_LIFETIME_TICKS);
	hash = fnv1a_byte(hash, world->climate_mode);
	if (world->climate_mode != PICOSYSTEM_GARDEN_CLIMATE_STEADY) {
		hash = fnv1a_u32(hash, PICOSYSTEM_GARDEN_CLIMATE_VERSION);
	}
#if defined(TOY_FACTORY_GARDEN_WET_GERMINATION)
	if (world->wet_germination_enabled) {
		hash = fnv1a_u32(hash, UINT32_C(0x57475431)); /* WGT1 active rule identity. */
	}
#endif
#if defined(TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE)
	hash = fnv1a_u32(hash, UINT32_C(0x44524e31)); /* DRN1 rule identity. */
#endif
#if defined(TOY_FACTORY_GARDEN_SOIL_WICKING)
	hash = fnv1a_u32(hash, UINT32_C(0x57494331)); /* WIC1 rule identity, even before onset. */
	hash = fnv1a_u32(hash, PICOSYSTEM_GARDEN_WICKING_VERSION);
	hash = fnv1a_u32(hash, PICOSYSTEM_GARDEN_WICKING_AFTER_TICK);
	hash = fnv1a_u32(hash, PICOSYSTEM_GARDEN_WICKING_PERIOD);
#endif
#if defined(TOY_FACTORY_GARDEN_LATE_UPTAKE_LIMIT)
	hash = fnv1a_u32(hash, UINT32_C(0x554c5431)); /* ULT1 identity, even before onset. */
	hash = fnv1a_u32(hash, PICOSYSTEM_GARDEN_UPTAKE_LIMIT_VERSION);
	hash = fnv1a_u32(hash, PICOSYSTEM_GARDEN_UPTAKE_LIMIT_AFTER_TICK);
	hash = fnv1a_u32(hash, PICOSYSTEM_GARDEN_UPTAKE_LIMIT_CAPACITY);
#endif
#if defined(TOY_FACTORY_GARDEN_LATE_DISPERSAL)
	hash = fnv1a_u32(hash, UINT32_C(0x4c445331)); /* LDS1 identity, even before onset. */
	hash = fnv1a_u32(hash, PICOSYSTEM_GARDEN_LATE_DISPERSAL_VERSION);
	hash = fnv1a_u32(hash, PICOSYSTEM_GARDEN_LATE_DISPERSAL_AFTER_TICK);
	hash = fnv1a_u32(hash, PICOSYSTEM_GARDEN_LATE_DISPERSAL_MINIMUM);
	hash = fnv1a_u32(hash, PICOSYSTEM_GARDEN_LATE_DISPERSAL_DISTANCES);
#endif
	/* Weather has its own identity, independent of plant randomness. */
	if (world->weather_seed != 0U) {
		hash = fnv1a_u32(hash, GARDEN_WEATHER_HASH_TAG);
		hash = fnv1a_u32(hash, PICOSYSTEM_GARDEN_RAIN_VERSION);
		hash = fnv1a_u32(hash, world->weather_seed);
	}
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
		hash = fnv1a_u16(hash, (uint16_t)plant->age_ecology_ticks);
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
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	hash = fnv1a_u32(hash, UINT32_C(0x4c454631)); /* LEF1 environment/state extension. */
	for (uint16_t index = 0U; index < world->node_count; ++index) {
		hash = fnv1a_byte(hash, world->leaf_condition[index]);
	}
	for (uint8_t index = 0U; index < world->plant_count; ++index) {
		hash = fnv1a_byte(hash, world->plants[index].leaf_energy_remainder);
	}
#endif
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
	/* Preserve pre-wrap v5 hashes, but include every high age word once needed. */
	for (uint8_t index = 0U; index < world->plant_count; ++index) {
		if (world->plants[index].age_ecology_ticks > UINT16_MAX) {
			hash = fnv1a_u32(hash, GARDEN_LONG_AGE_HASH_TAG);
			for (uint8_t owner = 0U; owner < world->plant_count; ++owner) {
				hash = fnv1a_u16(
					hash,
					(uint16_t)(world->plants[owner].age_ecology_ticks >> 16U));
			}
			break;
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
