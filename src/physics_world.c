/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "physics_world.h"

#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define PHYSICS_POSITION_LIMIT               PICOSYSTEM_PHYSICS_FIXED_FROM_INT(1024)
#define PHYSICS_VELOCITY_LIMIT               PICOSYSTEM_PHYSICS_FIXED_FROM_INT(8)
#define PHYSICS_ACCELERATION_LIMIT           PICOSYSTEM_PHYSICS_FIXED_ONE
#define PHYSICS_RADIUS_MINIMUM               PICOSYSTEM_PHYSICS_FIXED_ONE
#define PHYSICS_RADIUS_LIMIT                 PICOSYSTEM_PHYSICS_FIXED_FROM_INT(128)
#define PHYSICS_HALF_EXTENT_MINIMUM          PICOSYSTEM_PHYSICS_FIXED_ONE
#define PHYSICS_HALF_EXTENT_LIMIT            PICOSYSTEM_PHYSICS_FIXED_FROM_INT(64)
#define PHYSICS_JOINT_LOCAL_ANCHOR_LIMIT     PICOSYSTEM_PHYSICS_FIXED_FROM_INT(128)
#define PHYSICS_JOINT_DISTANCE_MINIMUM       PICOSYSTEM_PHYSICS_FIXED_ONE
#define PHYSICS_JOINT_DISTANCE_LIMIT         PICOSYSTEM_PHYSICS_FIXED_FROM_INT(256)
#define PHYSICS_INVERSE_MASS_MINIMUM         (PICOSYSTEM_PHYSICS_FIXED_ONE / 16)
#define PHYSICS_INVERSE_MASS_MAXIMUM         (PICOSYSTEM_PHYSICS_FIXED_ONE * 4)
#define PHYSICS_INVERSE_INERTIA_MAXIMUM      (PICOSYSTEM_PHYSICS_FIXED_ONE * 8)
#define PHYSICS_ANGULAR_VELOCITY_LIMIT       (PICOSYSTEM_PHYSICS_FIXED_ONE / 2)
#define PHYSICS_TAU_FIXED                    INT32_C(411775)
#define PHYSICS_PI_FIXED                     (PHYSICS_TAU_FIXED / 2)
#define PHYSICS_JOINT_MOTOR_IMPULSE_LIMIT    PICOSYSTEM_PHYSICS_FIXED_FROM_INT(8)
#define PHYSICS_JOINT_LIMIT_IMPULSE_LIMIT    PICOSYSTEM_PHYSICS_FIXED_FROM_INT(256)
#define PHYSICS_JOINT_ANGULAR_SLOP           (PHYSICS_TAU_FIXED / 360)
#define PHYSICS_JOINT_MAX_ANGULAR_CORRECTION (PHYSICS_TAU_FIXED / 24)
#define PHYSICS_POSITION_SLOP                (PICOSYSTEM_PHYSICS_FIXED_ONE / 256)
#define PHYSICS_JOINT_POSITION_SLOP          (PICOSYSTEM_PHYSICS_FIXED_ONE / 128)
#define PHYSICS_JOINT_CORRECTION_SCALE       (PICOSYSTEM_PHYSICS_FIXED_ONE / 2)
#define PHYSICS_JOINT_MAX_CORRECTION         PICOSYSTEM_PHYSICS_FIXED_FROM_INT(2)
#define PHYSICS_REVOLUTE_POSITION_TARGET     PICOSYSTEM_PHYSICS_FIXED_ONE
#define PHYSICS_BOUNCE_THRESHOLD             (PICOSYSTEM_PHYSICS_FIXED_ONE / 64)
#define PHYSICS_HASH_VERSION                 UINT32_C(7)
#define FNV1A_OFFSET_BASIS                   UINT32_C(2166136261)
#define FNV1A_PRIME                          UINT32_C(16777619)
#define STATIC_BODY_INDEX                    UINT8_MAX
#define STATIC_SEGMENT_INDEX                 UINT8_MAX
#define TRIG_QUARTER_SAMPLE_SHIFT            24U
#define TRIG_QUARTER_SAMPLE_COUNT            64U
#define TRIG_QUARTER_PHASE_MASK              UINT32_C(0x3fffffff)
#define PHYSICS_GRID_CELL_SIZE_FIXED                                                               \
	PICOSYSTEM_PHYSICS_FIXED_FROM_INT(PICOSYSTEM_PHYSICS_GRID_CELL_SIZE_PIXELS)
#define PHYSICS_GRID_WIDTH_FIXED                                                                   \
	PICOSYSTEM_PHYSICS_FIXED_FROM_INT(                                                         \
		PICOSYSTEM_PHYSICS_GRID_COLUMNS *PICOSYSTEM_PHYSICS_GRID_CELL_SIZE_PIXELS)
#define PHYSICS_GRID_HEIGHT_FIXED                                                                  \
	PICOSYSTEM_PHYSICS_FIXED_FROM_INT(                                                         \
		PICOSYSTEM_PHYSICS_GRID_ROWS *PICOSYSTEM_PHYSICS_GRID_CELL_SIZE_PIXELS)

_Static_assert(PICOSYSTEM_PHYSICS_MAX_BODIES <= UINT8_MAX, "body indices must fit in one byte");
_Static_assert(PICOSYSTEM_PHYSICS_MAX_BODIES <= 16U, "body occupancy must fit in uint16_t");
_Static_assert(PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS <= UINT8_MAX,
	       "segment indices must fit in one byte");
_Static_assert(PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS <= 8U,
	       "segment occupancy must fit in uint8_t");
_Static_assert(PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS <= UINT8_MAX,
	       "distance-joint indices must fit in one byte");
_Static_assert(PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS <= UINT8_MAX,
	       "revolute-joint indices must fit in one byte");
_Static_assert(PICOSYSTEM_PHYSICS_GRID_COLUMNS <= UINT8_MAX,
	       "grid columns must fit in a cell range");
_Static_assert(PICOSYSTEM_PHYSICS_GRID_ROWS <= UINT8_MAX, "grid rows must fit in a cell range");
_Static_assert(PICOSYSTEM_PHYSICS_GRID_CELL_COUNT <= UINT16_MAX,
	       "occupied grid-cell count must fit in uint16_t");
_Static_assert(PICOSYSTEM_PHYSICS_MAX_CONTACTS <= UINT16_MAX,
	       "contact count must fit in the public world field");
_Static_assert(PICOSYSTEM_PHYSICS_MAX_CONTACTS >= (PICOSYSTEM_PHYSICS_MAX_CANDIDATE_PAIRS *
						   PICOSYSTEM_PHYSICS_MAX_MANIFOLD_POINTS),
	       "contact storage must cover every brute-force manifold");
_Static_assert(PICOSYSTEM_PHYSICS_SOLVER_ITERATIONS <= UINT8_MAX,
	       "solver iteration diagnostics must fit in uint8_t");
_Static_assert(PICOSYSTEM_PHYSICS_REVOLUTE_POSITION_ITERATIONS <= UINT8_MAX,
	       "position iterations must fit in uint8_t");

struct box_geometry {
	struct picosystem_physics_vector axis_x;
	struct picosystem_physics_vector axis_y;
};

struct physics_aabb {
	picosystem_physics_fixed_t minimum_x;
	picosystem_physics_fixed_t minimum_y;
	picosystem_physics_fixed_t maximum_x;
	picosystem_physics_fixed_t maximum_y;
};

struct physics_grid_range {
	uint8_t minimum_column;
	uint8_t minimum_row;
	uint8_t maximum_column;
	uint8_t maximum_row;
};

struct physics_candidate_sets {
	uint16_t body_masks[PICOSYSTEM_PHYSICS_MAX_BODIES];
	uint8_t static_segment_masks[PICOSYSTEM_PHYSICS_MAX_BODIES];
};

struct contact_point_candidate {
	struct picosystem_physics_vector point;
	picosystem_physics_fixed_t penetration;
};

struct physics_step_profiler {
	const struct picosystem_physics_clock *clock;
	struct picosystem_physics_step_profile *profile;
	uint32_t total_start;
};

struct physics_symmetric_matrix {
	picosystem_physics_fixed_t xx;
	picosystem_physics_fixed_t xy;
	picosystem_physics_fixed_t yy;
};

enum revolute_limit_state {
	REVOLUTE_LIMIT_INACTIVE,
	REVOLUTE_LIMIT_LOWER,
	REVOLUTE_LIMIT_UPPER,
	REVOLUTE_LIMIT_EQUAL,
};

static bool profiler_is_active(const struct physics_step_profiler *profiler)
{
	return profiler->profile != NULL;
}

static uint32_t profiler_now(struct physics_step_profiler *profiler)
{
	++profiler->profile->clock_read_count;
	return profiler->clock->now(profiler->clock->context);
}

static uint32_t profiler_section_begin(struct physics_step_profiler *profiler)
{
	return profiler_is_active(profiler) ? profiler_now(profiler) : 0U;
}

static void profiler_section_end(struct physics_step_profiler *profiler,
				 enum picosystem_physics_profile_stage stage, uint32_t start)
{
	if (profiler_is_active(profiler)) {
		profiler->profile->stage_cycles[stage] += profiler_now(profiler) - start;
	}
}

static void profiler_finish(struct physics_step_profiler *profiler)
{
	if (!profiler_is_active(profiler)) {
		return;
	}

	const uint32_t total = profiler_now(profiler) - profiler->total_start;
	uint32_t attributed = 0U;
	for (enum picosystem_physics_profile_stage stage =
		     PICOSYSTEM_PHYSICS_PROFILE_FORCE_AND_INTEGRATE;
	     stage < PICOSYSTEM_PHYSICS_PROFILE_OTHER; ++stage) {
		attributed += profiler->profile->stage_cycles[stage];
	}
	profiler->profile->stage_cycles[PICOSYSTEM_PHYSICS_PROFILE_OTHER] =
		(total >= attributed) ? total - attributed : 0U;
	profiler->profile->stage_cycles[PICOSYSTEM_PHYSICS_PROFILE_TOTAL] = total;
}

static const picosystem_physics_fixed_t quarter_sine_samples[] = {
	0,     1608,  3216,  4821,  6424,  8022,  9616,  11204, 12785, 14359, 15924, 17479, 19024,
	20557, 22078, 23586, 25080, 26558, 28020, 29466, 30893, 32303, 33692, 35062, 36410, 37736,
	39040, 40320, 41576, 42806, 44011, 45190, 46341, 47464, 48559, 49624, 50660, 51665, 52639,
	53581, 54491, 55368, 56212, 57022, 57798, 58538, 59244, 59914, 60547, 61145, 61705, 62228,
	62714, 63162, 63572, 63944, 64277, 64571, 64827, 65043, 65220, 65358, 65457, 65516, 65536,
};

_Static_assert((sizeof(quarter_sine_samples) / sizeof(quarter_sine_samples[0])) ==
		       (TRIG_QUARTER_SAMPLE_COUNT + 1U),
	       "quarter-wave lookup table must include both endpoints");

static picosystem_physics_fixed_t fixed_minimum(picosystem_physics_fixed_t left,
						picosystem_physics_fixed_t right)
{
	return (left < right) ? left : right;
}

static picosystem_physics_fixed_t fixed_maximum(picosystem_physics_fixed_t left,
						picosystem_physics_fixed_t right)
{
	return (left > right) ? left : right;
}

static picosystem_physics_fixed_t fixed_absolute(picosystem_physics_fixed_t value)
{
	return (value < 0) ? -value : value;
}

static picosystem_physics_fixed_t fixed_clamp(picosystem_physics_fixed_t value,
					      picosystem_physics_fixed_t minimum,
					      picosystem_physics_fixed_t maximum)
{
	if (value < minimum) {
		return minimum;
	}
	if (value > maximum) {
		return maximum;
	}
	return value;
}

static picosystem_physics_fixed_t fixed_difference_bounded(picosystem_physics_fixed_t left,
							   picosystem_physics_fixed_t right,
							   picosystem_physics_fixed_t limit)
{
	const int64_t difference = (int64_t)left - right;
	if (difference < -(int64_t)limit) {
		return -limit;
	}
	if (difference > limit) {
		return limit;
	}
	return (picosystem_physics_fixed_t)difference;
}

static picosystem_physics_fixed_t fixed_multiply(picosystem_physics_fixed_t left,
						 picosystem_physics_fixed_t right)
{
	return (picosystem_physics_fixed_t)(((int64_t)left * right) / PICOSYSTEM_PHYSICS_FIXED_ONE);
}

static picosystem_physics_fixed_t fixed_divide(picosystem_physics_fixed_t numerator,
					       picosystem_physics_fixed_t denominator)
{
	return (picosystem_physics_fixed_t)(((int64_t)numerator * PICOSYSTEM_PHYSICS_FIXED_ONE) /
					    denominator);
}

