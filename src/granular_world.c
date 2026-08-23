/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "granular_world.h"

#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define GRANULAR_HASH_VERSION              UINT32_C(1)
#define GRANULAR_MAX_RADIUS                PICOSYSTEM_PHYSICS_FIXED_FROM_INT(4)
#define GRANULAR_MAX_SPEED                 PICOSYSTEM_PHYSICS_FIXED_FROM_INT(8)
#define GRANULAR_MAX_ACCELERATION          PICOSYSTEM_PHYSICS_FIXED_FROM_INT(1)
#define GRANULAR_MAX_BOUNDARY_CORRECTION   PICOSYSTEM_PHYSICS_FIXED_FROM_INT(8)
#define GRANULAR_MAX_COORDINATE            PICOSYSTEM_PHYSICS_FIXED_FROM_INT(239)
#define GRANULAR_BOUNDARY_SLOP             PICOSYSTEM_PHYSICS_FIXED_RATIO(1, 8)
#define GRANULAR_PAIR_NORMAL_FRACTION_BITS 12U
#define GRANULAR_PAIR_NORMAL_SCALE         (INT32_C(1) << GRANULAR_PAIR_NORMAL_FRACTION_BITS)
#define GRANULAR_PAIR_NORMAL_TO_FIXED      (PICOSYSTEM_PHYSICS_FIXED_ONE / GRANULAR_PAIR_NORMAL_SCALE)
#define FNV1A_OFFSET_BASIS                 UINT32_C(2166136261)
#define FNV1A_PRIME                        UINT32_C(16777619)

static picosystem_physics_fixed_t fixed_multiply(picosystem_physics_fixed_t left,
						 picosystem_physics_fixed_t right)
{
	return (picosystem_physics_fixed_t)(((int64_t)left * right) / PICOSYSTEM_PHYSICS_FIXED_ONE);
}

static struct picosystem_physics_vector
vector_subtract(const struct picosystem_physics_vector *left,
		const struct picosystem_physics_vector *right)
{
	return (struct picosystem_physics_vector){
		.x = left->x - right->x,
		.y = left->y - right->y,
	};
}

static picosystem_physics_fixed_t vector_dot(const struct picosystem_physics_vector *left,
					     const struct picosystem_physics_vector *right)
{
	const int64_t raw = ((int64_t)left->x * right->x) + ((int64_t)left->y * right->y);
	return (picosystem_physics_fixed_t)(raw / PICOSYSTEM_PHYSICS_FIXED_ONE);
}

static uint64_t vector_length_squared_raw(const struct picosystem_physics_vector *vector)
{
	return (uint64_t)(((int64_t)vector->x * vector->x) + ((int64_t)vector->y * vector->y));
}

static uint32_t integer_square_root(uint64_t value)
{
	uint64_t result = 0U;
	uint64_t bit = UINT64_C(1) << 62U;

	while (bit > value) {
		bit >>= 2U;
	}
	while (bit != 0U) {
		if (value >= (result + bit)) {
			value -= result + bit;
			result = (result >> 1U) + bit;
		} else {
			result >>= 1U;
		}
		bit >>= 2U;
	}
	return (uint32_t)result;
}

static picosystem_physics_fixed_t normalize_vector(const struct picosystem_physics_vector *vector,
						   struct picosystem_physics_vector *normal,
						   const struct picosystem_physics_vector *fallback)
{
	const uint32_t length = integer_square_root(vector_length_squared_raw(vector));
	if (length == 0U) {
		*normal = *fallback;
		return 0;
	}
	normal->x =
		(picosystem_physics_fixed_t)(((int64_t)vector->x * PICOSYSTEM_PHYSICS_FIXED_ONE) /
					     length);
	normal->y =
		(picosystem_physics_fixed_t)(((int64_t)vector->y * PICOSYSTEM_PHYSICS_FIXED_ONE) /
					     length);
	return (picosystem_physics_fixed_t)length;
}

static picosystem_physics_fixed_t
normalize_particle_delta(const struct picosystem_physics_vector *delta,
			 const struct picosystem_physics_vector *fallback,
			 struct picosystem_physics_vector *normal)
{
	const uint32_t length = integer_square_root(vector_length_squared_raw(delta));
	if (length == 0U) {
		*normal = *fallback;
		return 0;
	}

