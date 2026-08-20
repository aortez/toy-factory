/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_PHYSICS_WORLD_H_
#define PICOSYSTEM_PHYSICS_WORLD_H_

#include <stddef.h>
#include <stdint.h>

#define PICOSYSTEM_PHYSICS_FIXED_FRACTION_BITS   16U
#define PICOSYSTEM_PHYSICS_FIXED_ONE             (INT32_C(1) << PICOSYSTEM_PHYSICS_FIXED_FRACTION_BITS)
#define PICOSYSTEM_PHYSICS_FIXED_FROM_INT(value) ((int32_t)(value) * PICOSYSTEM_PHYSICS_FIXED_ONE)
#define PICOSYSTEM_PHYSICS_FIXED_RATIO(numerator, denominator)                                     \
	((int32_t)(((int64_t)(numerator) * PICOSYSTEM_PHYSICS_FIXED_ONE) / (denominator)))

#define PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT      4U
#define PICOSYSTEM_PHYSICS_MAX_BODIES            12U
#define PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS   8U
#define PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS   8U
#define PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS   8U
#define PICOSYSTEM_PHYSICS_MAX_PRISMATIC_JOINTS  8U
#define PICOSYSTEM_PHYSICS_MAX_MANIFOLD_POINTS   2U
#define PICOSYSTEM_PHYSICS_ANGLE_QUARTER_TURN    UINT32_C(0x40000000)
#define PICOSYSTEM_PHYSICS_GRID_CELL_SIZE_PIXELS 16U
#define PICOSYSTEM_PHYSICS_GRID_COLUMNS          16U
#define PICOSYSTEM_PHYSICS_GRID_ROWS             16U
#define PICOSYSTEM_PHYSICS_GRID_CELL_COUNT                                                         \
	(PICOSYSTEM_PHYSICS_GRID_COLUMNS * PICOSYSTEM_PHYSICS_GRID_ROWS)
#define PICOSYSTEM_PHYSICS_MAX_CANDIDATE_PAIRS                                                     \
	(((PICOSYSTEM_PHYSICS_MAX_BODIES * (PICOSYSTEM_PHYSICS_MAX_BODIES - 1U)) / 2U) +           \
	 (PICOSYSTEM_PHYSICS_MAX_BODIES * PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS))
#define PICOSYSTEM_PHYSICS_MAX_CONTACTS                                                            \
	(PICOSYSTEM_PHYSICS_MAX_CANDIDATE_PAIRS * PICOSYSTEM_PHYSICS_MAX_MANIFOLD_POINTS)
#define PICOSYSTEM_PHYSICS_SOLVER_ITERATIONS             7U
#define PICOSYSTEM_PHYSICS_REVOLUTE_POSITION_ITERATIONS  4U
#define PICOSYSTEM_PHYSICS_PRISMATIC_POSITION_ITERATIONS 4U
#define PICOSYSTEM_PHYSICS_WORLD_BODY_ID                 0U

typedef int32_t picosystem_physics_fixed_t;

enum picosystem_physics_step_mode {
	PICOSYSTEM_PHYSICS_STEP_MODE_GRID,
	PICOSYSTEM_PHYSICS_STEP_MODE_REFERENCE,
};

enum picosystem_physics_profile_stage {
	PICOSYSTEM_PHYSICS_PROFILE_FORCE_AND_INTEGRATE,
	PICOSYSTEM_PHYSICS_PROFILE_BOX_GEOMETRY,
	PICOSYSTEM_PHYSICS_PROFILE_BROAD_PHASE,
	PICOSYSTEM_PHYSICS_PROFILE_NARROW_BODY_BODY,
	PICOSYSTEM_PHYSICS_PROFILE_NARROW_BODY_SEGMENT,
	PICOSYSTEM_PHYSICS_PROFILE_POSITION_CORRECTION,
	PICOSYSTEM_PHYSICS_PROFILE_VELOCITY_SOLVER,
	PICOSYSTEM_PHYSICS_PROFILE_FINAL_CLAMP,
	PICOSYSTEM_PHYSICS_PROFILE_OTHER,
	PICOSYSTEM_PHYSICS_PROFILE_TOTAL,
	PICOSYSTEM_PHYSICS_PROFILE_STAGE_COUNT,
};

typedef uint32_t (*picosystem_physics_clock_now_t)(void *context);

struct picosystem_physics_clock {
	picosystem_physics_clock_now_t now;
	void *context;
};