static struct picosystem_physics_vector vector_add(const struct picosystem_physics_vector *left,
						   const struct picosystem_physics_vector *right)
{
	return (struct picosystem_physics_vector){
		.x = left->x + right->x,
		.y = left->y + right->y,
	};
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

static struct picosystem_physics_vector
vector_negate(const struct picosystem_physics_vector *vector)
{
	return (struct picosystem_physics_vector){
		.x = -vector->x,
		.y = -vector->y,
	};
}

static struct picosystem_physics_vector vector_scale(const struct picosystem_physics_vector *vector,
						     picosystem_physics_fixed_t scale)
{
	return (struct picosystem_physics_vector){
		.x = fixed_multiply(vector->x, scale),
		.y = fixed_multiply(vector->y, scale),
	};
}

static picosystem_physics_fixed_t vector_dot(const struct picosystem_physics_vector *left,
					     const struct picosystem_physics_vector *right)
{
	const int64_t raw = ((int64_t)left->x * right->x) + ((int64_t)left->y * right->y);
	return (picosystem_physics_fixed_t)(raw / PICOSYSTEM_PHYSICS_FIXED_ONE);
}

static picosystem_physics_fixed_t vector_cross(const struct picosystem_physics_vector *left,
					       const struct picosystem_physics_vector *right)
{
	const int64_t raw = ((int64_t)left->x * right->y) - ((int64_t)left->y * right->x);
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

static uint32_t integer_square_root_ceiling(uint64_t value)
{
	uint32_t result = integer_square_root(value);
	if (((uint64_t)result * result) < value) {
		++result;
	}
	return result;
}

static picosystem_physics_fixed_t
normalize_vector(const struct picosystem_physics_vector *vector,
		 struct picosystem_physics_vector *normal,
		 const struct picosystem_physics_vector *zero_fallback)
{
	const uint32_t length = integer_square_root(vector_length_squared_raw(vector));
	if (length == 0U) {
		*normal = *zero_fallback;
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

static void segment_normal_from_endpoints(const struct picosystem_physics_vector *start,
					  const struct picosystem_physics_vector *end,
					  struct picosystem_physics_vector *normal)
{
	const struct picosystem_physics_vector extent = vector_subtract(end, start);
	const struct picosystem_physics_vector raw_normal = {
		.x = -extent.y,
		.y = extent.x,
	};
	const struct picosystem_physics_vector unit_x = {
		.x = PICOSYSTEM_PHYSICS_FIXED_ONE,
	};
	(void)normalize_vector(&raw_normal, normal, &unit_x);
}

static picosystem_physics_fixed_t quarter_sine(uint32_t phase)
{
	if (phase >= PICOSYSTEM_PHYSICS_ANGLE_QUARTER_TURN) {
		return quarter_sine_samples[TRIG_QUARTER_SAMPLE_COUNT];
	}

	const uint32_t index = phase >> TRIG_QUARTER_SAMPLE_SHIFT;
	const uint32_t remainder = phase & ((UINT32_C(1) << TRIG_QUARTER_SAMPLE_SHIFT) - 1U);
	const picosystem_physics_fixed_t start = quarter_sine_samples[index];
	const picosystem_physics_fixed_t difference = quarter_sine_samples[index + 1U] - start;
	return start + (picosystem_physics_fixed_t)(((int64_t)difference * remainder) /
						    (UINT32_C(1) << TRIG_QUARTER_SAMPLE_SHIFT));
}

static picosystem_physics_fixed_t fixed_sine(uint32_t angle_turns)
{
	const uint32_t quadrant = angle_turns >> 30U;
	const uint32_t phase = angle_turns & TRIG_QUARTER_PHASE_MASK;

	switch (quadrant) {
	case 0U:
		return quarter_sine(phase);
	case 1U:
		return quarter_sine(PICOSYSTEM_PHYSICS_ANGLE_QUARTER_TURN - phase);
	case 2U:
		return -quarter_sine(phase);
	case 3U:
	default:
		return -quarter_sine(PICOSYSTEM_PHYSICS_ANGLE_QUARTER_TURN - phase);
	}
}

static picosystem_physics_fixed_t fixed_cosine(uint32_t angle_turns)
{
	return fixed_sine(angle_turns + PICOSYSTEM_PHYSICS_ANGLE_QUARTER_TURN);
}

static void box_geometry_from_body(const struct picosystem_physics_body *body,
				   struct box_geometry *geometry)
{
	geometry->axis_x = (struct picosystem_physics_vector){
		.x = fixed_cosine(body->angle_turns),
		.y = fixed_sine(body->angle_turns),
	};
	geometry->axis_y = (struct picosystem_physics_vector){
		.x = -geometry->axis_x.y,
		.y = geometry->axis_x.x,
	};
}

static struct picosystem_physics_vector
body_local_point_to_world(const struct picosystem_physics_body *body,
			  const struct picosystem_physics_vector *local_point)
{
	struct box_geometry geometry;
	box_geometry_from_body(body, &geometry);
	const struct picosystem_physics_vector along_x =
		vector_scale(&geometry.axis_x, local_point->x);
	const struct picosystem_physics_vector along_y =
		vector_scale(&geometry.axis_y, local_point->y);
	const struct picosystem_physics_vector offset = vector_add(&along_x, &along_y);
	return vector_add(&body->center, &offset);
}

static void box_vertices_from_geometry(
	const struct picosystem_physics_body *body, const struct box_geometry *geometry,
	struct picosystem_physics_vector vertices[PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT])
{
	const struct picosystem_physics_vector x =
		vector_scale(&geometry->axis_x, body->half_extent.x);
	const struct picosystem_physics_vector y =
		vector_scale(&geometry->axis_y, body->half_extent.y);
	const struct picosystem_physics_vector center_minus_x = vector_subtract(&body->center, &x);
	const struct picosystem_physics_vector center_plus_x = vector_add(&body->center, &x);

	vertices[0] = vector_subtract(&center_minus_x, &y);
	vertices[1] = vector_subtract(&center_plus_x, &y);
	vertices[2] = vector_add(&center_plus_x, &y);
	vertices[3] = vector_add(&center_minus_x, &y);
}

static bool fixed_is_bounded(picosystem_physics_fixed_t value, picosystem_physics_fixed_t limit)
{
	return (value >= -limit) && (value <= limit);
}

static bool material_is_valid(picosystem_physics_fixed_t coefficient)
{
	return (coefficient >= 0) && (coefficient <= PICOSYSTEM_PHYSICS_FIXED_ONE);
}

static bool vector_is_bounded(const struct picosystem_physics_vector *vector,
			      picosystem_physics_fixed_t limit)
{
	return fixed_is_bounded(vector->x, limit) && fixed_is_bounded(vector->y, limit);
}

static bool speed_is_bounded(const struct picosystem_physics_vector *velocity,
			     picosystem_physics_fixed_t maximum)
{
	const uint64_t speed_squared = vector_length_squared_raw(velocity);
	const uint64_t maximum_squared = (uint64_t)((int64_t)maximum * maximum);
	return speed_squared <= maximum_squared;
}

static bool common_body_config_is_valid(const struct picosystem_physics_vector *center,
					const struct picosystem_physics_vector *velocity_per_tick,
					picosystem_physics_fixed_t inverse_mass,
					picosystem_physics_fixed_t restitution,
					picosystem_physics_fixed_t friction,
					picosystem_physics_fixed_t angular_velocity_per_tick,
					uint16_t id, const struct picosystem_physics_world *world)
{
	return (id != 0U) && vector_is_bounded(center, PHYSICS_POSITION_LIMIT) &&
	       vector_is_bounded(velocity_per_tick, PHYSICS_VELOCITY_LIMIT) &&
	       speed_is_bounded(velocity_per_tick, world->max_speed_per_tick) &&
	       (inverse_mass >= PHYSICS_INVERSE_MASS_MINIMUM) &&
	       (inverse_mass <= PHYSICS_INVERSE_MASS_MAXIMUM) && material_is_valid(restitution) &&
	       material_is_valid(friction) &&
	       fixed_is_bounded(angular_velocity_per_tick, PHYSICS_ANGULAR_VELOCITY_LIMIT);
}

static bool circle_config_is_valid(const struct picosystem_physics_circle_config *config,
				   const struct picosystem_physics_world *world)
{
	return (config != NULL) &&
	       common_body_config_is_valid(&config->center, &config->velocity_per_tick,
					   config->inverse_mass, config->restitution,
					   config->friction, config->angular_velocity_per_tick,
					   config->id, world) &&
	       (config->radius >= PHYSICS_RADIUS_MINIMUM) &&
	       (config->radius <= PHYSICS_RADIUS_LIMIT);
}

static bool box_config_is_valid(const struct picosystem_physics_box_config *config,
				const struct picosystem_physics_world *world)
{
	return (config != NULL) &&
	       common_body_config_is_valid(&config->center, &config->velocity_per_tick,
					   config->inverse_mass, config->restitution,
					   config->friction, config->angular_velocity_per_tick,
					   config->id, world) &&
	       (config->half_extent.x >= PHYSICS_HALF_EXTENT_MINIMUM) &&
	       (config->half_extent.x <= PHYSICS_HALF_EXTENT_LIMIT) &&
	       (config->half_extent.y >= PHYSICS_HALF_EXTENT_MINIMUM) &&
	       (config->half_extent.y <= PHYSICS_HALF_EXTENT_LIMIT);
}

static bool segment_config_is_valid(const struct picosystem_physics_segment_config *config)
{
	if ((config == NULL) || (config->id == 0U) ||
	    !vector_is_bounded(&config->start, PHYSICS_POSITION_LIMIT) ||
	    !vector_is_bounded(&config->end, PHYSICS_POSITION_LIMIT) ||
	    !material_is_valid(config->restitution) || !material_is_valid(config->friction)) {
		return false;
	}

	const struct picosystem_physics_vector extent =
		vector_subtract(&config->end, &config->start);
	const uint64_t minimum_length_squared =
		(uint64_t)PICOSYSTEM_PHYSICS_FIXED_ONE * PICOSYSTEM_PHYSICS_FIXED_ONE;
	return vector_length_squared_raw(&extent) >= minimum_length_squared;
}

static bool
distance_joint_config_is_valid(const struct picosystem_physics_distance_joint_config *config)
{
	if ((config == NULL) || (config->id == 0U) ||
	    (config->body_a_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID) ||
	    ((config->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) &&
	     (config->body_a_id == config->body_b_id)) ||
	    !vector_is_bounded(&config->local_anchor_a, PHYSICS_JOINT_LOCAL_ANCHOR_LIMIT) ||
	    (config->target_distance < PHYSICS_JOINT_DISTANCE_MINIMUM) ||
	    (config->target_distance > PHYSICS_JOINT_DISTANCE_LIMIT)) {
		return false;
	}

	const picosystem_physics_fixed_t anchor_b_limit =
		(config->body_b_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID)
			? PHYSICS_POSITION_LIMIT
			: PHYSICS_JOINT_LOCAL_ANCHOR_LIMIT;
	return vector_is_bounded(&config->anchor_b, anchor_b_limit);
}

static bool
revolute_joint_config_is_valid(const struct picosystem_physics_revolute_joint_config *config)
{
	if ((config == NULL) || (config->id == 0U) ||
	    (config->body_a_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID) ||
	    ((config->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) &&
	     (config->body_a_id == config->body_b_id)) ||
	    (config->collide_connected > 1U) || (config->motor_enabled > 1U) ||
	    (config->limit_enabled > 1U) ||
	    !vector_is_bounded(&config->local_anchor_a, PHYSICS_JOINT_LOCAL_ANCHOR_LIMIT)) {
		return false;
	}
	if (config->motor_enabled != 0U) {
		if (!fixed_is_bounded(config->motor_speed_per_tick,
				      PHYSICS_ANGULAR_VELOCITY_LIMIT) ||
		    (config->maximum_motor_impulse_per_tick <= 0) ||
		    (config->maximum_motor_impulse_per_tick > PHYSICS_JOINT_MOTOR_IMPULSE_LIMIT)) {
			return false;
		}
	} else if ((config->motor_speed_per_tick != 0) ||
		   (config->maximum_motor_impulse_per_tick != 0)) {
		return false;
	}
	if (config->limit_enabled != 0U) {
		if (!fixed_is_bounded(config->lower_angle_radians, PHYSICS_PI_FIXED) ||
		    !fixed_is_bounded(config->upper_angle_radians, PHYSICS_PI_FIXED) ||
		    (config->lower_angle_radians > config->upper_angle_radians) ||
		    ((config->lower_angle_radians != config->upper_angle_radians) &&
		     ((config->upper_angle_radians - config->lower_angle_radians) <
		      (2 * PHYSICS_JOINT_ANGULAR_SLOP)))) {
			return false;
		}
	} else if ((config->lower_angle_radians != 0) || (config->upper_angle_radians != 0)) {
		return false;
	}

	const picosystem_physics_fixed_t anchor_b_limit =
		(config->body_b_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID)
			? PHYSICS_POSITION_LIMIT
			: PHYSICS_JOINT_LOCAL_ANCHOR_LIMIT;
	return vector_is_bounded(&config->anchor_b, anchor_b_limit);
}

static int body_index_for_id(const struct picosystem_physics_world *world, uint16_t id)
{
	for (uint16_t index = 0U; index < world->body_count; ++index) {
		if (world->bodies[index].id == id) {
			return index;
		}
	}
	return -ENOENT;
}

static picosystem_physics_fixed_t circle_inverse_inertia(picosystem_physics_fixed_t radius,
							 picosystem_physics_fixed_t inverse_mass)
{
	const picosystem_physics_fixed_t radius_squared = fixed_multiply(radius, radius);
	const picosystem_physics_fixed_t inverse_inertia =
		fixed_divide(inverse_mass * 2, radius_squared);
	return fixed_maximum(inverse_inertia, 1);
}

static picosystem_physics_fixed_t
box_inverse_inertia(const struct picosystem_physics_vector *half_extent,
		    picosystem_physics_fixed_t inverse_mass)
{
	const picosystem_physics_fixed_t squared_extent =
		fixed_multiply(half_extent->x, half_extent->x) +
		fixed_multiply(half_extent->y, half_extent->y);
	const picosystem_physics_fixed_t inverse_inertia =
		fixed_divide(inverse_mass * 3, squared_extent);
	return fixed_maximum(inverse_inertia, 1);
}

static bool body_is_valid(const struct picosystem_physics_body *body,
			  const struct picosystem_physics_world *world)
{
	const bool inertia_is_valid = (body->inverse_inertia > 0) &&
				      (body->inverse_inertia <= PHYSICS_INVERSE_INERTIA_MAXIMUM);
	if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_CIRCLE) {
		const struct picosystem_physics_circle_config config = {
			.center = body->center,
			.velocity_per_tick = body->velocity_per_tick,
			.radius = body->radius,
			.inverse_mass = body->inverse_mass,
			.restitution = body->restitution,
			.friction = body->friction,
			.angular_velocity_per_tick = body->angular_velocity_per_tick,
			.angle_turns = body->angle_turns,
			.id = body->id,
		};
		return circle_config_is_valid(&config, world) && (body->half_extent.x == 0) &&
		       (body->half_extent.y == 0) && inertia_is_valid;
	}

	if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_BOX) {
		const struct picosystem_physics_box_config config = {
			.center = body->center,
			.velocity_per_tick = body->velocity_per_tick,
			.half_extent = body->half_extent,
			.inverse_mass = body->inverse_mass,
			.restitution = body->restitution,
			.friction = body->friction,
			.angular_velocity_per_tick = body->angular_velocity_per_tick,
			.angle_turns = body->angle_turns,
			.id = body->id,
		};
		return box_config_is_valid(&config, world) && (body->radius == 0) &&
		       inertia_is_valid;
	}

	return false;
}

static bool segment_is_valid(const struct picosystem_physics_static_segment *segment)
{
	const struct picosystem_physics_segment_config config = {
		.start = segment->start,
		.end = segment->end,
		.restitution = segment->restitution,
		.friction = segment->friction,
		.id = segment->id,
	};
	if (!segment_config_is_valid(&config)) {
		return false;
	}

	const struct picosystem_physics_vector extent =
		vector_subtract(&segment->end, &segment->start);
	const struct picosystem_physics_vector raw_normal = {
		.x = -extent.y,
		.y = extent.x,
	};
	const uint64_t normal_length_squared = vector_length_squared_raw(&segment->normal);
	const uint64_t minimum_length = PICOSYSTEM_PHYSICS_FIXED_ONE - 2;
	const uint64_t minimum_length_squared = minimum_length * minimum_length;
	const uint64_t maximum_length_squared =
		(uint64_t)PICOSYSTEM_PHYSICS_FIXED_ONE * PICOSYSTEM_PHYSICS_FIXED_ONE;
	return (normal_length_squared >= minimum_length_squared) &&
	       (normal_length_squared <= maximum_length_squared) &&
	       (vector_dot(&raw_normal, &segment->normal) > 0) &&
	       (fixed_absolute(vector_cross(&raw_normal, &segment->normal)) <=
		(PICOSYSTEM_PHYSICS_FIXED_ONE / 16));
}

static bool body_local_anchor_is_valid(const struct picosystem_physics_body *body,
				       const struct picosystem_physics_vector *anchor)
{
	if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_CIRCLE) {
		return vector_length_squared_raw(anchor) <=
		       (uint64_t)((int64_t)body->radius * body->radius);
	}
	if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_BOX) {
		return (fixed_absolute(anchor->x) <= body->half_extent.x) &&
		       (fixed_absolute(anchor->y) <= body->half_extent.y);
	}
	return false;
}

static bool distance_joint_is_valid(const struct picosystem_physics_distance_joint *joint,
				    const struct picosystem_physics_world *world)
{
	const struct picosystem_physics_distance_joint_config config = {
		.local_anchor_a = joint->local_anchor_a,
		.anchor_b = joint->anchor_b,
		.target_distance = joint->target_distance,
		.id = joint->id,
		.body_a_id = joint->body_a_id,
		.body_b_id = joint->body_b_id,
	};
	if (!distance_joint_config_is_valid(&config) ||
	    (joint->body_a_index >= world->body_count) ||
	    (world->bodies[joint->body_a_index].id != joint->body_a_id) ||
	    !body_local_anchor_is_valid(&world->bodies[joint->body_a_index],
					&joint->local_anchor_a)) {
		return false;
	}

	if (joint->body_b_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		return joint->body_b_index == STATIC_BODY_INDEX;
	}
	return (joint->body_b_index < world->body_count) &&
	       (world->bodies[joint->body_b_index].id == joint->body_b_id) &&
	       body_local_anchor_is_valid(&world->bodies[joint->body_b_index], &joint->anchor_b);
}

static bool revolute_joint_is_valid(const struct picosystem_physics_revolute_joint *joint,
				    const struct picosystem_physics_world *world)
{
	const struct picosystem_physics_revolute_joint_config config = {
		.local_anchor_a = joint->local_anchor_a,
		.anchor_b = joint->anchor_b,
		.motor_speed_per_tick = joint->motor_speed_per_tick,
		.maximum_motor_impulse_per_tick = joint->maximum_motor_impulse_per_tick,
		.lower_angle_radians = joint->lower_angle_radians,
		.upper_angle_radians = joint->upper_angle_radians,
		.id = joint->id,
		.body_a_id = joint->body_a_id,
		.body_b_id = joint->body_b_id,
		.collide_connected = joint->collide_connected,
		.motor_enabled = joint->motor_enabled,
		.limit_enabled = joint->limit_enabled,
	};
	if (!revolute_joint_config_is_valid(&config) ||
	    (joint->body_a_index >= world->body_count) ||
	    (world->bodies[joint->body_a_index].id != joint->body_a_id) ||
	    !body_local_anchor_is_valid(&world->bodies[joint->body_a_index],
					&joint->local_anchor_a)) {
		return false;
	}

	if (joint->body_b_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		return joint->body_b_index == STATIC_BODY_INDEX;
	}
	return (joint->body_b_index < world->body_count) &&
	       (world->bodies[joint->body_b_index].id == joint->body_b_id) &&
	       body_local_anchor_is_valid(&world->bodies[joint->body_b_index], &joint->anchor_b);
}

static bool world_is_valid(const struct picosystem_physics_world *world)
{
	if ((world == NULL) || (world->max_speed_per_tick <= 0) ||
	    (world->max_speed_per_tick > PHYSICS_VELOCITY_LIMIT) ||
	    (world->body_count > PICOSYSTEM_PHYSICS_MAX_BODIES) ||
	    (world->static_segment_count > PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS) ||
	    (world->distance_joint_count > PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS) ||
	    (world->revolute_joint_count > PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS) ||
	    (world->contact_count > PICOSYSTEM_PHYSICS_MAX_CONTACTS)) {
		return false;
	}

	for (uint16_t body_index = 0U; body_index < world->body_count; ++body_index) {
		if (!body_is_valid(&world->bodies[body_index], world)) {
			return false;
		}
		for (uint16_t prior = 0U; prior < body_index; ++prior) {
			if (world->bodies[prior].id == world->bodies[body_index].id) {
				return false;
			}
		}
	}

	for (uint16_t segment_index = 0U; segment_index < world->static_segment_count;
	     ++segment_index) {
		if (!segment_is_valid(&world->static_segments[segment_index])) {
			return false;
		}
		for (uint16_t prior = 0U; prior < segment_index; ++prior) {
			if (world->static_segments[prior].id ==
			    world->static_segments[segment_index].id) {
				return false;
			}
		}
	}

	for (uint16_t joint_index = 0U; joint_index < world->distance_joint_count; ++joint_index) {
		if (!distance_joint_is_valid(&world->distance_joints[joint_index], world)) {
			return false;
		}
		for (uint16_t prior = 0U; prior < joint_index; ++prior) {
			if (world->distance_joints[prior].id ==
			    world->distance_joints[joint_index].id) {
				return false;
			}
		}
	}

	for (uint16_t joint_index = 0U; joint_index < world->revolute_joint_count; ++joint_index) {
		if (!revolute_joint_is_valid(&world->revolute_joints[joint_index], world)) {
			return false;
		}
		for (uint16_t prior = 0U; prior < joint_index; ++prior) {
			if (world->revolute_joints[prior].id ==
			    world->revolute_joints[joint_index].id) {
				return false;
			}
		}
	}

	return true;
}

