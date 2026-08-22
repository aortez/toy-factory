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

#if defined(CONFIG_TOY_FACTORY_CORE1_FULL_FRAME_RENDERER)
/* Keep the inlined physics step off XIP while core 1 rasterizes from SRAM. */
#define PICOSYSTEM_PHYSICS_RAMFUNC __attribute__((section(".ramfunc")))
#else
#define PICOSYSTEM_PHYSICS_RAMFUNC
#endif
#define PICOSYSTEM_PHYSICS_NOINLINE __attribute__((noinline))

#define PHYSICS_POSITION_LIMIT                    PICOSYSTEM_PHYSICS_FIXED_FROM_INT(1024)
#define PHYSICS_VELOCITY_LIMIT                    PICOSYSTEM_PHYSICS_FIXED_FROM_INT(8)
#define PHYSICS_ACCELERATION_LIMIT                PICOSYSTEM_PHYSICS_FIXED_ONE
#define PHYSICS_RADIUS_MINIMUM                    PICOSYSTEM_PHYSICS_FIXED_ONE
#define PHYSICS_RADIUS_LIMIT                      PICOSYSTEM_PHYSICS_FIXED_FROM_INT(128)
#define PHYSICS_HALF_EXTENT_MINIMUM               PICOSYSTEM_PHYSICS_FIXED_ONE
#define PHYSICS_HALF_EXTENT_LIMIT                 PICOSYSTEM_PHYSICS_FIXED_FROM_INT(64)
#define PHYSICS_ROPE_SEGMENT_LENGTH_MINIMUM       PICOSYSTEM_PHYSICS_FIXED_ONE
#define PHYSICS_ROPE_SEGMENT_LENGTH_LIMIT         PICOSYSTEM_PHYSICS_FIXED_FROM_INT(64)
#define PHYSICS_ROPE_COLLISION_RADIUS_MINIMUM     PICOSYSTEM_PHYSICS_FIXED_ONE
#define PHYSICS_ROPE_COLLISION_RADIUS_LIMIT       PICOSYSTEM_PHYSICS_FIXED_FROM_INT(8)
/* One 60 Hz damping step equals two former 120 Hz steps: (255 / 256)^2. */
#define PHYSICS_ROPE_VELOCITY_DAMPING             PICOSYSTEM_PHYSICS_FIXED_RATIO(65025, 65536)
#define PHYSICS_ROPE_MAX_CORRECTION               PICOSYSTEM_PHYSICS_FIXED_FROM_INT(8)
#define PHYSICS_ROPE_POSITION_LIMIT               (PHYSICS_POSITION_LIMIT + PHYSICS_JOINT_LOCAL_ANCHOR_LIMIT)
#define PHYSICS_JOINT_LOCAL_ANCHOR_LIMIT          PICOSYSTEM_PHYSICS_FIXED_FROM_INT(128)
#define PHYSICS_JOINT_DISTANCE_MINIMUM            PICOSYSTEM_PHYSICS_FIXED_ONE
#define PHYSICS_JOINT_DISTANCE_LIMIT              PICOSYSTEM_PHYSICS_FIXED_FROM_INT(256)
#define PHYSICS_JOINT_REFERENCE_TRANSLATION_LIMIT (PHYSICS_POSITION_LIMIT * 3)
#define PHYSICS_JOINT_AXIS_COMPONENT_LIMIT        PICOSYSTEM_PHYSICS_FIXED_ONE
#define PHYSICS_JOINT_AXIS_MINIMUM_LENGTH         (PICOSYSTEM_PHYSICS_FIXED_ONE / 16)
#define PHYSICS_INVERSE_MASS_MINIMUM              (PICOSYSTEM_PHYSICS_FIXED_ONE / 16)
#define PHYSICS_INVERSE_MASS_MAXIMUM              (PICOSYSTEM_PHYSICS_FIXED_ONE * 4)
#define PHYSICS_INVERSE_INERTIA_MAXIMUM           (PICOSYSTEM_PHYSICS_FIXED_ONE * 8)
#define PHYSICS_ANGULAR_VELOCITY_LIMIT            (PICOSYSTEM_PHYSICS_FIXED_ONE / 2)
#define PHYSICS_TAU_FIXED                         INT32_C(411775)
#define PHYSICS_PI_FIXED                          (PHYSICS_TAU_FIXED / 2)
#define PHYSICS_JOINT_MOTOR_IMPULSE_LIMIT         PICOSYSTEM_PHYSICS_FIXED_FROM_INT(8)
#define PHYSICS_SPRING_FREQUENCY_MINIMUM          (PICOSYSTEM_PHYSICS_FIXED_ONE / 64)
#define PHYSICS_SPRING_FREQUENCY_LIMIT            (PICOSYSTEM_PHYSICS_FIXED_ONE / 2)
#define PHYSICS_SPRING_DAMPING_RATIO_LIMIT        (PICOSYSTEM_PHYSICS_FIXED_ONE * 2)
#define PHYSICS_SPRING_IMPULSE_LIMIT              PICOSYSTEM_PHYSICS_FIXED_FROM_INT(8)
#define PHYSICS_JOINT_LIMIT_IMPULSE_LIMIT         PICOSYSTEM_PHYSICS_FIXED_FROM_INT(256)
#define PHYSICS_JOINT_ANGULAR_SLOP                (PHYSICS_TAU_FIXED / 360)
#define PHYSICS_JOINT_MAX_ANGULAR_CORRECTION      (PHYSICS_TAU_FIXED / 24)
#define PHYSICS_POSITION_SLOP                     (PICOSYSTEM_PHYSICS_FIXED_ONE / 256)
#define PHYSICS_JOINT_POSITION_SLOP               (PICOSYSTEM_PHYSICS_FIXED_ONE / 128)
#define PHYSICS_JOINT_CORRECTION_SCALE            (PICOSYSTEM_PHYSICS_FIXED_ONE / 2)
#define PHYSICS_JOINT_MAX_CORRECTION              PICOSYSTEM_PHYSICS_FIXED_FROM_INT(2)
#define PHYSICS_REVOLUTE_POSITION_TARGET          PICOSYSTEM_PHYSICS_FIXED_ONE
#define PHYSICS_PRISMATIC_POSITION_TARGET         PICOSYSTEM_PHYSICS_FIXED_ONE
/* A 1/8 cutoff still sustains resting bounce under the larger 60 Hz gravity step. */
#define PHYSICS_BOUNCE_THRESHOLD                  PICOSYSTEM_PHYSICS_FIXED_RATIO(3, 16)
#define PHYSICS_SLEEP_LINEAR_VELOCITY_THRESHOLD   (PICOSYSTEM_PHYSICS_FIXED_ONE / 32)
#define PHYSICS_SLEEP_ANGULAR_VELOCITY_THRESHOLD  (PICOSYSTEM_PHYSICS_FIXED_ONE / 256)
#define PHYSICS_HASH_VERSION                      UINT32_C(16)
#define FNV1A_OFFSET_BASIS                        UINT32_C(2166136261)
#define FNV1A_PRIME                               UINT32_C(16777619)
#define STATIC_BODY_INDEX                         UINT8_MAX
#define STATIC_SEGMENT_INDEX                      UINT8_MAX
#define TRIG_QUARTER_SAMPLE_SHIFT                 24U
#define TRIG_QUARTER_SAMPLE_COUNT                 64U
#define TRIG_QUARTER_PHASE_MASK                   UINT32_C(0x3fffffff)
#define PHYSICS_MAX_SOLVER_VELOCITY_REVISIONS_PER_BODY                                             \
	(PICOSYSTEM_PHYSICS_SOLVER_ITERATIONS *                                                    \
	 ((2U * PICOSYSTEM_PHYSICS_MAX_CONTACTS) + PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS +        \
	  (3U * PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS) +                                          \
	  (4U * PICOSYSTEM_PHYSICS_MAX_PRISMATIC_JOINTS)))
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
_Static_assert(PICOSYSTEM_PHYSICS_MAX_PRISMATIC_JOINTS <= UINT8_MAX,
	       "prismatic-joint indices must fit in one byte");
_Static_assert(PICOSYSTEM_PHYSICS_MAX_BOX_SENSORS <= UINT8_MAX,
	       "box-sensor indices must fit in one byte");
_Static_assert(PICOSYSTEM_PHYSICS_MAX_BOX_SENSORS <= 8U, "sensor occupancy must fit in uint8_t");
_Static_assert(PICOSYSTEM_PHYSICS_MAX_ROPES <= UINT8_MAX, "rope indices must fit in one byte");
_Static_assert(PICOSYSTEM_PHYSICS_MAX_ROPE_PARTICLES <= UINT8_MAX,
	       "rope particle counts must fit in one byte");
_Static_assert(PICOSYSTEM_PHYSICS_ROPE_SOLVER_ITERATIONS <= UINT8_MAX,
	       "rope solver iterations must fit in one byte");
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
_Static_assert(PICOSYSTEM_PHYSICS_MAX_CONTACT_EVENTS <= UINT16_MAX,
	       "contact-event count must fit in the public world field");
_Static_assert(PICOSYSTEM_PHYSICS_SOLVER_ITERATIONS <= UINT8_MAX,
	       "solver iteration diagnostics must fit in uint8_t");
_Static_assert(PHYSICS_MAX_SOLVER_VELOCITY_REVISIONS_PER_BODY <= UINT16_MAX,
	       "per-step solver velocity revisions must fit in uint16_t");
_Static_assert(PICOSYSTEM_PHYSICS_REVOLUTE_POSITION_ITERATIONS <= UINT8_MAX,
	       "position iterations must fit in uint8_t");
_Static_assert(PICOSYSTEM_PHYSICS_PRISMATIC_POSITION_ITERATIONS <= UINT8_MAX,
	       "prismatic position iterations must fit in uint8_t");
_Static_assert(PICOSYSTEM_PHYSICS_SLEEP_QUIET_TICKS <= UINT16_MAX,
	       "sleep quiet ticks must fit in uint16_t");

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
	uint8_t box_sensor_masks[PICOSYSTEM_PHYSICS_MAX_BODIES];
};

struct physics_contact_pair_masks {
	uint16_t body_masks[PICOSYSTEM_PHYSICS_MAX_BODIES];
	uint8_t static_segment_masks[PICOSYSTEM_PHYSICS_MAX_BODIES];
	uint8_t box_sensor_masks[PICOSYSTEM_PHYSICS_MAX_BODIES];
};

struct physics_sleep_graph {
	uint16_t neighbor_masks[PICOSYSTEM_PHYSICS_MAX_BODIES];
	uint16_t powered_body_mask;
};

struct contact_point_candidate {
	struct picosystem_physics_vector point;
	picosystem_physics_fixed_t penetration;
};