/* Deterministic, per-step work excluded from authoritative state hashes. */
struct picosystem_physics_work_counters {
	uint32_t possible_pair_count;
	uint32_t candidate_pair_count;
	uint32_t grid_cell_insertion_count;
	uint32_t occupied_grid_cell_count;
	uint32_t maximum_grid_cell_occupancy;
	uint32_t body_body_narrow_phase_test_count;
	uint32_t body_segment_narrow_phase_test_count;
	uint32_t joint_collision_filter_count;
	uint32_t manifold_count;
	uint32_t contact_point_count;
	uint32_t position_correction_visit_count;
	uint32_t solver_iteration_count;
	uint32_t solver_contact_visit_count;
	uint32_t solver_cached_contact_count;
	uint32_t solver_changed_contact_count;
	uint32_t distance_joint_count;
	uint32_t revolute_joint_count;
	uint32_t revolute_motor_count;
	uint32_t revolute_limit_count;
	uint32_t prismatic_joint_count;
	uint32_t prismatic_motor_count;
	uint32_t prismatic_limit_count;
	uint32_t joint_position_correction_visit_count;
	uint32_t joint_limit_position_correction_visit_count;
	uint32_t joint_limit_position_correction_changed_count;
	uint32_t joint_solver_visit_count;
	uint32_t joint_solver_changed_count;
	uint32_t joint_motor_solver_visit_count;
	uint32_t joint_motor_solver_changed_count;
	uint32_t joint_limit_solver_visit_count;
	uint32_t joint_limit_solver_changed_count;
	uint32_t broad_phase_fallback_count;
};

/* Optional elapsed-cycle sample for one step; the clock may wrap once per section. */
struct picosystem_physics_step_profile {
	uint32_t stage_cycles[PICOSYSTEM_PHYSICS_PROFILE_STAGE_COUNT];
	struct picosystem_physics_work_counters work;
	uint32_t clock_read_count;
};

struct picosystem_physics_vector {
	picosystem_physics_fixed_t x;
	picosystem_physics_fixed_t y;
};

enum picosystem_physics_shape {
	PICOSYSTEM_PHYSICS_SHAPE_CIRCLE,
	PICOSYSTEM_PHYSICS_SHAPE_BOX,
};

struct picosystem_physics_circle_config {
	struct picosystem_physics_vector center;
	struct picosystem_physics_vector velocity_per_tick;
	picosystem_physics_fixed_t radius;
	picosystem_physics_fixed_t inverse_mass;
	picosystem_physics_fixed_t restitution;
	picosystem_physics_fixed_t friction;
	picosystem_physics_fixed_t angular_velocity_per_tick;
	uint32_t angle_turns;
	uint16_t id;
};

struct picosystem_physics_box_config {
	struct picosystem_physics_vector center;
	struct picosystem_physics_vector velocity_per_tick;
	struct picosystem_physics_vector half_extent;
	picosystem_physics_fixed_t inverse_mass;
	picosystem_physics_fixed_t restitution;
	picosystem_physics_fixed_t friction;
	picosystem_physics_fixed_t angular_velocity_per_tick;
	uint32_t angle_turns;
	uint16_t id;
};

struct picosystem_physics_segment_config {
	struct picosystem_physics_vector start;
	struct picosystem_physics_vector end;
	picosystem_physics_fixed_t restitution;
	picosystem_physics_fixed_t friction;
	uint16_t id;
};

/* Anchor B is world-space when body_b_id is zero and body-local otherwise. */
struct picosystem_physics_distance_joint_config {
	struct picosystem_physics_vector local_anchor_a;
	struct picosystem_physics_vector anchor_b;
	picosystem_physics_fixed_t target_distance;
	uint16_t id;
	uint16_t body_a_id;
	uint16_t body_b_id;
};

/*
 * Anchor B is world-space when body_b_id is zero and body-local otherwise.
 * Positive motor speed rotates body A counter-clockwise relative to body B.
 * Limits are signed Q16.16 radians relative to the joint's creation pose.
 */
struct picosystem_physics_revolute_joint_config {
	struct picosystem_physics_vector local_anchor_a;
	struct picosystem_physics_vector anchor_b;
	picosystem_physics_fixed_t motor_speed_per_tick;
	picosystem_physics_fixed_t maximum_motor_impulse_per_tick;
	picosystem_physics_fixed_t lower_angle_radians;
	picosystem_physics_fixed_t upper_angle_radians;
	uint16_t id;
	uint16_t body_a_id;
	uint16_t body_b_id;
	uint8_t collide_connected;
	uint8_t motor_enabled;
	uint8_t limit_enabled;
};