static void clamp_body_speed(struct picosystem_physics_body *body,
			     picosystem_physics_fixed_t maximum)
{
	const uint64_t speed_squared = vector_length_squared_raw(&body->velocity_per_tick);
	const uint64_t maximum_squared = (uint64_t)((int64_t)maximum * maximum);
	if (speed_squared <= maximum_squared) {
		return;
	}

	/* A floor root can scale to a vector a few raw units above the promised limit. */
	const uint32_t speed = integer_square_root_ceiling(speed_squared);
	body->velocity_per_tick.x =
		(picosystem_physics_fixed_t)(((int64_t)body->velocity_per_tick.x * maximum) /
					     speed);
	body->velocity_per_tick.y =
		(picosystem_physics_fixed_t)(((int64_t)body->velocity_per_tick.y * maximum) /
					     speed);
}

static void clamp_body_angular_speed(struct picosystem_physics_body *body)
{
	body->angular_velocity_per_tick =
		fixed_clamp(body->angular_velocity_per_tick, -PHYSICS_ANGULAR_VELOCITY_LIMIT,
			    PHYSICS_ANGULAR_VELOCITY_LIMIT);
}

static void clamp_body_position(struct picosystem_physics_body *body)
{
	body->center.x =
		fixed_clamp(body->center.x, -PHYSICS_POSITION_LIMIT, PHYSICS_POSITION_LIMIT);
	body->center.y =
		fixed_clamp(body->center.y, -PHYSICS_POSITION_LIMIT, PHYSICS_POSITION_LIMIT);
}

static void apply_body_angle_delta(struct picosystem_physics_body *body,
				   picosystem_physics_fixed_t angular_delta)
{
	const int64_t phase_delta =
		((int64_t)angular_delta * (INT64_C(1) << 32U)) / PHYSICS_TAU_FIXED;
	body->angle_turns += (uint32_t)phase_delta;
}

static void integrate_body_angle(struct picosystem_physics_body *body)
{
	apply_body_angle_delta(body, body->angular_velocity_per_tick);
}

static picosystem_physics_fixed_t angle_turn_delta_to_radians(uint32_t angle_turn_delta)
{
	const int64_t signed_delta = (angle_turn_delta <= INT32_MAX)
					     ? angle_turn_delta
					     : (int64_t)angle_turn_delta - (INT64_C(1) << 32U);
	return (picosystem_physics_fixed_t)((signed_delta * PHYSICS_TAU_FIXED) /
					    (INT64_C(1) << 32U));
}

static uint32_t
revolute_joint_relative_angle_turns(const struct picosystem_physics_world *world,
				    const struct picosystem_physics_revolute_joint *joint)
{
	const uint32_t body_a_angle = world->bodies[joint->body_a_index].angle_turns;
	const uint32_t body_b_angle = (joint->body_b_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID)
					      ? 0U
					      : world->bodies[joint->body_b_index].angle_turns;
	return body_a_angle - body_b_angle;
}

static picosystem_physics_fixed_t
revolute_joint_relative_angle_radians(const struct picosystem_physics_world *world,
				      const struct picosystem_physics_revolute_joint *joint)
{
	const uint32_t relative_turns = revolute_joint_relative_angle_turns(world, joint);
	return angle_turn_delta_to_radians(relative_turns - joint->reference_angle_turns);
}

static void distance_joint_endpoints(const struct picosystem_physics_world *world,
				     const struct picosystem_physics_distance_joint *joint,
				     struct picosystem_physics_vector *world_anchor_a,
				     struct picosystem_physics_vector *world_anchor_b)
{
	*world_anchor_a = body_local_point_to_world(&world->bodies[joint->body_a_index],
						    &joint->local_anchor_a);
	if (joint->body_b_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		*world_anchor_b = joint->anchor_b;
		return;
	}
	*world_anchor_b =
		body_local_point_to_world(&world->bodies[joint->body_b_index], &joint->anchor_b);
}

static void revolute_joint_anchors(const struct picosystem_physics_world *world,
				   const struct picosystem_physics_revolute_joint *joint,
				   struct picosystem_physics_vector *world_anchor_a,
				   struct picosystem_physics_vector *world_anchor_b)
{
	*world_anchor_a = body_local_point_to_world(&world->bodies[joint->body_a_index],
						    &joint->local_anchor_a);
	if (joint->body_b_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		*world_anchor_b = joint->anchor_b;
		return;
	}
	*world_anchor_b =
		body_local_point_to_world(&world->bodies[joint->body_b_index], &joint->anchor_b);
}

static struct picosystem_physics_vector
body_velocity_at_point(const struct picosystem_physics_body *body,
		       const struct picosystem_physics_vector *point)
{
	const struct picosystem_physics_vector lever = vector_subtract(point, &body->center);
	return (struct picosystem_physics_vector){
		.x = body->velocity_per_tick.x -
		     fixed_multiply(body->angular_velocity_per_tick, lever.y),
		.y = body->velocity_per_tick.y +
		     fixed_multiply(body->angular_velocity_per_tick, lever.x),
	};
}

static struct picosystem_physics_vector
contact_relative_velocity(const struct picosystem_physics_world *world,
			  const struct picosystem_physics_contact *contact)
{
	const struct picosystem_physics_vector velocity_a =
		body_velocity_at_point(&world->bodies[contact->body_a_index], &contact->point);
	if (contact->type == PICOSYSTEM_PHYSICS_CONTACT_STATIC_SEGMENT) {
		return vector_negate(&velocity_a);
	}

	const struct picosystem_physics_vector velocity_b =
		body_velocity_at_point(&world->bodies[contact->body_b_index], &contact->point);
	return vector_subtract(&velocity_b, &velocity_a);
}

static picosystem_physics_fixed_t
body_direction_inverse_mass(const struct picosystem_physics_body *body,
			    const struct picosystem_physics_vector *point,
			    const struct picosystem_physics_vector *direction)
{
	const struct picosystem_physics_vector lever = vector_subtract(point, &body->center);
	const picosystem_physics_fixed_t cross = vector_cross(&lever, direction);
	const picosystem_physics_fixed_t rotational =
		fixed_multiply(body->inverse_inertia, fixed_multiply(cross, cross));
	return body->inverse_mass + rotational;
}

static picosystem_physics_fixed_t
contact_direction_inverse_mass(const struct picosystem_physics_world *world,
			       const struct picosystem_physics_contact *contact,
			       const struct picosystem_physics_vector *direction)
{
	picosystem_physics_fixed_t sum = body_direction_inverse_mass(
		&world->bodies[contact->body_a_index], &contact->point, direction);
	if (contact->type == PICOSYSTEM_PHYSICS_CONTACT_BODY) {
		sum += body_direction_inverse_mass(&world->bodies[contact->body_b_index],
						   &contact->point, direction);
	}
	return sum;
}

static picosystem_physics_fixed_t
distance_joint_direction_inverse_mass(const struct picosystem_physics_world *world,
				      const struct picosystem_physics_distance_joint *joint,
				      const struct picosystem_physics_vector *world_anchor_a,
				      const struct picosystem_physics_vector *world_anchor_b,
				      const struct picosystem_physics_vector *direction)
{
	picosystem_physics_fixed_t sum = body_direction_inverse_mass(
		&world->bodies[joint->body_a_index], world_anchor_a, direction);
	if (joint->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		sum += body_direction_inverse_mass(&world->bodies[joint->body_b_index],
						   world_anchor_b, direction);
	}
	return sum;
}

static void add_body_point_inverse_mass(const struct picosystem_physics_body *body,
					const struct picosystem_physics_vector *point,
					struct physics_symmetric_matrix *matrix)
{
	const struct picosystem_physics_vector lever = vector_subtract(point, &body->center);
	const picosystem_physics_fixed_t inertia_x = fixed_multiply(body->inverse_inertia, lever.x);
	const picosystem_physics_fixed_t inertia_y = fixed_multiply(body->inverse_inertia, lever.y);
	matrix->xx += body->inverse_mass + fixed_multiply(inertia_y, lever.y);
	matrix->xy -= fixed_multiply(inertia_x, lever.y);
	matrix->yy += body->inverse_mass + fixed_multiply(inertia_x, lever.x);
}

static bool revolute_joint_effective_mass(const struct picosystem_physics_world *world,
					  const struct picosystem_physics_revolute_joint *joint,
					  const struct picosystem_physics_vector *world_anchor_a,
					  const struct picosystem_physics_vector *world_anchor_b,
					  struct physics_symmetric_matrix *effective_mass)
{
	struct physics_symmetric_matrix inverse_mass = {0};
	add_body_point_inverse_mass(&world->bodies[joint->body_a_index], world_anchor_a,
				    &inverse_mass);
	if (joint->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		add_body_point_inverse_mass(&world->bodies[joint->body_b_index], world_anchor_b,
					    &inverse_mass);
	}

	const picosystem_physics_fixed_t determinant =
		fixed_multiply(inverse_mass.xx, inverse_mass.yy) -
		fixed_multiply(inverse_mass.xy, inverse_mass.xy);
	if (determinant <= 0) {
		*effective_mass = (struct physics_symmetric_matrix){0};
		return false;
	}

	*effective_mass = (struct physics_symmetric_matrix){
		.xx = fixed_divide(inverse_mass.yy, determinant),
		.xy = fixed_divide(-inverse_mass.xy, determinant),
		.yy = fixed_divide(inverse_mass.xx, determinant),
	};
	return true;
}

static picosystem_physics_fixed_t
revolute_joint_angular_inverse_mass(const struct picosystem_physics_world *world,
				    const struct picosystem_physics_revolute_joint *joint)
{
	picosystem_physics_fixed_t inverse_mass =
		world->bodies[joint->body_a_index].inverse_inertia;
	if (joint->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		inverse_mass += world->bodies[joint->body_b_index].inverse_inertia;
	}
	return inverse_mass;
}

static picosystem_physics_fixed_t
revolute_joint_angular_effective_mass(const struct picosystem_physics_world *world,
				      const struct picosystem_physics_revolute_joint *joint)
{
	return fixed_divide(PICOSYSTEM_PHYSICS_FIXED_ONE,
			    revolute_joint_angular_inverse_mass(world, joint));
}

static struct picosystem_physics_vector
matrix_transform(const struct physics_symmetric_matrix *matrix,
		 const struct picosystem_physics_vector *vector)
{
	return (struct picosystem_physics_vector){
		.x = fixed_multiply(matrix->xx, vector->x) + fixed_multiply(matrix->xy, vector->y),
		.y = fixed_multiply(matrix->xy, vector->x) + fixed_multiply(matrix->yy, vector->y),
	};
}

static picosystem_physics_fixed_t
distance_joint_geometry(const struct picosystem_physics_world *world,
			const struct picosystem_physics_distance_joint *joint,
			struct picosystem_physics_vector *world_anchor_a,
			struct picosystem_physics_vector *world_anchor_b,
			struct picosystem_physics_vector *normal)
{
	distance_joint_endpoints(world, joint, world_anchor_a, world_anchor_b);
	const struct picosystem_physics_vector delta =
		vector_subtract(world_anchor_b, world_anchor_a);
	const struct picosystem_physics_vector fallback = {
		.x = ((joint->id & 1U) == 0U) ? PICOSYSTEM_PHYSICS_FIXED_ONE
					      : -PICOSYSTEM_PHYSICS_FIXED_ONE,
	};
	return normalize_vector(&delta, normal, &fallback);
}

static picosystem_physics_fixed_t
contact_linear_inverse_mass(const struct picosystem_physics_world *world,
			    const struct picosystem_physics_contact *contact)
{
	picosystem_physics_fixed_t sum = world->bodies[contact->body_a_index].inverse_mass;
	if (contact->type == PICOSYSTEM_PHYSICS_CONTACT_BODY) {
		sum += world->bodies[contact->body_b_index].inverse_mass;
	}
	return sum;
}

static picosystem_physics_fixed_t contact_friction(const struct picosystem_physics_world *world,
						   const struct picosystem_physics_contact *contact)
{
	const picosystem_physics_fixed_t friction_a = world->bodies[contact->body_a_index].friction;
	if (contact->type == PICOSYSTEM_PHYSICS_CONTACT_STATIC_SEGMENT) {
		return fixed_minimum(friction_a,
				     world->static_segments[contact->segment_index].friction);
	}
	return fixed_minimum(friction_a, world->bodies[contact->body_b_index].friction);
}

static picosystem_physics_fixed_t
contact_restitution(const struct picosystem_physics_world *world,
		    const struct picosystem_physics_contact *contact)
{
	const picosystem_physics_fixed_t restitution_a =
		world->bodies[contact->body_a_index].restitution;
	if (contact->type == PICOSYSTEM_PHYSICS_CONTACT_STATIC_SEGMENT) {
		return fixed_minimum(restitution_a,
				     world->static_segments[contact->segment_index].restitution);
	}
	return fixed_minimum(restitution_a, world->bodies[contact->body_b_index].restitution);
}

static int append_contact(struct picosystem_physics_world *world,
			  const struct picosystem_physics_contact *contact)
{
	if (world->contact_count >= PICOSYSTEM_PHYSICS_MAX_CONTACTS) {
		return -EOVERFLOW;
	}

	world->contacts[world->contact_count++] = *contact;
	return 0;
}

static void initialize_contact_target(struct picosystem_physics_world *world,
				      struct picosystem_physics_contact *contact)
{
	const struct picosystem_physics_vector relative = contact_relative_velocity(world, contact);
	const picosystem_physics_fixed_t normal_velocity = vector_dot(&relative, &contact->normal);
	if (normal_velocity < -PHYSICS_BOUNCE_THRESHOLD) {
		contact->target_normal_velocity =
			-fixed_multiply(contact_restitution(world, contact), normal_velocity);
	}
}

static int append_generated_contact(struct picosystem_physics_world *world, uint8_t body_a_index,
				    uint8_t body_b_index, uint8_t segment_index, uint8_t type,
				    const struct picosystem_physics_vector *normal,
				    const struct contact_point_candidate *candidate,
				    picosystem_physics_fixed_t position_correction_scale)
{
	struct picosystem_physics_contact contact = {
		.point = candidate->point,
		.normal = *normal,
		.penetration = candidate->penetration,
		.position_correction_scale = position_correction_scale,
		.body_a_index = body_a_index,
		.body_b_index = body_b_index,
		.segment_index = segment_index,
		.type = type,
	};
	initialize_contact_target(world, &contact);
	return append_contact(world, &contact);
}

static int append_manifold(struct picosystem_physics_world *world, uint8_t body_a_index,
			   uint8_t body_b_index, uint8_t segment_index, uint8_t type,
			   const struct picosystem_physics_vector *normal,
			   const struct contact_point_candidate *candidates, size_t count)
{
	if ((count == 0U) || (count > PICOSYSTEM_PHYSICS_MAX_MANIFOLD_POINTS)) {
		return -EINVAL;
	}

	const picosystem_physics_fixed_t correction_scale =
		PICOSYSTEM_PHYSICS_FIXED_ONE / (picosystem_physics_fixed_t)count;
	for (size_t index = 0U; index < count; ++index) {
		const int err = append_generated_contact(world, body_a_index, body_b_index,
							 segment_index, type, normal,
							 &candidates[index], correction_scale);
		if (err != 0) {
			return err;
		}
	}
	return 0;
}

static int generate_circle_circle_contact(struct picosystem_physics_world *world,
					  uint8_t body_a_index, uint8_t body_b_index)
{
	const struct picosystem_physics_body *const body_a = &world->bodies[body_a_index];
	const struct picosystem_physics_body *const body_b = &world->bodies[body_b_index];
	const struct picosystem_physics_vector delta =
		vector_subtract(&body_b->center, &body_a->center);
	const picosystem_physics_fixed_t combined_radius = body_a->radius + body_b->radius;
	const uint64_t radius_squared = (uint64_t)((int64_t)combined_radius * combined_radius);
	if (vector_length_squared_raw(&delta) >= radius_squared) {
		return 0;
	}

	const struct picosystem_physics_vector fallback = {
		.x = (body_a->id < body_b->id) ? PICOSYSTEM_PHYSICS_FIXED_ONE
					       : -PICOSYSTEM_PHYSICS_FIXED_ONE,
	};
	struct picosystem_physics_vector normal;
	const picosystem_physics_fixed_t distance = normalize_vector(&delta, &normal, &fallback);
	const struct picosystem_physics_vector radius_a = vector_scale(&normal, body_a->radius);
	const struct picosystem_physics_vector radius_b = vector_scale(&normal, body_b->radius);
	const struct picosystem_physics_vector point_a = vector_add(&body_a->center, &radius_a);
	const struct picosystem_physics_vector point_b =
		vector_subtract(&body_b->center, &radius_b);
	const struct contact_point_candidate candidate = {
		.point =
			{
				.x = (point_a.x + point_b.x) / 2,
				.y = (point_a.y + point_b.y) / 2,
			},
		.penetration = combined_radius - distance,
	};
	return append_manifold(world, body_a_index, body_b_index, STATIC_SEGMENT_INDEX,
			       PICOSYSTEM_PHYSICS_CONTACT_BODY, &normal, &candidate, 1U);
}