	/* Contact deltas are strictly shorter than the maximum eight-pixel diameter,
	 * so scaling them to Q12 fits int32_t. Keeping this hot quotient 32-bit lets
	 * the RP2040 hardware divider replace two software 64-bit divisions per
	 * contact while retaining sub-pixel normal precision.
	 */
	const int32_t denominator = (int32_t)length;
	normal->x = ((delta->x * GRANULAR_PAIR_NORMAL_SCALE) / denominator) *
		    GRANULAR_PAIR_NORMAL_TO_FIXED;
	normal->y = ((delta->y * GRANULAR_PAIR_NORMAL_SCALE) / denominator) *
		    GRANULAR_PAIR_NORMAL_TO_FIXED;
	return (picosystem_physics_fixed_t)length;
}

static bool vector_within_limit(const struct picosystem_physics_vector *vector,
				picosystem_physics_fixed_t limit)
{
	return (vector->x >= -limit) && (vector->x <= limit) && (vector->y >= -limit) &&
	       (vector->y <= limit);
}

static bool vector_is_screen_coordinate(const struct picosystem_physics_vector *vector)
{
	return (vector->x >= 0) && (vector->x <= GRANULAR_MAX_COORDINATE) && (vector->y >= 0) &&
	       (vector->y <= GRANULAR_MAX_COORDINATE);
}

static bool world_configuration_is_valid(const struct picosystem_granular_world *world)
{
	return (world != NULL) && (world->particle_count <= PICOSYSTEM_GRANULAR_MAX_PARTICLES) &&
	       (world->boundary_count > 0U) &&
	       (world->boundary_count <= PICOSYSTEM_GRANULAR_MAX_BOUNDARIES) &&
	       (world->particle_radius > 0) && (world->particle_radius <= GRANULAR_MAX_RADIUS) &&
	       (world->maximum_speed_per_tick > 0) &&
	       (world->maximum_speed_per_tick <= GRANULAR_MAX_SPEED) &&
	       (world->velocity_damping >= 0) &&
	       (world->velocity_damping <= PICOSYSTEM_PHYSICS_FIXED_ONE) &&
	       (world->passage_deadband >= world->particle_radius);
}

static int validate_world_config(const struct picosystem_granular_world_config *config)
{
	if ((config == NULL) || (config->boundaries == NULL)) {
		return -EINVAL;
	}
	if ((config->boundary_count == 0U) ||
	    (config->boundary_count > PICOSYSTEM_GRANULAR_MAX_BOUNDARIES) ||
	    (config->particle_radius <= 0) || (config->particle_radius > GRANULAR_MAX_RADIUS) ||
	    (config->maximum_speed_per_tick <= 0) ||
	    (config->maximum_speed_per_tick > GRANULAR_MAX_SPEED) ||
	    (config->velocity_damping < 0) ||
	    (config->velocity_damping > PICOSYSTEM_PHYSICS_FIXED_ONE) ||
	    (config->passage_deadband < config->particle_radius) ||
	    !vector_is_screen_coordinate(&config->flip_center) || (config->passage_y < 0) ||
	    (config->passage_y > GRANULAR_MAX_COORDINATE)) {
		return -ERANGE;
	}
	for (uint16_t index = 0U; index < config->boundary_count; ++index) {
		const struct picosystem_granular_boundary_config *const boundary =
			&config->boundaries[index];
		if (!vector_is_screen_coordinate(&boundary->start) ||
		    !vector_is_screen_coordinate(&boundary->end) ||
		    (boundary->active_minimum_y < 0) ||
		    (boundary->active_maximum_y > GRANULAR_MAX_COORDINATE) ||
		    ((boundary->start.x == boundary->end.x) &&
		     (boundary->start.y == boundary->end.y)) ||
		    (boundary->active_minimum_y > boundary->active_maximum_y)) {
			return -ERANGE;
		}
		for (uint16_t prior = 0U; prior < index; ++prior) {
			if (config->boundaries[prior].id == boundary->id) {
				return -EEXIST;
			}
		}
	}
	return 0;
}

