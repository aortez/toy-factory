/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "game_world.h"

#include <errno.h>
#include <limits.h>
#include <stddef.h>
#include <stdint.h>

#define GAME_MAX_SPEED_PER_TICK PICOSYSTEM_PHYSICS_FIXED_RATIO(5, 2)
#define GAME_GRAVITY_PER_TICK   PICOSYSTEM_PHYSICS_FIXED_RATIO(1, 32)
#define GAME_CONTROL_PER_TICK   PICOSYSTEM_PHYSICS_FIXED_RATIO(3, 64)
#define GAME_RESTITUTION        PICOSYSTEM_PHYSICS_FIXED_RATIO(3, 4)
#define GAME_FRICTION           PICOSYSTEM_PHYSICS_FIXED_RATIO(1, 8)
#define GAME_WORLD_HASH_VERSION UINT32_C(3)
#define FNV1A_OFFSET_BASIS      UINT32_C(2166136261)
#define FNV1A_PRIME             UINT32_C(16777619)

#define FIXED(value)                  PICOSYSTEM_PHYSICS_FIXED_FROM_INT(value)
#define RATIO(numerator, denominator) PICOSYSTEM_PHYSICS_FIXED_RATIO(numerator, denominator)

struct canonical_body_config {
	union {
		struct picosystem_physics_circle_config circle;
		struct picosystem_physics_box_config box;
	};
	uint8_t shape;
};

static const struct canonical_body_config canonical_bodies[] =
	{
		{
			.box =
				{
					.center = {.x = FIXED(55), .y = FIXED(55)},
					.velocity_per_tick = {.x = RATIO(3, 4)},
					.half_extent = {.x = FIXED(10), .y = FIXED(7)},
					.inverse_mass = PICOSYSTEM_PHYSICS_FIXED_ONE,
					.restitution = GAME_RESTITUTION,
					.friction = GAME_FRICTION,
					.angular_velocity_per_tick = RATIO(1, 80),
					.angle_turns = UINT32_C(0x08000000),
					.id = 1U,
				},
			.shape = PICOSYSTEM_PHYSICS_SHAPE_BOX,
		},
		{
			.circle =
				{
					.center = {.x = FIXED(88), .y = FIXED(68)},
					.velocity_per_tick = {.x = -RATIO(1, 4), .y = RATIO(1, 8)},
					.radius = FIXED(7),
					.inverse_mass = RATIO(5, 4),
					.restitution = RATIO(2, 3),
					.friction = RATIO(1, 6),
					.id = 2U,
				},
			.shape = PICOSYSTEM_PHYSICS_SHAPE_CIRCLE,
		},
		{
			.box =
				{
					.center = {.x = FIXED(125), .y = FIXED(50)},
					.velocity_per_tick = {.x = RATIO(1, 8)},
					.half_extent = {.x = FIXED(12), .y = FIXED(7)},
					.inverse_mass = RATIO(3, 4),
					.restitution = RATIO(4, 5),
					.friction = RATIO(1, 10),
					.angular_velocity_per_tick = -RATIO(1, 96),
					.angle_turns = UINT32_C(0xf0000000),
					.id = 3U,
				},
			.shape = PICOSYSTEM_PHYSICS_SHAPE_BOX,
		},
		{
			.circle =
				{
					.center = {.x = FIXED(162), .y = FIXED(72)},
					.velocity_per_tick = {.x = -RATIO(1, 2), .y = -RATIO(1, 8)},
					.radius = FIXED(8),
					.inverse_mass = PICOSYSTEM_PHYSICS_FIXED_ONE,
					.restitution = RATIO(7, 10),
					.friction = RATIO(1, 5),
					.id = 4U,
				},
			.shape = PICOSYSTEM_PHYSICS_SHAPE_CIRCLE,
		},
		{
			.box =
				{
					.center = {.x = FIXED(200), .y = FIXED(52)},
					.velocity_per_tick = {.x = -RATIO(1, 8), .y = RATIO(1, 4)},
					.half_extent = {.x = FIXED(7), .y = FIXED(5)},
					.inverse_mass = RATIO(3, 2),
					.restitution = RATIO(5, 6),
					.friction = RATIO(1, 12),
					.angular_velocity_per_tick = RATIO(1, 64),
					.angle_turns = UINT32_C(0x20000000),
					.id = 5U,
				},
			.shape = PICOSYSTEM_PHYSICS_SHAPE_BOX,
		},
		{
			.circle =
				{
					.center = {.x = FIXED(120), .y = FIXED(105)},
					.velocity_per_tick = {.x = RATIO(3, 8), .y = -RATIO(1, 8)},
					.radius = FIXED(10),
					.inverse_mass = RATIO(4, 5),
					.restitution = RATIO(3, 4),
					.friction = RATIO(1, 7),
					.id = 6U,
				},
			.shape = PICOSYSTEM_PHYSICS_SHAPE_CIRCLE,
		},
		{
			.box =
				{
					.center = {.x = FIXED(35), .y = FIXED(112)},
					.velocity_per_tick = {.x = RATIO(1, 4), .y = -RATIO(1, 8)},
					.half_extent = {.x = FIXED(7), .y = FIXED(5)},
					.inverse_mass = RATIO(5, 4),
					.restitution = RATIO(7, 10),
					.friction = RATIO(1, 9),
					.angular_velocity_per_tick = RATIO(1, 72),
					.angle_turns = UINT32_C(0x30000000),
					.id = 7U,
				},
			.shape = PICOSYSTEM_PHYSICS_SHAPE_BOX,
		},
		{
			.circle =
				{
					.center = {.x = FIXED(68), .y = FIXED(126)},
					.velocity_per_tick = {.x = RATIO(3, 8), .y = -RATIO(1, 16)},
					.radius = FIXED(6),
					.inverse_mass = RATIO(3, 2),
					.restitution = RATIO(4, 5),
					.friction = RATIO(1, 6),
					.id = 8U,
				},
			.shape = PICOSYSTEM_PHYSICS_SHAPE_CIRCLE,
		},
};

