/* SPDX-License-Identifier: Apache-2.0 */

#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

#include "game_world.h"

#define EXPECTED_RESET_HASH          UINT32_C(0xbe490990)
#define EXPECTED_RIGHT_30_HASH       UINT32_C(0xf110b9f9)
#define EXPECTED_RIGHT_30_UP_15_HASH UINT32_C(0x62c9b14e)
#define EXPECTED_REPLAY_10000_HASH   UINT32_C(0xc79cc506)
#define BOUNDARY_TOLERANCE           PICOSYSTEM_PHYSICS_FIXED_FROM_INT(3)

static void assert_vector_equal(const struct picosystem_physics_vector *left,
				const struct picosystem_physics_vector *right)
{
	assert(left->x == right->x);
	assert(left->y == right->y);
}

static void assert_world_equal(const struct picosystem_game_world *left,
			       const struct picosystem_game_world *right)
{
	assert(left->logic_tick_count == right->logic_tick_count);
	assert(left->physics.max_speed_per_tick == right->physics.max_speed_per_tick);
	assert(left->physics.body_count == right->physics.body_count);
	assert(left->physics.static_segment_count == right->physics.static_segment_count);
	assert(left->physics.distance_joint_count == right->physics.distance_joint_count);
	assert(left->physics.revolute_joint_count == right->physics.revolute_joint_count);
	assert(left->physics.contact_count == right->physics.contact_count);
	assert(left->physics.last_candidate_pair_count == right->physics.last_candidate_pair_count);
	assert(left->physics.last_possible_pair_count == right->physics.last_possible_pair_count);
	assert(left->physics.last_occupied_grid_cell_count ==
	       right->physics.last_occupied_grid_cell_count);
	assert(left->physics.last_broad_phase_fallback == right->physics.last_broad_phase_fallback);
	assert(left->physics.last_solver_iteration_count ==
	       right->physics.last_solver_iteration_count);
	for (size_t index = 0U; index < PICOSYSTEM_PHYSICS_GRID_CELL_COUNT; ++index) {
		assert(left->physics.grid_cells[index].body_mask ==
		       right->physics.grid_cells[index].body_mask);
		assert(left->physics.grid_cells[index].static_segment_mask ==
		       right->physics.grid_cells[index].static_segment_mask);
	}

	for (uint16_t index = 0U; index < left->physics.body_count; ++index) {
		const struct picosystem_physics_body *const left_body =
			&left->physics.bodies[index];
		const struct picosystem_physics_body *const right_body =
			&right->physics.bodies[index];
		assert_vector_equal(&left_body->center, &right_body->center);
		assert_vector_equal(&left_body->velocity_per_tick, &right_body->velocity_per_tick);
		assert_vector_equal(&left_body->half_extent, &right_body->half_extent);
		assert(left_body->radius == right_body->radius);
		assert(left_body->inverse_mass == right_body->inverse_mass);
		assert(left_body->inverse_inertia == right_body->inverse_inertia);
		assert(left_body->restitution == right_body->restitution);
		assert(left_body->friction == right_body->friction);
		assert(left_body->angular_velocity_per_tick ==
		       right_body->angular_velocity_per_tick);
		assert(left_body->angle_turns == right_body->angle_turns);
		assert(left_body->id == right_body->id);
		assert(left_body->shape == right_body->shape);
	}

	for (uint16_t index = 0U; index < left->physics.static_segment_count; ++index) {
		const struct picosystem_physics_static_segment *const left_segment =
			&left->physics.static_segments[index];
		const struct picosystem_physics_static_segment *const right_segment =
			&right->physics.static_segments[index];
		assert_vector_equal(&left_segment->start, &right_segment->start);
		assert_vector_equal(&left_segment->end, &right_segment->end);
		assert_vector_equal(&left_segment->normal, &right_segment->normal);
		assert(left_segment->restitution == right_segment->restitution);
		assert(left_segment->friction == right_segment->friction);
		assert(left_segment->id == right_segment->id);
	}

	for (uint16_t index = 0U; index < left->physics.distance_joint_count; ++index) {
		const struct picosystem_physics_distance_joint *const left_joint =
			&left->physics.distance_joints[index];
		const struct picosystem_physics_distance_joint *const right_joint =
			&right->physics.distance_joints[index];
		assert_vector_equal(&left_joint->local_anchor_a, &right_joint->local_anchor_a);
		assert_vector_equal(&left_joint->anchor_b, &right_joint->anchor_b);
		assert(left_joint->target_distance == right_joint->target_distance);
		assert(left_joint->id == right_joint->id);
		assert(left_joint->body_a_id == right_joint->body_a_id);
		assert(left_joint->body_b_id == right_joint->body_b_id);
		assert(left_joint->body_a_index == right_joint->body_a_index);
		assert(left_joint->body_b_index == right_joint->body_b_index);
		assert_vector_equal(&left_joint->world_anchor_a, &right_joint->world_anchor_a);
		assert_vector_equal(&left_joint->world_anchor_b, &right_joint->world_anchor_b);
		assert_vector_equal(&left_joint->normal, &right_joint->normal);
		assert(left_joint->direction_inverse_mass == right_joint->direction_inverse_mass);
		assert(left_joint->accumulated_impulse == right_joint->accumulated_impulse);
	}

	for (uint16_t index = 0U; index < left->physics.revolute_joint_count; ++index) {
		const struct picosystem_physics_revolute_joint *const left_joint =
			&left->physics.revolute_joints[index];
		const struct picosystem_physics_revolute_joint *const right_joint =
			&right->physics.revolute_joints[index];
		assert_vector_equal(&left_joint->local_anchor_a, &right_joint->local_anchor_a);
		assert_vector_equal(&left_joint->anchor_b, &right_joint->anchor_b);
		assert(left_joint->id == right_joint->id);
		assert(left_joint->body_a_id == right_joint->body_a_id);
		assert(left_joint->body_b_id == right_joint->body_b_id);
		assert(left_joint->body_a_index == right_joint->body_a_index);
		assert(left_joint->body_b_index == right_joint->body_b_index);
		assert(left_joint->collide_connected == right_joint->collide_connected);
		assert_vector_equal(&left_joint->world_anchor_a, &right_joint->world_anchor_a);
		assert_vector_equal(&left_joint->world_anchor_b, &right_joint->world_anchor_b);
		assert_vector_equal(&left_joint->accumulated_impulse,
				    &right_joint->accumulated_impulse);
		assert(left_joint->effective_mass_xx == right_joint->effective_mass_xx);
		assert(left_joint->effective_mass_xy == right_joint->effective_mass_xy);
		assert(left_joint->effective_mass_yy == right_joint->effective_mass_yy);
		assert(left_joint->effective_mass_valid == right_joint->effective_mass_valid);
	}
}