static struct picosystem_physics_vector
box_support_point(const struct picosystem_physics_body *body, const struct box_geometry *geometry,
		  const struct picosystem_physics_vector *direction)
{
	const picosystem_physics_fixed_t x_sign = (vector_dot(direction, &geometry->axis_x) >= 0)
							  ? body->half_extent.x
							  : -body->half_extent.x;
	const picosystem_physics_fixed_t y_sign = (vector_dot(direction, &geometry->axis_y) >= 0)
							  ? body->half_extent.y
							  : -body->half_extent.y;
	const struct picosystem_physics_vector x = vector_scale(&geometry->axis_x, x_sign);
	const struct picosystem_physics_vector y = vector_scale(&geometry->axis_y, y_sign);
	const struct picosystem_physics_vector center_plus_x = vector_add(&body->center, &x);
	return vector_add(&center_plus_x, &y);
}

static int generate_circle_box_contact(struct picosystem_physics_world *world, uint8_t circle_index,
				       uint8_t box_index, const struct box_geometry *geometry,
				       bool circle_is_body_a)
{
	const struct picosystem_physics_body *const circle = &world->bodies[circle_index];
	const struct picosystem_physics_body *const box = &world->bodies[box_index];

	const struct picosystem_physics_vector relative =
		vector_subtract(&circle->center, &box->center);
	const picosystem_physics_fixed_t local_x = vector_dot(&relative, &geometry->axis_x);
	const picosystem_physics_fixed_t local_y = vector_dot(&relative, &geometry->axis_y);
	const picosystem_physics_fixed_t closest_x =
		fixed_clamp(local_x, -box->half_extent.x, box->half_extent.x);
	const picosystem_physics_fixed_t closest_y =
		fixed_clamp(local_y, -box->half_extent.y, box->half_extent.y);
	const struct picosystem_physics_vector closest_offset_x =
		vector_scale(&geometry->axis_x, closest_x);
	const struct picosystem_physics_vector closest_offset_y =
		vector_scale(&geometry->axis_y, closest_y);
	const struct picosystem_physics_vector closest_with_x =
		vector_add(&box->center, &closest_offset_x);
	struct picosystem_physics_vector closest = vector_add(&closest_with_x, &closest_offset_y);
	const struct picosystem_physics_vector circle_to_closest =
		vector_subtract(&closest, &circle->center);
	const uint64_t distance_squared = vector_length_squared_raw(&circle_to_closest);
	const uint64_t radius_squared = (uint64_t)((int64_t)circle->radius * circle->radius);

	struct picosystem_physics_vector circle_to_box_normal;
	picosystem_physics_fixed_t penetration;
	bool circle_inside_box = false;
	if (distance_squared != 0U) {
		if (distance_squared >= radius_squared) {
			return 0;
		}
		const struct picosystem_physics_vector fallback = {
			.x = PICOSYSTEM_PHYSICS_FIXED_ONE,
		};
		const picosystem_physics_fixed_t distance =
			normalize_vector(&circle_to_closest, &circle_to_box_normal, &fallback);
		penetration = circle->radius - distance;
	} else {
		circle_inside_box = true;
		const picosystem_physics_fixed_t distance_x =
			box->half_extent.x - fixed_absolute(local_x);
		const picosystem_physics_fixed_t distance_y =
			box->half_extent.y - fixed_absolute(local_y);
		if (distance_x <= distance_y) {
			const picosystem_physics_fixed_t face_x =
				(local_x >= 0) ? box->half_extent.x : -box->half_extent.x;
			circle_to_box_normal = (local_x >= 0) ? geometry->axis_x
							      : vector_negate(&geometry->axis_x);
			const struct picosystem_physics_vector face_offset_x =
				vector_scale(&geometry->axis_x, face_x);
			const struct picosystem_physics_vector face_offset_y =
				vector_scale(&geometry->axis_y, local_y);
			const struct picosystem_physics_vector face_with_x =
				vector_add(&box->center, &face_offset_x);
			closest = vector_add(&face_with_x, &face_offset_y);
			penetration = circle->radius + distance_x;
		} else {
			const picosystem_physics_fixed_t face_y =
				(local_y >= 0) ? box->half_extent.y : -box->half_extent.y;
			circle_to_box_normal = (local_y >= 0) ? geometry->axis_y
							      : vector_negate(&geometry->axis_y);
			const struct picosystem_physics_vector face_offset_x =
				vector_scale(&geometry->axis_x, local_x);
			const struct picosystem_physics_vector face_offset_y =
				vector_scale(&geometry->axis_y, face_y);
			const struct picosystem_physics_vector face_with_x =
				vector_add(&box->center, &face_offset_x);
			closest = vector_add(&face_with_x, &face_offset_y);
			penetration = circle->radius + distance_y;
		}
		circle_to_box_normal = vector_negate(&circle_to_box_normal);
	}

	struct picosystem_physics_vector normal = circle_to_box_normal;
	if (!circle_is_body_a) {
		normal = vector_negate(&normal);
	}
	struct picosystem_physics_vector contact_point = closest;
	if (!circle_inside_box) {
		const struct picosystem_physics_vector circle_radius =
			vector_scale(&circle_to_box_normal, circle->radius);
		const struct picosystem_physics_vector circle_surface =
			vector_add(&circle->center, &circle_radius);
		contact_point = (struct picosystem_physics_vector){
			.x = (circle_surface.x + closest.x) / 2,
			.y = (circle_surface.y + closest.y) / 2,
		};
	}
	const struct contact_point_candidate candidate = {
		.point = contact_point,
		.penetration = penetration,
	};
	const uint8_t body_a_index = circle_is_body_a ? circle_index : box_index;
	const uint8_t body_b_index = circle_is_body_a ? box_index : circle_index;
	return append_manifold(world, body_a_index, body_b_index, STATIC_SEGMENT_INDEX,
			       PICOSYSTEM_PHYSICS_CONTACT_BODY, &normal, &candidate, 1U);
}

static picosystem_physics_fixed_t
box_projection_radius(const struct picosystem_physics_body *body,
		      const struct box_geometry *geometry,
		      const struct picosystem_physics_vector *axis)
{
	return fixed_multiply(body->half_extent.x,
			      fixed_absolute(vector_dot(&geometry->axis_x, axis))) +
	       fixed_multiply(body->half_extent.y,
			      fixed_absolute(vector_dot(&geometry->axis_y, axis)));
}

static size_t clip_segment_to_plane(
	const struct picosystem_physics_vector *input, size_t input_count,
	const struct picosystem_physics_vector *normal, picosystem_physics_fixed_t offset,
	struct picosystem_physics_vector output[PICOSYSTEM_PHYSICS_MAX_MANIFOLD_POINTS])
{
	if (input_count == 0U) {
		return 0U;
	}
	if (input_count == 1U) {
		if (vector_dot(&input[0], normal) <= offset) {
			output[0] = input[0];
			return 1U;
		}
		return 0U;
	}

	const picosystem_physics_fixed_t distance_0 = vector_dot(&input[0], normal) - offset;
	const picosystem_physics_fixed_t distance_1 = vector_dot(&input[1], normal) - offset;
	const bool inside_0 = distance_0 <= 0;
	const bool inside_1 = distance_1 <= 0;
	size_t output_count = 0U;

	if (inside_0) {
		output[output_count++] = input[0];
	}
	if (inside_0 != inside_1) {
		const picosystem_physics_fixed_t fraction =
			fixed_divide(distance_0, distance_0 - distance_1);
		const struct picosystem_physics_vector extent =
			vector_subtract(&input[1], &input[0]);
		const struct picosystem_physics_vector offset_vector =
			vector_scale(&extent, fraction);
		output[output_count++] = vector_add(&input[0], &offset_vector);
	}
	if (inside_1) {
		output[output_count++] = input[1];
	}

	return output_count;
}

static size_t clip_segment_to_box(
	const struct picosystem_physics_vector input[PICOSYSTEM_PHYSICS_MAX_MANIFOLD_POINTS],
	const struct picosystem_physics_body *box, const struct box_geometry *geometry,
	struct picosystem_physics_vector output[PICOSYSTEM_PHYSICS_MAX_MANIFOLD_POINTS])
{
	struct picosystem_physics_vector first[PICOSYSTEM_PHYSICS_MAX_MANIFOLD_POINTS];
	struct picosystem_physics_vector second[PICOSYSTEM_PHYSICS_MAX_MANIFOLD_POINTS];
	first[0] = input[0];
	first[1] = input[1];
	size_t count = PICOSYSTEM_PHYSICS_MAX_MANIFOLD_POINTS;

	const struct picosystem_physics_vector negative_x = vector_negate(&geometry->axis_x);
	const struct picosystem_physics_vector negative_y = vector_negate(&geometry->axis_y);
	const struct picosystem_physics_vector normals[] = {
		geometry->axis_x,
		negative_x,
		geometry->axis_y,
		negative_y,
	};
	const picosystem_physics_fixed_t offsets[] = {
		vector_dot(&box->center, &geometry->axis_x) + box->half_extent.x,
		vector_dot(&box->center, &negative_x) + box->half_extent.x,
		vector_dot(&box->center, &geometry->axis_y) + box->half_extent.y,
		vector_dot(&box->center, &negative_y) + box->half_extent.y,
	};

	for (size_t plane = 0U; plane < (sizeof(normals) / sizeof(normals[0])); ++plane) {
		struct picosystem_physics_vector *const source =
			(plane & 1U) == 0U ? first : second;
		struct picosystem_physics_vector *const destination =
			(plane & 1U) == 0U ? second : first;
		count = clip_segment_to_plane(source, count, &normals[plane], offsets[plane],
					      destination);
		if (count == 0U) {
			return 0U;
		}
	}

	for (size_t index = 0U; index < count; ++index) {
		output[index] = first[index];
	}
	return count;
}

static void
incident_box_edge(const struct picosystem_physics_body *body, const struct box_geometry *geometry,
		  const struct picosystem_physics_vector *reference_normal,
		  struct picosystem_physics_vector edge[PICOSYSTEM_PHYSICS_MAX_MANIFOLD_POINTS])
{
	const picosystem_physics_fixed_t dot_x = vector_dot(reference_normal, &geometry->axis_x);
	const picosystem_physics_fixed_t dot_y = vector_dot(reference_normal, &geometry->axis_y);
	struct picosystem_physics_vector outward;
	struct picosystem_physics_vector tangent;
	picosystem_physics_fixed_t normal_extent;
	picosystem_physics_fixed_t tangent_extent;

	if (fixed_absolute(dot_x) >= fixed_absolute(dot_y)) {
		outward = (dot_x > 0) ? vector_negate(&geometry->axis_x) : geometry->axis_x;
		tangent = geometry->axis_y;
		normal_extent = body->half_extent.x;
		tangent_extent = body->half_extent.y;
	} else {
		outward = (dot_y > 0) ? vector_negate(&geometry->axis_y) : geometry->axis_y;
		tangent = geometry->axis_x;
		normal_extent = body->half_extent.y;
		tangent_extent = body->half_extent.x;
	}

	const struct picosystem_physics_vector normal_offset =
		vector_scale(&outward, normal_extent);
	const struct picosystem_physics_vector tangent_offset =
		vector_scale(&tangent, tangent_extent);
	const struct picosystem_physics_vector face_center =
		vector_add(&body->center, &normal_offset);
	edge[0] = vector_subtract(&face_center, &tangent_offset);
	edge[1] = vector_add(&face_center, &tangent_offset);
}

static int generate_box_box_contact(struct picosystem_physics_world *world, uint8_t body_a_index,
				    uint8_t body_b_index, const struct box_geometry *geometry_a,
				    const struct box_geometry *geometry_b)
{
	const struct picosystem_physics_body *const body_a = &world->bodies[body_a_index];
	const struct picosystem_physics_body *const body_b = &world->bodies[body_b_index];
	const struct picosystem_physics_vector center_delta =
		vector_subtract(&body_b->center, &body_a->center);
	const struct picosystem_physics_vector axes[] = {
		geometry_a->axis_x,
		geometry_a->axis_y,
		geometry_b->axis_x,
		geometry_b->axis_y,
	};
	picosystem_physics_fixed_t minimum_overlap = INT32_MAX;
	size_t minimum_axis = 0U;

	for (size_t axis_index = 0U; axis_index < (sizeof(axes) / sizeof(axes[0])); ++axis_index) {
		const picosystem_physics_fixed_t radius_a =
			box_projection_radius(body_a, geometry_a, &axes[axis_index]);
		const picosystem_physics_fixed_t radius_b =
			box_projection_radius(body_b, geometry_b, &axes[axis_index]);
		const picosystem_physics_fixed_t distance =
			fixed_absolute(vector_dot(&center_delta, &axes[axis_index]));
		const picosystem_physics_fixed_t overlap = radius_a + radius_b - distance;
		if (overlap <= 0) {
			return 0;
		}
		if (overlap < minimum_overlap) {
			minimum_overlap = overlap;
			minimum_axis = axis_index;
		}
	}

	struct picosystem_physics_vector normal = axes[minimum_axis];
	const picosystem_physics_fixed_t normal_projection = vector_dot(&center_delta, &normal);
	if ((normal_projection < 0) || ((normal_projection == 0) && (body_a->id > body_b->id))) {
		normal = vector_negate(&normal);
	}

	const bool reference_is_a = minimum_axis < 2U;
	const struct picosystem_physics_body *const reference = reference_is_a ? body_a : body_b;
	const struct picosystem_physics_body *const incident = reference_is_a ? body_b : body_a;
	const struct box_geometry *const reference_geometry =
		reference_is_a ? geometry_a : geometry_b;
	const struct box_geometry *const incident_geometry =
		reference_is_a ? geometry_b : geometry_a;
	struct picosystem_physics_vector reference_normal =
		reference_is_a ? normal : vector_negate(&normal);
	const bool reference_x_axis = (minimum_axis == 0U) || (minimum_axis == 2U);
	const picosystem_physics_fixed_t reference_normal_extent =
		reference_x_axis ? reference->half_extent.x : reference->half_extent.y;
	const picosystem_physics_fixed_t reference_tangent_extent =
		reference_x_axis ? reference->half_extent.y : reference->half_extent.x;
	const struct picosystem_physics_vector reference_tangent =
		reference_x_axis ? reference_geometry->axis_y : reference_geometry->axis_x;
	const struct picosystem_physics_vector reference_normal_offset =
		vector_scale(&reference_normal, reference_normal_extent);
	const struct picosystem_physics_vector reference_face_center =
		vector_add(&reference->center, &reference_normal_offset);

	struct picosystem_physics_vector incident_edge[PICOSYSTEM_PHYSICS_MAX_MANIFOLD_POINTS];
	incident_box_edge(incident, incident_geometry, &reference_normal, incident_edge);
	struct picosystem_physics_vector first_clip[PICOSYSTEM_PHYSICS_MAX_MANIFOLD_POINTS];
	const picosystem_physics_fixed_t positive_offset =
		vector_dot(&reference_face_center, &reference_tangent) + reference_tangent_extent;
	size_t clipped_count =
		clip_segment_to_plane(incident_edge, PICOSYSTEM_PHYSICS_MAX_MANIFOLD_POINTS,
				      &reference_tangent, positive_offset, first_clip);
	if (clipped_count == 0U) {
		return 0;
	}
	const struct picosystem_physics_vector negative_tangent = vector_negate(&reference_tangent);
	const picosystem_physics_fixed_t negative_offset =
		vector_dot(&reference_face_center, &negative_tangent) + reference_tangent_extent;
	struct picosystem_physics_vector second_clip[PICOSYSTEM_PHYSICS_MAX_MANIFOLD_POINTS];
	clipped_count = clip_segment_to_plane(first_clip, clipped_count, &negative_tangent,
					      negative_offset, second_clip);

	struct contact_point_candidate candidates[PICOSYSTEM_PHYSICS_MAX_MANIFOLD_POINTS];
	size_t candidate_count = 0U;
	for (size_t index = 0U; index < clipped_count; ++index) {
		const struct picosystem_physics_vector from_face =
			vector_subtract(&second_clip[index], &reference_face_center);
		const picosystem_physics_fixed_t separation =
			vector_dot(&from_face, &reference_normal);
		if (separation > 0) {
			continue;
		}
		const struct picosystem_physics_vector midpoint_offset =
			vector_scale(&reference_normal, separation / 2);
		candidates[candidate_count++] = (struct contact_point_candidate){
			.point = vector_subtract(&second_clip[index], &midpoint_offset),
			.penetration = -separation,
		};
	}

	if (candidate_count == 0U) {
		const struct picosystem_physics_vector negative_normal = vector_negate(&normal);
		const struct picosystem_physics_vector support_a =
			box_support_point(body_a, geometry_a, &normal);
		const struct picosystem_physics_vector support_b =
			box_support_point(body_b, geometry_b, &negative_normal);
		candidates[0] = (struct contact_point_candidate){
			.point =
				{
					.x = (support_a.x + support_b.x) / 2,
					.y = (support_a.y + support_b.y) / 2,
				},
			.penetration = minimum_overlap,
		};
		candidate_count = 1U;
	}

	return append_manifold(world, body_a_index, body_b_index, STATIC_SEGMENT_INDEX,
			       PICOSYSTEM_PHYSICS_CONTACT_BODY, &normal, candidates,
			       candidate_count);
}