int picosystem_granular_world_init(struct picosystem_granular_world *world,
				   const struct picosystem_granular_world_config *config)
{
	if (world == NULL) {
		return -EINVAL;
	}
	const int err = validate_world_config(config);
	if (err != 0) {
		return err;
	}

	memset(world, 0, sizeof(*world));
	world->flip_center = config->flip_center;
	world->particle_radius = config->particle_radius;
	world->maximum_speed_per_tick = config->maximum_speed_per_tick;
	world->velocity_damping = config->velocity_damping;
	world->passage_deadband = config->passage_deadband;
	world->passage_y = config->passage_y;
	world->boundary_count = config->boundary_count;
	for (uint16_t index = 0U; index < config->boundary_count; ++index) {
		const struct picosystem_granular_boundary_config *const source =
			&config->boundaries[index];
		struct picosystem_granular_boundary *const destination = &world->boundaries[index];
		const struct picosystem_physics_vector extent =
			vector_subtract(&source->end, &source->start);
		const struct picosystem_physics_vector raw_normal = {
			.x = -extent.y,
			.y = extent.x,
		};
		const struct picosystem_physics_vector fallback = {
			.x = PICOSYSTEM_PHYSICS_FIXED_ONE,
		};
		(void)normalize_vector(&raw_normal, &destination->inward_normal, &fallback);
		destination->start = source->start;
		destination->end = source->end;
		destination->active_minimum_y = source->active_minimum_y;
		destination->active_maximum_y = source->active_maximum_y;
		destination->id = source->id;
	}
	memset(world->grid_heads, PICOSYSTEM_GRANULAR_GRID_EMPTY, sizeof(world->grid_heads));
	memset(world->grid_next, PICOSYSTEM_GRANULAR_GRID_EMPTY, sizeof(world->grid_next));
	return 0;
}

int picosystem_granular_world_add_particle(struct picosystem_granular_world *world,
					   const struct picosystem_physics_vector *position)
{
	if ((world == NULL) || (position == NULL)) {
		return -EINVAL;
	}
	if (!world_configuration_is_valid(world)) {
		return -ERANGE;
	}
	if (world->particle_count >= PICOSYSTEM_GRANULAR_MAX_PARTICLES) {
		return -ENOSPC;
	}
	if (!vector_is_screen_coordinate(position)) {
		return -ERANGE;
	}

	world->particles[world->particle_count] = (struct picosystem_granular_particle){
		.position = *position,
		.previous_position = *position,
	};
	if (position->y > (world->passage_y + world->passage_deadband)) {
		const uint16_t word = world->particle_count / 32U;
		const uint16_t bit = world->particle_count % 32U;
		world->lower_particle_mask[word] |= UINT32_C(1) << bit;
	}
	++world->particle_count;
	return 0;
}

static void clamp_velocity(struct picosystem_physics_vector *velocity,
			   picosystem_physics_fixed_t maximum_speed)
{
	const uint64_t maximum_squared = (uint64_t)((int64_t)maximum_speed * maximum_speed);
	const uint64_t length_squared = vector_length_squared_raw(velocity);
	if (length_squared <= maximum_squared) {
		return;
	}
	const uint32_t length = integer_square_root(length_squared);
	if (length == 0U) {
		*velocity = (struct picosystem_physics_vector){0};
		return;
	}
	velocity->x = (picosystem_physics_fixed_t)(((int64_t)velocity->x * maximum_speed) / length);
	velocity->y = (picosystem_physics_fixed_t)(((int64_t)velocity->y * maximum_speed) / length);
}

static void integrate_particles(struct picosystem_granular_world *world,
				const struct picosystem_physics_vector *acceleration)
{
	for (uint16_t index = 0U; index < world->particle_count; ++index) {
		struct picosystem_granular_particle *const particle = &world->particles[index];
		struct picosystem_physics_vector velocity =
			vector_subtract(&particle->position, &particle->previous_position);
		velocity.x = fixed_multiply(velocity.x, world->velocity_damping);
		velocity.y = fixed_multiply(velocity.y, world->velocity_damping);
		velocity.x += acceleration->x;
		velocity.y += acceleration->y;
		clamp_velocity(&velocity, world->maximum_speed_per_tick);
		particle->previous_position = particle->position;
		particle->position.x += velocity.x;
		particle->position.y += velocity.y;
	}
}

static void remove_outward_boundary_velocity(struct picosystem_granular_particle *particle,
					     const struct picosystem_physics_vector *normal)
{
	struct picosystem_physics_vector velocity =
		vector_subtract(&particle->position, &particle->previous_position);
	const picosystem_physics_fixed_t normal_velocity = vector_dot(&velocity, normal);
	if (normal_velocity < 0) {
		velocity.x -= fixed_multiply(normal->x, normal_velocity);
		velocity.y -= fixed_multiply(normal->y, normal_velocity);
		/* Boundary friction removes one quarter of the remaining tangent motion. */
		velocity.x = (velocity.x * 3) / 4;
		velocity.y = (velocity.y * 3) / 4;
	}
	particle->previous_position.x = particle->position.x - velocity.x;
	particle->previous_position.y = particle->position.y - velocity.y;
}

