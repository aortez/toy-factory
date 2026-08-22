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

#define GAME_MAX_SPEED_PER_TICK     PICOSYSTEM_PHYSICS_FIXED_RATIO(5, 2)
#define GAME_GRAVITY_PER_TICK       PICOSYSTEM_PHYSICS_FIXED_RATIO(1, 32)
#define GAME_CONTROL_PER_TICK       PICOSYSTEM_PHYSICS_FIXED_RATIO(3, 64)
#define GAME_RESTITUTION            PICOSYSTEM_PHYSICS_FIXED_RATIO(3, 4)
#define GAME_FRICTION               PICOSYSTEM_PHYSICS_FIXED_RATIO(1, 8)
#define GAME_PRISMATIC_MOTOR_SPEED  PICOSYSTEM_PHYSICS_FIXED_RATIO(1, 8)
#define GAME_PRISMATIC_REVERSE_SLOP PICOSYSTEM_PHYSICS_FIXED_RATIO(1, 32)
#define GAME_WORLD_HASH_VERSION     UINT32_C(13)
#define FNV1A_OFFSET_BASIS          UINT32_C(2166136261)
#define FNV1A_PRIME                 UINT32_C(16777619)

#define FIXED(value)                  PICOSYSTEM_PHYSICS_FIXED_FROM_INT(value)
#define RATIO(numerator, denominator) PICOSYSTEM_PHYSICS_FIXED_RATIO(numerator, denominator)

