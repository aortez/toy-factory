/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_GARDEN_WORLD_H_
#define PICOSYSTEM_GARDEN_WORLD_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define PICOSYSTEM_GARDEN_GRID_COLUMNS 28U
#define PICOSYSTEM_GARDEN_CANOPY_ROWS  14U
#define PICOSYSTEM_GARDEN_SOIL_ROWS    11U
#define PICOSYSTEM_GARDEN_CURSOR_ROWS  (PICOSYSTEM_GARDEN_CANOPY_ROWS + PICOSYSTEM_GARDEN_SOIL_ROWS)
#define PICOSYSTEM_GARDEN_SOIL_CELL_COUNT                                                          \
	(PICOSYSTEM_GARDEN_GRID_COLUMNS * PICOSYSTEM_GARDEN_SOIL_ROWS)
#define PICOSYSTEM_GARDEN_LIGHT_CELL_COUNT                                                         \
	(PICOSYSTEM_GARDEN_GRID_COLUMNS * PICOSYSTEM_GARDEN_CANOPY_ROWS)
#define PICOSYSTEM_GARDEN_CELL_PIXELS       8U
#define PICOSYSTEM_GARDEN_ORIGIN_X_PIXELS   8U
#define PICOSYSTEM_GARDEN_CANOPY_TOP_PIXELS 32U
#define PICOSYSTEM_GARDEN_SOIL_TOP_PIXELS                                                          \
	(PICOSYSTEM_GARDEN_CANOPY_TOP_PIXELS +                                                     \
	 (PICOSYSTEM_GARDEN_CANOPY_ROWS * PICOSYSTEM_GARDEN_CELL_PIXELS))
#define PICOSYSTEM_GARDEN_MAX_PLANTS                8U
#define PICOSYSTEM_GARDEN_MAX_NODES                 256U
#define PICOSYSTEM_GARDEN_NODE_NONE                 UINT16_MAX
#define PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR      15U
#define PICOSYSTEM_GARDEN_NODE_GROWTH_TICKS         12U
#define PICOSYSTEM_GARDEN_LEAF_ACTIVE_PROGRESS      96U
#define PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR  4U
#define PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD    8U
#define PICOSYSTEM_GARDEN_AUTO_CURSOR_TICK_DIVISOR  4U
#define PICOSYSTEM_GARDEN_CURSOR_REPEAT_DELAY_TICKS 10U
#define PICOSYSTEM_GARDEN_CURSOR_REPEAT_RATE_TICKS  4U

enum picosystem_garden_species_id {
	PICOSYSTEM_GARDEN_SPECIES_FLOWER,
	PICOSYSTEM_GARDEN_SPECIES_SHRUB,
	PICOSYSTEM_GARDEN_SPECIES_GROUND_COVER,
	PICOSYSTEM_GARDEN_SPECIES_COUNT,
};

enum picosystem_garden_node_kind {
	PICOSYSTEM_GARDEN_NODE_STEM,
	PICOSYSTEM_GARDEN_NODE_ROOT,
	PICOSYSTEM_GARDEN_NODE_KIND_COUNT,
};

enum picosystem_garden_node_flag {
	PICOSYSTEM_GARDEN_NODE_TIP = 1U << 0,
	PICOSYSTEM_GARDEN_NODE_LEAF = 1U << 1,
	PICOSYSTEM_GARDEN_NODE_FLOWER = 1U << 2,
	PICOSYSTEM_GARDEN_NODE_PRUNED = 1U << 3,
	PICOSYSTEM_GARDEN_NODE_BRANCH_PENDING = 1U << 4,
};

#define PICOSYSTEM_GARDEN_NODE_VALID_FLAGS                                                         \
	(PICOSYSTEM_GARDEN_NODE_TIP | PICOSYSTEM_GARDEN_NODE_LEAF |                                \
	 PICOSYSTEM_GARDEN_NODE_FLOWER | PICOSYSTEM_GARDEN_NODE_PRUNED |                           \
	 PICOSYSTEM_GARDEN_NODE_BRANCH_PENDING)

enum picosystem_garden_plant_flag {
	PICOSYSTEM_GARDEN_PLANT_DEAD = 1U << 0,
	PICOSYSTEM_GARDEN_PLANT_ENERGY_SHORTAGE = 1U << 1,
	PICOSYSTEM_GARDEN_PLANT_WATER_SHORTAGE = 1U << 2,
};

#define PICOSYSTEM_GARDEN_PLANT_VALID_FLAGS                                                        \
	(PICOSYSTEM_GARDEN_PLANT_DEAD | PICOSYSTEM_GARDEN_PLANT_ENERGY_SHORTAGE |                  \
	 PICOSYSTEM_GARDEN_PLANT_WATER_SHORTAGE)

enum picosystem_garden_tool {
	PICOSYSTEM_GARDEN_TOOL_FLOWER_SEED,
	PICOSYSTEM_GARDEN_TOOL_SHRUB_SEED,
	PICOSYSTEM_GARDEN_TOOL_GROUND_COVER_SEED,
	PICOSYSTEM_GARDEN_TOOL_WATER,
	PICOSYSTEM_GARDEN_TOOL_PRUNE,
	PICOSYSTEM_GARDEN_TOOL_COUNT,
};