static void constrain_particles_to_boundaries(struct picosystem_granular_world *world,
					      uint16_t iteration_count)
{
	for (uint16_t iteration = 0U; iteration < iteration_count; ++iteration) {
		for (uint16_t particle_index = 0U; particle_index < world->particle_count;
		     ++particle_index) {
			struct picosystem_granular_particle *const particle =
				&world->particles[particle_index];
			for (uint16_t boundary_index = 0U; boundary_index < world->boundary_count;
			     ++boundary_index) {
				const struct picosystem_granular_boundary *const boundary =
					&world->boundaries[boundary_index];
				if ((particle->position.y < boundary->active_minimum_y) ||
				    (particle->position.y > boundary->active_maximum_y)) {
					continue;
				}
				++world->last_work.boundary_test_count;
				const struct picosystem_physics_vector from_start =
					vector_subtract(&particle->position, &boundary->start);
				const picosystem_physics_fixed_t signed_distance =
					vector_dot(&from_start, &boundary->inward_normal);
				if (signed_distance >= world->particle_radius) {
					continue;
				}

				picosystem_physics_fixed_t correction = world->particle_radius -
									signed_distance +
									GRANULAR_BOUNDARY_SLOP;
				if (correction > GRANULAR_MAX_BOUNDARY_CORRECTION) {
					correction = GRANULAR_MAX_BOUNDARY_CORRECTION;
				}
				const picosystem_physics_fixed_t correction_x =
					fixed_multiply(boundary->inward_normal.x, correction);
				const picosystem_physics_fixed_t correction_y =
					fixed_multiply(boundary->inward_normal.y, correction);
				/* Preserve pre-contact velocity while projecting back into the
				 * container.
				 */
				particle->position.x += correction_x;
				particle->position.y += correction_y;
				particle->previous_position.x += correction_x;
				particle->previous_position.y += correction_y;
				remove_outward_boundary_velocity(particle,
								 &boundary->inward_normal);
				++world->last_work.boundary_contact_count;
				++world->last_work.position_correction_count;
			}
		}
	}
}

static uint16_t particle_grid_cell(const struct picosystem_granular_particle *particle)
{
	int32_t pixel_x = particle->position.x / PICOSYSTEM_PHYSICS_FIXED_ONE;
	int32_t pixel_y = particle->position.y / PICOSYSTEM_PHYSICS_FIXED_ONE;
	pixel_x -= (int32_t)PICOSYSTEM_GRANULAR_GRID_ORIGIN_X_PIXELS;
	pixel_y -= (int32_t)PICOSYSTEM_GRANULAR_GRID_ORIGIN_Y_PIXELS;
	const int32_t maximum_grid_x =
		(PICOSYSTEM_GRANULAR_GRID_COLUMNS * PICOSYSTEM_GRANULAR_GRID_CELL_PIXELS) - 1U;
	const int32_t maximum_grid_y =
		(PICOSYSTEM_GRANULAR_GRID_ROWS * PICOSYSTEM_GRANULAR_GRID_CELL_PIXELS) - 1U;
	/* Folding outliers into edge cells preserves candidate completeness. */
	if (pixel_x < 0) {
		pixel_x = 0;
	} else if (pixel_x > maximum_grid_x) {
		pixel_x = maximum_grid_x;
	}
	if (pixel_y < 0) {
		pixel_y = 0;
	} else if (pixel_y > maximum_grid_y) {
		pixel_y = maximum_grid_y;
	}
	const uint16_t column = (uint16_t)pixel_x / PICOSYSTEM_GRANULAR_GRID_CELL_PIXELS;
	const uint16_t row = (uint16_t)pixel_y / PICOSYSTEM_GRANULAR_GRID_CELL_PIXELS;
	return (uint16_t)((row * PICOSYSTEM_GRANULAR_GRID_COLUMNS) + column);
}