struct canonical_body_config {
	union {
		struct picosystem_physics_circle_config circle;
		struct picosystem_physics_box_config box;
		struct picosystem_physics_capsule_config capsule;
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
			.capsule =
				{
					.center = {.x = FIXED(162), .y = FIXED(72)},
					.velocity_per_tick = {.x = -RATIO(1, 2), .y = -RATIO(1, 8)},
					.half_length = FIXED(7),
					.radius = FIXED(4),
					.inverse_mass = PICOSYSTEM_PHYSICS_FIXED_ONE,
					.restitution = RATIO(7, 10),
					.friction = RATIO(1, 5),
					.angular_velocity_per_tick = -RATIO(1, 96),
					.angle_turns = UINT32_C(0x18000000),
					.id = 4U,
				},
			.shape = PICOSYSTEM_PHYSICS_SHAPE_CAPSULE,
		},
		{
			.box =
				{
					.center = {.x = FIXED(144), .y = FIXED(88)},
					.half_extent = {.x = FIXED(10), .y = FIXED(4)},
					.inverse_mass = PICOSYSTEM_PHYSICS_FIXED_ONE,
					.restitution = RATIO(1, 4),
					.friction = RATIO(1, 5),
					.id = 5U,
				},
			.shape = PICOSYSTEM_PHYSICS_SHAPE_BOX,
		},
		{
			.box =
				{
					.center = {.x = FIXED(164), .y = FIXED(88)},
					.half_extent = {.x = FIXED(10), .y = FIXED(4)},
					.inverse_mass = PICOSYSTEM_PHYSICS_FIXED_ONE,
					.restitution = RATIO(1, 4),
					.friction = RATIO(1, 5),
					.id = 6U,
				},
			.shape = PICOSYSTEM_PHYSICS_SHAPE_BOX,
		},
		{
			.box =
				{
					.center = {.x = FIXED(184), .y = FIXED(88)},
					.half_extent = {.x = FIXED(10), .y = FIXED(4)},
					.inverse_mass = PICOSYSTEM_PHYSICS_FIXED_ONE,
					.restitution = RATIO(1, 4),
					.friction = RATIO(1, 5),
					.id = 7U,
				},
			.shape = PICOSYSTEM_PHYSICS_SHAPE_BOX,
		},
		{
			.box =
				{
					.center = {.x = FIXED(118), .y = FIXED(190)},
					.half_extent = {.x = FIXED(14), .y = FIXED(5)},
					.inverse_mass = RATIO(1, 2),
					.restitution = RATIO(1, 4),
					.friction = RATIO(1, 3),
					.id = 9U,
				},
			.shape = PICOSYSTEM_PHYSICS_SHAPE_BOX,
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
		.surface_speed_per_tick = RATIO(1, 4),
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

static const struct picosystem_physics_distance_joint_config canonical_distance_joints[] = {
	{
		.anchor_b = {.x = FIXED(162), .y = FIXED(44)},
		.target_distance = FIXED(28),
		.spring_angular_frequency_per_tick = RATIO(1, 12),
		.spring_damping_ratio = RATIO(1, 2),
		.maximum_spring_impulse_per_tick = RATIO(1, 2),
		.id = 201U,
		.body_a_id = 4U,
		.body_b_id = PICOSYSTEM_PHYSICS_WORLD_BODY_ID,
		.spring_enabled = 1U,
	},
};

static const struct picosystem_physics_box_sensor_config canonical_box_sensors[] = {
	{
		.center = {.x = FIXED(70), .y = FIXED(124)},
		.half_extent = {.x = FIXED(30), .y = FIXED(10)},
		.id = 501U,
	},
};

static const struct picosystem_physics_revolute_joint_config canonical_revolute_joints[] = {
	{
		.local_anchor_a = {.x = -FIXED(10)},
		.anchor_b = {.x = FIXED(134), .y = FIXED(88)},
		.motor_speed_per_tick = RATIO(1, 96),
		.maximum_motor_impulse_per_tick = RATIO(1, 8),
		.id = 301U,
		.body_a_id = 5U,
		.body_b_id = PICOSYSTEM_PHYSICS_WORLD_BODY_ID,
		.motor_enabled = 1U,
	},
	{
		.local_anchor_a = {.x = FIXED(10)},
		.anchor_b = {.x = -FIXED(10)},
		.id = 302U,
		.body_a_id = 5U,
		.body_b_id = 6U,
	},
	{
		.local_anchor_a = {.x = FIXED(10)},
		.anchor_b = {.x = -FIXED(10)},
		.lower_angle_radians = -PICOSYSTEM_PHYSICS_FIXED_ONE,
		.upper_angle_radians = PICOSYSTEM_PHYSICS_FIXED_ONE,
		.id = 303U,
		.body_a_id = 6U,
		.body_b_id = 7U,
		.limit_enabled = 1U,
	},
};

static const struct picosystem_physics_prismatic_joint_config canonical_prismatic_joints[] = {
	{
		.anchor_b = {.x = FIXED(118), .y = FIXED(190)},
		.axis_b = {.y = PICOSYSTEM_PHYSICS_FIXED_ONE},
		.motor_speed_per_tick = -GAME_PRISMATIC_MOTOR_SPEED,
		.maximum_motor_impulse_per_tick = RATIO(1, 2),
		.lower_translation = -FIXED(48),
		.upper_translation = 0,
		.id = 401U,
		.body_a_id = 9U,
		.body_b_id = PICOSYSTEM_PHYSICS_WORLD_BODY_ID,
		.motor_enabled = 1U,
		.limit_enabled = 1U,
	},
};

static const struct picosystem_physics_rope_config canonical_ropes[] = {
	{
		.endpoint_a =
			{
				.anchor = {.x = FIXED(7)},
				.body_id = 4U,
				.pinned = 1U,
				.reaction_enabled = 1U,
			},
		.endpoint_b =
			{
				.anchor = {.x = FIXED(218), .y = FIXED(45)},
				.body_id = PICOSYSTEM_PHYSICS_WORLD_BODY_ID,
				.pinned = 1U,
			},
		.segment_length = FIXED(18),
		.collision_radius = FIXED(1),
		.id = 501U,
		.particle_count = 8U,
	},
};

_Static_assert(sizeof(canonical_bodies) / sizeof(canonical_bodies[0]) == PICOSYSTEM_GAME_BODY_COUNT,
	       "canonical body count must match the public contract");
_Static_assert(sizeof(canonical_segments) / sizeof(canonical_segments[0]) ==
		       PICOSYSTEM_GAME_STATIC_SEGMENT_COUNT,
	       "canonical segment count must match the public contract");
_Static_assert(sizeof(canonical_distance_joints) / sizeof(canonical_distance_joints[0]) ==
		       PICOSYSTEM_GAME_DISTANCE_JOINT_COUNT,
	       "canonical distance-joint count must match the public contract");
_Static_assert(sizeof(canonical_revolute_joints) / sizeof(canonical_revolute_joints[0]) ==
		       PICOSYSTEM_GAME_REVOLUTE_JOINT_COUNT,
	       "canonical revolute-joint count must match the public contract");
_Static_assert(sizeof(canonical_prismatic_joints) / sizeof(canonical_prismatic_joints[0]) ==
		       PICOSYSTEM_GAME_PRISMATIC_JOINT_COUNT,
	       "canonical prismatic-joint count must match the public contract");
_Static_assert(sizeof(canonical_box_sensors) / sizeof(canonical_box_sensors[0]) ==
		       PICOSYSTEM_GAME_BOX_SENSOR_COUNT,
	       "canonical box-sensor count must match the public contract");
_Static_assert(sizeof(canonical_ropes) / sizeof(canonical_ropes[0]) == PICOSYSTEM_GAME_ROPE_COUNT,
	       "canonical rope count must match the public contract");
_Static_assert(PICOSYSTEM_GAME_BODY_COUNT <= PICOSYSTEM_PHYSICS_MAX_BODIES,
	       "canonical bodies must fit physics storage");
_Static_assert(PICOSYSTEM_GAME_STATIC_SEGMENT_COUNT <= PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS,
	       "canonical segments must fit physics storage");
_Static_assert(PICOSYSTEM_GAME_DISTANCE_JOINT_COUNT <= PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS,
	       "canonical joints must fit physics storage");
_Static_assert(PICOSYSTEM_GAME_REVOLUTE_JOINT_COUNT <= PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS,
	       "canonical revolute joints must fit physics storage");
_Static_assert(PICOSYSTEM_GAME_PRISMATIC_JOINT_COUNT <= PICOSYSTEM_PHYSICS_MAX_PRISMATIC_JOINTS,
	       "canonical prismatic joints must fit physics storage");
_Static_assert(PICOSYSTEM_GAME_BOX_SENSOR_COUNT <= PICOSYSTEM_PHYSICS_MAX_BOX_SENSORS,
	       "canonical box sensors must fit physics storage");
_Static_assert(PICOSYSTEM_GAME_ROPE_COUNT <= PICOSYSTEM_PHYSICS_MAX_ROPES,
	       "canonical ropes must fit physics storage");

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
	world->sensor_entry_count = 0U;

	for (size_t index = 0U; index < PICOSYSTEM_GAME_BODY_COUNT; ++index) {
		if (canonical_bodies[index].shape == PICOSYSTEM_PHYSICS_SHAPE_CIRCLE) {
			err = picosystem_physics_world_add_circle(&world->physics,
								  &canonical_bodies[index].circle);
		} else if (canonical_bodies[index].shape == PICOSYSTEM_PHYSICS_SHAPE_BOX) {
			err = picosystem_physics_world_add_box(&world->physics,
							       &canonical_bodies[index].box);
		} else if (canonical_bodies[index].shape == PICOSYSTEM_PHYSICS_SHAPE_CAPSULE) {
			err = picosystem_physics_world_add_capsule(
				&world->physics, &canonical_bodies[index].capsule);
		} else {
			return -ERANGE;
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
	for (size_t index = 0U; index < PICOSYSTEM_GAME_BOX_SENSOR_COUNT; ++index) {
		err = picosystem_physics_world_add_box_sensor(&world->physics,
							      &canonical_box_sensors[index]);
		if (err != 0) {
			return err;
		}
	}
	for (size_t index = 0U; index < PICOSYSTEM_GAME_DISTANCE_JOINT_COUNT; ++index) {
		err = picosystem_physics_world_add_distance_joint(
			&world->physics, &canonical_distance_joints[index]);
		if (err != 0) {
			return err;
		}
	}
	for (size_t index = 0U; index < PICOSYSTEM_GAME_REVOLUTE_JOINT_COUNT; ++index) {
		err = picosystem_physics_world_add_revolute_joint(
			&world->physics, &canonical_revolute_joints[index]);
		if (err != 0) {
			return err;
		}
	}
	for (size_t index = 0U; index < PICOSYSTEM_GAME_PRISMATIC_JOINT_COUNT; ++index) {
		err = picosystem_physics_world_add_prismatic_joint(
			&world->physics, &canonical_prismatic_joints[index]);
		if (err != 0) {
			return err;
		}
	}
	for (size_t index = 0U; index < PICOSYSTEM_GAME_ROPE_COUNT; ++index) {
		err = picosystem_physics_world_add_rope(&world->physics, &canonical_ropes[index]);
		if (err != 0) {
			return err;
		}
	}

	return 0;
}

static int update_prismatic_drive(struct picosystem_game_world *world)
{
	if (world->physics.prismatic_joint_count == 0U) {
		return 0;
	}
	if (world->physics.prismatic_joint_count != PICOSYSTEM_GAME_PRISMATIC_JOINT_COUNT) {
		return -ERANGE;
	}
	struct picosystem_physics_prismatic_joint *const joint =
		&world->physics.prismatic_joints[0];
	picosystem_physics_fixed_t translation;
	int err = picosystem_physics_world_prismatic_joint_translation(&world->physics, 0U,
								       &translation);
	if (err != 0) {
		return err;
	}

	picosystem_physics_fixed_t target_speed = joint->motor_speed_per_tick;
	if ((target_speed < 0) &&
	    (translation <= (joint->lower_translation + GAME_PRISMATIC_REVERSE_SLOP))) {
		target_speed = GAME_PRISMATIC_MOTOR_SPEED;
	} else if ((target_speed > 0) &&
		   (translation >= (joint->upper_translation - GAME_PRISMATIC_REVERSE_SLOP))) {
		target_speed = -GAME_PRISMATIC_MOTOR_SPEED;
	}
	if (target_speed == joint->motor_speed_per_tick) {
		return 0;
	}
	err = picosystem_physics_world_set_prismatic_motor_speed(&world->physics, 0U, target_speed);
	return err;
}

static int process_contact_events(struct picosystem_game_world *world)
{
	for (uint16_t index = 0U; index < world->physics.contact_event_count; ++index) {
		const struct picosystem_physics_contact_event *const event =
			picosystem_physics_world_contact_event_at(&world->physics, index);
		if (event == NULL) {
			return -ERANGE;
		}
		if ((event->type == PICOSYSTEM_PHYSICS_CONTACT_EVENT_BODY_BOX_SENSOR) &&
		    (event->phase == PICOSYSTEM_PHYSICS_CONTACT_EVENT_BEGIN)) {
			increment_saturated(&world->sensor_entry_count);
		}
	}
	return 0;
}

static int game_world_step(struct picosystem_game_world *world,
			   const struct picosystem_game_input *input,
			   enum picosystem_physics_step_mode mode,
			   const struct picosystem_physics_clock *clock,
			   struct picosystem_physics_step_profile *profile)
{
	if ((world == NULL) || (input == NULL)) {
		return -EINVAL;
	}
	if ((input->horizontal < -1) || (input->horizontal > 1) || (input->vertical < -1) ||
	    (input->vertical > 1)) {
		return -ERANGE;
	}
	int err = update_prismatic_drive(world);
	if (err != 0) {
		return err;
	}

	const struct picosystem_physics_vector acceleration = {
		.x = input->horizontal * GAME_CONTROL_PER_TICK,
		.y = GAME_GRAVITY_PER_TICK + (input->vertical * GAME_CONTROL_PER_TICK),
	};
	err = picosystem_physics_world_step_profiled(&world->physics, &acceleration, mode, clock,
						     profile);
	if (err != 0) {
		return err;
	}
	err = process_contact_events(world);
	if (err != 0) {
		return err;
	}

	increment_saturated(&world->logic_tick_count);
	return 0;
}

int picosystem_game_world_step(struct picosystem_game_world *world,
			       const struct picosystem_game_input *input)
{
	return game_world_step(world, input, PICOSYSTEM_PHYSICS_STEP_MODE_GRID, NULL, NULL);
}

int picosystem_game_world_step_profiled(struct picosystem_game_world *world,
					const struct picosystem_game_input *input,
					enum picosystem_physics_step_mode mode,
					const struct picosystem_physics_clock *clock,
					struct picosystem_physics_step_profile *profile)
{
	return game_world_step(world, input, mode, clock, profile);
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
	    (world->physics.static_segment_count > PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS) ||
	    (world->physics.distance_joint_count > PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS) ||
	    (world->physics.revolute_joint_count > PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS) ||
	    (world->physics.prismatic_joint_count > PICOSYSTEM_PHYSICS_MAX_PRISMATIC_JOINTS) ||
	    (world->physics.box_sensor_count > PICOSYSTEM_PHYSICS_MAX_BOX_SENSORS) ||
	    (world->physics.rope_count > PICOSYSTEM_PHYSICS_MAX_ROPES)) {
		return 0U;
	}

	uint32_t hash = fnv1a_u32(FNV1A_OFFSET_BASIS, GAME_WORLD_HASH_VERSION);
	hash = fnv1a_u32(hash, world->logic_tick_count);
	hash = fnv1a_u32(hash, world->sensor_entry_count);
	const uint32_t physics_hash = picosystem_physics_world_hash(&world->physics);
	return (physics_hash != 0U) ? fnv1a_u32(hash, physics_hash) : 0U;
}