static void assert_hash(const char *label, uint32_t actual, uint32_t expected)
{
	if (actual != expected) {
		fprintf(stderr, "%s hash: %08x\n", label, actual);
	}
	assert(actual == expected);
}

static void step_many(struct picosystem_game_world *world,
		      const struct picosystem_game_input *input, uint32_t count)
{
	for (uint32_t step = 0U; step < count; ++step) {
		assert(picosystem_game_world_step(world, input) == 0);
	}
}

static void test_canonical_reset_and_golden_replay(void)
{
	struct picosystem_game_world world;
	assert(picosystem_game_world_reset(&world) == 0);
	assert(world.logic_tick_count == 0U);
	assert(world.physics.body_count == PICOSYSTEM_GAME_BODY_COUNT);
	assert(world.physics.static_segment_count == PICOSYSTEM_GAME_STATIC_SEGMENT_COUNT);
	assert(world.physics.distance_joint_count == PICOSYSTEM_GAME_DISTANCE_JOINT_COUNT);
	assert(world.physics.revolute_joint_count == PICOSYSTEM_GAME_REVOLUTE_JOINT_COUNT);
	assert(world.physics.contact_count == 0U);

	const struct picosystem_physics_body *const focus =
		picosystem_game_world_focus_body(&world);
	assert(focus != NULL);
	assert(focus->id == 1U);
	assert(focus->center.x == PICOSYSTEM_PHYSICS_FIXED_FROM_INT(55));
	assert(focus->center.y == PICOSYSTEM_PHYSICS_FIXED_FROM_INT(55));
	assert(focus->shape == PICOSYSTEM_PHYSICS_SHAPE_BOX);
	assert(focus->half_extent.x == PICOSYSTEM_PHYSICS_FIXED_FROM_INT(10));
	assert(focus->half_extent.y == PICOSYSTEM_PHYSICS_FIXED_FROM_INT(7));
	assert_hash("reset", picosystem_game_world_hash(&world), EXPECTED_RESET_HASH);

	const struct picosystem_game_input right = {.horizontal = 1};
	step_many(&world, &right, 30U);
	assert(world.logic_tick_count == 30U);
	assert_hash("right-30", picosystem_game_world_hash(&world), EXPECTED_RIGHT_30_HASH);

	const struct picosystem_game_input up = {.vertical = -1};
	step_many(&world, &up, 15U);
	assert(world.logic_tick_count == 45U);
	assert_hash("right-30-up-15", picosystem_game_world_hash(&world),
		    EXPECTED_RIGHT_30_UP_15_HASH);

	assert(picosystem_game_world_reset(&world) == 0);
	assert_hash("reset-after-replay", picosystem_game_world_hash(&world), EXPECTED_RESET_HASH);
}

