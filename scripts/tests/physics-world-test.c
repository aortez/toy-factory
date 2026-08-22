/* SPDX-License-Identifier: Apache-2.0 */

#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "physics_world.h"

#define FIXED(value)                  PICOSYSTEM_PHYSICS_FIXED_FROM_INT(value)
#define RATIO(numerator, denominator) PICOSYSTEM_PHYSICS_FIXED_RATIO(numerator, denominator)

static const struct picosystem_physics_vector no_acceleration = {0};

static uint32_t fake_clock_now(void *context)
{
	uint32_t *const cycles = context;
	*cycles += 10U;
	return *cycles;
}

static struct picosystem_physics_circle_config circle_config(uint16_t id, int32_t x, int32_t y,
							     int32_t radius)
{
	return (struct picosystem_physics_circle_config){
		.center = {.x = FIXED(x), .y = FIXED(y)},
		.radius = FIXED(radius),
		.inverse_mass = PICOSYSTEM_PHYSICS_FIXED_ONE,
		.restitution = RATIO(3, 4),
		.friction = RATIO(1, 5),
		.id = id,
	};
}

static struct picosystem_physics_box_config box_config(uint16_t id, int32_t x, int32_t y,
						       int32_t half_width, int32_t half_height)
{
	return (struct picosystem_physics_box_config){
		.center = {.x = FIXED(x), .y = FIXED(y)},
		.half_extent = {.x = FIXED(half_width), .y = FIXED(half_height)},
		.inverse_mass = PICOSYSTEM_PHYSICS_FIXED_ONE,
		.restitution = RATIO(3, 4),
		.friction = RATIO(1, 5),
		.id = id,
	};
}

static struct picosystem_physics_capsule_config capsule_config(uint16_t id, int32_t x, int32_t y,
							       int32_t half_length, int32_t radius)
{
	return (struct picosystem_physics_capsule_config){
		.center = {.x = FIXED(x), .y = FIXED(y)},
		.half_length = FIXED(half_length),
		.radius = FIXED(radius),
		.inverse_mass = PICOSYSTEM_PHYSICS_FIXED_ONE,
		.restitution = RATIO(3, 4),
		.friction = RATIO(1, 5),
		.id = id,
	};
}

static struct picosystem_physics_box_sensor_config
box_sensor_config(uint16_t id, int32_t x, int32_t y, int32_t half_width, int32_t half_height)
{
	return (struct picosystem_physics_box_sensor_config){
		.center = {.x = FIXED(x), .y = FIXED(y)},
		.half_extent = {.x = FIXED(half_width), .y = FIXED(half_height)},
		.id = id,
	};
}

static struct picosystem_physics_segment_config horizontal_segment(uint16_t id, int32_t y)
{
	return (struct picosystem_physics_segment_config){
		.start = {.x = FIXED(-10), .y = FIXED(y)},
		.end = {.x = FIXED(10), .y = FIXED(y)},
		.restitution = RATIO(3, 4),
		.friction = RATIO(1, 5),
		.id = id,
	};
}

static struct picosystem_physics_distance_joint_config
distance_joint_config(uint16_t id, uint16_t body_a_id, uint16_t body_b_id, int32_t target_distance)
{
	return (struct picosystem_physics_distance_joint_config){
		.target_distance = FIXED(target_distance),
		.id = id,
		.body_a_id = body_a_id,
		.body_b_id = body_b_id,
	};
}

static struct picosystem_physics_distance_joint_config
spring_joint_config(uint16_t id, uint16_t body_a_id, uint16_t body_b_id, int32_t target_distance)
{
	struct picosystem_physics_distance_joint_config config =
		distance_joint_config(id, body_a_id, body_b_id, target_distance);
	config.spring_angular_frequency_per_tick = RATIO(1, 8);
	config.spring_damping_ratio = RATIO(1, 2);
	config.maximum_spring_impulse_per_tick = FIXED(2);
	config.spring_enabled = 1U;
	return config;
}

static struct picosystem_physics_revolute_joint_config
revolute_joint_config(uint16_t id, uint16_t body_a_id, uint16_t body_b_id)
{
	return (struct picosystem_physics_revolute_joint_config){
		.id = id,
		.body_a_id = body_a_id,
		.body_b_id = body_b_id,
	};
}

static struct picosystem_physics_prismatic_joint_config
prismatic_joint_config(uint16_t id, uint16_t body_a_id, uint16_t body_b_id)
{
	return (struct picosystem_physics_prismatic_joint_config){
		.axis_b = {.x = PICOSYSTEM_PHYSICS_FIXED_ONE},
		.id = id,
		.body_a_id = body_a_id,
		.body_b_id = body_b_id,
	};
}

static struct picosystem_physics_rope_config rope_config(uint16_t id, int32_t start_x,
							 int32_t start_y, int32_t end_x,
							 int32_t end_y, uint8_t particle_count,
							 int32_t segment_length)
{
	return (struct picosystem_physics_rope_config){
		.endpoint_a =
			{
				.anchor = {.x = FIXED(start_x), .y = FIXED(start_y)},
				.body_id = PICOSYSTEM_PHYSICS_WORLD_BODY_ID,
			},
		.endpoint_b =
			{
				.anchor = {.x = FIXED(end_x), .y = FIXED(end_y)},
				.body_id = PICOSYSTEM_PHYSICS_WORLD_BODY_ID,
			},
		.segment_length = FIXED(segment_length),
		.id = id,
		.particle_count = particle_count,
	};
}

static void init_world(struct picosystem_physics_world *world,
		       picosystem_physics_fixed_t maximum_speed)
{
	assert(picosystem_physics_world_init(world, maximum_speed) == 0);
}

static void assert_fixed_close(picosystem_physics_fixed_t actual,
			       picosystem_physics_fixed_t expected,
			       picosystem_physics_fixed_t tolerance)
{
	const int64_t difference = (int64_t)actual - expected;
	if ((difference < -(int64_t)tolerance) || (difference > tolerance)) {
		fprintf(stderr, "fixed value %d differs from %d by %lld (tolerance %d)\n", actual,
			expected, (long long)difference, tolerance);
	}
	assert(difference >= -(int64_t)tolerance);
	assert(difference <= tolerance);
}

static void assert_vector_equal(const struct picosystem_physics_vector *left,
				const struct picosystem_physics_vector *right)
{
	assert(left->x == right->x);
	assert(left->y == right->y);
}

static void assert_body_equal(const struct picosystem_physics_body *left,
			      const struct picosystem_physics_body *right)
{
	assert_vector_equal(&left->center, &right->center);
	assert_vector_equal(&left->velocity_per_tick, &right->velocity_per_tick);
	assert_vector_equal(&left->half_extent, &right->half_extent);
	assert(left->radius == right->radius);
	assert(left->inverse_mass == right->inverse_mass);
	assert(left->inverse_inertia == right->inverse_inertia);
	assert(left->restitution == right->restitution);
	assert(left->friction == right->friction);
	assert(left->angular_velocity_per_tick == right->angular_velocity_per_tick);
	assert(left->angle_turns == right->angle_turns);
	assert(left->id == right->id);
	assert(left->shape == right->shape);
}

static void assert_contact_equal(const struct picosystem_physics_contact *left,
				 const struct picosystem_physics_contact *right)
{
	assert_vector_equal(&left->point, &right->point);
	assert_vector_equal(&left->normal, &right->normal);
	assert(left->penetration == right->penetration);
	assert(left->target_normal_velocity == right->target_normal_velocity);
	assert(left->accumulated_normal_impulse == right->accumulated_normal_impulse);
	assert(left->accumulated_tangent_impulse == right->accumulated_tangent_impulse);
	assert(left->position_correction_scale == right->position_correction_scale);
	assert(left->solved_velocity_revision_a == right->solved_velocity_revision_a);
	assert(left->solved_velocity_revision_b == right->solved_velocity_revision_b);
	assert(left->body_a_index == right->body_a_index);
	assert(left->body_b_index == right->body_b_index);
	assert(left->segment_index == right->segment_index);
	assert(left->type == right->type);
	assert(left->solved_velocity_valid == right->solved_velocity_valid);
}

static void assert_contact_event_equal(const struct picosystem_physics_contact_event *left,
				       const struct picosystem_physics_contact_event *right)
{
	assert(left->body_a_id == right->body_a_id);
	assert(left->body_b_id == right->body_b_id);
	assert(left->type == right->type);
	assert(left->phase == right->phase);
}

static void assert_contact_event(const struct picosystem_physics_world *world, size_t index,
				 uint16_t body_a_id, uint16_t body_b_id, uint8_t type,
				 uint8_t phase)
{
	const struct picosystem_physics_contact_event *const event =
		picosystem_physics_world_contact_event_at(world, index);
	assert(event != NULL);
	assert(event->body_a_id == body_a_id);
	assert(event->body_b_id == body_b_id);
	assert(event->type == type);
	assert(event->phase == phase);
}

static void assert_static_segment_equal(const struct picosystem_physics_static_segment *left,
					const struct picosystem_physics_static_segment *right)
{
	assert_vector_equal(&left->start, &right->start);
	assert_vector_equal(&left->end, &right->end);
	assert_vector_equal(&left->normal, &right->normal);
	assert(left->restitution == right->restitution);
	assert(left->friction == right->friction);
	assert(left->surface_speed_per_tick == right->surface_speed_per_tick);
	assert(left->id == right->id);
}

static void assert_distance_joint_equal(const struct picosystem_physics_distance_joint *left,
					const struct picosystem_physics_distance_joint *right)
{
	assert_vector_equal(&left->local_anchor_a, &right->local_anchor_a);
	assert_vector_equal(&left->anchor_b, &right->anchor_b);
	assert(left->target_distance == right->target_distance);
	assert(left->spring_angular_frequency_per_tick == right->spring_angular_frequency_per_tick);
	assert(left->spring_damping_ratio == right->spring_damping_ratio);
	assert(left->maximum_spring_impulse_per_tick == right->maximum_spring_impulse_per_tick);
	assert(left->id == right->id);
	assert(left->body_a_id == right->body_a_id);
	assert(left->body_b_id == right->body_b_id);
	assert(left->body_a_index == right->body_a_index);
	assert(left->body_b_index == right->body_b_index);
	assert(left->spring_enabled == right->spring_enabled);
	assert_vector_equal(&left->world_anchor_a, &right->world_anchor_a);
	assert_vector_equal(&left->world_anchor_b, &right->world_anchor_b);
	assert_vector_equal(&left->normal, &right->normal);
	assert(left->direction_inverse_mass == right->direction_inverse_mass);
	assert(left->accumulated_impulse == right->accumulated_impulse);
	assert(left->spring_softness == right->spring_softness);
	assert(left->spring_bias_velocity == right->spring_bias_velocity);
}

static void assert_revolute_joint_equal(const struct picosystem_physics_revolute_joint *left,
					const struct picosystem_physics_revolute_joint *right)
{
	assert_vector_equal(&left->local_anchor_a, &right->local_anchor_a);
	assert_vector_equal(&left->anchor_b, &right->anchor_b);
	assert(left->id == right->id);
	assert(left->body_a_id == right->body_a_id);
	assert(left->body_b_id == right->body_b_id);
	assert(left->body_a_index == right->body_a_index);
	assert(left->body_b_index == right->body_b_index);
	assert(left->collide_connected == right->collide_connected);
	assert(left->motor_enabled == right->motor_enabled);
	assert(left->limit_enabled == right->limit_enabled);
	assert(left->motor_speed_per_tick == right->motor_speed_per_tick);
	assert(left->maximum_motor_impulse_per_tick == right->maximum_motor_impulse_per_tick);
	assert(left->lower_angle_radians == right->lower_angle_radians);
	assert(left->upper_angle_radians == right->upper_angle_radians);
	assert(left->reference_angle_turns == right->reference_angle_turns);
	assert_vector_equal(&left->world_anchor_a, &right->world_anchor_a);
	assert_vector_equal(&left->world_anchor_b, &right->world_anchor_b);
	assert_vector_equal(&left->accumulated_impulse, &right->accumulated_impulse);
	assert(left->effective_mass_xx == right->effective_mass_xx);
	assert(left->effective_mass_xy == right->effective_mass_xy);
	assert(left->effective_mass_yy == right->effective_mass_yy);
	assert(left->angular_effective_mass == right->angular_effective_mass);
	assert(left->accumulated_motor_impulse == right->accumulated_motor_impulse);
	assert(left->accumulated_limit_impulse == right->accumulated_limit_impulse);
	assert(left->effective_mass_valid == right->effective_mass_valid);
	assert(left->limit_state == right->limit_state);
}

static void assert_prismatic_joint_equal(const struct picosystem_physics_prismatic_joint *left,
					 const struct picosystem_physics_prismatic_joint *right)
{
	assert_vector_equal(&left->local_anchor_a, &right->local_anchor_a);
	assert_vector_equal(&left->anchor_b, &right->anchor_b);
	assert_vector_equal(&left->axis_b, &right->axis_b);
	assert(left->motor_speed_per_tick == right->motor_speed_per_tick);
	assert(left->maximum_motor_impulse_per_tick == right->maximum_motor_impulse_per_tick);
	assert(left->lower_translation == right->lower_translation);
	assert(left->upper_translation == right->upper_translation);
	assert(left->reference_translation == right->reference_translation);
	assert(left->reference_angle_turns == right->reference_angle_turns);
	assert(left->id == right->id);
	assert(left->body_a_id == right->body_a_id);
	assert(left->body_b_id == right->body_b_id);
	assert(left->body_a_index == right->body_a_index);
	assert(left->body_b_index == right->body_b_index);
	assert(left->collide_connected == right->collide_connected);
	assert(left->motor_enabled == right->motor_enabled);
	assert(left->limit_enabled == right->limit_enabled);
	assert_vector_equal(&left->world_anchor_a, &right->world_anchor_a);
	assert_vector_equal(&left->world_anchor_b, &right->world_anchor_b);
	assert_vector_equal(&left->world_axis, &right->world_axis);
	assert_vector_equal(&left->world_perpendicular, &right->world_perpendicular);
	assert(left->lateral_effective_mass == right->lateral_effective_mass);
	assert(left->axial_effective_mass == right->axial_effective_mass);
	assert(left->angular_effective_mass == right->angular_effective_mass);
	assert(left->accumulated_lateral_impulse == right->accumulated_lateral_impulse);
	assert(left->accumulated_angular_impulse == right->accumulated_angular_impulse);
	assert(left->accumulated_motor_impulse == right->accumulated_motor_impulse);
	assert(left->accumulated_limit_impulse == right->accumulated_limit_impulse);
	assert(left->solved_velocity_revision_a == right->solved_velocity_revision_a);
	assert(left->solved_velocity_revision_b == right->solved_velocity_revision_b);
	assert(left->limit_state == right->limit_state);
	assert(left->solved_velocity_valid == right->solved_velocity_valid);
}

static void assert_rope_equal(const struct picosystem_physics_rope *left,
			      const struct picosystem_physics_rope *right)
{
	assert_vector_equal(&left->anchor_a, &right->anchor_a);
	assert_vector_equal(&left->anchor_b, &right->anchor_b);
	assert(left->segment_length == right->segment_length);
	assert(left->collision_radius == right->collision_radius);
	assert(left->id == right->id);
	assert(left->body_a_id == right->body_a_id);
	assert(left->body_b_id == right->body_b_id);
	assert(left->body_a_index == right->body_a_index);
	assert(left->body_b_index == right->body_b_index);
	assert(left->particle_count == right->particle_count);
	assert(left->pin_a == right->pin_a);
	assert(left->pin_b == right->pin_b);
	assert(left->reaction_a == right->reaction_a);
	assert(left->reaction_b == right->reaction_b);
	for (uint8_t index = 0U; index < left->particle_count; ++index) {
		assert_vector_equal(&left->particles[index].position,
				    &right->particles[index].position);
		assert_vector_equal(&left->particles[index].previous_position,
				    &right->particles[index].previous_position);
	}
}

static uint64_t vector_distance_squared(const struct picosystem_physics_vector *left,
					const struct picosystem_physics_vector *right)
{
	const int64_t x = (int64_t)right->x - left->x;
	const int64_t y = (int64_t)right->y - left->y;
	return (uint64_t)((x * x) + (y * y));
}

static void assert_distance_between(const struct picosystem_physics_vector *left,
				    const struct picosystem_physics_vector *right,
				    picosystem_physics_fixed_t minimum,
				    picosystem_physics_fixed_t maximum)
{
	const uint64_t distance_squared = vector_distance_squared(left, right);
	const uint64_t minimum_squared = (uint64_t)((int64_t)minimum * minimum);
	const uint64_t maximum_squared = (uint64_t)((int64_t)maximum * maximum);
	assert(distance_squared >= minimum_squared);
	assert(distance_squared <= maximum_squared);
}

static void assert_step_matches_reference(const struct picosystem_physics_world *grid,
					  const struct picosystem_physics_world *reference)
{
	assert(grid->body_count == reference->body_count);
	assert(grid->static_segment_count == reference->static_segment_count);
	assert(grid->distance_joint_count == reference->distance_joint_count);
	assert(grid->revolute_joint_count == reference->revolute_joint_count);
	assert(grid->prismatic_joint_count == reference->prismatic_joint_count);
	assert(grid->box_sensor_count == reference->box_sensor_count);
	assert(grid->rope_count == reference->rope_count);
	assert(grid->contact_count == reference->contact_count);
	assert(grid->contact_event_count == reference->contact_event_count);
	assert(grid->last_possible_pair_count == reference->last_possible_pair_count);
	assert(grid->sleeping_body_mask == reference->sleeping_body_mask);
	assert_vector_equal(&grid->last_global_acceleration_per_tick,
			    &reference->last_global_acceleration_per_tick);
	assert(reference->last_candidate_pair_count == reference->last_possible_pair_count);
	assert(grid->last_solver_iteration_count == reference->last_solver_iteration_count);
	assert(grid->last_work.possible_pair_count == reference->last_work.possible_pair_count);
	assert(grid->last_work.candidate_pair_count == grid->last_candidate_pair_count);
	assert(reference->last_work.candidate_pair_count ==
	       reference->last_work.possible_pair_count);
	assert(grid->last_work.body_body_narrow_phase_test_count +
		       grid->last_work.body_segment_narrow_phase_test_count +
		       grid->last_work.body_sensor_narrow_phase_test_count +
		       grid->last_work.joint_collision_filter_count ==
	       grid->last_work.candidate_pair_count);
	assert(reference->last_work.body_body_narrow_phase_test_count +
		       reference->last_work.body_segment_narrow_phase_test_count +
		       reference->last_work.body_sensor_narrow_phase_test_count +
		       reference->last_work.joint_collision_filter_count ==
	       reference->last_work.candidate_pair_count);
	assert(grid->last_work.joint_collision_filter_count ==
	       reference->last_work.joint_collision_filter_count);
	assert(grid->last_work.manifold_count == reference->last_work.manifold_count);
	assert(grid->last_work.contact_point_count == reference->last_work.contact_point_count);
	assert(grid->last_work.active_contact_pair_count ==
	       reference->last_work.active_contact_pair_count);
	assert(grid->last_work.sensor_overlap_count == reference->last_work.sensor_overlap_count);
	assert(grid->last_work.contact_begin_event_count ==
	       reference->last_work.contact_begin_event_count);
	assert(grid->last_work.contact_stay_event_count ==
	       reference->last_work.contact_stay_event_count);
	assert(grid->last_work.contact_end_event_count ==
	       reference->last_work.contact_end_event_count);
	assert(grid->last_work.position_correction_visit_count ==
	       reference->last_work.position_correction_visit_count);
	assert(grid->last_work.solver_iteration_count ==
	       reference->last_work.solver_iteration_count);
	assert(grid->last_work.solver_contact_visit_count ==
	       reference->last_work.solver_contact_visit_count);
	assert(grid->last_work.solver_cached_contact_count ==
	       reference->last_work.solver_cached_contact_count);
	assert(grid->last_work.solver_changed_contact_count ==
	       reference->last_work.solver_changed_contact_count);
	assert(grid->last_work.distance_joint_count == reference->last_work.distance_joint_count);
	assert(grid->last_work.revolute_joint_count == reference->last_work.revolute_joint_count);
	assert(grid->last_work.revolute_motor_count == reference->last_work.revolute_motor_count);
	assert(grid->last_work.revolute_limit_count == reference->last_work.revolute_limit_count);
	assert(grid->last_work.prismatic_joint_count == reference->last_work.prismatic_joint_count);
	assert(grid->last_work.prismatic_motor_count == reference->last_work.prismatic_motor_count);
	assert(grid->last_work.prismatic_limit_count == reference->last_work.prismatic_limit_count);
	assert(grid->last_work.joint_position_correction_visit_count ==
	       reference->last_work.joint_position_correction_visit_count);
	assert(grid->last_work.joint_limit_position_correction_visit_count ==
	       reference->last_work.joint_limit_position_correction_visit_count);
	assert(grid->last_work.joint_limit_position_correction_changed_count ==
	       reference->last_work.joint_limit_position_correction_changed_count);
	assert(grid->last_work.joint_solver_visit_count ==
	       reference->last_work.joint_solver_visit_count);
	assert(grid->last_work.joint_solver_changed_count ==
	       reference->last_work.joint_solver_changed_count);
	assert(grid->last_work.joint_motor_solver_visit_count ==
	       reference->last_work.joint_motor_solver_visit_count);
	assert(grid->last_work.joint_motor_solver_changed_count ==
	       reference->last_work.joint_motor_solver_changed_count);
	assert(grid->last_work.joint_limit_solver_visit_count ==
	       reference->last_work.joint_limit_solver_visit_count);
	assert(grid->last_work.joint_limit_solver_changed_count ==
	       reference->last_work.joint_limit_solver_changed_count);
	assert(grid->last_work.awake_body_count == reference->last_work.awake_body_count);
	assert(grid->last_work.sleeping_body_count == reference->last_work.sleeping_body_count);
	assert(grid->last_work.body_sleep_transition_count ==
	       reference->last_work.body_sleep_transition_count);
	assert(grid->last_work.body_wake_transition_count ==
	       reference->last_work.body_wake_transition_count);
	assert(grid->last_work.sleeping_contact_count ==
	       reference->last_work.sleeping_contact_count);
	assert(grid->last_work.sleeping_joint_count == reference->last_work.sleeping_joint_count);
	assert(grid->last_work.spring_joint_count == reference->last_work.spring_joint_count);
	assert(grid->last_work.spring_solver_visit_count ==
	       reference->last_work.spring_solver_visit_count);
	assert(grid->last_work.spring_solver_changed_count ==
	       reference->last_work.spring_solver_changed_count);
	assert(grid->last_work.conveyor_contact_count ==
	       reference->last_work.conveyor_contact_count);
	assert(grid->last_work.conveyor_solver_visit_count ==
	       reference->last_work.conveyor_solver_visit_count);
	assert(grid->last_work.conveyor_solver_changed_count ==
	       reference->last_work.conveyor_solver_changed_count);
	assert(grid->last_work.rope_count == reference->last_work.rope_count);
	assert(grid->last_work.rope_particle_count == reference->last_work.rope_particle_count);
	assert(grid->last_work.rope_solver_iteration_count ==
	       reference->last_work.rope_solver_iteration_count);
	assert(grid->last_work.rope_constraint_visit_count ==
	       reference->last_work.rope_constraint_visit_count);
	assert(grid->last_work.rope_constraint_changed_count ==
	       reference->last_work.rope_constraint_changed_count);
	assert(grid->last_work.rope_body_correction_visit_count ==
	       reference->last_work.rope_body_correction_visit_count);
	assert(grid->last_work.rope_body_correction_changed_count ==
	       reference->last_work.rope_body_correction_changed_count);
	assert(grid->last_work.rope_body_velocity_visit_count ==
	       reference->last_work.rope_body_velocity_visit_count);
	assert(grid->last_work.rope_body_velocity_changed_count ==
	       reference->last_work.rope_body_velocity_changed_count);
	assert(grid->last_work.rope_collision_possible_pair_count ==
	       reference->last_work.rope_collision_possible_pair_count);
	assert(grid->last_work.rope_collision_candidate_pair_count ==
	       reference->last_work.rope_collision_candidate_pair_count);
	assert(grid->last_work.rope_collision_contact_count ==
	       reference->last_work.rope_collision_contact_count);
	assert(grid->last_work.rope_collision_position_changed_count ==
	       reference->last_work.rope_collision_position_changed_count);
	assert(grid->last_work.rope_collision_velocity_changed_count ==
	       reference->last_work.rope_collision_velocity_changed_count);
	assert(reference->last_work.broad_phase_fallback_count == 0U);
	assert(picosystem_physics_world_hash(grid) == picosystem_physics_world_hash(reference));

	for (uint16_t index = 0U; index < grid->body_count; ++index) {
		assert_body_equal(&grid->bodies[index], &reference->bodies[index]);
		assert(grid->solver_velocity_revisions[index] ==
		       reference->solver_velocity_revisions[index]);
		assert(grid->active_body_contact_masks[index] ==
		       reference->active_body_contact_masks[index]);
		assert(grid->active_segment_contact_masks[index] ==
		       reference->active_segment_contact_masks[index]);
		assert(grid->active_sensor_contact_masks[index] ==
		       reference->active_sensor_contact_masks[index]);
		assert(grid->sleep_quiet_tick_counts[index] ==
		       reference->sleep_quiet_tick_counts[index]);
	}
	for (uint16_t index = 0U; index < grid->static_segment_count; ++index) {
		assert_static_segment_equal(&grid->static_segments[index],
					    &reference->static_segments[index]);
	}
	for (uint16_t index = 0U; index < grid->box_sensor_count; ++index) {
		assert_vector_equal(&grid->box_sensors[index].center,
				    &reference->box_sensors[index].center);
		assert_vector_equal(&grid->box_sensors[index].half_extent,
				    &reference->box_sensors[index].half_extent);
		assert(grid->box_sensors[index].id == reference->box_sensors[index].id);
	}
	for (uint16_t index = 0U; index < grid->rope_count; ++index) {
		assert_rope_equal(&grid->ropes[index], &reference->ropes[index]);
	}
	for (uint16_t index = 0U; index < grid->contact_count; ++index) {
		assert_contact_equal(&grid->contacts[index], &reference->contacts[index]);
	}
	for (uint16_t index = 0U; index < grid->contact_event_count; ++index) {
		assert_contact_event_equal(&grid->contact_events[index],
					   &reference->contact_events[index]);
	}
	for (uint16_t index = 0U; index < grid->distance_joint_count; ++index) {
		assert_distance_joint_equal(&grid->distance_joints[index],
					    &reference->distance_joints[index]);
	}
	for (uint16_t index = 0U; index < grid->revolute_joint_count; ++index) {
		assert_revolute_joint_equal(&grid->revolute_joints[index],
					    &reference->revolute_joints[index]);
	}
	for (uint16_t index = 0U; index < grid->prismatic_joint_count; ++index) {
		assert_prismatic_joint_equal(&grid->prismatic_joints[index],
					     &reference->prismatic_joints[index]);
	}
}

