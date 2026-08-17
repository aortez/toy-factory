/* SPDX-License-Identifier: Apache-2.0 */

#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>

#include "physics_world.h"

#define FIXED(value)                  PICOSYSTEM_PHYSICS_FIXED_FROM_INT(value)
#define RATIO(numerator, denominator) PICOSYSTEM_PHYSICS_FIXED_RATIO(numerator, denominator)

static const struct picosystem_physics_vector no_acceleration = {0};

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
	assert(picosystem_physics_world_add_static_segment(&world, &segment) == -EEXIST);
	segment.id = 9U;
	segment.end = segment.start;
	assert(picosystem_physics_world_add_static_segment(&world, &segment) == -ERANGE);
	assert(world.static_segment_count == 1U);
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
	assert(world.last_candidate_pair_count == PICOSYSTEM_PHYSICS_MAX_CONTACTS);
	assert(world.contact_count == PICOSYSTEM_PHYSICS_MAX_CONTACTS);
}

static void test_hash_excludes_scratch_and_diagnostics(void)
{
	struct picosystem_physics_world world;
	init_world(&world, FIXED(2));
	const struct picosystem_physics_circle_config body = circle_config(1U, 0, 0, 1);
	assert(picosystem_physics_world_add_circle(&world, &body) == 0);
	const uint32_t expected = picosystem_physics_world_hash(&world);

	world.last_candidate_pair_count = UINT32_MAX;
	world.contact_count = 1U;
	world.contacts[0].penetration = INT32_MAX;
	assert(picosystem_physics_world_hash(&world) == expected);
	assert(picosystem_physics_world_hash(NULL) == 0U);
	assert(picosystem_physics_world_body_at(&world, 0U) == &world.bodies[0]);
	assert(picosystem_physics_world_body_at(&world, 1U) == NULL);
	assert(picosystem_physics_world_body_at(NULL, 0U) == NULL);
	world.body_count = PICOSYSTEM_PHYSICS_MAX_BODIES + 1U;
	assert(picosystem_physics_world_hash(&world) == 0U);
	assert(picosystem_physics_world_body_at(&world, 0U) == NULL);
}

int main(void)
{
	test_initialization_and_add_boundaries();
	test_duplicate_ids_and_invalid_segments();
	test_integration_speed_clamp_and_invalid_step();
	test_equal_mass_head_on_collision();
	test_unequal_mass_head_on_collision();
	test_static_floor_and_diagonal_segment();
	test_coincident_centers_are_stable();
	test_contact_storage_covers_all_candidates();
	test_hash_excludes_scratch_and_diagnostics();
	puts("physics-world tests passed");
	return 0;
}