static void test_validation_preserves_state(void)
{
	struct picosystem_game_world world;
	assert(picosystem_game_world_reset(&world) == 0);

	const struct picosystem_game_world baseline = world;
	const struct picosystem_game_input invalid_horizontal = {.horizontal = 2};
	assert(picosystem_game_world_step(&world, &invalid_horizontal) == -ERANGE);
	assert_world_equal(&world, &baseline);

	const struct picosystem_game_input invalid_vertical = {.vertical = -2};
	assert(picosystem_game_world_step(&world, &invalid_vertical) == -ERANGE);
	assert_world_equal(&world, &baseline);

	const struct picosystem_game_input neutral = {0};
	world.physics.max_speed_per_tick = 0;
	const struct picosystem_game_world invalid_speed = world;
	assert(picosystem_game_world_step(&world, &neutral) == -ERANGE);
	assert_world_equal(&world, &invalid_speed);

	assert(picosystem_game_world_reset(&world) == 0);
	world.physics.bodies[0].id = 0U;
	const struct picosystem_game_world invalid_id = world;
	assert(picosystem_game_world_step(&world, &neutral) == -ERANGE);
	assert_world_equal(&world, &invalid_id);

	assert(picosystem_game_world_reset(NULL) == -EINVAL);
	assert(picosystem_game_world_step(NULL, &neutral) == -EINVAL);
	assert(picosystem_game_world_step(&world, NULL) == -EINVAL);
	assert(picosystem_game_world_focus_body(NULL) == NULL);
	assert(picosystem_game_world_hash(NULL) == 0U);
	assert(picosystem_game_world_reset(&world) == 0);
	world.physics.body_count = PICOSYSTEM_PHYSICS_MAX_BODIES + 1U;
	assert(picosystem_game_world_hash(&world) == 0U);
	assert(picosystem_game_world_reset(&world) == 0);
	world.physics.distance_joint_count = PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS + 1U;
	assert(picosystem_game_world_hash(&world) == 0U);
	assert(picosystem_game_world_reset(&world) == 0);
	world.physics.revolute_joint_count = PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS + 1U;
	assert(picosystem_game_world_hash(&world) == 0U);
}

static uint64_t vector_distance_squared(const struct picosystem_physics_vector *left,
					const struct picosystem_physics_vector *right)
{
	const int64_t x = (int64_t)right->x - left->x;
	const int64_t y = (int64_t)right->y - left->y;
	return (uint64_t)((x * x) + (y * y));
}

