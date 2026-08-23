/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "granular_world.h"

#define FIXED(value) PICOSYSTEM_PHYSICS_FIXED_FROM_INT(value)
#define RATIO(n, d)  PICOSYSTEM_PHYSICS_FIXED_RATIO(n, d)

static const struct picosystem_granular_boundary_config box_boundaries[] = {
	{
		.start = {.x = FIXED(20), .y = FIXED(20)},
		.end = {.x = FIXED(220), .y = FIXED(20)},
		.active_minimum_y = 0,
		.active_maximum_y = FIXED(239),
		.id = 1U,
	},
	{
		.start = {.x = FIXED(220), .y = FIXED(20)},
		.end = {.x = FIXED(220), .y = FIXED(220)},
		.active_minimum_y = 0,
		.active_maximum_y = FIXED(239),
		.id = 2U,
	},
	{
		.start = {.x = FIXED(220), .y = FIXED(220)},
		.end = {.x = FIXED(20), .y = FIXED(220)},
		.active_minimum_y = 0,
		.active_maximum_y = FIXED(239),
		.id = 3U,
	},
	{
		.start = {.x = FIXED(20), .y = FIXED(220)},
		.end = {.x = FIXED(20), .y = FIXED(20)},
		.active_minimum_y = 0,
		.active_maximum_y = FIXED(239),
		.id = 4U,
	},
};

static struct picosystem_granular_world_config box_config(void)
{
	return (struct picosystem_granular_world_config){
		.boundaries = box_boundaries,
		.flip_center = {.x = FIXED(120), .y = FIXED(120)},
		.particle_radius = FIXED(2),
		.maximum_speed_per_tick = FIXED(4),
		.velocity_damping = RATIO(255, 256),
		.passage_deadband = FIXED(2),
		.passage_y = FIXED(120),
		.boundary_count = 4U,
	};
}

static uint32_t reference_integer_square_root(uint64_t value)
{
	uint32_t minimum = 0U;
	uint32_t maximum = UINT32_C(1) << 19U;
	while ((minimum + 1U) < maximum) {
		const uint32_t candidate = minimum + ((maximum - minimum) / 2U);
		if (((uint64_t)candidate * candidate) <= value) {
			minimum = candidate;
		} else {
			maximum = candidate;
		}
	}
	return minimum;
}

static void assert_particle_contact_length(uint32_t absolute_x, uint32_t absolute_y)
{
	const uint64_t squared_length =
		((uint64_t)absolute_x * absolute_x) + ((uint64_t)absolute_y * absolute_y);
	const uint32_t expected = reference_integer_square_root(squared_length);
	const uint32_t actual =
		picosystem_granular_test_particle_contact_length(absolute_x, absolute_y);
	const uint32_t maximum_error = (expected / 360U) + 2U;
	assert(actual <= expected);
	assert((expected - actual) <= maximum_error);
}

static void test_particle_contact_length(void)
{
	const uint32_t component_limit = (uint32_t)FIXED(8);
	const uint64_t squared_limit = (uint64_t)component_limit * component_limit;
	for (uint32_t component = 0U; component < component_limit; ++component) {
		assert(picosystem_granular_test_particle_contact_length(component, 0U) ==
		       component);
		assert(picosystem_granular_test_particle_contact_length(0U, component) ==
		       component);
	}
	for (uint32_t absolute_x = 0U; absolute_x < component_limit; absolute_x += 1021U) {
		for (uint32_t absolute_y = 0U; absolute_y < component_limit; absolute_y += 1021U) {
			const uint64_t squared_length = ((uint64_t)absolute_x * absolute_x) +
							((uint64_t)absolute_y * absolute_y);
			if (squared_length < squared_limit) {
				assert_particle_contact_length(absolute_x, absolute_y);
			}
		}
	}

	uint64_t random_state = UINT64_C(0x4d595df4d0f33173);
	for (uint32_t sample = 0U; sample < 100000U; ++sample) {
		random_state = (random_state * UINT64_C(6364136223846793005)) + UINT64_C(1);
		const uint32_t absolute_x = (uint32_t)random_state & (component_limit - 1U);
		random_state = (random_state * UINT64_C(6364136223846793005)) + UINT64_C(1);
		const uint32_t absolute_y = (uint32_t)random_state & (component_limit - 1U);
		const uint64_t squared_length =
			((uint64_t)absolute_x * absolute_x) + ((uint64_t)absolute_y * absolute_y);
		if (squared_length < squared_limit) {
			assert_particle_contact_length(absolute_x, absolute_y);
		}
	}
}

