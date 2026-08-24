/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "game_scene.h"

#include <stdint.h>

#define GAME_RESTITUTION PICOSYSTEM_PHYSICS_FIXED_RATIO(3, 4)
#define GAME_FRICTION    PICOSYSTEM_PHYSICS_FIXED_RATIO(1, 8)
#define FIXED(value)     PICOSYSTEM_PHYSICS_FIXED_FROM_INT(value)
#define RATIO(n, d)      PICOSYSTEM_PHYSICS_FIXED_RATIO(n, d)

static const struct picosystem_game_body_config bodies[] =
	{
		{
			.box =
				{
					.center = {.x = FIXED(55), .y = FIXED(55)},
					.velocity_per_tick = {.x = RATIO(3, 2)},
					.half_extent = {.x = FIXED(10), .y = FIXED(7)},
					.inverse_mass = PICOSYSTEM_PHYSICS_FIXED_ONE,
					.restitution = GAME_RESTITUTION,
					.friction = GAME_FRICTION,
					.angular_velocity_per_tick = RATIO(1, 40),
					.angle_turns = UINT32_C(0x08000000),
					.id = 1U,
				},
			.shape = PICOSYSTEM_PHYSICS_SHAPE_BOX,
		},
		{
			.circle =
				{
					.center = {.x = FIXED(88), .y = FIXED(68)},
					.velocity_per_tick = {.x = -RATIO(1, 2), .y = RATIO(1, 4)},
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
					.velocity_per_tick = {.x = -FIXED(1), .y = -RATIO(1, 4)},
					.half_length = FIXED(7),
					.radius = FIXED(4),
					.inverse_mass = PICOSYSTEM_PHYSICS_FIXED_ONE,
					.restitution = RATIO(7, 10),
					.friction = RATIO(1, 5),
					.angular_velocity_per_tick = -RATIO(1, 48),
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

static const struct picosystem_physics_segment_config segments[] = {
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
		.surface_speed_per_tick = RATIO(1, 2),
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

static const struct picosystem_physics_distance_joint_config distance_joints[] = {
	{
		.anchor_b = {.x = FIXED(162), .y = FIXED(44)},
		.target_distance = FIXED(28),
		.spring_angular_frequency_per_tick = RATIO(1, 6),
		.spring_damping_ratio = RATIO(1, 2),
		.maximum_spring_impulse_per_tick = FIXED(2),
		.id = 201U,
		.body_a_id = 4U,
		.body_b_id = PICOSYSTEM_PHYSICS_WORLD_BODY_ID,
		.spring_enabled = 1U,
	},
};

static const struct picosystem_physics_box_sensor_config box_sensors[] = {
	{
		.center = {.x = FIXED(70), .y = FIXED(124)},
		.half_extent = {.x = FIXED(30), .y = FIXED(10)},
		.id = 501U,
	},
};

static const struct picosystem_physics_revolute_joint_config revolute_joints[] = {
	{
		.local_anchor_a = {.x = -FIXED(10)},
		.anchor_b = {.x = FIXED(134), .y = FIXED(88)},
		.motor_speed_per_tick = RATIO(1, 48),
		.maximum_motor_impulse_per_tick = RATIO(1, 2),
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

static const struct picosystem_physics_prismatic_joint_config prismatic_joints[] = {
	{
		.anchor_b = {.x = FIXED(118), .y = FIXED(190)},
		.axis_b = {.y = PICOSYSTEM_PHYSICS_FIXED_ONE},
		.motor_speed_per_tick = -RATIO(1, 4),
		.maximum_motor_impulse_per_tick = FIXED(2),
		.lower_translation = -FIXED(48),
		.upper_translation = 0,
		.id = 401U,
		.body_a_id = 9U,
		.body_b_id = PICOSYSTEM_PHYSICS_WORLD_BODY_ID,
		.motor_enabled = 1U,
		.limit_enabled = 1U,
	},
};

static const struct picosystem_physics_rope_config ropes[] = {
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

#define ELEMENT_COUNT(values) ((uint16_t)(sizeof(values) / sizeof((values)[0])))

_Static_assert(ELEMENT_COUNT(bodies) == PICOSYSTEM_GAME_BODY_COUNT,
	       "Machine Lab body count must match the public profiling contract");
_Static_assert(ELEMENT_COUNT(segments) == PICOSYSTEM_GAME_STATIC_SEGMENT_COUNT,
	       "Machine Lab segment count must match the public profiling contract");
_Static_assert(ELEMENT_COUNT(distance_joints) == PICOSYSTEM_GAME_DISTANCE_JOINT_COUNT,
	       "Machine Lab distance-joint count must match the public profiling contract");
_Static_assert(ELEMENT_COUNT(revolute_joints) == PICOSYSTEM_GAME_REVOLUTE_JOINT_COUNT,
	       "Machine Lab revolute-joint count must match the public profiling contract");
_Static_assert(ELEMENT_COUNT(prismatic_joints) == PICOSYSTEM_GAME_PRISMATIC_JOINT_COUNT,
	       "Machine Lab prismatic-joint count must match the public profiling contract");
_Static_assert(ELEMENT_COUNT(box_sensors) == PICOSYSTEM_GAME_BOX_SENSOR_COUNT,
	       "Machine Lab sensor count must match the public profiling contract");
_Static_assert(ELEMENT_COUNT(ropes) == PICOSYSTEM_GAME_ROPE_COUNT,
	       "Machine Lab rope count must match the public profiling contract");
_Static_assert(ELEMENT_COUNT(bodies) <= PICOSYSTEM_PHYSICS_MAX_BODIES,
	       "Machine Lab bodies must fit physics storage");
_Static_assert(ELEMENT_COUNT(segments) <= PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS,
	       "Machine Lab segments must fit physics storage");
_Static_assert(ELEMENT_COUNT(distance_joints) <= PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS,
	       "Machine Lab distance joints must fit physics storage");
_Static_assert(ELEMENT_COUNT(revolute_joints) <= PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS,
	       "Machine Lab revolute joints must fit physics storage");
_Static_assert(ELEMENT_COUNT(prismatic_joints) <= PICOSYSTEM_PHYSICS_MAX_PRISMATIC_JOINTS,
	       "Machine Lab prismatic joints must fit physics storage");
_Static_assert(ELEMENT_COUNT(box_sensors) <= PICOSYSTEM_PHYSICS_MAX_BOX_SENSORS,
	       "Machine Lab sensors must fit physics storage");
_Static_assert(ELEMENT_COUNT(ropes) <= PICOSYSTEM_PHYSICS_MAX_ROPES,
	       "Machine Lab ropes must fit physics storage");

static const struct picosystem_game_scene_config scene = {
	.bodies = bodies,
	.segments = segments,
	.distance_joints = distance_joints,
	.revolute_joints = revolute_joints,
	.prismatic_joints = prismatic_joints,
	.box_sensors = box_sensors,
	.ropes = ropes,
	.reversing_prismatic_motor_mask = UINT16_C(1),
	.sensor_entry_body_mask = UINT16_C(0x007f),
	.body_count = ELEMENT_COUNT(bodies),
	.segment_count = ELEMENT_COUNT(segments),
	.distance_joint_count = ELEMENT_COUNT(distance_joints),
	.revolute_joint_count = ELEMENT_COUNT(revolute_joints),
	.prismatic_joint_count = ELEMENT_COUNT(prismatic_joints),
	.box_sensor_count = ELEMENT_COUNT(box_sensors),
	.rope_count = ELEMENT_COUNT(ropes),
	.id = PICOSYSTEM_GAME_SCENE_MACHINE_LAB,
};

const struct picosystem_game_scene_config *picosystem_game_scene_machine_lab(void)
{
	return &scene;
}
