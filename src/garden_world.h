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
#define PICOSYSTEM_GARDEN_DEFAULT_PLANTS 8U
#if defined(TOY_FACTORY_GARDEN_FULL_POOL)
#include "garden_full_pool.h"
#endif
#if defined(TOY_FACTORY_GARDEN_PLANT_SLOTS)
#include "garden_plant_slots.h"
#define PICOSYSTEM_GARDEN_MAX_PLANTS 16U
#else
#define PICOSYSTEM_GARDEN_MAX_PLANTS PICOSYSTEM_GARDEN_DEFAULT_PLANTS
#endif
#if defined(TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION)
#include "garden_canopy_transmission.h"
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_SPACING)
#include "garden_seed_spacing.h"
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_ORDER)
#include "garden_seed_order.h"
#endif
#if defined(TOY_FACTORY_GARDEN_DAWN_FINISH)
#include "garden_dawn_finish.h"
#endif
#if defined(TOY_FACTORY_GARDEN_WET_GERMINATION)
#if defined(__ZEPHYR__) || !defined(TOY_FACTORY_GARDEN_NIGHT_CAPACITY)
#error "Wet germination requires the host-only night-capacity experiment"
#endif
#define PICOSYSTEM_GARDEN_WET_GERMINATION_NAME "wet-germination-v1"
#endif
#if defined(TOY_FACTORY_GARDEN_NIGHT_CAPACITY)
#include "garden_night_capacity.h"
#endif
#if defined(TOY_FACTORY_GARDEN_PURCHASE_VETO)
#include "garden_purchase_veto.h"
#endif
#if defined(TOY_FACTORY_GARDEN_DARK_GUARD)
#if defined(__ZEPHYR__) || !defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE) ||                        \
	!defined(TOY_FACTORY_GARDEN_LARGE_POOL) || defined(TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE) ||  \
	defined(TOY_FACTORY_GARDEN_LARGE_SEED_BANK) || defined(TOY_FACTORY_GARDEN_SEED_RESERVE) || \
	defined(TOY_FACTORY_GARDEN_FOCAL_SEED_VETO)
#error "Dark guard requires the ordinary undrained eight-seed host maintenance experiment"
#endif
#include "garden_dark_guard.h"
#endif
#if defined(TOY_FACTORY_GARDEN_FOCAL_SEED_VETO)
#if defined(__ZEPHYR__) || !defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE) ||                        \
	!defined(TOY_FACTORY_GARDEN_LARGE_POOL) || defined(TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE) ||  \
	defined(TOY_FACTORY_GARDEN_LARGE_SEED_BANK) || defined(TOY_FACTORY_GARDEN_SEED_RESERVE)
#error "Focal seed veto requires the ordinary undrained eight-seed host maintenance experiment"
#endif
#define PICOSYSTEM_GARDEN_FOCAL_SEED_VETO_NAME "founder-2-second-day-three-seeds-v1"
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_RESERVE)
#if defined(__ZEPHYR__) || !defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE) ||                        \
	!defined(TOY_FACTORY_GARDEN_LARGE_POOL) || defined(TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE)
#error "Seed reserve requires the undrained 512-node host maintenance experiment"
#endif
#define PICOSYSTEM_GARDEN_SEED_RESERVE_NAME "sunset-seed-reserve-v1"
#endif
#if defined(TOY_FACTORY_GARDEN_LARGE_POOL)
#if defined(__ZEPHYR__) || !defined(TOY_FACTORY_GARDEN_COMBINED_EXPERIMENT)
#error "Large node pool requires the explicit combined host experiment"
#endif
#define PICOSYSTEM_GARDEN_MAX_NODES 512U
#else
#define PICOSYSTEM_GARDEN_MAX_NODES 256U
#endif
#if defined(TOY_FACTORY_GARDEN_LARGE_SEED_BANK)
#if defined(__ZEPHYR__) || !defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE) ||                        \
	!defined(TOY_FACTORY_GARDEN_LARGE_POOL) || defined(TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE)