static void assert_joint_lengths_bounded(const struct picosystem_game_world *world)
{
	const int32_t tolerance = PICOSYSTEM_PHYSICS_FIXED_FROM_INT(3);
	for (uint16_t index = 0U; index < world->physics.distance_joint_count; ++index) {
		struct picosystem_physics_vector anchor_a;
		struct picosystem_physics_vector anchor_b;
		assert(picosystem_physics_world_distance_joint_endpoints(
			       &world->physics, index, &anchor_a, &anchor_b) == 0);
		const int32_t target = world->physics.distance_joints[index].target_distance;
		const int64_t minimum = target - tolerance;
		const int64_t maximum = target + tolerance;
		const uint64_t distance_squared = vector_distance_squared(&anchor_a, &anchor_b);
		assert(distance_squared >= (uint64_t)(minimum * minimum));
		assert(distance_squared <= (uint64_t)(maximum * maximum));
	}
	for (uint16_t index = 0U; index < world->physics.revolute_joint_count; ++index) {
		struct picosystem_physics_vector anchor_a;
		struct picosystem_physics_vector anchor_b;
		assert(picosystem_physics_world_revolute_joint_anchors(&world->physics, index,
								       &anchor_a, &anchor_b) == 0);
		const uint64_t distance_squared = vector_distance_squared(&anchor_a, &anchor_b);
		const int64_t revolute_tolerance = BOUNDARY_TOLERANCE;
		assert(distance_squared <= (uint64_t)(revolute_tolerance * revolute_tolerance));
	}
}

static void assert_bodies_inside_arena(const struct picosystem_game_world *world)
{
	const int32_t left =
		PICOSYSTEM_PHYSICS_FIXED_FROM_INT(PICOSYSTEM_GAME_PLAYFIELD_LEFT_PIXELS);
	const int32_t right =
		PICOSYSTEM_PHYSICS_FIXED_FROM_INT(PICOSYSTEM_GAME_PLAYFIELD_RIGHT_PIXELS);
	const int32_t top = PICOSYSTEM_PHYSICS_FIXED_FROM_INT(PICOSYSTEM_GAME_PLAYFIELD_TOP_PIXELS);
	const int32_t bottom =
		PICOSYSTEM_PHYSICS_FIXED_FROM_INT(PICOSYSTEM_GAME_PLAYFIELD_BOTTOM_PIXELS);

	for (uint16_t index = 0U; index < world->physics.body_count; ++index) {
		const struct picosystem_physics_body *const body = &world->physics.bodies[index];
		if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_CIRCLE) {
			assert(body->center.x >= (left + body->radius - BOUNDARY_TOLERANCE));
			assert(body->center.x <= (right - body->radius + BOUNDARY_TOLERANCE));
			assert(body->center.y >= (top + body->radius - BOUNDARY_TOLERANCE));
			assert(body->center.y <= (bottom - body->radius + BOUNDARY_TOLERANCE));
			continue;
		}

		struct picosystem_physics_vector vertices[PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT];
		assert(picosystem_physics_body_box_vertices(body, vertices) == 0);
		for (size_t vertex = 0U; vertex < PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT; ++vertex) {
			if ((vertices[vertex].x < (left - BOUNDARY_TOLERANCE)) ||
			    (vertices[vertex].x > (right + BOUNDARY_TOLERANCE)) ||
			    (vertices[vertex].y < (top - BOUNDARY_TOLERANCE)) ||
			    (vertices[vertex].y > (bottom + BOUNDARY_TOLERANCE))) {
				fprintf(stderr,
					"box %u vertex %u escaped at tick %u: point=(%d,%d)\n",
					index, (unsigned int)vertex, world->logic_tick_count,
					vertices[vertex].x, vertices[vertex].y);
			}
			assert(vertices[vertex].x >= (left - BOUNDARY_TOLERANCE));
			assert(vertices[vertex].x <= (right + BOUNDARY_TOLERANCE));
			assert(vertices[vertex].y >= (top - BOUNDARY_TOLERANCE));
			assert(vertices[vertex].y <= (bottom + BOUNDARY_TOLERANCE));
		}
	}
}