/*
 * Anchor B and axis B are world-space when body_b_id is zero and body-local otherwise.
 * Positive motor speed moves body A along axis B relative to body B. Translation limits are
 * signed Q16.16 pixels relative to the joint's creation pose. The solver constrains lateral
 * motion and relative rotation while leaving axial translation free.
 */
struct picosystem_physics_prismatic_joint_config {
	struct picosystem_physics_vector local_anchor_a;
	struct picosystem_physics_vector anchor_b;
	struct picosystem_physics_vector axis_b;
	picosystem_physics_fixed_t motor_speed_per_tick;
	picosystem_physics_fixed_t maximum_motor_impulse_per_tick;
	picosystem_physics_fixed_t lower_translation;
	picosystem_physics_fixed_t upper_translation;
	uint16_t id;
	uint16_t body_a_id;
	uint16_t body_b_id;
	uint8_t collide_connected;
	uint8_t motor_enabled;
	uint8_t limit_enabled;
};

struct picosystem_physics_body {
	struct picosystem_physics_vector center;
	struct picosystem_physics_vector velocity_per_tick;
	struct picosystem_physics_vector half_extent;
	picosystem_physics_fixed_t radius;
	picosystem_physics_fixed_t inverse_mass;
	picosystem_physics_fixed_t inverse_inertia;
	picosystem_physics_fixed_t restitution;
	picosystem_physics_fixed_t friction;
	picosystem_physics_fixed_t angular_velocity_per_tick;
	uint32_t angle_turns;
	uint16_t id;
	uint8_t shape;
};

struct picosystem_physics_static_segment {
	struct picosystem_physics_vector start;
	struct picosystem_physics_vector end;
	struct picosystem_physics_vector normal;
	picosystem_physics_fixed_t restitution;
	picosystem_physics_fixed_t friction;
	uint16_t id;
};

struct picosystem_physics_distance_joint {
	/* Persistent configuration included in the authoritative hash. */
	struct picosystem_physics_vector local_anchor_a;
	struct picosystem_physics_vector anchor_b;
	picosystem_physics_fixed_t target_distance;
	uint16_t id;
	uint16_t body_a_id;
	uint16_t body_b_id;
	uint8_t body_a_index;
	uint8_t body_b_index;

	/* Scratch solver state rebuilt every step and excluded from the hash. */
	struct picosystem_physics_vector world_anchor_a;
	struct picosystem_physics_vector world_anchor_b;
	struct picosystem_physics_vector normal;
	picosystem_physics_fixed_t direction_inverse_mass;
	picosystem_physics_fixed_t accumulated_impulse;
};

struct picosystem_physics_revolute_joint {
	/* Persistent configuration included in the authoritative hash. */
	struct picosystem_physics_vector local_anchor_a;
	struct picosystem_physics_vector anchor_b;
	picosystem_physics_fixed_t motor_speed_per_tick;
	picosystem_physics_fixed_t maximum_motor_impulse_per_tick;
	picosystem_physics_fixed_t lower_angle_radians;
	picosystem_physics_fixed_t upper_angle_radians;
	uint32_t reference_angle_turns;
	uint16_t id;
	uint16_t body_a_id;
	uint16_t body_b_id;
	uint8_t body_a_index;
	uint8_t body_b_index;
	uint8_t collide_connected;
	uint8_t motor_enabled;
	uint8_t limit_enabled;

	/* Scratch solver state rebuilt every step and excluded from the hash. */
	struct picosystem_physics_vector world_anchor_a;
	struct picosystem_physics_vector world_anchor_b;
	struct picosystem_physics_vector accumulated_impulse;
	picosystem_physics_fixed_t effective_mass_xx;
	picosystem_physics_fixed_t effective_mass_xy;
	picosystem_physics_fixed_t effective_mass_yy;
	picosystem_physics_fixed_t angular_effective_mass;
	picosystem_physics_fixed_t accumulated_motor_impulse;
	picosystem_physics_fixed_t accumulated_limit_impulse;
	uint8_t effective_mass_valid;
	uint8_t limit_state;
};

