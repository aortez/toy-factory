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
	assert(picosystem_granular_world_particle_at(&world, 127U) != NULL);
	assert(picosystem_granular_world_particle_at(&world, 128U) == NULL);
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
	test_configuration_validation();
	test_particle_capacity_and_access();
	test_pair_separation_and_falling();
	test_flip_and_deterministic_replay();
	printf("granular world tests passed\n");
	return 0;
}