static void test_bounded_motion_contacts_and_saturated_tick(void)
{
	struct picosystem_game_world world;
	assert(picosystem_game_world_reset(&world) == 0);
	const struct picosystem_game_input inputs[] = {
		{0},
		{.horizontal = 1},
		{.vertical = -1},
		{.horizontal = -1, .vertical = 1},
	};
	bool saw_body_contact = false;
	bool saw_static_contact = false;
	bool saw_candidate_reduction = false;
	uint32_t minimum_candidate_count = UINT32_MAX;
	uint32_t maximum_candidate_count = 0U;
	uint16_t maximum_contact_count = 0U;
	uint8_t maximum_solver_iteration_count = 0U;

	for (uint32_t step = 0U; step < 10000U; ++step) {
		const size_t input_index = (step / 250U) % (sizeof(inputs) / sizeof(inputs[0]));
		const int err = picosystem_game_world_step(&world, &inputs[input_index]);
		if (err != 0) {
			fprintf(stderr, "bounded replay failed at step %u: %d\n", step, err);
			for (uint16_t index = 0U; index < world.physics.body_count; ++index) {
				const struct picosystem_physics_body *const body =
					&world.physics.bodies[index];
				fprintf(stderr, "body %u p=(%d,%d) v=(%d,%d)\n", index,
					body->center.x, body->center.y, body->velocity_per_tick.x,
					body->velocity_per_tick.y);
			}
		}
		assert(err == 0);
		assert_bodies_inside_arena(&world);
		assert_joint_lengths_bounded(&world);
		assert(world.physics.last_possible_pair_count == 76U);
		assert(world.physics.last_candidate_pair_count <=
		       world.physics.last_possible_pair_count);
		assert(world.physics.last_occupied_grid_cell_count > 0U);
		assert(world.physics.last_broad_phase_fallback == 0U);
		if (world.physics.last_candidate_pair_count <
		    world.physics.last_possible_pair_count) {
			saw_candidate_reduction = true;
		}
		if (world.physics.last_candidate_pair_count < minimum_candidate_count) {
			minimum_candidate_count = world.physics.last_candidate_pair_count;
		}
		if (world.physics.last_candidate_pair_count > maximum_candidate_count) {
			maximum_candidate_count = world.physics.last_candidate_pair_count;
		}
		if (world.physics.contact_count > maximum_contact_count) {
			maximum_contact_count = world.physics.contact_count;
		}
		if (world.physics.last_solver_iteration_count > maximum_solver_iteration_count) {
			maximum_solver_iteration_count = world.physics.last_solver_iteration_count;
		}

		for (uint16_t index = 0U; index < world.physics.contact_count; ++index) {
			if (world.physics.contacts[index].type == PICOSYSTEM_PHYSICS_CONTACT_BODY) {
				saw_body_contact = true;
			} else {
				saw_static_contact = true;
			}
		}
	}

	assert(saw_body_contact);
	assert(saw_static_contact);
	assert(saw_candidate_reduction);
	fprintf(stderr, "candidate range: %u-%u/76, max contacts: %u, max solver: %u\n",
		minimum_candidate_count, maximum_candidate_count, maximum_contact_count,
		maximum_solver_iteration_count);
	world.logic_tick_count = UINT32_MAX;
	assert(picosystem_game_world_step(&world, &inputs[0]) == 0);
	assert(world.logic_tick_count == UINT32_MAX);
}

static void replay_pattern(struct picosystem_game_world *world)
{
	static const struct picosystem_game_input inputs[] = {
		{.horizontal = 1},
		{.vertical = -1},
		{.horizontal = -1, .vertical = 1},
		{0},
	};

	for (uint32_t step = 0U; step < 10000U; ++step) {
		const size_t input_index = step % (sizeof(inputs) / sizeof(inputs[0]));
		assert(picosystem_game_world_step(world, &inputs[input_index]) == 0);
	}
}

static void test_reset_replay_is_bit_exact(void)
{
	struct picosystem_game_world first;
	assert(picosystem_game_world_reset(&first) == 0);
	replay_pattern(&first);

	struct picosystem_game_world second;
	assert(picosystem_game_world_reset(&second) == 0);
	replay_pattern(&second);

	assert_world_equal(&first, &second);
	assert_hash("replay-10000", picosystem_game_world_hash(&first), EXPECTED_REPLAY_10000_HASH);
}

int main(void)
{
	test_bounded_motion_contacts_and_saturated_tick();
	test_canonical_reset_and_golden_replay();
	test_validation_preserves_state();
	test_reset_replay_is_bit_exact();
	puts("game-world tests passed");
	return 0;
}