static int
generate_body_contact(struct picosystem_physics_world *world, uint8_t body_a_index,
		      uint8_t body_b_index,
		      const struct box_geometry geometries[PICOSYSTEM_PHYSICS_MAX_BODIES])
{
	const uint8_t shape_a = world->bodies[body_a_index].shape;
	const uint8_t shape_b = world->bodies[body_b_index].shape;
	if ((shape_a == PICOSYSTEM_PHYSICS_SHAPE_CIRCLE) &&
	    (shape_b == PICOSYSTEM_PHYSICS_SHAPE_CIRCLE)) {
		return generate_circle_circle_contact(world, body_a_index, body_b_index);
	}
	if ((shape_a == PICOSYSTEM_PHYSICS_SHAPE_CIRCLE) &&
	    (shape_b == PICOSYSTEM_PHYSICS_SHAPE_BOX)) {
		return generate_circle_box_contact(world, body_a_index, body_b_index,
						   &geometries[body_b_index], true);
	}
	if ((shape_a == PICOSYSTEM_PHYSICS_SHAPE_BOX) &&
	    (shape_b == PICOSYSTEM_PHYSICS_SHAPE_CIRCLE)) {
		return generate_circle_box_contact(world, body_b_index, body_a_index,
						   &geometries[body_a_index], false);
	}
	return generate_box_box_contact(world, body_a_index, body_b_index,
					&geometries[body_a_index], &geometries[body_b_index]);
}

static struct picosystem_physics_vector
closest_point_on_segment(const struct picosystem_physics_vector *point,
			 const struct picosystem_physics_static_segment *segment)
{
	const struct picosystem_physics_vector extent =
		vector_subtract(&segment->end, &segment->start);
	const struct picosystem_physics_vector from_start = vector_subtract(point, &segment->start);
	const int64_t projection_raw =
		((int64_t)from_start.x * extent.x) + ((int64_t)from_start.y * extent.y);
	const int64_t length_squared_raw = (int64_t)vector_length_squared_raw(&extent);
	if (projection_raw <= 0) {
		return segment->start;
	}
	if (projection_raw >= length_squared_raw) {
		return segment->end;
	}

	const int64_t reduced_projection = projection_raw / PICOSYSTEM_PHYSICS_FIXED_ONE;
	const int64_t reduced_length = length_squared_raw / PICOSYSTEM_PHYSICS_FIXED_ONE;
	const picosystem_physics_fixed_t fraction =
		(picosystem_physics_fixed_t)((reduced_projection * PICOSYSTEM_PHYSICS_FIXED_ONE) /
					     reduced_length);
	const struct picosystem_physics_vector offset = vector_scale(&extent, fraction);
	return vector_add(&segment->start, &offset);
}

static int generate_circle_segment_contact(struct picosystem_physics_world *world,
					   uint8_t body_index, uint8_t segment_index)
{
	const struct picosystem_physics_body *const body = &world->bodies[body_index];
	const struct picosystem_physics_static_segment *const segment =
		&world->static_segments[segment_index];
	const struct picosystem_physics_vector closest =
		closest_point_on_segment(&body->center, segment);
	const struct picosystem_physics_vector body_to_segment =
		vector_subtract(&closest, &body->center);
	const uint64_t radius_squared = (uint64_t)((int64_t)body->radius * body->radius);
	if (vector_length_squared_raw(&body_to_segment) >= radius_squared) {
		return 0;
	}

	struct picosystem_physics_vector normal;
	const picosystem_physics_fixed_t distance =
		normalize_vector(&body_to_segment, &normal, &segment->normal);
	const struct contact_point_candidate candidate = {
		.point = closest,
		.penetration = body->radius - distance,
	};
	return append_manifold(world, body_index, STATIC_BODY_INDEX, segment_index,
			       PICOSYSTEM_PHYSICS_CONTACT_STATIC_SEGMENT, &normal, &candidate, 1U);
}

static picosystem_physics_fixed_t interval_separation_depth(
	picosystem_physics_fixed_t body_minimum, picosystem_physics_fixed_t body_maximum,
	picosystem_physics_fixed_t segment_minimum, picosystem_physics_fixed_t segment_maximum)
{
	if ((body_maximum <= segment_minimum) || (segment_maximum <= body_minimum)) {
		return 0;
	}
	return fixed_minimum(body_maximum - segment_minimum, segment_maximum - body_minimum);
}

static int generate_box_segment_contact(struct picosystem_physics_world *world, uint8_t body_index,
					uint8_t segment_index, const struct box_geometry *geometry)
{
	const struct picosystem_physics_body *const body = &world->bodies[body_index];
	const struct picosystem_physics_static_segment *const segment =
		&world->static_segments[segment_index];
	const struct picosystem_physics_vector axes[] = {
		geometry->axis_x,
		geometry->axis_y,
		segment->normal,
	};
	picosystem_physics_fixed_t minimum_depth = INT32_MAX;
	size_t minimum_axis = 0U;

	for (size_t axis_index = 0U; axis_index < (sizeof(axes) / sizeof(axes[0])); ++axis_index) {
		const picosystem_physics_fixed_t center =
			vector_dot(&body->center, &axes[axis_index]);
		const picosystem_physics_fixed_t radius =
			box_projection_radius(body, geometry, &axes[axis_index]);
		const picosystem_physics_fixed_t start =
			vector_dot(&segment->start, &axes[axis_index]);
		const picosystem_physics_fixed_t end = vector_dot(&segment->end, &axes[axis_index]);
		const picosystem_physics_fixed_t segment_minimum = fixed_minimum(start, end);
		const picosystem_physics_fixed_t segment_maximum = fixed_maximum(start, end);
		const picosystem_physics_fixed_t depth = interval_separation_depth(
			center - radius, center + radius, segment_minimum, segment_maximum);
		if (depth <= 0) {
			return 0;
		}
		if (depth < minimum_depth) {
			minimum_depth = depth;
			minimum_axis = axis_index;
		}
	}

	struct picosystem_physics_vector normal = axes[minimum_axis];
	const struct picosystem_physics_vector segment_midpoint = {
		.x = (segment->start.x + segment->end.x) / 2,
		.y = (segment->start.y + segment->end.y) / 2,
	};
	const struct picosystem_physics_vector body_to_segment_midpoint =
		vector_subtract(&segment_midpoint, &body->center);
	const picosystem_physics_fixed_t direction = vector_dot(&body_to_segment_midpoint, &normal);
	if ((direction < 0) || ((direction == 0) && (body->id > segment->id))) {
		normal = vector_negate(&normal);
	}

	const struct picosystem_physics_vector input[] = {
		segment->start,
		segment->end,
	};
	struct picosystem_physics_vector clipped[PICOSYSTEM_PHYSICS_MAX_MANIFOLD_POINTS];
	size_t candidate_count = clip_segment_to_box(input, body, geometry, clipped);
	if ((candidate_count == 2U) && (clipped[0].x == clipped[1].x) &&
	    (clipped[0].y == clipped[1].y)) {
		candidate_count = 1U;
	}
	if (candidate_count == 0U) {
		return 0;
	}

	struct contact_point_candidate candidates[PICOSYSTEM_PHYSICS_MAX_MANIFOLD_POINTS];
	for (size_t index = 0U; index < candidate_count; ++index) {
		candidates[index] = (struct contact_point_candidate){
			.point = clipped[index],
			.penetration = minimum_depth,
		};
	}
	return append_manifold(world, body_index, STATIC_BODY_INDEX, segment_index,
			       PICOSYSTEM_PHYSICS_CONTACT_STATIC_SEGMENT, &normal, candidates,
			       candidate_count);
}

static int generate_segment_contact(struct picosystem_physics_world *world, uint8_t body_index,
				    uint8_t segment_index, const struct box_geometry *geometry)
{
	if (world->bodies[body_index].shape == PICOSYSTEM_PHYSICS_SHAPE_CIRCLE) {
		return generate_circle_segment_contact(world, body_index, segment_index);
	}
	return generate_box_segment_contact(world, body_index, segment_index, geometry);
}

static void body_aabb(const struct picosystem_physics_body *body,
		      const struct box_geometry *geometry, struct physics_aabb *aabb)
{
	picosystem_physics_fixed_t extent_x = body->radius;
	picosystem_physics_fixed_t extent_y = body->radius;
	if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_BOX) {
		extent_x = fixed_multiply(fixed_absolute(geometry->axis_x.x), body->half_extent.x) +
			   fixed_multiply(fixed_absolute(geometry->axis_y.x), body->half_extent.y);
		extent_y = fixed_multiply(fixed_absolute(geometry->axis_x.y), body->half_extent.x) +
			   fixed_multiply(fixed_absolute(geometry->axis_y.y), body->half_extent.y);
	}

	*aabb = (struct physics_aabb){
		.minimum_x = body->center.x - extent_x,
		.minimum_y = body->center.y - extent_y,
		.maximum_x = body->center.x + extent_x,
		.maximum_y = body->center.y + extent_y,
	};
}

static void segment_aabb(const struct picosystem_physics_static_segment *segment,
			 struct physics_aabb *aabb)
{
	*aabb = (struct physics_aabb){
		.minimum_x = fixed_minimum(segment->start.x, segment->end.x),
		.minimum_y = fixed_minimum(segment->start.y, segment->end.y),
		.maximum_x = fixed_maximum(segment->start.x, segment->end.x),
		.maximum_y = fixed_maximum(segment->start.y, segment->end.y),
	};
}

static bool grid_range_from_aabb(const struct physics_aabb *aabb, struct physics_grid_range *range)
{
	if ((aabb->minimum_x < 0) || (aabb->minimum_y < 0) || (aabb->maximum_x < aabb->minimum_x) ||
	    (aabb->maximum_y < aabb->minimum_y) || (aabb->maximum_x >= PHYSICS_GRID_WIDTH_FIXED) ||
	    (aabb->maximum_y >= PHYSICS_GRID_HEIGHT_FIXED)) {
		return false;
	}

	*range = (struct physics_grid_range){
		.minimum_column = (uint8_t)(aabb->minimum_x / PHYSICS_GRID_CELL_SIZE_FIXED),
		.minimum_row = (uint8_t)(aabb->minimum_y / PHYSICS_GRID_CELL_SIZE_FIXED),
		.maximum_column = (uint8_t)(aabb->maximum_x / PHYSICS_GRID_CELL_SIZE_FIXED),
		.maximum_row = (uint8_t)(aabb->maximum_y / PHYSICS_GRID_CELL_SIZE_FIXED),
	};
	return true;
}

static void clear_grid(struct picosystem_physics_world *world)
{
	memset(world->grid_cells, 0, sizeof(world->grid_cells));
	world->last_occupied_grid_cell_count = 0U;
	world->last_work.occupied_grid_cell_count = 0U;
}

static void occupy_grid_range(struct picosystem_physics_world *world,
			      const struct physics_grid_range *range, uint16_t body_mask,
			      uint8_t static_segment_mask)
{
	for (uint16_t row = range->minimum_row; row <= range->maximum_row; ++row) {
		for (uint16_t column = range->minimum_column; column <= range->maximum_column;
		     ++column) {
			const size_t index = (row * PICOSYSTEM_PHYSICS_GRID_COLUMNS) + column;
			struct picosystem_physics_grid_cell *const cell = &world->grid_cells[index];
			if ((cell->body_mask == 0U) && (cell->static_segment_mask == 0U)) {
				++world->last_occupied_grid_cell_count;
				++world->last_work.occupied_grid_cell_count;
			}
			cell->body_mask |= body_mask;
			cell->static_segment_mask |= static_segment_mask;
			++world->last_work.grid_cell_insertion_count;
			const uint32_t occupancy =
				(uint32_t)__builtin_popcount((unsigned int)cell->body_mask) +
				(uint32_t)__builtin_popcount(
					(unsigned int)cell->static_segment_mask);
			if (occupancy > world->last_work.maximum_grid_cell_occupancy) {
				world->last_work.maximum_grid_cell_occupancy = occupancy;
			}
		}
	}
}

static void collect_grid_candidates(const struct picosystem_physics_world *world,
				    struct physics_candidate_sets *candidates)
{
	for (size_t cell_index = 0U; cell_index < PICOSYSTEM_PHYSICS_GRID_CELL_COUNT;
	     ++cell_index) {
		const struct picosystem_physics_grid_cell *const cell =
			&world->grid_cells[cell_index];
		for (uint8_t body_index = 0U; body_index < world->body_count; ++body_index) {
			const uint16_t body_bit = (uint16_t)(UINT16_C(1) << body_index);
			if ((cell->body_mask & body_bit) == 0U) {
				continue;
			}

			const uint16_t through_current =
				(uint16_t)((UINT32_C(1) << ((uint32_t)body_index + 1U)) - 1U);
			candidates->body_masks[body_index] |=
				cell->body_mask & (uint16_t)~through_current;
			candidates->static_segment_masks[body_index] |= cell->static_segment_mask;
		}
	}
}

static bool
build_grid_candidates(struct picosystem_physics_world *world,
		      const struct box_geometry geometries[PICOSYSTEM_PHYSICS_MAX_BODIES],
		      struct physics_candidate_sets *candidates)
{
	clear_grid(world);
	memset(candidates, 0, sizeof(*candidates));

	for (uint8_t body_index = 0U; body_index < world->body_count; ++body_index) {
		struct physics_aabb aabb;
		body_aabb(&world->bodies[body_index], &geometries[body_index], &aabb);
		struct physics_grid_range range;
		if (!grid_range_from_aabb(&aabb, &range)) {
			clear_grid(world);
			return false;
		}
		occupy_grid_range(world, &range, (uint16_t)(UINT16_C(1) << body_index), 0U);
	}

	for (uint8_t segment_index = 0U; segment_index < world->static_segment_count;
	     ++segment_index) {
		struct physics_aabb aabb;
		segment_aabb(&world->static_segments[segment_index], &aabb);
		struct physics_grid_range range;
		if (!grid_range_from_aabb(&aabb, &range)) {
			clear_grid(world);
			return false;
		}
		occupy_grid_range(world, &range, 0U, (uint8_t)(UINT8_C(1) << segment_index));
	}

	collect_grid_candidates(world, candidates);
	return true;
}

static uint32_t possible_pair_count(const struct picosystem_physics_world *world)
{
	const uint32_t body_count = world->body_count;
	const uint32_t body_pair_count =
		(body_count < 2U) ? 0U : (body_count * (body_count - 1U)) / 2U;
	return body_pair_count + (body_count * world->static_segment_count);
}

static bool body_pair_collision_is_disabled(const struct picosystem_physics_world *world,
					    uint8_t body_a_index, uint8_t body_b_index)
{
	for (uint16_t index = 0U; index < world->revolute_joint_count; ++index) {
		const struct picosystem_physics_revolute_joint *const joint =
			&world->revolute_joints[index];
		if ((joint->body_b_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID) ||
		    (joint->collide_connected != 0U)) {
			continue;
		}
		if (((joint->body_a_index == body_a_index) &&
		     (joint->body_b_index == body_b_index)) ||
		    ((joint->body_a_index == body_b_index) &&
		     (joint->body_b_index == body_a_index))) {
			return true;
		}
	}
	return false;
}

static int build_contacts(struct picosystem_physics_world *world, bool force_brute_force,
			  struct physics_step_profiler *profiler)
{
	world->contact_count = 0U;
	world->last_candidate_pair_count = 0U;
	world->last_possible_pair_count = possible_pair_count(world);
	world->last_work.possible_pair_count = world->last_possible_pair_count;
	uint32_t section_start = profiler_section_begin(profiler);
	struct box_geometry geometries[PICOSYSTEM_PHYSICS_MAX_BODIES] = {0};
	for (uint8_t body_index = 0U; body_index < world->body_count; ++body_index) {
		if (world->bodies[body_index].shape == PICOSYSTEM_PHYSICS_SHAPE_BOX) {
			box_geometry_from_body(&world->bodies[body_index], &geometries[body_index]);
		}
	}
	profiler_section_end(profiler, PICOSYSTEM_PHYSICS_PROFILE_BOX_GEOMETRY, section_start);

	section_start = profiler_section_begin(profiler);
	struct physics_candidate_sets candidates = {0};
	const bool use_brute_force =
		force_brute_force || !build_grid_candidates(world, geometries, &candidates);
	world->last_broad_phase_fallback = use_brute_force ? 1U : 0U;
	world->last_work.broad_phase_fallback_count =
		(use_brute_force && !force_brute_force) ? 1U : 0U;
	if (force_brute_force) {
		clear_grid(world);
	}
	profiler_section_end(profiler, PICOSYSTEM_PHYSICS_PROFILE_BROAD_PHASE, section_start);