static void test_initialization_and_add_boundaries(void)
{
	struct picosystem_physics_world world = {.max_speed_per_tick = 123};
	assert(picosystem_physics_world_init(NULL, FIXED(1)) == -EINVAL);
	assert(picosystem_physics_world_init(&world, 0) == -ERANGE);
	assert(world.max_speed_per_tick == 123);
	assert(picosystem_physics_world_init(&world, FIXED(9)) == -ERANGE);
	assert(world.max_speed_per_tick == 123);
	init_world(&world, FIXED(2));

	assert(picosystem_physics_world_add_circle(NULL, NULL) == -EINVAL);
	assert(picosystem_physics_world_add_box(NULL, NULL) == -EINVAL);
	assert(picosystem_physics_world_add_capsule(NULL, NULL) == -EINVAL);
	assert(picosystem_physics_world_add_static_segment(NULL, NULL) == -EINVAL);
	assert(picosystem_physics_world_add_box_sensor(NULL, NULL) == -EINVAL);

	struct picosystem_physics_circle_config invalid = circle_config(1U, 0, 0, 1);
	invalid.radius = 0;
	const uint32_t empty_hash = picosystem_physics_world_hash(&world);
	assert(picosystem_physics_world_add_circle(&world, &invalid) == -ERANGE);
	assert(world.body_count == 0U);
	assert(picosystem_physics_world_hash(&world) == empty_hash);

	for (uint16_t index = 0U; index < PICOSYSTEM_PHYSICS_MAX_BODIES; ++index) {
		struct picosystem_physics_circle_config config =
			circle_config((uint16_t)(index + 1U), (int32_t)index * 3, 0, 1);
		assert(picosystem_physics_world_add_circle(&world, &config) == 0);
	}
	struct picosystem_physics_circle_config duplicate = circle_config(1U, 0, 3, 1);
	assert(picosystem_physics_world_add_circle(&world, &duplicate) == -ENOSPC);
	struct picosystem_physics_circle_config excess = circle_config(99U, 0, 3, 1);
	assert(picosystem_physics_world_add_circle(&world, &excess) == -ENOSPC);
	assert(world.body_count == PICOSYSTEM_PHYSICS_MAX_BODIES);

	for (uint16_t index = 0U; index < PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS; ++index) {
		const struct picosystem_physics_segment_config segment =
			horizontal_segment((uint16_t)(index + 1U), (int32_t)index + 10);
		assert(picosystem_physics_world_add_static_segment(&world, &segment) == 0);
	}
	const struct picosystem_physics_segment_config excess_segment = horizontal_segment(99U, 30);
	assert(picosystem_physics_world_add_static_segment(&world, &excess_segment) == -ENOSPC);
	assert(world.static_segment_count == PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS);

	struct picosystem_physics_world sensor_world;
	init_world(&sensor_world, FIXED(2));
	struct picosystem_physics_box_sensor_config sensor = box_sensor_config(201U, 10, 10, 2, 3);
	const uint32_t empty_sensor_hash = picosystem_physics_world_hash(&sensor_world);
	sensor.half_extent.x = 0;
	assert(picosystem_physics_world_add_box_sensor(&sensor_world, &sensor) == -ERANGE);
	assert(picosystem_physics_world_hash(&sensor_world) == empty_sensor_hash);
	sensor = box_sensor_config(201U, 10, 10, 2, 3);
	assert(picosystem_physics_world_add_box_sensor(&sensor_world, &sensor) == 0);
	assert(picosystem_physics_world_add_box_sensor(&sensor_world, &sensor) == -EEXIST);
	for (uint16_t index = 1U; index < PICOSYSTEM_PHYSICS_MAX_BOX_SENSORS; ++index) {
		sensor = box_sensor_config((uint16_t)(201U + index), 10 + index, 10, 2, 3);
		assert(picosystem_physics_world_add_box_sensor(&sensor_world, &sensor) == 0);
	}
	sensor = box_sensor_config(250U, 30, 30, 2, 3);
	assert(picosystem_physics_world_add_box_sensor(&sensor_world, &sensor) == -ENOSPC);
	assert(sensor_world.box_sensor_count == PICOSYSTEM_PHYSICS_MAX_BOX_SENSORS);
	sensor_world.box_sensors[0].id = 0U;
	assert(picosystem_physics_world_step(&sensor_world, &no_acceleration) == -ERANGE);

	struct picosystem_physics_world box_world;
	init_world(&box_world, FIXED(2));
	struct picosystem_physics_box_config invalid_box = box_config(1U, 0, 0, 1, 1);
	invalid_box.half_extent.x = 0;
	assert(picosystem_physics_world_add_box(&box_world, &invalid_box) == -ERANGE);
	assert(box_world.body_count == 0U);
	const struct picosystem_physics_box_config valid_box = box_config(1U, 0, 0, 1, 1);
	assert(picosystem_physics_world_add_box(&box_world, &valid_box) == 0);
	assert(picosystem_physics_world_add_box(&box_world, &valid_box) == -EEXIST);
	assert(box_world.bodies[0].shape == PICOSYSTEM_PHYSICS_SHAPE_BOX);
	assert(box_world.bodies[0].inverse_inertia > 0);
	box_world.bodies[0].inverse_inertia = 0;
	assert(picosystem_physics_world_step(&box_world, &no_acceleration) == -ERANGE);
}

static void test_capsule_boundaries_and_geometry(void)
{
	struct picosystem_physics_world world;
	init_world(&world, FIXED(4));
	struct picosystem_physics_capsule_config invalid = capsule_config(1U, 10, 20, 3, 2);
	invalid.half_length = 0;
	const uint32_t empty_hash = picosystem_physics_world_hash(&world);
	assert(picosystem_physics_world_add_capsule(&world, &invalid) == -ERANGE);
	assert(world.body_count == 0U);
	assert(picosystem_physics_world_hash(&world) == empty_hash);
	invalid = capsule_config(1U, 10, 20, 3, 2);
	invalid.radius = FIXED(65);
	assert(picosystem_physics_world_add_capsule(&world, &invalid) == -ERANGE);

	struct picosystem_physics_capsule_config capsule = capsule_config(1U, 10, 20, 3, 2);
	capsule.angle_turns = PICOSYSTEM_PHYSICS_ANGLE_QUARTER_TURN;
	assert(picosystem_physics_world_add_capsule(&world, &capsule) == 0);
	assert(picosystem_physics_world_add_capsule(&world, &capsule) == -EEXIST);
	assert(world.bodies[0].shape == PICOSYSTEM_PHYSICS_SHAPE_CAPSULE);
	assert(world.bodies[0].half_extent.x == FIXED(3));
	assert(world.bodies[0].half_extent.y == 0);
	assert(world.bodies[0].radius == FIXED(2));
	assert(world.bodies[0].inverse_inertia > 0);

	struct picosystem_physics_vector start;
	struct picosystem_physics_vector end;
	assert(picosystem_physics_body_capsule_endpoints(&world.bodies[0], &start, &end) == 0);
	assert(start.x == FIXED(10));
	assert(start.y == FIXED(17));
	assert(end.x == FIXED(10));
	assert(end.y == FIXED(23));
	struct picosystem_physics_vector vertices[PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT];
	assert(picosystem_physics_body_capsule_vertices(&world.bodies[0], vertices) == 0);
	assert(vertices[0].x == FIXED(12));
	assert(vertices[0].y == FIXED(17));
	assert(vertices[1].x == FIXED(12));
	assert(vertices[1].y == FIXED(23));
	assert(vertices[2].x == FIXED(8));
	assert(vertices[2].y == FIXED(23));
	assert(vertices[3].x == FIXED(8));
	assert(vertices[3].y == FIXED(17));
	assert(picosystem_physics_body_capsule_endpoints(NULL, &start, &end) == -EINVAL);
	assert(picosystem_physics_body_capsule_endpoints(&world.bodies[0], NULL, &end) == -EINVAL);
	assert(picosystem_physics_body_box_vertices(&world.bodies[0], vertices) == -ENOTSUP);
	struct picosystem_physics_body wrong_shape = world.bodies[0];
	wrong_shape.shape = PICOSYSTEM_PHYSICS_SHAPE_CIRCLE;
	assert(picosystem_physics_body_capsule_vertices(&wrong_shape, vertices) == -ENOTSUP);

	world.bodies[0].half_extent.y = 1;
	assert(picosystem_physics_world_step(&world, &no_acceleration) == -ERANGE);
}

static void test_rope_boundaries_dynamics_and_reference(void)
{
	struct picosystem_physics_world world;
	init_world(&world, FIXED(4));
	assert(picosystem_physics_world_add_rope(NULL, NULL) == -EINVAL);
	struct picosystem_physics_rope_config invalid = rope_config(101U, 0, 0, 6, 0, 1U, 2);
	const uint32_t empty_hash = picosystem_physics_world_hash(&world);
	assert(picosystem_physics_world_add_rope(&world, &invalid) == -ERANGE);
	assert(world.rope_count == 0U);
	assert(picosystem_physics_world_hash(&world) == empty_hash);
	invalid = rope_config(101U, 0, 0, 6, 0, 4U, 2);
	invalid.collision_radius = -1;
	assert(picosystem_physics_world_add_rope(&world, &invalid) == -ERANGE);
	invalid.collision_radius = PICOSYSTEM_PHYSICS_FIXED_ONE / 2;
	assert(picosystem_physics_world_add_rope(&world, &invalid) == -ERANGE);
	invalid.collision_radius = FIXED(9);
	assert(picosystem_physics_world_add_rope(&world, &invalid) == -ERANGE);
	invalid = rope_config(101U, 0, 0, 6, 0, 4U, 2);
	invalid.endpoint_a.reaction_enabled = 1U;
	assert(picosystem_physics_world_add_rope(&world, &invalid) == -ERANGE);
	invalid = rope_config(101U, 0, 0, 6, 0, 4U, 2);
	invalid.endpoint_a.body_id = 99U;
	invalid.endpoint_a.pinned = 0U;
	assert(picosystem_physics_world_add_rope(&world, &invalid) == -ERANGE);
	invalid.endpoint_a.pinned = 1U;
	assert(picosystem_physics_world_add_rope(&world, &invalid) == -ENOENT);

	struct picosystem_physics_capsule_config capsule = capsule_config(1U, 10, 10, 3, 2);
	capsule.velocity_per_tick.x = RATIO(1, 2);
	capsule.angular_velocity_per_tick = RATIO(1, 128);
	assert(picosystem_physics_world_add_capsule(&world, &capsule) == 0);
	struct picosystem_physics_rope_config attached = rope_config(101U, 0, 0, 20, 10, 4U, 3);
	attached.endpoint_a.anchor.x = FIXED(3);
	attached.endpoint_a.body_id = 1U;
	attached.endpoint_a.pinned = 1U;
	struct picosystem_physics_rope_config invalid_reaction = attached;
	invalid_reaction.endpoint_a.reaction_enabled = 2U;
	assert(picosystem_physics_world_add_rope(&world, &invalid_reaction) == -ERANGE);
	invalid_reaction = attached;
	invalid_reaction.endpoint_b = invalid_reaction.endpoint_a;
	invalid_reaction.endpoint_a.reaction_enabled = 1U;
	assert(picosystem_physics_world_add_rope(&world, &invalid_reaction) == -ERANGE);
	assert(picosystem_physics_world_add_rope(&world, &attached) == 0);
	assert(world.rope_count == 1U);
	assert(world.ropes[0].body_a_index == 0U);
	assert(world.ropes[0].body_b_index == UINT8_MAX);
	assert(world.ropes[0].particles[0].position.x == FIXED(13));
	assert(world.ropes[0].particles[0].position.y == FIXED(10));
	assert(world.ropes[0].particles[3].position.x == FIXED(20));
	assert(world.ropes[0].particles[3].position.y == FIXED(10));
	assert(picosystem_physics_world_rope_particle_at(&world, 0U, 0U) ==
	       &world.ropes[0].particles[0]);
	assert(picosystem_physics_world_rope_particle_at(NULL, 0U, 0U) == NULL);
	assert(picosystem_physics_world_rope_particle_at(&world, 1U, 0U) == NULL);
	assert(picosystem_physics_world_rope_particle_at(&world, 0U, 4U) == NULL);
	assert(picosystem_physics_world_add_rope(&world, &attached) == -EEXIST);

	struct picosystem_physics_world reference = world;
	const struct picosystem_physics_vector gravity = {.y = RATIO(1, 4)};
	assert(picosystem_physics_world_step(&world, &gravity) == 0);
	assert(picosystem_physics_world_step_reference(&reference, &gravity) == 0);
	assert_step_matches_reference(&world, &reference);
	struct picosystem_physics_vector capsule_start;
	struct picosystem_physics_vector capsule_end;
	assert(picosystem_physics_body_capsule_endpoints(&world.bodies[0], &capsule_start,
							 &capsule_end) == 0);
	assert_vector_equal(&world.ropes[0].particles[0].position, &capsule_end);
	assert_vector_equal(&world.ropes[0].particles[0].previous_position, &capsule_end);
	assert(world.last_work.rope_count == 1U);
	assert(world.last_work.rope_particle_count == 4U);
	assert(world.last_work.rope_solver_iteration_count ==
	       PICOSYSTEM_PHYSICS_ROPE_SOLVER_ITERATIONS);
	assert(world.last_work.rope_constraint_visit_count ==
	       PICOSYSTEM_PHYSICS_ROPE_SOLVER_ITERATIONS * 3U);

	struct picosystem_physics_rope_config second = rope_config(102U, 30, 10, 36, 10, 4U, 2);
	assert(picosystem_physics_world_add_rope(&world, &second) == 0);
	struct picosystem_physics_rope_config excess = rope_config(103U, 40, 10, 46, 10, 4U, 2);
	assert(picosystem_physics_world_add_rope(&world, &excess) == -ENOSPC);
	assert(world.rope_count == PICOSYSTEM_PHYSICS_MAX_ROPES);
	world.ropes[0].particle_count = 1U;
	assert(picosystem_physics_world_step(&world, &no_acceleration) == -ERANGE);

	struct picosystem_physics_world free_world;
	init_world(&free_world, FIXED(4));
	const struct picosystem_physics_rope_config free_rope =
		rope_config(101U, 0, 0, 6, 0, 4U, 2);
	assert(picosystem_physics_world_add_rope(&free_world, &free_rope) == 0);
	assert(picosystem_physics_world_step(&free_world, &gravity) == 0);
	for (uint8_t index = 0U; index < 4U; ++index) {
		assert(free_world.ropes[0].particles[index].position.y == RATIO(1, 4));
	}
	assert(free_world.last_work.rope_constraint_changed_count <=
	       free_world.last_work.rope_constraint_visit_count);

	struct picosystem_physics_world slack_world;
	init_world(&slack_world, FIXED(4));
	struct picosystem_physics_rope_config slack = rope_config(101U, 0, 0, 6, 0, 4U, 3);
	slack.endpoint_a.pinned = 1U;
	slack.endpoint_b.pinned = 1U;
	assert(picosystem_physics_world_add_rope(&slack_world, &slack) == 0);
	for (uint32_t step = 0U; step < 60U; ++step) {
		assert(picosystem_physics_world_step(&slack_world, &gravity) == 0);
	}
	assert(slack_world.ropes[0].particles[0].position.x == 0);
	assert(slack_world.ropes[0].particles[0].position.y == 0);
	assert(slack_world.ropes[0].particles[3].position.x == FIXED(6));
	assert(slack_world.ropes[0].particles[3].position.y == 0);
	assert(slack_world.ropes[0].particles[1].position.y > 0);
	assert(slack_world.ropes[0].particles[2].position.y > 0);
	for (uint8_t index = 0U; index < 3U; ++index) {
		assert_distance_between(&slack_world.ropes[0].particles[index].position,
					&slack_world.ropes[0].particles[index + 1U].position,
					FIXED(3) - RATIO(1, 8), FIXED(3) + RATIO(1, 8));
	}
}

static void test_rope_body_reaction_and_sleep_policy(void)
{
	struct picosystem_physics_world suspended;
	init_world(&suspended, FIXED(8));
	const struct picosystem_physics_circle_config bob = circle_config(1U, 0, 0, 1);
	assert(picosystem_physics_world_add_circle(&suspended, &bob) == 0);
	struct picosystem_physics_rope_config tether = rope_config(101U, 0, 0, 10, 0, 2U, 5);
	tether.endpoint_a.body_id = 1U;
	tether.endpoint_a.pinned = 1U;
	tether.endpoint_a.reaction_enabled = 1U;
	tether.endpoint_b.pinned = 1U;
	assert(picosystem_physics_world_add_rope(&suspended, &tether) == 0);

	struct picosystem_physics_world reference = suspended;
	assert(picosystem_physics_world_step(&suspended, &no_acceleration) == 0);
	assert(picosystem_physics_world_step_reference(&reference, &no_acceleration) == 0);
	assert_step_matches_reference(&suspended, &reference);
	assert_fixed_close(suspended.bodies[0].center.x, FIXED(5), 2);
	assert(suspended.bodies[0].center.y == 0);
	assert_fixed_close(suspended.bodies[0].velocity_per_tick.x, 0, 2);
	assert_fixed_close(suspended.ropes[0].particles[0].position.x, FIXED(5), 2);
	assert(suspended.last_work.rope_body_correction_visit_count ==
	       PICOSYSTEM_PHYSICS_ROPE_SOLVER_ITERATIONS);
	assert(suspended.last_work.rope_body_correction_changed_count == 1U);
	assert(suspended.last_work.rope_body_velocity_visit_count == 1U);
	assert(suspended.last_work.rope_body_velocity_changed_count == 0U);
	assert(!picosystem_physics_world_body_is_sleeping(&suspended, 0U));
	assert(picosystem_physics_world_step(&suspended, &no_acceleration) == 0);
	assert_fixed_close(suspended.bodies[0].center.x, FIXED(5), 4);
	assert_fixed_close(suspended.bodies[0].velocity_per_tick.x, 0, 4);
	for (uint32_t tick = 0U; tick < PICOSYSTEM_PHYSICS_SLEEP_QUIET_TICKS; ++tick) {
		assert(picosystem_physics_world_step(&suspended, &no_acceleration) == 0);
	}
	assert(picosystem_physics_world_body_is_sleeping(&suspended, 0U));

	struct picosystem_physics_world kinematic;
	init_world(&kinematic, FIXED(8));
	assert(picosystem_physics_world_add_circle(&kinematic, &bob) == 0);
	tether.endpoint_a.reaction_enabled = 0U;
	assert(picosystem_physics_world_add_rope(&kinematic, &tether) == 0);
	assert(picosystem_physics_world_hash(&kinematic) !=
	       picosystem_physics_world_hash(&reference));
	assert(picosystem_physics_world_step(&kinematic, &no_acceleration) == 0);
	assert(kinematic.bodies[0].center.x == 0);
	assert(kinematic.ropes[0].particles[0].position.x == 0);

	struct picosystem_physics_world hanging;
	init_world(&hanging, FIXED(8));
	const struct picosystem_physics_circle_config hanging_bob = circle_config(1U, 0, 5, 1);
	assert(picosystem_physics_world_add_circle(&hanging, &hanging_bob) == 0);
	struct picosystem_physics_rope_config vertical = rope_config(104U, 0, 0, 0, 0, 2U, 5);
	vertical.endpoint_a.body_id = 1U;
	vertical.endpoint_a.pinned = 1U;
	vertical.endpoint_a.reaction_enabled = 1U;
	vertical.endpoint_b.pinned = 1U;
	assert(picosystem_physics_world_add_rope(&hanging, &vertical) == 0);
	const struct picosystem_physics_vector gravity = {.y = RATIO(1, 4)};
	for (uint32_t tick = 0U; tick < 240U; ++tick) {
		assert(picosystem_physics_world_step(&hanging, &gravity) == 0);
		assert_fixed_close(hanging.bodies[0].center.x, 0, 2);
		assert_fixed_close(hanging.bodies[0].center.y, FIXED(5), 8);
		assert_fixed_close(hanging.bodies[0].velocity_per_tick.y, 0, 8);
	}
	assert(picosystem_physics_world_body_is_sleeping(&hanging, 0U));

	struct picosystem_physics_world pair;
	init_world(&pair, FIXED(8));
	const struct picosystem_physics_circle_config left = circle_config(1U, 0, 0, 1);
	const struct picosystem_physics_circle_config right = circle_config(2U, 10, 0, 1);
	assert(picosystem_physics_world_add_circle(&pair, &left) == 0);
	assert(picosystem_physics_world_add_circle(&pair, &right) == 0);
	struct picosystem_physics_rope_config bridge = rope_config(102U, 0, 0, 0, 0, 2U, 6);
	bridge.endpoint_a.body_id = 1U;
	bridge.endpoint_a.pinned = 1U;
	bridge.endpoint_a.reaction_enabled = 1U;
	bridge.endpoint_b.body_id = 2U;
	bridge.endpoint_b.pinned = 1U;
	bridge.endpoint_b.reaction_enabled = 1U;
	assert(picosystem_physics_world_add_rope(&pair, &bridge) == 0);
	assert(picosystem_physics_world_step(&pair, &no_acceleration) == 0);
	assert_fixed_close(pair.bodies[0].center.x, FIXED(2), 2);
	assert_fixed_close(pair.bodies[1].center.x, FIXED(8), 2);
	assert_fixed_close(pair.bodies[0].velocity_per_tick.x, 0, 2);
	assert_fixed_close(pair.bodies[1].velocity_per_tick.x, 0, 2);
	assert_fixed_close(pair.bodies[0].center.x + pair.bodies[1].center.x, FIXED(10), 2);
	assert(pair.last_work.rope_body_correction_visit_count ==
	       2U * PICOSYSTEM_PHYSICS_ROPE_SOLVER_ITERATIONS);
	assert(pair.last_work.rope_body_correction_changed_count == 2U);
	assert(pair.last_work.rope_body_velocity_visit_count == 2U);
	assert(pair.last_work.rope_body_velocity_changed_count == 0U);
	assert(picosystem_physics_world_step(&pair, &no_acceleration) == 0);
	assert_fixed_close(pair.bodies[0].center.x, FIXED(2), 4);
	assert_fixed_close(pair.bodies[1].center.x, FIXED(8), 4);
	assert_fixed_close(pair.bodies[0].velocity_per_tick.x, 0, 4);
	assert_fixed_close(pair.bodies[1].velocity_per_tick.x, 0, 4);

	struct picosystem_physics_world off_center;
	init_world(&off_center, FIXED(8));
	struct picosystem_physics_box_config arm = box_config(1U, 0, 0, 2, 2);
	arm.velocity_per_tick.x = PICOSYSTEM_PHYSICS_FIXED_ONE;
	assert(picosystem_physics_world_add_box(&off_center, &arm) == 0);
	struct picosystem_physics_rope_config angled = rope_config(103U, 0, 0, 10, 1, 2U, 5);
	angled.endpoint_a.anchor.y = FIXED(1);
	angled.endpoint_a.body_id = 1U;
	angled.endpoint_a.pinned = 1U;
	angled.endpoint_a.reaction_enabled = 1U;
	angled.endpoint_b.pinned = 1U;
	assert(picosystem_physics_world_add_rope(&off_center, &angled) == 0);
	assert(picosystem_physics_world_step(&off_center, &no_acceleration) == 0);
	assert(off_center.bodies[0].center.x > 0);
	assert(off_center.bodies[0].angle_turns != 0U);
	assert(off_center.bodies[0].angular_velocity_per_tick != 0);
}

