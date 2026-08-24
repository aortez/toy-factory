/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "game_scene.h"

#include <stdint.h>

#define CLOCKWORK_RESTITUTION PICOSYSTEM_PHYSICS_FIXED_RATIO(1, 4)
#define CLOCKWORK_FRICTION    PICOSYSTEM_PHYSICS_FIXED_RATIO(1, 3)
#define FIXED(value)          PICOSYSTEM_PHYSICS_FIXED_FROM_INT(value)
#define RATIO(n, d)           PICOSYSTEM_PHYSICS_FIXED_RATIO(n, d)

enum clockwork_body_id {
	CLOCKWORK_BODY_DRIVE_GEAR = 21U,
	CLOCKWORK_BODY_FOLLOWER_GEAR,
	CLOCKWORK_BODY_CONNECTING_ROD,
	CLOCKWORK_BODY_SLIDER,
	CLOCKWORK_BODY_PENDULUM,
	CLOCKWORK_BODY_PENDULUM_BOB,
	CLOCKWORK_BODY_SPRING_BOB,
	CLOCKWORK_BODY_MOBILE_ROOT,
	CLOCKWORK_BODY_MOBILE_TIP,
};

static const struct picosystem_game_body_config bodies[] =
	{
		{
			.circle =
				{
					.center = {.x = FIXED(45), .y = FIXED(70)},
					.radius = FIXED(14),
					.inverse_mass = RATIO(1, 2),
					.restitution = 0,
					.friction = RATIO(7, 8),
					.id = CLOCKWORK_BODY_DRIVE_GEAR,
				},
			.shape = PICOSYSTEM_PHYSICS_SHAPE_CIRCLE,
		},
		{
			.circle =
				{
					.center = {.x = FIXED(45), .y = FIXED(96)},
					.radius = FIXED(12),
					.inverse_mass = RATIO(2, 3),
					.restitution = 0,
					.friction = RATIO(7, 8),
					.id = CLOCKWORK_BODY_FOLLOWER_GEAR,
				},
			.shape = PICOSYSTEM_PHYSICS_SHAPE_CIRCLE,
		},
		{
			.capsule =
				{
					.center = {.x = FIXED(80), .y = FIXED(70)},
					.half_length = FIXED(23),
					.radius = FIXED(3),
					.inverse_mass = RATIO(3, 4),
					.restitution = CLOCKWORK_RESTITUTION,
					.friction = CLOCKWORK_FRICTION,
					.id = CLOCKWORK_BODY_CONNECTING_ROD,
				},
			.shape = PICOSYSTEM_PHYSICS_SHAPE_CAPSULE,
		},
		{
			.box =
				{
					.center = {.x = FIXED(113), .y = FIXED(70)},
					.half_extent = {.x = FIXED(10), .y = FIXED(7)},
					.inverse_mass = RATIO(1, 2),
					.restitution = CLOCKWORK_RESTITUTION,
					.friction = CLOCKWORK_FRICTION,
					.id = CLOCKWORK_BODY_SLIDER,
				},
			.shape = PICOSYSTEM_PHYSICS_SHAPE_BOX,
		},
		{
			.capsule =
				{
					.center = {.x = FIXED(170), .y = FIXED(78)},
					.velocity_per_tick = {.x = RATIO(1, 2)},
					.half_length = FIXED(24),
					.radius = FIXED(3),
					.inverse_mass = RATIO(3, 4),
					.restitution = CLOCKWORK_RESTITUTION,
					.friction = CLOCKWORK_FRICTION,
					.angle_turns = PICOSYSTEM_PHYSICS_ANGLE_QUARTER_TURN,
					.id = CLOCKWORK_BODY_PENDULUM,
				},
			.shape = PICOSYSTEM_PHYSICS_SHAPE_CAPSULE,
		},
		{
			.circle =
				{
					.center = {.x = FIXED(170), .y = FIXED(108)},
					.velocity_per_tick = {.x = RATIO(1, 2)},
					.radius = FIXED(8),
					.inverse_mass = PICOSYSTEM_PHYSICS_FIXED_ONE,
					.restitution = RATIO(1, 3),
					.friction = CLOCKWORK_FRICTION,
					.id = CLOCKWORK_BODY_PENDULUM_BOB,
				},
			.shape = PICOSYSTEM_PHYSICS_SHAPE_CIRCLE,
		},
		{
			.circle =
				{
					.center = {.x = FIXED(214), .y = FIXED(84)},
					.velocity_per_tick = {.x = -RATIO(1, 3)},
					.radius = FIXED(7),
					.inverse_mass = PICOSYSTEM_PHYSICS_FIXED_ONE,
					.restitution = RATIO(1, 3),
					.friction = CLOCKWORK_FRICTION,
					.id = CLOCKWORK_BODY_SPRING_BOB,
				},
			.shape = PICOSYSTEM_PHYSICS_SHAPE_CIRCLE,
		},
		{
			.box =
				{
					.center = {.x = FIXED(72), .y = FIXED(158)},
					.half_extent = {.x = FIXED(18), .y = FIXED(3)},
					.inverse_mass = RATIO(3, 4),
					.restitution = CLOCKWORK_RESTITUTION,
					.friction = CLOCKWORK_FRICTION,
					.id = CLOCKWORK_BODY_MOBILE_ROOT,
				},
			.shape = PICOSYSTEM_PHYSICS_SHAPE_BOX,
		},
		{
			.box =
				{
					.center = {.x = FIXED(108), .y = FIXED(158)},
					.half_extent = {.x = FIXED(18), .y = FIXED(3)},
					.inverse_mass = PICOSYSTEM_PHYSICS_FIXED_ONE,
					.restitution = CLOCKWORK_RESTITUTION,
					.friction = CLOCKWORK_FRICTION,
					.id = CLOCKWORK_BODY_MOBILE_TIP,
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
		.restitution = CLOCKWORK_RESTITUTION,
		.friction = CLOCKWORK_FRICTION,
		.id = 121U,
	},
	{
		.start = {.x = FIXED(PICOSYSTEM_GAME_PLAYFIELD_RIGHT_PIXELS),
			  .y = FIXED(PICOSYSTEM_GAME_PLAYFIELD_BOTTOM_PIXELS)},
		.end = {.x = FIXED(PICOSYSTEM_GAME_PLAYFIELD_RIGHT_PIXELS),
			.y = FIXED(PICOSYSTEM_GAME_PLAYFIELD_TOP_PIXELS)},
		.restitution = CLOCKWORK_RESTITUTION,
		.friction = CLOCKWORK_FRICTION,
		.id = 122U,
	},
	{
		.start = {.x = FIXED(PICOSYSTEM_GAME_PLAYFIELD_RIGHT_PIXELS),
			  .y = FIXED(PICOSYSTEM_GAME_PLAYFIELD_BOTTOM_PIXELS)},
		.end = {.x = FIXED(PICOSYSTEM_GAME_PLAYFIELD_LEFT_PIXELS),
			.y = FIXED(PICOSYSTEM_GAME_PLAYFIELD_BOTTOM_PIXELS)},
		.restitution = CLOCKWORK_RESTITUTION,
		.friction = CLOCKWORK_FRICTION,
		.id = 123U,
	},
	{
		.start = {.x = FIXED(PICOSYSTEM_GAME_PLAYFIELD_LEFT_PIXELS),
			  .y = FIXED(PICOSYSTEM_GAME_PLAYFIELD_TOP_PIXELS)},
		.end = {.x = FIXED(PICOSYSTEM_GAME_PLAYFIELD_LEFT_PIXELS),
			.y = FIXED(PICOSYSTEM_GAME_PLAYFIELD_BOTTOM_PIXELS)},
		.restitution = CLOCKWORK_RESTITUTION,
		.friction = CLOCKWORK_FRICTION,
		.id = 124U,
	},
};

static const struct picosystem_physics_distance_joint_config distance_joints[] = {
	{
		.anchor_b = {.x = FIXED(214), .y = FIXED(50)},
		.target_distance = FIXED(34),
		.spring_angular_frequency_per_tick = RATIO(1, 10),
		.spring_damping_ratio = RATIO(1, 3),
		.maximum_spring_impulse_per_tick = FIXED(1),
		.id = 221U,
		.body_a_id = CLOCKWORK_BODY_SPRING_BOB,
		.body_b_id = PICOSYSTEM_PHYSICS_WORLD_BODY_ID,
		.spring_enabled = 1U,
	},
};

static const struct picosystem_physics_revolute_joint_config revolute_joints[] = {
	{
		.anchor_b = {.x = FIXED(45), .y = FIXED(70)},
		.motor_speed_per_tick = RATIO(1, 48),
		.maximum_motor_impulse_per_tick = RATIO(3, 2),
		.id = 321U,
		.body_a_id = CLOCKWORK_BODY_DRIVE_GEAR,
		.body_b_id = PICOSYSTEM_PHYSICS_WORLD_BODY_ID,
		.motor_enabled = 1U,
	},
	{
		.anchor_b = {.x = FIXED(45), .y = FIXED(96)},
		.id = 322U,
		.body_a_id = CLOCKWORK_BODY_FOLLOWER_GEAR,
		.body_b_id = PICOSYSTEM_PHYSICS_WORLD_BODY_ID,
	},
	{
		.local_anchor_a = {.x = FIXED(12)},
		.anchor_b = {.x = -FIXED(23)},
		.id = 323U,
		.body_a_id = CLOCKWORK_BODY_DRIVE_GEAR,
		.body_b_id = CLOCKWORK_BODY_CONNECTING_ROD,
	},
	{
		.local_anchor_a = {.x = FIXED(23)},
		.anchor_b = {.x = -FIXED(10)},
		.id = 324U,
		.body_a_id = CLOCKWORK_BODY_CONNECTING_ROD,
		.body_b_id = CLOCKWORK_BODY_SLIDER,
	},
	{
		.local_anchor_a = {.x = -FIXED(24)},
		.anchor_b = {.x = FIXED(170), .y = FIXED(54)},
		.lower_angle_radians = -RATIO(5, 4),
		.upper_angle_radians = RATIO(5, 4),
		.id = 325U,
		.body_a_id = CLOCKWORK_BODY_PENDULUM,
		.body_b_id = PICOSYSTEM_PHYSICS_WORLD_BODY_ID,
		.limit_enabled = 1U,
	},
	{
		.local_anchor_a = {.x = FIXED(24)},
		.anchor_b = {.y = -FIXED(6)},
		.id = 326U,
		.body_a_id = CLOCKWORK_BODY_PENDULUM,
		.body_b_id = CLOCKWORK_BODY_PENDULUM_BOB,
	},
	{
		.local_anchor_a = {.x = -FIXED(18)},
		.anchor_b = {.x = FIXED(54), .y = FIXED(158)},
		.lower_angle_radians = -RATIO(3, 2),
		.upper_angle_radians = RATIO(3, 2),
		.id = 327U,
		.body_a_id = CLOCKWORK_BODY_MOBILE_ROOT,
		.body_b_id = PICOSYSTEM_PHYSICS_WORLD_BODY_ID,
		.limit_enabled = 1U,
	},
	{
		.local_anchor_a = {.x = FIXED(18)},
		.anchor_b = {.x = -FIXED(18)},
		.lower_angle_radians = -RATIO(3, 2),
		.upper_angle_radians = RATIO(3, 2),
		.id = 328U,
		.body_a_id = CLOCKWORK_BODY_MOBILE_ROOT,
		.body_b_id = CLOCKWORK_BODY_MOBILE_TIP,
		.limit_enabled = 1U,
	},
};

static const struct picosystem_physics_prismatic_joint_config prismatic_joints[] = {
	{
		.anchor_b = {.x = FIXED(113), .y = FIXED(70)},
		.axis_b = {.x = PICOSYSTEM_PHYSICS_FIXED_ONE},
		.lower_translation = -FIXED(24),
		.upper_translation = 0,
		.id = 421U,
		.body_a_id = CLOCKWORK_BODY_SLIDER,
		.body_b_id = PICOSYSTEM_PHYSICS_WORLD_BODY_ID,
		.limit_enabled = 1U,
	},
};

static const struct picosystem_physics_box_sensor_config box_sensors[] = {
	{
		.center = {.x = FIXED(92), .y = FIXED(70)},
		.half_extent = {.x = FIXED(2), .y = FIXED(9)},
		.id = 521U,
	},
};

static const struct picosystem_physics_rope_config ropes[] = {
	{
		.endpoint_a =
			{
				.anchor = {.x = FIXED(18)},
				.body_id = CLOCKWORK_BODY_MOBILE_TIP,
				.pinned = 1U,
				.reaction_enabled = 1U,
			},
		.endpoint_b =
			{
				.anchor = {.x = FIXED(218), .y = FIXED(160)},
				.body_id = PICOSYSTEM_PHYSICS_WORLD_BODY_ID,
				.pinned = 1U,
			},
		.segment_length = FIXED(20),
		.collision_radius = FIXED(1),
		.id = 621U,
		.particle_count = 6U,
	},
};

#define ELEMENT_COUNT(values) ((uint16_t)(sizeof(values) / sizeof((values)[0])))

_Static_assert(ELEMENT_COUNT(bodies) <= PICOSYSTEM_PHYSICS_MAX_BODIES,
	       "Clockwork bodies must fit physics storage");
_Static_assert(ELEMENT_COUNT(segments) <= PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS,
	       "Clockwork segments must fit physics storage");
_Static_assert(ELEMENT_COUNT(distance_joints) <= PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS,
	       "Clockwork distance joints must fit physics storage");
_Static_assert(ELEMENT_COUNT(revolute_joints) <= PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS,
	       "Clockwork revolute joints must fit physics storage");
_Static_assert(ELEMENT_COUNT(prismatic_joints) <= PICOSYSTEM_PHYSICS_MAX_PRISMATIC_JOINTS,
	       "Clockwork prismatic joints must fit physics storage");
_Static_assert(ELEMENT_COUNT(box_sensors) <= PICOSYSTEM_PHYSICS_MAX_BOX_SENSORS,
	       "Clockwork sensors must fit physics storage");
_Static_assert(ELEMENT_COUNT(ropes) <= PICOSYSTEM_PHYSICS_MAX_ROPES,
	       "Clockwork ropes must fit physics storage");

static const struct picosystem_game_scene_config scene = {
	.bodies = bodies,
	.segments = segments,
	.distance_joints = distance_joints,
	.revolute_joints = revolute_joints,
	.prismatic_joints = prismatic_joints,
	.box_sensors = box_sensors,
	.ropes = ropes,
	.gear_body_mask = UINT16_C(0x0003),
	.sensor_entry_body_mask = UINT16_C(0x01ff),
	.body_count = ELEMENT_COUNT(bodies),
	.segment_count = ELEMENT_COUNT(segments),
	.distance_joint_count = ELEMENT_COUNT(distance_joints),
	.revolute_joint_count = ELEMENT_COUNT(revolute_joints),
	.prismatic_joint_count = ELEMENT_COUNT(prismatic_joints),
	.box_sensor_count = ELEMENT_COUNT(box_sensors),
	.rope_count = ELEMENT_COUNT(ropes),
	.id = PICOSYSTEM_GAME_SCENE_CLOCKWORK,
};

const struct picosystem_game_scene_config *picosystem_game_scene_clockwork(void)
{
	return &scene;
}
