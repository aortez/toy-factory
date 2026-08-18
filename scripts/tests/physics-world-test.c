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
	assert(left->body_a_index == right->body_a_index);
	assert(left->body_b_index == right->body_b_index);
	assert(left->segment_index == right->segment_index);
	assert(left->type == right->type);
}

static void assert_distance_joint_equal(const struct picosystem_physics_distance_joint *left,
					const struct picosystem_physics_distance_joint *right)
{
	assert_vector_equal(&left->local_anchor_a, &right->local_anchor_a);
	assert_vector_equal(&left->anchor_b, &right->anchor_b);
	assert(left->target_distance == right->target_distance);
	assert(left->id == right->id);
	assert(left->body_a_id == right->body_a_id);
	assert(left->body_b_id == right->body_b_id);
	assert(left->body_a_index == right->body_a_index);
	assert(left->body_b_index == right->body_b_index);
	assert_vector_equal(&left->world_anchor_a, &right->world_anchor_a);
	assert_vector_equal(&left->world_anchor_b, &right->world_anchor_b);
	assert_vector_equal(&left->normal, &right->normal);
	assert(left->direction_inverse_mass == right->direction_inverse_mass);
	assert(left->accumulated_impulse == right->accumulated_impulse);
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
	assert(grid->contact_count == reference->contact_count);
	assert(grid->last_possible_pair_count == reference->last_possible_pair_count);
	assert(reference->last_candidate_pair_count == reference->last_possible_pair_count);
	assert(grid->last_solver_iteration_count == reference->last_solver_iteration_count);
	assert(grid->last_work.possible_pair_count == reference->last_work.possible_pair_count);
	assert(grid->last_work.candidate_pair_count == grid->last_candidate_pair_count);
	assert(reference->last_work.candidate_pair_count ==
	       reference->last_work.possible_pair_count);
	assert(grid->last_work.body_body_narrow_phase_test_count +
		       grid->last_work.body_segment_narrow_phase_test_count ==
	       grid->last_work.candidate_pair_count);
	assert(reference->last_work.body_body_narrow_phase_test_count +
		       reference->last_work.body_segment_narrow_phase_test_count ==
	       reference->last_work.candidate_pair_count);
	assert(grid->last_work.manifold_count == reference->last_work.manifold_count);
	assert(grid->last_work.contact_point_count == reference->last_work.contact_point_count);
	assert(grid->last_work.position_correction_visit_count ==
	       reference->last_work.position_correction_visit_count);
	assert(grid->last_work.solver_iteration_count ==
	       reference->last_work.solver_iteration_count);
	assert(grid->last_work.solver_contact_visit_count ==
	       reference->last_work.solver_contact_visit_count);
	assert(grid->last_work.solver_changed_contact_count ==
	       reference->last_work.solver_changed_contact_count);
	assert(grid->last_work.distance_joint_count == reference->last_work.distance_joint_count);
	assert(grid->last_work.joint_position_correction_visit_count ==
	       reference->last_work.joint_position_correction_visit_count);
	assert(grid->last_work.joint_solver_visit_count ==
	       reference->last_work.joint_solver_visit_count);
	assert(grid->last_work.joint_solver_changed_count ==
	       reference->last_work.joint_solver_changed_count);
	assert(reference->last_work.broad_phase_fallback_count == 0U);
	assert(picosystem_physics_world_hash(grid) == picosystem_physics_world_hash(reference));

	for (uint16_t index = 0U; index < grid->body_count; ++index) {
		assert_body_equal(&grid->bodies[index], &reference->bodies[index]);
	}
	for (uint16_t index = 0U; index < grid->contact_count; ++index) {
		assert_contact_equal(&grid->contacts[index], &reference->contacts[index]);
	}
	for (uint16_t index = 0U; index < grid->distance_joint_count; ++index) {
		assert_distance_joint_equal(&grid->distance_joints[index],
					    &reference->distance_joints[index]);
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
	assert(picosystem_physics_world_add_static_segment(NULL, NULL) == -EINVAL);

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
	assert(world.static_segment_count == 1U);

	world.static_segments[0].normal.x = PICOSYSTEM_PHYSICS_FIXED_ONE;
	world.static_segments[0].normal.y = 0;
	assert(picosystem_physics_world_step(&world, &no_acceleration) == -ERANGE);
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
		if ((index % 2U) == 0U) {
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

	assert(picosystem_physics_world_step(&world, &no_acceleration) == 0);
	assert(world.last_candidate_pair_count == PICOSYSTEM_PHYSICS_MAX_CANDIDATE_PAIRS);
	assert(world.contact_count == PICOSYSTEM_PHYSICS_MAX_CANDIDATE_PAIRS);
}

static void test_hash_excludes_scratch_and_diagnostics(void)
{
	struct picosystem_physics_world world;
	init_world(&world, FIXED(2));
	const struct picosystem_physics_circle_config body = circle_config(1U, 0, 0, 1);
	assert(picosystem_physics_world_add_circle(&world, &body) == 0);
	const struct picosystem_physics_distance_joint_config joint =
		distance_joint_config(101U, 1U, PICOSYSTEM_PHYSICS_WORLD_BODY_ID, 1);
	assert(picosystem_physics_world_add_distance_joint(&world, &joint) == 0);
	const uint32_t expected = picosystem_physics_world_hash(&world);

	world.last_candidate_pair_count = UINT32_MAX;
	world.last_possible_pair_count = UINT32_MAX;
	world.last_occupied_grid_cell_count = UINT16_MAX;
	world.last_broad_phase_fallback = UINT8_MAX;
	world.last_solver_iteration_count = UINT8_MAX;
	memset(&world.last_work, UINT8_MAX, sizeof(world.last_work));
	world.grid_cells[0].body_mask = UINT16_MAX;
	world.grid_cells[0].static_segment_mask = UINT8_MAX;
	world.contact_count = 1U;
	world.contacts[0].penetration = INT32_MAX;
	world.distance_joints[0].world_anchor_a.x = INT32_MAX;
	world.distance_joints[0].world_anchor_b.y = INT32_MIN;
	world.distance_joints[0].normal.x = INT32_MAX;
	world.distance_joints[0].direction_inverse_mass = INT32_MAX;
	world.distance_joints[0].accumulated_impulse = INT32_MIN;
	assert(picosystem_physics_world_hash(&world) == expected);
	struct picosystem_physics_world changed = world;
	changed.distance_joints[0].target_distance += 1;
	assert(picosystem_physics_world_hash(&changed) != expected);
	changed = world;
	changed.distance_joint_count = 0U;
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
}

int main(void)
{
	test_initialization_and_add_boundaries();
	test_duplicate_ids_and_invalid_segments();
	test_distance_joint_boundaries_and_endpoints();
	test_distance_joint_dynamics();
	test_integration_speed_clamp_and_invalid_step();
	test_box_geometry_and_angular_integration();
	test_equal_mass_head_on_collision();
	test_unequal_mass_head_on_collision();
	test_static_floor_and_diagonal_segment();
	test_box_floor_manifold_and_off_center_torque();
	test_box_box_and_circle_box_collisions();
	test_coincident_centers_are_stable();
	test_uniform_grid_filter_and_fallback();
	test_profiled_step_and_reference_work();
	test_uniform_grid_matches_brute_force_oracle();
	test_contact_storage_covers_all_candidates();
	test_hash_excludes_scratch_and_diagnostics();
	puts("physics-world tests passed");
	return 0;
}