#error "Large seed bank requires the undrained 512-node host maintenance experiment"
#endif
#define PICOSYSTEM_GARDEN_MAX_SEEDS 16U
#else
#define PICOSYSTEM_GARDEN_MAX_SEEDS 8U
#endif
#define PICOSYSTEM_GARDEN_NODE_NONE                 UINT16_MAX
#define PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR      15U
#define PICOSYSTEM_GARDEN_NODE_GROWTH_TICKS         12U
#define PICOSYSTEM_GARDEN_LEAF_ACTIVE_PROGRESS      96U
#define PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR  4U
#define PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD    8U
#define PICOSYSTEM_GARDEN_NIGHT_RESERVE_PERIODS     40
#define PICOSYSTEM_GARDEN_RESERVE_TRAIT_PERIOD_STEP 4
#define PICOSYSTEM_GARDEN_SEED_DORMANCY_TICKS       8U
#define PICOSYSTEM_GARDEN_SEED_LIFETIME_TICKS       256U
#define PICOSYSTEM_GARDEN_GENOME_TRAIT_MIN          (-2)
#define PICOSYSTEM_GARDEN_GENOME_TRAIT_MAX          2
#define PICOSYSTEM_GARDEN_AGENT_MEMORY_WIDTH        8U
#define PICOSYSTEM_GARDEN_AUTO_CURSOR_TICK_DIVISOR  4U
#define PICOSYSTEM_GARDEN_CURSOR_REPEAT_DELAY_TICKS 10U
#define PICOSYSTEM_GARDEN_CURSOR_REPEAT_RATE_TICKS  4U
#define PICOSYSTEM_GARDEN_RAIN_VERSION              1U
#define PICOSYSTEM_GARDEN_RAIN_WINDOW_TICKS         128U
#define PICOSYSTEM_GARDEN_RAIN_MAX_RATE             4U

#if defined(TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE)
#if defined(__ZEPHYR__) || !defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
#error "Bottom drainage requires the explicit host maintenance experiment"
#endif
#define PICOSYSTEM_GARDEN_DRAINAGE_NAME   "bottom-drain-v1"
#define PICOSYSTEM_GARDEN_DRAINAGE_PERIOD 16U
#endif

#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
#if defined(__ZEPHYR__) || !defined(TOY_FACTORY_GARDEN_COMBINED_EXPERIMENT)
#error "Leaf maintenance requires the explicit combined host experiment"
#endif
#define PICOSYSTEM_GARDEN_LEAF_ENVIRONMENT  "leaf-maintenance-v1"
#define PICOSYSTEM_GARDEN_LEAF_RENEW_ENERGY 9U
#define PICOSYSTEM_GARDEN_LEAF_RENEW_WATER  5U

/* Derived diagnostics, not controller inputs or authoritative hash state. */
struct picosystem_garden_leaf_telemetry {
	uint32_t observations;
	uint32_t proposals;
	uint32_t renewals;
	uint32_t restored;
	uint32_t worn;
};
#endif

/* Host-only ecology experiment. Normal builds retain the device's scattering rule. */
#if defined(TOY_FACTORY_GARDEN_WIDE_DISPERSAL)
#if defined(__ZEPHYR__)
#error "Wide dispersal is an unqualified host experiment, not a firmware option"
#endif
#define PICOSYSTEM_GARDEN_DISPERSAL_MINIMUM 3
#define PICOSYSTEM_GARDEN_DISPERSAL_CHOICES 7U
#define PICOSYSTEM_GARDEN_DISPERSAL_NAME    "wide-v1"
#else
#define PICOSYSTEM_GARDEN_DISPERSAL_MINIMUM 5
#define PICOSYSTEM_GARDEN_DISPERSAL_CHOICES 3U
#define PICOSYSTEM_GARDEN_DISPERSAL_NAME    "narrow-v1"
#endif

#if defined(TOY_FACTORY_GARDEN_COMBINED_EXPERIMENT) &&                                             \
	(!defined(TOY_FACTORY_GARDEN_WIDE_DISPERSAL) ||                                            \
	 !defined(TOY_FACTORY_GARDEN_WATER_HEADROOM))
#error "Combined experiment requires both scattering and water headroom"
#endif

#if defined(TOY_FACTORY_GARDEN_WATER_HEADROOM)
#if defined(__ZEPHYR__)
#error "Water headroom is a host experiment, not a firmware option"
#endif
#if defined(TOY_FACTORY_GARDEN_WIDE_DISPERSAL) && !defined(TOY_FACTORY_GARDEN_COMBINED_EXPERIMENT)
#error "Combining ecology rules requires explicit experiment opt-in"
#endif
#define PICOSYSTEM_GARDEN_WATER_UPTAKE_NAME "headroom-v1"
#else
#define PICOSYSTEM_GARDEN_WATER_UPTAKE_NAME "legacy-v1"
#endif

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
	/* Spent for this Garden day; living flowers renew at dawn. */
	PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED = 1U << 5,
};