static void build_grid(struct picosystem_granular_world *world)
{
	memset(world->grid_heads, PICOSYSTEM_GRANULAR_GRID_EMPTY, sizeof(world->grid_heads));
	memset(world->grid_next, PICOSYSTEM_GRANULAR_GRID_EMPTY, sizeof(world->grid_next));
	for (uint16_t index = 0U; index < world->particle_count; ++index) {
		const uint16_t cell = particle_grid_cell(&world->particles[index]);
		uint32_t occupancy = 1U;
		for (uint8_t other = world->grid_heads[cell];
		     other != PICOSYSTEM_GRANULAR_GRID_EMPTY; other = world->grid_next[other]) {
			++occupancy;
		}
		if (world->grid_heads[cell] == PICOSYSTEM_GRANULAR_GRID_EMPTY) {
			++world->last_work.occupied_grid_cell_count;
		}
		if (occupancy > world->last_work.maximum_grid_cell_occupancy) {
			world->last_work.maximum_grid_cell_occupancy = occupancy;
		}
		world->grid_next[index] = world->grid_heads[cell];
		world->grid_heads[cell] = (uint8_t)index;
	}
}

static struct picosystem_physics_vector pair_fallback_normal(uint16_t left, uint16_t right)
{
	const uint16_t choice = (uint16_t)((left * 31U + right) & 3U);
	switch (choice) {
	case 0U:
		return (struct picosystem_physics_vector){.x = PICOSYSTEM_PHYSICS_FIXED_ONE};
	case 1U:
		return (struct picosystem_physics_vector){.y = PICOSYSTEM_PHYSICS_FIXED_ONE};
	case 2U:
		return (struct picosystem_physics_vector){.x = -PICOSYSTEM_PHYSICS_FIXED_ONE};
	case 3U:
	default:
		return (struct picosystem_physics_vector){.y = -PICOSYSTEM_PHYSICS_FIXED_ONE};
	}
}

static void solve_particle_pair(struct picosystem_granular_world *world, uint16_t left_index,
				uint16_t right_index)
{
	++world->last_work.candidate_pair_count;
	struct picosystem_granular_particle *const left = &world->particles[left_index];
	struct picosystem_granular_particle *const right = &world->particles[right_index];
	const struct picosystem_physics_vector delta =
		vector_subtract(&right->position, &left->position);
	const picosystem_physics_fixed_t diameter = world->particle_radius * 2;
	const uint64_t diameter_squared = (uint64_t)((int64_t)diameter * diameter);
	if (vector_length_squared_raw(&delta) >= diameter_squared) {
		return;
	}

	struct picosystem_physics_vector normal;
	const struct picosystem_physics_vector fallback =
		pair_fallback_normal(left_index, right_index);
	const picosystem_physics_fixed_t distance =
		normalize_particle_delta(&delta, &fallback, &normal);
	const picosystem_physics_fixed_t correction = (diameter - distance + 1) / 2;
	const picosystem_physics_fixed_t correction_x = fixed_multiply(normal.x, correction);
	const picosystem_physics_fixed_t correction_y = fixed_multiply(normal.y, correction);
	left->position.x -= correction_x;
	left->position.y -= correction_y;
	right->position.x += correction_x;
	right->position.y += correction_y;
	++world->last_work.contact_count;
	++world->last_work.position_correction_count;
}