static void test_configuration_validation(void)
{
	struct picosystem_granular_world world;
	memset(&world, 0xa5, sizeof(world));
	const struct picosystem_granular_world unchanged = world;
	assert(picosystem_granular_world_init(
		       NULL, &(struct picosystem_granular_world_config){0}) == -EINVAL);
	assert(picosystem_granular_world_init(&world, NULL) == -EINVAL);
	assert(memcmp(&world, &unchanged, sizeof(world)) == 0);

	struct picosystem_granular_world_config config = box_config();
	config.particle_radius = 0;
	assert(picosystem_granular_world_init(&world, &config) == -ERANGE);
	assert(memcmp(&world, &unchanged, sizeof(world)) == 0);

	config = box_config();
	config.flip_center.x = FIXED(240);
	assert(picosystem_granular_world_init(&world, &config) == -ERANGE);
	assert(memcmp(&world, &unchanged, sizeof(world)) == 0);

	config = box_config();
	struct picosystem_granular_boundary_config out_of_range_boundaries[4];
	memcpy(out_of_range_boundaries, box_boundaries, sizeof(out_of_range_boundaries));
	out_of_range_boundaries[0].start.y = -1;
	config.boundaries = out_of_range_boundaries;
	assert(picosystem_granular_world_init(&world, &config) == -ERANGE);
	assert(memcmp(&world, &unchanged, sizeof(world)) == 0);

	config = box_config();
	struct picosystem_granular_boundary_config duplicate_boundaries[4];
	memcpy(duplicate_boundaries, box_boundaries, sizeof(duplicate_boundaries));
	duplicate_boundaries[3].id = duplicate_boundaries[0].id;
	config.boundaries = duplicate_boundaries;
	assert(picosystem_granular_world_init(&world, &config) == -EEXIST);
	assert(memcmp(&world, &unchanged, sizeof(world)) == 0);

	config = box_config();
	assert(picosystem_granular_world_init(&world, &config) == 0);
	assert(world.boundary_count == 4U);
	assert(world.particle_count == 0U);
	assert(world.boundaries[0].inward_normal.y == PICOSYSTEM_PHYSICS_FIXED_ONE);
	assert(world.boundaries[1].inward_normal.x == -PICOSYSTEM_PHYSICS_FIXED_ONE);
	assert(world.boundaries[2].inward_normal.y == -PICOSYSTEM_PHYSICS_FIXED_ONE);
	assert(world.boundaries[3].inward_normal.x == PICOSYSTEM_PHYSICS_FIXED_ONE);
}

static void test_particle_capacity_and_access(void)
{
	struct picosystem_granular_world world;
	const struct picosystem_granular_world_config config = box_config();
	assert(picosystem_granular_world_init(&world, &config) == 0);
	assert(picosystem_granular_world_add_particle(&world, NULL) == -EINVAL);
	const struct picosystem_physics_vector invalid = {.x = -1, .y = FIXED(40)};
	assert(picosystem_granular_world_add_particle(&world, &invalid) == -ERANGE);

	for (uint16_t index = 0U; index < PICOSYSTEM_GRANULAR_MAX_PARTICLES; ++index) {
		const struct picosystem_physics_vector position = {
			.x = FIXED(30) + ((int32_t)(index % 16U) * FIXED(5)),
			.y = FIXED(30) + ((int32_t)(index / 16U) * FIXED(5)),
		};
		assert(picosystem_granular_world_add_particle(&world, &position) == 0);
	}
	assert(world.particle_count == PICOSYSTEM_GRANULAR_MAX_PARTICLES);
	const struct picosystem_granular_world full = world;
	const struct picosystem_physics_vector extra = {.x = FIXED(100), .y = FIXED(100)};
	assert(picosystem_granular_world_add_particle(&world, &extra) == -ENOSPC);
	assert(memcmp(&world, &full, sizeof(world)) == 0);
	assert(picosystem_granular_world_particle_at(&world, PICOSYSTEM_GRANULAR_MAX_PARTICLES -
								     1U) != NULL);
	assert(picosystem_granular_world_particle_at(&world, PICOSYSTEM_GRANULAR_MAX_PARTICLES) ==
	       NULL);
}