	for (uint8_t body_a = 0U; body_a < world->body_count; ++body_a) {
		section_start = profiler_section_begin(profiler);
		for (uint8_t body_b = body_a + 1U; body_b < world->body_count; ++body_b) {
			const uint16_t body_b_mask = (uint16_t)(UINT16_C(1) << body_b);
			if (!use_brute_force &&
			    ((candidates.body_masks[body_a] & body_b_mask) == 0U)) {
				continue;
			}
			++world->last_candidate_pair_count;
			++world->last_work.candidate_pair_count;
			if (body_pair_collision_is_disabled(world, body_a, body_b)) {
				++world->last_work.joint_collision_filter_count;
				continue;
			}
			++world->last_work.body_body_narrow_phase_test_count;
			const uint16_t previous_contact_count = world->contact_count;
			const int err = generate_body_contact(world, body_a, body_b, geometries);
			if (err != 0) {
				profiler_section_end(profiler,
						     PICOSYSTEM_PHYSICS_PROFILE_NARROW_BODY_BODY,
						     section_start);
				return err;
			}
			if (world->contact_count > previous_contact_count) {
				++world->last_work.manifold_count;
			}
		}
		profiler_section_end(profiler, PICOSYSTEM_PHYSICS_PROFILE_NARROW_BODY_BODY,
				     section_start);

		section_start = profiler_section_begin(profiler);
		for (uint8_t segment = 0U; segment < world->static_segment_count; ++segment) {
			const uint8_t segment_mask = (uint8_t)(UINT8_C(1) << segment);
			if (!use_brute_force &&
			    ((candidates.static_segment_masks[body_a] & segment_mask) == 0U)) {
				continue;
			}
			++world->last_candidate_pair_count;
			++world->last_work.candidate_pair_count;
			++world->last_work.body_segment_narrow_phase_test_count;
			const uint16_t previous_contact_count = world->contact_count;
			const int err = generate_segment_contact(world, body_a, segment,
								 &geometries[body_a]);
			if (err != 0) {
				profiler_section_end(profiler,
						     PICOSYSTEM_PHYSICS_PROFILE_NARROW_BODY_SEGMENT,
						     section_start);
				return err;
			}
			if (world->contact_count > previous_contact_count) {
				++world->last_work.manifold_count;
			}
		}
		profiler_section_end(profiler, PICOSYSTEM_PHYSICS_PROFILE_NARROW_BODY_SEGMENT,
				     section_start);
	}
	world->last_work.contact_point_count = world->contact_count;

	return 0;
}

static void apply_position_correction(struct picosystem_physics_world *world,
				      const struct picosystem_physics_contact *contact)
{
	picosystem_physics_fixed_t depth = contact->penetration - PHYSICS_POSITION_SLOP;
	if (depth <= 0) {
		return;
	}
	depth = fixed_multiply(depth, contact->position_correction_scale);

	const picosystem_physics_fixed_t inverse_mass_sum =
		contact_linear_inverse_mass(world, contact);
	const picosystem_physics_fixed_t correction_impulse = fixed_divide(depth, inverse_mass_sum);
	struct picosystem_physics_body *const body_a = &world->bodies[contact->body_a_index];
	const picosystem_physics_fixed_t correction_a =
		fixed_multiply(correction_impulse, body_a->inverse_mass);
	body_a->center.x -= fixed_multiply(contact->normal.x, correction_a);
	body_a->center.y -= fixed_multiply(contact->normal.y, correction_a);

	if (contact->type == PICOSYSTEM_PHYSICS_CONTACT_BODY) {
		struct picosystem_physics_body *const body_b =
			&world->bodies[contact->body_b_index];
		const picosystem_physics_fixed_t correction_b =
			fixed_multiply(correction_impulse, body_b->inverse_mass);
		body_b->center.x += fixed_multiply(contact->normal.x, correction_b);
		body_b->center.y += fixed_multiply(contact->normal.y, correction_b);
	}
}

static void apply_body_impulse(struct picosystem_physics_body *body,
			       const struct picosystem_physics_vector *point,
			       const struct picosystem_physics_vector *direction,
			       picosystem_physics_fixed_t impulse, picosystem_physics_fixed_t sign)
{
	const picosystem_physics_fixed_t signed_impulse = fixed_multiply(impulse, sign);
	const picosystem_physics_fixed_t velocity_change =
		fixed_multiply(signed_impulse, body->inverse_mass);
	body->velocity_per_tick.x += fixed_multiply(direction->x, velocity_change);
	body->velocity_per_tick.y += fixed_multiply(direction->y, velocity_change);

	const struct picosystem_physics_vector lever = vector_subtract(point, &body->center);
	const picosystem_physics_fixed_t angular_impulse =
		fixed_multiply(vector_cross(&lever, direction), signed_impulse);
	body->angular_velocity_per_tick += fixed_multiply(body->inverse_inertia, angular_impulse);
}

static void apply_body_vector_impulse(struct picosystem_physics_body *body,
				      const struct picosystem_physics_vector *point,
				      const struct picosystem_physics_vector *impulse, bool negate)
{
	const struct picosystem_physics_vector signed_impulse =
		negate ? vector_negate(impulse) : *impulse;
	body->velocity_per_tick.x += fixed_multiply(signed_impulse.x, body->inverse_mass);
	body->velocity_per_tick.y += fixed_multiply(signed_impulse.y, body->inverse_mass);

	const struct picosystem_physics_vector lever = vector_subtract(point, &body->center);
	const picosystem_physics_fixed_t angular_impulse = vector_cross(&lever, &signed_impulse);
	body->angular_velocity_per_tick += fixed_multiply(body->inverse_inertia, angular_impulse);
}

static void apply_contact_impulse(struct picosystem_physics_world *world,
				  const struct picosystem_physics_contact *contact,
				  const struct picosystem_physics_vector *direction,
				  picosystem_physics_fixed_t impulse)
{
	apply_body_impulse(&world->bodies[contact->body_a_index], &contact->point, direction,
			   impulse, -PICOSYSTEM_PHYSICS_FIXED_ONE);
	if (contact->type == PICOSYSTEM_PHYSICS_CONTACT_BODY) {
		apply_body_impulse(&world->bodies[contact->body_b_index], &contact->point,
				   direction, impulse, PICOSYSTEM_PHYSICS_FIXED_ONE);
	}
}

static bool solve_contact_velocity(struct picosystem_physics_world *world,
				   struct picosystem_physics_contact *contact)
{
	const picosystem_physics_fixed_t normal_inverse_mass =
		contact_direction_inverse_mass(world, contact, &contact->normal);
	struct picosystem_physics_vector relative = contact_relative_velocity(world, contact);
	const picosystem_physics_fixed_t normal_velocity = vector_dot(&relative, &contact->normal);
	const picosystem_physics_fixed_t normal_delta = fixed_divide(
		contact->target_normal_velocity - normal_velocity, normal_inverse_mass);
	const picosystem_physics_fixed_t previous_normal = contact->accumulated_normal_impulse;
	contact->accumulated_normal_impulse =
		(previous_normal + normal_delta > 0) ? previous_normal + normal_delta : 0;
	const picosystem_physics_fixed_t applied_normal =
		contact->accumulated_normal_impulse - previous_normal;
	apply_contact_impulse(world, contact, &contact->normal, applied_normal);

	relative = contact_relative_velocity(world, contact);
	const struct picosystem_physics_vector tangent = {
		.x = -contact->normal.y,
		.y = contact->normal.x,
	};
	const picosystem_physics_fixed_t tangent_inverse_mass =
		contact_direction_inverse_mass(world, contact, &tangent);
	const picosystem_physics_fixed_t tangent_velocity = vector_dot(&relative, &tangent);
	const picosystem_physics_fixed_t tangent_delta =
		fixed_divide(-tangent_velocity, tangent_inverse_mass);
	const picosystem_physics_fixed_t maximum_friction = fixed_multiply(
		contact_friction(world, contact), contact->accumulated_normal_impulse);
	const picosystem_physics_fixed_t previous_tangent = contact->accumulated_tangent_impulse;
	contact->accumulated_tangent_impulse =
		fixed_clamp(previous_tangent + tangent_delta, -maximum_friction, maximum_friction);
	const picosystem_physics_fixed_t applied_tangent =
		contact->accumulated_tangent_impulse - previous_tangent;
	apply_contact_impulse(world, contact, &tangent, applied_tangent);
	return (applied_normal != 0) || (applied_tangent != 0);
}

static void apply_body_position_impulse(struct picosystem_physics_body *body,
					const struct picosystem_physics_vector *point,
					const struct picosystem_physics_vector *direction,
					picosystem_physics_fixed_t impulse,
					picosystem_physics_fixed_t sign)
{
	const struct picosystem_physics_vector lever = vector_subtract(point, &body->center);
	const picosystem_physics_fixed_t signed_impulse = fixed_multiply(impulse, sign);
	const picosystem_physics_fixed_t position_change =
		fixed_multiply(signed_impulse, body->inverse_mass);
	body->center.x += fixed_multiply(direction->x, position_change);
	body->center.y += fixed_multiply(direction->y, position_change);

	const picosystem_physics_fixed_t angular_impulse =
		fixed_multiply(vector_cross(&lever, direction), signed_impulse);
	const picosystem_physics_fixed_t angular_change =
		fixed_multiply(body->inverse_inertia, angular_impulse);
	apply_body_angle_delta(body, angular_change);
}

static void apply_body_position_vector_impulse(struct picosystem_physics_body *body,
					       const struct picosystem_physics_vector *point,
					       const struct picosystem_physics_vector *impulse,
					       bool negate)
{
	const struct picosystem_physics_vector signed_impulse =
		negate ? vector_negate(impulse) : *impulse;
	const struct picosystem_physics_vector lever = vector_subtract(point, &body->center);
	body->center.x += fixed_multiply(signed_impulse.x, body->inverse_mass);
	body->center.y += fixed_multiply(signed_impulse.y, body->inverse_mass);

	const picosystem_physics_fixed_t angular_impulse = vector_cross(&lever, &signed_impulse);
	const picosystem_physics_fixed_t angular_change =
		fixed_multiply(body->inverse_inertia, angular_impulse);
	apply_body_angle_delta(body, angular_change);
}

static bool
apply_distance_joint_position_correction(struct picosystem_physics_world *world,
					 const struct picosystem_physics_distance_joint *joint)
{
	struct picosystem_physics_vector world_anchor_a;
	struct picosystem_physics_vector world_anchor_b;
	struct picosystem_physics_vector normal;
	const picosystem_physics_fixed_t distance =
		distance_joint_geometry(world, joint, &world_anchor_a, &world_anchor_b, &normal);
	picosystem_physics_fixed_t error = distance - joint->target_distance;
	if (fixed_absolute(error) <= PHYSICS_JOINT_POSITION_SLOP) {
		return false;
	}
	error += (error > 0) ? -PHYSICS_JOINT_POSITION_SLOP : PHYSICS_JOINT_POSITION_SLOP;
	error = fixed_clamp(error, -PHYSICS_JOINT_MAX_CORRECTION, PHYSICS_JOINT_MAX_CORRECTION);
	const picosystem_physics_fixed_t correction =
		fixed_multiply(error, PHYSICS_JOINT_CORRECTION_SCALE);
	const picosystem_physics_fixed_t direction_inverse_mass =
		distance_joint_direction_inverse_mass(world, joint, &world_anchor_a,
						      &world_anchor_b, &normal);
	const picosystem_physics_fixed_t impulse = fixed_divide(correction, direction_inverse_mass);
	apply_body_position_impulse(&world->bodies[joint->body_a_index], &world_anchor_a, &normal,
				    impulse, PICOSYSTEM_PHYSICS_FIXED_ONE);
	if (joint->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		apply_body_position_impulse(&world->bodies[joint->body_b_index], &world_anchor_b,
					    &normal, impulse, -PICOSYSTEM_PHYSICS_FIXED_ONE);
	}
	return true;
}

static void prepare_distance_joint(struct picosystem_physics_world *world,
				   struct picosystem_physics_distance_joint *joint)
{
	(void)distance_joint_geometry(world, joint, &joint->world_anchor_a, &joint->world_anchor_b,
				      &joint->normal);
	joint->direction_inverse_mass = distance_joint_direction_inverse_mass(
		world, joint, &joint->world_anchor_a, &joint->world_anchor_b, &joint->normal);
	joint->accumulated_impulse = 0;
}

static struct picosystem_physics_vector
distance_joint_relative_velocity(const struct picosystem_physics_world *world,
				 const struct picosystem_physics_distance_joint *joint)
{
	const struct picosystem_physics_vector velocity_a =
		body_velocity_at_point(&world->bodies[joint->body_a_index], &joint->world_anchor_a);
	if (joint->body_b_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		return vector_negate(&velocity_a);
	}
	const struct picosystem_physics_vector velocity_b =
		body_velocity_at_point(&world->bodies[joint->body_b_index], &joint->world_anchor_b);
	return vector_subtract(&velocity_b, &velocity_a);
}

static bool solve_distance_joint_velocity(struct picosystem_physics_world *world,
					  struct picosystem_physics_distance_joint *joint)
{
	const struct picosystem_physics_vector relative =
		distance_joint_relative_velocity(world, joint);
	const picosystem_physics_fixed_t velocity = vector_dot(&relative, &joint->normal);
	const picosystem_physics_fixed_t impulse =
		fixed_divide(-velocity, joint->direction_inverse_mass);
	joint->accumulated_impulse += impulse;
	apply_body_impulse(&world->bodies[joint->body_a_index], &joint->world_anchor_a,
			   &joint->normal, impulse, -PICOSYSTEM_PHYSICS_FIXED_ONE);
	if (joint->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		apply_body_impulse(&world->bodies[joint->body_b_index], &joint->world_anchor_b,
				   &joint->normal, impulse, PICOSYSTEM_PHYSICS_FIXED_ONE);
	}
	return impulse != 0;
}

static bool
apply_revolute_joint_position_correction(struct picosystem_physics_world *world,
					 const struct picosystem_physics_revolute_joint *joint)
{
	struct picosystem_physics_vector world_anchor_a;
	struct picosystem_physics_vector world_anchor_b;
	revolute_joint_anchors(world, joint, &world_anchor_a, &world_anchor_b);
	const struct picosystem_physics_vector error =
		vector_subtract(&world_anchor_b, &world_anchor_a);
	struct picosystem_physics_vector normal;
	const struct picosystem_physics_vector fallback = {
		.x = PICOSYSTEM_PHYSICS_FIXED_ONE,
	};
	const picosystem_physics_fixed_t distance = normalize_vector(&error, &normal, &fallback);
	if (distance <= PHYSICS_JOINT_POSITION_SLOP) {
		return false;
	}

	struct physics_symmetric_matrix effective_mass;
	if (!revolute_joint_effective_mass(world, joint, &world_anchor_a, &world_anchor_b,
					   &effective_mass)) {
		return false;
	}
	const picosystem_physics_fixed_t bounded_error =
		fixed_minimum(distance - PHYSICS_JOINT_POSITION_SLOP, PHYSICS_JOINT_MAX_CORRECTION);
	const picosystem_physics_fixed_t correction_distance =
		fixed_multiply(bounded_error, PHYSICS_JOINT_CORRECTION_SCALE);
	const struct picosystem_physics_vector correction =
		vector_scale(&normal, correction_distance);
	const struct picosystem_physics_vector impulse =
		matrix_transform(&effective_mass, &correction);
	apply_body_position_vector_impulse(&world->bodies[joint->body_a_index], &world_anchor_a,
					   &impulse, false);
	if (joint->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		apply_body_position_vector_impulse(&world->bodies[joint->body_b_index],
						   &world_anchor_b, &impulse, true);
	}
	return (impulse.x != 0) || (impulse.y != 0);
}

static picosystem_physics_fixed_t
revolute_joint_limit_error(const struct picosystem_physics_world *world,
			   const struct picosystem_physics_revolute_joint *joint)
{
	if (joint->limit_enabled == 0U) {
		return 0;
	}

	const picosystem_physics_fixed_t angle =
		revolute_joint_relative_angle_radians(world, joint);
	if (joint->lower_angle_radians == joint->upper_angle_radians) {
		return angle - joint->lower_angle_radians;
	}
	if (angle < joint->lower_angle_radians) {
		return angle - joint->lower_angle_radians;
	}
	if (angle > joint->upper_angle_radians) {
		return angle - joint->upper_angle_radians;
	}
	return 0;
}

static void
apply_revolute_joint_angular_position_impulse(struct picosystem_physics_world *world,
					      const struct picosystem_physics_revolute_joint *joint,
					      picosystem_physics_fixed_t impulse)
{
	struct picosystem_physics_body *const body_a = &world->bodies[joint->body_a_index];
	apply_body_angle_delta(body_a, fixed_multiply(body_a->inverse_inertia, impulse));
	if (joint->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		struct picosystem_physics_body *const body_b = &world->bodies[joint->body_b_index];
		apply_body_angle_delta(body_b, -fixed_multiply(body_b->inverse_inertia, impulse));
	}
}