static void test_rope_particle_collision(void)
{
	struct picosystem_physics_world segment_world;
	init_world(&segment_world, FIXED(8));
	const struct picosystem_physics_segment_config floor = horizontal_segment(201U, 0);
	assert(picosystem_physics_world_add_static_segment(&segment_world, &floor) == 0);
	struct picosystem_physics_rope_config colliding = rope_config(101U, -2, 0, 2, 0, 2U, 4);
	colliding.collision_radius = FIXED(1);
	assert(picosystem_physics_world_add_rope(&segment_world, &colliding) == 0);
	struct picosystem_physics_world segment_reference = segment_world;
	assert(picosystem_physics_world_step(&segment_world, &no_acceleration) == 0);
	assert(picosystem_physics_world_step_reference(&segment_reference, &no_acceleration) == 0);
	assert_step_matches_reference(&segment_world, &segment_reference);
	for (uint8_t index = 0U; index < 2U; ++index) {
		assert(segment_world.ropes[0].particles[index].position.y == -FIXED(1));
		assert(segment_world.ropes[0].particles[index].previous_position.y == -FIXED(1));
	}
	assert(segment_world.last_work.rope_collision_possible_pair_count ==
	       2U * PICOSYSTEM_PHYSICS_ROPE_COLLISION_ITERATIONS);
	assert(segment_world.last_work.rope_collision_candidate_pair_count == 2U);
	assert(segment_world.last_work.rope_collision_contact_count == 2U);
	assert(segment_world.last_work.rope_collision_position_changed_count == 2U);
	assert(segment_world.last_work.rope_collision_velocity_changed_count == 0U);

	struct picosystem_physics_world swept_world;
	init_world(&swept_world, FIXED(8));
	assert(picosystem_physics_world_add_static_segment(&swept_world, &floor) == 0);
	struct picosystem_physics_rope_config tunneling = rope_config(102U, -2, -2, 2, -2, 2U, 4);
	tunneling.collision_radius = FIXED(1);
	assert(picosystem_physics_world_add_rope(&swept_world, &tunneling) == 0);
	for (uint8_t index = 0U; index < 2U; ++index) {
		swept_world.ropes[0].particles[index].previous_position.y = -FIXED(6);
	}
	struct picosystem_physics_world swept_reference = swept_world;
	assert(picosystem_physics_world_step(&swept_world, &no_acceleration) == 0);
	assert(picosystem_physics_world_step_reference(&swept_reference, &no_acceleration) == 0);
	assert_step_matches_reference(&swept_world, &swept_reference);
	for (uint8_t index = 0U; index < 2U; ++index) {
		assert_fixed_close(swept_world.ropes[0].particles[index].position.y, -FIXED(1), 4);
		assert_fixed_close(swept_world.ropes[0].particles[index].previous_position.y,
				   -FIXED(1), 4);
	}
	assert(swept_world.last_work.rope_collision_candidate_pair_count == 2U);
	assert(swept_world.last_work.rope_collision_contact_count == 2U);
	assert(swept_world.last_work.rope_collision_position_changed_count == 2U);
	assert(swept_world.last_work.rope_collision_velocity_changed_count == 2U);

	for (uint8_t shape = PICOSYSTEM_PHYSICS_SHAPE_CIRCLE;
	     shape <= PICOSYSTEM_PHYSICS_SHAPE_CAPSULE; ++shape) {
		struct picosystem_physics_world body_world;
		init_world(&body_world, FIXED(8));
		if (shape == PICOSYSTEM_PHYSICS_SHAPE_CIRCLE) {
			const struct picosystem_physics_circle_config body =
				circle_config(1U, 0, 0, 2);
			assert(picosystem_physics_world_add_circle(&body_world, &body) == 0);
		} else if (shape == PICOSYSTEM_PHYSICS_SHAPE_BOX) {
			const struct picosystem_physics_box_config body =
				box_config(1U, 0, 0, 2, 2);
			assert(picosystem_physics_world_add_box(&body_world, &body) == 0);
		} else {
			const struct picosystem_physics_capsule_config body =
				capsule_config(1U, 0, 0, 2, 1);
			assert(picosystem_physics_world_add_capsule(&body_world, &body) == 0);
		}
		struct picosystem_physics_rope_config rope = rope_config(101U, -2, 0, -6, 0, 2U, 4);
		rope.endpoint_b.pinned = 1U;
		rope.collision_radius = FIXED(1);
		assert(picosystem_physics_world_add_rope(&body_world, &rope) == 0);
		body_world.ropes[0].particles[0].previous_position.x = -FIXED(3);
		body_world.sleeping_body_mask = 1U;
		body_world.sleep_quiet_tick_counts[0] = PICOSYSTEM_PHYSICS_SLEEP_QUIET_TICKS;
		struct picosystem_physics_world body_reference = body_world;
		assert(picosystem_physics_world_step(&body_world, &no_acceleration) == 0);
		assert(picosystem_physics_world_step_reference(&body_reference, &no_acceleration) ==
		       0);
		assert_step_matches_reference(&body_world, &body_reference);
		assert(body_world.sleeping_body_mask == 0U);
		assert(body_world.last_work.body_wake_transition_count == 1U);
		assert((body_world.bodies[0].center.x != 0) ||
		       (body_world.bodies[0].center.y != 0));
		assert(body_world.last_work.rope_collision_possible_pair_count ==
		       PICOSYSTEM_PHYSICS_ROPE_COLLISION_ITERATIONS);
		assert(body_world.last_work.rope_collision_candidate_pair_count > 0U);
		assert(body_world.last_work.rope_collision_contact_count > 0U);
		assert(body_world.last_work.rope_collision_position_changed_count > 0U);
		if (shape == PICOSYSTEM_PHYSICS_SHAPE_CIRCLE) {
			assert(body_world.bodies[0].velocity_per_tick.x > 0);
			assert(body_world.last_work.rope_collision_velocity_changed_count > 0U);
		}
	}

	struct picosystem_physics_world self_collision_disabled;
	init_world(&self_collision_disabled, FIXED(8));
	struct picosystem_physics_rope_config crossing = rope_config(101U, -2, 0, 0, 2, 4U, 4);
	assert(picosystem_physics_world_add_rope(&self_collision_disabled, &crossing) == 0);
	self_collision_disabled.ropes[0].particles[1].position =
		(struct picosystem_physics_vector){.x = FIXED(2)};
	self_collision_disabled.ropes[0].particles[1].previous_position =
		self_collision_disabled.ropes[0].particles[1].position;
	self_collision_disabled.ropes[0].particles[2].position =
		(struct picosystem_physics_vector){.y = -FIXED(2)};
	self_collision_disabled.ropes[0].particles[2].previous_position =
		self_collision_disabled.ropes[0].particles[2].position;
	struct picosystem_physics_world no_self_collision = self_collision_disabled;
	no_self_collision.ropes[0].collision_radius = FIXED(1);
	assert(picosystem_physics_world_hash(&self_collision_disabled) !=
	       picosystem_physics_world_hash(&no_self_collision));
	assert(picosystem_physics_world_step(&self_collision_disabled, &no_acceleration) == 0);
	assert(picosystem_physics_world_step(&no_self_collision, &no_acceleration) == 0);
	for (uint8_t index = 0U; index < 4U; ++index) {
		assert_vector_equal(&self_collision_disabled.ropes[0].particles[index].position,
				    &no_self_collision.ropes[0].particles[index].position);
		assert_vector_equal(
			&self_collision_disabled.ropes[0].particles[index].previous_position,
			&no_self_collision.ropes[0].particles[index].previous_position);
	}
	assert(no_self_collision.last_work.rope_collision_possible_pair_count == 0U);
}

static void test_duplicate_ids_and_invalid_segments(void)
{
	struct picosystem_physics_world world;
	init_world(&world, FIXED(2));

	const struct picosystem_physics_circle_config body = circle_config(7U, 0, 0, 1);
	assert(picosystem_physics_world_add_circle(&world, &body) == 0);
	assert(picosystem_physics_world_add_circle(&world, &body) == -EEXIST);
	assert(world.body_count == 1U);

	struct picosystem_physics_segment_config segment = horizontal_segment(8U, 4);
	assert(picosystem_physics_world_add_static_segment(&world, &segment) == 0);
	assert(world.static_segments[0].normal.x == 0);
	assert(world.static_segments[0].normal.y == PICOSYSTEM_PHYSICS_FIXED_ONE);
	assert(picosystem_physics_world_add_static_segment(&world, &segment) == -EEXIST);
	segment.id = 9U;
	segment.end = segment.start;
	assert(picosystem_physics_world_add_static_segment(&world, &segment) == -ERANGE);
	segment = horizontal_segment(9U, 5);
	segment.surface_speed_per_tick = FIXED(17);
	assert(picosystem_physics_world_add_static_segment(&world, &segment) == -ERANGE);
	assert(world.static_segment_count == 1U);

	world.static_segments[0].normal.x = PICOSYSTEM_PHYSICS_FIXED_ONE;
	world.static_segments[0].normal.y = 0;
	assert(picosystem_physics_world_step(&world, &no_acceleration) == -ERANGE);
}

static void test_sensor_overlap_and_contact_event_lifecycle(void)
{
	struct picosystem_physics_world sensor_world;
	init_world(&sensor_world, FIXED(2));
	struct picosystem_physics_circle_config moving = circle_config(1U, 5, 10, 1);
	moving.velocity_per_tick.x = FIXED(2);
	const struct picosystem_physics_box_sensor_config sensor =
		box_sensor_config(201U, 10, 10, 2, 2);
	assert(picosystem_physics_world_add_circle(&sensor_world, &moving) == 0);
	assert(picosystem_physics_world_add_box_sensor(&sensor_world, &sensor) == 0);
	assert(picosystem_physics_world_contact_event_at(NULL, 0U) == NULL);
	assert(picosystem_physics_world_contact_event_at(&sensor_world, 0U) == NULL);

	assert(picosystem_physics_world_step(&sensor_world, &no_acceleration) == 0);
	assert(sensor_world.contact_count == 0U);
	assert(sensor_world.contact_event_count == 0U);
	assert(sensor_world.last_work.sensor_overlap_count == 0U);
	assert(sensor_world.bodies[0].velocity_per_tick.x == FIXED(2));

	assert(picosystem_physics_world_step(&sensor_world, &no_acceleration) == 0);
	assert(sensor_world.contact_count == 0U);
	assert(sensor_world.contact_event_count == 1U);
	assert_contact_event(&sensor_world, 0U, 1U, 201U,
			     PICOSYSTEM_PHYSICS_CONTACT_EVENT_BODY_BOX_SENSOR,
			     PICOSYSTEM_PHYSICS_CONTACT_EVENT_BEGIN);
	assert(sensor_world.last_work.active_contact_pair_count == 1U);
	assert(sensor_world.last_work.sensor_overlap_count == 1U);
	assert(sensor_world.last_work.contact_begin_event_count == 1U);
	assert(sensor_world.active_sensor_contact_masks[0] == UINT8_C(1));
	struct picosystem_physics_world inactive_copy = sensor_world;
	inactive_copy.active_sensor_contact_masks[0] = 0U;
	assert(picosystem_physics_world_hash(&sensor_world) !=
	       picosystem_physics_world_hash(&inactive_copy));

	assert(picosystem_physics_world_step(&sensor_world, &no_acceleration) == 0);
	assert(sensor_world.contact_event_count == 1U);
	assert_contact_event(&sensor_world, 0U, 1U, 201U,
			     PICOSYSTEM_PHYSICS_CONTACT_EVENT_BODY_BOX_SENSOR,
			     PICOSYSTEM_PHYSICS_CONTACT_EVENT_STAY);
	assert(sensor_world.last_work.contact_stay_event_count == 1U);

	assert(picosystem_physics_world_step(&sensor_world, &no_acceleration) == 0);
	assert(sensor_world.contact_event_count == 1U);
	assert_contact_event(&sensor_world, 0U, 1U, 201U,
			     PICOSYSTEM_PHYSICS_CONTACT_EVENT_BODY_BOX_SENSOR,
			     PICOSYSTEM_PHYSICS_CONTACT_EVENT_END);
	assert(sensor_world.last_work.active_contact_pair_count == 0U);
	assert(sensor_world.last_work.contact_end_event_count == 1U);
	assert(sensor_world.active_sensor_contact_masks[0] == 0U);
	assert(sensor_world.bodies[0].velocity_per_tick.x == FIXED(2));

	assert(picosystem_physics_world_step(&sensor_world, &no_acceleration) == 0);
	assert(sensor_world.contact_event_count == 0U);
	assert(picosystem_physics_world_contact_event_at(&sensor_world, 0U) == NULL);

	struct picosystem_physics_world physical_world;
	init_world(&physical_world, FIXED(2));
	const struct picosystem_physics_circle_config circle = circle_config(1U, 0, 0, 2);
	const struct picosystem_physics_segment_config floor = horizontal_segment(101U, 1);
	assert(picosystem_physics_world_add_circle(&physical_world, &circle) == 0);
	assert(picosystem_physics_world_add_static_segment(&physical_world, &floor) == 0);
	assert(picosystem_physics_world_step(&physical_world, &no_acceleration) == 0);
	assert(physical_world.contact_count == 1U);
	assert(physical_world.contact_event_count == 1U);
	assert_contact_event(&physical_world, 0U, 1U, 101U,
			     PICOSYSTEM_PHYSICS_CONTACT_EVENT_BODY_STATIC_SEGMENT,
			     PICOSYSTEM_PHYSICS_CONTACT_EVENT_BEGIN);
	assert(picosystem_physics_world_step(&physical_world, &no_acceleration) == 0);
	assert_contact_event(&physical_world, 0U, 1U, 101U,
			     PICOSYSTEM_PHYSICS_CONTACT_EVENT_BODY_STATIC_SEGMENT,
			     PICOSYSTEM_PHYSICS_CONTACT_EVENT_STAY);
	physical_world.bodies[0].center.y = -FIXED(10);
	assert(picosystem_physics_world_step(&physical_world, &no_acceleration) == 0);
	assert_contact_event(&physical_world, 0U, 1U, 101U,
			     PICOSYSTEM_PHYSICS_CONTACT_EVENT_BODY_STATIC_SEGMENT,
			     PICOSYSTEM_PHYSICS_CONTACT_EVENT_END);
}

static void test_exact_circle_and_rotated_box_sensor_overlap(void)
{
	struct picosystem_physics_world corner_world;
	init_world(&corner_world, FIXED(2));
	struct picosystem_physics_circle_config circle = circle_config(1U, 13, 13, 1);
	const struct picosystem_physics_box_sensor_config corner_sensor =
		box_sensor_config(201U, 10, 10, 2, 2);
	assert(picosystem_physics_world_add_circle(&corner_world, &circle) == 0);
	assert(picosystem_physics_world_add_box_sensor(&corner_world, &corner_sensor) == 0);
	assert(picosystem_physics_world_step(&corner_world, &no_acceleration) == 0);
	assert(corner_world.contact_event_count == 0U);

	init_world(&corner_world, FIXED(2));
	circle.center.x = FIXED(12) + RATIO(1, 2);
	circle.center.y = FIXED(12) + RATIO(1, 2);
	assert(picosystem_physics_world_add_circle(&corner_world, &circle) == 0);
	assert(picosystem_physics_world_add_box_sensor(&corner_world, &corner_sensor) == 0);
	assert(picosystem_physics_world_step(&corner_world, &no_acceleration) == 0);
	assert(corner_world.contact_event_count == 1U);
	assert_contact_event(&corner_world, 0U, 1U, 201U,
			     PICOSYSTEM_PHYSICS_CONTACT_EVENT_BODY_BOX_SENSOR,
			     PICOSYSTEM_PHYSICS_CONTACT_EVENT_BEGIN);

	struct picosystem_physics_world box_world;
	init_world(&box_world, FIXED(2));
	struct picosystem_physics_box_config box = box_config(1U, 10, 10, 4, 1);
	box.angle_turns = UINT32_C(0x20000000);
	const struct picosystem_physics_box_sensor_config separated =
		box_sensor_config(201U, 14, 6, 1, 1);
	const struct picosystem_physics_box_sensor_config overlapping =
		box_sensor_config(202U, 13, 13, 1, 1);
	assert(picosystem_physics_world_add_box(&box_world, &box) == 0);
	assert(picosystem_physics_world_add_box_sensor(&box_world, &separated) == 0);
	assert(picosystem_physics_world_add_box_sensor(&box_world, &overlapping) == 0);
	assert(picosystem_physics_world_step(&box_world, &no_acceleration) == 0);
	assert(box_world.last_broad_phase_fallback == 0U);
	assert(box_world.last_work.body_sensor_narrow_phase_test_count == 2U);
	assert(box_world.last_work.sensor_overlap_count == 1U);
	assert(box_world.contact_event_count == 1U);
	assert_contact_event(&box_world, 0U, 1U, 202U,
			     PICOSYSTEM_PHYSICS_CONTACT_EVENT_BODY_BOX_SENSOR,
			     PICOSYSTEM_PHYSICS_CONTACT_EVENT_BEGIN);
}

