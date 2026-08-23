/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_GRANULAR_WORLD_H_
#define PICOSYSTEM_GRANULAR_WORLD_H_

#include <stddef.h>
#include <stdint.h>

#include "physics_world.h"

#define PICOSYSTEM_GRANULAR_MAX_PARTICLES        512U
#define PICOSYSTEM_GRANULAR_MAX_BOUNDARIES       8U
#define PICOSYSTEM_GRANULAR_SOLVER_ITERATIONS    2U
#define PICOSYSTEM_GRANULAR_GRID_CELL_PIXELS     4U
#define PICOSYSTEM_GRANULAR_GRID_ORIGIN_X_PIXELS 40U
#define PICOSYSTEM_GRANULAR_GRID_ORIGIN_Y_PIXELS 40U
#define PICOSYSTEM_GRANULAR_GRID_COLUMNS         40U
#define PICOSYSTEM_GRANULAR_GRID_ROWS            48U
#define PICOSYSTEM_GRANULAR_GRID_CELL_COUNT                                                        \
	(PICOSYSTEM_GRANULAR_GRID_COLUMNS * PICOSYSTEM_GRANULAR_GRID_ROWS)
#define PICOSYSTEM_GRANULAR_GRID_EMPTY UINT16_MAX
enum picosystem_granular_profile_stage {
	PICOSYSTEM_GRANULAR_PROFILE_INTEGRATE,
	PICOSYSTEM_GRANULAR_PROFILE_BOUNDARIES,
	PICOSYSTEM_GRANULAR_PROFILE_GRID_BUILD,
	PICOSYSTEM_GRANULAR_PROFILE_PAIR_SOLVE,
	PICOSYSTEM_GRANULAR_PROFILE_PASSAGES,
	PICOSYSTEM_GRANULAR_PROFILE_OTHER,
	PICOSYSTEM_GRANULAR_PROFILE_TOTAL,
	PICOSYSTEM_GRANULAR_PROFILE_STAGE_COUNT,
};

struct picosystem_granular_boundary_config {
	struct picosystem_physics_vector start;
	struct picosystem_physics_vector end;
	picosystem_physics_fixed_t active_minimum_y;
	picosystem_physics_fixed_t active_maximum_y;
	uint16_t id;
};

struct picosystem_granular_world_config {
	const struct picosystem_granular_boundary_config *boundaries;
	struct picosystem_physics_vector flip_center;
	picosystem_physics_fixed_t particle_radius;
	picosystem_physics_fixed_t maximum_speed_per_tick;
	picosystem_physics_fixed_t velocity_damping;
	picosystem_physics_fixed_t passage_deadband;
	picosystem_physics_fixed_t passage_y;
	uint16_t boundary_count;
};

struct picosystem_granular_particle {
	struct picosystem_physics_vector position;
	struct picosystem_physics_vector previous_position;
};

struct picosystem_granular_boundary {
	struct picosystem_physics_vector start;
	struct picosystem_physics_vector end;
	struct picosystem_physics_vector inward_normal;
	picosystem_physics_fixed_t coarse_negative_fraction_margin;
	picosystem_physics_fixed_t active_minimum_y;
	picosystem_physics_fixed_t active_maximum_y;
	uint16_t id;
};

/* Deterministic per-step work excluded from the authoritative hash. */
struct picosystem_granular_work_counters {
	uint32_t possible_pair_count;
	uint32_t candidate_pair_count;
	uint32_t axis_rejection_count;
	uint32_t diagonal_rejection_count;
	uint32_t distance_test_count;
	uint32_t contact_count;
	uint32_t position_correction_count;
	uint32_t boundary_test_count;
	uint32_t coarse_boundary_rejection_count;
	uint32_t boundary_contact_count;
	uint32_t occupied_grid_cell_count;
	uint32_t maximum_grid_cell_occupancy;
};

/* Optional elapsed-cycle sample for one step; timing never enters authoritative state. */
struct picosystem_granular_step_profile {
	uint32_t stage_cycles[PICOSYSTEM_GRANULAR_PROFILE_STAGE_COUNT];
	struct picosystem_granular_work_counters work;
	uint32_t clock_read_count;
};

/* Caller-owned fixed-capacity state. Grid links are scratch and rebuilt every pass. */
struct picosystem_granular_world {
	struct picosystem_granular_particle particles[PICOSYSTEM_GRANULAR_MAX_PARTICLES];
	struct picosystem_granular_boundary boundaries[PICOSYSTEM_GRANULAR_MAX_BOUNDARIES];
	uint32_t lower_particle_mask[PICOSYSTEM_GRANULAR_MAX_PARTICLES / 32U];
	struct picosystem_physics_vector flip_center;
	struct picosystem_physics_vector last_acceleration_per_tick;
	struct picosystem_granular_work_counters last_work;
	picosystem_physics_fixed_t particle_radius;
	picosystem_physics_fixed_t maximum_speed_per_tick;
	picosystem_physics_fixed_t velocity_damping;
	picosystem_physics_fixed_t passage_deadband;
	picosystem_physics_fixed_t passage_y;
	uint32_t passage_count;
	uint16_t particle_count;
	uint16_t boundary_count;
	uint16_t occupied_grid_cell_count;
	uint8_t grid_boundary_masks[PICOSYSTEM_GRANULAR_GRID_CELL_COUNT];
	uint16_t grid_heads[PICOSYSTEM_GRANULAR_GRID_CELL_COUNT];
	uint16_t grid_next[PICOSYSTEM_GRANULAR_MAX_PARTICLES];
	uint16_t occupied_grid_cells[PICOSYSTEM_GRANULAR_MAX_PARTICLES];
};

/* Initialize an empty world after validating the complete immutable configuration. */
int picosystem_granular_world_init(struct picosystem_granular_world *world,
				   const struct picosystem_granular_world_config *config);

/* Append one grain at rest; validation and capacity failures preserve the world. */
int picosystem_granular_world_add_particle(struct picosystem_granular_world *world,
					   const struct picosystem_physics_vector *position);

/* Advance exactly one fixed tick using bounded grid and solver work. */
int picosystem_granular_world_step(struct picosystem_granular_world *world,
				   const struct picosystem_physics_vector *acceleration_per_tick);

int picosystem_granular_world_step_profiled(
	struct picosystem_granular_world *world,
	const struct picosystem_physics_vector *acceleration_per_tick,
	const struct picosystem_physics_clock *clock,
	struct picosystem_granular_step_profile *profile);

/* Rotate all particle position and velocity state exactly 180 degrees about the configured center.
 */
int picosystem_granular_world_flip(struct picosystem_granular_world *world);

const struct picosystem_granular_particle *
picosystem_granular_world_particle_at(const struct picosystem_granular_world *world, size_t index);

uint16_t
picosystem_granular_world_lower_particle_count(const struct picosystem_granular_world *world);

/* Hash persistent configuration and particle state, excluding grid links and work counters. */
uint32_t picosystem_granular_world_hash(const struct picosystem_granular_world *world);

#if defined(PICOSYSTEM_GRANULAR_WORLD_TEST)
/* Test-only access to the conservative length used for bounded particle contacts. */
uint32_t picosystem_granular_test_particle_contact_length(uint32_t absolute_x, uint32_t absolute_y);
#endif

#endif /* PICOSYSTEM_GRANULAR_WORLD_H_ */