#define PICOSYSTEM_GARDEN_NODE_VALID_FLAGS                                                         \
	(PICOSYSTEM_GARDEN_NODE_TIP | PICOSYSTEM_GARDEN_NODE_LEAF |                                \
	 PICOSYSTEM_GARDEN_NODE_FLOWER | PICOSYSTEM_GARDEN_NODE_PRUNED |                           \
	 PICOSYSTEM_GARDEN_NODE_BRANCH_PENDING | PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED)

enum picosystem_garden_plant_flag {
	PICOSYSTEM_GARDEN_PLANT_DEAD = 1U << 0,
	PICOSYSTEM_GARDEN_PLANT_ENERGY_SHORTAGE = 1U << 1,
	PICOSYSTEM_GARDEN_PLANT_WATER_SHORTAGE = 1U << 2,
};

#define PICOSYSTEM_GARDEN_PLANT_VALID_FLAGS                                                        \
	(PICOSYSTEM_GARDEN_PLANT_DEAD | PICOSYSTEM_GARDEN_PLANT_ENERGY_SHORTAGE |                  \
	 PICOSYSTEM_GARDEN_PLANT_WATER_SHORTAGE)

enum picosystem_garden_seed_germination_blocker {
	PICOSYSTEM_GARDEN_SEED_BLOCKED_DORMANT = 1U << 0,
	PICOSYSTEM_GARDEN_SEED_BLOCKED_MOISTURE = 1U << 1,
	PICOSYSTEM_GARDEN_SEED_BLOCKED_LIGHT = 1U << 2,
	PICOSYSTEM_GARDEN_SEED_BLOCKED_PLANT_CAPACITY = 1U << 3,
	PICOSYSTEM_GARDEN_SEED_BLOCKED_NODE_CAPACITY = 1U << 4,
	PICOSYSTEM_GARDEN_SEED_BLOCKED_SPACING = 1U << 5,
};

#define PICOSYSTEM_GARDEN_SEED_VALID_BLOCKERS                                                      \
	(PICOSYSTEM_GARDEN_SEED_BLOCKED_DORMANT | PICOSYSTEM_GARDEN_SEED_BLOCKED_MOISTURE |        \
	 PICOSYSTEM_GARDEN_SEED_BLOCKED_LIGHT | PICOSYSTEM_GARDEN_SEED_BLOCKED_PLANT_CAPACITY |    \
	 PICOSYSTEM_GARDEN_SEED_BLOCKED_NODE_CAPACITY | PICOSYSTEM_GARDEN_SEED_BLOCKED_SPACING)

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

/* Compact heritable offsets around a flash-resident species template. */
struct picosystem_garden_genome {
	int8_t growth_rate;
	int8_t shoot_bias;
	int8_t light_seeking;
	int8_t water_seeking;
	int8_t branching;
	int8_t stature;
	int8_t reserve_strategy;
	int8_t dispersal;
};

/* Opaque lifetime memory owned by the authoritative world, never inherited. */
struct picosystem_garden_agent_memory {
	int8_t hidden[PICOSYSTEM_GARDEN_AGENT_MEMORY_WIDTH];
};

/* Derived policy diagnostics; deliberately excluded from the authoritative hash. */
struct picosystem_garden_agent_telemetry {
	uint32_t decision_count;
	uint32_t extend_count;
	uint32_t wait_count;
	uint32_t finish_count;
	uint32_t root_decision_count;
	uint32_t shoot_decision_count;
	uint32_t root_extend_count;
	uint32_t shoot_extend_count;
	int16_t last_priority;
	uint8_t last_tip_x;
	uint8_t last_tip_y;
	uint8_t last_tip_depth;
	uint8_t last_tissue_kind;
	uint8_t last_action;
	uint8_t reserved;
};