static bool apply_revolute_joint_limit_position_correction(
	struct picosystem_physics_world *world,
	const struct picosystem_physics_revolute_joint *joint)
{
	if (joint->limit_enabled == 0U) {
		return false;
	}
	++world->last_work.joint_limit_position_correction_visit_count;

	picosystem_physics_fixed_t error = revolute_joint_limit_error(world, joint);
	if (fixed_absolute(error) <= PHYSICS_JOINT_ANGULAR_SLOP) {
		return false;
	}
	error += (error > 0) ? -PHYSICS_JOINT_ANGULAR_SLOP : PHYSICS_JOINT_ANGULAR_SLOP;
	error = fixed_clamp(error, -PHYSICS_JOINT_MAX_ANGULAR_CORRECTION,
			    PHYSICS_JOINT_MAX_ANGULAR_CORRECTION);
	const picosystem_physics_fixed_t correction = -error;
	const picosystem_physics_fixed_t impulse =
		fixed_multiply(correction, joint->angular_effective_mass);
	apply_revolute_joint_angular_position_impulse(world, joint, impulse);
	if (impulse != 0) {
		++world->last_work.joint_limit_position_correction_changed_count;
	}
	return impulse != 0;
}

static bool apply_revolute_joint_position_pass(struct picosystem_physics_world *world, bool reverse)
{
	bool correction_changed = false;
	for (uint16_t visit = 0U; visit < world->revolute_joint_count; ++visit) {
		const uint16_t index =
			reverse ? (uint16_t)(world->revolute_joint_count - visit - 1U) : visit;
		const bool anchor_changed = apply_revolute_joint_position_correction(
			world, &world->revolute_joints[index]);
		(void)apply_revolute_joint_limit_position_correction(
			world, &world->revolute_joints[index]);
		correction_changed |= anchor_changed;
		++world->last_work.joint_position_correction_visit_count;
	}
	return correction_changed;
}

static bool revolute_joint_positions_within_target(const struct picosystem_physics_world *world)
{
	const uint64_t target_squared = (uint64_t)((int64_t)PHYSICS_REVOLUTE_POSITION_TARGET *
						   PHYSICS_REVOLUTE_POSITION_TARGET);
	for (uint16_t index = 0U; index < world->revolute_joint_count; ++index) {
		struct picosystem_physics_vector anchor_a;
		struct picosystem_physics_vector anchor_b;
		revolute_joint_anchors(world, &world->revolute_joints[index], &anchor_a, &anchor_b);
		const struct picosystem_physics_vector error =
			vector_subtract(&anchor_b, &anchor_a);
		if (vector_length_squared_raw(&error) > target_squared) {
			return false;
		}
	}
	return true;
}

static void prepare_revolute_joint(struct picosystem_physics_world *world,
				   struct picosystem_physics_revolute_joint *joint)
{
	revolute_joint_anchors(world, joint, &joint->world_anchor_a, &joint->world_anchor_b);
	struct physics_symmetric_matrix effective_mass;
	joint->effective_mass_valid = revolute_joint_effective_mass(
		world, joint, &joint->world_anchor_a, &joint->world_anchor_b, &effective_mass);
	joint->effective_mass_xx = effective_mass.xx;
	joint->effective_mass_xy = effective_mass.xy;
	joint->effective_mass_yy = effective_mass.yy;
	joint->accumulated_impulse = (struct picosystem_physics_vector){0};
	joint->accumulated_motor_impulse = 0;
	joint->accumulated_limit_impulse = 0;
	joint->limit_state = REVOLUTE_LIMIT_INACTIVE;
	if (joint->motor_enabled != 0U) {
		++world->last_work.revolute_motor_count;
	}
	if (joint->limit_enabled == 0U) {
		return;
	}
	++world->last_work.revolute_limit_count;
	const picosystem_physics_fixed_t angle =
		revolute_joint_relative_angle_radians(world, joint);
	if (joint->lower_angle_radians == joint->upper_angle_radians) {
		joint->limit_state = REVOLUTE_LIMIT_EQUAL;
	} else if (angle <= (joint->lower_angle_radians + PHYSICS_JOINT_ANGULAR_SLOP)) {
		joint->limit_state = REVOLUTE_LIMIT_LOWER;
	} else if (angle >= (joint->upper_angle_radians - PHYSICS_JOINT_ANGULAR_SLOP)) {
		joint->limit_state = REVOLUTE_LIMIT_UPPER;
	}
}

static struct picosystem_physics_vector
revolute_joint_relative_velocity(const struct picosystem_physics_world *world,
				 const struct picosystem_physics_revolute_joint *joint)
{
	const struct picosystem_physics_vector velocity_a =
		body_velocity_at_point(&world->bodies[joint->body_a_index], &joint->world_anchor_a);
	if (joint->body_b_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		return vector_negate(&velocity_a);
	}
	const struct picosystem_physics_vector velocity_b =
		body_velocity_at_point(&world->bodies[joint->body_b_index], &joint->world_anchor_b);
	return vector_subtract(&velocity_b, &velocity_a);
}

static picosystem_physics_fixed_t
revolute_joint_relative_angular_velocity(const struct picosystem_physics_world *world,
					 const struct picosystem_physics_revolute_joint *joint)
{
	const picosystem_physics_fixed_t body_b_velocity =
		(joint->body_b_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID)
			? 0
			: world->bodies[joint->body_b_index].angular_velocity_per_tick;
	return fixed_difference_bounded(
		world->bodies[joint->body_a_index].angular_velocity_per_tick, body_b_velocity,
		PHYSICS_VELOCITY_LIMIT);
}

static void
apply_revolute_joint_angular_impulse(struct picosystem_physics_world *world,
				     const struct picosystem_physics_revolute_joint *joint,
				     picosystem_physics_fixed_t impulse)
{
	struct picosystem_physics_body *const body_a = &world->bodies[joint->body_a_index];
	body_a->angular_velocity_per_tick += fixed_multiply(body_a->inverse_inertia, impulse);
	if (joint->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		struct picosystem_physics_body *const body_b = &world->bodies[joint->body_b_index];
		body_b->angular_velocity_per_tick -=
			fixed_multiply(body_b->inverse_inertia, impulse);
	}
}

static bool solve_revolute_joint_motor(struct picosystem_physics_world *world,
				       struct picosystem_physics_revolute_joint *joint)
{
	if (joint->motor_enabled == 0U) {
		return false;
	}
	++world->last_work.joint_motor_solver_visit_count;

	const picosystem_physics_fixed_t relative =
		revolute_joint_relative_angular_velocity(world, joint);
	const picosystem_physics_fixed_t velocity_error = fixed_difference_bounded(
		joint->motor_speed_per_tick, relative, PHYSICS_VELOCITY_LIMIT);
	const picosystem_physics_fixed_t impulse_delta = fixed_clamp(
		fixed_multiply(velocity_error, joint->angular_effective_mass),
		-joint->maximum_motor_impulse_per_tick, joint->maximum_motor_impulse_per_tick);
	const picosystem_physics_fixed_t previous = joint->accumulated_motor_impulse;
	joint->accumulated_motor_impulse =
		fixed_clamp(previous + impulse_delta, -joint->maximum_motor_impulse_per_tick,
			    joint->maximum_motor_impulse_per_tick);
	const picosystem_physics_fixed_t applied = joint->accumulated_motor_impulse - previous;
	apply_revolute_joint_angular_impulse(world, joint, applied);
	if (applied != 0) {
		++world->last_work.joint_motor_solver_changed_count;
	}
	return applied != 0;
}

static bool solve_revolute_joint_limit(struct picosystem_physics_world *world,
				       struct picosystem_physics_revolute_joint *joint)
{
	if (joint->limit_state == REVOLUTE_LIMIT_INACTIVE) {
		return false;
	}
	++world->last_work.joint_limit_solver_visit_count;

	const picosystem_physics_fixed_t relative =
		revolute_joint_relative_angular_velocity(world, joint);
	const picosystem_physics_fixed_t velocity_error =
		fixed_difference_bounded(0, relative, PHYSICS_VELOCITY_LIMIT);
	const picosystem_physics_fixed_t impulse_delta =
		fixed_clamp(fixed_multiply(velocity_error, joint->angular_effective_mass),
			    -PHYSICS_JOINT_LIMIT_IMPULSE_LIMIT, PHYSICS_JOINT_LIMIT_IMPULSE_LIMIT);
	const picosystem_physics_fixed_t previous = joint->accumulated_limit_impulse;
	const picosystem_physics_fixed_t candidate = previous + impulse_delta;
	if (joint->limit_state == REVOLUTE_LIMIT_LOWER) {
		joint->accumulated_limit_impulse =
			fixed_clamp(candidate, 0, PHYSICS_JOINT_LIMIT_IMPULSE_LIMIT);
	} else if (joint->limit_state == REVOLUTE_LIMIT_UPPER) {
		joint->accumulated_limit_impulse =
			fixed_clamp(candidate, -PHYSICS_JOINT_LIMIT_IMPULSE_LIMIT, 0);
	} else {
		joint->accumulated_limit_impulse =
			fixed_clamp(candidate, -PHYSICS_JOINT_LIMIT_IMPULSE_LIMIT,
				    PHYSICS_JOINT_LIMIT_IMPULSE_LIMIT);
	}
	const picosystem_physics_fixed_t applied = joint->accumulated_limit_impulse - previous;
	apply_revolute_joint_angular_impulse(world, joint, applied);
	if (applied != 0) {
		++world->last_work.joint_limit_solver_changed_count;
	}
	return applied != 0;
}

static bool solve_revolute_joint_velocity(struct picosystem_physics_world *world,
					  struct picosystem_physics_revolute_joint *joint)
{
	bool changed = false;
	if (joint->effective_mass_valid != 0U) {
		const struct physics_symmetric_matrix effective_mass = {
			.xx = joint->effective_mass_xx,
			.xy = joint->effective_mass_xy,
			.yy = joint->effective_mass_yy,
		};
		const struct picosystem_physics_vector relative =
			revolute_joint_relative_velocity(world, joint);
		const struct picosystem_physics_vector negated_relative = vector_negate(&relative);
		const struct picosystem_physics_vector impulse =
			matrix_transform(&effective_mass, &negated_relative);
		joint->accumulated_impulse = vector_add(&joint->accumulated_impulse, &impulse);
		apply_body_vector_impulse(&world->bodies[joint->body_a_index],
					  &joint->world_anchor_a, &impulse, true);
		if (joint->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
			apply_body_vector_impulse(&world->bodies[joint->body_b_index],
						  &joint->world_anchor_b, &impulse, false);
		}
		changed = (impulse.x != 0) || (impulse.y != 0);
	}
	changed |= solve_revolute_joint_motor(world, joint);
	changed |= solve_revolute_joint_limit(world, joint);
	return changed;
}

static uint32_t fnv1a_u32(uint32_t hash, uint32_t value)
{
	for (uint32_t shift = 0U; shift < 32U; shift += 8U) {
		hash ^= (value >> shift) & UINT32_C(0xff);
		hash *= FNV1A_PRIME;
	}
	return hash;
}

int picosystem_physics_world_init(struct picosystem_physics_world *world,
				  picosystem_physics_fixed_t max_speed_per_tick)
{
	if (world == NULL) {
		return -EINVAL;
	}
	if ((max_speed_per_tick <= 0) || (max_speed_per_tick > PHYSICS_VELOCITY_LIMIT)) {
		return -ERANGE;
	}

	memset(world, 0, sizeof(*world));
	world->max_speed_per_tick = max_speed_per_tick;
	return 0;
}

static int body_slot_for_config(struct picosystem_physics_world *world, uint16_t id)
{
	if (world->body_count >= PICOSYSTEM_PHYSICS_MAX_BODIES) {
		return -ENOSPC;
	}
	for (uint16_t index = 0U; index < world->body_count; ++index) {
		if (world->bodies[index].id == id) {
			return -EEXIST;
		}
	}
	return world->body_count;
}

int picosystem_physics_world_add_circle(struct picosystem_physics_world *world,
					const struct picosystem_physics_circle_config *config)
{
	if ((world == NULL) || (config == NULL)) {
		return -EINVAL;
	}
	if (!world_is_valid(world) || !circle_config_is_valid(config, world)) {
		return -ERANGE;
	}
	const int slot = body_slot_for_config(world, config->id);
	if (slot < 0) {
		return slot;
	}

	world->bodies[slot] = (struct picosystem_physics_body){
		.center = config->center,
		.velocity_per_tick = config->velocity_per_tick,
		.radius = config->radius,
		.inverse_mass = config->inverse_mass,
		.inverse_inertia = circle_inverse_inertia(config->radius, config->inverse_mass),
		.restitution = config->restitution,
		.friction = config->friction,
		.angular_velocity_per_tick = config->angular_velocity_per_tick,
		.angle_turns = config->angle_turns,
		.id = config->id,
		.shape = PICOSYSTEM_PHYSICS_SHAPE_CIRCLE,
	};
	++world->body_count;
	return 0;
}

int picosystem_physics_world_add_box(struct picosystem_physics_world *world,
				     const struct picosystem_physics_box_config *config)
{
	if ((world == NULL) || (config == NULL)) {
		return -EINVAL;
	}
	if (!world_is_valid(world) || !box_config_is_valid(config, world)) {
		return -ERANGE;
	}
	const int slot = body_slot_for_config(world, config->id);
	if (slot < 0) {
		return slot;
	}

	world->bodies[slot] = (struct picosystem_physics_body){
		.center = config->center,
		.velocity_per_tick = config->velocity_per_tick,
		.half_extent = config->half_extent,
		.inverse_mass = config->inverse_mass,
		.inverse_inertia = box_inverse_inertia(&config->half_extent, config->inverse_mass),
		.restitution = config->restitution,
		.friction = config->friction,
		.angular_velocity_per_tick = config->angular_velocity_per_tick,
		.angle_turns = config->angle_turns,
		.id = config->id,
		.shape = PICOSYSTEM_PHYSICS_SHAPE_BOX,
	};
	++world->body_count;
	return 0;
}

int picosystem_physics_world_add_static_segment(
	struct picosystem_physics_world *world,
	const struct picosystem_physics_segment_config *config)
{
	if ((world == NULL) || (config == NULL)) {
		return -EINVAL;
	}
	if (!world_is_valid(world) || !segment_config_is_valid(config)) {
		return -ERANGE;
	}
	if (world->static_segment_count >= PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS) {
		return -ENOSPC;
	}
	for (uint16_t index = 0U; index < world->static_segment_count; ++index) {
		if (world->static_segments[index].id == config->id) {
			return -EEXIST;
		}
	}

	struct picosystem_physics_static_segment *const segment =
		&world->static_segments[world->static_segment_count];
	*segment = (struct picosystem_physics_static_segment){
		.start = config->start,
		.end = config->end,
		.restitution = config->restitution,
		.friction = config->friction,
		.id = config->id,
	};
	segment_normal_from_endpoints(&segment->start, &segment->end, &segment->normal);
	++world->static_segment_count;
	return 0;
}

int picosystem_physics_world_add_distance_joint(
	struct picosystem_physics_world *world,
	const struct picosystem_physics_distance_joint_config *config)
{
	if ((world == NULL) || (config == NULL)) {
		return -EINVAL;
	}
	if (!world_is_valid(world) || !distance_joint_config_is_valid(config)) {
		return -ERANGE;
	}
	if (world->distance_joint_count >= PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS) {
		return -ENOSPC;
	}
	for (uint16_t index = 0U; index < world->distance_joint_count; ++index) {
		if (world->distance_joints[index].id == config->id) {
			return -EEXIST;
		}
	}

	const int body_a_index = body_index_for_id(world, config->body_a_id);
	if (body_a_index < 0) {
		return body_a_index;
	}
	if (!body_local_anchor_is_valid(&world->bodies[body_a_index], &config->local_anchor_a)) {
		return -ERANGE;
	}
	int body_b_index = STATIC_BODY_INDEX;
	if (config->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		body_b_index = body_index_for_id(world, config->body_b_id);
		if (body_b_index < 0) {
			return body_b_index;
		}
		if (!body_local_anchor_is_valid(&world->bodies[body_b_index], &config->anchor_b)) {
			return -ERANGE;
		}
	}

	world->distance_joints[world->distance_joint_count] =
		(struct picosystem_physics_distance_joint){
			.local_anchor_a = config->local_anchor_a,
			.anchor_b = config->anchor_b,
			.target_distance = config->target_distance,
			.id = config->id,
			.body_a_id = config->body_a_id,
			.body_b_id = config->body_b_id,
			.body_a_index = (uint8_t)body_a_index,
			.body_b_index = (uint8_t)body_b_index,
		};
	++world->distance_joint_count;
	return 0;
}

int picosystem_physics_world_add_revolute_joint(
	struct picosystem_physics_world *world,
	const struct picosystem_physics_revolute_joint_config *config)
{
	if ((world == NULL) || (config == NULL)) {
		return -EINVAL;
	}
	if (!world_is_valid(world) || !revolute_joint_config_is_valid(config)) {
		return -ERANGE;
	}
	if (world->revolute_joint_count >= PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS) {
		return -ENOSPC;
	}
	for (uint16_t index = 0U; index < world->revolute_joint_count; ++index) {
		if (world->revolute_joints[index].id == config->id) {
			return -EEXIST;
		}
	}

	const int body_a_index = body_index_for_id(world, config->body_a_id);
	if (body_a_index < 0) {
		return body_a_index;
	}
	if (!body_local_anchor_is_valid(&world->bodies[body_a_index], &config->local_anchor_a)) {
		return -ERANGE;
	}
	int body_b_index = STATIC_BODY_INDEX;
	if (config->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		body_b_index = body_index_for_id(world, config->body_b_id);
		if (body_b_index < 0) {
			return body_b_index;
		}
		if (!body_local_anchor_is_valid(&world->bodies[body_b_index], &config->anchor_b)) {
			return -ERANGE;
		}
	}

	struct picosystem_physics_revolute_joint *const joint =
		&world->revolute_joints[world->revolute_joint_count];
	*joint = (struct picosystem_physics_revolute_joint){
		.local_anchor_a = config->local_anchor_a,
		.anchor_b = config->anchor_b,
		.motor_speed_per_tick = config->motor_speed_per_tick,
		.maximum_motor_impulse_per_tick = config->maximum_motor_impulse_per_tick,
		.lower_angle_radians = config->lower_angle_radians,
		.upper_angle_radians = config->upper_angle_radians,
		.id = config->id,
		.body_a_id = config->body_a_id,
		.body_b_id = config->body_b_id,
		.body_a_index = (uint8_t)body_a_index,
		.body_b_index = (uint8_t)body_b_index,
		.collide_connected = config->collide_connected,
		.motor_enabled = config->motor_enabled,
		.limit_enabled = config->limit_enabled,
	};
	joint->reference_angle_turns = revolute_joint_relative_angle_turns(world, joint);
	++world->revolute_joint_count;
	return 0;
}