static void solve_grid_pairs(struct picosystem_granular_world *world, bool reverse)
{
	world->last_work.possible_pair_count +=
		((uint32_t)world->particle_count * (world->particle_count - 1U)) / 2U;
	for (uint16_t visit = 0U; visit < world->particle_count; ++visit) {
		const uint16_t particle_index =
			reverse ? (uint16_t)(world->particle_count - visit - 1U) : visit;
		const uint16_t cell = particle_grid_cell(&world->particles[particle_index]);
		const uint16_t center_row = cell / PICOSYSTEM_GRANULAR_GRID_COLUMNS;
		const uint16_t center_column = cell % PICOSYSTEM_GRANULAR_GRID_COLUMNS;
		const uint16_t minimum_row = (center_row == 0U) ? 0U : (uint16_t)(center_row - 1U);
		const uint16_t maximum_row = (center_row + 1U < PICOSYSTEM_GRANULAR_GRID_ROWS)
						     ? (uint16_t)(center_row + 1U)
						     : PICOSYSTEM_GRANULAR_GRID_ROWS - 1U;
		const uint16_t minimum_column =
			(center_column == 0U) ? 0U : (uint16_t)(center_column - 1U);
		const uint16_t maximum_column =
			(center_column + 1U < PICOSYSTEM_GRANULAR_GRID_COLUMNS)
				? (uint16_t)(center_column + 1U)
				: PICOSYSTEM_GRANULAR_GRID_COLUMNS - 1U;

		for (uint16_t row_visit = 0U; row_visit <= (maximum_row - minimum_row);
		     ++row_visit) {
			const uint16_t row =
				reverse ? maximum_row - row_visit : minimum_row + row_visit;
			for (uint16_t column_visit = 0U;
			     column_visit <= (maximum_column - minimum_column); ++column_visit) {
				const uint16_t column = reverse ? maximum_column - column_visit
								: minimum_column + column_visit;
				const uint16_t neighbor_cell =
					(uint16_t)((row * PICOSYSTEM_GRANULAR_GRID_COLUMNS) +
						   column);
				for (uint8_t other = world->grid_heads[neighbor_cell];
				     other != PICOSYSTEM_GRANULAR_GRID_EMPTY;
				     other = world->grid_next[other]) {
					const bool unique = reverse ? (other < particle_index)
								    : (other > particle_index);
					if (unique) {
						solve_particle_pair(world, particle_index, other);
					}
				}
			}
		}
	}
}

static bool particle_is_lower(const struct picosystem_granular_world *world, uint16_t index)
{
	const uint16_t word = index / 32U;
	const uint16_t bit = index % 32U;
	return (world->lower_particle_mask[word] & (UINT32_C(1) << bit)) != 0U;
}

static void set_particle_lower(struct picosystem_granular_world *world, uint16_t index, bool lower)
{
	const uint16_t word = index / 32U;
	const uint16_t bit = index % 32U;
	const uint32_t mask = UINT32_C(1) << bit;
	if (lower) {
		world->lower_particle_mask[word] |= mask;
	} else {
		world->lower_particle_mask[word] &= ~mask;
	}
}

static void update_passages(struct picosystem_granular_world *world)
{
	const picosystem_physics_fixed_t upper_threshold =
		world->passage_y - world->passage_deadband;
	const picosystem_physics_fixed_t lower_threshold =
		world->passage_y + world->passage_deadband;
	for (uint16_t index = 0U; index < world->particle_count; ++index) {
		const bool was_lower = particle_is_lower(world, index);
		bool is_lower = was_lower;
		if (world->particles[index].position.y < upper_threshold) {
			is_lower = false;
		} else if (world->particles[index].position.y > lower_threshold) {
			is_lower = true;
		}
		if (is_lower != was_lower) {
			set_particle_lower(world, index, is_lower);
			if (world->passage_count < UINT32_MAX) {
				++world->passage_count;
			}
		}
	}
}

int picosystem_granular_world_step(struct picosystem_granular_world *world,
				   const struct picosystem_physics_vector *acceleration_per_tick)
{
	if ((world == NULL) || (acceleration_per_tick == NULL)) {
		return -EINVAL;
	}
	if (!world_configuration_is_valid(world) ||
	    !vector_within_limit(acceleration_per_tick, GRANULAR_MAX_ACCELERATION)) {
		return -ERANGE;
	}

	world->last_work = (struct picosystem_granular_work_counters){0};
	world->last_acceleration_per_tick = *acceleration_per_tick;
	integrate_particles(world, acceleration_per_tick);
	constrain_particles_to_boundaries(world, 1U);
	for (uint16_t iteration = 0U; iteration < PICOSYSTEM_GRANULAR_SOLVER_ITERATIONS;
	     ++iteration) {
		build_grid(world);
		solve_grid_pairs(world, (iteration & 1U) != 0U);
		constrain_particles_to_boundaries(world, 1U);
	}
	/* The extra pass converges cap/slope corner contacts after the final pair solve. */
	constrain_particles_to_boundaries(world, 1U);
	update_passages(world);
	return 0;
}