static const struct picosystem_physics_segment_config canonical_segments[] = {
	{
		.start = {.x = FIXED(PICOSYSTEM_GAME_PLAYFIELD_LEFT_PIXELS),
			  .y = FIXED(PICOSYSTEM_GAME_PLAYFIELD_TOP_PIXELS)},
		.end = {.x = FIXED(PICOSYSTEM_GAME_PLAYFIELD_RIGHT_PIXELS),
			.y = FIXED(PICOSYSTEM_GAME_PLAYFIELD_TOP_PIXELS)},
		.restitution = GAME_RESTITUTION,
		.friction = GAME_FRICTION,
		.id = 101U,
	},
	{
		.start = {.x = FIXED(PICOSYSTEM_GAME_PLAYFIELD_RIGHT_PIXELS),
			  .y = FIXED(PICOSYSTEM_GAME_PLAYFIELD_BOTTOM_PIXELS)},
		.end = {.x = FIXED(PICOSYSTEM_GAME_PLAYFIELD_RIGHT_PIXELS),
			.y = FIXED(PICOSYSTEM_GAME_PLAYFIELD_TOP_PIXELS)},
		.restitution = GAME_RESTITUTION,
		.friction = GAME_FRICTION,
		.id = 102U,
	},
	{
		.start = {.x = FIXED(PICOSYSTEM_GAME_PLAYFIELD_RIGHT_PIXELS),
			  .y = FIXED(PICOSYSTEM_GAME_PLAYFIELD_BOTTOM_PIXELS)},
		.end = {.x = FIXED(PICOSYSTEM_GAME_PLAYFIELD_LEFT_PIXELS),
			.y = FIXED(PICOSYSTEM_GAME_PLAYFIELD_BOTTOM_PIXELS)},
		.restitution = GAME_RESTITUTION,
		.friction = GAME_FRICTION,
		.id = 103U,
	},
	{
		.start = {.x = FIXED(PICOSYSTEM_GAME_PLAYFIELD_LEFT_PIXELS),
			  .y = FIXED(PICOSYSTEM_GAME_PLAYFIELD_TOP_PIXELS)},
		.end = {.x = FIXED(PICOSYSTEM_GAME_PLAYFIELD_LEFT_PIXELS),
			.y = FIXED(PICOSYSTEM_GAME_PLAYFIELD_BOTTOM_PIXELS)},
		.restitution = GAME_RESTITUTION,
		.friction = GAME_FRICTION,
		.id = 104U,
	},
	{
		.start = {.x = FIXED(34), .y = FIXED(160)},
		.end = {.x = FIXED(103), .y = FIXED(188)},
		.restitution = RATIO(2, 3),
		.friction = RATIO(1, 4),
		.id = 105U,
	},
	{
		.start = {.x = FIXED(137), .y = FIXED(145)},
		.end = {.x = FIXED(210), .y = FIXED(112)},
		.restitution = RATIO(4, 5),
		.friction = RATIO(1, 12),
		.id = 106U,
	},
};