static void test_distance_joint_boundaries_and_endpoints(void)
{
	struct picosystem_physics_world world;
	init_world(&world, FIXED(4));
	struct picosystem_physics_box_config box = box_config(1U, 10, 20, 2, 1);
	box.angle_turns = PICOSYSTEM_PHYSICS_ANGLE_QUARTER_TURN;
	const struct picosystem_physics_circle_config circle = circle_config(2U, 30, 40, 3);
	assert(picosystem_physics_world_add_box(&world, &box) == 0);
	assert(picosystem_physics_world_add_circle(&world, &circle) == 0);

	assert(picosystem_physics_world_add_distance_joint(NULL, NULL) == -EINVAL);
	assert(picosystem_physics_world_add_distance_joint(&world, NULL) == -EINVAL);
	struct picosystem_physics_distance_joint_config joint =
		distance_joint_config(101U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID, 20);
	joint.local_anchor_a.x = FIXED(2);
	joint.anchor_b = (struct picosystem_physics_vector){.x = FIXED(30), .y = FIXED(40)};
	assert(picosystem_physics_world_add_distance_joint(&world, &joint) == 0);
	assert(world.distance_joint_count == 1U);
	assert(world.distance_joints[0].body_a_index == 0U);
	assert(world.distance_joints[0].body_b_index == UINT8_MAX);

	struct picosystem_physics_vector anchor_a;
	struct picosystem_physics_vector anchor_b;
	assert(picosystem_physics_world_distance_joint_endpoints(&world, 0U, &anchor_a,
								 &anchor_b) == 0);
	assert(anchor_a.x == FIXED(10));
	assert(anchor_a.y == FIXED(22));
	assert(anchor_b.x == FIXED(30));
	assert(anchor_b.y == FIXED(40));
	assert(picosystem_physics_world_distance_joint_endpoints(NULL, 0U, &anchor_a, &anchor_b) ==
	       -EINVAL);
	assert(picosystem_physics_world_distance_joint_endpoints(&world, 0U, NULL, &anchor_b) ==
	       -EINVAL);
	assert(picosystem_physics_world_distance_joint_endpoints(&world, 1U, &anchor_a,
								 &anchor_b) == -ENOENT);

	const uint32_t one_joint_hash = picosystem_physics_world_hash(&world);
	assert(picosystem_physics_world_add_distance_joint(&world, &joint) == -EEXIST);
	assert(picosystem_physics_world_hash(&world) == one_joint_hash);

	struct picosystem_physics_distance_joint_config invalid = joint;
	invalid.id = 0U;
	assert(picosystem_physics_world_add_distance_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 102U;
	invalid.body_a_id = PICOSYSTEM_PHYSICS_WORLD_BODY_ID;
	assert(picosystem_physics_world_add_distance_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 102U;
	invalid.body_b_id = invalid.body_a_id;
	assert(picosystem_physics_world_add_distance_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 102U;
	invalid.target_distance = 0;
	assert(picosystem_physics_world_add_distance_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 102U;
	invalid.target_distance = FIXED(257);
	assert(picosystem_physics_world_add_distance_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 102U;
	invalid.local_anchor_a.x = INT32_MAX;
	assert(picosystem_physics_world_add_distance_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 102U;
	invalid.local_anchor_a.x = FIXED(3);
	assert(picosystem_physics_world_add_distance_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 102U;
	invalid.anchor_b.x = INT32_MAX;
	assert(picosystem_physics_world_add_distance_joint(&world, &invalid) == -ERANGE);
	assert(picosystem_physics_world_hash(&world) == one_joint_hash);

	struct picosystem_physics_distance_joint_config missing =
		distance_joint_config(102U, 99U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID, 1);
	assert(picosystem_physics_world_add_distance_joint(&world, &missing) == -ENOENT);
	missing.body_a_id = 1U;
	missing.body_b_id = 99U;
	assert(picosystem_physics_world_add_distance_joint(&world, &missing) == -ENOENT);

	joint = distance_joint_config(102U, 1U, 2U, 10);
	joint.anchor_b.x = FIXED(4);
	assert(picosystem_physics_world_add_distance_joint(&world, &joint) == -ERANGE);
	joint.anchor_b = (struct picosystem_physics_vector){.x = FIXED(1), .y = FIXED(-2)};
	assert(picosystem_physics_world_add_distance_joint(&world, &joint) == 0);
	assert(picosystem_physics_world_distance_joint_endpoints(&world, 1U, &anchor_a,
								 &anchor_b) == 0);
	assert(anchor_a.x == FIXED(10));
	assert(anchor_a.y == FIXED(20));
	assert(anchor_b.x == FIXED(31));
	assert(anchor_b.y == FIXED(38));

	for (uint16_t index = world.distance_joint_count;
	     index < PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS; ++index) {
		joint = distance_joint_config((uint16_t)(101U + index), 2U,
					      PICOSYSTEM_PHYSICS_WORLD_BODY_ID, 1);
		joint.anchor_b.x = FIXED(index);
		assert(picosystem_physics_world_add_distance_joint(&world, &joint) == 0);
	}
	assert(world.distance_joint_count == PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS);
	joint = distance_joint_config(200U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID, 1);
	assert(picosystem_physics_world_add_distance_joint(&world, &joint) == -ENOSPC);

	struct picosystem_physics_world corrupt = world;
	corrupt.body_count = PICOSYSTEM_PHYSICS_MAX_BODIES + 1U;
	assert(picosystem_physics_world_distance_joint_endpoints(&corrupt, 0U, &anchor_a,
								 &anchor_b) == -ERANGE);
	corrupt = world;
	corrupt.distance_joint_count = PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS + 1U;
	assert(picosystem_physics_world_distance_joint_endpoints(&corrupt, 0U, &anchor_a,
								 &anchor_b) == -ERANGE);
	corrupt = world;
	corrupt.distance_joints[0].body_a_index = UINT8_MAX;
	assert(picosystem_physics_world_distance_joint_endpoints(&corrupt, 0U, &anchor_a,
								 &anchor_b) == -ERANGE);
}

static void test_distance_joint_dynamics(void)
{
	struct picosystem_physics_world pendulum;
	init_world(&pendulum, FIXED(4));
	struct picosystem_physics_circle_config bob = circle_config(1U, 30, 0, 2);
	bob.velocity_per_tick.y = RATIO(1, 2);
	assert(picosystem_physics_world_add_circle(&pendulum, &bob) == 0);
	const struct picosystem_physics_distance_joint_config tether =
		distance_joint_config(101U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID, 30);
	assert(picosystem_physics_world_add_distance_joint(&pendulum, &tether) == 0);
	const struct picosystem_physics_vector gravity = {.y = RATIO(1, 128)};
	for (uint32_t step = 0U; step < 1000U; ++step) {
		assert(picosystem_physics_world_step(&pendulum, &gravity) == 0);
		struct picosystem_physics_vector endpoint_a;
		struct picosystem_physics_vector endpoint_b;
		assert(picosystem_physics_world_distance_joint_endpoints(&pendulum, 0U, &endpoint_a,
									 &endpoint_b) == 0);
		assert_distance_between(&endpoint_a, &endpoint_b, FIXED(29), FIXED(31));
		assert(pendulum.last_work.distance_joint_count == 1U);
		assert(pendulum.last_work.joint_position_correction_visit_count == 1U);
		assert(pendulum.last_work.joint_solver_visit_count ==
		       pendulum.last_work.solver_iteration_count);
		assert(pendulum.last_work.joint_solver_changed_count <=
		       pendulum.last_work.joint_solver_visit_count);
	}

	struct picosystem_physics_world pair;
	init_world(&pair, FIXED(4));
	struct picosystem_physics_circle_config left = circle_config(1U, -5, 0, 1);
	struct picosystem_physics_circle_config right = circle_config(2U, 5, 0, 1);
	left.velocity_per_tick.x = -RATIO(1, 2);
	right.velocity_per_tick.x = RATIO(1, 2);
	assert(picosystem_physics_world_add_circle(&pair, &left) == 0);
	assert(picosystem_physics_world_add_circle(&pair, &right) == 0);
	const struct picosystem_physics_distance_joint_config link =
		distance_joint_config(101U, 1U, 2U, 10);
	assert(picosystem_physics_world_add_distance_joint(&pair, &link) == 0);
	for (uint32_t step = 0U; step < 32U; ++step) {
		assert(picosystem_physics_world_step(&pair, &no_acceleration) == 0);
	}
	struct picosystem_physics_vector endpoint_a;
	struct picosystem_physics_vector endpoint_b;
	assert(picosystem_physics_world_distance_joint_endpoints(&pair, 0U, &endpoint_a,
								 &endpoint_b) == 0);
	assert_distance_between(&endpoint_a, &endpoint_b, FIXED(9), FIXED(11));
	assert_fixed_close(pair.bodies[0].velocity_per_tick.x, pair.bodies[1].velocity_per_tick.x,
			   RATIO(1, 64));

	struct picosystem_physics_world off_center;
	init_world(&off_center, FIXED(4));
	struct picosystem_physics_box_config swinging_box = box_config(1U, 20, 0, 2, 4);
	swinging_box.velocity_per_tick.y = PICOSYSTEM_PHYSICS_FIXED_ONE;
	assert(picosystem_physics_world_add_box(&off_center, &swinging_box) == 0);
	struct picosystem_physics_distance_joint_config off_center_tether =
		distance_joint_config(102U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID, 20);
	off_center_tether.local_anchor_a.y = FIXED(4);
	assert(picosystem_physics_world_add_distance_joint(&off_center, &off_center_tether) == 0);
	assert(picosystem_physics_world_step(&off_center, &no_acceleration) == 0);
	assert(off_center.bodies[0].angular_velocity_per_tick != 0);

	struct picosystem_physics_world coincident;
	init_world(&coincident, FIXED(2));
	const struct picosystem_physics_circle_config center = circle_config(1U, 0, 0, 1);
	assert(picosystem_physics_world_add_circle(&coincident, &center) == 0);
	const struct picosystem_physics_distance_joint_config fallback =
		distance_joint_config(102U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID, 1);
	assert(picosystem_physics_world_add_distance_joint(&coincident, &fallback) == 0);
	assert(picosystem_physics_world_step(&coincident, &no_acceleration) == 0);
	assert(coincident.bodies[0].center.x < 0);
}

static void test_revolute_joint_boundaries_and_anchors(void)
{
	struct picosystem_physics_world world;
	init_world(&world, FIXED(4));
	struct picosystem_physics_box_config box = box_config(1U, 10, 20, 2, 1);
	box.angle_turns = PICOSYSTEM_PHYSICS_ANGLE_QUARTER_TURN;
	const struct picosystem_physics_circle_config circle = circle_config(2U, 30, 40, 3);
	assert(picosystem_physics_world_add_box(&world, &box) == 0);
	assert(picosystem_physics_world_add_circle(&world, &circle) == 0);

	assert(picosystem_physics_world_add_revolute_joint(NULL, NULL) == -EINVAL);
	assert(picosystem_physics_world_add_revolute_joint(&world, NULL) == -EINVAL);
	struct picosystem_physics_revolute_joint_config joint =
		revolute_joint_config(201U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID);
	joint.local_anchor_a.x = FIXED(2);
	joint.anchor_b = (struct picosystem_physics_vector){.x = FIXED(30), .y = FIXED(40)};
	assert(picosystem_physics_world_add_revolute_joint(&world, &joint) == 0);
	assert(world.revolute_joint_count == 1U);
	assert(world.revolute_joints[0].body_a_index == 0U);
	assert(world.revolute_joints[0].body_b_index == UINT8_MAX);
	assert(world.revolute_joints[0].reference_angle_turns ==
	       PICOSYSTEM_PHYSICS_ANGLE_QUARTER_TURN);

	struct picosystem_physics_vector anchor_a;
	struct picosystem_physics_vector anchor_b;
	assert(picosystem_physics_world_revolute_joint_anchors(&world, 0U, &anchor_a, &anchor_b) ==
	       0);
	assert(anchor_a.x == FIXED(10));
	assert(anchor_a.y == FIXED(22));
	assert(anchor_b.x == FIXED(30));
	assert(anchor_b.y == FIXED(40));
	assert(picosystem_physics_world_revolute_joint_anchors(NULL, 0U, &anchor_a, &anchor_b) ==
	       -EINVAL);
	assert(picosystem_physics_world_revolute_joint_anchors(&world, 0U, NULL, &anchor_b) ==
	       -EINVAL);
	assert(picosystem_physics_world_revolute_joint_anchors(&world, 1U, &anchor_a, &anchor_b) ==
	       -ENOENT);
	picosystem_physics_fixed_t relative_angle = INT32_MAX;
	assert(picosystem_physics_world_revolute_joint_angle(&world, 0U, &relative_angle) == 0);
	assert(relative_angle == 0);
	assert(picosystem_physics_world_revolute_joint_angle(NULL, 0U, &relative_angle) == -EINVAL);
	assert(picosystem_physics_world_revolute_joint_angle(&world, 0U, NULL) == -EINVAL);
	assert(picosystem_physics_world_revolute_joint_angle(&world, 1U, &relative_angle) ==
	       -ENOENT);

	const uint32_t one_joint_hash = picosystem_physics_world_hash(&world);
	assert(picosystem_physics_world_add_revolute_joint(&world, &joint) == -EEXIST);
	assert(picosystem_physics_world_hash(&world) == one_joint_hash);

	struct picosystem_physics_revolute_joint_config invalid = joint;
	invalid.id = 0U;
	assert(picosystem_physics_world_add_revolute_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 202U;
	invalid.body_a_id = PICOSYSTEM_PHYSICS_WORLD_BODY_ID;
	assert(picosystem_physics_world_add_revolute_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 202U;
	invalid.body_b_id = invalid.body_a_id;
	assert(picosystem_physics_world_add_revolute_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 202U;
	invalid.collide_connected = 2U;
	assert(picosystem_physics_world_add_revolute_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 202U;
	invalid.motor_enabled = 2U;
	assert(picosystem_physics_world_add_revolute_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 202U;
	invalid.limit_enabled = 2U;
	assert(picosystem_physics_world_add_revolute_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 202U;
	invalid.motor_speed_per_tick = RATIO(1, 64);
	assert(picosystem_physics_world_add_revolute_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 202U;
	invalid.motor_enabled = 1U;
	invalid.motor_speed_per_tick = RATIO(1, 64);
	assert(picosystem_physics_world_add_revolute_joint(&world, &invalid) == -ERANGE);
	invalid.maximum_motor_impulse_per_tick = FIXED(9);
	assert(picosystem_physics_world_add_revolute_joint(&world, &invalid) == -ERANGE);
	invalid.maximum_motor_impulse_per_tick = RATIO(1, 4);
	invalid.motor_speed_per_tick = PICOSYSTEM_PHYSICS_FIXED_ONE;
	assert(picosystem_physics_world_add_revolute_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 202U;
	invalid.lower_angle_radians = -RATIO(1, 4);
	assert(picosystem_physics_world_add_revolute_joint(&world, &invalid) == -ERANGE);
	invalid.limit_enabled = 1U;
	invalid.upper_angle_radians = -RATIO(1, 2);
	assert(picosystem_physics_world_add_revolute_joint(&world, &invalid) == -ERANGE);
	invalid.lower_angle_radians = -FIXED(4);
	invalid.upper_angle_radians = RATIO(1, 2);
	assert(picosystem_physics_world_add_revolute_joint(&world, &invalid) == -ERANGE);
	invalid.lower_angle_radians = 0;
	invalid.upper_angle_radians = 1;
	assert(picosystem_physics_world_add_revolute_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 202U;
	invalid.local_anchor_a.x = INT32_MAX;
	assert(picosystem_physics_world_add_revolute_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 202U;
	invalid.local_anchor_a.x = FIXED(3);
	assert(picosystem_physics_world_add_revolute_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 202U;
	invalid.anchor_b.x = INT32_MAX;
	assert(picosystem_physics_world_add_revolute_joint(&world, &invalid) == -ERANGE);
	assert(picosystem_physics_world_hash(&world) == one_joint_hash);

	struct picosystem_physics_revolute_joint_config missing =
		revolute_joint_config(202U, 99U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID);
	assert(picosystem_physics_world_add_revolute_joint(&world, &missing) == -ENOENT);
	missing.body_a_id = 1U;
	missing.body_b_id = 99U;
	assert(picosystem_physics_world_add_revolute_joint(&world, &missing) == -ENOENT);

	joint = revolute_joint_config(202U, 1U, 2U);
	joint.anchor_b.x = FIXED(4);
	assert(picosystem_physics_world_add_revolute_joint(&world, &joint) == -ERANGE);
	joint.anchor_b = (struct picosystem_physics_vector){.x = FIXED(1), .y = FIXED(-2)};
	assert(picosystem_physics_world_add_revolute_joint(&world, &joint) == 0);
	assert(picosystem_physics_world_revolute_joint_anchors(&world, 1U, &anchor_a, &anchor_b) ==
	       0);
	assert(anchor_a.x == FIXED(10));
	assert(anchor_a.y == FIXED(20));
	assert(anchor_b.x == FIXED(31));
	assert(anchor_b.y == FIXED(38));

	for (uint16_t index = world.revolute_joint_count;
	     index < PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS; ++index) {
		joint = revolute_joint_config((uint16_t)(201U + index), 2U,
					      PICOSYSTEM_PHYSICS_WORLD_BODY_ID);
		joint.anchor_b.x = FIXED(index);
		assert(picosystem_physics_world_add_revolute_joint(&world, &joint) == 0);
	}
	assert(world.revolute_joint_count == PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS);
	joint = revolute_joint_config(300U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID);
	assert(picosystem_physics_world_add_revolute_joint(&world, &joint) == -ENOSPC);

	struct picosystem_physics_world corrupt = world;
	corrupt.body_count = PICOSYSTEM_PHYSICS_MAX_BODIES + 1U;
	assert(picosystem_physics_world_revolute_joint_anchors(&corrupt, 0U, &anchor_a,
							       &anchor_b) == -ERANGE);
	corrupt = world;
	corrupt.revolute_joint_count = PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS + 1U;
	assert(picosystem_physics_world_revolute_joint_anchors(&corrupt, 0U, &anchor_a,
							       &anchor_b) == -ERANGE);
	corrupt = world;
	corrupt.revolute_joints[0].body_a_index = UINT8_MAX;
	assert(picosystem_physics_world_revolute_joint_anchors(&corrupt, 0U, &anchor_a,
							       &anchor_b) == -ERANGE);
	assert(picosystem_physics_world_revolute_joint_angle(&corrupt, 0U, &relative_angle) ==
	       -ERANGE);
}

static void test_revolute_joint_dynamics_and_multilink_chain(void)
{
	struct picosystem_physics_world pinned;
	init_world(&pinned, FIXED(4));
	struct picosystem_physics_box_config arm = box_config(1U, 2, 0, 2, 1);
	arm.velocity_per_tick.y = RATIO(1, 2);
	assert(picosystem_physics_world_add_box(&pinned, &arm) == 0);
	struct picosystem_physics_revolute_joint_config pin =
		revolute_joint_config(201U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID);
	pin.local_anchor_a.x = -FIXED(2);
	assert(picosystem_physics_world_add_revolute_joint(&pinned, &pin) == 0);
	for (uint32_t step = 0U; step < 1000U; ++step) {
		assert(picosystem_physics_world_step(&pinned, &no_acceleration) == 0);
		struct picosystem_physics_vector anchor_a;
		struct picosystem_physics_vector anchor_b;
		assert(picosystem_physics_world_revolute_joint_anchors(&pinned, 0U, &anchor_a,
								       &anchor_b) == 0);
		assert_distance_between(&anchor_a, &anchor_b, 0, RATIO(1, 2));
		assert(pinned.last_work.revolute_joint_count == 1U);
		assert(pinned.last_work.joint_position_correction_visit_count >= 1U);
		assert(pinned.last_work.joint_position_correction_visit_count <=
		       PICOSYSTEM_PHYSICS_REVOLUTE_POSITION_ITERATIONS);
		assert(pinned.last_work.joint_solver_visit_count ==
		       pinned.last_work.solver_iteration_count);
	}
	assert(pinned.bodies[0].angle_turns != 0U);

	struct picosystem_physics_world chain;
	init_world(&chain, FIXED(4));
	for (uint16_t index = 0U; index < 4U; ++index) {
		const struct picosystem_physics_box_config link =
			box_config((uint16_t)(index + 1U), 2 + ((int32_t)index * 4), 0, 2, 1);
		assert(picosystem_physics_world_add_box(&chain, &link) == 0);
	}
	pin = revolute_joint_config(201U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID);
	pin.local_anchor_a.x = -FIXED(2);
	assert(picosystem_physics_world_add_revolute_joint(&chain, &pin) == 0);
	for (uint16_t index = 1U; index < 4U; ++index) {
		struct picosystem_physics_revolute_joint_config link = revolute_joint_config(
			(uint16_t)(201U + index), index, (uint16_t)(index + 1U));
		link.local_anchor_a.x = FIXED(2);
		link.anchor_b.x = -FIXED(2);
		assert(picosystem_physics_world_add_revolute_joint(&chain, &link) == 0);
	}
	const struct picosystem_physics_vector gravity = {.y = RATIO(1, 512)};
	for (uint32_t step = 0U; step < 2000U; ++step) {
		assert(picosystem_physics_world_wake_body(&chain, 0U) == 0);
		assert(picosystem_physics_world_step(&chain, &gravity) == 0);
		for (uint16_t index = 0U; index < chain.revolute_joint_count; ++index) {
			struct picosystem_physics_vector anchor_a;
			struct picosystem_physics_vector anchor_b;
			assert(picosystem_physics_world_revolute_joint_anchors(
				       &chain, index, &anchor_a, &anchor_b) == 0);
			assert_distance_between(&anchor_a, &anchor_b, 0, FIXED(1));
		}
		assert(chain.last_work.revolute_joint_count == 4U);
		assert(chain.last_work.joint_position_correction_visit_count >= 4U);
		assert(chain.last_work.joint_position_correction_visit_count <=
		       4U * PICOSYSTEM_PHYSICS_REVOLUTE_POSITION_ITERATIONS);
		assert((chain.last_work.joint_position_correction_visit_count % 4U) == 0U);
		assert(chain.last_work.joint_solver_visit_count ==
		       4U * chain.last_work.solver_iteration_count);
	}
}

static picosystem_physics_fixed_t revolute_joint_angle(const struct picosystem_physics_world *world,
						       size_t index)
{
	picosystem_physics_fixed_t angle = 0;
	assert(picosystem_physics_world_revolute_joint_angle(world, index, &angle) == 0);
	return angle;
}

static void test_revolute_joint_motor_and_limits(void)
{
	struct picosystem_physics_world motor;
	init_world(&motor, FIXED(2));
	const struct picosystem_physics_circle_config rotor = circle_config(1U, 0, 0, 2);
	assert(picosystem_physics_world_add_circle(&motor, &rotor) == 0);
	struct picosystem_physics_revolute_joint_config drive =
		revolute_joint_config(201U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID);
	drive.motor_speed_per_tick = RATIO(1, 32);
	drive.maximum_motor_impulse_per_tick = RATIO(1, 4);
	drive.motor_enabled = 1U;
	assert(picosystem_physics_world_add_revolute_joint(&motor, &drive) == 0);
	for (uint32_t step = 0U; step < 32U; ++step) {
		assert(picosystem_physics_world_step(&motor, &no_acceleration) == 0);
		assert(motor.last_work.revolute_motor_count == 1U);
		assert(motor.last_work.revolute_limit_count == 0U);
		assert(motor.last_work.joint_motor_solver_visit_count >= 1U);
		assert(motor.last_work.joint_motor_solver_visit_count <=
		       motor.last_work.solver_iteration_count);
		assert(motor.last_work.joint_limit_solver_visit_count == 0U);
	}
	assert_fixed_close(motor.bodies[0].angular_velocity_per_tick, drive.motor_speed_per_tick,
			   1);
	assert_fixed_close(revolute_joint_angle(&motor, 0U), RATIO(31, 32), RATIO(1, 128));

	struct picosystem_physics_world motor_pair;
	init_world(&motor_pair, FIXED(2));
	const struct picosystem_physics_circle_config rotor_pair_a = circle_config(1U, 0, 0, 2);
	const struct picosystem_physics_circle_config rotor_pair_b = circle_config(2U, 0, 0, 2);
	assert(picosystem_physics_world_add_circle(&motor_pair, &rotor_pair_a) == 0);
	assert(picosystem_physics_world_add_circle(&motor_pair, &rotor_pair_b) == 0);
	drive = revolute_joint_config(206U, 1U, 2U);
	drive.motor_speed_per_tick = RATIO(1, 32);
	drive.maximum_motor_impulse_per_tick = RATIO(1, 4);
	drive.motor_enabled = 1U;
	assert(picosystem_physics_world_add_revolute_joint(&motor_pair, &drive) == 0);
	assert(picosystem_physics_world_step(&motor_pair, &no_acceleration) == 0);
	assert(motor_pair.bodies[0].angular_velocity_per_tick > 0);
	assert(motor_pair.bodies[1].angular_velocity_per_tick < 0);
	assert_fixed_close(motor_pair.bodies[0].angular_velocity_per_tick -
				   motor_pair.bodies[1].angular_velocity_per_tick,
			   drive.motor_speed_per_tick, 1);
	assert_fixed_close(motor_pair.bodies[0].angular_velocity_per_tick +
				   motor_pair.bodies[1].angular_velocity_per_tick,
			   0, 1);

	struct picosystem_physics_world torque_limited;
	init_world(&torque_limited, FIXED(2));
	assert(picosystem_physics_world_add_circle(&torque_limited, &rotor) == 0);
	drive = revolute_joint_config(202U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID);
	drive.motor_speed_per_tick = RATIO(1, 32);
	drive.maximum_motor_impulse_per_tick = RATIO(1, 256);
	drive.motor_enabled = 1U;
	assert(picosystem_physics_world_add_revolute_joint(&torque_limited, &drive) == 0);
	assert(picosystem_physics_world_step(&torque_limited, &no_acceleration) == 0);
	assert(torque_limited.revolute_joints[0].accumulated_motor_impulse ==
	       drive.maximum_motor_impulse_per_tick);
	assert(torque_limited.bodies[0].angular_velocity_per_tick < drive.motor_speed_per_tick);

	struct picosystem_physics_world limited;
	init_world(&limited, FIXED(2));
	const struct picosystem_physics_box_config arm = box_config(1U, 0, 0, 2, 1);
	assert(picosystem_physics_world_add_box(&limited, &arm) == 0);
	drive = revolute_joint_config(203U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID);
	drive.motor_speed_per_tick = RATIO(1, 16);
	drive.maximum_motor_impulse_per_tick = RATIO(1, 2);
	drive.lower_angle_radians = -RATIO(1, 4);
	drive.upper_angle_radians = RATIO(1, 4);
	drive.motor_enabled = 1U;
	drive.limit_enabled = 1U;
	assert(picosystem_physics_world_add_revolute_joint(&limited, &drive) == 0);
	struct picosystem_physics_world reference = limited;
	bool saw_active_limit = false;
	for (uint32_t step = 0U; step < 1000U; ++step) {
		assert(picosystem_physics_world_step(&limited, &no_acceleration) == 0);
		assert(picosystem_physics_world_step_reference(&reference, &no_acceleration) == 0);
		assert_step_matches_reference(&limited, &reference);
		const picosystem_physics_fixed_t angle = revolute_joint_angle(&limited, 0U);
		assert(angle >= (drive.lower_angle_radians - RATIO(1, 32)));
		assert(angle <= (drive.upper_angle_radians + RATIO(1, 32)));
		assert(limited.last_work.revolute_motor_count == 1U);
		assert(limited.last_work.revolute_limit_count == 1U);
		if (limited.last_work.joint_limit_solver_visit_count != 0U) {
			saw_active_limit = true;
		}
	}
	assert(saw_active_limit);
	assert_fixed_close(revolute_joint_angle(&limited, 0U), drive.upper_angle_radians,
			   RATIO(1, 32));

	struct picosystem_physics_world lower_limited;
	init_world(&lower_limited, FIXED(2));
	assert(picosystem_physics_world_add_box(&lower_limited, &arm) == 0);
	drive.id = 207U;
	drive.motor_speed_per_tick = -RATIO(1, 16);
	assert(picosystem_physics_world_add_revolute_joint(&lower_limited, &drive) == 0);
	for (uint32_t step = 0U; step < 256U; ++step) {
		assert(picosystem_physics_world_step(&lower_limited, &no_acceleration) == 0);
	}
	assert_fixed_close(revolute_joint_angle(&lower_limited, 0U), drive.lower_angle_radians,
			   RATIO(1, 32));

	struct picosystem_physics_world locked;
	init_world(&locked, FIXED(2));
	struct picosystem_physics_box_config moving_arm = arm;
	moving_arm.angular_velocity_per_tick = RATIO(1, 8);
	assert(picosystem_physics_world_add_box(&locked, &moving_arm) == 0);
	struct picosystem_physics_revolute_joint_config lock =
		revolute_joint_config(204U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID);
	lock.limit_enabled = 1U;
	assert(picosystem_physics_world_add_revolute_joint(&locked, &lock) == 0);
	for (uint32_t step = 0U; step < 64U; ++step) {
		assert(picosystem_physics_world_step(&locked, &no_acceleration) == 0);
	}
	assert_fixed_close(revolute_joint_angle(&locked, 0U), 0, RATIO(1, 32));
	assert_fixed_close(locked.bodies[0].angular_velocity_per_tick, 0, 1);

	struct picosystem_physics_world wrapped;
	init_world(&wrapped, FIXED(2));
	struct picosystem_physics_box_config wrapped_arm = arm;
	wrapped_arm.angle_turns = UINT32_MAX - 1000U;
	wrapped_arm.angular_velocity_per_tick = RATIO(1, 64);
	assert(picosystem_physics_world_add_box(&wrapped, &wrapped_arm) == 0);
	const struct picosystem_physics_revolute_joint_config wrapped_pin =
		revolute_joint_config(205U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID);
	assert(picosystem_physics_world_add_revolute_joint(&wrapped, &wrapped_pin) == 0);
	assert(picosystem_physics_world_step(&wrapped, &no_acceleration) == 0);
	assert_fixed_close(revolute_joint_angle(&wrapped, 0U), RATIO(1, 64), 2);
}

static void test_revolute_joint_connected_collision_policy(void)
{
	struct picosystem_physics_world filtered;
	init_world(&filtered, FIXED(2));
	const struct picosystem_physics_circle_config first = circle_config(1U, 0, 0, 2);
	const struct picosystem_physics_circle_config second = circle_config(2U, 0, 0, 2);
	assert(picosystem_physics_world_add_circle(&filtered, &first) == 0);
	assert(picosystem_physics_world_add_circle(&filtered, &second) == 0);
	const struct picosystem_physics_revolute_joint_config filtered_joint =
		revolute_joint_config(201U, 1U, 2U);
	assert(picosystem_physics_world_add_revolute_joint(&filtered, &filtered_joint) == 0);
	assert(picosystem_physics_world_step(&filtered, &no_acceleration) == 0);
	assert(filtered.contact_count == 0U);
	assert(filtered.last_work.joint_collision_filter_count == 1U);
	assert(filtered.last_work.body_body_narrow_phase_test_count == 0U);

	struct picosystem_physics_world colliding;
	init_world(&colliding, FIXED(2));
	assert(picosystem_physics_world_add_circle(&colliding, &first) == 0);
	assert(picosystem_physics_world_add_circle(&colliding, &second) == 0);
	struct picosystem_physics_revolute_joint_config colliding_joint = filtered_joint;
	colliding_joint.collide_connected = 1U;
	assert(picosystem_physics_world_add_revolute_joint(&colliding, &colliding_joint) == 0);
	assert(picosystem_physics_world_step(&colliding, &no_acceleration) == 0);
	assert(colliding.contact_count == 1U);
	assert(colliding.last_work.joint_collision_filter_count == 0U);
	assert(colliding.last_work.body_body_narrow_phase_test_count == 1U);
}

static void test_prismatic_joint_boundaries_and_queries(void)
{
	struct picosystem_physics_world world;
	init_world(&world, FIXED(4));
	struct picosystem_physics_box_config box = box_config(1U, 10, 20, 2, 1);
	box.angle_turns = PICOSYSTEM_PHYSICS_ANGLE_QUARTER_TURN;
	const struct picosystem_physics_circle_config circle = circle_config(2U, 30, 40, 3);
	assert(picosystem_physics_world_add_box(&world, &box) == 0);
	assert(picosystem_physics_world_add_circle(&world, &circle) == 0);

	assert(picosystem_physics_world_add_prismatic_joint(NULL, NULL) == -EINVAL);
	assert(picosystem_physics_world_add_prismatic_joint(&world, NULL) == -EINVAL);
	struct picosystem_physics_prismatic_joint_config joint =
		prismatic_joint_config(401U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID);
	joint.local_anchor_a.x = FIXED(2);
	joint.anchor_b = (struct picosystem_physics_vector){.x = FIXED(30), .y = FIXED(40)};
	joint.axis_b.x = RATIO(1, 2);
	assert(picosystem_physics_world_add_prismatic_joint(&world, &joint) == 0);
	assert(world.prismatic_joint_count == 1U);
	assert(world.prismatic_joints[0].body_a_index == 0U);
	assert(world.prismatic_joints[0].body_b_index == UINT8_MAX);
	assert(world.prismatic_joints[0].axis_b.x == PICOSYSTEM_PHYSICS_FIXED_ONE);
	assert(world.prismatic_joints[0].axis_b.y == 0);
	assert(world.prismatic_joints[0].reference_translation == -FIXED(20));
	assert(world.prismatic_joints[0].reference_angle_turns ==
	       PICOSYSTEM_PHYSICS_ANGLE_QUARTER_TURN);

	struct picosystem_physics_vector anchor_a;
	struct picosystem_physics_vector anchor_b;
	struct picosystem_physics_vector axis;
	assert(picosystem_physics_world_prismatic_joint_geometry(&world, 0U, &anchor_a, &anchor_b,
								 &axis) == 0);
	assert(anchor_a.x == FIXED(10));
	assert(anchor_a.y == FIXED(22));
	assert(anchor_b.x == FIXED(30));
	assert(anchor_b.y == FIXED(40));
	assert(axis.x == PICOSYSTEM_PHYSICS_FIXED_ONE);
	assert(axis.y == 0);
	picosystem_physics_fixed_t translation = INT32_MAX;
	assert(picosystem_physics_world_prismatic_joint_translation(&world, 0U, &translation) == 0);
	assert(translation == 0);
	picosystem_physics_fixed_t relative_angle = INT32_MAX;
	assert(picosystem_physics_world_prismatic_joint_angle(&world, 0U, &relative_angle) == 0);
	assert(relative_angle == 0);
	assert(picosystem_physics_world_prismatic_joint_geometry(NULL, 0U, &anchor_a, &anchor_b,
								 &axis) == -EINVAL);
	assert(picosystem_physics_world_prismatic_joint_geometry(&world, 0U, NULL, &anchor_b,
								 &axis) == -EINVAL);
	assert(picosystem_physics_world_prismatic_joint_geometry(&world, 1U, &anchor_a, &anchor_b,
								 &axis) == -ENOENT);
	assert(picosystem_physics_world_prismatic_joint_translation(NULL, 0U, &translation) ==
	       -EINVAL);
	assert(picosystem_physics_world_prismatic_joint_translation(&world, 0U, NULL) == -EINVAL);
	assert(picosystem_physics_world_prismatic_joint_translation(&world, 1U, &translation) ==
	       -ENOENT);
	assert(picosystem_physics_world_prismatic_joint_angle(NULL, 0U, &relative_angle) ==
	       -EINVAL);
	assert(picosystem_physics_world_prismatic_joint_angle(&world, 0U, NULL) == -EINVAL);
	assert(picosystem_physics_world_prismatic_joint_angle(&world, 1U, &relative_angle) ==
	       -ENOENT);
	assert(picosystem_physics_world_set_prismatic_motor_speed(NULL, 0U, 0) == -EINVAL);
	assert(picosystem_physics_world_set_prismatic_motor_speed(&world, 1U, 0) == -ENOENT);
	assert(picosystem_physics_world_set_prismatic_motor_speed(&world, 0U, FIXED(9)) == -ERANGE);
	assert(picosystem_physics_world_set_prismatic_motor_speed(&world, 0U, 0) == -ENOTSUP);

	const uint32_t one_joint_hash = picosystem_physics_world_hash(&world);
	assert(picosystem_physics_world_add_prismatic_joint(&world, &joint) == -EEXIST);
	assert(picosystem_physics_world_hash(&world) == one_joint_hash);

	struct picosystem_physics_prismatic_joint_config invalid = joint;
	invalid.id = 0U;
	assert(picosystem_physics_world_add_prismatic_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 402U;
	invalid.body_a_id = PICOSYSTEM_PHYSICS_WORLD_BODY_ID;
	assert(picosystem_physics_world_add_prismatic_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 402U;
	invalid.body_b_id = invalid.body_a_id;
	assert(picosystem_physics_world_add_prismatic_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 402U;
	invalid.collide_connected = 2U;
	assert(picosystem_physics_world_add_prismatic_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 402U;
	invalid.motor_enabled = 2U;
	assert(picosystem_physics_world_add_prismatic_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 402U;
	invalid.limit_enabled = 2U;
	assert(picosystem_physics_world_add_prismatic_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 402U;
	invalid.axis_b = (struct picosystem_physics_vector){0};
	assert(picosystem_physics_world_add_prismatic_joint(&world, &invalid) == -ERANGE);
	invalid.axis_b.x = 1;
	assert(picosystem_physics_world_add_prismatic_joint(&world, &invalid) == -ERANGE);
	invalid.axis_b.x = PICOSYSTEM_PHYSICS_FIXED_ONE + 1;
	assert(picosystem_physics_world_add_prismatic_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 402U;
	invalid.motor_speed_per_tick = RATIO(1, 16);
	assert(picosystem_physics_world_add_prismatic_joint(&world, &invalid) == -ERANGE);
	invalid.motor_enabled = 1U;
	assert(picosystem_physics_world_add_prismatic_joint(&world, &invalid) == -ERANGE);
	invalid.maximum_motor_impulse_per_tick = FIXED(9);
	assert(picosystem_physics_world_add_prismatic_joint(&world, &invalid) == -ERANGE);
	invalid.maximum_motor_impulse_per_tick = RATIO(1, 4);
	invalid.motor_speed_per_tick = FIXED(9);
	assert(picosystem_physics_world_add_prismatic_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 402U;
	invalid.lower_translation = -FIXED(1);
	assert(picosystem_physics_world_add_prismatic_joint(&world, &invalid) == -ERANGE);
	invalid.limit_enabled = 1U;
	invalid.upper_translation = -FIXED(2);
	assert(picosystem_physics_world_add_prismatic_joint(&world, &invalid) == -ERANGE);
	invalid.lower_translation = 0;
	invalid.upper_translation = 1;
	assert(picosystem_physics_world_add_prismatic_joint(&world, &invalid) == -ERANGE);
	invalid.lower_translation = -FIXED(257);
	invalid.upper_translation = FIXED(1);
	assert(picosystem_physics_world_add_prismatic_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 402U;
	invalid.local_anchor_a.x = FIXED(3);
	assert(picosystem_physics_world_add_prismatic_joint(&world, &invalid) == -ERANGE);
	invalid = joint;
	invalid.id = 402U;
	invalid.anchor_b.x = INT32_MAX;
	assert(picosystem_physics_world_add_prismatic_joint(&world, &invalid) == -ERANGE);
	assert(picosystem_physics_world_hash(&world) == one_joint_hash);

	struct picosystem_physics_prismatic_joint_config missing =
		prismatic_joint_config(402U, 99U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID);
	assert(picosystem_physics_world_add_prismatic_joint(&world, &missing) == -ENOENT);
	missing.body_a_id = 1U;
	missing.body_b_id = 99U;
	assert(picosystem_physics_world_add_prismatic_joint(&world, &missing) == -ENOENT);

	joint = prismatic_joint_config(402U, 1U, 2U);
	joint.anchor_b = (struct picosystem_physics_vector){.x = FIXED(1), .y = FIXED(-2)};
	joint.axis_b = (struct picosystem_physics_vector){.y = PICOSYSTEM_PHYSICS_FIXED_ONE};
	assert(picosystem_physics_world_add_prismatic_joint(&world, &joint) == 0);
	assert(picosystem_physics_world_prismatic_joint_geometry(&world, 1U, &anchor_a, &anchor_b,
								 &axis) == 0);
	assert(anchor_a.x == FIXED(10));
	assert(anchor_a.y == FIXED(20));
	assert(anchor_b.x == FIXED(31));
	assert(anchor_b.y == FIXED(38));
	assert(axis.x == 0);
	assert(axis.y == PICOSYSTEM_PHYSICS_FIXED_ONE);

	for (uint16_t index = world.prismatic_joint_count;
	     index < PICOSYSTEM_PHYSICS_MAX_PRISMATIC_JOINTS; ++index) {
		joint = prismatic_joint_config((uint16_t)(401U + index), 2U,
					       PICOSYSTEM_PHYSICS_WORLD_BODY_ID);
		joint.anchor_b.x = FIXED(index);
		assert(picosystem_physics_world_add_prismatic_joint(&world, &joint) == 0);
	}
	assert(world.prismatic_joint_count == PICOSYSTEM_PHYSICS_MAX_PRISMATIC_JOINTS);
	joint = prismatic_joint_config(500U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID);
	assert(picosystem_physics_world_add_prismatic_joint(&world, &joint) == -ENOSPC);

	struct picosystem_physics_world corrupt = world;
	corrupt.body_count = PICOSYSTEM_PHYSICS_MAX_BODIES + 1U;
	assert(picosystem_physics_world_prismatic_joint_geometry(&corrupt, 0U, &anchor_a, &anchor_b,
								 &axis) == -ERANGE);
	corrupt = world;
	corrupt.prismatic_joint_count = PICOSYSTEM_PHYSICS_MAX_PRISMATIC_JOINTS + 1U;
	assert(picosystem_physics_world_prismatic_joint_translation(&corrupt, 0U, &translation) ==
	       -ERANGE);
	corrupt = world;
	corrupt.prismatic_joints[0].axis_b.x = 0;
	assert(picosystem_physics_world_prismatic_joint_geometry(&corrupt, 0U, &anchor_a, &anchor_b,
								 &axis) == -ERANGE);

	struct picosystem_physics_world rotated_carrier;
	init_world(&rotated_carrier, FIXED(4));
	const struct picosystem_physics_box_config slider = box_config(1U, 20, 10, 3, 3);
	struct picosystem_physics_box_config carrier = box_config(2U, 10, 10, 3, 3);
	carrier.angle_turns = PICOSYSTEM_PHYSICS_ANGLE_QUARTER_TURN;
	assert(picosystem_physics_world_add_box(&rotated_carrier, &slider) == 0);
	assert(picosystem_physics_world_add_box(&rotated_carrier, &carrier) == 0);
	joint = prismatic_joint_config(601U, 1U, 2U);
	joint.anchor_b.x = FIXED(2);
	assert(picosystem_physics_world_add_prismatic_joint(&rotated_carrier, &joint) == 0);
	assert(picosystem_physics_world_prismatic_joint_geometry(&rotated_carrier, 0U, &anchor_a,
								 &anchor_b, &axis) == 0);
	assert(anchor_b.x == FIXED(10));
	assert(anchor_b.y == FIXED(12));
	assert(axis.x == 0);
	assert(axis.y == PICOSYSTEM_PHYSICS_FIXED_ONE);
	assert(picosystem_physics_world_prismatic_joint_translation(&rotated_carrier, 0U,
								    &translation) == 0);
	assert(translation == 0);
}

static picosystem_physics_fixed_t
prismatic_joint_translation(const struct picosystem_physics_world *world, size_t index)
{
	picosystem_physics_fixed_t translation = 0;
	assert(picosystem_physics_world_prismatic_joint_translation(world, index, &translation) ==
	       0);
	return translation;
}

static void test_prismatic_joint_dynamics_motor_and_limits(void)
{
	struct picosystem_physics_world free_slider;
	init_world(&free_slider, FIXED(2));
	struct picosystem_physics_box_config carriage = box_config(1U, 0, 0, 2, 1);
	carriage.velocity_per_tick =
		(struct picosystem_physics_vector){.x = RATIO(1, 2), .y = RATIO(1, 4)};
	carriage.angular_velocity_per_tick = RATIO(1, 8);
	assert(picosystem_physics_world_add_box(&free_slider, &carriage) == 0);
	const struct picosystem_physics_prismatic_joint_config rail =
		prismatic_joint_config(401U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID);
	assert(picosystem_physics_world_add_prismatic_joint(&free_slider, &rail) == 0);
	for (uint32_t step = 0U; step < 64U; ++step) {
		assert(picosystem_physics_world_step(&free_slider, &no_acceleration) == 0);
		assert(free_slider.last_work.prismatic_joint_count == 1U);
		assert(free_slider.last_work.prismatic_motor_count == 0U);
		assert(free_slider.last_work.prismatic_limit_count == 0U);
		assert(free_slider.last_work.joint_position_correction_visit_count >= 1U);
		assert(free_slider.last_work.joint_position_correction_visit_count <=
		       PICOSYSTEM_PHYSICS_PRISMATIC_POSITION_ITERATIONS);
		assert(free_slider.last_work.joint_solver_visit_count ==
		       free_slider.last_work.solver_iteration_count);
	}
	assert_fixed_close(prismatic_joint_translation(&free_slider, 0U), FIXED(32), RATIO(1, 32));
	assert_fixed_close(free_slider.bodies[0].center.y, 0, RATIO(1, 32));
	assert_fixed_close(free_slider.bodies[0].velocity_per_tick.y, 0, 1);
	assert_fixed_close(free_slider.bodies[0].angular_velocity_per_tick, 0, 1);
	picosystem_physics_fixed_t relative_angle = INT32_MAX;
	assert(picosystem_physics_world_prismatic_joint_angle(&free_slider, 0U, &relative_angle) ==
	       0);
	assert_fixed_close(relative_angle, 0, RATIO(1, 32));

	struct picosystem_physics_world limited;
	init_world(&limited, FIXED(2));
	carriage = box_config(1U, 0, 0, 2, 1);
	assert(picosystem_physics_world_add_box(&limited, &carriage) == 0);
	struct picosystem_physics_prismatic_joint_config drive =
		prismatic_joint_config(402U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID);
	drive.motor_speed_per_tick = RATIO(1, 8);
	drive.maximum_motor_impulse_per_tick = RATIO(1, 2);
	drive.lower_translation = -FIXED(3);
	drive.upper_translation = FIXED(3);
	drive.motor_enabled = 1U;
	drive.limit_enabled = 1U;
	assert(picosystem_physics_world_add_prismatic_joint(&limited, &drive) == 0);
	struct picosystem_physics_world reference = limited;
	bool saw_upper_limit = false;
	for (uint32_t step = 0U; step < 200U; ++step) {
		assert(picosystem_physics_world_step(&limited, &no_acceleration) == 0);
		assert(picosystem_physics_world_step_reference(&reference, &no_acceleration) == 0);
		assert_step_matches_reference(&limited, &reference);
		const picosystem_physics_fixed_t translation =
			prismatic_joint_translation(&limited, 0U);
		assert(translation >= (drive.lower_translation - RATIO(1, 16)));
		assert(translation <= (drive.upper_translation + RATIO(1, 16)));
		assert(limited.last_work.prismatic_motor_count == 1U);
		assert(limited.last_work.prismatic_limit_count == 1U);
		if (limited.last_work.joint_limit_solver_visit_count != 0U) {
			saw_upper_limit = true;
		}
	}
	assert(saw_upper_limit);
	assert_fixed_close(prismatic_joint_translation(&limited, 0U), drive.upper_translation,
			   RATIO(1, 16));
	const uint32_t upper_hash = picosystem_physics_world_hash(&limited);
	assert(picosystem_physics_world_set_prismatic_motor_speed(&limited, 0U, -RATIO(1, 8)) == 0);
	assert(picosystem_physics_world_set_prismatic_motor_speed(&reference, 0U, -RATIO(1, 8)) ==
	       0);
	assert(picosystem_physics_world_hash(&limited) != upper_hash);
	for (uint32_t step = 0U; step < 200U; ++step) {
		assert(picosystem_physics_world_step(&limited, &no_acceleration) == 0);
		assert(picosystem_physics_world_step_reference(&reference, &no_acceleration) == 0);
		assert_step_matches_reference(&limited, &reference);
	}
	assert_fixed_close(prismatic_joint_translation(&limited, 0U), drive.lower_translation,
			   RATIO(1, 16));

	struct picosystem_physics_world impulse_limited;
	init_world(&impulse_limited, FIXED(2));
	assert(picosystem_physics_world_add_box(&impulse_limited, &carriage) == 0);
	drive = prismatic_joint_config(403U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID);
	drive.motor_speed_per_tick = RATIO(1, 2);
	drive.maximum_motor_impulse_per_tick = RATIO(1, 256);
	drive.motor_enabled = 1U;
	assert(picosystem_physics_world_add_prismatic_joint(&impulse_limited, &drive) == 0);
	assert(picosystem_physics_world_step(&impulse_limited, &no_acceleration) == 0);
	assert(impulse_limited.prismatic_joints[0].accumulated_motor_impulse ==
	       drive.maximum_motor_impulse_per_tick);
	assert(impulse_limited.bodies[0].velocity_per_tick.x < drive.motor_speed_per_tick);
	assert(impulse_limited.last_work.solver_iteration_count == 2U);
	assert(impulse_limited.last_work.joint_motor_solver_visit_count == 1U);

	struct picosystem_physics_world locked;
	init_world(&locked, FIXED(2));
	carriage.velocity_per_tick.x = RATIO(1, 2);
	assert(picosystem_physics_world_add_box(&locked, &carriage) == 0);
	struct picosystem_physics_prismatic_joint_config lock =
		prismatic_joint_config(404U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID);
	lock.limit_enabled = 1U;
	assert(picosystem_physics_world_add_prismatic_joint(&locked, &lock) == 0);
	for (uint32_t step = 0U; step < 64U; ++step) {
		assert(picosystem_physics_world_step(&locked, &no_acceleration) == 0);
	}
	assert_fixed_close(prismatic_joint_translation(&locked, 0U), 0, RATIO(1, 32));
	assert_fixed_close(locked.bodies[0].velocity_per_tick.x, 0, 1);

	struct picosystem_physics_world motor_pair;
	init_world(&motor_pair, FIXED(2));
	const struct picosystem_physics_circle_config first = circle_config(1U, 0, 0, 2);
	const struct picosystem_physics_circle_config second = circle_config(2U, 0, 0, 2);
	assert(picosystem_physics_world_add_circle(&motor_pair, &first) == 0);
	assert(picosystem_physics_world_add_circle(&motor_pair, &second) == 0);
	drive = prismatic_joint_config(405U, 1U, 2U);
	drive.motor_speed_per_tick = RATIO(1, 8);
	drive.maximum_motor_impulse_per_tick = RATIO(1, 2);
	drive.motor_enabled = 1U;
	assert(picosystem_physics_world_add_prismatic_joint(&motor_pair, &drive) == 0);
	assert(picosystem_physics_world_step(&motor_pair, &no_acceleration) == 0);
	assert(motor_pair.contact_count == 0U);
	assert(motor_pair.last_work.joint_collision_filter_count == 1U);
	assert(motor_pair.bodies[0].velocity_per_tick.x > 0);
	assert(motor_pair.bodies[1].velocity_per_tick.x < 0);
	assert_fixed_close(motor_pair.bodies[0].velocity_per_tick.x -
				   motor_pair.bodies[1].velocity_per_tick.x,
			   drive.motor_speed_per_tick, 1);
	assert_fixed_close(motor_pair.bodies[0].velocity_per_tick.x +
				   motor_pair.bodies[1].velocity_per_tick.x,
			   0, 1);
}

static void test_prismatic_joint_connected_collision_policy(void)
{
	struct picosystem_physics_world colliding;
	init_world(&colliding, FIXED(2));
	const struct picosystem_physics_circle_config first = circle_config(1U, 0, 0, 2);
	const struct picosystem_physics_circle_config second = circle_config(2U, 0, 0, 2);
	assert(picosystem_physics_world_add_circle(&colliding, &first) == 0);
	assert(picosystem_physics_world_add_circle(&colliding, &second) == 0);
	struct picosystem_physics_prismatic_joint_config joint =
		prismatic_joint_config(401U, 1U, 2U);
	joint.collide_connected = 1U;
	assert(picosystem_physics_world_add_prismatic_joint(&colliding, &joint) == 0);
	assert(picosystem_physics_world_step(&colliding, &no_acceleration) == 0);
	assert(colliding.contact_count == 1U);
	assert(colliding.last_work.joint_collision_filter_count == 0U);
	assert(colliding.last_work.body_body_narrow_phase_test_count == 1U);
}

static void test_integration_speed_clamp_and_invalid_step(void)
{
	struct picosystem_physics_world world;
	init_world(&world, FIXED(2));
	struct picosystem_physics_circle_config body = circle_config(1U, 0, 0, 1);
	assert(picosystem_physics_world_add_circle(&world, &body) == 0);

	const struct picosystem_physics_vector acceleration = {.x = RATIO(1, 4)};
	assert(picosystem_physics_world_step(&world, &acceleration) == 0);
	assert(world.bodies[0].velocity_per_tick.x == RATIO(1, 4));
	assert(world.bodies[0].center.x == RATIO(1, 4));
	assert(world.last_candidate_pair_count == 0U);
	assert(world.contact_count == 0U);

	world.bodies[0].velocity_per_tick.x = RATIO(19, 10);
	const struct picosystem_physics_vector strong = {.x = PICOSYSTEM_PHYSICS_FIXED_ONE};
	assert(picosystem_physics_world_step(&world, &strong) == 0);
	assert_fixed_close(world.bodies[0].velocity_per_tick.x, FIXED(2), 1);
	const struct picosystem_physics_vector diagonal_acceleration = {
		.x = RATIO(1, 32),
		.y = RATIO(1, 32),
	};
	assert(picosystem_physics_world_step(&world, &diagonal_acceleration) == 0);
	/* A clamped vector must remain valid as input to the following tick. */
	assert(picosystem_physics_world_step(&world, &no_acceleration) == 0);

	struct picosystem_physics_world boundary_world;
	init_world(&boundary_world, FIXED(2));
	struct picosystem_physics_circle_config boundary_body = circle_config(1U, 1024, 0, 1);
	boundary_body.velocity_per_tick.x = FIXED(1);
	assert(picosystem_physics_world_add_circle(&boundary_world, &boundary_body) == 0);
	assert(picosystem_physics_world_step(&boundary_world, &no_acceleration) == 0);
	assert(boundary_world.bodies[0].center.x == FIXED(1024));
	/* A position at the safety envelope must also remain valid on the next tick. */
	assert(picosystem_physics_world_step(&boundary_world, &no_acceleration) == 0);

	const uint32_t hash_before = picosystem_physics_world_hash(&world);
	const struct picosystem_physics_body body_before = world.bodies[0];
	const struct picosystem_physics_vector invalid = {
		.x = PICOSYSTEM_PHYSICS_FIXED_ONE + 1,
	};
	assert(picosystem_physics_world_step(&world, &invalid) == -ERANGE);
	assert(picosystem_physics_world_hash(&world) == hash_before);
	assert(world.bodies[0].center.x == body_before.center.x);
	assert(world.bodies[0].velocity_per_tick.x == body_before.velocity_per_tick.x);
	assert(picosystem_physics_world_step(NULL, &no_acceleration) == -EINVAL);
	assert(picosystem_physics_world_step(&world, NULL) == -EINVAL);
}

static void test_box_geometry_and_angular_integration(void)
{
	struct picosystem_physics_world world;
	init_world(&world, FIXED(4));
	struct picosystem_physics_box_config box = box_config(1U, 0, 0, 2, 1);
	assert(picosystem_physics_world_add_box(&world, &box) == 0);

	struct picosystem_physics_vector vertices[PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT];
	assert(picosystem_physics_body_box_vertices(&world.bodies[0], vertices) == 0);
	assert(vertices[0].x == FIXED(-2));
	assert(vertices[0].y == FIXED(-1));
	assert(vertices[1].x == FIXED(2));
	assert(vertices[1].y == FIXED(-1));
	assert(vertices[2].x == FIXED(2));
	assert(vertices[2].y == FIXED(1));
	assert(vertices[3].x == FIXED(-2));
	assert(vertices[3].y == FIXED(1));

	world.bodies[0].angle_turns = PICOSYSTEM_PHYSICS_ANGLE_QUARTER_TURN;
	assert(picosystem_physics_body_box_vertices(&world.bodies[0], vertices) == 0);
	assert(vertices[0].x == FIXED(1));
	assert(vertices[0].y == FIXED(-2));
	assert(vertices[1].x == FIXED(1));
	assert(vertices[1].y == FIXED(2));
	assert(vertices[2].x == FIXED(-1));
	assert(vertices[2].y == FIXED(2));
	assert(vertices[3].x == FIXED(-1));
	assert(vertices[3].y == FIXED(-2));

	world.bodies[0].angle_turns = 0U;
	world.bodies[0].angular_velocity_per_tick = RATIO(1, 8);
	assert(picosystem_physics_world_step(&world, &no_acceleration) == 0);
	assert(world.bodies[0].angle_turns != 0U);
	assert(world.bodies[0].angular_velocity_per_tick == RATIO(1, 8));

	struct picosystem_physics_circle_config circle = circle_config(2U, 8, 0, 1);
	assert(picosystem_physics_world_add_circle(&world, &circle) == 0);
	assert(picosystem_physics_body_box_vertices(&world.bodies[1], vertices) == -ENOTSUP);
	assert(picosystem_physics_body_box_vertices(NULL, vertices) == -EINVAL);
	assert(picosystem_physics_body_box_vertices(&world.bodies[0], NULL) == -EINVAL);
}

static void test_equal_mass_head_on_collision(void)
{
	struct picosystem_physics_world world;
	init_world(&world, FIXED(4));
	struct picosystem_physics_circle_config left = circle_config(1U, -1, 0, 1);
	struct picosystem_physics_circle_config right = circle_config(2U, 1, 0, 1);
	left.center.x = -RATIO(3, 4);
	right.center.x = RATIO(3, 4);
	left.velocity_per_tick.x = RATIO(1, 2);
	right.velocity_per_tick.x = -RATIO(1, 2);
	left.restitution = PICOSYSTEM_PHYSICS_FIXED_ONE;
	right.restitution = PICOSYSTEM_PHYSICS_FIXED_ONE;
	left.friction = 0;
	right.friction = 0;
	assert(picosystem_physics_world_add_circle(&world, &left) == 0);
	assert(picosystem_physics_world_add_circle(&world, &right) == 0);

	assert(picosystem_physics_world_step(&world, &no_acceleration) == 0);
	assert(world.last_candidate_pair_count == 1U);
	assert(world.contact_count == 1U);
	assert_fixed_close(world.bodies[0].velocity_per_tick.x, -RATIO(1, 2), 4);
	assert_fixed_close(world.bodies[1].velocity_per_tick.x, RATIO(1, 2), 4);
	assert(world.bodies[0].center.x < world.bodies[1].center.x);
	assert((world.bodies[1].center.x - world.bodies[0].center.x) >= (FIXED(2) - RATIO(1, 128)));
	assert(world.last_work.solver_iteration_count == 2U);
	assert(world.last_work.solver_contact_visit_count == 2U);
	assert(world.last_work.solver_cached_contact_count == 1U);
	assert(world.last_work.solver_changed_contact_count == 1U);
}

static void test_unequal_mass_head_on_collision(void)
{
	struct picosystem_physics_world world;
	init_world(&world, FIXED(4));
	struct picosystem_physics_circle_config light = circle_config(1U, -1, 0, 1);
	struct picosystem_physics_circle_config heavy = circle_config(2U, 1, 0, 1);
	light.center.x = -RATIO(3, 4);
	heavy.center.x = RATIO(3, 4);
	light.velocity_per_tick.x = RATIO(3, 5);
	light.restitution = PICOSYSTEM_PHYSICS_FIXED_ONE;
	heavy.restitution = PICOSYSTEM_PHYSICS_FIXED_ONE;
	light.friction = 0;
	heavy.friction = 0;
	heavy.inverse_mass = RATIO(1, 2);
	assert(picosystem_physics_world_add_circle(&world, &light) == 0);
	assert(picosystem_physics_world_add_circle(&world, &heavy) == 0);

	assert(picosystem_physics_world_step(&world, &no_acceleration) == 0);
	assert_fixed_close(world.bodies[0].velocity_per_tick.x, -RATIO(1, 5), 8);
	assert_fixed_close(world.bodies[1].velocity_per_tick.x, RATIO(2, 5), 8);
}

static void test_static_floor_and_diagonal_segment(void)
{
	struct picosystem_physics_world floor_world;
	init_world(&floor_world, FIXED(4));
	struct picosystem_physics_circle_config falling = circle_config(1U, 0, 0, 1);
	falling.center.y = RATIO(3, 4);
	falling.velocity_per_tick.y = RATIO(1, 2);
	falling.restitution = PICOSYSTEM_PHYSICS_FIXED_ONE;
	falling.friction = 0;
	struct picosystem_physics_segment_config floor = horizontal_segment(1U, 2);
	floor.restitution = PICOSYSTEM_PHYSICS_FIXED_ONE;
	floor.friction = 0;
	assert(picosystem_physics_world_add_circle(&floor_world, &falling) == 0);
	assert(picosystem_physics_world_add_static_segment(&floor_world, &floor) == 0);
	assert(picosystem_physics_world_step(&floor_world, &no_acceleration) == 0);
	assert(floor_world.contact_count == 1U);
	assert_fixed_close(floor_world.bodies[0].velocity_per_tick.y, -RATIO(1, 2), 4);
	assert(floor_world.bodies[0].center.y <= (FIXED(1) + RATIO(1, 128)));

	struct picosystem_physics_world diagonal_world;
	init_world(&diagonal_world, FIXED(4));
	struct picosystem_physics_circle_config diagonal_body = circle_config(1U, 5, 4, 1);
	diagonal_body.velocity_per_tick.y = RATIO(1, 2);
	diagonal_body.restitution = PICOSYSTEM_PHYSICS_FIXED_ONE;
	diagonal_body.friction = 0;
	const struct picosystem_physics_segment_config diagonal = {
		.start = {.x = FIXED(0), .y = FIXED(0)},
		.end = {.x = FIXED(10), .y = FIXED(10)},
		.restitution = PICOSYSTEM_PHYSICS_FIXED_ONE,
		.friction = 0,
		.id = 1U,
	};
	assert(picosystem_physics_world_add_circle(&diagonal_world, &diagonal_body) == 0);
	assert(picosystem_physics_world_add_static_segment(&diagonal_world, &diagonal) == 0);
	assert(picosystem_physics_world_step(&diagonal_world, &no_acceleration) == 0);
	assert(diagonal_world.contact_count == 1U);
	assert(diagonal_world.bodies[0].velocity_per_tick.x > RATIO(2, 5));
	assert_fixed_close(diagonal_world.bodies[0].velocity_per_tick.y, 0, RATIO(1, 64));

	struct picosystem_physics_world endpoint_world;
	init_world(&endpoint_world, FIXED(4));
	struct picosystem_physics_circle_config endpoint_body = circle_config(1U, 11, 0, 1);
	endpoint_body.velocity_per_tick.x = -RATIO(3, 4);
	endpoint_body.restitution = PICOSYSTEM_PHYSICS_FIXED_ONE;
	endpoint_body.friction = 0;
	struct picosystem_physics_segment_config endpoint = horizontal_segment(1U, 0);
	endpoint.restitution = PICOSYSTEM_PHYSICS_FIXED_ONE;
	endpoint.friction = 0;
	assert(picosystem_physics_world_add_circle(&endpoint_world, &endpoint_body) == 0);
	assert(picosystem_physics_world_add_static_segment(&endpoint_world, &endpoint) == 0);
	assert(picosystem_physics_world_step(&endpoint_world, &no_acceleration) == 0);
	assert(endpoint_world.contact_count == 1U);
	assert(endpoint_world.bodies[0].center.x > FIXED(10));
	assert_fixed_close(endpoint_world.bodies[0].velocity_per_tick.x, RATIO(3, 4), 4);
}

static void test_box_floor_manifold_and_off_center_torque(void)
{
	struct picosystem_physics_world symmetric;
	init_world(&symmetric, FIXED(4));
	struct picosystem_physics_box_config falling = box_config(1U, 0, 0, 2, 1);
	falling.velocity_per_tick.y = RATIO(1, 2);
	falling.restitution = PICOSYSTEM_PHYSICS_FIXED_ONE;
	falling.friction = 0;
	struct picosystem_physics_segment_config floor = horizontal_segment(1U, 1);
	floor.start.y = FIXED(1) + RATIO(1, 4);
	floor.end.y = floor.start.y;
	floor.restitution = PICOSYSTEM_PHYSICS_FIXED_ONE;
	floor.friction = 0;
	assert(picosystem_physics_world_add_box(&symmetric, &falling) == 0);
	assert(picosystem_physics_world_add_static_segment(&symmetric, &floor) == 0);
	assert(picosystem_physics_world_step(&symmetric, &no_acceleration) == 0);
	assert(symmetric.contact_count == 2U);
	assert_fixed_close(symmetric.bodies[0].velocity_per_tick.y, -RATIO(1, 2), RATIO(1, 32));
	assert_fixed_close(symmetric.bodies[0].angular_velocity_per_tick, 0, RATIO(1, 128));

	struct picosystem_physics_world off_center;
	init_world(&off_center, FIXED(4));
	falling.center = (struct picosystem_physics_vector){0};
	falling.velocity_per_tick.y = RATIO(1, 2);
	assert(picosystem_physics_world_add_box(&off_center, &falling) == 0);
	floor.start.x = FIXED(1);
	assert(picosystem_physics_world_add_static_segment(&off_center, &floor) == 0);
	assert(picosystem_physics_world_step(&off_center, &no_acceleration) == 0);
	assert(off_center.contact_count >= 1U);
	assert(off_center.bodies[0].angular_velocity_per_tick != 0);
}

static void test_box_box_and_circle_box_collisions(void)
{
	struct picosystem_physics_world boxes;
	init_world(&boxes, FIXED(4));
	struct picosystem_physics_box_config left = box_config(1U, -1, 0, 1, 1);
	struct picosystem_physics_box_config right = box_config(2U, 1, 0, 1, 1);
	left.center.x = -RATIO(3, 4);
	right.center.x = RATIO(3, 4);
	left.velocity_per_tick.x = RATIO(1, 2);
	right.velocity_per_tick.x = -RATIO(1, 2);
	left.restitution = PICOSYSTEM_PHYSICS_FIXED_ONE;
	right.restitution = PICOSYSTEM_PHYSICS_FIXED_ONE;
	left.friction = 0;
	right.friction = 0;
	assert(picosystem_physics_world_add_box(&boxes, &left) == 0);
	assert(picosystem_physics_world_add_box(&boxes, &right) == 0);
	assert(picosystem_physics_world_step(&boxes, &no_acceleration) == 0);
	assert(boxes.contact_count == 2U);
	assert_fixed_close(boxes.bodies[0].velocity_per_tick.x, -RATIO(1, 2), RATIO(1, 32));
	assert_fixed_close(boxes.bodies[1].velocity_per_tick.x, RATIO(1, 2), RATIO(1, 32));

	struct picosystem_physics_world mixed;
	init_world(&mixed, FIXED(4));
	struct picosystem_physics_circle_config circle = circle_config(1U, -1, 0, 1);
	struct picosystem_physics_box_config box = box_config(2U, 1, 0, 1, 1);
	circle.center.x = -RATIO(5, 4);
	circle.velocity_per_tick.x = RATIO(1, 2);
	circle.restitution = PICOSYSTEM_PHYSICS_FIXED_ONE;
	circle.friction = 0;
	box.restitution = PICOSYSTEM_PHYSICS_FIXED_ONE;
	box.friction = 0;
	assert(picosystem_physics_world_add_circle(&mixed, &circle) == 0);
	assert(picosystem_physics_world_add_box(&mixed, &box) == 0);
	assert(picosystem_physics_world_step(&mixed, &no_acceleration) == 0);
	assert(mixed.contact_count == 1U);
	assert_fixed_close(mixed.bodies[0].velocity_per_tick.x, 0, RATIO(1, 32));
	assert_fixed_close(mixed.bodies[1].velocity_per_tick.x, RATIO(1, 2), RATIO(1, 32));

	struct picosystem_physics_world contained;
	init_world(&contained, FIXED(4));
	circle = circle_config(1U, 1, 0, 1);
	box = box_config(2U, 0, 0, 2, 2);
	circle.restitution = 0;
	box.restitution = 0;
	assert(picosystem_physics_world_add_circle(&contained, &circle) == 0);
	assert(picosystem_physics_world_add_box(&contained, &box) == 0);
	assert(picosystem_physics_world_step(&contained, &no_acceleration) == 0);
	assert(contained.contact_count == 1U);
	assert(contained.bodies[0].center.x > FIXED(1));
	assert(contained.bodies[1].center.x < 0);
}

static void test_capsule_collisions_and_sensor_overlap(void)
{
	struct picosystem_physics_world circle_world;
	init_world(&circle_world, FIXED(4));
	struct picosystem_physics_capsule_config capsule = capsule_config(1U, 0, 0, 2, 1);
	struct picosystem_physics_circle_config circle = circle_config(2U, 4, 0, 1);
	circle.center.x = FIXED(7) / 2;
	capsule.restitution = 0;
	circle.restitution = 0;
	assert(picosystem_physics_world_add_capsule(&circle_world, &capsule) == 0);
	assert(picosystem_physics_world_add_circle(&circle_world, &circle) == 0);
	assert(picosystem_physics_world_step(&circle_world, &no_acceleration) == 0);
	assert(circle_world.contact_count == 1U);
	assert(circle_world.bodies[0].center.x < 0);
	assert(circle_world.bodies[1].center.x > (FIXED(7) / 2));
	init_world(&circle_world, FIXED(4));
	circle.center.x = FIXED(4);
	assert(picosystem_physics_world_add_capsule(&circle_world, &capsule) == 0);
	assert(picosystem_physics_world_add_circle(&circle_world, &circle) == 0);
	assert(picosystem_physics_world_step(&circle_world, &no_acceleration) == 0);
	assert(circle_world.contact_count == 0U);

	struct picosystem_physics_world capsule_world;
	init_world(&capsule_world, FIXED(4));
	struct picosystem_physics_capsule_config upper = capsule_config(2U, 0, 2, 3, 1);
	upper.center.y = FIXED(3) / 2;
	capsule = capsule_config(1U, 0, 0, 3, 1);
	capsule.restitution = 0;
	upper.restitution = 0;
	assert(picosystem_physics_world_add_capsule(&capsule_world, &capsule) == 0);
	assert(picosystem_physics_world_add_capsule(&capsule_world, &upper) == 0);
	assert(picosystem_physics_world_step(&capsule_world, &no_acceleration) == 0);
	assert(capsule_world.contact_count == 1U);
	assert(capsule_world.bodies[0].center.y < 0);
	assert(capsule_world.bodies[1].center.y > (FIXED(3) / 2));
	init_world(&capsule_world, FIXED(4));
	upper.center.y = FIXED(2);
	assert(picosystem_physics_world_add_capsule(&capsule_world, &capsule) == 0);
	assert(picosystem_physics_world_add_capsule(&capsule_world, &upper) == 0);
	assert(picosystem_physics_world_step(&capsule_world, &no_acceleration) == 0);
	assert(capsule_world.contact_count == 0U);
	init_world(&capsule_world, FIXED(4));
	upper.center.y = 0;
	upper.angle_turns = PICOSYSTEM_PHYSICS_ANGLE_QUARTER_TURN;
	assert(picosystem_physics_world_add_capsule(&capsule_world, &capsule) == 0);
	assert(picosystem_physics_world_add_capsule(&capsule_world, &upper) == 0);
	assert(picosystem_physics_world_step(&capsule_world, &no_acceleration) == 0);
	assert(capsule_world.contact_count == 1U);
	assert(capsule_world.bodies[0].center.y < capsule_world.bodies[1].center.y);

	struct picosystem_physics_world box_world;
	init_world(&box_world, FIXED(4));
	capsule = capsule_config(1U, 0, 0, 2, 1);
	struct picosystem_physics_box_config box = box_config(2U, 4, 0, 1, 1);
	box.center.x = FIXED(7) / 2;
	capsule.restitution = 0;
	box.restitution = 0;
	assert(picosystem_physics_world_add_capsule(&box_world, &capsule) == 0);
	assert(picosystem_physics_world_add_box(&box_world, &box) == 0);
	assert(picosystem_physics_world_step(&box_world, &no_acceleration) == 0);
	assert(box_world.contact_count == 1U);
	assert(box_world.bodies[0].center.x < 0);
	assert(box_world.bodies[1].center.x > (FIXED(7) / 2));
	init_world(&box_world, FIXED(4));
	box.center.x = RATIO(19, 5);
	box.center.y = RATIO(9, 5);
	assert(picosystem_physics_world_add_capsule(&box_world, &capsule) == 0);
	assert(picosystem_physics_world_add_box(&box_world, &box) == 0);
	assert(picosystem_physics_world_step(&box_world, &no_acceleration) == 0);
	assert(box_world.contact_count == 0U);

	struct picosystem_physics_world floor_world;
	init_world(&floor_world, FIXED(4));
	capsule = capsule_config(1U, 0, 0, 3, 1);
	capsule.restitution = 0;
	struct picosystem_physics_segment_config floor = horizontal_segment(101U, 1);
	floor.start.y = RATIO(3, 4);
	floor.end.y = floor.start.y;
	floor.restitution = 0;
	assert(picosystem_physics_world_add_capsule(&floor_world, &capsule) == 0);
	assert(picosystem_physics_world_add_static_segment(&floor_world, &floor) == 0);
	assert(picosystem_physics_world_step(&floor_world, &no_acceleration) == 0);
	assert(floor_world.contact_count == 2U);
	assert(floor_world.bodies[0].center.y < 0);
	assert(floor_world.bodies[0].angular_velocity_per_tick == 0);
	init_world(&floor_world, FIXED(4));
	floor.start.y = FIXED(1);
	floor.end.y = FIXED(1);
	assert(picosystem_physics_world_add_capsule(&floor_world, &capsule) == 0);
	assert(picosystem_physics_world_add_static_segment(&floor_world, &floor) == 0);
	assert(picosystem_physics_world_step(&floor_world, &no_acceleration) == 0);
	assert(floor_world.contact_count == 0U);

	struct picosystem_physics_world sensor_world;
	init_world(&sensor_world, FIXED(4));
	capsule = capsule_config(1U, 10, 10, 3, 1);
	const struct picosystem_physics_box_sensor_config sensor =
		box_sensor_config(201U, 10, 10, 1, 1);
	assert(picosystem_physics_world_add_capsule(&sensor_world, &capsule) == 0);
	assert(picosystem_physics_world_add_box_sensor(&sensor_world, &sensor) == 0);
	assert(picosystem_physics_world_step(&sensor_world, &no_acceleration) == 0);
	assert(sensor_world.last_work.sensor_overlap_count == 1U);
	assert(sensor_world.contact_event_count == 1U);

	init_world(&sensor_world, FIXED(4));
	capsule.center.y = FIXED(12);
	assert(picosystem_physics_world_add_capsule(&sensor_world, &capsule) == 0);
	assert(picosystem_physics_world_add_box_sensor(&sensor_world, &sensor) == 0);
	assert(picosystem_physics_world_step(&sensor_world, &no_acceleration) == 0);
	assert(sensor_world.last_work.sensor_overlap_count == 0U);
	capsule.center.y = FIXED(23) / 2;
	init_world(&sensor_world, FIXED(4));
	assert(picosystem_physics_world_add_capsule(&sensor_world, &capsule) == 0);
	assert(picosystem_physics_world_add_box_sensor(&sensor_world, &sensor) == 0);
	assert(picosystem_physics_world_step(&sensor_world, &no_acceleration) == 0);
	assert(sensor_world.last_work.sensor_overlap_count == 1U);
}

static void test_coincident_centers_are_stable(void)
{
	struct picosystem_physics_world world;
	init_world(&world, FIXED(2));
	struct picosystem_physics_circle_config left = circle_config(1U, 0, 0, 1);
	struct picosystem_physics_circle_config right = circle_config(2U, 0, 0, 1);
	left.restitution = 0;
	right.restitution = 0;
	assert(picosystem_physics_world_add_circle(&world, &left) == 0);
	assert(picosystem_physics_world_add_circle(&world, &right) == 0);
	assert(picosystem_physics_world_step(&world, &no_acceleration) == 0);
	assert(world.contact_count == 1U);
	assert(world.bodies[0].center.x < world.bodies[1].center.x);
	assert(world.bodies[0].center.y == 0);
	assert(world.bodies[1].center.y == 0);
}

static void test_uniform_grid_filter_and_fallback(void)
{
	struct picosystem_physics_world separated;
	init_world(&separated, FIXED(2));
	const struct picosystem_physics_circle_config left = circle_config(1U, 8, 8, 2);
	const struct picosystem_physics_circle_config right = circle_config(2U, 232, 232, 2);
	assert(picosystem_physics_world_add_circle(&separated, &left) == 0);
	assert(picosystem_physics_world_add_circle(&separated, &right) == 0);
	assert(picosystem_physics_world_step(&separated, &no_acceleration) == 0);
	assert(separated.last_possible_pair_count == 1U);
	assert(separated.last_candidate_pair_count == 0U);
	assert(separated.last_occupied_grid_cell_count == 2U);
	assert(separated.last_broad_phase_fallback == 0U);
	assert(separated.last_solver_iteration_count == 0U);
	assert(separated.contact_count == 0U);
	assert(separated.last_work.possible_pair_count == 1U);
	assert(separated.last_work.candidate_pair_count == 0U);
	assert(separated.last_work.grid_cell_insertion_count == 2U);
	assert(separated.last_work.occupied_grid_cell_count == 2U);
	assert(separated.last_work.maximum_grid_cell_occupancy == 1U);
	assert(separated.last_work.body_body_narrow_phase_test_count == 0U);
	assert(separated.last_work.body_segment_narrow_phase_test_count == 0U);
	assert(separated.last_work.manifold_count == 0U);
	assert(separated.last_work.contact_point_count == 0U);
	assert(separated.last_work.position_correction_visit_count == 0U);
	assert(separated.last_work.solver_iteration_count == 0U);
	assert(separated.last_work.solver_contact_visit_count == 0U);
	assert(separated.last_work.solver_changed_contact_count == 0U);
	assert(separated.last_work.broad_phase_fallback_count == 0U);

	struct picosystem_physics_world boundary;
	init_world(&boundary, FIXED(2));
	struct picosystem_physics_circle_config boundary_left = circle_config(1U, 31, 64, 1);
	struct picosystem_physics_circle_config boundary_right = circle_config(2U, 33, 64, 1);
	boundary_left.center.x += RATIO(1, 4);
	boundary_right.center.x -= RATIO(1, 4);
	assert(picosystem_physics_world_add_circle(&boundary, &boundary_left) == 0);
	assert(picosystem_physics_world_add_circle(&boundary, &boundary_right) == 0);
	assert(picosystem_physics_world_step(&boundary, &no_acceleration) == 0);
	assert(boundary.last_candidate_pair_count == 1U);
	assert(boundary.last_broad_phase_fallback == 0U);
	assert(boundary.contact_count == 1U);
	assert(boundary.last_solver_iteration_count == 1U);
	assert(boundary.last_work.candidate_pair_count == 1U);
	assert(boundary.last_work.body_body_narrow_phase_test_count == 1U);
	assert(boundary.last_work.manifold_count == 1U);
	assert(boundary.last_work.contact_point_count == 1U);
	assert(boundary.last_work.position_correction_visit_count == 1U);
	assert(boundary.last_work.solver_iteration_count == 1U);
	assert(boundary.last_work.solver_contact_visit_count == 1U);

	struct picosystem_physics_world fallback;
	init_world(&fallback, FIXED(2));
	struct picosystem_physics_circle_config outside_left = circle_config(1U, -1, 0, 1);
	struct picosystem_physics_circle_config outside_right = circle_config(2U, 1, 0, 1);
	outside_left.center.x = -RATIO(3, 4);
	outside_right.center.x = RATIO(3, 4);
	assert(picosystem_physics_world_add_circle(&fallback, &outside_left) == 0);
	assert(picosystem_physics_world_add_circle(&fallback, &outside_right) == 0);
	assert(picosystem_physics_world_step(&fallback, &no_acceleration) == 0);
	assert(fallback.last_possible_pair_count == 1U);
	assert(fallback.last_candidate_pair_count == 1U);
	assert(fallback.last_occupied_grid_cell_count == 0U);
	assert(fallback.last_broad_phase_fallback == 1U);
	assert(fallback.contact_count == 1U);
	assert(fallback.last_solver_iteration_count == 1U);
	assert(fallback.last_work.broad_phase_fallback_count == 1U);
}

static void test_profiled_step_and_reference_work(void)
{
	struct picosystem_physics_world grid;
	init_world(&grid, FIXED(2));
	const struct picosystem_physics_circle_config left = circle_config(1U, 8, 8, 2);
	const struct picosystem_physics_circle_config right = circle_config(2U, 232, 232, 2);
	assert(picosystem_physics_world_add_circle(&grid, &left) == 0);
	assert(picosystem_physics_world_add_circle(&grid, &right) == 0);
	struct picosystem_physics_world reference = grid;

	uint32_t grid_cycles = 0U;
	const struct picosystem_physics_clock grid_clock = {
		.now = fake_clock_now,
		.context = &grid_cycles,
	};
	struct picosystem_physics_step_profile grid_profile;
	assert(picosystem_physics_world_step_profiled(&grid, &no_acceleration,
						      PICOSYSTEM_PHYSICS_STEP_MODE_GRID,
						      &grid_clock, &grid_profile) == 0);
	assert(grid_profile.clock_read_count > 0U);
	assert(grid_profile.stage_cycles[PICOSYSTEM_PHYSICS_PROFILE_TOTAL] > 0U);
	uint32_t attributed_cycles = 0U;
	for (size_t stage = PICOSYSTEM_PHYSICS_PROFILE_FORCE_AND_INTEGRATE;
	     stage < PICOSYSTEM_PHYSICS_PROFILE_TOTAL; ++stage) {
		attributed_cycles += grid_profile.stage_cycles[stage];
	}
	assert(attributed_cycles == grid_profile.stage_cycles[PICOSYSTEM_PHYSICS_PROFILE_TOTAL]);
	assert(grid_profile.work.candidate_pair_count == 0U);
	assert(grid_profile.work.grid_cell_insertion_count == 2U);

	uint32_t reference_cycles = 0U;
	const struct picosystem_physics_clock reference_clock = {
		.now = fake_clock_now,
		.context = &reference_cycles,
	};
	struct picosystem_physics_step_profile reference_profile;
	assert(picosystem_physics_world_step_profiled(&reference, &no_acceleration,
						      PICOSYSTEM_PHYSICS_STEP_MODE_REFERENCE,
						      &reference_clock, &reference_profile) == 0);
	assert(reference_profile.work.possible_pair_count == 1U);
	assert(reference_profile.work.candidate_pair_count == 1U);
	assert(reference_profile.work.body_body_narrow_phase_test_count == 1U);
	assert(reference_profile.work.grid_cell_insertion_count == 0U);
	assert(reference_profile.work.broad_phase_fallback_count == 0U);
	assert(reference.last_broad_phase_fallback == 1U);
	assert(picosystem_physics_world_hash(&grid) == picosystem_physics_world_hash(&reference));

	assert(picosystem_physics_world_step_profiled(&grid, &no_acceleration,
						      (enum picosystem_physics_step_mode)99,
						      &grid_clock, &grid_profile) == -EINVAL);
	assert(picosystem_physics_world_step_profiled(&grid, &no_acceleration,
						      PICOSYSTEM_PHYSICS_STEP_MODE_GRID, NULL,
						      &grid_profile) == -EINVAL);
}

static void add_grid_oracle_fixture(struct picosystem_physics_world *world)
{
	static const int16_t centers[][2] = {
		{40, 52},  {50, 52},  {82, 48},   {115, 55},  {150, 50},  {190, 48},
		{35, 105}, {70, 110}, {105, 100}, {140, 110}, {175, 100}, {210, 108},
	};
	static const struct picosystem_physics_segment_config segments[] = {
		{.start = {.x = FIXED(4), .y = FIXED(24)},
		 .end = {.x = FIXED(252), .y = FIXED(24)},
		 .restitution = RATIO(3, 4),
		 .friction = RATIO(1, 8),
		 .id = 101U},
		{.start = {.x = FIXED(252), .y = FIXED(232)},
		 .end = {.x = FIXED(252), .y = FIXED(24)},
		 .restitution = RATIO(3, 4),
		 .friction = RATIO(1, 8),
		 .id = 102U},
		{.start = {.x = FIXED(252), .y = FIXED(232)},
		 .end = {.x = FIXED(4), .y = FIXED(232)},
		 .restitution = RATIO(3, 4),
		 .friction = RATIO(1, 8),
		 .id = 103U},
		{.start = {.x = FIXED(4), .y = FIXED(24)},
		 .end = {.x = FIXED(4), .y = FIXED(232)},
		 .restitution = RATIO(3, 4),
		 .friction = RATIO(1, 8),
		 .id = 104U},
		{.start = {.x = FIXED(30), .y = FIXED(170)},
		 .end = {.x = FIXED(110), .y = FIXED(195)},
		 .restitution = RATIO(2, 3),
		 .friction = RATIO(1, 5),
		 .id = 105U},
		{.start = {.x = FIXED(135), .y = FIXED(185)},
		 .end = {.x = FIXED(225), .y = FIXED(140)},
		 .restitution = RATIO(4, 5),
		 .friction = RATIO(1, 10),
		 .id = 106U},
	};

	init_world(world, FIXED(3));
	for (uint16_t index = 0U; index < PICOSYSTEM_PHYSICS_MAX_BODIES; ++index) {
		const int32_t velocity_direction = (int32_t)(index % 3U) - 1;
		if ((index % 3U) == 0U) {
			struct picosystem_physics_capsule_config capsule = capsule_config(
				(uint16_t)(index + 1U), centers[index][0], centers[index][1], 6, 3);
			capsule.velocity_per_tick.x = velocity_direction * RATIO(1, 4);
			capsule.velocity_per_tick.y = RATIO(1, 16);
			capsule.angular_velocity_per_tick =
				((index & 1U) == 0U) ? RATIO(1, 96) : -RATIO(1, 96);
			capsule.angle_turns = (uint32_t)index * UINT32_C(0x08000000);
			assert(picosystem_physics_world_add_capsule(world, &capsule) == 0);
		} else if ((index % 3U) == 1U) {
			struct picosystem_physics_circle_config circle = circle_config(
				(uint16_t)(index + 1U), centers[index][0], centers[index][1], 6);
			circle.velocity_per_tick.x = velocity_direction * RATIO(1, 4);
			circle.velocity_per_tick.y = RATIO(1, 16);
			assert(picosystem_physics_world_add_circle(world, &circle) == 0);
		} else {
			struct picosystem_physics_box_config box = box_config(
				(uint16_t)(index + 1U), centers[index][0], centers[index][1], 7, 5);
			box.velocity_per_tick.x = velocity_direction * RATIO(1, 4);
			box.velocity_per_tick.y = RATIO(1, 16);
			box.angular_velocity_per_tick =
				((index & 2U) == 0U) ? RATIO(1, 96) : -RATIO(1, 96);
			box.angle_turns = (uint32_t)index * UINT32_C(0x08000000);
			assert(picosystem_physics_world_add_box(world, &box) == 0);
		}
	}
	for (size_t index = 0U; index < (sizeof(segments) / sizeof(segments[0])); ++index) {
		assert(picosystem_physics_world_add_static_segment(world, &segments[index]) == 0);
	}
	const struct picosystem_physics_box_sensor_config sensors[] = {
		box_sensor_config(301U, 50, 52, 14, 10),
		box_sensor_config(302U, 145, 105, 18, 12),
		box_sensor_config(303U, 225, 210, 8, 8),
	};
	for (size_t index = 0U; index < (sizeof(sensors) / sizeof(sensors[0])); ++index) {
		assert(picosystem_physics_world_add_box_sensor(world, &sensors[index]) == 0);
	}
	struct picosystem_physics_distance_joint_config joint =
		distance_joint_config(201U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID, 32);
	joint.anchor_b = (struct picosystem_physics_vector){.x = FIXED(40), .y = FIXED(20)};
	assert(picosystem_physics_world_add_distance_joint(world, &joint) == 0);
	joint = distance_joint_config(202U, 1U, 2U, 10);
	assert(picosystem_physics_world_add_distance_joint(world, &joint) == 0);
	joint = distance_joint_config(203U, 2U, 3U, 30);
	joint.local_anchor_a.x = FIXED(2);
	assert(picosystem_physics_world_add_distance_joint(world, &joint) == 0);
}

static void test_uniform_grid_matches_brute_force_oracle(void)
{
	struct picosystem_physics_world grid;
	add_grid_oracle_fixture(&grid);
	struct picosystem_physics_world reference = grid;
	static const struct picosystem_physics_vector accelerations[] = {
		{.y = RATIO(1, 64)},
		{.x = RATIO(1, 64), .y = RATIO(1, 64)},
		{.x = -RATIO(1, 64)},
		{.x = -RATIO(1, 64), .y = -RATIO(1, 64)},
	};
	bool saw_contact = false;
	bool saw_strict_reduction = false;

	for (uint32_t step = 0U; step < 1000U; ++step) {
		const struct picosystem_physics_vector *const acceleration =
			&accelerations[(step / 100U) %
				       (sizeof(accelerations) / sizeof(accelerations[0]))];
		assert(picosystem_physics_world_step(&grid, acceleration) == 0);
		assert(picosystem_physics_world_step_reference(&reference, acceleration) == 0);
		assert(grid.last_broad_phase_fallback == 0U);
		assert(reference.last_broad_phase_fallback == 1U);
		assert(grid.last_occupied_grid_cell_count > 0U);
		assert(grid.last_candidate_pair_count <= grid.last_possible_pair_count);
		if (grid.last_candidate_pair_count < grid.last_possible_pair_count) {
			saw_strict_reduction = true;
		}
		if (grid.contact_count > 0U) {
			saw_contact = true;
		}
		assert_step_matches_reference(&grid, &reference);
	}

	assert(saw_contact);
	assert(saw_strict_reduction);
}

static void test_contact_storage_covers_all_candidates(void)
{
	struct picosystem_physics_world world;
	init_world(&world, FIXED(1));
	for (uint16_t index = 0U; index < PICOSYSTEM_PHYSICS_MAX_BODIES; ++index) {
		const struct picosystem_physics_circle_config body =
			circle_config((uint16_t)(index + 1U), 0, 0, 1);
		assert(picosystem_physics_world_add_circle(&world, &body) == 0);
	}
	for (uint16_t index = 0U; index < PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS; ++index) {
		const struct picosystem_physics_segment_config segment =
			horizontal_segment((uint16_t)(index + 1U), 0);
		assert(picosystem_physics_world_add_static_segment(&world, &segment) == 0);
	}
	for (uint16_t index = 0U; index < PICOSYSTEM_PHYSICS_MAX_BOX_SENSORS; ++index) {
		const struct picosystem_physics_box_sensor_config sensor =
			box_sensor_config((uint16_t)(201U + index), 0, 0, 1, 1);
		assert(picosystem_physics_world_add_box_sensor(&world, &sensor) == 0);
	}

	assert(picosystem_physics_world_step(&world, &no_acceleration) == 0);
	assert(world.last_candidate_pair_count == PICOSYSTEM_PHYSICS_MAX_CONTACT_EVENTS);
	assert(world.contact_count == PICOSYSTEM_PHYSICS_MAX_CANDIDATE_PAIRS);
	assert(world.contact_event_count == PICOSYSTEM_PHYSICS_MAX_CONTACT_EVENTS);
	assert(world.last_work.sensor_overlap_count ==
	       (PICOSYSTEM_PHYSICS_MAX_BODIES * PICOSYSTEM_PHYSICS_MAX_BOX_SENSORS));
	assert(world.last_work.contact_begin_event_count == PICOSYSTEM_PHYSICS_MAX_CONTACT_EVENTS);
}

static void step_without_acceleration(struct picosystem_physics_world *world, uint32_t count)
{
	for (uint32_t tick = 0U; tick < count; ++tick) {
		assert(picosystem_physics_world_step(world, &no_acceleration) == 0);
	}
}

static void test_spring_boundaries_and_setter(void)
{
	struct picosystem_physics_world world;
	init_world(&world, FIXED(4));
	const struct picosystem_physics_circle_config body = circle_config(1U, 10, 0, 1);
	assert(picosystem_physics_world_add_circle(&world, &body) == 0);
	struct picosystem_physics_distance_joint_config spring =
		spring_joint_config(101U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID, 10);
	const uint32_t body_hash = picosystem_physics_world_hash(&world);

	assert(picosystem_physics_world_set_spring_target_distance(NULL, 0U, FIXED(8)) == -EINVAL);
	assert(picosystem_physics_world_set_spring_target_distance(&world, 0U, FIXED(8)) ==
	       -ENOENT);
	struct picosystem_physics_distance_joint_config invalid = spring;
	invalid.spring_enabled = 2U;
	assert(picosystem_physics_world_add_distance_joint(&world, &invalid) == -ERANGE);
	invalid = spring;
	invalid.spring_angular_frequency_per_tick = RATIO(1, 128);
	assert(picosystem_physics_world_add_distance_joint(&world, &invalid) == -ERANGE);
	invalid = spring;
	invalid.spring_angular_frequency_per_tick = RATIO(33, 64);
	assert(picosystem_physics_world_add_distance_joint(&world, &invalid) == -ERANGE);
	invalid = spring;
	invalid.spring_damping_ratio = -1;
	assert(picosystem_physics_world_add_distance_joint(&world, &invalid) == -ERANGE);
	invalid = spring;
	invalid.spring_damping_ratio = FIXED(2) + 1;
	assert(picosystem_physics_world_add_distance_joint(&world, &invalid) == -ERANGE);
	invalid = spring;
	invalid.maximum_spring_impulse_per_tick = 0;
	assert(picosystem_physics_world_add_distance_joint(&world, &invalid) == -ERANGE);
	invalid = spring;
	invalid.maximum_spring_impulse_per_tick = FIXED(8) + 1;
	assert(picosystem_physics_world_add_distance_joint(&world, &invalid) == -ERANGE);
	invalid = distance_joint_config(101U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID, 10);
	invalid.spring_damping_ratio = RATIO(1, 2);
	assert(picosystem_physics_world_add_distance_joint(&world, &invalid) == -ERANGE);
	assert(picosystem_physics_world_hash(&world) == body_hash);

	assert(picosystem_physics_world_add_distance_joint(&world, &spring) == 0);
	assert(world.distance_joints[0].spring_enabled == 1U);
	const uint32_t spring_hash = picosystem_physics_world_hash(&world);
	assert(picosystem_physics_world_set_spring_target_distance(&world, 1U, FIXED(8)) ==
	       -ENOENT);
	assert(picosystem_physics_world_set_spring_target_distance(&world, 0U, 0) == -ERANGE);
	assert(picosystem_physics_world_hash(&world) == spring_hash);
	assert(picosystem_physics_world_set_spring_target_distance(&world, 0U, FIXED(8)) == 0);
	assert(world.distance_joints[0].target_distance == FIXED(8));
	assert(picosystem_physics_world_hash(&world) != spring_hash);

	struct picosystem_physics_world hard_world;
	init_world(&hard_world, FIXED(4));
	assert(picosystem_physics_world_add_circle(&hard_world, &body) == 0);
	const struct picosystem_physics_distance_joint_config hard =
		distance_joint_config(101U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID, 10);
	assert(picosystem_physics_world_add_distance_joint(&hard_world, &hard) == 0);
	assert(picosystem_physics_world_set_spring_target_distance(&hard_world, 0U, FIXED(8)) ==
	       -ENOTSUP);
}

static void test_spring_dynamics_sleep_and_reference(void)
{
	struct picosystem_physics_world spring_world;
	init_world(&spring_world, FIXED(4));
	const struct picosystem_physics_circle_config body = circle_config(1U, 20, 0, 1);
	assert(picosystem_physics_world_add_circle(&spring_world, &body) == 0);
	const struct picosystem_physics_distance_joint_config spring =
		spring_joint_config(101U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID, 10);
	assert(picosystem_physics_world_add_distance_joint(&spring_world, &spring) == 0);
	assert(picosystem_physics_world_step(&spring_world, &no_acceleration) == 0);
	assert(spring_world.bodies[0].center.x == FIXED(20));
	assert(spring_world.bodies[0].velocity_per_tick.x < 0);
	assert(spring_world.last_work.spring_joint_count == 1U);
	assert(spring_world.last_work.joint_position_correction_visit_count == 0U);
	assert(spring_world.last_work.spring_solver_visit_count > 0U);
	assert(spring_world.last_work.spring_solver_changed_count > 0U);
	for (uint32_t tick = 0U; tick < 120U; ++tick) {
		assert(picosystem_physics_world_step(&spring_world, &no_acceleration) == 0);
	}
	assert_fixed_close(spring_world.bodies[0].center.x, FIXED(10), FIXED(1));

	struct picosystem_physics_world limited;
	init_world(&limited, FIXED(4));
	assert(picosystem_physics_world_add_circle(&limited, &body) == 0);
	struct picosystem_physics_distance_joint_config limited_spring = spring;
	limited_spring.maximum_spring_impulse_per_tick = RATIO(1, 64);
	assert(picosystem_physics_world_add_distance_joint(&limited, &limited_spring) == 0);
	assert(picosystem_physics_world_step(&limited, &no_acceleration) == 0);
	assert(limited.bodies[0].velocity_per_tick.x == -RATIO(1, 64));

	struct picosystem_physics_world off_center;
	init_world(&off_center, FIXED(4));
	const struct picosystem_physics_box_config box = box_config(1U, 20, 0, 2, 4);
	assert(picosystem_physics_world_add_box(&off_center, &box) == 0);
	struct picosystem_physics_distance_joint_config offset_spring = spring;
	offset_spring.local_anchor_a.y = FIXED(4);
	assert(picosystem_physics_world_add_distance_joint(&off_center, &offset_spring) == 0);
	assert(picosystem_physics_world_step(&off_center, &no_acceleration) == 0);
	assert(off_center.bodies[0].angular_velocity_per_tick != 0);

	struct picosystem_physics_world sleeping;
	init_world(&sleeping, FIXED(4));
	const struct picosystem_physics_circle_config resting = circle_config(1U, 10, 0, 1);
	assert(picosystem_physics_world_add_circle(&sleeping, &resting) == 0);
	assert(picosystem_physics_world_add_distance_joint(&sleeping, &spring) == 0);
	step_without_acceleration(&sleeping, PICOSYSTEM_PHYSICS_SLEEP_QUIET_TICKS);
	assert(picosystem_physics_world_body_is_sleeping(&sleeping, 0U));
	assert(picosystem_physics_world_set_spring_target_distance(&sleeping, 0U, FIXED(8)) == 0);
	assert(!picosystem_physics_world_body_is_sleeping(&sleeping, 0U));

	struct picosystem_physics_world gravity_sleeping;
	init_world(&gravity_sleeping, FIXED(4));
	struct picosystem_physics_circle_config hanging = circle_config(1U, 0, 10, 1);
	hanging.restitution = 0;
	assert(picosystem_physics_world_add_circle(&gravity_sleeping, &hanging) == 0);
	assert(picosystem_physics_world_add_distance_joint(&gravity_sleeping, &spring) == 0);
	const struct picosystem_physics_vector gravity = {.y = RATIO(1, 64)};
	for (uint32_t tick = 0U;
	     (tick < 2000U) && !picosystem_physics_world_body_is_sleeping(&gravity_sleeping, 0U);
	     ++tick) {
		assert(picosystem_physics_world_step(&gravity_sleeping, &gravity) == 0);
	}
	assert(picosystem_physics_world_body_is_sleeping(&gravity_sleeping, 0U));

	struct picosystem_physics_world sleeping_pair;
	init_world(&sleeping_pair, FIXED(4));
	const struct picosystem_physics_circle_config left = circle_config(1U, -2, 0, 1);
	const struct picosystem_physics_circle_config right = circle_config(2U, 2, 0, 1);
	assert(picosystem_physics_world_add_circle(&sleeping_pair, &left) == 0);
	assert(picosystem_physics_world_add_circle(&sleeping_pair, &right) == 0);
	const struct picosystem_physics_distance_joint_config pair_spring =
		spring_joint_config(102U, 1U, 2U, 4);
	assert(picosystem_physics_world_add_distance_joint(&sleeping_pair, &pair_spring) == 0);
	step_without_acceleration(&sleeping_pair, PICOSYSTEM_PHYSICS_SLEEP_QUIET_TICKS);
	assert(sleeping_pair.sleeping_body_mask == UINT16_C(3));
	assert(picosystem_physics_world_set_spring_target_distance(&sleeping_pair, 0U, FIXED(3)) ==
	       0);
	assert(sleeping_pair.sleeping_body_mask == 0U);

	struct picosystem_physics_world grid = off_center;
	struct picosystem_physics_world reference = off_center;
	for (uint32_t tick = 0U; tick < 64U; ++tick) {
		assert(picosystem_physics_world_step(&grid, &no_acceleration) == 0);
		assert(picosystem_physics_world_step_reference(&reference, &no_acceleration) == 0);
		assert_step_matches_reference(&grid, &reference);
	}
}

static void init_conveyor_world(struct picosystem_physics_world *world,
				picosystem_physics_fixed_t surface_speed,
				picosystem_physics_fixed_t friction)
{
	init_world(world, FIXED(4));
	struct picosystem_physics_circle_config body = circle_config(1U, 0, -1, 2);
	body.restitution = 0;
	body.friction = friction;
	struct picosystem_physics_segment_config segment = horizontal_segment(101U, 0);
	segment.restitution = 0;
	segment.friction = friction;
	segment.surface_speed_per_tick = surface_speed;
	assert(picosystem_physics_world_add_circle(world, &body) == 0);
	assert(picosystem_physics_world_add_static_segment(world, &segment) == 0);
}

static void test_conveyor_direction_setter_sleep_and_reference(void)
{
	const struct picosystem_physics_vector gravity = {.y = RATIO(1, 64)};
	struct picosystem_physics_world forward;
	init_conveyor_world(&forward, RATIO(1, 2), PICOSYSTEM_PHYSICS_FIXED_ONE);
	assert(picosystem_physics_world_step(&forward, &gravity) == 0);
	assert(forward.bodies[0].velocity_per_tick.x > 0);
	assert(forward.last_work.conveyor_contact_count == 1U);
	assert(forward.last_work.conveyor_solver_visit_count > 0U);
	assert(forward.last_work.conveyor_solver_changed_count > 0U);

	struct picosystem_physics_world reverse;
	init_conveyor_world(&reverse, -RATIO(1, 2), PICOSYSTEM_PHYSICS_FIXED_ONE);
	assert(picosystem_physics_world_step(&reverse, &gravity) == 0);
	assert(reverse.bodies[0].velocity_per_tick.x < 0);

	struct picosystem_physics_world frictionless;
	init_conveyor_world(&frictionless, RATIO(1, 2), 0);
	assert(picosystem_physics_world_step(&frictionless, &gravity) == 0);
	assert(frictionless.bodies[0].velocity_per_tick.x == 0);
	assert(frictionless.last_work.conveyor_contact_count == 1U);
	assert(frictionless.last_work.conveyor_solver_changed_count == 0U);

	assert(picosystem_physics_world_set_segment_surface_speed(NULL, 0U, 0) == -EINVAL);
	assert(picosystem_physics_world_set_segment_surface_speed(&forward, 1U, 0) == -ENOENT);
	const uint32_t forward_hash = picosystem_physics_world_hash(&forward);
	assert(picosystem_physics_world_set_segment_surface_speed(&forward, 0U, FIXED(17)) ==
	       -ERANGE);
	assert(picosystem_physics_world_hash(&forward) == forward_hash);
	assert(picosystem_physics_world_set_segment_surface_speed(&forward, 0U, -RATIO(1, 2)) == 0);
	assert(forward.static_segments[0].surface_speed_per_tick == -RATIO(1, 2));
	assert(picosystem_physics_world_hash(&forward) != forward_hash);

	struct picosystem_physics_world sleeping;
	init_conveyor_world(&sleeping, 0, PICOSYSTEM_PHYSICS_FIXED_ONE);
	for (uint32_t tick = 0U; tick < PICOSYSTEM_PHYSICS_SLEEP_QUIET_TICKS; ++tick) {
		assert(picosystem_physics_world_step(&sleeping, &gravity) == 0);
	}
	assert(picosystem_physics_world_body_is_sleeping(&sleeping, 0U));
	assert(picosystem_physics_world_set_segment_surface_speed(&sleeping, 0U, RATIO(1, 2)) == 0);
	assert(!picosystem_physics_world_body_is_sleeping(&sleeping, 0U));
	for (uint32_t tick = 0U; tick < PICOSYSTEM_PHYSICS_SLEEP_QUIET_TICKS + 4U; ++tick) {
		assert(picosystem_physics_world_step(&sleeping, &gravity) == 0);
		assert(!picosystem_physics_world_body_is_sleeping(&sleeping, 0U));
	}

	struct picosystem_physics_world grid;
	init_conveyor_world(&grid, RATIO(1, 2), PICOSYSTEM_PHYSICS_FIXED_ONE);
	struct picosystem_physics_world reference = grid;
	for (uint32_t tick = 0U; tick < 24U; ++tick) {
		assert(picosystem_physics_world_step(&grid, &gravity) == 0);
		assert(picosystem_physics_world_step_reference(&reference, &gravity) == 0);
		assert_step_matches_reference(&grid, &reference);
	}
}

static void test_sleep_boundary_and_acceleration_wake(void)
{
	struct picosystem_physics_world world;
	init_world(&world, FIXED(2));
	const struct picosystem_physics_circle_config body = circle_config(1U, 10, 20, 2);
	assert(picosystem_physics_world_add_circle(&world, &body) == 0);
	assert(!picosystem_physics_world_body_is_sleeping(NULL, 0U));
	assert(!picosystem_physics_world_body_is_sleeping(&world, 1U));
	assert(picosystem_physics_world_wake_body(NULL, 0U) == -EINVAL);
	assert(picosystem_physics_world_wake_body(&world, 1U) == -ENOENT);

	step_without_acceleration(&world, PICOSYSTEM_PHYSICS_SLEEP_QUIET_TICKS - 1U);
	assert(!picosystem_physics_world_body_is_sleeping(&world, 0U));
	assert(world.sleep_quiet_tick_counts[0] == PICOSYSTEM_PHYSICS_SLEEP_QUIET_TICKS - 1U);
	assert(world.last_work.awake_body_count == 1U);
	assert(world.last_work.sleeping_body_count == 0U);

	assert(picosystem_physics_world_step(&world, &no_acceleration) == 0);
	assert(picosystem_physics_world_body_is_sleeping(&world, 0U));
	assert(world.sleep_quiet_tick_counts[0] == PICOSYSTEM_PHYSICS_SLEEP_QUIET_TICKS);
	assert(world.last_work.body_sleep_transition_count == 1U);
	assert(world.last_work.awake_body_count == 0U);
	assert(world.last_work.sleeping_body_count == 1U);
	const struct picosystem_physics_vector sleeping_center = world.bodies[0].center;

	assert(picosystem_physics_world_step(&world, &no_acceleration) == 0);
	assert(picosystem_physics_world_body_is_sleeping(&world, 0U));
	assert_vector_equal(&world.bodies[0].center, &sleeping_center);
	assert(world.last_work.body_sleep_transition_count == 0U);
	assert(world.last_work.body_wake_transition_count == 0U);
	assert(world.last_solver_iteration_count == 0U);

	const struct picosystem_physics_vector acceleration = {.x = RATIO(1, 16)};
	assert(picosystem_physics_world_step(&world, &acceleration) == 0);
	assert(!picosystem_physics_world_body_is_sleeping(&world, 0U));
	assert(world.last_work.body_wake_transition_count == 1U);
	assert(world.sleep_quiet_tick_counts[0] == 0U);
	assert(world.bodies[0].velocity_per_tick.x == acceleration.x);
	assert(world.bodies[0].center.x == sleeping_center.x + acceleration.x);
	assert_vector_equal(&world.last_global_acceleration_per_tick, &acceleration);

	struct picosystem_physics_world corrupt = world;
	corrupt.sleep_quiet_tick_counts[0] = PICOSYSTEM_PHYSICS_SLEEP_QUIET_TICKS;
	const struct picosystem_physics_world unchanged = corrupt;
	assert(picosystem_physics_world_step(&corrupt, &acceleration) == -ERANGE);
	assert(memcmp(&corrupt, &unchanged, sizeof(corrupt)) == 0);
}

static void test_sleep_islands_and_motor_exclusion(void)
{
	struct picosystem_physics_world island;
	init_world(&island, FIXED(2));
	const struct picosystem_physics_circle_config left = circle_config(1U, 0, 0, 1);
	const struct picosystem_physics_circle_config right = circle_config(2U, 4, 0, 1);
	assert(picosystem_physics_world_add_circle(&island, &left) == 0);
	assert(picosystem_physics_world_add_circle(&island, &right) == 0);
	const struct picosystem_physics_distance_joint_config joint =
		distance_joint_config(101U, 1U, 2U, 4);
	assert(picosystem_physics_world_add_distance_joint(&island, &joint) == 0);
	step_without_acceleration(&island, PICOSYSTEM_PHYSICS_SLEEP_QUIET_TICKS);
	assert(picosystem_physics_world_body_is_sleeping(&island, 0U));
	assert(picosystem_physics_world_body_is_sleeping(&island, 1U));
	assert(island.last_work.body_sleep_transition_count == 2U);

	assert(picosystem_physics_world_step(&island, &no_acceleration) == 0);
	assert(island.last_work.sleeping_joint_count == 1U);
	assert(island.last_work.joint_solver_visit_count == 0U);
	assert(island.last_solver_iteration_count == 0U);
	assert(picosystem_physics_world_wake_body(&island, 0U) == 0);
	assert(!picosystem_physics_world_body_is_sleeping(&island, 0U));
	assert(picosystem_physics_world_body_is_sleeping(&island, 1U));
	assert(picosystem_physics_world_step(&island, &no_acceleration) == 0);
	assert(!picosystem_physics_world_body_is_sleeping(&island, 0U));
	assert(!picosystem_physics_world_body_is_sleeping(&island, 1U));
	assert(island.last_work.body_wake_transition_count == 1U);
	assert(island.sleep_quiet_tick_counts[0] == 1U);
	assert(island.sleep_quiet_tick_counts[1] == 1U);

	struct picosystem_physics_world motor;
	init_world(&motor, FIXED(2));
	const struct picosystem_physics_circle_config rotor = circle_config(1U, 0, 0, 1);
	assert(picosystem_physics_world_add_circle(&motor, &rotor) == 0);
	struct picosystem_physics_revolute_joint_config motor_joint =
		revolute_joint_config(201U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID);
	motor_joint.maximum_motor_impulse_per_tick = RATIO(1, 4);
	motor_joint.motor_enabled = 1U;
	assert(picosystem_physics_world_add_revolute_joint(&motor, &motor_joint) == 0);
	step_without_acceleration(&motor, PICOSYSTEM_PHYSICS_SLEEP_QUIET_TICKS + 10U);
	assert(!picosystem_physics_world_body_is_sleeping(&motor, 0U));
	assert(motor.sleep_quiet_tick_counts[0] == 0U);
	assert(motor.last_work.awake_body_count == 1U);
}

static void test_contact_wake_and_sleeping_sensor_lifecycle(void)
{
	struct picosystem_physics_world collision;
	init_world(&collision, FIXED(4));
	const struct picosystem_physics_circle_config target = circle_config(1U, 0, 0, 1);
	const struct picosystem_physics_circle_config projectile = circle_config(2U, 5, 0, 1);
	assert(picosystem_physics_world_add_circle(&collision, &target) == 0);
	assert(picosystem_physics_world_add_circle(&collision, &projectile) == 0);
	step_without_acceleration(&collision, PICOSYSTEM_PHYSICS_SLEEP_QUIET_TICKS);
	assert(collision.sleeping_body_mask == UINT16_C(3));
	assert(picosystem_physics_world_wake_body(&collision, 1U) == 0);
	collision.bodies[1].velocity_per_tick.x = -FIXED(4);
	assert(picosystem_physics_world_step(&collision, &no_acceleration) == 0);
	assert(collision.contact_count > 0U);
	assert(!picosystem_physics_world_body_is_sleeping(&collision, 0U));
	assert(!picosystem_physics_world_body_is_sleeping(&collision, 1U));
	assert(collision.last_work.body_wake_transition_count == 1U);

	struct picosystem_physics_world sensor_world;
	init_world(&sensor_world, FIXED(2));
	const struct picosystem_physics_circle_config observed = circle_config(1U, 0, 0, 1);
	const struct picosystem_physics_box_sensor_config sensor =
		box_sensor_config(101U, 0, 0, 4, 4);
	assert(picosystem_physics_world_add_circle(&sensor_world, &observed) == 0);
	assert(picosystem_physics_world_add_box_sensor(&sensor_world, &sensor) == 0);
	step_without_acceleration(&sensor_world, PICOSYSTEM_PHYSICS_SLEEP_QUIET_TICKS);
	assert(picosystem_physics_world_body_is_sleeping(&sensor_world, 0U));
	assert(sensor_world.contact_event_count == 1U);
	assert_contact_event(&sensor_world, 0U, 1U, 101U,
			     PICOSYSTEM_PHYSICS_CONTACT_EVENT_BODY_BOX_SENSOR,
			     PICOSYSTEM_PHYSICS_CONTACT_EVENT_STAY);
	assert(picosystem_physics_world_step(&sensor_world, &no_acceleration) == 0);
	assert(picosystem_physics_world_body_is_sleeping(&sensor_world, 0U));
	assert(sensor_world.last_work.body_wake_transition_count == 0U);
	assert(sensor_world.last_work.sensor_overlap_count == 1U);
	assert(sensor_world.last_work.contact_stay_event_count == 1U);
	assert_contact_event(&sensor_world, 0U, 1U, 101U,
			     PICOSYSTEM_PHYSICS_CONTACT_EVENT_BODY_BOX_SENSOR,
			     PICOSYSTEM_PHYSICS_CONTACT_EVENT_STAY);
}

static void test_hash_excludes_scratch_and_diagnostics(void)
{
	struct picosystem_physics_world world;
	init_world(&world, FIXED(2));
	const struct picosystem_physics_circle_config body = circle_config(1U, 0, 0, 1);
	assert(picosystem_physics_world_add_circle(&world, &body) == 0);
	const struct picosystem_physics_distance_joint_config joint =
		spring_joint_config(101U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID, 1);
	assert(picosystem_physics_world_add_distance_joint(&world, &joint) == 0);
	struct picosystem_physics_segment_config segment = horizontal_segment(501U, 10);
	segment.surface_speed_per_tick = RATIO(1, 2);
	assert(picosystem_physics_world_add_static_segment(&world, &segment) == 0);
	struct picosystem_physics_revolute_joint_config revolute_joint =
		revolute_joint_config(201U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID);
	revolute_joint.motor_speed_per_tick = RATIO(1, 64);
	revolute_joint.maximum_motor_impulse_per_tick = RATIO(1, 4);
	revolute_joint.lower_angle_radians = -RATIO(1, 2);
	revolute_joint.upper_angle_radians = RATIO(1, 2);
	revolute_joint.motor_enabled = 1U;
	revolute_joint.limit_enabled = 1U;
	assert(picosystem_physics_world_add_revolute_joint(&world, &revolute_joint) == 0);
	struct picosystem_physics_prismatic_joint_config prismatic_joint =
		prismatic_joint_config(301U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID);
	prismatic_joint.motor_speed_per_tick = RATIO(1, 8);
	prismatic_joint.maximum_motor_impulse_per_tick = RATIO(1, 4);
	prismatic_joint.lower_translation = -FIXED(1);
	prismatic_joint.upper_translation = FIXED(1);
	prismatic_joint.motor_enabled = 1U;
	prismatic_joint.limit_enabled = 1U;
	assert(picosystem_physics_world_add_prismatic_joint(&world, &prismatic_joint) == 0);
	const struct picosystem_physics_box_sensor_config sensor =
		box_sensor_config(401U, 20, 20, 3, 4);
	assert(picosystem_physics_world_add_box_sensor(&world, &sensor) == 0);
	const struct picosystem_physics_rope_config rope = rope_config(601U, 30, 0, 36, 0, 4U, 2);
	assert(picosystem_physics_world_add_rope(&world, &rope) == 0);
	const uint32_t expected = picosystem_physics_world_hash(&world);

	world.last_candidate_pair_count = UINT32_MAX;
	world.last_possible_pair_count = UINT32_MAX;
	world.last_occupied_grid_cell_count = UINT16_MAX;
	world.last_broad_phase_fallback = UINT8_MAX;
	world.last_solver_iteration_count = UINT8_MAX;
	memset(&world.last_work, UINT8_MAX, sizeof(world.last_work));
	world.grid_cells[0].body_mask = UINT16_MAX;
	world.grid_cells[0].static_segment_mask = UINT8_MAX;
	world.grid_cells[0].box_sensor_mask = UINT8_MAX;
	world.solver_velocity_revisions[0] = UINT16_MAX;
	world.contact_count = 1U;
	world.contacts[0].penetration = INT32_MAX;
	world.contacts[0].solved_velocity_revision_a = UINT16_MAX;
	world.contacts[0].solved_velocity_revision_b = UINT16_MAX;
	world.contacts[0].solved_velocity_valid = UINT8_MAX;
	world.contact_event_count = 1U;
	world.contact_events[0] = (struct picosystem_physics_contact_event){
		.body_a_id = UINT16_MAX,
		.body_b_id = UINT16_MAX,
		.type = UINT8_MAX,
		.phase = UINT8_MAX,
	};
	world.distance_joints[0].world_anchor_a.x = INT32_MAX;
	world.distance_joints[0].world_anchor_b.y = INT32_MIN;
	world.distance_joints[0].normal.x = INT32_MAX;
	world.distance_joints[0].direction_inverse_mass = INT32_MAX;
	world.distance_joints[0].accumulated_impulse = INT32_MIN;
	world.distance_joints[0].spring_softness = INT32_MAX;
	world.distance_joints[0].spring_bias_velocity = INT32_MIN;
	world.revolute_joints[0].world_anchor_a.x = INT32_MAX;
	world.revolute_joints[0].world_anchor_b.y = INT32_MIN;
	world.revolute_joints[0].effective_mass_xx = INT32_MAX;
	world.revolute_joints[0].effective_mass_xy = INT32_MIN;
	world.revolute_joints[0].effective_mass_yy = INT32_MAX;
	world.revolute_joints[0].angular_effective_mass = INT32_MAX;
	world.revolute_joints[0].accumulated_impulse.x = INT32_MIN;
	world.revolute_joints[0].accumulated_motor_impulse = INT32_MIN;
	world.revolute_joints[0].accumulated_limit_impulse = INT32_MAX;
	world.revolute_joints[0].effective_mass_valid = UINT8_MAX;
	world.revolute_joints[0].limit_state = UINT8_MAX;
	world.prismatic_joints[0].world_anchor_a.x = INT32_MAX;
	world.prismatic_joints[0].world_anchor_b.y = INT32_MIN;
	world.prismatic_joints[0].world_axis.x = INT32_MAX;
	world.prismatic_joints[0].world_perpendicular.y = INT32_MIN;
	world.prismatic_joints[0].lateral_effective_mass = INT32_MAX;
	world.prismatic_joints[0].axial_effective_mass = INT32_MIN;
	world.prismatic_joints[0].angular_effective_mass = INT32_MAX;
	world.prismatic_joints[0].accumulated_lateral_impulse = INT32_MIN;
	world.prismatic_joints[0].accumulated_angular_impulse = INT32_MAX;
	world.prismatic_joints[0].accumulated_motor_impulse = INT32_MIN;
	world.prismatic_joints[0].accumulated_limit_impulse = INT32_MAX;
	world.prismatic_joints[0].solved_velocity_revision_a = UINT16_MAX;
	world.prismatic_joints[0].solved_velocity_revision_b = UINT16_MAX;
	world.prismatic_joints[0].limit_state = UINT8_MAX;
	world.prismatic_joints[0].solved_velocity_valid = UINT8_MAX;
	assert(picosystem_physics_world_hash(&world) == expected);
	struct picosystem_physics_world changed = world;
	changed.distance_joints[0].target_distance += 1;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.distance_joints[0].spring_angular_frequency_per_tick += 1;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.distance_joints[0].spring_damping_ratio += 1;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.distance_joints[0].maximum_spring_impulse_per_tick += 1;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.distance_joints[0].spring_enabled = 0U;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.distance_joint_count = 0U;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.static_segments[0].surface_speed_per_tick += 1;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.revolute_joints[0].anchor_b.x += 1;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.revolute_joints[0].collide_connected = 1U;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.revolute_joints[0].motor_speed_per_tick += 1;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.revolute_joints[0].maximum_motor_impulse_per_tick += 1;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.revolute_joints[0].lower_angle_radians += 1;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.revolute_joints[0].upper_angle_radians -= 1;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.revolute_joints[0].reference_angle_turns += 1U;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.revolute_joints[0].motor_enabled = 0U;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.revolute_joints[0].limit_enabled = 0U;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.revolute_joint_count = 0U;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.prismatic_joints[0].axis_b.y += 1;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.prismatic_joints[0].motor_speed_per_tick += 1;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.prismatic_joints[0].maximum_motor_impulse_per_tick += 1;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.prismatic_joints[0].lower_translation += 1;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.prismatic_joints[0].upper_translation -= 1;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.prismatic_joints[0].reference_translation += 1;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.prismatic_joints[0].reference_angle_turns += 1U;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.prismatic_joints[0].collide_connected = 1U;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.prismatic_joints[0].motor_enabled = 0U;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.prismatic_joints[0].limit_enabled = 0U;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.prismatic_joint_count = 0U;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.box_sensors[0].center.x += 1;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.box_sensors[0].half_extent.y += 1;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.box_sensor_count = 0U;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.ropes[0].anchor_a.x += 1;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.ropes[0].segment_length += 1;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.ropes[0].pin_a = 1U;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.ropes[0].particles[1].position.y += 1;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.ropes[0].particles[1].previous_position.y += 1;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.rope_count = 0U;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.active_sensor_contact_masks[0] = UINT8_C(1);
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.sleeping_body_mask = UINT16_C(1);
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.sleep_quiet_tick_counts[0] = 1U;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.last_global_acceleration_per_tick.x = 1;
	assert(picosystem_physics_world_hash(&changed) != expected);
	assert(picosystem_physics_world_hash(NULL) == 0U);
	assert(picosystem_physics_world_body_at(&world, 0U) == &world.bodies[0]);
	assert(picosystem_physics_world_body_at(&world, 1U) == NULL);
	assert(picosystem_physics_world_body_at(NULL, 0U) == NULL);
	world.body_count = PICOSYSTEM_PHYSICS_MAX_BODIES + 1U;
	assert(picosystem_physics_world_hash(&world) == 0U);
	assert(picosystem_physics_world_body_at(&world, 0U) == NULL);
	world.body_count = 1U;
	world.distance_joint_count = PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS + 1U;
	assert(picosystem_physics_world_hash(&world) == 0U);
	world.distance_joint_count = 1U;
	world.revolute_joint_count = PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS + 1U;
	assert(picosystem_physics_world_hash(&world) == 0U);
	world.revolute_joint_count = 1U;
	world.prismatic_joint_count = PICOSYSTEM_PHYSICS_MAX_PRISMATIC_JOINTS + 1U;
	assert(picosystem_physics_world_hash(&world) == 0U);
	world.prismatic_joint_count = 1U;
	world.box_sensor_count = PICOSYSTEM_PHYSICS_MAX_BOX_SENSORS + 1U;
	assert(picosystem_physics_world_hash(&world) == 0U);
	world.box_sensor_count = 1U;
	world.rope_count = PICOSYSTEM_PHYSICS_MAX_ROPES + 1U;
	assert(picosystem_physics_world_hash(&world) == 0U);
	world.rope_count = 1U;
	world.ropes[0].particle_count = 1U;
	assert(picosystem_physics_world_hash(&world) == 0U);
	world.ropes[0].particle_count = PICOSYSTEM_PHYSICS_MAX_ROPE_PARTICLES + 1U;
	assert(picosystem_physics_world_hash(&world) == 0U);
}

int main(void)
{
	test_initialization_and_add_boundaries();
	test_capsule_boundaries_and_geometry();
	test_rope_boundaries_dynamics_and_reference();
	test_rope_body_reaction_and_sleep_policy();
	test_rope_particle_collision();
	test_duplicate_ids_and_invalid_segments();
	test_sensor_overlap_and_contact_event_lifecycle();
	test_exact_circle_and_rotated_box_sensor_overlap();
	test_distance_joint_boundaries_and_endpoints();
	test_distance_joint_dynamics();
	test_revolute_joint_boundaries_and_anchors();
	test_revolute_joint_dynamics_and_multilink_chain();
	test_revolute_joint_motor_and_limits();
	test_revolute_joint_connected_collision_policy();
	test_prismatic_joint_boundaries_and_queries();
	test_prismatic_joint_dynamics_motor_and_limits();
	test_prismatic_joint_connected_collision_policy();
	test_integration_speed_clamp_and_invalid_step();
	test_box_geometry_and_angular_integration();
	test_equal_mass_head_on_collision();
	test_unequal_mass_head_on_collision();
	test_static_floor_and_diagonal_segment();
	test_box_floor_manifold_and_off_center_torque();
	test_box_box_and_circle_box_collisions();
	test_capsule_collisions_and_sensor_overlap();
	test_coincident_centers_are_stable();
	test_uniform_grid_filter_and_fallback();
	test_profiled_step_and_reference_work();
	test_uniform_grid_matches_brute_force_oracle();
	test_contact_storage_covers_all_candidates();
	test_spring_boundaries_and_setter();
	test_spring_dynamics_sleep_and_reference();
	test_conveyor_direction_setter_sleep_and_reference();
	test_sleep_boundary_and_acceleration_wake();
	test_sleep_islands_and_motor_exclusion();
	test_contact_wake_and_sleeping_sensor_lifecycle();
	test_hash_excludes_scratch_and_diagnostics();
	puts("physics-world tests passed");
	return 0;
}