struct picosystem_garden_plant {
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	struct picosystem_garden_leaf_telemetry leaf_telemetry;
	uint8_t leaf_energy_remainder;
#endif
	uint32_t random_state;
	uint32_t lineage_id;
	uint32_t parent_lineage_id;
	/* Monotonic lifetime age; saturates only at UINT32_MAX. */
	uint32_t age_ecology_ticks;
	uint16_t base_node_index;
	uint16_t last_shoot_tip_index;
	uint16_t last_root_tip_index;
	uint16_t stored_energy;
	uint16_t stored_water;
	uint16_t node_count;
	uint16_t offspring_count;
	uint16_t generation;
	struct picosystem_garden_genome genome;
	struct picosystem_garden_agent_memory agent_memory;
	struct picosystem_garden_agent_telemetry agent_telemetry;
	uint8_t base_column;
	uint8_t growth_cooldown;
	uint8_t reproduction_cooldown;
	uint8_t growth_phase;
	uint8_t species_id;
	int8_t lean;
	int8_t vigor;
	uint8_t stress;
	uint8_t flags;
	uint8_t last_energy_income;
	uint8_t last_water_income;
};

struct picosystem_garden_agent_policy;

/* Dense fixed-capacity seed bank; entries wait for a viable germination window. */
struct picosystem_garden_seed {
	struct picosystem_garden_genome genome;
	uint32_t parent_lineage_id;
	uint16_t age_ecology_ticks;
	uint16_t generation;
	uint8_t column;
	uint8_t species_id;
	int8_t visual_offset;
};

/* Caller-owned read-only diagnostic; never retained in the authoritative world. */
struct picosystem_garden_seed_sites {
	/* All possible dispersal columns for each living parent, as a bit set. */
	uint32_t dispersal_columns[PICOSYSTEM_GARDEN_MAX_PLANTS];
	/* Site constraints for a hypothetical mature seed; excludes dormancy. */
	uint8_t blockers[PICOSYSTEM_GARDEN_GRID_COLUMNS];
};

/* Caller-owned fixed-capacity state; no garden operation allocates memory. */
struct picosystem_garden_world {
#if defined(TOY_FACTORY_GARDEN_FULL_POOL)
	struct picosystem_garden_full_pool_audit full_pool;
#endif
#if defined(TOY_FACTORY_GARDEN_PLANT_SLOTS)
	/* Host-only admission configuration, reset off and outside the physical hash. */
	bool plant_slots_sixteen;
#endif
#if defined(TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION)
	/* Host configuration: reset off, explicit metadata, outside the physical hash. */
	bool canopy_transmission_enabled;
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_SPACING)
	/* Host configuration only: reset off and reported separately from the hash. */
	bool seed_spacing_two;
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_ORDER)
	/* Host run configuration, like dawn_finish: reset off, separately reported,
	 * not part of the physical world hash or an agent observation.
	 */
	bool seed_order_rotating;
#endif
#if defined(TOY_FACTORY_GARDEN_DAWN_FINISH)
	struct picosystem_garden_dawn_finish dawn_finish;
#endif
#if defined(TOY_FACTORY_GARDEN_WET_GERMINATION)
	/* Authoritative opt-in state, disabled on reset; not a controller input. */
	bool wet_germination_enabled;
#endif
#if defined(TOY_FACTORY_GARDEN_NIGHT_CAPACITY)
	struct picosystem_garden_night_audit night_capacity;
#endif
#if defined(TOY_FACTORY_GARDEN_PURCHASE_VETO)
	struct picosystem_garden_purchase_veto purchase_veto;
#endif
#if defined(TOY_FACTORY_GARDEN_DARK_GUARD)
	struct picosystem_garden_dark_audit dark_guard;
#endif
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	uint8_t leaf_condition[PICOSYSTEM_GARDEN_MAX_NODES];
	struct picosystem_garden_leaf_telemetry leaf_telemetry;
#endif
	struct picosystem_garden_node nodes[PICOSYSTEM_GARDEN_MAX_NODES];
	struct picosystem_garden_plant plants[PICOSYSTEM_GARDEN_MAX_PLANTS];
	struct picosystem_garden_seed seeds[PICOSYSTEM_GARDEN_MAX_SEEDS];
	/* Aggregate telemetry survives individual plant reclamation. */
	struct picosystem_garden_agent_telemetry agent_telemetry;
	uint8_t moisture[PICOSYSTEM_GARDEN_SOIL_CELL_COUNT];
	uint8_t light[PICOSYSTEM_GARDEN_LIGHT_CELL_COUNT];
	uint32_t random_state;
	uint32_t logic_tick_count;
	uint32_t ecology_tick_count;
	/* Independent weather seed; zero disables rain without advancing plant RNGs. */
	uint32_t weather_seed;
	/* Derived, saturating counters, excluded from the authoritative hash. */
	uint32_t rain_deposited;
	uint32_t rain_runoff;
	uint32_t manual_action_count;
	uint32_t auto_decision_count;
	uint32_t auto_action_count;
	uint32_t bloom_count;
	uint32_t death_count;
	uint32_t reclaimed_plant_count;
	uint32_t reclaimed_node_count;
	uint32_t seed_creation_count;
	uint32_t germination_count;
	uint32_t seed_expiration_count;
	uint32_t mutation_count;
	uint32_t lineage_sequence;
	uint16_t node_count;
	uint16_t moisture_total;
	uint16_t maximum_generation;
	uint8_t plant_count;
	uint8_t seed_count;
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