_Static_assert(sizeof(canonical_bodies) / sizeof(canonical_bodies[0]) == PICOSYSTEM_GAME_BODY_COUNT,
	       "canonical body count must match the public contract");
_Static_assert(sizeof(canonical_segments) / sizeof(canonical_segments[0]) ==
		       PICOSYSTEM_GAME_STATIC_SEGMENT_COUNT,
	       "canonical segment count must match the public contract");
_Static_assert(PICOSYSTEM_GAME_BODY_COUNT <= PICOSYSTEM_PHYSICS_MAX_BODIES,
	       "canonical bodies must fit physics storage");
_Static_assert(PICOSYSTEM_GAME_STATIC_SEGMENT_COUNT <= PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS,
	       "canonical segments must fit physics storage");

static void increment_saturated(uint32_t *value)
{
	if (*value < UINT32_MAX) {
		++*value;
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

int picosystem_game_world_reset(struct picosystem_game_world *world)
{
	if (world == NULL) {
		return -EINVAL;
	}

	int err = picosystem_physics_world_init(&world->physics, GAME_MAX_SPEED_PER_TICK);
	if (err != 0) {
		return err;
	}
	world->logic_tick_count = 0U;

	for (size_t index = 0U; index < PICOSYSTEM_GAME_BODY_COUNT; ++index) {
		if (canonical_bodies[index].shape == PICOSYSTEM_PHYSICS_SHAPE_CIRCLE) {
			err = picosystem_physics_world_add_circle(&world->physics,
								  &canonical_bodies[index].circle);
		} else {
			err = picosystem_physics_world_add_box(&world->physics,
							       &canonical_bodies[index].box);
		}
		if (err != 0) {
			return err;
		}
	}
	for (size_t index = 0U; index < PICOSYSTEM_GAME_STATIC_SEGMENT_COUNT; ++index) {
		err = picosystem_physics_world_add_static_segment(&world->physics,
								  &canonical_segments[index]);
		if (err != 0) {
			return err;
		}
	}

	return 0;
}

int picosystem_game_world_step(struct picosystem_game_world *world,
			       const struct picosystem_game_input *input)
{
	if ((world == NULL) || (input == NULL)) {
		return -EINVAL;
	}
	if ((input->horizontal < -1) || (input->horizontal > 1) || (input->vertical < -1) ||
	    (input->vertical > 1)) {
		return -ERANGE;
	}

	const struct picosystem_physics_vector acceleration = {
		.x = input->horizontal * GAME_CONTROL_PER_TICK,
		.y = GAME_GRAVITY_PER_TICK + (input->vertical * GAME_CONTROL_PER_TICK),
	};
	const int err = picosystem_physics_world_step(&world->physics, &acceleration);
	if (err != 0) {
		return err;
	}

	increment_saturated(&world->logic_tick_count);
	return 0;
}

const struct picosystem_physics_body *
picosystem_game_world_focus_body(const struct picosystem_game_world *world)
{
	if (world == NULL) {
		return NULL;
	}
	return picosystem_physics_world_body_at(&world->physics, PICOSYSTEM_GAME_FOCUS_BODY_INDEX);
}

uint32_t picosystem_game_world_hash(const struct picosystem_game_world *world)
{
	if ((world == NULL) || (world->physics.body_count > PICOSYSTEM_PHYSICS_MAX_BODIES) ||
	    (world->physics.static_segment_count > PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS)) {
		return 0U;
	}

	uint32_t hash = fnv1a_u32(FNV1A_OFFSET_BASIS, GAME_WORLD_HASH_VERSION);
	hash = fnv1a_u32(hash, world->logic_tick_count);
	return fnv1a_u32(hash, picosystem_physics_world_hash(&world->physics));
}