static void test_wide_particle_grid_indices(void)
{
	struct picosystem_granular_world world;
	const struct picosystem_granular_world_config config = box_config();
	assert(picosystem_granular_world_init(&world, &config) == 0);
	for (uint16_t index = 0U; index < 256U; ++index) {
		const struct picosystem_physics_vector position = {
			.x = FIXED(30) + ((int32_t)(index % 16U) * FIXED(5)),
			.y = FIXED(30) + ((int32_t)(index / 16U) * FIXED(5)),
		};
		assert(picosystem_granular_world_add_particle(&world, &position) == 0);
	}
	const struct picosystem_physics_vector overlapping = {
		.x = FIXED(108),
		.y = FIXED(105),
	};
	assert(picosystem_granular_world_add_particle(&world, &overlapping) == 0);
	assert(world.particle_count == 257U);

	const struct picosystem_physics_vector no_acceleration = {0};
	assert(picosystem_granular_world_step(&world, &no_acceleration) == 0);
	const int64_t delta_x =
		(int64_t)world.particles[256].position.x - world.particles[255].position.x;
	const int64_t delta_y =
		(int64_t)world.particles[256].position.y - world.particles[255].position.y;
	const int64_t diameter = FIXED(4);
	assert((delta_x * delta_x) + (delta_y * delta_y) >= (diameter * diameter) - 8);
	assert(world.last_work.contact_count > 0U);
}

static void test_pair_separation_and_falling(void)
{
	struct picosystem_granular_world world;
	const struct picosystem_granular_world_config config = box_config();
	assert(picosystem_granular_world_init(&world, &config) == 0);
	const struct picosystem_physics_vector left = {.x = FIXED(118), .y = FIXED(40)};
	const struct picosystem_physics_vector right = {.x = FIXED(121), .y = FIXED(40)};
	assert(picosystem_granular_world_add_particle(&world, &left) == 0);
	assert(picosystem_granular_world_add_particle(&world, &right) == 0);
	const struct picosystem_physics_vector no_acceleration = {0};
	assert(picosystem_granular_world_step(&world, &no_acceleration) == 0);
	const int64_t delta_x =
		(int64_t)world.particles[1].position.x - world.particles[0].position.x;
	const int64_t delta_y =
		(int64_t)world.particles[1].position.y - world.particles[0].position.y;
	const int64_t diameter = FIXED(4);
	assert((delta_x * delta_x) + (delta_y * delta_y) >= (diameter * diameter) - 8);
	assert(world.last_work.contact_count > 0U);
	assert(world.last_work.candidate_pair_count > 0U);

	const struct picosystem_physics_vector gravity = {.y = RATIO(1, 8)};
	for (uint32_t tick = 0U; tick < 1000U; ++tick) {
		assert(picosystem_granular_world_step(&world, &gravity) == 0);
	}
	for (uint16_t index = 0U; index < world.particle_count; ++index) {
		assert(world.particles[index].position.x >= FIXED(22) - 2);
		assert(world.particles[index].position.x <= FIXED(218) + 2);
		assert(world.particles[index].position.y >= FIXED(22) - 2);
		assert(world.particles[index].position.y <= FIXED(218) + 2);
	}
	assert(picosystem_granular_world_lower_particle_count(&world) == 2U);
	assert(world.passage_count == 2U);
}