struct picosystem_physics_prismatic_joint {
	/* Persistent configuration included in the authoritative hash. */
	struct picosystem_physics_vector local_anchor_a;
	struct picosystem_physics_vector anchor_b;
	struct picosystem_physics_vector axis_b;
	picosystem_physics_fixed_t motor_speed_per_tick;
	picosystem_physics_fixed_t maximum_motor_impulse_per_tick;
	picosystem_physics_fixed_t lower_translation;
	picosystem_physics_fixed_t upper_translation;
	picosystem_physics_fixed_t reference_translation;
	uint32_t reference_angle_turns;
	uint16_t id;
	uint16_t body_a_id;
	uint16_t body_b_id;
	uint8_t body_a_index;
	uint8_t body_b_index;
	uint8_t collide_connected;
	uint8_t motor_enabled;
	uint8_t limit_enabled;

	/* Scratch solver state rebuilt every step and excluded from the hash. */
	struct picosystem_physics_vector world_anchor_a;
	struct picosystem_physics_vector world_anchor_b;
	struct picosystem_physics_vector world_axis;
	struct picosystem_physics_vector world_perpendicular;
	picosystem_physics_fixed_t lateral_effective_mass;
	picosystem_physics_fixed_t axial_effective_mass;
	picosystem_physics_fixed_t angular_effective_mass;
	picosystem_physics_fixed_t accumulated_lateral_impulse;
	picosystem_physics_fixed_t accumulated_angular_impulse;
	picosystem_physics_fixed_t accumulated_motor_impulse;
	picosystem_physics_fixed_t accumulated_limit_impulse;
	uint16_t solved_velocity_revision_a;
	uint16_t solved_velocity_revision_b;
	uint8_t limit_state;
	uint8_t solved_velocity_valid;
};

enum picosystem_physics_contact_type {
	PICOSYSTEM_PHYSICS_CONTACT_BODY,
	PICOSYSTEM_PHYSICS_CONTACT_STATIC_SEGMENT,
};

/* Scratch contact state rebuilt on every update and excluded from authoritative hashes. */
struct picosystem_physics_contact {
	struct picosystem_physics_vector point;
	struct picosystem_physics_vector normal;
	picosystem_physics_fixed_t penetration;
	picosystem_physics_fixed_t target_normal_velocity;
	picosystem_physics_fixed_t accumulated_normal_impulse;
	picosystem_physics_fixed_t accumulated_tangent_impulse;
	picosystem_physics_fixed_t position_correction_scale;
	uint16_t solved_velocity_revision_a;
	uint16_t solved_velocity_revision_b;
	uint8_t body_a_index;
	uint8_t body_b_index;
	uint8_t segment_index;
	uint8_t type;
	uint8_t solved_velocity_valid;
};

/* Scratch occupancy rebuilt on every update and excluded from authoritative hashes. */
struct picosystem_physics_grid_cell {
	uint16_t body_mask;
	uint8_t static_segment_mask;
};

struct picosystem_physics_world {
	struct picosystem_physics_body bodies[PICOSYSTEM_PHYSICS_MAX_BODIES];
	struct picosystem_physics_static_segment
		static_segments[PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS];
	struct picosystem_physics_distance_joint
		distance_joints[PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS];
	struct picosystem_physics_revolute_joint
		revolute_joints[PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS];
	struct picosystem_physics_prismatic_joint
		prismatic_joints[PICOSYSTEM_PHYSICS_MAX_PRISMATIC_JOINTS];
	struct picosystem_physics_contact contacts[PICOSYSTEM_PHYSICS_MAX_CONTACTS];
	struct picosystem_physics_grid_cell grid_cells[PICOSYSTEM_PHYSICS_GRID_CELL_COUNT];
	/* Revisions change with every solver velocity mutation and are excluded from hashes. */
	uint16_t solver_velocity_revisions[PICOSYSTEM_PHYSICS_MAX_BODIES];
	struct picosystem_physics_work_counters last_work;
	picosystem_physics_fixed_t max_speed_per_tick;
	uint32_t last_candidate_pair_count;
	uint32_t last_possible_pair_count;
	uint16_t body_count;
	uint16_t static_segment_count;
	uint16_t distance_joint_count;
	uint16_t revolute_joint_count;
	uint16_t prismatic_joint_count;
	uint16_t contact_count;
	uint16_t last_occupied_grid_cell_count;
	uint8_t last_broad_phase_fallback;
	uint8_t last_solver_iteration_count;
};