int picosystem_granular_world_flip(struct picosystem_granular_world *world)
{
	if (!world_configuration_is_valid(world)) {
		return (world == NULL) ? -EINVAL : -ERANGE;
	}
	const int64_t doubled_center_x = (int64_t)world->flip_center.x * 2;
	const int64_t doubled_center_y = (int64_t)world->flip_center.y * 2;
	for (uint16_t index = 0U; index < world->particle_count; ++index) {
		struct picosystem_granular_particle *const particle = &world->particles[index];
		particle->position.x =
			(picosystem_physics_fixed_t)(doubled_center_x - particle->position.x);
		particle->position.y =
			(picosystem_physics_fixed_t)(doubled_center_y - particle->position.y);
		particle->previous_position.x =
			(picosystem_physics_fixed_t)(doubled_center_x -
						     particle->previous_position.x);
		particle->previous_position.y =
			(picosystem_physics_fixed_t)(doubled_center_y -
						     particle->previous_position.y);
		set_particle_lower(world, index, !particle_is_lower(world, index));
	}
	return 0;
}

const struct picosystem_granular_particle *
picosystem_granular_world_particle_at(const struct picosystem_granular_world *world, size_t index)
{
	if ((world == NULL) || (index >= world->particle_count) ||
	    (world->particle_count > PICOSYSTEM_GRANULAR_MAX_PARTICLES)) {
		return NULL;
	}
	return &world->particles[index];
}

uint16_t
picosystem_granular_world_lower_particle_count(const struct picosystem_granular_world *world)
{
	if ((world == NULL) || (world->particle_count > PICOSYSTEM_GRANULAR_MAX_PARTICLES)) {
		return 0U;
	}
	uint16_t count = 0U;
	for (uint16_t index = 0U; index < world->particle_count; ++index) {
		if (particle_is_lower(world, index)) {
			++count;
		}
	}
	return count;
}

static uint32_t fnv1a_u32(uint32_t hash, uint32_t value)
{
	for (uint32_t shift = 0U; shift < 32U; shift += 8U) {
		hash ^= (value >> shift) & UINT32_C(0xff);
		hash *= FNV1A_PRIME;
	}
	return hash;
}

uint32_t picosystem_granular_world_hash(const struct picosystem_granular_world *world)
{
	if (!world_configuration_is_valid(world)) {
		return 0U;
	}
	uint32_t hash = fnv1a_u32(FNV1A_OFFSET_BASIS, GRANULAR_HASH_VERSION);
	hash = fnv1a_u32(hash, world->particle_count);
	hash = fnv1a_u32(hash, world->boundary_count);
	hash = fnv1a_u32(hash, (uint32_t)world->particle_radius);
	hash = fnv1a_u32(hash, (uint32_t)world->maximum_speed_per_tick);
	hash = fnv1a_u32(hash, (uint32_t)world->velocity_damping);
	hash = fnv1a_u32(hash, (uint32_t)world->passage_y);
	hash = fnv1a_u32(hash, (uint32_t)world->passage_deadband);
	hash = fnv1a_u32(hash, (uint32_t)world->flip_center.x);
	hash = fnv1a_u32(hash, (uint32_t)world->flip_center.y);
	hash = fnv1a_u32(hash, (uint32_t)world->last_acceleration_per_tick.x);
	hash = fnv1a_u32(hash, (uint32_t)world->last_acceleration_per_tick.y);
	hash = fnv1a_u32(hash, world->passage_count);
	for (size_t word = 0U; word < (PICOSYSTEM_GRANULAR_MAX_PARTICLES / 32U); ++word) {
		hash = fnv1a_u32(hash, world->lower_particle_mask[word]);
	}
	for (uint16_t index = 0U; index < world->boundary_count; ++index) {
		const struct picosystem_granular_boundary *const boundary =
			&world->boundaries[index];
		hash = fnv1a_u32(hash, (uint32_t)boundary->start.x);
		hash = fnv1a_u32(hash, (uint32_t)boundary->start.y);
		hash = fnv1a_u32(hash, (uint32_t)boundary->end.x);
		hash = fnv1a_u32(hash, (uint32_t)boundary->end.y);
		hash = fnv1a_u32(hash, (uint32_t)boundary->active_minimum_y);
		hash = fnv1a_u32(hash, (uint32_t)boundary->active_maximum_y);
		hash = fnv1a_u32(hash, boundary->id);
	}
	for (uint16_t index = 0U; index < world->particle_count; ++index) {
		const struct picosystem_granular_particle *const particle =
			&world->particles[index];
		hash = fnv1a_u32(hash, (uint32_t)particle->position.x);
		hash = fnv1a_u32(hash, (uint32_t)particle->position.y);
		hash = fnv1a_u32(hash, (uint32_t)particle->previous_position.x);
		hash = fnv1a_u32(hash, (uint32_t)particle->previous_position.y);
	}
	return hash;
}