#if defined(TOY_FACTORY_GARDEN_WET_GERMINATION)
/* Enable once at an ecology boundary with the gardener off. Change only the
 * germination light gate and hash identity; leave the world unchanged on error.
 */
int picosystem_garden_world_enable_wet_germination(struct picosystem_garden_world *world);
#endif

#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
/* Host-only environmental death, inclusive ground columns. Retain tissue for ordinary
 * decomposition; preserve soil, seeds and RNG. Invalid input leaves the world unchanged.
 */
int picosystem_garden_world_experimental_kill_patch(struct picosystem_garden_world *world,
						    uint8_t first_column, uint8_t last_column);
#endif

/* Query current sites using the same checks as germination and seed dispersal.
 * No seeds are placed and no RNG is consumed. Simultaneously open sites are
 * independent alternatives, not a promise they can all be occupied together.
 * Invalid arguments return -EINVAL and leave sites unchanged.
 */
int picosystem_garden_world_seed_sites(const struct picosystem_garden_world *world,
				       struct picosystem_garden_seed_sites *sites);

/* Append one seedling after validating spacing and fixed capacities. */
int picosystem_garden_world_plant_seed(struct picosystem_garden_world *world,
				       enum picosystem_garden_species_id species_id,
				       uint8_t column);

/* Deposit a bounded amount of water around one soil column. */
int picosystem_garden_world_water(struct picosystem_garden_world *world, uint8_t column,
				  uint8_t amount);

/* Pure surface-water units per column per ecology step; seed zero means dry. */
uint8_t picosystem_garden_rain_at(uint32_t weather_seed, uint32_t ecology_tick);

/* Change only the weather seed. Does not reset time, moisture, or diagnostics. */
int picosystem_garden_world_set_weather(struct picosystem_garden_world *world,
					uint32_t weather_seed);

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

/* Advance with a caller-owned pure policy; its context must be immutable. */
int picosystem_garden_world_step_with_policy(struct picosystem_garden_world *world,
					     const struct picosystem_garden_agent_policy *policy);

/* Apply cursor input and a caller-owned policy in one authoritative tick. */
int picosystem_garden_world_step_input_with_policy(
	struct picosystem_garden_world *world, int8_t horizontal, int8_t vertical,
	const struct picosystem_garden_agent_policy *policy);

const struct picosystem_garden_node *
picosystem_garden_world_node_at(const struct picosystem_garden_world *world, size_t index);

const struct picosystem_garden_plant *
picosystem_garden_world_plant_at(const struct picosystem_garden_world *world, size_t index);

const struct picosystem_garden_seed *
picosystem_garden_world_seed_at(const struct picosystem_garden_world *world, size_t index);

/* Report every current reason a seed cannot germinate without mutating the world. */
int picosystem_garden_world_seed_germination_blockers(const struct picosystem_garden_world *world,
						      size_t seed_index, uint8_t *blockers);

uint8_t picosystem_garden_world_living_plant_count(const struct picosystem_garden_world *world);
uint8_t picosystem_garden_world_dead_plant_count(const struct picosystem_garden_world *world);

/* Hash persistent and presentation-visible state without structure padding. */
uint32_t picosystem_garden_world_hash(const struct picosystem_garden_world *world);

#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
/* Host assay only: export one living plant and its stores, without natural death/reclamation
 * counters or soil/seed/RNG changes. Refresh light; preserve survivor state through compaction.
 * Invalid/missing targets leave the complete world unchanged. Not a gardener action.
 */
int picosystem_garden_world_experimental_clear(struct picosystem_garden_world *world,
					       uint32_t lineage_id);
#endif

const char *picosystem_garden_species_name(enum picosystem_garden_species_id species_id);
const char *picosystem_garden_tool_name(enum picosystem_garden_tool tool);

#endif /* PICOSYSTEM_GARDEN_WORLD_H_ */