struct picosystem_garden_node {
	uint16_t parent_index;
	uint8_t x;
	uint8_t y;
	uint8_t plant_index;
	uint8_t depth;
	uint8_t growth_progress;
	uint8_t child_count;
	uint8_t kind;
	uint8_t flags;
};

struct picosystem_garden_plant {
	uint32_t random_state;
	uint16_t base_node_index;
	uint16_t last_shoot_tip_index;
	uint16_t last_root_tip_index;
	uint16_t stored_energy;
	uint16_t stored_water;
	uint16_t age_ecology_ticks;
	uint16_t node_count;
	uint8_t base_column;
	uint8_t growth_cooldown;
	uint8_t growth_phase;
	uint8_t species_id;
	int8_t lean;
	int8_t vigor;
	uint8_t stress;
	uint8_t flags;
	uint8_t last_energy_income;
	uint8_t last_water_income;
};

/* Caller-owned fixed-capacity state; no garden operation allocates memory. */
struct picosystem_garden_world {
	struct picosystem_garden_node nodes[PICOSYSTEM_GARDEN_MAX_NODES];
	struct picosystem_garden_plant plants[PICOSYSTEM_GARDEN_MAX_PLANTS];
	uint8_t moisture[PICOSYSTEM_GARDEN_SOIL_CELL_COUNT];
	uint8_t light[PICOSYSTEM_GARDEN_LIGHT_CELL_COUNT];
	uint32_t random_state;
	uint32_t logic_tick_count;
	uint32_t ecology_tick_count;
	uint32_t manual_action_count;
	uint32_t auto_decision_count;
	uint32_t auto_action_count;
	uint32_t bloom_count;
	uint32_t death_count;
	uint32_t reclaimed_plant_count;
	uint32_t reclaimed_node_count;
	uint16_t node_count;
	uint16_t moisture_total;
	uint8_t plant_count;
	uint8_t cursor_column;
	uint8_t cursor_row;
	uint8_t selected_tool;
	uint8_t auto_target_column;
	uint8_t auto_target_row;
	uint8_t auto_target_tool;
	uint8_t cursor_repeat_ticks;
	int8_t previous_horizontal_input;
	int8_t previous_vertical_input;
	bool auto_gardener_enabled;
	bool auto_target_valid;
};

/* Restore an empty, reproducible garden. A zero seed selects a stable default. */
int picosystem_garden_world_reset(struct picosystem_garden_world *world, uint32_t random_seed);

/* Append one seedling after validating spacing and fixed capacities. */
int picosystem_garden_world_plant_seed(struct picosystem_garden_world *world,
				       enum picosystem_garden_species_id species_id,
				       uint8_t column);

/* Deposit a bounded amount of water around one soil column. */
int picosystem_garden_world_water(struct picosystem_garden_world *world, uint8_t column,
				  uint8_t amount);

/* Pinch the nearest active shoot tip so its next segment turns and branches. */
int picosystem_garden_world_prune(struct picosystem_garden_world *world, uint8_t column,
				  uint8_t row);

/* Move the visible cursor by one bounded grid step. */
int picosystem_garden_world_move_cursor(struct picosystem_garden_world *world, int8_t horizontal,
					int8_t vertical);

/* Select the following tool, wrapping at the end of the palette. */
int picosystem_garden_world_cycle_tool(struct picosystem_garden_world *world);

/* Apply the selected tool at the cursor through the ordinary manual action path. */
int picosystem_garden_world_use_tool(struct picosystem_garden_world *world);

/* Enable or disable the deterministic policy without changing garden contents. */
int picosystem_garden_world_set_auto_gardener(struct picosystem_garden_world *world, bool enabled);

/* Advance exactly one 1/60-second authoritative tick. */
int picosystem_garden_world_step(struct picosystem_garden_world *world);

/* Advance one tick while applying immediate-then-repeating cursor input. */
int picosystem_garden_world_step_input(struct picosystem_garden_world *world, int8_t horizontal,
				       int8_t vertical);

const struct picosystem_garden_node *
picosystem_garden_world_node_at(const struct picosystem_garden_world *world, size_t index);

const struct picosystem_garden_plant *
picosystem_garden_world_plant_at(const struct picosystem_garden_world *world, size_t index);

uint8_t picosystem_garden_world_living_plant_count(const struct picosystem_garden_world *world);
uint8_t picosystem_garden_world_dead_plant_count(const struct picosystem_garden_world *world);

/* Hash persistent and presentation-visible state without structure padding. */
uint32_t picosystem_garden_world_hash(const struct picosystem_garden_world *world);

const char *picosystem_garden_species_name(enum picosystem_garden_species_id species_id);
const char *picosystem_garden_tool_name(enum picosystem_garden_tool tool);

#endif /* PICOSYSTEM_GARDEN_WORLD_H_ */