static int physics_world_step(struct picosystem_physics_world *world,
			      const struct picosystem_physics_vector *global_acceleration_per_tick,
			      bool force_brute_force, const struct picosystem_physics_clock *clock,
			      struct picosystem_physics_step_profile *profile)
{
	if ((world == NULL) || (global_acceleration_per_tick == NULL)) {
		return -EINVAL;
	}
	if (((clock == NULL) != (profile == NULL)) || ((clock != NULL) && (clock->now == NULL))) {
		return -EINVAL;
	}

	if (profile != NULL) {
		memset(profile, 0, sizeof(*profile));
	}
	struct physics_step_profiler profiler = {
		.clock = clock,
		.profile = profile,
	};
	if (profiler_is_active(&profiler)) {
		profiler.total_start = profiler_now(&profiler);
	}
	if (!world_is_valid(world) ||
	    !vector_is_bounded(global_acceleration_per_tick, PHYSICS_ACCELERATION_LIMIT)) {
		return -ERANGE;
	}
	memset(&world->last_work, 0, sizeof(world->last_work));
	world->last_work.distance_joint_count = world->distance_joint_count;
	world->last_work.revolute_joint_count = world->revolute_joint_count;

	uint32_t section_start = profiler_section_begin(&profiler);
	for (uint16_t index = 0U; index < world->body_count; ++index) {
		struct picosystem_physics_body *const body = &world->bodies[index];
		body->velocity_per_tick.x += global_acceleration_per_tick->x;
		body->velocity_per_tick.y += global_acceleration_per_tick->y;
		clamp_body_speed(body, world->max_speed_per_tick);
		body->center.x += body->velocity_per_tick.x;
		body->center.y += body->velocity_per_tick.y;
		integrate_body_angle(body);
		clamp_body_position(body);
	}
	profiler_section_end(&profiler, PICOSYSTEM_PHYSICS_PROFILE_FORCE_AND_INTEGRATE,
			     section_start);

	int err = build_contacts(world, force_brute_force, &profiler);
	if (err != 0) {
		return err;
	}

	section_start = profiler_section_begin(&profiler);
	for (uint16_t index = 0U; index < world->contact_count; ++index) {
		apply_position_correction(world, &world->contacts[index]);
		++world->last_work.position_correction_visit_count;
	}
	for (uint16_t index = 0U; index < world->distance_joint_count; ++index) {
		(void)apply_distance_joint_position_correction(world,
							       &world->distance_joints[index]);
		++world->last_work.joint_position_correction_visit_count;
	}
	for (uint16_t index = 0U; index < world->revolute_joint_count; ++index) {
		struct picosystem_physics_revolute_joint *const joint =
			&world->revolute_joints[index];
		joint->angular_effective_mass =
			((joint->motor_enabled != 0U) || (joint->limit_enabled != 0U))
				? revolute_joint_angular_effective_mass(world, joint)
				: 0;
	}
	/* Alternate extra sweeps so storage order does not always favor the same chain end. */
	for (uint8_t iteration = 0U; iteration < PICOSYSTEM_PHYSICS_REVOLUTE_POSITION_ITERATIONS;
	     ++iteration) {
		const bool reverse = (iteration & 1U) != 0U;
		const bool correction_changed = apply_revolute_joint_position_pass(world, reverse);
		if (!correction_changed || revolute_joint_positions_within_target(world)) {
			break;
		}
	}
	profiler_section_end(&profiler, PICOSYSTEM_PHYSICS_PROFILE_POSITION_CORRECTION,
			     section_start);

	section_start = profiler_section_begin(&profiler);
	for (uint16_t index = 0U; index < world->distance_joint_count; ++index) {
		prepare_distance_joint(world, &world->distance_joints[index]);
	}
	for (uint16_t index = 0U; index < world->revolute_joint_count; ++index) {
		prepare_revolute_joint(world, &world->revolute_joints[index]);
	}
	world->last_solver_iteration_count = 0U;
	for (uint8_t iteration = 0U;
	     (iteration < PICOSYSTEM_PHYSICS_SOLVER_ITERATIONS) &&
	     ((world->contact_count > 0U) || (world->distance_joint_count > 0U) ||
	      (world->revolute_joint_count > 0U));
	     ++iteration) {
		bool impulse_changed = false;
		for (uint16_t index = 0U; index < world->contact_count; ++index) {
			const bool contact_changed =
				solve_contact_velocity(world, &world->contacts[index]);
			impulse_changed |= contact_changed;
			++world->last_work.solver_contact_visit_count;
			if (contact_changed) {
				++world->last_work.solver_changed_contact_count;
			}
		}
		for (uint16_t index = 0U; index < world->distance_joint_count; ++index) {
			const bool joint_changed = solve_distance_joint_velocity(
				world, &world->distance_joints[index]);
			impulse_changed |= joint_changed;
			++world->last_work.joint_solver_visit_count;
			if (joint_changed) {
				++world->last_work.joint_solver_changed_count;
			}
		}
		for (uint16_t index = 0U; index < world->revolute_joint_count; ++index) {
			const bool joint_changed = solve_revolute_joint_velocity(
				world, &world->revolute_joints[index]);
			impulse_changed |= joint_changed;
			++world->last_work.joint_solver_visit_count;
			if (joint_changed) {
				++world->last_work.joint_solver_changed_count;
			}
		}
		world->last_solver_iteration_count = iteration + 1U;
		++world->last_work.solver_iteration_count;
		if (!impulse_changed) {
			break;
		}
	}
	profiler_section_end(&profiler, PICOSYSTEM_PHYSICS_PROFILE_VELOCITY_SOLVER, section_start);

	section_start = profiler_section_begin(&profiler);
	for (uint16_t index = 0U; index < world->body_count; ++index) {
		clamp_body_position(&world->bodies[index]);
		clamp_body_speed(&world->bodies[index], world->max_speed_per_tick);
		clamp_body_angular_speed(&world->bodies[index]);
	}
	profiler_section_end(&profiler, PICOSYSTEM_PHYSICS_PROFILE_FINAL_CLAMP, section_start);
	if (profile != NULL) {
		profile->work = world->last_work;
	}
	profiler_finish(&profiler);
	return 0;
}

int picosystem_physics_world_step(
	struct picosystem_physics_world *world,
	const struct picosystem_physics_vector *global_acceleration_per_tick)
{
	return physics_world_step(world, global_acceleration_per_tick, false, NULL, NULL);
}

int picosystem_physics_world_step_reference(
	struct picosystem_physics_world *world,
	const struct picosystem_physics_vector *global_acceleration_per_tick)
{
	return physics_world_step(world, global_acceleration_per_tick, true, NULL, NULL);
}

int picosystem_physics_world_step_profiled(
	struct picosystem_physics_world *world,
	const struct picosystem_physics_vector *global_acceleration_per_tick,
	enum picosystem_physics_step_mode mode, const struct picosystem_physics_clock *clock,
	struct picosystem_physics_step_profile *profile)
{
	if ((mode != PICOSYSTEM_PHYSICS_STEP_MODE_GRID) &&
	    (mode != PICOSYSTEM_PHYSICS_STEP_MODE_REFERENCE)) {
		return -EINVAL;
	}

	return physics_world_step(world, global_acceleration_per_tick,
				  mode == PICOSYSTEM_PHYSICS_STEP_MODE_REFERENCE, clock, profile);
}

const struct picosystem_physics_body *
picosystem_physics_world_body_at(const struct picosystem_physics_world *world, size_t index)
{
	if ((world == NULL) || (world->body_count > PICOSYSTEM_PHYSICS_MAX_BODIES) ||
	    (index >= world->body_count)) {
		return NULL;
	}
	return &world->bodies[index];
}

int picosystem_physics_world_distance_joint_endpoints(
	const struct picosystem_physics_world *world, size_t index,
	struct picosystem_physics_vector *world_anchor_a,
	struct picosystem_physics_vector *world_anchor_b)
{
	if ((world == NULL) || (world_anchor_a == NULL) || (world_anchor_b == NULL)) {
		return -EINVAL;
	}
	if ((world->body_count > PICOSYSTEM_PHYSICS_MAX_BODIES) ||
	    (world->distance_joint_count > PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS)) {
		return -ERANGE;
	}
	if (index >= world->distance_joint_count) {
		return -ENOENT;
	}
	const struct picosystem_physics_distance_joint *const joint =
		&world->distance_joints[index];
	if (!distance_joint_is_valid(joint, world)) {
		return -ERANGE;
	}

	distance_joint_endpoints(world, joint, world_anchor_a, world_anchor_b);
	return 0;
}

int picosystem_physics_world_revolute_joint_anchors(
	const struct picosystem_physics_world *world, size_t index,
	struct picosystem_physics_vector *world_anchor_a,
	struct picosystem_physics_vector *world_anchor_b)
{
	if ((world == NULL) || (world_anchor_a == NULL) || (world_anchor_b == NULL)) {
		return -EINVAL;
	}
	if ((world->body_count > PICOSYSTEM_PHYSICS_MAX_BODIES) ||
	    (world->revolute_joint_count > PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS)) {
		return -ERANGE;
	}
	if (index >= world->revolute_joint_count) {
		return -ENOENT;
	}
	const struct picosystem_physics_revolute_joint *const joint =
		&world->revolute_joints[index];
	if (!revolute_joint_is_valid(joint, world)) {
		return -ERANGE;
	}

	revolute_joint_anchors(world, joint, world_anchor_a, world_anchor_b);
	return 0;
}

int picosystem_physics_world_revolute_joint_angle(
	const struct picosystem_physics_world *world, size_t index,
	picosystem_physics_fixed_t *relative_angle_radians)
{
	if ((world == NULL) || (relative_angle_radians == NULL)) {
		return -EINVAL;
	}
	if ((world->body_count > PICOSYSTEM_PHYSICS_MAX_BODIES) ||
	    (world->revolute_joint_count > PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS)) {
		return -ERANGE;
	}
	if (index >= world->revolute_joint_count) {
		return -ENOENT;
	}
	const struct picosystem_physics_revolute_joint *const joint =
		&world->revolute_joints[index];
	if (!revolute_joint_is_valid(joint, world)) {
		return -ERANGE;
	}

	*relative_angle_radians = revolute_joint_relative_angle_radians(world, joint);
	return 0;
}

int picosystem_physics_body_box_vertices(
	const struct picosystem_physics_body *body,
	struct picosystem_physics_vector vertices[PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT])
{
	if ((body == NULL) || (vertices == NULL)) {
		return -EINVAL;
	}
	if (body->shape != PICOSYSTEM_PHYSICS_SHAPE_BOX) {
		return -ENOTSUP;
	}
	if ((body->half_extent.x <= 0) || (body->half_extent.y <= 0)) {
		return -ERANGE;
	}

	struct box_geometry geometry;
	box_geometry_from_body(body, &geometry);
	box_vertices_from_geometry(body, &geometry, vertices);
	return 0;
}

uint32_t picosystem_physics_world_hash(const struct picosystem_physics_world *world)
{
	if ((world == NULL) || (world->body_count > PICOSYSTEM_PHYSICS_MAX_BODIES) ||
	    (world->static_segment_count > PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS) ||
	    (world->distance_joint_count > PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS) ||
	    (world->revolute_joint_count > PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS)) {
		return 0U;
	}

	uint32_t hash = fnv1a_u32(FNV1A_OFFSET_BASIS, PHYSICS_HASH_VERSION);
	hash = fnv1a_u32(hash, (uint32_t)world->max_speed_per_tick);
	hash = fnv1a_u32(hash, world->body_count);
	hash = fnv1a_u32(hash, world->static_segment_count);
	hash = fnv1a_u32(hash, world->distance_joint_count);
	hash = fnv1a_u32(hash, world->revolute_joint_count);
	for (uint16_t index = 0U; index < world->body_count; ++index) {
		const struct picosystem_physics_body *const body = &world->bodies[index];
		hash = fnv1a_u32(hash, body->id);
		hash = fnv1a_u32(hash, body->shape);
		hash = fnv1a_u32(hash, (uint32_t)body->center.x);
		hash = fnv1a_u32(hash, (uint32_t)body->center.y);
		hash = fnv1a_u32(hash, (uint32_t)body->velocity_per_tick.x);
		hash = fnv1a_u32(hash, (uint32_t)body->velocity_per_tick.y);
		hash = fnv1a_u32(hash, (uint32_t)body->half_extent.x);
		hash = fnv1a_u32(hash, (uint32_t)body->half_extent.y);
		hash = fnv1a_u32(hash, (uint32_t)body->radius);
		hash = fnv1a_u32(hash, (uint32_t)body->inverse_mass);
		hash = fnv1a_u32(hash, (uint32_t)body->inverse_inertia);
		hash = fnv1a_u32(hash, (uint32_t)body->restitution);
		hash = fnv1a_u32(hash, (uint32_t)body->friction);
		hash = fnv1a_u32(hash, (uint32_t)body->angular_velocity_per_tick);
		hash = fnv1a_u32(hash, body->angle_turns);
	}
	for (uint16_t index = 0U; index < world->static_segment_count; ++index) {
		const struct picosystem_physics_static_segment *const segment =
			&world->static_segments[index];
		hash = fnv1a_u32(hash, segment->id);
		hash = fnv1a_u32(hash, (uint32_t)segment->start.x);
		hash = fnv1a_u32(hash, (uint32_t)segment->start.y);
		hash = fnv1a_u32(hash, (uint32_t)segment->end.x);
		hash = fnv1a_u32(hash, (uint32_t)segment->end.y);
		hash = fnv1a_u32(hash, (uint32_t)segment->normal.x);
		hash = fnv1a_u32(hash, (uint32_t)segment->normal.y);
		hash = fnv1a_u32(hash, (uint32_t)segment->restitution);
		hash = fnv1a_u32(hash, (uint32_t)segment->friction);
	}
	for (uint16_t index = 0U; index < world->distance_joint_count; ++index) {
		const struct picosystem_physics_distance_joint *const joint =
			&world->distance_joints[index];
		hash = fnv1a_u32(hash, joint->id);
		hash = fnv1a_u32(hash, joint->body_a_id);
		hash = fnv1a_u32(hash, joint->body_b_id);
		hash = fnv1a_u32(hash, joint->body_a_index);
		hash = fnv1a_u32(hash, joint->body_b_index);
		hash = fnv1a_u32(hash, (uint32_t)joint->local_anchor_a.x);
		hash = fnv1a_u32(hash, (uint32_t)joint->local_anchor_a.y);
		hash = fnv1a_u32(hash, (uint32_t)joint->anchor_b.x);
		hash = fnv1a_u32(hash, (uint32_t)joint->anchor_b.y);
		hash = fnv1a_u32(hash, (uint32_t)joint->target_distance);
	}
	for (uint16_t index = 0U; index < world->revolute_joint_count; ++index) {
		const struct picosystem_physics_revolute_joint *const joint =
			&world->revolute_joints[index];
		hash = fnv1a_u32(hash, joint->id);
		hash = fnv1a_u32(hash, joint->body_a_id);
		hash = fnv1a_u32(hash, joint->body_b_id);
		hash = fnv1a_u32(hash, joint->body_a_index);
		hash = fnv1a_u32(hash, joint->body_b_index);
		hash = fnv1a_u32(hash, joint->collide_connected);
		hash = fnv1a_u32(hash, joint->motor_enabled);
		hash = fnv1a_u32(hash, joint->limit_enabled);
		hash = fnv1a_u32(hash, (uint32_t)joint->local_anchor_a.x);
		hash = fnv1a_u32(hash, (uint32_t)joint->local_anchor_a.y);
		hash = fnv1a_u32(hash, (uint32_t)joint->anchor_b.x);
		hash = fnv1a_u32(hash, (uint32_t)joint->anchor_b.y);
		hash = fnv1a_u32(hash, (uint32_t)joint->motor_speed_per_tick);
		hash = fnv1a_u32(hash, (uint32_t)joint->maximum_motor_impulse_per_tick);
		hash = fnv1a_u32(hash, (uint32_t)joint->lower_angle_radians);
		hash = fnv1a_u32(hash, (uint32_t)joint->upper_angle_radians);
		hash = fnv1a_u32(hash, joint->reference_angle_turns);
	}
	return hash;
}