static void test_polygon_contact_separation(void)
{
	static const struct picosystem_physics_vector offsets[] = {
		{0},
		{.x = FIXED(1), .y = FIXED(1)},
		{.x = FIXED(2), .y = FIXED(1)},
		{.x = FIXED(1), .y = FIXED(2)},
		{.x = FIXED(3), .y = FIXED(1)},
		{.x = FIXED(1), .y = FIXED(3)},
		{.x = FIXED(3), .y = FIXED(2)},
		{.x = FIXED(2), .y = FIXED(3)},
	};
	const struct picosystem_physics_vector no_acceleration = {0};
	const int64_t diameter = FIXED(4);
	for (size_t index = 0U; index < (sizeof(offsets) / sizeof(offsets[0])); ++index) {
		struct picosystem_granular_world world;
		const struct picosystem_granular_world_config config = box_config();
		assert(picosystem_granular_world_init(&world, &config) == 0);
		const struct picosystem_physics_vector left = {.x = FIXED(100), .y = FIXED(100)};
		const struct picosystem_physics_vector right = {
			.x = left.x + offsets[index].x,
			.y = left.y + offsets[index].y,
		};
		assert(picosystem_granular_world_add_particle(&world, &left) == 0);
		assert(picosystem_granular_world_add_particle(&world, &right) == 0);
		assert(picosystem_granular_world_step(&world, &no_acceleration) == 0);
		const int64_t delta_x =
			(int64_t)world.particles[1].position.x - world.particles[0].position.x;
		const int64_t delta_y =
			(int64_t)world.particles[1].position.y - world.particles[0].position.y;
		assert((delta_x * delta_x) + (delta_y * delta_y) >= (diameter * diameter) - 8);
		assert(world.last_work.contact_count > 0U);
	}
}

static uint32_t fake_clock_now(void *context)
{
	uint32_t *const next = context;
	return (*next)++;
}

static void test_profiled_step(void)
{
	struct picosystem_granular_world unprofiled;
	const struct picosystem_granular_world_config config = box_config();
	assert(picosystem_granular_world_init(&unprofiled, &config) == 0);
	const struct picosystem_physics_vector left = {.x = FIXED(118), .y = FIXED(40)};
	const struct picosystem_physics_vector right = {.x = FIXED(121), .y = FIXED(40)};
	assert(picosystem_granular_world_add_particle(&unprofiled, &left) == 0);
	assert(picosystem_granular_world_add_particle(&unprofiled, &right) == 0);
	struct picosystem_granular_world profiled = unprofiled;
	const struct picosystem_physics_vector gravity = {.y = RATIO(1, 8)};
	assert(picosystem_granular_world_step(&unprofiled, &gravity) == 0);

	uint32_t next_cycle = 0U;
	const struct picosystem_physics_clock clock = {
		.now = fake_clock_now,
		.context = &next_cycle,
	};
	struct picosystem_granular_step_profile profile;
	memset(&profile, 0xa5, sizeof(profile));
	assert(picosystem_granular_world_step_profiled(&profiled, &gravity, &clock, &profile) == 0);
	assert(memcmp(&profiled, &unprofiled, sizeof(profiled)) == 0);
	assert(profile.clock_read_count == (10U + (6U * PICOSYSTEM_GRANULAR_SOLVER_ITERATIONS)));
	assert(profile.stage_cycles[PICOSYSTEM_GRANULAR_PROFILE_INTEGRATE] == 1U);
	assert(profile.stage_cycles[PICOSYSTEM_GRANULAR_PROFILE_BOUNDARIES] ==
	       (PICOSYSTEM_GRANULAR_SOLVER_ITERATIONS + 2U));
	assert(profile.stage_cycles[PICOSYSTEM_GRANULAR_PROFILE_GRID_BUILD] ==
	       PICOSYSTEM_GRANULAR_SOLVER_ITERATIONS);
	assert(profile.stage_cycles[PICOSYSTEM_GRANULAR_PROFILE_PAIR_SOLVE] ==
	       PICOSYSTEM_GRANULAR_SOLVER_ITERATIONS);
	assert(profile.stage_cycles[PICOSYSTEM_GRANULAR_PROFILE_PASSAGES] == 1U);
	assert(profile.stage_cycles[PICOSYSTEM_GRANULAR_PROFILE_OTHER] ==
	       (5U + (3U * PICOSYSTEM_GRANULAR_SOLVER_ITERATIONS)));
	assert(profile.stage_cycles[PICOSYSTEM_GRANULAR_PROFILE_TOTAL] ==
	       (9U + (6U * PICOSYSTEM_GRANULAR_SOLVER_ITERATIONS)));
	assert(memcmp(&profile.work, &profiled.last_work, sizeof(profile.work)) == 0);
	assert(profile.work.candidate_pair_count ==
	       (profile.work.axis_rejection_count + profile.work.diagonal_rejection_count +
		profile.work.distance_test_count));
	assert(profile.work.coarse_boundary_rejection_count <= profile.work.boundary_test_count);

	const struct picosystem_granular_world unchanged = profiled;
	assert(picosystem_granular_world_step_profiled(&profiled, &gravity, NULL, &profile) ==
	       -EINVAL);
	assert(memcmp(&profiled, &unchanged, sizeof(profiled)) == 0);
	assert(picosystem_granular_world_step_profiled(&profiled, &gravity, &clock, NULL) ==
	       -EINVAL);
	assert(memcmp(&profiled, &unchanged, sizeof(profiled)) == 0);
}