/* Initialize an empty, caller-owned world with a bounded vector-speed limit. */
int picosystem_physics_world_init(struct picosystem_physics_world *world,
				  picosystem_physics_fixed_t max_speed_per_tick);

/* Append canonical configuration before stepping; failures preserve the world. */
int picosystem_physics_world_add_circle(struct picosystem_physics_world *world,
					const struct picosystem_physics_circle_config *config);
int picosystem_physics_world_add_box(struct picosystem_physics_world *world,
				     const struct picosystem_physics_box_config *config);
int picosystem_physics_world_add_static_segment(
	struct picosystem_physics_world *world,
	const struct picosystem_physics_segment_config *config);
int picosystem_physics_world_add_distance_joint(
	struct picosystem_physics_world *world,
	const struct picosystem_physics_distance_joint_config *config);
int picosystem_physics_world_add_revolute_joint(
	struct picosystem_physics_world *world,
	const struct picosystem_physics_revolute_joint_config *config);
int picosystem_physics_world_add_prismatic_joint(
	struct picosystem_physics_world *world,
	const struct picosystem_physics_prismatic_joint_config *config);

/* Change one enabled prismatic motor target without changing any other state. */
int picosystem_physics_world_set_prismatic_motor_speed(
	struct picosystem_physics_world *world, size_t index,
	picosystem_physics_fixed_t motor_speed_per_tick);

/* Advance exactly one tick with a global acceleration expressed in pixels/tick^2. */
int picosystem_physics_world_step(
	struct picosystem_physics_world *world,
	const struct picosystem_physics_vector *global_acceleration_per_tick);

/* Advance with brute-force candidates as a deterministic validation oracle. */
int picosystem_physics_world_step_reference(
	struct picosystem_physics_world *world,
	const struct picosystem_physics_vector *global_acceleration_per_tick);

/* Advance one grid or reference step and collect optional platform-neutral timing. */
int picosystem_physics_world_step_profiled(
	struct picosystem_physics_world *world,
	const struct picosystem_physics_vector *global_acceleration_per_tick,
	enum picosystem_physics_step_mode mode, const struct picosystem_physics_clock *clock,
	struct picosystem_physics_step_profile *profile);

const struct picosystem_physics_body *
picosystem_physics_world_body_at(const struct picosystem_physics_world *world, size_t index);

/* Resolve the current world-space endpoints of one distance joint. */
int picosystem_physics_world_distance_joint_endpoints(
	const struct picosystem_physics_world *world, size_t index,
	struct picosystem_physics_vector *world_anchor_a,
	struct picosystem_physics_vector *world_anchor_b);

/* Resolve the current world-space anchors constrained by one revolute joint. */
int picosystem_physics_world_revolute_joint_anchors(
	const struct picosystem_physics_world *world, size_t index,
	struct picosystem_physics_vector *world_anchor_a,
	struct picosystem_physics_vector *world_anchor_b);

/* Resolve signed Q16.16 radians relative to one revolute joint's creation pose. */
int picosystem_physics_world_revolute_joint_angle(
	const struct picosystem_physics_world *world, size_t index,
	picosystem_physics_fixed_t *relative_angle_radians);

/* Resolve one prismatic joint's current anchors and positive world-space rail axis. */
int picosystem_physics_world_prismatic_joint_geometry(
	const struct picosystem_physics_world *world, size_t index,
	struct picosystem_physics_vector *world_anchor_a,
	struct picosystem_physics_vector *world_anchor_b,
	struct picosystem_physics_vector *world_axis);

/* Resolve signed Q16.16 pixels along the rail relative to the creation pose. */
int picosystem_physics_world_prismatic_joint_translation(
	const struct picosystem_physics_world *world, size_t index,
	picosystem_physics_fixed_t *relative_translation);

/* Resolve signed Q16.16 radians relative to the rotation locked at creation. */
int picosystem_physics_world_prismatic_joint_angle(
	const struct picosystem_physics_world *world, size_t index,
	picosystem_physics_fixed_t *relative_angle_radians);

/* Resolve a box's four world-space corners in stable winding order. */
int picosystem_physics_body_box_vertices(
	const struct picosystem_physics_body *body,
	struct picosystem_physics_vector vertices[PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT]);

/* Hash persistent configuration and body state, excluding contacts and diagnostics. */
uint32_t picosystem_physics_world_hash(const struct picosystem_physics_world *world);

#endif /* PICOSYSTEM_PHYSICS_WORLD_H_ */