struct segment_closest_result {
	struct picosystem_physics_vector point_a;
	struct picosystem_physics_vector point_b;
	uint64_t distance_squared_raw;
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

enum prismatic_limit_state {
	PRISMATIC_LIMIT_INACTIVE,
	PRISMATIC_LIMIT_LOWER,
	PRISMATIC_LIMIT_UPPER,
	PRISMATIC_LIMIT_EQUAL,
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

static struct picosystem_physics_vector
body_local_vector_to_world(const struct picosystem_physics_body *body,
			   const struct picosystem_physics_vector *local_vector)
{
	struct box_geometry geometry;
	box_geometry_from_body(body, &geometry);
	const struct picosystem_physics_vector along_x =
		vector_scale(&geometry.axis_x, local_vector->x);
	const struct picosystem_physics_vector along_y =
		vector_scale(&geometry.axis_y, local_vector->y);
	return vector_add(&along_x, &along_y);
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

static void capsule_centerline_from_geometry(const struct picosystem_physics_body *body,
					     const struct box_geometry *geometry,
					     struct picosystem_physics_vector *start,
					     struct picosystem_physics_vector *end)
{
	const struct picosystem_physics_vector offset =
		vector_scale(&geometry->axis_x, body->half_extent.x);
	*start = vector_subtract(&body->center, &offset);
	*end = vector_add(&body->center, &offset);
}

static struct picosystem_physics_vector
closest_point_on_segment_endpoints(const struct picosystem_physics_vector *point,
				   const struct picosystem_physics_vector *start,
				   const struct picosystem_physics_vector *end)
{
	const struct picosystem_physics_vector extent = vector_subtract(end, start);
	const struct picosystem_physics_vector from_start = vector_subtract(point, start);
	const int64_t projection_raw =
		((int64_t)from_start.x * extent.x) + ((int64_t)from_start.y * extent.y);
	const int64_t length_squared_raw = (int64_t)vector_length_squared_raw(&extent);
	if (projection_raw <= 0) {
		return *start;
	}
	if (projection_raw >= length_squared_raw) {
		return *end;
	}

	const int64_t reduced_projection = projection_raw / PICOSYSTEM_PHYSICS_FIXED_ONE;
	const int64_t reduced_length = length_squared_raw / PICOSYSTEM_PHYSICS_FIXED_ONE;
	const picosystem_physics_fixed_t fraction =
		(picosystem_physics_fixed_t)((reduced_projection * PICOSYSTEM_PHYSICS_FIXED_ONE) /
					     reduced_length);
	const struct picosystem_physics_vector offset = vector_scale(&extent, fraction);
	return vector_add(start, &offset);
}

static int64_t vector_cross_raw(const struct picosystem_physics_vector *left,
				const struct picosystem_physics_vector *right)
{
	return ((int64_t)left->x * right->y) - ((int64_t)left->y * right->x);
}

static bool ratio_is_in_closed_unit_interval(int64_t numerator, int64_t denominator)
{
	return (denominator > 0) ? ((numerator >= 0) && (numerator <= denominator))
				 : ((numerator <= 0) && (numerator >= denominator));
}

static picosystem_physics_fixed_t fixed_fraction_from_ratio(int64_t numerator, int64_t denominator)
{
	if (denominator < 0) {
		numerator = -numerator;
		denominator = -denominator;
	}
	if (numerator <= 0) {
		return 0;
	}
	if (numerator >= denominator) {
		return PICOSYSTEM_PHYSICS_FIXED_ONE;
	}

	uint64_t remainder = (uint64_t)numerator;
	const uint64_t divisor = (uint64_t)denominator;
	uint32_t fraction = 0U;
	for (uint32_t bit = 0U; bit < PICOSYSTEM_PHYSICS_FIXED_FRACTION_BITS; ++bit) {
		remainder <<= 1U;
		fraction <<= 1U;
		if (remainder >= divisor) {
			remainder -= divisor;
			fraction |= 1U;
		}
	}
	return (picosystem_physics_fixed_t)fraction;
}

static bool proper_segment_intersection(const struct picosystem_physics_vector *start_a,
					const struct picosystem_physics_vector *end_a,
					const struct picosystem_physics_vector *start_b,
					const struct picosystem_physics_vector *end_b,
					struct picosystem_physics_vector *intersection)
{
	const struct picosystem_physics_vector extent_a = vector_subtract(end_a, start_a);
	const struct picosystem_physics_vector extent_b = vector_subtract(end_b, start_b);
	const struct picosystem_physics_vector a_to_b = vector_subtract(start_b, start_a);
	const int64_t denominator = vector_cross_raw(&extent_a, &extent_b);
	if (denominator == 0) {
		return false;
	}

	const int64_t numerator_a = vector_cross_raw(&a_to_b, &extent_b);
	const int64_t numerator_b = vector_cross_raw(&a_to_b, &extent_a);
	if (!ratio_is_in_closed_unit_interval(numerator_a, denominator) ||
	    !ratio_is_in_closed_unit_interval(numerator_b, denominator)) {
		return false;
	}

	const picosystem_physics_fixed_t fraction =
		fixed_fraction_from_ratio(numerator_a, denominator);
	const struct picosystem_physics_vector offset = vector_scale(&extent_a, fraction);
	*intersection = vector_add(start_a, &offset);
	return true;
}

static void update_segment_closest(struct segment_closest_result *result,
				   const struct picosystem_physics_vector *point_a,
				   const struct picosystem_physics_vector *point_b)
{
	const struct picosystem_physics_vector delta = vector_subtract(point_b, point_a);
	const uint64_t distance_squared = vector_length_squared_raw(&delta);
	if (distance_squared < result->distance_squared_raw) {
		result->point_a = *point_a;
		result->point_b = *point_b;
		result->distance_squared_raw = distance_squared;
	}
}

static struct segment_closest_result
closest_points_between_segments(const struct picosystem_physics_vector *start_a,
				const struct picosystem_physics_vector *end_a,
				const struct picosystem_physics_vector *start_b,
				const struct picosystem_physics_vector *end_b)
{
	struct segment_closest_result result = {
		.distance_squared_raw = UINT64_MAX,
	};
	struct picosystem_physics_vector closest =
		closest_point_on_segment_endpoints(start_a, start_b, end_b);
	update_segment_closest(&result, start_a, &closest);
	closest = closest_point_on_segment_endpoints(end_a, start_b, end_b);
	update_segment_closest(&result, end_a, &closest);
	closest = closest_point_on_segment_endpoints(start_b, start_a, end_a);
	update_segment_closest(&result, &closest, start_b);
	closest = closest_point_on_segment_endpoints(end_b, start_a, end_a);
	update_segment_closest(&result, &closest, end_b);

	struct picosystem_physics_vector intersection;
	if (proper_segment_intersection(start_a, end_a, start_b, end_b, &intersection)) {
		result.point_a = intersection;
		result.point_b = intersection;
		result.distance_squared_raw = 0U;
	}
	return result;
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

static bool capsule_config_is_valid(const struct picosystem_physics_capsule_config *config,
				    const struct picosystem_physics_world *world)
{
	return (config != NULL) &&
	       common_body_config_is_valid(&config->center, &config->velocity_per_tick,
					   config->inverse_mass, config->restitution,
					   config->friction, config->angular_velocity_per_tick,
					   config->id, world) &&
	       (config->half_length >= PHYSICS_HALF_EXTENT_MINIMUM) &&
	       (config->half_length <= PHYSICS_HALF_EXTENT_LIMIT) &&
	       (config->radius >= PHYSICS_RADIUS_MINIMUM) &&
	       (config->radius <= PHYSICS_HALF_EXTENT_LIMIT) &&
	       (config->half_length <= (PHYSICS_RADIUS_LIMIT - config->radius));
}

static bool segment_config_is_valid(const struct picosystem_physics_segment_config *config)
{
	if ((config == NULL) || (config->id == 0U) ||
	    !vector_is_bounded(&config->start, PHYSICS_POSITION_LIMIT) ||
	    !vector_is_bounded(&config->end, PHYSICS_POSITION_LIMIT) ||
	    !material_is_valid(config->restitution) || !material_is_valid(config->friction) ||
	    !fixed_is_bounded(config->surface_speed_per_tick, PHYSICS_VELOCITY_LIMIT)) {
		return false;
	}

	const struct picosystem_physics_vector extent =
		vector_subtract(&config->end, &config->start);
	const uint64_t minimum_length_squared =
		(uint64_t)PICOSYSTEM_PHYSICS_FIXED_ONE * PICOSYSTEM_PHYSICS_FIXED_ONE;
	return vector_length_squared_raw(&extent) >= minimum_length_squared;
}

static bool box_sensor_config_is_valid(const struct picosystem_physics_box_sensor_config *config)
{
	return (config != NULL) && (config->id != 0U) &&
	       vector_is_bounded(&config->center, PHYSICS_POSITION_LIMIT) &&
	       (config->half_extent.x >= PHYSICS_HALF_EXTENT_MINIMUM) &&
	       (config->half_extent.x <= PHYSICS_HALF_EXTENT_LIMIT) &&
	       (config->half_extent.y >= PHYSICS_HALF_EXTENT_MINIMUM) &&
	       (config->half_extent.y <= PHYSICS_HALF_EXTENT_LIMIT);
}

static bool
rope_endpoint_config_is_valid(const struct picosystem_physics_rope_endpoint_config *endpoint)
{
	if ((endpoint->pinned > 1U) || (endpoint->reaction_enabled > 1U) ||
	    ((endpoint->body_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID) &&
	     (endpoint->reaction_enabled != 0U)) ||
	    ((endpoint->body_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) && (endpoint->pinned == 0U))) {
		return false;
	}
	const picosystem_physics_fixed_t anchor_limit =
		(endpoint->body_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID)
			? PHYSICS_POSITION_LIMIT
			: PHYSICS_JOINT_LOCAL_ANCHOR_LIMIT;
	return vector_is_bounded(&endpoint->anchor, anchor_limit);
}

static bool rope_config_is_valid(const struct picosystem_physics_rope_config *config)
{
	if ((config == NULL) || (config->id == 0U) || (config->particle_count < 2U) ||
	    (config->particle_count > PICOSYSTEM_PHYSICS_MAX_ROPE_PARTICLES) ||
	    (config->segment_length < PHYSICS_ROPE_SEGMENT_LENGTH_MINIMUM) ||
	    (config->segment_length > PHYSICS_ROPE_SEGMENT_LENGTH_LIMIT) ||
	    (config->collision_radius < 0) ||
	    ((config->collision_radius != 0) &&
	     ((config->collision_radius < PHYSICS_ROPE_COLLISION_RADIUS_MINIMUM) ||
	      (config->collision_radius > PHYSICS_ROPE_COLLISION_RADIUS_LIMIT))) ||
	    !rope_endpoint_config_is_valid(&config->endpoint_a) ||
	    !rope_endpoint_config_is_valid(&config->endpoint_b)) {
		return false;
	}
	return (config->endpoint_a.body_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID) ||
	       (config->endpoint_a.body_id != config->endpoint_b.body_id) ||
	       ((config->endpoint_a.reaction_enabled == 0U) &&
		(config->endpoint_b.reaction_enabled == 0U));
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
	    (config->target_distance > PHYSICS_JOINT_DISTANCE_LIMIT) ||
	    (config->spring_enabled > 1U)) {
		return false;
	}
	if (config->spring_enabled != 0U) {
		if ((config->spring_angular_frequency_per_tick <
		     PHYSICS_SPRING_FREQUENCY_MINIMUM) ||
		    (config->spring_angular_frequency_per_tick > PHYSICS_SPRING_FREQUENCY_LIMIT) ||
		    (config->spring_damping_ratio < 0) ||
		    (config->spring_damping_ratio > PHYSICS_SPRING_DAMPING_RATIO_LIMIT) ||
		    (config->maximum_spring_impulse_per_tick <= 0) ||
		    (config->maximum_spring_impulse_per_tick > PHYSICS_SPRING_IMPULSE_LIMIT)) {
			return false;
		}
	} else if ((config->spring_angular_frequency_per_tick != 0) ||
		   (config->spring_damping_ratio != 0) ||
		   (config->maximum_spring_impulse_per_tick != 0)) {
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

static bool
prismatic_joint_config_is_valid(const struct picosystem_physics_prismatic_joint_config *config)
{
	if ((config == NULL) || (config->id == 0U) ||
	    (config->body_a_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID) ||
	    ((config->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) &&
	     (config->body_a_id == config->body_b_id)) ||
	    (config->collide_connected > 1U) || (config->motor_enabled > 1U) ||
	    (config->limit_enabled > 1U) ||
	    !vector_is_bounded(&config->local_anchor_a, PHYSICS_JOINT_LOCAL_ANCHOR_LIMIT) ||
	    !vector_is_bounded(&config->axis_b, PHYSICS_JOINT_AXIS_COMPONENT_LIMIT)) {
		return false;
	}

	const uint64_t minimum_axis_length_squared =
		(uint64_t)PHYSICS_JOINT_AXIS_MINIMUM_LENGTH * PHYSICS_JOINT_AXIS_MINIMUM_LENGTH;
	if (vector_length_squared_raw(&config->axis_b) < minimum_axis_length_squared) {
		return false;
	}
	if (config->motor_enabled != 0U) {
		if (!fixed_is_bounded(config->motor_speed_per_tick, PHYSICS_VELOCITY_LIMIT) ||
		    (config->maximum_motor_impulse_per_tick <= 0) ||
		    (config->maximum_motor_impulse_per_tick > PHYSICS_JOINT_MOTOR_IMPULSE_LIMIT)) {
			return false;
		}
	} else if ((config->motor_speed_per_tick != 0) ||
		   (config->maximum_motor_impulse_per_tick != 0)) {
		return false;
	}
	if (config->limit_enabled != 0U) {
		if (!fixed_is_bounded(config->lower_translation, PHYSICS_JOINT_DISTANCE_LIMIT) ||
		    !fixed_is_bounded(config->upper_translation, PHYSICS_JOINT_DISTANCE_LIMIT) ||
		    (config->lower_translation > config->upper_translation) ||
		    ((config->lower_translation != config->upper_translation) &&
		     ((config->upper_translation - config->lower_translation) <
		      (2 * PHYSICS_JOINT_POSITION_SLOP)))) {
			return false;
		}
	} else if ((config->lower_translation != 0) || (config->upper_translation != 0)) {
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

static picosystem_physics_fixed_t capsule_inverse_inertia(picosystem_physics_fixed_t half_length,
							  picosystem_physics_fixed_t radius,
							  picosystem_physics_fixed_t inverse_mass)
{
	/* A rectangular envelope is a stable, conservative gameplay approximation. */
	const struct picosystem_physics_vector envelope = {
		.x = half_length + radius,
		.y = radius,
	};
	return box_inverse_inertia(&envelope, inverse_mass);
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

	if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_CAPSULE) {
		const struct picosystem_physics_capsule_config config = {
			.center = body->center,
			.velocity_per_tick = body->velocity_per_tick,
			.half_length = body->half_extent.x,
			.radius = body->radius,
			.inverse_mass = body->inverse_mass,
			.restitution = body->restitution,
			.friction = body->friction,
			.angular_velocity_per_tick = body->angular_velocity_per_tick,
			.angle_turns = body->angle_turns,
			.id = body->id,
		};
		return capsule_config_is_valid(&config, world) && (body->half_extent.y == 0) &&
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
		.surface_speed_per_tick = segment->surface_speed_per_tick,
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

static bool sensor_is_valid(const struct picosystem_physics_box_sensor *sensor)
{
	const struct picosystem_physics_box_sensor_config config = {
		.center = sensor->center,
		.half_extent = sensor->half_extent,
		.id = sensor->id,
	};
	return box_sensor_config_is_valid(&config);
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
	if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_CAPSULE) {
		const picosystem_physics_fixed_t outside_x =
			fixed_maximum(fixed_absolute(anchor->x) - body->half_extent.x, 0);
		const struct picosystem_physics_vector from_centerline = {
			.x = outside_x,
			.y = anchor->y,
		};
		return vector_length_squared_raw(&from_centerline) <=
		       (uint64_t)((int64_t)body->radius * body->radius);
	}
	return false;
}

static bool rope_endpoint_is_valid(const struct picosystem_physics_world *world,
				   const struct picosystem_physics_vector *anchor, uint16_t body_id,
				   uint8_t body_index, uint8_t pinned, uint8_t reaction_enabled)
{
	const struct picosystem_physics_rope_endpoint_config endpoint = {
		.anchor = *anchor,
		.body_id = body_id,
		.pinned = pinned,
		.reaction_enabled = reaction_enabled,
	};
	if (!rope_endpoint_config_is_valid(&endpoint)) {
		return false;
	}
	if (body_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		return body_index == STATIC_BODY_INDEX;
	}
	return (body_index < world->body_count) && (world->bodies[body_index].id == body_id) &&
	       body_local_anchor_is_valid(&world->bodies[body_index], anchor);
}

static bool rope_is_valid(const struct picosystem_physics_rope *rope,
			  const struct picosystem_physics_world *world)
{
	const struct picosystem_physics_rope_config config = {
		.endpoint_a =
			{
				.anchor = rope->anchor_a,
				.body_id = rope->body_a_id,
				.pinned = rope->pin_a,
				.reaction_enabled = rope->reaction_a,
			},
		.endpoint_b =
			{
				.anchor = rope->anchor_b,
				.body_id = rope->body_b_id,
				.pinned = rope->pin_b,
				.reaction_enabled = rope->reaction_b,
			},
		.segment_length = rope->segment_length,
		.collision_radius = rope->collision_radius,
		.id = rope->id,
		.particle_count = rope->particle_count,
	};
	if (!rope_config_is_valid(&config) ||
	    !rope_endpoint_is_valid(world, &rope->anchor_a, rope->body_a_id, rope->body_a_index,
				    rope->pin_a, rope->reaction_a) ||
	    !rope_endpoint_is_valid(world, &rope->anchor_b, rope->body_b_id, rope->body_b_index,
				    rope->pin_b, rope->reaction_b)) {
		return false;
	}
	for (uint8_t index = 0U; index < rope->particle_count; ++index) {
		if (!vector_is_bounded(&rope->particles[index].position,
				       PHYSICS_ROPE_POSITION_LIMIT) ||
		    !vector_is_bounded(&rope->particles[index].previous_position,
				       PHYSICS_ROPE_POSITION_LIMIT)) {
			return false;
		}
	}
	return true;
}

static bool distance_joint_is_valid(const struct picosystem_physics_distance_joint *joint,
				    const struct picosystem_physics_world *world)
{
	const struct picosystem_physics_distance_joint_config config = {
		.local_anchor_a = joint->local_anchor_a,
		.anchor_b = joint->anchor_b,
		.target_distance = joint->target_distance,
		.spring_angular_frequency_per_tick = joint->spring_angular_frequency_per_tick,
		.spring_damping_ratio = joint->spring_damping_ratio,
		.maximum_spring_impulse_per_tick = joint->maximum_spring_impulse_per_tick,
		.id = joint->id,
		.body_a_id = joint->body_a_id,
		.body_b_id = joint->body_b_id,
		.spring_enabled = joint->spring_enabled,
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

static bool unit_vector_is_valid(const struct picosystem_physics_vector *vector)
{
	const uint64_t length_squared = vector_length_squared_raw(vector);
	const uint64_t minimum_length = PICOSYSTEM_PHYSICS_FIXED_ONE - 2;
	return (length_squared >= (minimum_length * minimum_length)) &&
	       (length_squared <=
		(uint64_t)PICOSYSTEM_PHYSICS_FIXED_ONE * PICOSYSTEM_PHYSICS_FIXED_ONE);
}

static bool prismatic_joint_is_valid(const struct picosystem_physics_prismatic_joint *joint,
				     const struct picosystem_physics_world *world)
{
	const struct picosystem_physics_prismatic_joint_config config = {
		.local_anchor_a = joint->local_anchor_a,
		.anchor_b = joint->anchor_b,
		.axis_b = joint->axis_b,
		.motor_speed_per_tick = joint->motor_speed_per_tick,
		.maximum_motor_impulse_per_tick = joint->maximum_motor_impulse_per_tick,
		.lower_translation = joint->lower_translation,
		.upper_translation = joint->upper_translation,
		.id = joint->id,
		.body_a_id = joint->body_a_id,
		.body_b_id = joint->body_b_id,
		.collide_connected = joint->collide_connected,
		.motor_enabled = joint->motor_enabled,
		.limit_enabled = joint->limit_enabled,
	};
	if (!prismatic_joint_config_is_valid(&config) || !unit_vector_is_valid(&joint->axis_b) ||
	    !fixed_is_bounded(joint->reference_translation,
			      PHYSICS_JOINT_REFERENCE_TRANSLATION_LIMIT) ||
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
	    (world->prismatic_joint_count > PICOSYSTEM_PHYSICS_MAX_PRISMATIC_JOINTS) ||
	    (world->box_sensor_count > PICOSYSTEM_PHYSICS_MAX_BOX_SENSORS) ||
	    (world->rope_count > PICOSYSTEM_PHYSICS_MAX_ROPES) ||
	    (world->contact_count > PICOSYSTEM_PHYSICS_MAX_CONTACTS) ||
	    (world->contact_event_count > PICOSYSTEM_PHYSICS_MAX_CONTACT_EVENTS) ||
	    !vector_is_bounded(&world->last_global_acceleration_per_tick,
			       PHYSICS_ACCELERATION_LIMIT)) {
		return false;
	}

	for (uint16_t sensor_index = 0U; sensor_index < world->box_sensor_count; ++sensor_index) {
		if (!sensor_is_valid(&world->box_sensors[sensor_index])) {
			return false;
		}
		for (uint16_t prior = 0U; prior < sensor_index; ++prior) {
			if (world->box_sensors[prior].id == world->box_sensors[sensor_index].id) {
				return false;
			}
		}
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

	for (uint16_t rope_index = 0U; rope_index < world->rope_count; ++rope_index) {
		if (!rope_is_valid(&world->ropes[rope_index], world)) {
			return false;
		}
		for (uint16_t prior = 0U; prior < rope_index; ++prior) {
			if (world->ropes[prior].id == world->ropes[rope_index].id) {
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

	for (uint16_t joint_index = 0U; joint_index < world->prismatic_joint_count; ++joint_index) {
		if (!prismatic_joint_is_valid(&world->prismatic_joints[joint_index], world)) {
			return false;
		}
		for (uint16_t prior = 0U; prior < joint_index; ++prior) {
			if (world->prismatic_joints[prior].id ==
			    world->prismatic_joints[joint_index].id) {
				return false;
			}
		}
	}

	const uint16_t valid_body_mask =
		(uint16_t)((UINT16_C(1) << world->body_count) - UINT16_C(1));
	if ((world->sleeping_body_mask & (uint16_t)~valid_body_mask) != 0U) {
		return false;
	}
	const uint8_t valid_segment_mask =
		(uint8_t)((world->static_segment_count == 8U)
				  ? UINT8_MAX
				  : ((UINT16_C(1) << world->static_segment_count) - UINT16_C(1)));
	const uint8_t valid_sensor_mask =
		(uint8_t)((world->box_sensor_count == 8U)
				  ? UINT8_MAX
				  : ((UINT16_C(1) << world->box_sensor_count) - UINT16_C(1)));
	for (uint16_t body_index = 0U; body_index < PICOSYSTEM_PHYSICS_MAX_BODIES; ++body_index) {
		const uint16_t lower_body_mask =
			(uint16_t)((UINT16_C(1) << (body_index + 1U)) - UINT16_C(1));
		const bool configured_body = body_index < world->body_count;
		const bool sleeping =
			(world->sleeping_body_mask & (uint16_t)(UINT16_C(1) << body_index)) != 0U;
		const uint16_t quiet_ticks = world->sleep_quiet_tick_counts[body_index];
		if ((!configured_body && ((world->active_body_contact_masks[body_index] != 0U) ||
					  (world->active_segment_contact_masks[body_index] != 0U) ||
					  (world->active_sensor_contact_masks[body_index] != 0U) ||
					  (quiet_ticks != 0U))) ||
		    (quiet_ticks > PICOSYSTEM_PHYSICS_SLEEP_QUIET_TICKS) ||
		    (sleeping && ((quiet_ticks != PICOSYSTEM_PHYSICS_SLEEP_QUIET_TICKS) ||
				  (world->bodies[body_index].velocity_per_tick.x != 0) ||
				  (world->bodies[body_index].velocity_per_tick.y != 0) ||
				  (world->bodies[body_index].angular_velocity_per_tick != 0))) ||
		    (!sleeping && configured_body &&
		     (quiet_ticks == PICOSYSTEM_PHYSICS_SLEEP_QUIET_TICKS)) ||
		    ((world->active_body_contact_masks[body_index] &
		      (uint16_t)(~valid_body_mask | lower_body_mask)) != 0U) ||
		    ((world->active_segment_contact_masks[body_index] &
		      (uint8_t)~valid_segment_mask) != 0U) ||
		    ((world->active_sensor_contact_masks[body_index] &
		      (uint8_t)~valid_sensor_mask) != 0U)) {
			return false;
		}
	}

	return true;
}

static uint16_t body_mask_for_index(uint8_t body_index)
{
	return (uint16_t)(UINT16_C(1) << body_index);
}

static uint16_t configured_body_mask(const struct picosystem_physics_world *world)
{
	return (uint16_t)((UINT16_C(1) << world->body_count) - UINT16_C(1));
}

static bool body_index_is_sleeping(const struct picosystem_physics_world *world, uint8_t body_index)
{
	return (world->sleeping_body_mask & body_mask_for_index(body_index)) != 0U;
}

static bool dynamic_pair_is_sleeping(const struct picosystem_physics_world *world,
				     uint8_t body_a_index, uint16_t body_b_id, uint8_t body_b_index)
{
	return body_index_is_sleeping(world, body_a_index) &&
	       ((body_b_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID) ||
		body_index_is_sleeping(world, body_b_index));
}

static bool contact_is_sleeping(const struct picosystem_physics_world *world,
				const struct picosystem_physics_contact *contact)
{
	const uint16_t body_b_id = (contact->type == PICOSYSTEM_PHYSICS_CONTACT_BODY)
					   ? world->bodies[contact->body_b_index].id
					   : PICOSYSTEM_PHYSICS_WORLD_BODY_ID;
	return dynamic_pair_is_sleeping(world, contact->body_a_index, body_b_id,
					contact->body_b_index);
}

static bool distance_joint_is_sleeping(const struct picosystem_physics_world *world,
				       const struct picosystem_physics_distance_joint *joint)
{
	return dynamic_pair_is_sleeping(world, joint->body_a_index, joint->body_b_id,
					joint->body_b_index);
}

static bool revolute_joint_is_sleeping(const struct picosystem_physics_world *world,
				       const struct picosystem_physics_revolute_joint *joint)
{
	return dynamic_pair_is_sleeping(world, joint->body_a_index, joint->body_b_id,
					joint->body_b_index);
}

static bool prismatic_joint_is_sleeping(const struct picosystem_physics_world *world,
					const struct picosystem_physics_prismatic_joint *joint)
{
	return dynamic_pair_is_sleeping(world, joint->body_a_index, joint->body_b_id,
					joint->body_b_index);
}

static void sleep_graph_add_edge(struct physics_sleep_graph *graph, uint8_t body_a_index,
				 uint8_t body_b_index)
{
	graph->neighbor_masks[body_a_index] |= body_mask_for_index(body_b_index);
	graph->neighbor_masks[body_b_index] |= body_mask_for_index(body_a_index);
}

static void sleep_graph_add_joint(struct physics_sleep_graph *graph, uint8_t body_a_index,
				  uint16_t body_b_id, uint8_t body_b_index)
{
	if (body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		sleep_graph_add_edge(graph, body_a_index, body_b_index);
	}
}

static void build_sleep_graph(const struct picosystem_physics_world *world,
			      const struct physics_contact_pair_masks *contact_pairs,
			      struct physics_sleep_graph *graph)
{
	memset(graph, 0, sizeof(*graph));
	for (uint8_t body_a = 0U; body_a < world->body_count; ++body_a) {
		uint16_t body_mask = contact_pairs->body_masks[body_a];
		while (body_mask != 0U) {
			const uint8_t body_b = (uint8_t)__builtin_ctz((unsigned int)body_mask);
			sleep_graph_add_edge(graph, body_a, body_b);
			body_mask &= (uint16_t)(body_mask - UINT16_C(1));
		}

		uint8_t segment_mask = contact_pairs->static_segment_masks[body_a];
		while (segment_mask != 0U) {
			const uint8_t segment_index =
				(uint8_t)__builtin_ctz((unsigned int)segment_mask);
			if (world->static_segments[segment_index].surface_speed_per_tick != 0) {
				graph->powered_body_mask |= body_mask_for_index(body_a);
			}
			segment_mask &= (uint8_t)(segment_mask - UINT8_C(1));
		}
	}

	for (uint16_t index = 0U; index < world->distance_joint_count; ++index) {
		const struct picosystem_physics_distance_joint *const joint =
			&world->distance_joints[index];
		sleep_graph_add_joint(graph, joint->body_a_index, joint->body_b_id,
				      joint->body_b_index);
	}
	for (uint16_t index = 0U; index < world->revolute_joint_count; ++index) {
		const struct picosystem_physics_revolute_joint *const joint =
			&world->revolute_joints[index];
		sleep_graph_add_joint(graph, joint->body_a_index, joint->body_b_id,
				      joint->body_b_index);
		if (joint->motor_enabled != 0U) {
			graph->powered_body_mask |= body_mask_for_index(joint->body_a_index);
			if (joint->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
				graph->powered_body_mask |=
					body_mask_for_index(joint->body_b_index);
			}
		}
	}
	for (uint16_t index = 0U; index < world->prismatic_joint_count; ++index) {
		const struct picosystem_physics_prismatic_joint *const joint =
			&world->prismatic_joints[index];
		sleep_graph_add_joint(graph, joint->body_a_index, joint->body_b_id,
				      joint->body_b_index);
		if (joint->motor_enabled != 0U) {
			graph->powered_body_mask |= body_mask_for_index(joint->body_a_index);
			if (joint->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
				graph->powered_body_mask |=
					body_mask_for_index(joint->body_b_index);
			}
		}
	}
	for (uint16_t index = 0U; index < world->rope_count; ++index) {
		const struct picosystem_physics_rope *const rope = &world->ropes[index];
		const bool reacts_at_a = rope->reaction_a != 0U;
		const bool reacts_at_b = rope->reaction_b != 0U;
		if ((reacts_at_a || reacts_at_b) &&
		    (rope->body_a_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) &&
		    (rope->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID)) {
			sleep_graph_add_edge(graph, rope->body_a_index, rope->body_b_index);
		}
	}
}

static uint16_t sleep_graph_expand_mask(const struct physics_sleep_graph *graph, uint16_t body_mask)
{
	uint16_t expanded = body_mask;
	for (;;) {
		uint16_t neighbors = 0U;
		uint16_t remaining = expanded;
		while (remaining != 0U) {
			const uint8_t body_index = (uint8_t)__builtin_ctz((unsigned int)remaining);
			neighbors |= graph->neighbor_masks[body_index];
			remaining &= (uint16_t)(remaining - UINT16_C(1));
		}
		const uint16_t next = expanded | neighbors;
		if (next == expanded) {
			return expanded;
		}
		expanded = next;
	}
}

static uint16_t wake_sleeping_body_mask(struct picosystem_physics_world *world,
					uint16_t requested_mask, bool record_transition)
{
	const uint16_t waking_mask = world->sleeping_body_mask & requested_mask;
	uint16_t remaining = waking_mask;
	while (remaining != 0U) {
		const uint8_t body_index = (uint8_t)__builtin_ctz((unsigned int)remaining);
		world->sleep_quiet_tick_counts[body_index] = 0U;
		remaining &= (uint16_t)(remaining - UINT16_C(1));
	}
	world->sleeping_body_mask &= (uint16_t)~waking_mask;
	if (record_transition) {
		world->last_work.body_wake_transition_count +=
			(uint32_t)__builtin_popcount((unsigned int)waking_mask);
	}
	return waking_mask;
}

static void wake_interacting_sleepers(struct picosystem_physics_world *world,
				      const struct physics_sleep_graph *graph)
{
	if (world->sleeping_body_mask == 0U) {
		return;
	}
	const uint16_t awake_sources =
		(configured_body_mask(world) & (uint16_t)~world->sleeping_body_mask) |
		graph->powered_body_mask;
	const uint16_t connected_awake = sleep_graph_expand_mask(graph, awake_sources);
	(void)wake_sleeping_body_mask(world, connected_awake, true);
}

static bool body_motion_is_quiet(const struct picosystem_physics_body *body)
{
	const uint64_t linear_threshold_squared =
		(uint64_t)((int64_t)PHYSICS_SLEEP_LINEAR_VELOCITY_THRESHOLD *
			   PHYSICS_SLEEP_LINEAR_VELOCITY_THRESHOLD);
	return (vector_length_squared_raw(&body->velocity_per_tick) <= linear_threshold_squared) &&
	       (fixed_absolute(body->angular_velocity_per_tick) <=
		PHYSICS_SLEEP_ANGULAR_VELOCITY_THRESHOLD);
}

static void put_body_mask_to_sleep(struct picosystem_physics_world *world, uint16_t body_mask)
{
	uint16_t remaining = body_mask;
	while (remaining != 0U) {
		const uint8_t body_index = (uint8_t)__builtin_ctz((unsigned int)remaining);
		struct picosystem_physics_body *const body = &world->bodies[body_index];
		body->velocity_per_tick = (struct picosystem_physics_vector){0};
		body->angular_velocity_per_tick = 0;
		world->sleep_quiet_tick_counts[body_index] = PICOSYSTEM_PHYSICS_SLEEP_QUIET_TICKS;
		remaining &= (uint16_t)(remaining - UINT16_C(1));
	}
	world->sleeping_body_mask |= body_mask;
	world->last_work.body_sleep_transition_count +=
		(uint32_t)__builtin_popcount((unsigned int)body_mask);
}

static void update_sleep_state(struct picosystem_physics_world *world,
			       const struct physics_sleep_graph *graph)
{
	uint16_t unvisited = configured_body_mask(world);
	while (unvisited != 0U) {
		const uint8_t first_body = (uint8_t)__builtin_ctz((unsigned int)unvisited);
		const uint16_t component =
			sleep_graph_expand_mask(graph, body_mask_for_index(first_body));
		unvisited &= (uint16_t)~component;

		if ((world->sleeping_body_mask & component) == component) {
			continue;
		}

		bool quiet = (graph->powered_body_mask & component) == 0U;
		uint16_t minimum_quiet_ticks = PICOSYSTEM_PHYSICS_SLEEP_QUIET_TICKS;
		uint16_t remaining = component;
		while (remaining != 0U) {
			const uint8_t body_index = (uint8_t)__builtin_ctz((unsigned int)remaining);
			quiet &= body_motion_is_quiet(&world->bodies[body_index]);
			if (world->sleep_quiet_tick_counts[body_index] < minimum_quiet_ticks) {
				minimum_quiet_ticks = world->sleep_quiet_tick_counts[body_index];
			}
			remaining &= (uint16_t)(remaining - UINT16_C(1));
		}

		if (!quiet) {
			remaining = component;
			while (remaining != 0U) {
				const uint8_t body_index =
					(uint8_t)__builtin_ctz((unsigned int)remaining);
				world->sleep_quiet_tick_counts[body_index] = 0U;
				remaining &= (uint16_t)(remaining - UINT16_C(1));
			}
			continue;
		}

		const uint16_t next_quiet_ticks = minimum_quiet_ticks + 1U;
		if (next_quiet_ticks >= PICOSYSTEM_PHYSICS_SLEEP_QUIET_TICKS) {
			put_body_mask_to_sleep(world, component);
			continue;
		}
		remaining = component;
		while (remaining != 0U) {
			const uint8_t body_index = (uint8_t)__builtin_ctz((unsigned int)remaining);
			world->sleep_quiet_tick_counts[body_index] = next_quiet_ticks;
			remaining &= (uint16_t)(remaining - UINT16_C(1));
		}
	}

	world->last_work.sleeping_body_count =
		(uint32_t)__builtin_popcount((unsigned int)world->sleeping_body_mask);
	world->last_work.awake_body_count =
		(uint32_t)world->body_count - world->last_work.sleeping_body_count;
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

static struct picosystem_physics_vector
clamp_vector_length(const struct picosystem_physics_vector *vector,
		    picosystem_physics_fixed_t maximum)
{
	const uint64_t length_squared = vector_length_squared_raw(vector);
	const uint64_t maximum_squared = (uint64_t)((int64_t)maximum * maximum);
	if (length_squared <= maximum_squared) {
		return *vector;
	}
	const uint32_t length = integer_square_root_ceiling(length_squared);
	return (struct picosystem_physics_vector){
		.x = (picosystem_physics_fixed_t)(((int64_t)vector->x * maximum) / length),
		.y = (picosystem_physics_fixed_t)(((int64_t)vector->y * maximum) / length),
	};
}

static void clamp_rope_particle_position(struct picosystem_physics_rope_particle *particle)
{
	particle->position.x = fixed_clamp(particle->position.x, -PHYSICS_ROPE_POSITION_LIMIT,
					   PHYSICS_ROPE_POSITION_LIMIT);
	particle->position.y = fixed_clamp(particle->position.y, -PHYSICS_ROPE_POSITION_LIMIT,
					   PHYSICS_ROPE_POSITION_LIMIT);
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

static uint32_t
prismatic_joint_relative_angle_turns(const struct picosystem_physics_world *world,
				     const struct picosystem_physics_prismatic_joint *joint)
{
	const uint32_t body_a_angle = world->bodies[joint->body_a_index].angle_turns;
	const uint32_t body_b_angle = (joint->body_b_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID)
					      ? 0U
					      : world->bodies[joint->body_b_index].angle_turns;
	return body_a_angle - body_b_angle;
}

static picosystem_physics_fixed_t
prismatic_joint_relative_angle_radians(const struct picosystem_physics_world *world,
				       const struct picosystem_physics_prismatic_joint *joint)
{
	const uint32_t relative_turns = prismatic_joint_relative_angle_turns(world, joint);
	return angle_turn_delta_to_radians(relative_turns - joint->reference_angle_turns);
}

static void prismatic_joint_geometry(const struct picosystem_physics_world *world,
				     const struct picosystem_physics_prismatic_joint *joint,
				     struct picosystem_physics_vector *world_anchor_a,
				     struct picosystem_physics_vector *world_anchor_b,
				     struct picosystem_physics_vector *world_axis)
{
	*world_anchor_a = body_local_point_to_world(&world->bodies[joint->body_a_index],
						    &joint->local_anchor_a);
	if (joint->body_b_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		*world_anchor_b = joint->anchor_b;
		*world_axis = joint->axis_b;
		return;
	}
	*world_anchor_b =
		body_local_point_to_world(&world->bodies[joint->body_b_index], &joint->anchor_b);
	*world_axis =
		body_local_vector_to_world(&world->bodies[joint->body_b_index], &joint->axis_b);
}

static picosystem_physics_fixed_t
prismatic_joint_translation(const struct picosystem_physics_world *world,
			    const struct picosystem_physics_prismatic_joint *joint)
{
	struct picosystem_physics_vector world_anchor_a;
	struct picosystem_physics_vector world_anchor_b;
	struct picosystem_physics_vector world_axis;
	prismatic_joint_geometry(world, joint, &world_anchor_a, &world_anchor_b, &world_axis);
	const struct picosystem_physics_vector delta =
		vector_subtract(&world_anchor_a, &world_anchor_b);
	return vector_dot(&delta, &world_axis) - joint->reference_translation;
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

static picosystem_physics_fixed_t
prismatic_joint_direction_inverse_mass(const struct picosystem_physics_world *world,
				       const struct picosystem_physics_prismatic_joint *joint,
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

static picosystem_physics_fixed_t
prismatic_joint_angular_effective_mass(const struct picosystem_physics_world *world,
				       const struct picosystem_physics_prismatic_joint *joint)
{
	picosystem_physics_fixed_t inverse_mass =
		world->bodies[joint->body_a_index].inverse_inertia;
	if (joint->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		inverse_mass += world->bodies[joint->body_b_index].inverse_inertia;
	}
	return fixed_divide(PICOSYSTEM_PHYSICS_FIXED_ONE, inverse_mass);
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

static picosystem_physics_fixed_t
capsule_projection_radius(const struct picosystem_physics_body *body,
			  const struct box_geometry *geometry,
			  const struct picosystem_physics_vector *axis)
{
	return fixed_multiply(body->half_extent.x,
			      fixed_absolute(vector_dot(&geometry->axis_x, axis))) +
	       body->radius;
}

static bool update_symmetric_sat_axis(const struct picosystem_physics_vector *center_delta,
				      picosystem_physics_fixed_t radius_a,
				      picosystem_physics_fixed_t radius_b,
				      const struct picosystem_physics_vector *axis,
				      picosystem_physics_fixed_t *minimum_overlap,
				      struct picosystem_physics_vector *minimum_axis)
{
	const picosystem_physics_fixed_t distance = fixed_absolute(vector_dot(center_delta, axis));
	const picosystem_physics_fixed_t overlap = radius_a + radius_b - distance;
	if (overlap <= 0) {
		return false;
	}
	if (overlap < *minimum_overlap) {
		*minimum_overlap = overlap;
		*minimum_axis = *axis;
	}
	return true;
}

static struct picosystem_physics_vector
capsule_support_feature(const struct picosystem_physics_body *body,
			const struct box_geometry *geometry,
			const struct picosystem_physics_vector *direction)
{
	struct picosystem_physics_vector centerline_point = body->center;
	const picosystem_physics_fixed_t axial_projection =
		vector_dot(direction, &geometry->axis_x);
	if (axial_projection != 0) {
		const picosystem_physics_fixed_t axial_distance =
			(axial_projection > 0) ? body->half_extent.x : -body->half_extent.x;
		const struct picosystem_physics_vector axial_offset =
			vector_scale(&geometry->axis_x, axial_distance);
		centerline_point = vector_add(&centerline_point, &axial_offset);
	}
	const struct picosystem_physics_vector radius_offset =
		vector_scale(direction, body->radius);
	return vector_add(&centerline_point, &radius_offset);
}

static struct picosystem_physics_vector
box_support_feature(const struct picosystem_physics_body *body, const struct box_geometry *geometry,
		    const struct picosystem_physics_vector *direction)
{
	struct picosystem_physics_vector point = body->center;
	const picosystem_physics_fixed_t projection_x = vector_dot(direction, &geometry->axis_x);
	if (projection_x != 0) {
		const picosystem_physics_fixed_t distance_x =
			(projection_x > 0) ? body->half_extent.x : -body->half_extent.x;
		const struct picosystem_physics_vector offset_x =
			vector_scale(&geometry->axis_x, distance_x);
		point = vector_add(&point, &offset_x);
	}
	const picosystem_physics_fixed_t projection_y = vector_dot(direction, &geometry->axis_y);
	if (projection_y != 0) {
		const picosystem_physics_fixed_t distance_y =
			(projection_y > 0) ? body->half_extent.y : -body->half_extent.y;
		const struct picosystem_physics_vector offset_y =
			vector_scale(&geometry->axis_y, distance_y);
		point = vector_add(&point, &offset_y);
	}
	return point;
}

static void orient_axis_from_a_to_b(struct picosystem_physics_vector *axis,
				    const struct picosystem_physics_vector *center_delta,
				    uint16_t id_a, uint16_t id_b)
{
	const picosystem_physics_fixed_t projection = vector_dot(center_delta, axis);
	if ((projection < 0) || ((projection == 0) && (id_a > id_b))) {
		*axis = vector_negate(axis);
	}
}

static int generate_capsule_circle_contact(struct picosystem_physics_world *world,
					   uint8_t capsule_index, uint8_t circle_index,
					   const struct box_geometry *capsule_geometry,
					   bool capsule_is_body_a)
{
	const struct picosystem_physics_body *const capsule = &world->bodies[capsule_index];
	const struct picosystem_physics_body *const circle = &world->bodies[circle_index];
	struct picosystem_physics_vector start;
	struct picosystem_physics_vector end;
	capsule_centerline_from_geometry(capsule, capsule_geometry, &start, &end);
	const struct picosystem_physics_vector closest =
		closest_point_on_segment_endpoints(&circle->center, &start, &end);
	const struct picosystem_physics_vector capsule_to_circle =
		vector_subtract(&circle->center, &closest);
	const picosystem_physics_fixed_t combined_radius = capsule->radius + circle->radius;
	const uint64_t radius_squared = (uint64_t)((int64_t)combined_radius * combined_radius);
	if (vector_length_squared_raw(&capsule_to_circle) >= radius_squared) {
		return 0;
	}

	struct picosystem_physics_vector fallback = capsule_geometry->axis_y;
	if (capsule->id > circle->id) {
		fallback = vector_negate(&fallback);
	}
	struct picosystem_physics_vector capsule_to_circle_normal;
	const picosystem_physics_fixed_t distance =
		normalize_vector(&capsule_to_circle, &capsule_to_circle_normal, &fallback);
	const struct picosystem_physics_vector capsule_radius =
		vector_scale(&capsule_to_circle_normal, capsule->radius);
	const struct picosystem_physics_vector circle_radius =
		vector_scale(&capsule_to_circle_normal, circle->radius);
	const struct picosystem_physics_vector point_capsule =
		vector_add(&closest, &capsule_radius);
	const struct picosystem_physics_vector point_circle =
		vector_subtract(&circle->center, &circle_radius);
	const struct contact_point_candidate candidate = {
		.point =
			{
				.x = (point_capsule.x + point_circle.x) / 2,
				.y = (point_capsule.y + point_circle.y) / 2,
			},
		.penetration = combined_radius - distance,
	};
	struct picosystem_physics_vector normal = capsule_to_circle_normal;
	if (!capsule_is_body_a) {
		normal = vector_negate(&normal);
	}
	const uint8_t body_a_index = capsule_is_body_a ? capsule_index : circle_index;
	const uint8_t body_b_index = capsule_is_body_a ? circle_index : capsule_index;
	return append_manifold(world, body_a_index, body_b_index, STATIC_SEGMENT_INDEX,
			       PICOSYSTEM_PHYSICS_CONTACT_BODY, &normal, &candidate, 1U);
}

static bool update_capsule_capsule_endpoint_axis(
	const struct picosystem_physics_body *body_a, const struct box_geometry *geometry_a,
	const struct picosystem_physics_body *body_b, const struct box_geometry *geometry_b,
	const struct picosystem_physics_vector *center_delta,
	const struct picosystem_physics_vector *point_a,
	const struct picosystem_physics_vector *point_b,
	picosystem_physics_fixed_t *minimum_overlap, struct picosystem_physics_vector *minimum_axis)
{
	const struct picosystem_physics_vector delta = vector_subtract(point_b, point_a);
	if (vector_length_squared_raw(&delta) == 0U) {
		return true;
	}
	const struct picosystem_physics_vector fallback = {
		.x = PICOSYSTEM_PHYSICS_FIXED_ONE,
	};
	struct picosystem_physics_vector axis;
	(void)normalize_vector(&delta, &axis, &fallback);
	return update_symmetric_sat_axis(center_delta,
					 capsule_projection_radius(body_a, geometry_a, &axis),
					 capsule_projection_radius(body_b, geometry_b, &axis),
					 &axis, minimum_overlap, minimum_axis);
}

static int generate_capsule_capsule_contact(struct picosystem_physics_world *world,
					    uint8_t body_a_index, uint8_t body_b_index,
					    const struct box_geometry *geometry_a,
					    const struct box_geometry *geometry_b)
{
	const struct picosystem_physics_body *const body_a = &world->bodies[body_a_index];
	const struct picosystem_physics_body *const body_b = &world->bodies[body_b_index];
	const struct picosystem_physics_vector center_delta =
		vector_subtract(&body_b->center, &body_a->center);
	picosystem_physics_fixed_t minimum_overlap = INT32_MAX;
	struct picosystem_physics_vector minimum_axis;
	const struct picosystem_physics_vector side_axes[] = {
		geometry_a->axis_y,
		geometry_b->axis_y,
	};
	for (size_t index = 0U; index < (sizeof(side_axes) / sizeof(side_axes[0])); ++index) {
		if (!update_symmetric_sat_axis(
			    &center_delta,
			    capsule_projection_radius(body_a, geometry_a, &side_axes[index]),
			    capsule_projection_radius(body_b, geometry_b, &side_axes[index]),
			    &side_axes[index], &minimum_overlap, &minimum_axis)) {
			return 0;
		}
	}

	struct picosystem_physics_vector start_a;
	struct picosystem_physics_vector end_a;
	struct picosystem_physics_vector start_b;
	struct picosystem_physics_vector end_b;
	capsule_centerline_from_geometry(body_a, geometry_a, &start_a, &end_a);
	capsule_centerline_from_geometry(body_b, geometry_b, &start_b, &end_b);
	const struct picosystem_physics_vector endpoints_a[] = {start_a, end_a};
	const struct picosystem_physics_vector endpoints_b[] = {start_b, end_b};
	for (size_t index = 0U; index < 2U; ++index) {
		const struct picosystem_physics_vector closest_b =
			closest_point_on_segment_endpoints(&endpoints_a[index], &start_b, &end_b);
		if (!update_capsule_capsule_endpoint_axis(
			    body_a, geometry_a, body_b, geometry_b, &center_delta,
			    &endpoints_a[index], &closest_b, &minimum_overlap, &minimum_axis)) {
			return 0;
		}
		const struct picosystem_physics_vector closest_a =
			closest_point_on_segment_endpoints(&endpoints_b[index], &start_a, &end_a);
		if (!update_capsule_capsule_endpoint_axis(
			    body_a, geometry_a, body_b, geometry_b, &center_delta, &closest_a,
			    &endpoints_b[index], &minimum_overlap, &minimum_axis)) {
			return 0;
		}
	}

	orient_axis_from_a_to_b(&minimum_axis, &center_delta, body_a->id, body_b->id);
	const struct picosystem_physics_vector negative_normal = vector_negate(&minimum_axis);
	const struct picosystem_physics_vector point_a =
		capsule_support_feature(body_a, geometry_a, &minimum_axis);
	const struct picosystem_physics_vector point_b =
		capsule_support_feature(body_b, geometry_b, &negative_normal);
	const struct contact_point_candidate candidate = {
		.point =
			{
				.x = (point_a.x + point_b.x) / 2,
				.y = (point_a.y + point_b.y) / 2,
			},
		.penetration = minimum_overlap,
	};
	return append_manifold(world, body_a_index, body_b_index, STATIC_SEGMENT_INDEX,
			       PICOSYSTEM_PHYSICS_CONTACT_BODY, &minimum_axis, &candidate, 1U);
}

static int generate_capsule_box_contact(struct picosystem_physics_world *world,
					uint8_t capsule_index, uint8_t box_index,
					const struct box_geometry *capsule_geometry,
					const struct box_geometry *box_geometry,
					bool capsule_is_body_a)
{
	const struct picosystem_physics_body *const capsule = &world->bodies[capsule_index];
	const struct picosystem_physics_body *const box = &world->bodies[box_index];
	const struct picosystem_physics_vector capsule_to_box =
		vector_subtract(&box->center, &capsule->center);
	picosystem_physics_fixed_t minimum_overlap = INT32_MAX;
	struct picosystem_physics_vector minimum_axis;
	const struct picosystem_physics_vector face_axes[] = {
		box_geometry->axis_x,
		box_geometry->axis_y,
		capsule_geometry->axis_y,
	};
	for (size_t index = 0U; index < (sizeof(face_axes) / sizeof(face_axes[0])); ++index) {
		if (!update_symmetric_sat_axis(
			    &capsule_to_box,
			    capsule_projection_radius(capsule, capsule_geometry, &face_axes[index]),
			    box_projection_radius(box, box_geometry, &face_axes[index]),
			    &face_axes[index], &minimum_overlap, &minimum_axis)) {
			return 0;
		}
	}

	struct picosystem_physics_vector start;
	struct picosystem_physics_vector end;
	capsule_centerline_from_geometry(capsule, capsule_geometry, &start, &end);
	struct picosystem_physics_vector vertices[PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT];
	box_vertices_from_geometry(box, box_geometry, vertices);
	for (size_t index = 0U; index < PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT; ++index) {
		const struct picosystem_physics_vector closest =
			closest_point_on_segment_endpoints(&vertices[index], &start, &end);
		const struct picosystem_physics_vector delta =
			vector_subtract(&vertices[index], &closest);
		if (vector_length_squared_raw(&delta) == 0U) {
			continue;
		}
		const struct picosystem_physics_vector fallback = {
			.x = PICOSYSTEM_PHYSICS_FIXED_ONE,
		};
		struct picosystem_physics_vector axis;
		(void)normalize_vector(&delta, &axis, &fallback);
		if (!update_symmetric_sat_axis(
			    &capsule_to_box,
			    capsule_projection_radius(capsule, capsule_geometry, &axis),
			    box_projection_radius(box, box_geometry, &axis), &axis,
			    &minimum_overlap, &minimum_axis)) {
			return 0;
		}
	}

	orient_axis_from_a_to_b(&minimum_axis, &capsule_to_box, capsule->id, box->id);
	const struct picosystem_physics_vector negative_normal = vector_negate(&minimum_axis);
	const struct picosystem_physics_vector point_capsule =
		capsule_support_feature(capsule, capsule_geometry, &minimum_axis);
	const struct picosystem_physics_vector point_box =
		box_support_feature(box, box_geometry, &negative_normal);
	const struct contact_point_candidate candidate = {
		.point =
			{
				.x = (point_capsule.x + point_box.x) / 2,
				.y = (point_capsule.y + point_box.y) / 2,
			},
		.penetration = minimum_overlap,
	};
	struct picosystem_physics_vector normal = minimum_axis;
	if (!capsule_is_body_a) {
		normal = vector_negate(&normal);
	}
	const uint8_t body_a_index = capsule_is_body_a ? capsule_index : box_index;
	const uint8_t body_b_index = capsule_is_body_a ? box_index : capsule_index;
	return append_manifold(world, body_a_index, body_b_index, STATIC_SEGMENT_INDEX,
			       PICOSYSTEM_PHYSICS_CONTACT_BODY, &normal, &candidate, 1U);
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
	if ((shape_a == PICOSYSTEM_PHYSICS_SHAPE_CAPSULE) &&
	    (shape_b == PICOSYSTEM_PHYSICS_SHAPE_CIRCLE)) {
		return generate_capsule_circle_contact(world, body_a_index, body_b_index,
						       &geometries[body_a_index], true);
	}
	if ((shape_a == PICOSYSTEM_PHYSICS_SHAPE_CIRCLE) &&
	    (shape_b == PICOSYSTEM_PHYSICS_SHAPE_CAPSULE)) {
		return generate_capsule_circle_contact(world, body_b_index, body_a_index,
						       &geometries[body_b_index], false);
	}
	if ((shape_a == PICOSYSTEM_PHYSICS_SHAPE_CAPSULE) &&
	    (shape_b == PICOSYSTEM_PHYSICS_SHAPE_CAPSULE)) {
		return generate_capsule_capsule_contact(world, body_a_index, body_b_index,
							&geometries[body_a_index],
							&geometries[body_b_index]);
	}
	if ((shape_a == PICOSYSTEM_PHYSICS_SHAPE_CAPSULE) &&
	    (shape_b == PICOSYSTEM_PHYSICS_SHAPE_BOX)) {
		return generate_capsule_box_contact(world, body_a_index, body_b_index,
						    &geometries[body_a_index],
						    &geometries[body_b_index], true);
	}
	if ((shape_a == PICOSYSTEM_PHYSICS_SHAPE_BOX) &&
	    (shape_b == PICOSYSTEM_PHYSICS_SHAPE_CAPSULE)) {
		return generate_capsule_box_contact(world, body_b_index, body_a_index,
						    &geometries[body_b_index],
						    &geometries[body_a_index], false);
	}
	return generate_box_box_contact(world, body_a_index, body_b_index,
					&geometries[body_a_index], &geometries[body_b_index]);
}

static struct picosystem_physics_vector
closest_point_on_segment(const struct picosystem_physics_vector *point,
			 const struct picosystem_physics_static_segment *segment)
{
	return closest_point_on_segment_endpoints(point, &segment->start, &segment->end);
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

static bool update_capsule_segment_sat_axis(const struct picosystem_physics_body *body,
					    const struct box_geometry *geometry,
					    const struct picosystem_physics_static_segment *segment,
					    const struct picosystem_physics_vector *axis,
					    picosystem_physics_fixed_t *minimum_depth,
					    struct picosystem_physics_vector *minimum_axis)
{
	const picosystem_physics_fixed_t center = vector_dot(&body->center, axis);
	const picosystem_physics_fixed_t radius = capsule_projection_radius(body, geometry, axis);
	const picosystem_physics_fixed_t start = vector_dot(&segment->start, axis);
	const picosystem_physics_fixed_t end = vector_dot(&segment->end, axis);
	const picosystem_physics_fixed_t depth =
		interval_separation_depth(center - radius, center + radius,
					  fixed_minimum(start, end), fixed_maximum(start, end));
	if (depth <= 0) {
		return false;
	}
	if (depth < *minimum_depth) {
		*minimum_depth = depth;
		*minimum_axis = *axis;
	}
	return true;
}

static bool capsule_endpoint_contact_candidate(
	const struct picosystem_physics_vector *endpoint,
	const struct picosystem_physics_static_segment *segment,
	const struct picosystem_physics_vector *normal, picosystem_physics_fixed_t radius,
	picosystem_physics_fixed_t penetration, struct contact_point_candidate *candidate)
{
	const struct picosystem_physics_vector closest =
		closest_point_on_segment(endpoint, segment);
	const struct picosystem_physics_vector delta = vector_subtract(&closest, endpoint);
	const uint64_t radius_squared = (uint64_t)((int64_t)radius * radius);
	if ((vector_length_squared_raw(&delta) >= radius_squared) ||
	    (vector_dot(&delta, normal) <= 0)) {
		return false;
	}

	const struct picosystem_physics_vector radius_offset = vector_scale(normal, radius);
	const struct picosystem_physics_vector body_surface = vector_add(endpoint, &radius_offset);
	*candidate = (struct contact_point_candidate){
		.point =
			{
				.x = (body_surface.x + closest.x) / 2,
				.y = (body_surface.y + closest.y) / 2,
			},
		.penetration = penetration,
	};
	return true;
}

static int generate_capsule_segment_contact(struct picosystem_physics_world *world,
					    uint8_t body_index, uint8_t segment_index,
					    const struct box_geometry *geometry)
{
	const struct picosystem_physics_body *const body = &world->bodies[body_index];
	const struct picosystem_physics_static_segment *const segment =
		&world->static_segments[segment_index];
	picosystem_physics_fixed_t minimum_depth = INT32_MAX;
	struct picosystem_physics_vector minimum_axis;
	const struct picosystem_physics_vector axes[] = {
		geometry->axis_y,
		segment->normal,
	};
	for (size_t index = 0U; index < (sizeof(axes) / sizeof(axes[0])); ++index) {
		if (!update_capsule_segment_sat_axis(body, geometry, segment, &axes[index],
						     &minimum_depth, &minimum_axis)) {
			return 0;
		}
	}

	struct picosystem_physics_vector start;
	struct picosystem_physics_vector end;
	capsule_centerline_from_geometry(body, geometry, &start, &end);
	const struct segment_closest_result closest =
		closest_points_between_segments(&start, &end, &segment->start, &segment->end);
	if (closest.distance_squared_raw != 0U) {
		const struct picosystem_physics_vector closest_delta =
			vector_subtract(&closest.point_b, &closest.point_a);
		const struct picosystem_physics_vector fallback = {
			.x = PICOSYSTEM_PHYSICS_FIXED_ONE,
		};
		struct picosystem_physics_vector closest_axis;
		(void)normalize_vector(&closest_delta, &closest_axis, &fallback);
		if (!update_capsule_segment_sat_axis(body, geometry, segment, &closest_axis,
						     &minimum_depth, &minimum_axis)) {
			return 0;
		}
	}

	const struct picosystem_physics_vector segment_midpoint = {
		.x = (segment->start.x + segment->end.x) / 2,
		.y = (segment->start.y + segment->end.y) / 2,
	};
	const struct picosystem_physics_vector body_to_segment =
		vector_subtract(&segment_midpoint, &body->center);
	orient_axis_from_a_to_b(&minimum_axis, &body_to_segment, body->id, segment->id);

	struct contact_point_candidate candidates[PICOSYSTEM_PHYSICS_MAX_MANIFOLD_POINTS];
	size_t candidate_count = 0U;
	if (capsule_endpoint_contact_candidate(&start, segment, &minimum_axis, body->radius,
					       minimum_depth, &candidates[candidate_count])) {
		++candidate_count;
	}
	if (capsule_endpoint_contact_candidate(&end, segment, &minimum_axis, body->radius,
					       minimum_depth, &candidates[candidate_count])) {
		if ((candidate_count == 0U) ||
		    (candidates[0].point.x != candidates[candidate_count].point.x) ||
		    (candidates[0].point.y != candidates[candidate_count].point.y)) {
			++candidate_count;
		}
	}

	if (candidate_count == 0U) {
		struct picosystem_physics_vector contact_point = closest.point_a;
		if (closest.distance_squared_raw != 0U) {
			const struct picosystem_physics_vector radius_offset =
				vector_scale(&minimum_axis, body->radius);
			const struct picosystem_physics_vector body_surface =
				vector_add(&closest.point_a, &radius_offset);
			contact_point = (struct picosystem_physics_vector){
				.x = (body_surface.x + closest.point_b.x) / 2,
				.y = (body_surface.y + closest.point_b.y) / 2,
			};
		}
		candidates[0] = (struct contact_point_candidate){
			.point = contact_point,
			.penetration = minimum_depth,
		};
		candidate_count = 1U;
	}

	return append_manifold(world, body_index, STATIC_BODY_INDEX, segment_index,
			       PICOSYSTEM_PHYSICS_CONTACT_STATIC_SEGMENT, &minimum_axis, candidates,
			       candidate_count);
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
	if (world->bodies[body_index].shape == PICOSYSTEM_PHYSICS_SHAPE_CAPSULE) {
		return generate_capsule_segment_contact(world, body_index, segment_index, geometry);
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
	} else if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_CAPSULE) {
		extent_x = fixed_multiply(fixed_absolute(geometry->axis_x.x), body->half_extent.x) +
			   body->radius;
		extent_y = fixed_multiply(fixed_absolute(geometry->axis_x.y), body->half_extent.x) +
			   body->radius;
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

static void sensor_aabb(const struct picosystem_physics_box_sensor *sensor,
			struct physics_aabb *aabb)
{
	*aabb = (struct physics_aabb){
		.minimum_x = sensor->center.x - sensor->half_extent.x,
		.minimum_y = sensor->center.y - sensor->half_extent.y,
		.maximum_x = sensor->center.x + sensor->half_extent.x,
		.maximum_y = sensor->center.y + sensor->half_extent.y,
	};
}

static bool circle_overlaps_sensor(const struct picosystem_physics_body *body,
				   const struct picosystem_physics_box_sensor *sensor)
{
	const picosystem_physics_fixed_t delta_x =
		fixed_absolute(body->center.x - sensor->center.x);
	const picosystem_physics_fixed_t delta_y =
		fixed_absolute(body->center.y - sensor->center.y);
	const picosystem_physics_fixed_t outside_x =
		fixed_maximum(delta_x - sensor->half_extent.x, 0);
	const picosystem_physics_fixed_t outside_y =
		fixed_maximum(delta_y - sensor->half_extent.y, 0);
	const uint64_t distance_squared =
		(uint64_t)(((int64_t)outside_x * outside_x) + ((int64_t)outside_y * outside_y));
	const uint64_t radius_squared = (uint64_t)((int64_t)body->radius * body->radius);
	return distance_squared < radius_squared;
}

static picosystem_physics_fixed_t
sensor_projection_radius(const struct picosystem_physics_box_sensor *sensor,
			 const struct picosystem_physics_vector *axis)
{
	return fixed_multiply(fixed_absolute(axis->x), sensor->half_extent.x) +
	       fixed_multiply(fixed_absolute(axis->y), sensor->half_extent.y);
}

static bool box_overlaps_sensor(const struct picosystem_physics_body *body,
				const struct box_geometry *geometry,
				const struct picosystem_physics_box_sensor *sensor)
{
	const struct picosystem_physics_vector unit_x = {
		.x = PICOSYSTEM_PHYSICS_FIXED_ONE,
	};
	const struct picosystem_physics_vector unit_y = {
		.y = PICOSYSTEM_PHYSICS_FIXED_ONE,
	};
	const struct picosystem_physics_vector axes[] = {
		unit_x,
		unit_y,
		geometry->axis_x,
		geometry->axis_y,
	};
	const struct picosystem_physics_vector delta =
		vector_subtract(&body->center, &sensor->center);
	for (size_t index = 0U; index < (sizeof(axes) / sizeof(axes[0])); ++index) {
		const picosystem_physics_fixed_t distance =
			fixed_absolute(vector_dot(&delta, &axes[index]));
		const picosystem_physics_fixed_t radius =
			box_projection_radius(body, geometry, &axes[index]) +
			sensor_projection_radius(sensor, &axes[index]);
		if (distance >= radius) {
			return false;
		}
	}
	return true;
}

static bool point_is_inside_sensor(const struct picosystem_physics_vector *point,
				   const struct picosystem_physics_box_sensor *sensor)
{
	return (fixed_absolute(point->x - sensor->center.x) <= sensor->half_extent.x) &&
	       (fixed_absolute(point->y - sensor->center.y) <= sensor->half_extent.y);
}

static bool capsule_overlaps_sensor(const struct picosystem_physics_body *body,
				    const struct box_geometry *geometry,
				    const struct picosystem_physics_box_sensor *sensor)
{
	struct picosystem_physics_vector start;
	struct picosystem_physics_vector end;
	capsule_centerline_from_geometry(body, geometry, &start, &end);
	if (point_is_inside_sensor(&start, sensor) || point_is_inside_sensor(&end, sensor)) {
		return true;
	}

	const picosystem_physics_fixed_t left = sensor->center.x - sensor->half_extent.x;
	const picosystem_physics_fixed_t right = sensor->center.x + sensor->half_extent.x;
	const picosystem_physics_fixed_t top = sensor->center.y - sensor->half_extent.y;
	const picosystem_physics_fixed_t bottom = sensor->center.y + sensor->half_extent.y;
	const struct picosystem_physics_vector corners[] = {
		{.x = left, .y = top},
		{.x = right, .y = top},
		{.x = right, .y = bottom},
		{.x = left, .y = bottom},
	};
	const uint64_t radius_squared = (uint64_t)((int64_t)body->radius * body->radius);
	for (size_t index = 0U; index < 4U; ++index) {
		const size_t next = (index + 1U) % 4U;
		const struct segment_closest_result closest = closest_points_between_segments(
			&start, &end, &corners[index], &corners[next]);
		if (closest.distance_squared_raw < radius_squared) {
			return true;
		}
	}
	return false;
}

static bool body_overlaps_sensor(const struct picosystem_physics_body *body,
				 const struct box_geometry *geometry,
				 const struct picosystem_physics_box_sensor *sensor)
{
	if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_CIRCLE) {
		return circle_overlaps_sensor(body, sensor);
	}
	if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_CAPSULE) {
		return capsule_overlaps_sensor(body, geometry, sensor);
	}
	return box_overlaps_sensor(body, geometry, sensor);
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
			      uint8_t static_segment_mask, uint8_t box_sensor_mask)
{
	for (uint16_t row = range->minimum_row; row <= range->maximum_row; ++row) {
		for (uint16_t column = range->minimum_column; column <= range->maximum_column;
		     ++column) {
			const size_t index = (row * PICOSYSTEM_PHYSICS_GRID_COLUMNS) + column;
			struct picosystem_physics_grid_cell *const cell = &world->grid_cells[index];
			if ((cell->body_mask == 0U) && (cell->static_segment_mask == 0U) &&
			    (cell->box_sensor_mask == 0U)) {
				++world->last_occupied_grid_cell_count;
				++world->last_work.occupied_grid_cell_count;
			}
			cell->body_mask |= body_mask;
			cell->static_segment_mask |= static_segment_mask;
			cell->box_sensor_mask |= box_sensor_mask;
			++world->last_work.grid_cell_insertion_count;
			const uint32_t occupancy =
				(uint32_t)__builtin_popcount((unsigned int)cell->body_mask) +
				(uint32_t)__builtin_popcount(
					(unsigned int)cell->static_segment_mask) +
				(uint32_t)__builtin_popcount((unsigned int)cell->box_sensor_mask);
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
			candidates->box_sensor_masks[body_index] |= cell->box_sensor_mask;
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
		occupy_grid_range(world, &range, (uint16_t)(UINT16_C(1) << body_index), 0U, 0U);
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
		occupy_grid_range(world, &range, 0U, (uint8_t)(UINT8_C(1) << segment_index), 0U);
	}

	for (uint8_t sensor_index = 0U; sensor_index < world->box_sensor_count; ++sensor_index) {
		struct physics_aabb aabb;
		sensor_aabb(&world->box_sensors[sensor_index], &aabb);
		struct physics_grid_range range;
		if (!grid_range_from_aabb(&aabb, &range)) {
			clear_grid(world);
			return false;
		}
		occupy_grid_range(world, &range, 0U, 0U, (uint8_t)(UINT8_C(1) << sensor_index));
	}

	collect_grid_candidates(world, candidates);
	return true;
}

static uint32_t possible_pair_count(const struct picosystem_physics_world *world)
{
	const uint32_t body_count = world->body_count;
	const uint32_t body_pair_count =
		(body_count < 2U) ? 0U : (body_count * (body_count - 1U)) / 2U;
	return body_pair_count + (body_count * world->static_segment_count) +
	       (body_count * world->box_sensor_count);
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
	for (uint16_t index = 0U; index < world->prismatic_joint_count; ++index) {
		const struct picosystem_physics_prismatic_joint *const joint =
			&world->prismatic_joints[index];
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

static int append_contact_event(struct picosystem_physics_world *world, uint16_t body_a_id,
				uint16_t body_b_id, uint8_t type, bool was_active, bool is_active)
{
	if (!was_active && !is_active) {
		return 0;
	}
	if (world->contact_event_count >= PICOSYSTEM_PHYSICS_MAX_CONTACT_EVENTS) {
		return -EOVERFLOW;
	}

	uint8_t phase = PICOSYSTEM_PHYSICS_CONTACT_EVENT_STAY;
	if (!was_active) {
		phase = PICOSYSTEM_PHYSICS_CONTACT_EVENT_BEGIN;
		++world->last_work.contact_begin_event_count;
	} else if (!is_active) {
		phase = PICOSYSTEM_PHYSICS_CONTACT_EVENT_END;
		++world->last_work.contact_end_event_count;
	} else {
		++world->last_work.contact_stay_event_count;
	}
	if (is_active) {
		++world->last_work.active_contact_pair_count;
	}

	world->contact_events[world->contact_event_count++] =
		(struct picosystem_physics_contact_event){
			.body_a_id = body_a_id,
			.body_b_id = body_b_id,
			.type = type,
			.phase = phase,
		};
	return 0;
}

static int publish_contact_events(struct picosystem_physics_world *world,
				  const struct physics_contact_pair_masks *current)
{
	world->contact_event_count = 0U;
	for (uint8_t body_a = 0U; body_a < world->body_count; ++body_a) {
		uint16_t body_mask =
			world->active_body_contact_masks[body_a] | current->body_masks[body_a];
		while (body_mask != 0U) {
			const uint8_t body_b = (uint8_t)__builtin_ctz((unsigned int)body_mask);
			const uint16_t mask = (uint16_t)(UINT16_C(1) << body_b);
			const int err = append_contact_event(
				world, world->bodies[body_a].id, world->bodies[body_b].id,
				PICOSYSTEM_PHYSICS_CONTACT_EVENT_BODY_BODY,
				(world->active_body_contact_masks[body_a] & mask) != 0U,
				(current->body_masks[body_a] & mask) != 0U);
			if (err != 0) {
				return err;
			}
			body_mask &= (uint16_t)(body_mask - UINT16_C(1));
		}

		uint8_t segment_mask = world->active_segment_contact_masks[body_a] |
				       current->static_segment_masks[body_a];
		while (segment_mask != 0U) {
			const uint8_t segment = (uint8_t)__builtin_ctz((unsigned int)segment_mask);
			const uint8_t mask = (uint8_t)(UINT8_C(1) << segment);
			const int err = append_contact_event(
				world, world->bodies[body_a].id, world->static_segments[segment].id,
				PICOSYSTEM_PHYSICS_CONTACT_EVENT_BODY_STATIC_SEGMENT,
				(world->active_segment_contact_masks[body_a] & mask) != 0U,
				(current->static_segment_masks[body_a] & mask) != 0U);
			if (err != 0) {
				return err;
			}
			segment_mask &= (uint8_t)(segment_mask - UINT8_C(1));
		}

		uint8_t sensor_mask = world->active_sensor_contact_masks[body_a] |
				      current->box_sensor_masks[body_a];
		while (sensor_mask != 0U) {
			const uint8_t sensor = (uint8_t)__builtin_ctz((unsigned int)sensor_mask);
			const uint8_t mask = (uint8_t)(UINT8_C(1) << sensor);
			const int err = append_contact_event(
				world, world->bodies[body_a].id, world->box_sensors[sensor].id,
				PICOSYSTEM_PHYSICS_CONTACT_EVENT_BODY_BOX_SENSOR,
				(world->active_sensor_contact_masks[body_a] & mask) != 0U,
				(current->box_sensor_masks[body_a] & mask) != 0U);
			if (err != 0) {
				return err;
			}
			sensor_mask &= (uint8_t)(sensor_mask - UINT8_C(1));
		}
	}

	memcpy(world->active_body_contact_masks, current->body_masks,
	       sizeof(world->active_body_contact_masks));
	memcpy(world->active_segment_contact_masks, current->static_segment_masks,
	       sizeof(world->active_segment_contact_masks));
	memcpy(world->active_sensor_contact_masks, current->box_sensor_masks,
	       sizeof(world->active_sensor_contact_masks));
	return 0;
}

static int build_contacts(struct picosystem_physics_world *world, bool force_brute_force,
			  struct physics_step_profiler *profiler,
			  struct physics_contact_pair_masks *contact_pairs)
{
	world->contact_count = 0U;
	memset(contact_pairs, 0, sizeof(*contact_pairs));
	world->last_candidate_pair_count = 0U;
	world->last_possible_pair_count = possible_pair_count(world);
	world->last_work.possible_pair_count = world->last_possible_pair_count;
	uint32_t section_start = profiler_section_begin(profiler);
	struct box_geometry geometries[PICOSYSTEM_PHYSICS_MAX_BODIES] = {0};
	for (uint8_t body_index = 0U; body_index < world->body_count; ++body_index) {
		if (world->bodies[body_index].shape != PICOSYSTEM_PHYSICS_SHAPE_CIRCLE) {
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
				contact_pairs->body_masks[body_a] |= body_b_mask;
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
				contact_pairs->static_segment_masks[body_a] |= segment_mask;
				++world->last_work.manifold_count;
			}
		}
		profiler_section_end(profiler, PICOSYSTEM_PHYSICS_PROFILE_NARROW_BODY_SEGMENT,
				     section_start);

		section_start = profiler_section_begin(profiler);
		for (uint8_t sensor = 0U; sensor < world->box_sensor_count; ++sensor) {
			const uint8_t sensor_mask = (uint8_t)(UINT8_C(1) << sensor);
			if (!use_brute_force &&
			    ((candidates.box_sensor_masks[body_a] & sensor_mask) == 0U)) {
				continue;
			}
			++world->last_candidate_pair_count;
			++world->last_work.candidate_pair_count;
			++world->last_work.body_sensor_narrow_phase_test_count;
			if (body_overlaps_sensor(&world->bodies[body_a], &geometries[body_a],
						 &world->box_sensors[sensor])) {
				contact_pairs->box_sensor_masks[body_a] |= sensor_mask;
				++world->last_work.sensor_overlap_count;
			}
		}
		profiler_section_end(profiler, PICOSYSTEM_PHYSICS_PROFILE_NARROW_BODY_SENSOR,
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

static void apply_body_impulse(struct picosystem_physics_world *world, uint8_t body_index,
			       const struct picosystem_physics_vector *point,
			       const struct picosystem_physics_vector *direction,
			       picosystem_physics_fixed_t impulse, picosystem_physics_fixed_t sign)
{
	struct picosystem_physics_body *const body = &world->bodies[body_index];
	const picosystem_physics_fixed_t signed_impulse = fixed_multiply(impulse, sign);
	const picosystem_physics_fixed_t velocity_change =
		fixed_multiply(signed_impulse, body->inverse_mass);
	const picosystem_physics_fixed_t velocity_change_x =
		fixed_multiply(direction->x, velocity_change);
	const picosystem_physics_fixed_t velocity_change_y =
		fixed_multiply(direction->y, velocity_change);
	body->velocity_per_tick.x += velocity_change_x;
	body->velocity_per_tick.y += velocity_change_y;

	const struct picosystem_physics_vector lever = vector_subtract(point, &body->center);
	const picosystem_physics_fixed_t angular_impulse =
		fixed_multiply(vector_cross(&lever, direction), signed_impulse);
	const picosystem_physics_fixed_t angular_velocity_change =
		fixed_multiply(body->inverse_inertia, angular_impulse);
	body->angular_velocity_per_tick += angular_velocity_change;
	if ((velocity_change_x != 0) || (velocity_change_y != 0) ||
	    (angular_velocity_change != 0)) {
		++world->solver_velocity_revisions[body_index];
	}
}

static void apply_body_vector_impulse(struct picosystem_physics_world *world, uint8_t body_index,
				      const struct picosystem_physics_vector *point,
				      const struct picosystem_physics_vector *impulse, bool negate)
{
	struct picosystem_physics_body *const body = &world->bodies[body_index];
	const struct picosystem_physics_vector signed_impulse =
		negate ? vector_negate(impulse) : *impulse;
	const picosystem_physics_fixed_t velocity_change_x =
		fixed_multiply(signed_impulse.x, body->inverse_mass);
	const picosystem_physics_fixed_t velocity_change_y =
		fixed_multiply(signed_impulse.y, body->inverse_mass);
	body->velocity_per_tick.x += velocity_change_x;
	body->velocity_per_tick.y += velocity_change_y;

	const struct picosystem_physics_vector lever = vector_subtract(point, &body->center);
	const picosystem_physics_fixed_t angular_impulse = vector_cross(&lever, &signed_impulse);
	const picosystem_physics_fixed_t angular_velocity_change =
		fixed_multiply(body->inverse_inertia, angular_impulse);
	body->angular_velocity_per_tick += angular_velocity_change;
	if ((velocity_change_x != 0) || (velocity_change_y != 0) ||
	    (angular_velocity_change != 0)) {
		++world->solver_velocity_revisions[body_index];
	}
}

static void apply_contact_impulse(struct picosystem_physics_world *world,
				  const struct picosystem_physics_contact *contact,
				  const struct picosystem_physics_vector *direction,
				  picosystem_physics_fixed_t impulse)
{
	apply_body_impulse(world, contact->body_a_index, &contact->point, direction, impulse,
			   -PICOSYSTEM_PHYSICS_FIXED_ONE);
	if (contact->type == PICOSYSTEM_PHYSICS_CONTACT_BODY) {
		apply_body_impulse(world, contact->body_b_index, &contact->point, direction,
				   impulse, PICOSYSTEM_PHYSICS_FIXED_ONE);
	}
}

static bool contact_solved_velocity_matches(const struct picosystem_physics_world *world,
					    const struct picosystem_physics_contact *contact)
{
	if (contact->solved_velocity_valid == 0U) {
		return false;
	}

	if (world->solver_velocity_revisions[contact->body_a_index] !=
	    contact->solved_velocity_revision_a) {
		return false;
	}
	if (contact->type == PICOSYSTEM_PHYSICS_CONTACT_STATIC_SEGMENT) {
		return true;
	}

	return world->solver_velocity_revisions[contact->body_b_index] ==
	       contact->solved_velocity_revision_b;
}

static void cache_contact_solved_velocity(const struct picosystem_physics_world *world,
					  struct picosystem_physics_contact *contact)
{
	contact->solved_velocity_revision_a =
		world->solver_velocity_revisions[contact->body_a_index];
	contact->solved_velocity_revision_b = 0U;
	if (contact->type == PICOSYSTEM_PHYSICS_CONTACT_BODY) {
		contact->solved_velocity_revision_b =
			world->solver_velocity_revisions[contact->body_b_index];
	}
	contact->solved_velocity_valid = 1U;
}

static bool contact_has_conveyor(const struct picosystem_physics_world *world,
				 const struct picosystem_physics_contact *contact)
{
	return (contact->type == PICOSYSTEM_PHYSICS_CONTACT_STATIC_SEGMENT) &&
	       (world->static_segments[contact->segment_index].surface_speed_per_tick != 0);
}

static picosystem_physics_fixed_t
contact_surface_tangent_velocity(const struct picosystem_physics_world *world,
				 const struct picosystem_physics_contact *contact,
				 const struct picosystem_physics_vector *contact_tangent)
{
	if (!contact_has_conveyor(world, contact)) {
		return 0;
	}

	const struct picosystem_physics_static_segment *const segment =
		&world->static_segments[contact->segment_index];
	const struct picosystem_physics_vector segment_tangent = {
		.x = segment->normal.y,
		.y = -segment->normal.x,
	};
	const struct picosystem_physics_vector surface_velocity =
		vector_scale(&segment_tangent, segment->surface_speed_per_tick);
	return vector_dot(&surface_velocity, contact_tangent);
}

static bool solve_contact_velocity(struct picosystem_physics_world *world,
				   struct picosystem_physics_contact *contact)
{
	const bool conveyor = contact_has_conveyor(world, contact);
	if (conveyor) {
		++world->last_work.conveyor_solver_visit_count;
	}
	if (contact_solved_velocity_matches(world, contact)) {
		++world->last_work.solver_cached_contact_count;
		return false;
	}

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
	const picosystem_physics_fixed_t tangent_velocity =
		vector_dot(&relative, &tangent) +
		contact_surface_tangent_velocity(world, contact, &tangent);
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
	if (conveyor && (applied_tangent != 0)) {
		++world->last_work.conveyor_solver_changed_count;
	}
	cache_contact_solved_velocity(world, contact);
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
	const picosystem_physics_fixed_t distance = distance_joint_geometry(
		world, joint, &joint->world_anchor_a, &joint->world_anchor_b, &joint->normal);
	joint->direction_inverse_mass = distance_joint_direction_inverse_mass(
		world, joint, &joint->world_anchor_a, &joint->world_anchor_b, &joint->normal);
	joint->accumulated_impulse = 0;
	joint->spring_softness = 0;
	joint->spring_bias_velocity = 0;
	if (joint->spring_enabled == 0U) {
		return;
	}

	const picosystem_physics_fixed_t effective_mass =
		fixed_divide(PICOSYSTEM_PHYSICS_FIXED_ONE, joint->direction_inverse_mass);
	const picosystem_physics_fixed_t angular_frequency_squared = fixed_multiply(
		joint->spring_angular_frequency_per_tick, joint->spring_angular_frequency_per_tick);
	const picosystem_physics_fixed_t stiffness =
		fixed_multiply(effective_mass, angular_frequency_squared);
	const picosystem_physics_fixed_t damping = fixed_multiply(
		effective_mass, fixed_multiply(joint->spring_damping_ratio * 2,
					       joint->spring_angular_frequency_per_tick));
	joint->spring_softness = fixed_divide(PICOSYSTEM_PHYSICS_FIXED_ONE, damping + stiffness);
	joint->spring_bias_velocity =
		fixed_multiply(distance - joint->target_distance,
			       fixed_multiply(stiffness, joint->spring_softness));
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
	picosystem_physics_fixed_t impulse;
	if (joint->spring_enabled != 0U) {
		const picosystem_physics_fixed_t softness_impulse =
			fixed_multiply(joint->spring_softness, joint->accumulated_impulse);
		impulse = fixed_divide(-(velocity + joint->spring_bias_velocity + softness_impulse),
				       joint->direction_inverse_mass + joint->spring_softness);
		const picosystem_physics_fixed_t previous_impulse = joint->accumulated_impulse;
		joint->accumulated_impulse = fixed_clamp(previous_impulse + impulse,
							 -joint->maximum_spring_impulse_per_tick,
							 joint->maximum_spring_impulse_per_tick);
		impulse = joint->accumulated_impulse - previous_impulse;
	} else {
		impulse = fixed_divide(-velocity, joint->direction_inverse_mass);
		joint->accumulated_impulse += impulse;
	}
	apply_body_impulse(world, joint->body_a_index, &joint->world_anchor_a, &joint->normal,
			   impulse, -PICOSYSTEM_PHYSICS_FIXED_ONE);
	if (joint->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		apply_body_impulse(world, joint->body_b_index, &joint->world_anchor_b,
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
		if (revolute_joint_is_sleeping(world, &world->revolute_joints[index])) {
			continue;
		}
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
		if (revolute_joint_is_sleeping(world, &world->revolute_joints[index])) {
			continue;
		}
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
	const picosystem_physics_fixed_t change_a =
		fixed_multiply(body_a->inverse_inertia, impulse);
	body_a->angular_velocity_per_tick += change_a;
	if (change_a != 0) {
		++world->solver_velocity_revisions[joint->body_a_index];
	}
	if (joint->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		struct picosystem_physics_body *const body_b = &world->bodies[joint->body_b_index];
		const picosystem_physics_fixed_t change_b =
			-fixed_multiply(body_b->inverse_inertia, impulse);
		body_b->angular_velocity_per_tick += change_b;
		if (change_b != 0) {
			++world->solver_velocity_revisions[joint->body_b_index];
		}
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
		apply_body_vector_impulse(world, joint->body_a_index, &joint->world_anchor_a,
					  &impulse, true);
		if (joint->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
			apply_body_vector_impulse(world, joint->body_b_index,
						  &joint->world_anchor_b, &impulse, false);
		}
		changed = (impulse.x != 0) || (impulse.y != 0);
	}
	changed |= solve_revolute_joint_motor(world, joint);
	changed |= solve_revolute_joint_limit(world, joint);
	return changed;
}

static void apply_prismatic_joint_angular_position_impulse(
	struct picosystem_physics_world *world,
	const struct picosystem_physics_prismatic_joint *joint, picosystem_physics_fixed_t impulse)
{
	struct picosystem_physics_body *const body_a = &world->bodies[joint->body_a_index];
	apply_body_angle_delta(body_a, fixed_multiply(body_a->inverse_inertia, impulse));
	if (joint->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		struct picosystem_physics_body *const body_b = &world->bodies[joint->body_b_index];
		apply_body_angle_delta(body_b, -fixed_multiply(body_b->inverse_inertia, impulse));
	}
}

static bool apply_prismatic_joint_direction_position_correction(
	struct picosystem_physics_world *world,
	const struct picosystem_physics_prismatic_joint *joint,
	const struct picosystem_physics_vector *world_anchor_a,
	const struct picosystem_physics_vector *world_anchor_b,
	const struct picosystem_physics_vector *direction, picosystem_physics_fixed_t error)
{
	if (fixed_absolute(error) <= PHYSICS_JOINT_POSITION_SLOP) {
		return false;
	}
	error += (error > 0) ? -PHYSICS_JOINT_POSITION_SLOP : PHYSICS_JOINT_POSITION_SLOP;
	error = fixed_clamp(error, -PHYSICS_JOINT_MAX_CORRECTION, PHYSICS_JOINT_MAX_CORRECTION);
	const picosystem_physics_fixed_t correction =
		-fixed_multiply(error, PHYSICS_JOINT_CORRECTION_SCALE);
	const picosystem_physics_fixed_t inverse_mass = prismatic_joint_direction_inverse_mass(
		world, joint, world_anchor_a, world_anchor_b, direction);
	const picosystem_physics_fixed_t impulse = fixed_divide(correction, inverse_mass);
	apply_body_position_impulse(&world->bodies[joint->body_a_index], world_anchor_a, direction,
				    impulse, PICOSYSTEM_PHYSICS_FIXED_ONE);
	if (joint->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		apply_body_position_impulse(&world->bodies[joint->body_b_index], world_anchor_b,
					    direction, impulse, -PICOSYSTEM_PHYSICS_FIXED_ONE);
	}
	return impulse != 0;
}

static bool apply_prismatic_joint_lateral_position_correction(
	struct picosystem_physics_world *world,
	const struct picosystem_physics_prismatic_joint *joint)
{
	struct picosystem_physics_vector world_anchor_a;
	struct picosystem_physics_vector world_anchor_b;
	struct picosystem_physics_vector world_axis;
	prismatic_joint_geometry(world, joint, &world_anchor_a, &world_anchor_b, &world_axis);
	const struct picosystem_physics_vector perpendicular = {
		.x = -world_axis.y,
		.y = world_axis.x,
	};
	const struct picosystem_physics_vector delta =
		vector_subtract(&world_anchor_a, &world_anchor_b);
	const picosystem_physics_fixed_t error = vector_dot(&delta, &perpendicular);
	return apply_prismatic_joint_direction_position_correction(
		world, joint, &world_anchor_a, &world_anchor_b, &perpendicular, error);
}

static bool apply_prismatic_joint_angular_position_correction(
	struct picosystem_physics_world *world,
	const struct picosystem_physics_prismatic_joint *joint)
{
	picosystem_physics_fixed_t error = prismatic_joint_relative_angle_radians(world, joint);
	if (fixed_absolute(error) <= PHYSICS_JOINT_ANGULAR_SLOP) {
		return false;
	}
	error += (error > 0) ? -PHYSICS_JOINT_ANGULAR_SLOP : PHYSICS_JOINT_ANGULAR_SLOP;
	error = fixed_clamp(error, -PHYSICS_JOINT_MAX_ANGULAR_CORRECTION,
			    PHYSICS_JOINT_MAX_ANGULAR_CORRECTION);
	const picosystem_physics_fixed_t correction = -error;
	const picosystem_physics_fixed_t impulse =
		fixed_multiply(correction, prismatic_joint_angular_effective_mass(world, joint));
	apply_prismatic_joint_angular_position_impulse(world, joint, impulse);
	return impulse != 0;
}

static picosystem_physics_fixed_t
prismatic_joint_limit_error(const struct picosystem_physics_world *world,
			    const struct picosystem_physics_prismatic_joint *joint)
{
	if (joint->limit_enabled == 0U) {
		return 0;
	}
	const picosystem_physics_fixed_t translation = prismatic_joint_translation(world, joint);
	if (joint->lower_translation == joint->upper_translation) {
		return translation - joint->lower_translation;
	}
	if (translation < joint->lower_translation) {
		return translation - joint->lower_translation;
	}
	if (translation > joint->upper_translation) {
		return translation - joint->upper_translation;
	}
	return 0;
}

static bool apply_prismatic_joint_limit_position_correction(
	struct picosystem_physics_world *world,
	const struct picosystem_physics_prismatic_joint *joint)
{
	if (joint->limit_enabled == 0U) {
		return false;
	}
	++world->last_work.joint_limit_position_correction_visit_count;
	const picosystem_physics_fixed_t error = prismatic_joint_limit_error(world, joint);
	if (fixed_absolute(error) <= PHYSICS_JOINT_POSITION_SLOP) {
		return false;
	}

	struct picosystem_physics_vector world_anchor_a;
	struct picosystem_physics_vector world_anchor_b;
	struct picosystem_physics_vector world_axis;
	prismatic_joint_geometry(world, joint, &world_anchor_a, &world_anchor_b, &world_axis);
	const bool changed = apply_prismatic_joint_direction_position_correction(
		world, joint, &world_anchor_a, &world_anchor_b, &world_axis, error);
	if (changed) {
		++world->last_work.joint_limit_position_correction_changed_count;
	}
	return changed;
}

static bool apply_prismatic_joint_position_pass(struct picosystem_physics_world *world,
						bool reverse)
{
	bool correction_changed = false;
	for (uint16_t visit = 0U; visit < world->prismatic_joint_count; ++visit) {
		const uint16_t index =
			reverse ? (uint16_t)(world->prismatic_joint_count - visit - 1U) : visit;
		const struct picosystem_physics_prismatic_joint *const joint =
			&world->prismatic_joints[index];
		if (prismatic_joint_is_sleeping(world, joint)) {
			continue;
		}
		correction_changed |=
			apply_prismatic_joint_lateral_position_correction(world, joint);
		correction_changed |=
			apply_prismatic_joint_angular_position_correction(world, joint);
		correction_changed |= apply_prismatic_joint_limit_position_correction(world, joint);
		++world->last_work.joint_position_correction_visit_count;
	}
	return correction_changed;
}

static bool prismatic_joint_positions_within_target(const struct picosystem_physics_world *world)
{
	for (uint16_t index = 0U; index < world->prismatic_joint_count; ++index) {
		const struct picosystem_physics_prismatic_joint *const joint =
			&world->prismatic_joints[index];
		if (prismatic_joint_is_sleeping(world, joint)) {
			continue;
		}
		struct picosystem_physics_vector world_anchor_a;
		struct picosystem_physics_vector world_anchor_b;
		struct picosystem_physics_vector world_axis;
		prismatic_joint_geometry(world, joint, &world_anchor_a, &world_anchor_b,
					 &world_axis);
		const struct picosystem_physics_vector perpendicular = {
			.x = -world_axis.y,
			.y = world_axis.x,
		};
		const struct picosystem_physics_vector delta =
			vector_subtract(&world_anchor_a, &world_anchor_b);
		if (fixed_absolute(vector_dot(&delta, &perpendicular)) >
		    PHYSICS_PRISMATIC_POSITION_TARGET) {
			return false;
		}
		if (fixed_absolute(prismatic_joint_relative_angle_radians(world, joint)) >
		    PHYSICS_JOINT_ANGULAR_SLOP) {
			return false;
		}
		if (fixed_absolute(prismatic_joint_limit_error(world, joint)) >
		    PHYSICS_PRISMATIC_POSITION_TARGET) {
			return false;
		}
	}
	return true;
}

static void prepare_prismatic_joint(struct picosystem_physics_world *world,
				    struct picosystem_physics_prismatic_joint *joint)
{
	prismatic_joint_geometry(world, joint, &joint->world_anchor_a, &joint->world_anchor_b,
				 &joint->world_axis);
	joint->world_perpendicular = (struct picosystem_physics_vector){
		.x = -joint->world_axis.y,
		.y = joint->world_axis.x,
	};
	const picosystem_physics_fixed_t lateral_inverse_mass =
		prismatic_joint_direction_inverse_mass(world, joint, &joint->world_anchor_a,
						       &joint->world_anchor_b,
						       &joint->world_perpendicular);
	const picosystem_physics_fixed_t axial_inverse_mass =
		prismatic_joint_direction_inverse_mass(world, joint, &joint->world_anchor_a,
						       &joint->world_anchor_b, &joint->world_axis);
	joint->lateral_effective_mass =
		fixed_divide(PICOSYSTEM_PHYSICS_FIXED_ONE, lateral_inverse_mass);
	joint->axial_effective_mass =
		fixed_divide(PICOSYSTEM_PHYSICS_FIXED_ONE, axial_inverse_mass);
	joint->angular_effective_mass = prismatic_joint_angular_effective_mass(world, joint);
	joint->accumulated_lateral_impulse = 0;
	joint->accumulated_angular_impulse = 0;
	joint->accumulated_motor_impulse = 0;
	joint->accumulated_limit_impulse = 0;
	joint->limit_state = PRISMATIC_LIMIT_INACTIVE;
	joint->solved_velocity_valid = 0U;
	if (joint->motor_enabled != 0U) {
		++world->last_work.prismatic_motor_count;
	}
	if (joint->limit_enabled == 0U) {
		return;
	}
	++world->last_work.prismatic_limit_count;
	const picosystem_physics_fixed_t translation = prismatic_joint_translation(world, joint);
	if (joint->lower_translation == joint->upper_translation) {
		joint->limit_state = PRISMATIC_LIMIT_EQUAL;
	} else if (translation <= (joint->lower_translation + PHYSICS_JOINT_POSITION_SLOP)) {
		joint->limit_state = PRISMATIC_LIMIT_LOWER;
	} else if (translation >= (joint->upper_translation - PHYSICS_JOINT_POSITION_SLOP)) {
		joint->limit_state = PRISMATIC_LIMIT_UPPER;
	}
}

static struct picosystem_physics_vector
prismatic_joint_relative_velocity(const struct picosystem_physics_world *world,
				  const struct picosystem_physics_prismatic_joint *joint)
{
	const struct picosystem_physics_vector velocity_a =
		body_velocity_at_point(&world->bodies[joint->body_a_index], &joint->world_anchor_a);
	if (joint->body_b_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		return velocity_a;
	}
	const struct picosystem_physics_vector velocity_b =
		body_velocity_at_point(&world->bodies[joint->body_b_index], &joint->world_anchor_b);
	return vector_subtract(&velocity_a, &velocity_b);
}

static picosystem_physics_fixed_t
prismatic_joint_relative_angular_velocity(const struct picosystem_physics_world *world,
					  const struct picosystem_physics_prismatic_joint *joint)
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
apply_prismatic_joint_linear_impulse(struct picosystem_physics_world *world,
				     const struct picosystem_physics_prismatic_joint *joint,
				     const struct picosystem_physics_vector *direction,
				     picosystem_physics_fixed_t impulse)
{
	apply_body_impulse(world, joint->body_a_index, &joint->world_anchor_a, direction, impulse,
			   PICOSYSTEM_PHYSICS_FIXED_ONE);
	if (joint->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		apply_body_impulse(world, joint->body_b_index, &joint->world_anchor_b, direction,
				   impulse, -PICOSYSTEM_PHYSICS_FIXED_ONE);
	}
}

static void
apply_prismatic_joint_angular_impulse(struct picosystem_physics_world *world,
				      const struct picosystem_physics_prismatic_joint *joint,
				      picosystem_physics_fixed_t impulse)
{
	struct picosystem_physics_body *const body_a = &world->bodies[joint->body_a_index];
	const picosystem_physics_fixed_t change_a =
		fixed_multiply(body_a->inverse_inertia, impulse);
	body_a->angular_velocity_per_tick += change_a;
	if (change_a != 0) {
		++world->solver_velocity_revisions[joint->body_a_index];
	}
	if (joint->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		struct picosystem_physics_body *const body_b = &world->bodies[joint->body_b_index];
		const picosystem_physics_fixed_t change_b =
			-fixed_multiply(body_b->inverse_inertia, impulse);
		body_b->angular_velocity_per_tick += change_b;
		if (change_b != 0) {
			++world->solver_velocity_revisions[joint->body_b_index];
		}
	}
}

static bool solve_prismatic_joint_motor(struct picosystem_physics_world *world,
					struct picosystem_physics_prismatic_joint *joint)
{
	if (joint->motor_enabled == 0U) {
		return false;
	}
	++world->last_work.joint_motor_solver_visit_count;
	const struct picosystem_physics_vector relative =
		prismatic_joint_relative_velocity(world, joint);
	const picosystem_physics_fixed_t axial_velocity = vector_dot(&relative, &joint->world_axis);
	const picosystem_physics_fixed_t velocity_error = fixed_difference_bounded(
		joint->motor_speed_per_tick, axial_velocity, PHYSICS_VELOCITY_LIMIT);
	const picosystem_physics_fixed_t impulse_delta = fixed_clamp(
		fixed_multiply(velocity_error, joint->axial_effective_mass),
		-joint->maximum_motor_impulse_per_tick, joint->maximum_motor_impulse_per_tick);
	const picosystem_physics_fixed_t previous = joint->accumulated_motor_impulse;
	joint->accumulated_motor_impulse =
		fixed_clamp(previous + impulse_delta, -joint->maximum_motor_impulse_per_tick,
			    joint->maximum_motor_impulse_per_tick);
	const picosystem_physics_fixed_t applied = joint->accumulated_motor_impulse - previous;
	apply_prismatic_joint_linear_impulse(world, joint, &joint->world_axis, applied);
	if (applied != 0) {
		++world->last_work.joint_motor_solver_changed_count;
	}
	return applied != 0;
}

static bool solve_prismatic_joint_limit(struct picosystem_physics_world *world,
					struct picosystem_physics_prismatic_joint *joint)
{
	if (joint->limit_state == PRISMATIC_LIMIT_INACTIVE) {
		return false;
	}
	++world->last_work.joint_limit_solver_visit_count;
	const struct picosystem_physics_vector relative =
		prismatic_joint_relative_velocity(world, joint);
	const picosystem_physics_fixed_t axial_velocity = vector_dot(&relative, &joint->world_axis);
	const picosystem_physics_fixed_t velocity_error =
		fixed_difference_bounded(0, axial_velocity, PHYSICS_VELOCITY_LIMIT);
	const picosystem_physics_fixed_t impulse_delta =
		fixed_clamp(fixed_multiply(velocity_error, joint->axial_effective_mass),
			    -PHYSICS_JOINT_LIMIT_IMPULSE_LIMIT, PHYSICS_JOINT_LIMIT_IMPULSE_LIMIT);
	const picosystem_physics_fixed_t previous = joint->accumulated_limit_impulse;
	const picosystem_physics_fixed_t candidate = previous + impulse_delta;
	if (joint->limit_state == PRISMATIC_LIMIT_LOWER) {
		joint->accumulated_limit_impulse =
			fixed_clamp(candidate, 0, PHYSICS_JOINT_LIMIT_IMPULSE_LIMIT);
	} else if (joint->limit_state == PRISMATIC_LIMIT_UPPER) {
		joint->accumulated_limit_impulse =
			fixed_clamp(candidate, -PHYSICS_JOINT_LIMIT_IMPULSE_LIMIT, 0);
	} else {
		joint->accumulated_limit_impulse =
			fixed_clamp(candidate, -PHYSICS_JOINT_LIMIT_IMPULSE_LIMIT,
				    PHYSICS_JOINT_LIMIT_IMPULSE_LIMIT);
	}
	const picosystem_physics_fixed_t applied = joint->accumulated_limit_impulse - previous;
	apply_prismatic_joint_linear_impulse(world, joint, &joint->world_axis, applied);
	if (applied != 0) {
		++world->last_work.joint_limit_solver_changed_count;
	}
	return applied != 0;
}

static bool
prismatic_joint_solved_velocity_matches(const struct picosystem_physics_world *world,
					const struct picosystem_physics_prismatic_joint *joint)
{
	if (joint->solved_velocity_valid == 0U) {
		return false;
	}

	if (world->solver_velocity_revisions[joint->body_a_index] !=
	    joint->solved_velocity_revision_a) {
		return false;
	}
	if (joint->body_b_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		return true;
	}

	return world->solver_velocity_revisions[joint->body_b_index] ==
	       joint->solved_velocity_revision_b;
}

static void cache_prismatic_joint_solved_velocity(const struct picosystem_physics_world *world,
						  struct picosystem_physics_prismatic_joint *joint)
{
	joint->solved_velocity_revision_a = world->solver_velocity_revisions[joint->body_a_index];
	joint->solved_velocity_revision_b = 0U;
	if (joint->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		joint->solved_velocity_revision_b =
			world->solver_velocity_revisions[joint->body_b_index];
	}
	joint->solved_velocity_valid = 1U;
}

static bool solve_prismatic_joint_velocity(struct picosystem_physics_world *world,
					   struct picosystem_physics_prismatic_joint *joint)
{
	if (prismatic_joint_solved_velocity_matches(world, joint)) {
		return false;
	}

	struct picosystem_physics_vector relative = prismatic_joint_relative_velocity(world, joint);
	const picosystem_physics_fixed_t lateral_velocity =
		vector_dot(&relative, &joint->world_perpendicular);
	const picosystem_physics_fixed_t lateral_impulse =
		fixed_multiply(-lateral_velocity, joint->lateral_effective_mass);
	joint->accumulated_lateral_impulse += lateral_impulse;
	apply_prismatic_joint_linear_impulse(world, joint, &joint->world_perpendicular,
					     lateral_impulse);

	const picosystem_physics_fixed_t relative_angular_velocity =
		prismatic_joint_relative_angular_velocity(world, joint);
	const picosystem_physics_fixed_t angular_impulse =
		fixed_multiply(-relative_angular_velocity, joint->angular_effective_mass);
	joint->accumulated_angular_impulse += angular_impulse;
	apply_prismatic_joint_angular_impulse(world, joint, angular_impulse);

	bool changed = (lateral_impulse != 0) || (angular_impulse != 0);
	changed |= solve_prismatic_joint_motor(world, joint);
	changed |= solve_prismatic_joint_limit(world, joint);
	cache_prismatic_joint_solved_velocity(world, joint);
	return changed;
}

static struct picosystem_physics_vector
rope_endpoint_world_position(const struct picosystem_physics_world *world,
			     const struct picosystem_physics_rope *rope, bool endpoint_a)
{
	const uint16_t body_id = endpoint_a ? rope->body_a_id : rope->body_b_id;
	const struct picosystem_physics_vector *const anchor =
		endpoint_a ? &rope->anchor_a : &rope->anchor_b;
	if (body_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		return *anchor;
	}
	const uint8_t body_index = endpoint_a ? rope->body_a_index : rope->body_b_index;
	return body_local_point_to_world(&world->bodies[body_index], anchor);
}

static bool rope_particle_is_pinned(const struct picosystem_physics_rope *rope,
				    uint8_t particle_index)
{
	return ((particle_index == 0U) && (rope->pin_a != 0U)) ||
	       ((particle_index == (rope->particle_count - 1U)) && (rope->pin_b != 0U));
}

static void pin_rope_endpoints(const struct picosystem_physics_world *world,
			       struct picosystem_physics_rope *rope,
			       const struct picosystem_physics_vector *position_a,
			       const struct picosystem_physics_vector *position_b)
{
	if (rope->pin_a != 0U) {
		const struct picosystem_physics_vector pinned_position =
			(rope->reaction_a != 0U) ? rope_endpoint_world_position(world, rope, true)
						 : *position_a;
		rope->particles[0].position = pinned_position;
		rope->particles[0].previous_position = pinned_position;
	}
	if (rope->pin_b != 0U) {
		struct picosystem_physics_rope_particle *const particle =
			&rope->particles[rope->particle_count - 1U];
		const struct picosystem_physics_vector pinned_position =
			(rope->reaction_b != 0U) ? rope_endpoint_world_position(world, rope, false)
						 : *position_b;
		particle->position = pinned_position;
		particle->previous_position = pinned_position;
	}
}

static void
integrate_rope_particles(const struct picosystem_physics_world *world,
			 struct picosystem_physics_rope *rope,
			 const struct picosystem_physics_vector *global_acceleration_per_tick,
			 const struct picosystem_physics_vector *pin_position_a,
			 const struct picosystem_physics_vector *pin_position_b)
{
	pin_rope_endpoints(world, rope, pin_position_a, pin_position_b);
	for (uint8_t index = 0U; index < rope->particle_count; ++index) {
		if (rope_particle_is_pinned(rope, index)) {
			continue;
		}
		struct picosystem_physics_rope_particle *const particle = &rope->particles[index];
		const struct picosystem_physics_vector raw_velocity =
			vector_subtract(&particle->position, &particle->previous_position);
		const struct picosystem_physics_vector bounded_velocity =
			clamp_vector_length(&raw_velocity, world->max_speed_per_tick);
		const struct picosystem_physics_vector damped_velocity =
			vector_scale(&bounded_velocity, PHYSICS_ROPE_VELOCITY_DAMPING);
		const struct picosystem_physics_vector previous = particle->position;
		const struct picosystem_physics_vector accelerated =
			vector_add(&damped_velocity, global_acceleration_per_tick);
		particle->position = vector_add(&particle->position, &accelerated);
		particle->previous_position = previous;
		clamp_rope_particle_position(particle);
	}
}

static bool rope_particle_has_body_reaction(const struct picosystem_physics_rope *rope,
					    uint8_t particle_index)
{
	return ((particle_index == 0U) && (rope->reaction_a != 0U)) ||
	       ((particle_index == (rope->particle_count - 1U)) && (rope->reaction_b != 0U));
}

static bool rope_particle_is_endpoint_a(uint8_t particle_index)
{
	return particle_index == 0U;
}

static picosystem_physics_fixed_t rope_particle_direction_inverse_mass(
	const struct picosystem_physics_world *world, const struct picosystem_physics_rope *rope,
	uint8_t particle_index, const struct picosystem_physics_vector *direction)
{
	if (!rope_particle_is_pinned(rope, particle_index)) {
		return PICOSYSTEM_PHYSICS_FIXED_ONE;
	}
	if (!rope_particle_has_body_reaction(rope, particle_index)) {
		return 0;
	}
	const bool endpoint_a = rope_particle_is_endpoint_a(particle_index);
	const uint8_t body_index = endpoint_a ? rope->body_a_index : rope->body_b_index;
	return body_direction_inverse_mass(&world->bodies[body_index],
					   &rope->particles[particle_index].position, direction);
}

static bool apply_rope_particle_position_correction(
	struct picosystem_physics_world *world, struct picosystem_physics_rope *rope,
	uint8_t particle_index, const struct picosystem_physics_vector *direction,
	picosystem_physics_fixed_t impulse, bool negate)
{
	if (impulse == 0) {
		return false;
	}
	if (!rope_particle_is_pinned(rope, particle_index)) {
		const struct picosystem_physics_vector correction =
			vector_scale(direction, impulse);
		if (negate) {
			rope->particles[particle_index].position = vector_subtract(
				&rope->particles[particle_index].position, &correction);
		} else {
			rope->particles[particle_index].position =
				vector_add(&rope->particles[particle_index].position, &correction);
		}
		return (correction.x != 0) || (correction.y != 0);
	}
	if (!rope_particle_has_body_reaction(rope, particle_index)) {
		return false;
	}

	const bool endpoint_a = rope_particle_is_endpoint_a(particle_index);
	const uint8_t body_index = endpoint_a ? rope->body_a_index : rope->body_b_index;
	struct picosystem_physics_body *const body = &world->bodies[body_index];
	const struct picosystem_physics_vector point = rope->particles[particle_index].position;
	const struct picosystem_physics_vector center_before = body->center;
	const uint32_t angle_before = body->angle_turns;
	apply_body_position_impulse(body, &point, direction, impulse,
				    negate ? -PICOSYSTEM_PHYSICS_FIXED_ONE
					   : PICOSYSTEM_PHYSICS_FIXED_ONE);
	const bool changed = (body->center.x != center_before.x) ||
			     (body->center.y != center_before.y) ||
			     (body->angle_turns != angle_before);
	if (changed) {
		(void)wake_sleeping_body_mask(world, body_mask_for_index(body_index), true);
	}
	return changed;
}

static bool solve_rope_constraint(struct picosystem_physics_world *world,
				  struct picosystem_physics_rope *rope, uint8_t particle_a_index)
{
	struct picosystem_physics_rope_particle *const particle_a =
		&rope->particles[particle_a_index];
	struct picosystem_physics_rope_particle *const particle_b =
		&rope->particles[particle_a_index + 1U];
	const struct picosystem_physics_vector delta =
		vector_subtract(&particle_b->position, &particle_a->position);
	const struct picosystem_physics_vector fallback = {
		.x = (((rope->id + particle_a_index) & 1U) == 0U) ? PICOSYSTEM_PHYSICS_FIXED_ONE
								  : -PICOSYSTEM_PHYSICS_FIXED_ONE,
	};
	struct picosystem_physics_vector normal;
	const picosystem_physics_fixed_t distance = normalize_vector(&delta, &normal, &fallback);
	picosystem_physics_fixed_t error = distance - rope->segment_length;
	if (error == 0) {
		world->last_work.rope_body_correction_visit_count +=
			rope_particle_has_body_reaction(rope, particle_a_index) ? 1U : 0U;
		world->last_work.rope_body_correction_visit_count +=
			rope_particle_has_body_reaction(rope, particle_a_index + 1U) ? 1U : 0U;
		return false;
	}
	error = fixed_clamp(error, -PHYSICS_ROPE_MAX_CORRECTION, PHYSICS_ROPE_MAX_CORRECTION);
	const bool reacts_a = rope_particle_has_body_reaction(rope, particle_a_index);
	const bool reacts_b = rope_particle_has_body_reaction(rope, particle_a_index + 1U);
	world->last_work.rope_body_correction_visit_count += reacts_a ? 1U : 0U;
	world->last_work.rope_body_correction_visit_count += reacts_b ? 1U : 0U;
	if (reacts_a || reacts_b) {
		const picosystem_physics_fixed_t inverse_mass_a =
			rope_particle_direction_inverse_mass(world, rope, particle_a_index,
							     &normal);
		const picosystem_physics_fixed_t inverse_mass_b =
			rope_particle_direction_inverse_mass(world, rope, particle_a_index + 1U,
							     &normal);
		const picosystem_physics_fixed_t inverse_mass_sum = inverse_mass_a + inverse_mass_b;
		if (inverse_mass_sum <= 0) {
			return false;
		}
		const picosystem_physics_fixed_t impulse = fixed_divide(error, inverse_mass_sum);
		const bool changed_a = apply_rope_particle_position_correction(
			world, rope, particle_a_index, &normal, impulse, false);
		const bool changed_b = apply_rope_particle_position_correction(
			world, rope, particle_a_index + 1U, &normal, impulse, true);
		world->last_work.rope_body_correction_changed_count +=
			(reacts_a && changed_a) ? 1U : 0U;
		world->last_work.rope_body_correction_changed_count +=
			(reacts_b && changed_b) ? 1U : 0U;
		return changed_a || changed_b;
	}

	const bool pinned_a = rope_particle_is_pinned(rope, particle_a_index);
	const bool pinned_b = rope_particle_is_pinned(rope, particle_a_index + 1U);
	if (pinned_a && pinned_b) {
		return false;
	}

	picosystem_physics_fixed_t correction_a = error;
	picosystem_physics_fixed_t correction_b = error;
	if (!pinned_a && !pinned_b) {
		correction_a /= 2;
		correction_b -= correction_a;
	}
	if (!pinned_a) {
		const struct picosystem_physics_vector correction =
			vector_scale(&normal, correction_a);
		particle_a->position = vector_add(&particle_a->position, &correction);
	}
	if (!pinned_b) {
		const struct picosystem_physics_vector correction =
			vector_scale(&normal, correction_b);
		particle_b->position = vector_subtract(&particle_b->position, &correction);
	}
	return true;
}

static struct picosystem_physics_vector
rope_particle_velocity(const struct picosystem_physics_world *world,
		       const struct picosystem_physics_rope *rope, uint8_t particle_index)
{
	if (!rope_particle_is_pinned(rope, particle_index)) {
		return vector_subtract(&rope->particles[particle_index].position,
				       &rope->particles[particle_index].previous_position);
	}
	const bool endpoint_a = rope_particle_is_endpoint_a(particle_index);
	const uint16_t body_id = endpoint_a ? rope->body_a_id : rope->body_b_id;
	if (body_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		return (struct picosystem_physics_vector){0};
	}
	const uint8_t body_index = endpoint_a ? rope->body_a_index : rope->body_b_index;
	return body_velocity_at_point(&world->bodies[body_index],
				      &rope->particles[particle_index].position);
}

static bool apply_rope_particle_velocity_impulse(struct picosystem_physics_world *world,
						 struct picosystem_physics_rope *rope,
						 uint8_t particle_index,
						 const struct picosystem_physics_vector *direction,
						 picosystem_physics_fixed_t impulse, bool negate)
{
	if (impulse == 0) {
		return false;
	}
	if (!rope_particle_is_pinned(rope, particle_index)) {
		const struct picosystem_physics_vector velocity_delta =
			vector_scale(direction, impulse);
		if (negate) {
			rope->particles[particle_index].previous_position =
				vector_add(&rope->particles[particle_index].previous_position,
					   &velocity_delta);
		} else {
			rope->particles[particle_index].previous_position =
				vector_subtract(&rope->particles[particle_index].previous_position,
						&velocity_delta);
		}
		return (velocity_delta.x != 0) || (velocity_delta.y != 0);
	}
	if (!rope_particle_has_body_reaction(rope, particle_index)) {
		return false;
	}
	const bool endpoint_a = rope_particle_is_endpoint_a(particle_index);
	const uint8_t body_index = endpoint_a ? rope->body_a_index : rope->body_b_index;
	const uint32_t revision_before = world->solver_velocity_revisions[body_index];
	apply_body_impulse(world, body_index, &rope->particles[particle_index].position, direction,
			   impulse,
			   negate ? -PICOSYSTEM_PHYSICS_FIXED_ONE : PICOSYSTEM_PHYSICS_FIXED_ONE);
	const bool changed = world->solver_velocity_revisions[body_index] != revision_before;
	if (changed) {
		(void)wake_sleeping_body_mask(world, body_mask_for_index(body_index), true);
	}
	return changed;
}

static bool solve_rope_body_velocity(struct picosystem_physics_world *world,
				     struct picosystem_physics_rope *rope, uint8_t particle_a_index)
{
	const uint8_t particle_b_index = particle_a_index + 1U;
	const bool reacts_a = rope_particle_has_body_reaction(rope, particle_a_index);
	const bool reacts_b = rope_particle_has_body_reaction(rope, particle_b_index);
	if (!reacts_a && !reacts_b) {
		return false;
	}
	world->last_work.rope_body_velocity_visit_count += reacts_a ? 1U : 0U;
	world->last_work.rope_body_velocity_visit_count += reacts_b ? 1U : 0U;
	const struct picosystem_physics_vector delta =
		vector_subtract(&rope->particles[particle_b_index].position,
				&rope->particles[particle_a_index].position);
	const struct picosystem_physics_vector fallback = {
		.x = (((rope->id + particle_a_index) & 1U) == 0U) ? PICOSYSTEM_PHYSICS_FIXED_ONE
								  : -PICOSYSTEM_PHYSICS_FIXED_ONE,
	};
	struct picosystem_physics_vector normal;
	(void)normalize_vector(&delta, &normal, &fallback);
	const struct picosystem_physics_vector velocity_a =
		rope_particle_velocity(world, rope, particle_a_index);
	const struct picosystem_physics_vector velocity_b =
		rope_particle_velocity(world, rope, particle_b_index);
	const struct picosystem_physics_vector relative = vector_subtract(&velocity_b, &velocity_a);
	const picosystem_physics_fixed_t constraint_velocity = vector_dot(&relative, &normal);
	if (constraint_velocity == 0) {
		return false;
	}
	const picosystem_physics_fixed_t inverse_mass_a =
		rope_particle_direction_inverse_mass(world, rope, particle_a_index, &normal);
	const picosystem_physics_fixed_t inverse_mass_b =
		rope_particle_direction_inverse_mass(world, rope, particle_b_index, &normal);
	const picosystem_physics_fixed_t inverse_mass_sum = inverse_mass_a + inverse_mass_b;
	if (inverse_mass_sum <= 0) {
		return false;
	}
	const picosystem_physics_fixed_t impulse =
		fixed_divide(constraint_velocity, inverse_mass_sum);
	const bool changed_a = apply_rope_particle_velocity_impulse(world, rope, particle_a_index,
								    &normal, impulse, false);
	const bool changed_b = apply_rope_particle_velocity_impulse(world, rope, particle_b_index,
								    &normal, impulse, true);
	world->last_work.rope_body_velocity_changed_count += (reacts_a && changed_a) ? 1U : 0U;
	world->last_work.rope_body_velocity_changed_count += (reacts_b && changed_b) ? 1U : 0U;
	return changed_a || changed_b;
}

struct rope_particle_collision {
	struct picosystem_physics_vector point;
	struct picosystem_physics_vector normal;
	picosystem_physics_fixed_t penetration;
	uint8_t body_index;
};

static picosystem_physics_fixed_t
rope_body_bounding_radius(const struct picosystem_physics_body *body)
{
	if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_BOX) {
		return body->half_extent.x + body->half_extent.y;
	}
	if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_CAPSULE) {
		return body->half_extent.x + body->radius;
	}
	return body->radius;
}

static bool
rope_particle_might_collide_with_body(const struct picosystem_physics_rope_particle *particle,
				      picosystem_physics_fixed_t collision_radius,
				      const struct picosystem_physics_body *body)
{
	const picosystem_physics_fixed_t maximum_distance =
		collision_radius + rope_body_bounding_radius(body);
	return (fixed_absolute(particle->position.x - body->center.x) < maximum_distance) &&
	       (fixed_absolute(particle->position.y - body->center.y) < maximum_distance);
}

static bool
rope_particle_might_collide_with_segment(const struct picosystem_physics_rope_particle *particle,
					 picosystem_physics_fixed_t collision_radius,
					 const struct picosystem_physics_static_segment *segment)
{
	const picosystem_physics_fixed_t minimum_x =
		fixed_minimum(particle->position.x, particle->previous_position.x) -
		collision_radius;
	const picosystem_physics_fixed_t maximum_x =
		fixed_maximum(particle->position.x, particle->previous_position.x) +
		collision_radius;
	const picosystem_physics_fixed_t minimum_y =
		fixed_minimum(particle->position.y, particle->previous_position.y) -
		collision_radius;
	const picosystem_physics_fixed_t maximum_y =
		fixed_maximum(particle->position.y, particle->previous_position.y) +
		collision_radius;
	return (maximum_x > fixed_minimum(segment->start.x, segment->end.x)) &&
	       (minimum_x < fixed_maximum(segment->start.x, segment->end.x)) &&
	       (maximum_y > fixed_minimum(segment->start.y, segment->end.y)) &&
	       (minimum_y < fixed_maximum(segment->start.y, segment->end.y));
}

static bool find_rope_particle_circle_collision(const struct picosystem_physics_rope *rope,
						uint8_t particle_index,
						const struct picosystem_physics_body *body,
						uint8_t body_index,
						struct rope_particle_collision *collision)
{
	const struct picosystem_physics_vector delta =
		vector_subtract(&body->center, &rope->particles[particle_index].position);
	const picosystem_physics_fixed_t combined_radius = rope->collision_radius + body->radius;
	const uint64_t combined_radius_squared =
		(uint64_t)((int64_t)combined_radius * combined_radius);
	if (vector_length_squared_raw(&delta) >= combined_radius_squared) {
		return false;
	}

	const struct picosystem_physics_vector fallback = {
		.x = (((uint32_t)rope->id + particle_index + body->id) & 1U) != 0U
			     ? PICOSYSTEM_PHYSICS_FIXED_ONE
			     : -PICOSYSTEM_PHYSICS_FIXED_ONE,
	};
	struct picosystem_physics_vector normal;
	const picosystem_physics_fixed_t distance = normalize_vector(&delta, &normal, &fallback);
	const struct picosystem_physics_vector surface_offset = vector_scale(&normal, body->radius);
	*collision = (struct rope_particle_collision){
		.point = vector_subtract(&body->center, &surface_offset),
		.normal = normal,
		.penetration = combined_radius - distance,
		.body_index = body_index,
	};
	return true;
}

static bool find_rope_particle_box_collision(const struct picosystem_physics_rope *rope,
					     uint8_t particle_index,
					     const struct picosystem_physics_body *body,
					     uint8_t body_index,
					     struct rope_particle_collision *collision)
{
	struct box_geometry geometry;
	box_geometry_from_body(body, &geometry);
	const struct picosystem_physics_vector relative =
		vector_subtract(&rope->particles[particle_index].position, &body->center);
	const picosystem_physics_fixed_t local_x = vector_dot(&relative, &geometry.axis_x);
	const picosystem_physics_fixed_t local_y = vector_dot(&relative, &geometry.axis_y);
	const picosystem_physics_fixed_t closest_x =
		fixed_clamp(local_x, -body->half_extent.x, body->half_extent.x);
	const picosystem_physics_fixed_t closest_y =
		fixed_clamp(local_y, -body->half_extent.y, body->half_extent.y);
	const struct picosystem_physics_vector offset_x = vector_scale(&geometry.axis_x, closest_x);
	const struct picosystem_physics_vector offset_y = vector_scale(&geometry.axis_y, closest_y);
	const struct picosystem_physics_vector center_with_x = vector_add(&body->center, &offset_x);
	struct picosystem_physics_vector closest = vector_add(&center_with_x, &offset_y);
	const struct picosystem_physics_vector local_particle_to_closest = {
		.x = closest_x - local_x,
		.y = closest_y - local_y,
	};
	const uint64_t distance_squared = vector_length_squared_raw(&local_particle_to_closest);
	const uint64_t radius_squared =
		(uint64_t)((int64_t)rope->collision_radius * rope->collision_radius);

	picosystem_physics_fixed_t penetration;
	struct picosystem_physics_vector normal;
	if (distance_squared != 0U) {
		if (distance_squared >= radius_squared) {
			return false;
		}
		const struct picosystem_physics_vector fallback = {
			.x = PICOSYSTEM_PHYSICS_FIXED_ONE,
		};
		struct picosystem_physics_vector local_normal;
		const picosystem_physics_fixed_t distance =
			normalize_vector(&local_particle_to_closest, &local_normal, &fallback);
		const struct picosystem_physics_vector normal_x =
			vector_scale(&geometry.axis_x, local_normal.x);
		const struct picosystem_physics_vector normal_y =
			vector_scale(&geometry.axis_y, local_normal.y);
		normal = vector_add(&normal_x, &normal_y);
		penetration = rope->collision_radius - distance;
	} else {
		const picosystem_physics_fixed_t distance_x =
			body->half_extent.x - fixed_absolute(local_x);
		const picosystem_physics_fixed_t distance_y =
			body->half_extent.y - fixed_absolute(local_y);
		if (distance_x <= distance_y) {
			const bool positive = local_x >= 0;
			const picosystem_physics_fixed_t face_x =
				positive ? body->half_extent.x : -body->half_extent.x;
			const struct picosystem_physics_vector outward =
				positive ? geometry.axis_x : vector_negate(&geometry.axis_x);
			normal = vector_negate(&outward);
			const struct picosystem_physics_vector face_offset_x =
				vector_scale(&geometry.axis_x, face_x);
			const struct picosystem_physics_vector face_offset_y =
				vector_scale(&geometry.axis_y, local_y);
			const struct picosystem_physics_vector face_with_x =
				vector_add(&body->center, &face_offset_x);
			closest = vector_add(&face_with_x, &face_offset_y);
			penetration = rope->collision_radius + distance_x;
		} else {
			const bool positive = local_y >= 0;
			const picosystem_physics_fixed_t face_y =
				positive ? body->half_extent.y : -body->half_extent.y;
			const struct picosystem_physics_vector outward =
				positive ? geometry.axis_y : vector_negate(&geometry.axis_y);
			normal = vector_negate(&outward);
			const struct picosystem_physics_vector face_offset_x =
				vector_scale(&geometry.axis_x, local_x);
			const struct picosystem_physics_vector face_offset_y =
				vector_scale(&geometry.axis_y, face_y);
			const struct picosystem_physics_vector face_with_x =
				vector_add(&body->center, &face_offset_x);
			closest = vector_add(&face_with_x, &face_offset_y);
			penetration = rope->collision_radius + distance_y;
		}
	}

	*collision = (struct rope_particle_collision){
		.point = closest,
		.normal = normal,
		.penetration = penetration,
		.body_index = body_index,
	};
	return true;
}

static bool find_rope_particle_capsule_collision(const struct picosystem_physics_rope *rope,
						 uint8_t particle_index,
						 const struct picosystem_physics_body *body,
						 uint8_t body_index,
						 struct rope_particle_collision *collision)
{
	struct box_geometry geometry;
	box_geometry_from_body(body, &geometry);
	struct picosystem_physics_vector start;
	struct picosystem_physics_vector end;
	capsule_centerline_from_geometry(body, &geometry, &start, &end);
	const struct picosystem_physics_vector *const position =
		&rope->particles[particle_index].position;
	const struct picosystem_physics_vector extent = vector_subtract(&end, &start);
	const struct picosystem_physics_vector from_start = vector_subtract(position, &start);
	const int64_t projection_raw =
		((int64_t)from_start.x * extent.x) + ((int64_t)from_start.y * extent.y);
	const int64_t length_squared_raw = (int64_t)vector_length_squared_raw(&extent);
	struct picosystem_physics_vector fallback = geometry.axis_y;
	if ((((uint32_t)rope->id + particle_index + body->id) & 1U) == 0U) {
		fallback = vector_negate(&fallback);
	}
	struct picosystem_physics_vector closest;
	struct picosystem_physics_vector normal;
	picosystem_physics_fixed_t distance;
	if ((projection_raw > 0) && (projection_raw < length_squared_raw)) {
		const picosystem_physics_fixed_t signed_distance =
			vector_dot(&from_start, &geometry.axis_y);
		distance = fixed_absolute(signed_distance);
		normal = (signed_distance > 0)   ? vector_negate(&geometry.axis_y)
			 : (signed_distance < 0) ? geometry.axis_y
						 : fallback;
		const struct picosystem_physics_vector offset = vector_scale(&normal, distance);
		closest = vector_add(position, &offset);
	} else {
		closest = (projection_raw <= 0) ? start : end;
		const struct picosystem_physics_vector delta = vector_subtract(&closest, position);
		distance = normalize_vector(&delta, &normal, &fallback);
	}
	const picosystem_physics_fixed_t combined_radius = rope->collision_radius + body->radius;
	const uint64_t combined_radius_squared =
		(uint64_t)((int64_t)combined_radius * combined_radius);
	if ((uint64_t)((int64_t)distance * distance) >= combined_radius_squared) {
		return false;
	}

	const struct picosystem_physics_vector surface_offset = vector_scale(&normal, body->radius);
	*collision = (struct rope_particle_collision){
		.point = vector_subtract(&closest, &surface_offset),
		.normal = normal,
		.penetration = combined_radius - distance,
		.body_index = body_index,
	};
	return true;
}

static bool find_rope_particle_body_collision(const struct picosystem_physics_rope *rope,
					      uint8_t particle_index,
					      const struct picosystem_physics_body *body,
					      uint8_t body_index,
					      struct rope_particle_collision *collision)
{
	if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_CIRCLE) {
		return find_rope_particle_circle_collision(rope, particle_index, body, body_index,
							   collision);
	}
	if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_CAPSULE) {
		return find_rope_particle_capsule_collision(rope, particle_index, body, body_index,
							    collision);
	}
	return find_rope_particle_box_collision(rope, particle_index, body, body_index, collision);
}

static bool
find_rope_particle_segment_collision(const struct picosystem_physics_rope *rope,
				     uint8_t particle_index,
				     const struct picosystem_physics_static_segment *segment,
				     struct rope_particle_collision *collision)
{
	const struct picosystem_physics_rope_particle *const particle =
		&rope->particles[particle_index];
	const struct picosystem_physics_vector *const position = &particle->position;
	/* A length correction may cross a zero-width segment completely; restore the prior side. */
	struct picosystem_physics_vector intersection;
	if (proper_segment_intersection(&particle->previous_position, position, &segment->start,
					&segment->end, &intersection)) {
		const struct picosystem_physics_vector previous_from_start =
			vector_subtract(&particle->previous_position, &segment->start);
		const struct picosystem_physics_vector current_from_start =
			vector_subtract(position, &segment->start);
		const picosystem_physics_fixed_t previous_side =
			vector_dot(&previous_from_start, &segment->normal);
		const picosystem_physics_fixed_t current_side =
			vector_dot(&current_from_start, &segment->normal);
		struct picosystem_physics_vector allowed_normal;
		if (previous_side > 0) {
			allowed_normal = segment->normal;
		} else if (previous_side < 0) {
			allowed_normal = vector_negate(&segment->normal);
		} else {
			allowed_normal = (current_side <= 0) ? segment->normal
							     : vector_negate(&segment->normal);
		}
		const struct picosystem_physics_vector from_intersection =
			vector_subtract(position, &intersection);
		const picosystem_physics_fixed_t allowed_distance =
			vector_dot(&from_intersection, &allowed_normal);
		const picosystem_physics_fixed_t penetration =
			rope->collision_radius - allowed_distance;
		if (penetration > 0) {
			*collision = (struct rope_particle_collision){
				.point = intersection,
				.normal = vector_negate(&allowed_normal),
				.penetration = penetration,
				.body_index = STATIC_BODY_INDEX,
			};
			return true;
		}
	}

	const struct picosystem_physics_vector extent =
		vector_subtract(&segment->end, &segment->start);
	const struct picosystem_physics_vector from_start =
		vector_subtract(position, &segment->start);
	const int64_t projection_raw =
		((int64_t)from_start.x * extent.x) + ((int64_t)from_start.y * extent.y);
	const int64_t length_squared_raw = (int64_t)vector_length_squared_raw(&extent);
	struct picosystem_physics_vector closest;
	struct picosystem_physics_vector normal;
	picosystem_physics_fixed_t distance;
	if ((projection_raw > 0) && (projection_raw < length_squared_raw)) {
		const picosystem_physics_fixed_t signed_distance =
			vector_dot(&from_start, &segment->normal);
		distance = fixed_absolute(signed_distance);
		normal = (signed_distance > 0) ? vector_negate(&segment->normal) : segment->normal;
		const struct picosystem_physics_vector offset = vector_scale(&normal, distance);
		closest = vector_add(position, &offset);
	} else {
		closest = (projection_raw <= 0) ? segment->start : segment->end;
		const struct picosystem_physics_vector delta = vector_subtract(&closest, position);
		distance = normalize_vector(&delta, &normal, &segment->normal);
	}
	const uint64_t radius_squared =
		(uint64_t)((int64_t)rope->collision_radius * rope->collision_radius);
	if ((uint64_t)((int64_t)distance * distance) >= radius_squared) {
		return false;
	}

	*collision = (struct rope_particle_collision){
		.point = closest,
		.normal = normal,
		.penetration = rope->collision_radius - distance,
		.body_index = STATIC_BODY_INDEX,
	};
	return true;
}

static bool apply_rope_particle_collision(struct picosystem_physics_world *world,
					  struct picosystem_physics_rope *rope,
					  uint8_t particle_index,
					  const struct rope_particle_collision *collision)
{
	struct picosystem_physics_rope_particle *const particle = &rope->particles[particle_index];
	picosystem_physics_fixed_t inverse_mass_sum = PICOSYSTEM_PHYSICS_FIXED_ONE;
	if (collision->body_index != STATIC_BODY_INDEX) {
		inverse_mass_sum +=
			body_direction_inverse_mass(&world->bodies[collision->body_index],
						    &collision->point, &collision->normal);
	}
	if (inverse_mass_sum <= 0) {
		return false;
	}

	const picosystem_physics_fixed_t bounded_penetration =
		fixed_minimum(collision->penetration, PHYSICS_ROPE_MAX_CORRECTION);
	const picosystem_physics_fixed_t position_impulse =
		fixed_divide(bounded_penetration, inverse_mass_sum);
	const struct picosystem_physics_vector particle_correction =
		vector_scale(&collision->normal, position_impulse);
	particle->position = vector_subtract(&particle->position, &particle_correction);
	particle->previous_position =
		vector_subtract(&particle->previous_position, &particle_correction);
	bool position_changed = (particle_correction.x != 0) || (particle_correction.y != 0);
	if (collision->body_index != STATIC_BODY_INDEX) {
		struct picosystem_physics_body *const body = &world->bodies[collision->body_index];
		const struct picosystem_physics_vector center_before = body->center;
		const uint32_t angle_before = body->angle_turns;
		apply_body_position_impulse(body, &collision->point, &collision->normal,
					    position_impulse, PICOSYSTEM_PHYSICS_FIXED_ONE);
		const bool body_changed = (body->center.x != center_before.x) ||
					  (body->center.y != center_before.y) ||
					  (body->angle_turns != angle_before);
		position_changed |= body_changed;
		if (body_changed) {
			(void)wake_sleeping_body_mask(
				world, body_mask_for_index(collision->body_index), true);
		}
	}
	world->last_work.rope_collision_position_changed_count += position_changed ? 1U : 0U;

	const struct picosystem_physics_vector particle_velocity =
		vector_subtract(&particle->position, &particle->previous_position);
	struct picosystem_physics_vector collider_velocity = {0};
	if (collision->body_index != STATIC_BODY_INDEX) {
		collider_velocity = body_velocity_at_point(&world->bodies[collision->body_index],
							   &collision->point);
	}
	const struct picosystem_physics_vector relative_velocity =
		vector_subtract(&collider_velocity, &particle_velocity);
	const picosystem_physics_fixed_t closing_velocity =
		vector_dot(&relative_velocity, &collision->normal);
	if (closing_velocity >= 0) {
		return position_changed;
	}

	inverse_mass_sum = PICOSYSTEM_PHYSICS_FIXED_ONE;
	if (collision->body_index != STATIC_BODY_INDEX) {
		inverse_mass_sum +=
			body_direction_inverse_mass(&world->bodies[collision->body_index],
						    &collision->point, &collision->normal);
	}
	const picosystem_physics_fixed_t velocity_impulse =
		fixed_divide(-closing_velocity, inverse_mass_sum);
	const struct picosystem_physics_vector particle_velocity_change =
		vector_scale(&collision->normal, velocity_impulse);
	particle->previous_position =
		vector_add(&particle->previous_position, &particle_velocity_change);
	bool velocity_changed =
		(particle_velocity_change.x != 0) || (particle_velocity_change.y != 0);
	if (collision->body_index != STATIC_BODY_INDEX) {
		const uint32_t revision_before =
			world->solver_velocity_revisions[collision->body_index];
		apply_body_impulse(world, collision->body_index, &collision->point,
				   &collision->normal, velocity_impulse,
				   PICOSYSTEM_PHYSICS_FIXED_ONE);
		const bool body_changed =
			world->solver_velocity_revisions[collision->body_index] != revision_before;
		velocity_changed |= body_changed;
		if (body_changed) {
			(void)wake_sleeping_body_mask(
				world, body_mask_for_index(collision->body_index), true);
		}
	}
	world->last_work.rope_collision_velocity_changed_count += velocity_changed ? 1U : 0U;
	return position_changed || velocity_changed;
}

static PICOSYSTEM_PHYSICS_RAMFUNC PICOSYSTEM_PHYSICS_NOINLINE void
solve_rope_particle_collisions(struct picosystem_physics_world *world,
			       struct picosystem_physics_rope *rope, uint8_t particle_index)
{
	for (uint8_t body_index = 0U; body_index < world->body_count; ++body_index) {
		++world->last_work.rope_collision_possible_pair_count;
		if (!rope_particle_might_collide_with_body(&rope->particles[particle_index],
							   rope->collision_radius,
							   &world->bodies[body_index])) {
			continue;
		}
		++world->last_work.rope_collision_candidate_pair_count;
		struct rope_particle_collision collision;
		if (find_rope_particle_body_collision(rope, particle_index,
						      &world->bodies[body_index], body_index,
						      &collision)) {
			++world->last_work.rope_collision_contact_count;
			(void)apply_rope_particle_collision(world, rope, particle_index,
							    &collision);
		}
	}
	for (uint8_t segment_index = 0U; segment_index < world->static_segment_count;
	     ++segment_index) {
		++world->last_work.rope_collision_possible_pair_count;
		if (!rope_particle_might_collide_with_segment(
			    &rope->particles[particle_index], rope->collision_radius,
			    &world->static_segments[segment_index])) {
			continue;
		}
		++world->last_work.rope_collision_candidate_pair_count;
		struct rope_particle_collision collision;
		if (find_rope_particle_segment_collision(rope, particle_index,
							 &world->static_segments[segment_index],
							 &collision)) {
			++world->last_work.rope_collision_contact_count;
			(void)apply_rope_particle_collision(world, rope, particle_index,
							    &collision);
		}
	}
}

static void step_ropes(struct picosystem_physics_world *world,
		       const struct picosystem_physics_vector *global_acceleration_per_tick)
{
	for (uint16_t rope_index = 0U; rope_index < world->rope_count; ++rope_index) {
		struct picosystem_physics_rope *const rope = &world->ropes[rope_index];
		struct picosystem_physics_vector pin_position_a = {0};
		struct picosystem_physics_vector pin_position_b = {0};
		if (rope->pin_a != 0U) {
			pin_position_a = rope_endpoint_world_position(world, rope, true);
		}
		if (rope->pin_b != 0U) {
			pin_position_b = rope_endpoint_world_position(world, rope, false);
		}
		integrate_rope_particles(world, rope, global_acceleration_per_tick, &pin_position_a,
					 &pin_position_b);
		for (uint8_t iteration = 0U; iteration < PICOSYSTEM_PHYSICS_ROPE_SOLVER_ITERATIONS;
		     ++iteration) {
			const bool reverse = (iteration & 1U) != 0U;
			for (uint8_t visit = 0U; visit < (rope->particle_count - 1U); ++visit) {
				const uint8_t particle_a_index =
					reverse ? (uint8_t)(rope->particle_count - visit - 2U)
						: visit;
				const bool changed =
					solve_rope_constraint(world, rope, particle_a_index);
				++world->last_work.rope_constraint_visit_count;
				world->last_work.rope_constraint_changed_count += changed ? 1U : 0U;
			}
			if ((rope->collision_radius != 0) && ((iteration & 1U) != 0U)) {
				const bool collision_reverse = ((iteration / 2U) & 1U) != 0U;
				for (uint8_t visit = 0U; visit < rope->particle_count; ++visit) {
					const uint8_t particle_index =
						collision_reverse ? (uint8_t)(rope->particle_count -
									      visit - 1U)
								  : visit;
					if (!rope_particle_is_pinned(rope, particle_index)) {
						solve_rope_particle_collisions(world, rope,
									       particle_index);
					}
				}
			}
			pin_rope_endpoints(world, rope, &pin_position_a, &pin_position_b);
			++world->last_work.rope_solver_iteration_count;
		}
		for (uint8_t index = 0U; index < rope->particle_count; ++index) {
			clamp_rope_particle_position(&rope->particles[index]);
		}
		for (uint8_t index = 0U; index < (rope->particle_count - 1U); ++index) {
			(void)solve_rope_body_velocity(world, rope, index);
		}
	}
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

int picosystem_physics_world_add_capsule(struct picosystem_physics_world *world,
					 const struct picosystem_physics_capsule_config *config)
{
	if ((world == NULL) || (config == NULL)) {
		return -EINVAL;
	}
	if (!world_is_valid(world) || !capsule_config_is_valid(config, world)) {
		return -ERANGE;
	}
	const int slot = body_slot_for_config(world, config->id);
	if (slot < 0) {
		return slot;
	}

	world->bodies[slot] = (struct picosystem_physics_body){
		.center = config->center,
		.velocity_per_tick = config->velocity_per_tick,
		.half_extent = {.x = config->half_length},
		.radius = config->radius,
		.inverse_mass = config->inverse_mass,
		.inverse_inertia = capsule_inverse_inertia(config->half_length, config->radius,
							   config->inverse_mass),
		.restitution = config->restitution,
		.friction = config->friction,
		.angular_velocity_per_tick = config->angular_velocity_per_tick,
		.angle_turns = config->angle_turns,
		.id = config->id,
		.shape = PICOSYSTEM_PHYSICS_SHAPE_CAPSULE,
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
		.surface_speed_per_tick = config->surface_speed_per_tick,
		.id = config->id,
	};
	segment_normal_from_endpoints(&segment->start, &segment->end, &segment->normal);
	++world->static_segment_count;
	(void)wake_sleeping_body_mask(world, configured_body_mask(world), false);
	return 0;
}

int picosystem_physics_world_add_box_sensor(
	struct picosystem_physics_world *world,
	const struct picosystem_physics_box_sensor_config *config)
{
	if ((world == NULL) || (config == NULL)) {
		return -EINVAL;
	}
	if (!world_is_valid(world) || !box_sensor_config_is_valid(config)) {
		return -ERANGE;
	}
	if (world->box_sensor_count >= PICOSYSTEM_PHYSICS_MAX_BOX_SENSORS) {
		return -ENOSPC;
	}
	for (uint16_t index = 0U; index < world->box_sensor_count; ++index) {
		if (world->box_sensors[index].id == config->id) {
			return -EEXIST;
		}
	}

	world->box_sensors[world->box_sensor_count] = (struct picosystem_physics_box_sensor){
		.center = config->center,
		.half_extent = config->half_extent,
		.id = config->id,
	};
	++world->box_sensor_count;
	return 0;
}

static int
resolve_rope_endpoint_config(const struct picosystem_physics_world *world,
			     const struct picosystem_physics_rope_endpoint_config *endpoint,
			     uint8_t *body_index, struct picosystem_physics_vector *world_position)
{
	if (endpoint->body_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		*body_index = STATIC_BODY_INDEX;
		*world_position = endpoint->anchor;
		return 0;
	}

	const int resolved_index = body_index_for_id(world, endpoint->body_id);
	if (resolved_index < 0) {
		return resolved_index;
	}
	if (!body_local_anchor_is_valid(&world->bodies[resolved_index], &endpoint->anchor)) {
		return -ERANGE;
	}
	*body_index = (uint8_t)resolved_index;
	*world_position =
		body_local_point_to_world(&world->bodies[resolved_index], &endpoint->anchor);
	return 0;
}

int picosystem_physics_world_add_rope(struct picosystem_physics_world *world,
				      const struct picosystem_physics_rope_config *config)
{
	if ((world == NULL) || (config == NULL)) {
		return -EINVAL;
	}
	if (!world_is_valid(world) || !rope_config_is_valid(config)) {
		return -ERANGE;
	}
	if (world->rope_count >= PICOSYSTEM_PHYSICS_MAX_ROPES) {
		return -ENOSPC;
	}
	for (uint16_t index = 0U; index < world->rope_count; ++index) {
		if (world->ropes[index].id == config->id) {
			return -EEXIST;
		}
	}

	uint8_t body_a_index;
	uint8_t body_b_index;
	struct picosystem_physics_vector start;
	struct picosystem_physics_vector end;
	int err = resolve_rope_endpoint_config(world, &config->endpoint_a, &body_a_index, &start);
	if (err != 0) {
		return err;
	}
	err = resolve_rope_endpoint_config(world, &config->endpoint_b, &body_b_index, &end);
	if (err != 0) {
		return err;
	}

	struct picosystem_physics_rope rope = {
		.anchor_a = config->endpoint_a.anchor,
		.anchor_b = config->endpoint_b.anchor,
		.segment_length = config->segment_length,
		.collision_radius = config->collision_radius,
		.id = config->id,
		.body_a_id = config->endpoint_a.body_id,
		.body_b_id = config->endpoint_b.body_id,
		.body_a_index = body_a_index,
		.body_b_index = body_b_index,
		.particle_count = config->particle_count,
		.pin_a = config->endpoint_a.pinned,
		.pin_b = config->endpoint_b.pinned,
		.reaction_a = config->endpoint_a.reaction_enabled,
		.reaction_b = config->endpoint_b.reaction_enabled,
	};
	const struct picosystem_physics_vector extent = vector_subtract(&end, &start);
	const uint32_t segment_count = (uint32_t)config->particle_count - 1U;
	for (uint8_t index = 0U; index < config->particle_count; ++index) {
		const picosystem_physics_fixed_t fraction =
			(picosystem_physics_fixed_t)(((uint32_t)index *
						      (uint32_t)PICOSYSTEM_PHYSICS_FIXED_ONE) /
						     segment_count);
		const struct picosystem_physics_vector offset = vector_scale(&extent, fraction);
		const struct picosystem_physics_vector position = vector_add(&start, &offset);
		rope.particles[index] = (struct picosystem_physics_rope_particle){
			.position = position,
			.previous_position = position,
		};
	}
	world->ropes[world->rope_count] = rope;
	++world->rope_count;
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
			.spring_angular_frequency_per_tick =
				config->spring_angular_frequency_per_tick,
			.spring_damping_ratio = config->spring_damping_ratio,
			.maximum_spring_impulse_per_tick = config->maximum_spring_impulse_per_tick,
			.id = config->id,
			.body_a_id = config->body_a_id,
			.body_b_id = config->body_b_id,
			.body_a_index = (uint8_t)body_a_index,
			.body_b_index = (uint8_t)body_b_index,
			.spring_enabled = config->spring_enabled,
		};
	++world->distance_joint_count;
	uint16_t wake_mask = body_mask_for_index((uint8_t)body_a_index);
	if (config->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		wake_mask |= body_mask_for_index((uint8_t)body_b_index);
	}
	(void)wake_sleeping_body_mask(world, wake_mask, false);
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
	uint16_t wake_mask = body_mask_for_index((uint8_t)body_a_index);
	if (config->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		wake_mask |= body_mask_for_index((uint8_t)body_b_index);
	}
	(void)wake_sleeping_body_mask(world, wake_mask, false);
	return 0;
}

int picosystem_physics_world_add_prismatic_joint(
	struct picosystem_physics_world *world,
	const struct picosystem_physics_prismatic_joint_config *config)
{
	if ((world == NULL) || (config == NULL)) {
		return -EINVAL;
	}
	if (!world_is_valid(world) || !prismatic_joint_config_is_valid(config)) {
		return -ERANGE;
	}
	if (world->prismatic_joint_count >= PICOSYSTEM_PHYSICS_MAX_PRISMATIC_JOINTS) {
		return -ENOSPC;
	}
	for (uint16_t index = 0U; index < world->prismatic_joint_count; ++index) {
		if (world->prismatic_joints[index].id == config->id) {
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

	struct picosystem_physics_prismatic_joint *const joint =
		&world->prismatic_joints[world->prismatic_joint_count];
	*joint = (struct picosystem_physics_prismatic_joint){
		.local_anchor_a = config->local_anchor_a,
		.anchor_b = config->anchor_b,
		.motor_speed_per_tick = config->motor_speed_per_tick,
		.maximum_motor_impulse_per_tick = config->maximum_motor_impulse_per_tick,
		.lower_translation = config->lower_translation,
		.upper_translation = config->upper_translation,
		.id = config->id,
		.body_a_id = config->body_a_id,
		.body_b_id = config->body_b_id,
		.body_a_index = (uint8_t)body_a_index,
		.body_b_index = (uint8_t)body_b_index,
		.collide_connected = config->collide_connected,
		.motor_enabled = config->motor_enabled,
		.limit_enabled = config->limit_enabled,
	};
	const struct picosystem_physics_vector unit_x = {
		.x = PICOSYSTEM_PHYSICS_FIXED_ONE,
	};
	(void)normalize_vector(&config->axis_b, &joint->axis_b, &unit_x);
	joint->reference_angle_turns = prismatic_joint_relative_angle_turns(world, joint);
	struct picosystem_physics_vector world_anchor_a;
	struct picosystem_physics_vector world_anchor_b;
	struct picosystem_physics_vector world_axis;
	prismatic_joint_geometry(world, joint, &world_anchor_a, &world_anchor_b, &world_axis);
	const struct picosystem_physics_vector delta =
		vector_subtract(&world_anchor_a, &world_anchor_b);
	joint->reference_translation = vector_dot(&delta, &world_axis);
	++world->prismatic_joint_count;
	uint16_t wake_mask = body_mask_for_index((uint8_t)body_a_index);
	if (config->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		wake_mask |= body_mask_for_index((uint8_t)body_b_index);
	}
	(void)wake_sleeping_body_mask(world, wake_mask, false);
	return 0;
}

int picosystem_physics_world_set_prismatic_motor_speed(
	struct picosystem_physics_world *world, size_t index,
	picosystem_physics_fixed_t motor_speed_per_tick)
{
	if (world == NULL) {
		return -EINVAL;
	}
	if (!world_is_valid(world) ||
	    !fixed_is_bounded(motor_speed_per_tick, PHYSICS_VELOCITY_LIMIT)) {
		return -ERANGE;
	}
	if (index >= world->prismatic_joint_count) {
		return -ENOENT;
	}
	struct picosystem_physics_prismatic_joint *const joint = &world->prismatic_joints[index];
	if (joint->motor_enabled == 0U) {
		return -ENOTSUP;
	}
	joint->motor_speed_per_tick = motor_speed_per_tick;
	uint16_t wake_mask = body_mask_for_index(joint->body_a_index);
	if (joint->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		wake_mask |= body_mask_for_index(joint->body_b_index);
	}
	(void)wake_sleeping_body_mask(world, wake_mask, false);
	return 0;
}

int picosystem_physics_world_set_spring_target_distance(struct picosystem_physics_world *world,
							size_t index,
							picosystem_physics_fixed_t target_distance)
{
	if (world == NULL) {
		return -EINVAL;
	}
	if (!world_is_valid(world) || (target_distance < PHYSICS_JOINT_DISTANCE_MINIMUM) ||
	    (target_distance > PHYSICS_JOINT_DISTANCE_LIMIT)) {
		return -ERANGE;
	}
	if (index >= world->distance_joint_count) {
		return -ENOENT;
	}
	struct picosystem_physics_distance_joint *const joint = &world->distance_joints[index];
	if (joint->spring_enabled == 0U) {
		return -ENOTSUP;
	}
	if (joint->target_distance == target_distance) {
		return 0;
	}

	joint->target_distance = target_distance;
	uint16_t wake_mask = body_mask_for_index(joint->body_a_index);
	if (joint->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) {
		wake_mask |= body_mask_for_index(joint->body_b_index);
	}
	(void)wake_sleeping_body_mask(world, wake_mask, false);
	return 0;
}

int picosystem_physics_world_set_segment_surface_speed(
	struct picosystem_physics_world *world, size_t index,
	picosystem_physics_fixed_t surface_speed_per_tick)
{
	if (world == NULL) {
		return -EINVAL;
	}
	if (!world_is_valid(world) ||
	    !fixed_is_bounded(surface_speed_per_tick, PHYSICS_VELOCITY_LIMIT)) {
		return -ERANGE;
	}
	if (index >= world->static_segment_count) {
		return -ENOENT;
	}
	struct picosystem_physics_static_segment *const segment = &world->static_segments[index];
	if (segment->surface_speed_per_tick == surface_speed_per_tick) {
		return 0;
	}

	segment->surface_speed_per_tick = surface_speed_per_tick;
	const uint8_t segment_mask = (uint8_t)(UINT8_C(1) << index);
	uint16_t wake_mask = 0U;
	for (uint8_t body_index = 0U; body_index < world->body_count; ++body_index) {
		if ((world->active_segment_contact_masks[body_index] & segment_mask) != 0U) {
			wake_mask |= body_mask_for_index(body_index);
		}
	}
	(void)wake_sleeping_body_mask(world, wake_mask, false);
	return 0;
}

int picosystem_physics_world_wake_body(struct picosystem_physics_world *world, size_t index)
{
	if (world == NULL) {
		return -EINVAL;
	}
	if (!world_is_valid(world)) {
		return -ERANGE;
	}
	if (index >= world->body_count) {
		return -ENOENT;
	}
	(void)wake_sleeping_body_mask(world, body_mask_for_index((uint8_t)index), false);
	return 0;
}

bool picosystem_physics_world_body_is_sleeping(const struct picosystem_physics_world *world,
					       size_t index)
{
	return (world != NULL) && (world->body_count <= PICOSYSTEM_PHYSICS_MAX_BODIES) &&
	       (index < world->body_count) && body_index_is_sleeping(world, (uint8_t)index);
}

static PICOSYSTEM_PHYSICS_RAMFUNC int
physics_world_step(struct picosystem_physics_world *world,
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
	world->last_work.prismatic_joint_count = world->prismatic_joint_count;
	world->last_work.rope_count = world->rope_count;
	for (uint16_t index = 0U; index < world->rope_count; ++index) {
		world->last_work.rope_particle_count += world->ropes[index].particle_count;
	}
	for (uint16_t index = 0U; index < world->distance_joint_count; ++index) {
		world->last_work.spring_joint_count +=
			(world->distance_joints[index].spring_enabled != 0U) ? 1U : 0U;
	}
	if ((world->last_global_acceleration_per_tick.x != global_acceleration_per_tick->x) ||
	    (world->last_global_acceleration_per_tick.y != global_acceleration_per_tick->y)) {
		(void)wake_sleeping_body_mask(world, configured_body_mask(world), true);
		world->last_global_acceleration_per_tick = *global_acceleration_per_tick;
	}

	uint32_t section_start = profiler_section_begin(&profiler);
	for (uint16_t index = 0U; index < world->body_count; ++index) {
		if (body_index_is_sleeping(world, (uint8_t)index)) {
			continue;
		}
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

	struct physics_contact_pair_masks contact_pairs;
	int err = build_contacts(world, force_brute_force, &profiler, &contact_pairs);
	if (err != 0) {
		return err;
	}
	struct physics_sleep_graph sleep_graph;
	build_sleep_graph(world, &contact_pairs, &sleep_graph);
	wake_interacting_sleepers(world, &sleep_graph);

	bool has_awake_constraint = false;
	for (uint16_t index = 0U; index < world->contact_count; ++index) {
		if (contact_has_conveyor(world, &world->contacts[index])) {
			++world->last_work.conveyor_contact_count;
		}
		if (contact_is_sleeping(world, &world->contacts[index])) {
			++world->last_work.sleeping_contact_count;
		} else {
			has_awake_constraint = true;
		}
	}
	for (uint16_t index = 0U; index < world->distance_joint_count; ++index) {
		if (distance_joint_is_sleeping(world, &world->distance_joints[index])) {
			++world->last_work.sleeping_joint_count;
		} else {
			has_awake_constraint = true;
		}
	}
	for (uint16_t index = 0U; index < world->revolute_joint_count; ++index) {
		if (revolute_joint_is_sleeping(world, &world->revolute_joints[index])) {
			++world->last_work.sleeping_joint_count;
		} else {
			has_awake_constraint = true;
		}
	}
	for (uint16_t index = 0U; index < world->prismatic_joint_count; ++index) {
		if (prismatic_joint_is_sleeping(world, &world->prismatic_joints[index])) {
			++world->last_work.sleeping_joint_count;
		} else {
			has_awake_constraint = true;
		}
	}

	section_start = profiler_section_begin(&profiler);
	for (uint16_t index = 0U; index < world->contact_count; ++index) {
		if (contact_is_sleeping(world, &world->contacts[index])) {
			continue;
		}
		apply_position_correction(world, &world->contacts[index]);
		++world->last_work.position_correction_visit_count;
	}
	for (uint16_t index = 0U; index < world->distance_joint_count; ++index) {
		const struct picosystem_physics_distance_joint *const joint =
			&world->distance_joints[index];
		if (distance_joint_is_sleeping(world, joint) || (joint->spring_enabled != 0U)) {
			continue;
		}
		(void)apply_distance_joint_position_correction(world, joint);
		++world->last_work.joint_position_correction_visit_count;
	}
	for (uint16_t index = 0U; index < world->revolute_joint_count; ++index) {
		struct picosystem_physics_revolute_joint *const joint =
			&world->revolute_joints[index];
		if (revolute_joint_is_sleeping(world, joint)) {
			joint->angular_effective_mass = 0;
			continue;
		}
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
	for (uint8_t iteration = 0U; iteration < PICOSYSTEM_PHYSICS_PRISMATIC_POSITION_ITERATIONS;
	     ++iteration) {
		const bool reverse = (iteration & 1U) != 0U;
		const bool correction_changed = apply_prismatic_joint_position_pass(world, reverse);
		if (!correction_changed || prismatic_joint_positions_within_target(world)) {
			break;
		}
	}
	profiler_section_end(&profiler, PICOSYSTEM_PHYSICS_PROFILE_POSITION_CORRECTION,
			     section_start);

	section_start = profiler_section_begin(&profiler);
	for (uint16_t index = 0U; index < world->distance_joint_count; ++index) {
		if (distance_joint_is_sleeping(world, &world->distance_joints[index])) {
			continue;
		}
		prepare_distance_joint(world, &world->distance_joints[index]);
	}
	for (uint16_t index = 0U; index < world->revolute_joint_count; ++index) {
		if (revolute_joint_is_sleeping(world, &world->revolute_joints[index])) {
			continue;
		}
		prepare_revolute_joint(world, &world->revolute_joints[index]);
	}
	for (uint16_t index = 0U; index < world->prismatic_joint_count; ++index) {
		if (prismatic_joint_is_sleeping(world, &world->prismatic_joints[index])) {
			continue;
		}
		prepare_prismatic_joint(world, &world->prismatic_joints[index]);
	}
	world->last_solver_iteration_count = 0U;
	for (uint8_t iteration = 0U;
	     (iteration < PICOSYSTEM_PHYSICS_SOLVER_ITERATIONS) && has_awake_constraint;
	     ++iteration) {
		bool impulse_changed = false;
		for (uint16_t index = 0U; index < world->contact_count; ++index) {
			if (contact_is_sleeping(world, &world->contacts[index])) {
				continue;
			}
			const bool contact_changed =
				solve_contact_velocity(world, &world->contacts[index]);
			impulse_changed |= contact_changed;
			++world->last_work.solver_contact_visit_count;
			if (contact_changed) {
				++world->last_work.solver_changed_contact_count;
			}
		}
		for (uint16_t index = 0U; index < world->distance_joint_count; ++index) {
			struct picosystem_physics_distance_joint *const joint =
				&world->distance_joints[index];
			if (distance_joint_is_sleeping(world, joint)) {
				continue;
			}
			const bool joint_changed = solve_distance_joint_velocity(world, joint);
			impulse_changed |= joint_changed;
			++world->last_work.joint_solver_visit_count;
			if (joint->spring_enabled != 0U) {
				++world->last_work.spring_solver_visit_count;
			}
			if (joint_changed) {
				++world->last_work.joint_solver_changed_count;
				if (joint->spring_enabled != 0U) {
					++world->last_work.spring_solver_changed_count;
				}
			}
		}
		for (uint16_t index = 0U; index < world->revolute_joint_count; ++index) {
			if (revolute_joint_is_sleeping(world, &world->revolute_joints[index])) {
				continue;
			}
			const bool joint_changed = solve_revolute_joint_velocity(
				world, &world->revolute_joints[index]);
			impulse_changed |= joint_changed;
			++world->last_work.joint_solver_visit_count;
			if (joint_changed) {
				++world->last_work.joint_solver_changed_count;
			}
		}
		for (uint16_t index = 0U; index < world->prismatic_joint_count; ++index) {
			if (prismatic_joint_is_sleeping(world, &world->prismatic_joints[index])) {
				continue;
			}
			const bool joint_changed = solve_prismatic_joint_velocity(
				world, &world->prismatic_joints[index]);
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
	step_ropes(world, global_acceleration_per_tick);
	profiler_section_end(&profiler, PICOSYSTEM_PHYSICS_PROFILE_ROPE, section_start);

	section_start = profiler_section_begin(&profiler);
	for (uint16_t index = 0U; index < world->body_count; ++index) {
		if (body_index_is_sleeping(world, (uint8_t)index)) {
			continue;
		}
		clamp_body_position(&world->bodies[index]);
		clamp_body_speed(&world->bodies[index], world->max_speed_per_tick);
		clamp_body_angular_speed(&world->bodies[index]);
	}
	profiler_section_end(&profiler, PICOSYSTEM_PHYSICS_PROFILE_FINAL_CLAMP, section_start);
	update_sleep_state(world, &sleep_graph);

	err = publish_contact_events(world, &contact_pairs);
	if (err != 0) {
		return err;
	}
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

const struct picosystem_physics_contact_event *
picosystem_physics_world_contact_event_at(const struct picosystem_physics_world *world,
					  size_t index)
{
	if ((world == NULL) ||
	    (world->contact_event_count > PICOSYSTEM_PHYSICS_MAX_CONTACT_EVENTS) ||
	    (index >= world->contact_event_count)) {
		return NULL;
	}
	return &world->contact_events[index];
}

const struct picosystem_physics_rope_particle *
picosystem_physics_world_rope_particle_at(const struct picosystem_physics_world *world,
					  size_t rope_index, size_t particle_index)
{
	if ((world == NULL) || (world->rope_count > PICOSYSTEM_PHYSICS_MAX_ROPES) ||
	    (rope_index >= world->rope_count)) {
		return NULL;
	}
	const struct picosystem_physics_rope *const rope = &world->ropes[rope_index];
	if ((rope->particle_count > PICOSYSTEM_PHYSICS_MAX_ROPE_PARTICLES) ||
	    (particle_index >= rope->particle_count)) {
		return NULL;
	}
	return &rope->particles[particle_index];
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

int picosystem_physics_world_prismatic_joint_geometry(
	const struct picosystem_physics_world *world, size_t index,
	struct picosystem_physics_vector *world_anchor_a,
	struct picosystem_physics_vector *world_anchor_b,
	struct picosystem_physics_vector *world_axis)
{
	if ((world == NULL) || (world_anchor_a == NULL) || (world_anchor_b == NULL) ||
	    (world_axis == NULL)) {
		return -EINVAL;
	}
	if ((world->body_count > PICOSYSTEM_PHYSICS_MAX_BODIES) ||
	    (world->prismatic_joint_count > PICOSYSTEM_PHYSICS_MAX_PRISMATIC_JOINTS)) {
		return -ERANGE;
	}
	if (index >= world->prismatic_joint_count) {
		return -ENOENT;
	}
	const struct picosystem_physics_prismatic_joint *const joint =
		&world->prismatic_joints[index];
	if (!prismatic_joint_is_valid(joint, world)) {
		return -ERANGE;
	}

	prismatic_joint_geometry(world, joint, world_anchor_a, world_anchor_b, world_axis);
	return 0;
}

int picosystem_physics_world_prismatic_joint_translation(
	const struct picosystem_physics_world *world, size_t index,
	picosystem_physics_fixed_t *relative_translation)
{
	if ((world == NULL) || (relative_translation == NULL)) {
		return -EINVAL;
	}
	if ((world->body_count > PICOSYSTEM_PHYSICS_MAX_BODIES) ||
	    (world->prismatic_joint_count > PICOSYSTEM_PHYSICS_MAX_PRISMATIC_JOINTS)) {
		return -ERANGE;
	}
	if (index >= world->prismatic_joint_count) {
		return -ENOENT;
	}
	const struct picosystem_physics_prismatic_joint *const joint =
		&world->prismatic_joints[index];
	if (!prismatic_joint_is_valid(joint, world)) {
		return -ERANGE;
	}

	*relative_translation = prismatic_joint_translation(world, joint);
	return 0;
}

int picosystem_physics_world_prismatic_joint_angle(
	const struct picosystem_physics_world *world, size_t index,
	picosystem_physics_fixed_t *relative_angle_radians)
{
	if ((world == NULL) || (relative_angle_radians == NULL)) {
		return -EINVAL;
	}
	if ((world->body_count > PICOSYSTEM_PHYSICS_MAX_BODIES) ||
	    (world->prismatic_joint_count > PICOSYSTEM_PHYSICS_MAX_PRISMATIC_JOINTS)) {
		return -ERANGE;
	}
	if (index >= world->prismatic_joint_count) {
		return -ENOENT;
	}
	const struct picosystem_physics_prismatic_joint *const joint =
		&world->prismatic_joints[index];
	if (!prismatic_joint_is_valid(joint, world)) {
		return -ERANGE;
	}

	*relative_angle_radians = prismatic_joint_relative_angle_radians(world, joint);
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

int picosystem_physics_body_capsule_endpoints(const struct picosystem_physics_body *body,
					      struct picosystem_physics_vector *start,
					      struct picosystem_physics_vector *end)
{
	if ((body == NULL) || (start == NULL) || (end == NULL)) {
		return -EINVAL;
	}
	if (body->shape != PICOSYSTEM_PHYSICS_SHAPE_CAPSULE) {
		return -ENOTSUP;
	}
	if ((body->half_extent.x <= 0) || (body->half_extent.y != 0) || (body->radius <= 0)) {
		return -ERANGE;
	}

	struct box_geometry geometry;
	box_geometry_from_body(body, &geometry);
	const struct picosystem_physics_vector offset =
		vector_scale(&geometry.axis_x, body->half_extent.x);
	*start = vector_subtract(&body->center, &offset);
	*end = vector_add(&body->center, &offset);
	return 0;
}

int picosystem_physics_body_capsule_vertices(
	const struct picosystem_physics_body *body,
	struct picosystem_physics_vector vertices[PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT])
{
	if ((body == NULL) || (vertices == NULL)) {
		return -EINVAL;
	}
	if (body->shape != PICOSYSTEM_PHYSICS_SHAPE_CAPSULE) {
		return -ENOTSUP;
	}
	if ((body->half_extent.x <= 0) || (body->half_extent.y != 0) || (body->radius <= 0)) {
		return -ERANGE;
	}

	struct box_geometry geometry;
	box_geometry_from_body(body, &geometry);
	const struct picosystem_physics_body shaft = {
		.center = body->center,
		.half_extent = {.x = body->half_extent.x, .y = body->radius},
	};
	box_vertices_from_geometry(&shaft, &geometry, vertices);
	return 0;
}

uint32_t picosystem_physics_world_hash(const struct picosystem_physics_world *world)
{
	if ((world == NULL) || (world->body_count > PICOSYSTEM_PHYSICS_MAX_BODIES) ||
	    (world->static_segment_count > PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS) ||
	    (world->distance_joint_count > PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS) ||
	    (world->revolute_joint_count > PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS) ||
	    (world->prismatic_joint_count > PICOSYSTEM_PHYSICS_MAX_PRISMATIC_JOINTS) ||
	    (world->box_sensor_count > PICOSYSTEM_PHYSICS_MAX_BOX_SENSORS) ||
	    (world->rope_count > PICOSYSTEM_PHYSICS_MAX_ROPES)) {
		return 0U;
	}
	for (uint16_t index = 0U; index < world->rope_count; ++index) {
		if ((world->ropes[index].particle_count < 2U) ||
		    (world->ropes[index].particle_count > PICOSYSTEM_PHYSICS_MAX_ROPE_PARTICLES)) {
			return 0U;
		}
	}

	uint32_t hash = fnv1a_u32(FNV1A_OFFSET_BASIS, PHYSICS_HASH_VERSION);
	hash = fnv1a_u32(hash, (uint32_t)world->max_speed_per_tick);
	hash = fnv1a_u32(hash, world->body_count);
	hash = fnv1a_u32(hash, world->static_segment_count);
	hash = fnv1a_u32(hash, world->distance_joint_count);
	hash = fnv1a_u32(hash, world->revolute_joint_count);
	hash = fnv1a_u32(hash, world->prismatic_joint_count);
	hash = fnv1a_u32(hash, world->box_sensor_count);
	hash = fnv1a_u32(hash, world->rope_count);
	hash = fnv1a_u32(hash, world->sleeping_body_mask);
	hash = fnv1a_u32(hash, (uint32_t)world->last_global_acceleration_per_tick.x);
	hash = fnv1a_u32(hash, (uint32_t)world->last_global_acceleration_per_tick.y);
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
		hash = fnv1a_u32(hash, world->sleep_quiet_tick_counts[index]);
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
		hash = fnv1a_u32(hash, (uint32_t)segment->surface_speed_per_tick);
	}
	for (uint16_t index = 0U; index < world->box_sensor_count; ++index) {
		const struct picosystem_physics_box_sensor *const sensor =
			&world->box_sensors[index];
		hash = fnv1a_u32(hash, sensor->id);
		hash = fnv1a_u32(hash, (uint32_t)sensor->center.x);
		hash = fnv1a_u32(hash, (uint32_t)sensor->center.y);
		hash = fnv1a_u32(hash, (uint32_t)sensor->half_extent.x);
		hash = fnv1a_u32(hash, (uint32_t)sensor->half_extent.y);
	}
	for (uint16_t index = 0U; index < world->rope_count; ++index) {
		const struct picosystem_physics_rope *const rope = &world->ropes[index];
		hash = fnv1a_u32(hash, rope->id);
		hash = fnv1a_u32(hash, rope->body_a_id);
		hash = fnv1a_u32(hash, rope->body_b_id);
		hash = fnv1a_u32(hash, rope->body_a_index);
		hash = fnv1a_u32(hash, rope->body_b_index);
		hash = fnv1a_u32(hash, rope->particle_count);
		hash = fnv1a_u32(hash, rope->pin_a);
		hash = fnv1a_u32(hash, rope->pin_b);
		hash = fnv1a_u32(hash, rope->reaction_a);
		hash = fnv1a_u32(hash, rope->reaction_b);
		hash = fnv1a_u32(hash, (uint32_t)rope->anchor_a.x);
		hash = fnv1a_u32(hash, (uint32_t)rope->anchor_a.y);
		hash = fnv1a_u32(hash, (uint32_t)rope->anchor_b.x);
		hash = fnv1a_u32(hash, (uint32_t)rope->anchor_b.y);
		hash = fnv1a_u32(hash, (uint32_t)rope->segment_length);
		hash = fnv1a_u32(hash, (uint32_t)rope->collision_radius);
		for (uint8_t particle_index = 0U; particle_index < rope->particle_count;
		     ++particle_index) {
			const struct picosystem_physics_rope_particle *const particle =
				&rope->particles[particle_index];
			hash = fnv1a_u32(hash, (uint32_t)particle->position.x);
			hash = fnv1a_u32(hash, (uint32_t)particle->position.y);
			hash = fnv1a_u32(hash, (uint32_t)particle->previous_position.x);
			hash = fnv1a_u32(hash, (uint32_t)particle->previous_position.y);
		}
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
		hash = fnv1a_u32(hash, (uint32_t)joint->spring_angular_frequency_per_tick);
		hash = fnv1a_u32(hash, (uint32_t)joint->spring_damping_ratio);
		hash = fnv1a_u32(hash, (uint32_t)joint->maximum_spring_impulse_per_tick);
		hash = fnv1a_u32(hash, joint->spring_enabled);
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
	for (uint16_t index = 0U; index < world->prismatic_joint_count; ++index) {
		const struct picosystem_physics_prismatic_joint *const joint =
			&world->prismatic_joints[index];
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
		hash = fnv1a_u32(hash, (uint32_t)joint->axis_b.x);
		hash = fnv1a_u32(hash, (uint32_t)joint->axis_b.y);
		hash = fnv1a_u32(hash, (uint32_t)joint->motor_speed_per_tick);
		hash = fnv1a_u32(hash, (uint32_t)joint->maximum_motor_impulse_per_tick);
		hash = fnv1a_u32(hash, (uint32_t)joint->lower_translation);
		hash = fnv1a_u32(hash, (uint32_t)joint->upper_translation);
		hash = fnv1a_u32(hash, (uint32_t)joint->reference_translation);
		hash = fnv1a_u32(hash, joint->reference_angle_turns);
	}
	for (uint16_t index = 0U; index < world->body_count; ++index) {
		hash = fnv1a_u32(hash, world->active_body_contact_masks[index]);
		hash = fnv1a_u32(hash, world->active_segment_contact_masks[index]);
		hash = fnv1a_u32(hash, world->active_sensor_contact_masks[index]);
	}
	return hash;
}