static void test_exact_pair_rejections(void)
{
	struct picosystem_granular_world world;
	const struct picosystem_granular_world_config config = box_config();
	assert(picosystem_granular_world_init(&world, &config) == 0);
	const struct picosystem_physics_vector upper_left = {.x = FIXED(100), .y = FIXED(100)};
	const struct picosystem_physics_vector lower_right = {.x = FIXED(103), .y = FIXED(103)};
	assert(picosystem_granular_world_add_particle(&world, &upper_left) == 0);
	assert(picosystem_granular_world_add_particle(&world, &lower_right) == 0);
	const struct picosystem_physics_vector no_acceleration = {0};
	assert(picosystem_granular_world_step(&world, &no_acceleration) == 0);
	assert(world.last_work.candidate_pair_count == 2U);
	assert(world.last_work.axis_rejection_count == 0U);
	assert(world.last_work.diagonal_rejection_count == 2U);
	assert(world.last_work.distance_test_count == 0U);
	assert(world.last_work.contact_count == 0U);
}

static void populate_replay_world(struct picosystem_granular_world *world)
{
	const struct picosystem_granular_world_config config = box_config();
	assert(picosystem_granular_world_init(world, &config) == 0);
	for (uint16_t row = 0U; row < 6U; ++row) {
		for (uint16_t column = 0U; column < 8U; ++column) {
			const struct picosystem_physics_vector position = {
				.x = FIXED(96) + ((int32_t)column * FIXED(5)),
				.y = FIXED(40) + ((int32_t)row * FIXED(5)),
			};
			assert(picosystem_granular_world_add_particle(world, &position) == 0);
		}
	}
}

static void replay_pattern(struct picosystem_granular_world *world)
{
	for (uint32_t tick = 0U; tick < 3000U; ++tick) {
		const int32_t horizontal =
			((tick / 250U) & 1U) == 0U ? RATIO(1, 32) : -RATIO(1, 32);
		const struct picosystem_physics_vector acceleration = {
			.x = horizontal,
			.y = RATIO(1, 8),
		};
		assert(picosystem_granular_world_step(world, &acceleration) == 0);
		if ((tick == 999U) || (tick == 1999U)) {
			assert(picosystem_granular_world_flip(world) == 0);
		}
	}
}

static void test_flip_and_deterministic_replay(void)
{
	struct picosystem_granular_world first;
	populate_replay_world(&first);
	const uint32_t initial_hash = picosystem_granular_world_hash(&first);
	assert(initial_hash != 0U);
	assert(picosystem_granular_world_flip(&first) == 0);
	assert(picosystem_granular_world_lower_particle_count(&first) == first.particle_count);
	assert(picosystem_granular_world_flip(&first) == 0);
	assert(picosystem_granular_world_hash(&first) == initial_hash);

	struct picosystem_granular_world second = first;
	replay_pattern(&first);
	replay_pattern(&second);
	assert(picosystem_granular_world_hash(&first) == picosystem_granular_world_hash(&second));
	for (uint16_t index = 0U; index < first.particle_count; ++index) {
		assert(first.particles[index].position.x >= FIXED(22) - 4);
		assert(first.particles[index].position.x <= FIXED(218) + 4);
		assert(first.particles[index].position.y >= FIXED(22) - 4);
		assert(first.particles[index].position.y <= FIXED(218) + 4);
	}
}

int main(void)
{
	test_particle_contact_length();
	test_configuration_validation();
	test_particle_capacity_and_access();
	test_wide_particle_grid_indices();
	test_pair_separation_and_falling();
	test_polygon_contact_separation();
	test_profiled_step();
	test_exact_pair_rejections();
	test_flip_and_deterministic_replay();
	printf("granular world tests passed\n");
	return 0;
}
