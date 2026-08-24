/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "game_scene.h"

#include <stdint.h>

#define MARBLE_RESTITUTION   PICOSYSTEM_PHYSICS_FIXED_RATIO(2, 5)
#define MARBLE_FRICTION      PICOSYSTEM_PHYSICS_FIXED_RATIO(7, 8)
#define MACHINE_FRICTION     PICOSYSTEM_PHYSICS_FIXED_ONE
#define LAUNCHER_RESTITUTION PICOSYSTEM_PHYSICS_FIXED_RATIO(3, 4)
#define FIXED(value)         PICOSYSTEM_PHYSICS_FIXED_FROM_INT(value)
#define RATIO(n, d)          PICOSYSTEM_PHYSICS_FIXED_RATIO(n, d)

enum marble_machine_body_id {
	MARBLE_MACHINE_BODY_MARBLE_1 = 701U,
	MARBLE_MACHINE_BODY_MARBLE_2,
	MARBLE_MACHINE_BODY_MARBLE_3,
	MARBLE_MACHINE_BODY_MARBLE_4,
	MARBLE_MACHINE_BODY_MARBLE_5,
	MARBLE_MACHINE_BODY_MARBLE_6,
	MARBLE_MACHINE_BODY_MARBLE_7,
	MARBLE_MACHINE_BODY_MARBLE_8,
	MARBLE_MACHINE_BODY_MARBLE_9,
	MARBLE_MACHINE_BODY_PADDLE,
	MARBLE_MACHINE_BODY_LAUNCHER,
	MARBLE_MACHINE_BODY_ACCUMULATOR,
};

static const struct picosystem_game_body_config
	bodies[] =
		{
			{
				.circle =
					{
						.center = {.x = FIXED(60), .y = FIXED(101)},
						.radius = FIXED(5),
						.inverse_mass = PICOSYSTEM_PHYSICS_FIXED_ONE,
						.restitution = MARBLE_RESTITUTION,
						.friction = MARBLE_FRICTION,
						.id = MARBLE_MACHINE_BODY_MARBLE_1,
					},
				.shape = PICOSYSTEM_PHYSICS_SHAPE_CIRCLE,
			},
			{
				.circle =
					{
						.center = {.x = FIXED(105), .y = FIXED(114)},
						.radius = FIXED(5),
						.inverse_mass = PICOSYSTEM_PHYSICS_FIXED_ONE,
						.restitution = MARBLE_RESTITUTION,
						.friction = MARBLE_FRICTION,
						.id = MARBLE_MACHINE_BODY_MARBLE_2,
					},
				.shape = PICOSYSTEM_PHYSICS_SHAPE_CIRCLE,
			},
			{
				.circle =
					{
						.center = {.x = FIXED(150), .y = FIXED(126)},
						.radius = FIXED(5),
						.inverse_mass = PICOSYSTEM_PHYSICS_FIXED_ONE,
						.restitution = MARBLE_RESTITUTION,
						.friction = MARBLE_FRICTION,
						.id = MARBLE_MACHINE_BODY_MARBLE_3,
					},
				.shape = PICOSYSTEM_PHYSICS_SHAPE_CIRCLE,
			},
			{
				.circle =
					{
						.center = {.x = FIXED(195), .y = FIXED(138)},
						.radius = FIXED(5),
						.inverse_mass = PICOSYSTEM_PHYSICS_FIXED_ONE,
						.restitution = MARBLE_RESTITUTION,
						.friction = MARBLE_FRICTION,
						.id = MARBLE_MACHINE_BODY_MARBLE_4,
					},
				.shape = PICOSYSTEM_PHYSICS_SHAPE_CIRCLE,
			},
			{
				.circle =
					{
						.center = {.x = FIXED(190), .y = FIXED(170)},
						.radius = FIXED(5),
						.inverse_mass = PICOSYSTEM_PHYSICS_FIXED_ONE,
						.restitution = MARBLE_RESTITUTION,
						.friction = MARBLE_FRICTION,
						.id = MARBLE_MACHINE_BODY_MARBLE_5,
					},
				.shape = PICOSYSTEM_PHYSICS_SHAPE_CIRCLE,
			},
			{
				.circle =
					{
						.center = {.x = FIXED(140), .y = FIXED(183)},
						.radius = FIXED(5),
						.inverse_mass = PICOSYSTEM_PHYSICS_FIXED_ONE,
						.restitution = MARBLE_RESTITUTION,
						.friction = MARBLE_FRICTION,
						.id = MARBLE_MACHINE_BODY_MARBLE_6,
					},
				.shape = PICOSYSTEM_PHYSICS_SHAPE_CIRCLE,
			},
			{
				.circle =
					{
						.center = {.x = FIXED(150), .y = FIXED(213)},
						.radius = FIXED(5),
						.inverse_mass = PICOSYSTEM_PHYSICS_FIXED_ONE,
						.restitution = MARBLE_RESTITUTION,
						.friction = MARBLE_FRICTION,
						.id = MARBLE_MACHINE_BODY_MARBLE_7,
					},
				.shape = PICOSYSTEM_PHYSICS_SHAPE_CIRCLE,
			},
			{
				.circle =
					{
						.center = {.x = FIXED(50), .y = FIXED(229)},
						.radius = FIXED(5),
						.inverse_mass = PICOSYSTEM_PHYSICS_FIXED_ONE,
						.restitution = MARBLE_RESTITUTION,
						.friction = MARBLE_FRICTION,
						.id = MARBLE_MACHINE_BODY_MARBLE_8,
					},
				.shape = PICOSYSTEM_PHYSICS_SHAPE_CIRCLE,
			},
			{
				.circle =
					{
						.center = {.x = FIXED(205), .y = FIXED(128)},
						.radius = FIXED(5),
						.inverse_mass = PICOSYSTEM_PHYSICS_FIXED_ONE,
						.restitution = MARBLE_RESTITUTION,
						.friction = MARBLE_FRICTION,
						.id = MARBLE_MACHINE_BODY_MARBLE_9,
					},
				.shape = PICOSYSTEM_PHYSICS_SHAPE_CIRCLE,
			},
			{
				.capsule =
					{
						.center = {.x = FIXED(184), .y = FIXED(115)},
						.half_length = FIXED(7),
						.radius = FIXED(2),
						.inverse_mass = RATIO(1, 2),
						.restitution = MARBLE_RESTITUTION,
						.friction = MACHINE_FRICTION,
						.angle_turns =
							PICOSYSTEM_PHYSICS_ANGLE_QUARTER_TURN,
						.id = MARBLE_MACHINE_BODY_PADDLE,
					},
				.shape = PICOSYSTEM_PHYSICS_SHAPE_CAPSULE,
			},
			{
				.capsule =
					{
						.center = {.x = FIXED(125), .y = FIXED(125)},
						.half_length = FIXED(25),
						.radius = FIXED(3),
						.inverse_mass = RATIO(1, 2),
						.restitution = LAUNCHER_RESTITUTION,
						.friction = MACHINE_FRICTION,
						.angle_turns = UINT32_C(0x10000000),
						.id = MARBLE_MACHINE_BODY_LAUNCHER,
					},
				.shape = PICOSYSTEM_PHYSICS_SHAPE_CAPSULE,
			},
			{
				.capsule =
					{
						.center = {.x = FIXED(195), .y = FIXED(148)},
						.half_length = FIXED(24),
						.radius = FIXED(3),
						.inverse_mass = RATIO(1, 4),
						.restitution = MARBLE_RESTITUTION,
						.friction = MACHINE_FRICTION,
						.angle_turns = UINT32_C(0x04000000),
						.id = MARBLE_MACHINE_BODY_ACCUMULATOR,
					},
				.shape = PICOSYSTEM_PHYSICS_SHAPE_CAPSULE,
			},
};

static const struct picosystem_physics_segment_config segments[] = {
	{
		.start = {.x = FIXED(PICOSYSTEM_GAME_PLAYFIELD_LEFT_PIXELS),
			  .y = FIXED(PICOSYSTEM_GAME_PLAYFIELD_TOP_PIXELS)},
		.end = {.x = FIXED(PICOSYSTEM_GAME_PLAYFIELD_LEFT_PIXELS),
			.y = FIXED(PICOSYSTEM_GAME_PLAYFIELD_BOTTOM_PIXELS)},
		.restitution = MARBLE_RESTITUTION,
		.friction = MARBLE_FRICTION,
		.id = 801U,
	},
	{
		.start = {.x = FIXED(232), .y = FIXED(PICOSYSTEM_GAME_PLAYFIELD_BOTTOM_PIXELS)},
		.end = {.x = FIXED(232), .y = FIXED(PICOSYSTEM_GAME_PLAYFIELD_TOP_PIXELS)},
		.restitution = MARBLE_RESTITUTION,
		.friction = MARBLE_FRICTION,
		.id = 802U,
	},
	{
		.start = {.x = FIXED(232), .y = FIXED(PICOSYSTEM_GAME_PLAYFIELD_BOTTOM_PIXELS)},
		.end = {.x = FIXED(PICOSYSTEM_GAME_PLAYFIELD_LEFT_PIXELS),
			.y = FIXED(PICOSYSTEM_GAME_PLAYFIELD_BOTTOM_PIXELS)},
		.restitution = MARBLE_RESTITUTION,
		.friction = MACHINE_FRICTION,
		.surface_speed_per_tick = FIXED(3),
		.id = 803U,
	},
	{
		.start = {.x = FIXED(35), .y = FIXED(218)},
		.end = {.x = FIXED(35), .y = FIXED(70)},
		.restitution = MARBLE_RESTITUTION,
		.friction = MACHINE_FRICTION,
		.surface_speed_per_tick = FIXED(1),
		.id = 804U,
	},
	{
		.start = {.x = FIXED(35), .y = FIXED(70)},
		.end = {.x = FIXED(104), .y = FIXED(96)},
		.restitution = MARBLE_RESTITUTION,
		.friction = MARBLE_FRICTION,
		.id = 805U,
	},
	{
		.start = {.x = FIXED(232), .y = FIXED(168)},
		.end = {.x = FIXED(110), .y = FIXED(210)},
		.restitution = MARBLE_RESTITUTION,
		.friction = MACHINE_FRICTION,
		.surface_speed_per_tick = FIXED(2),
		.id = 806U,
	},
	{
		.start = {.x = FIXED(232), .y = FIXED(88)},
		.end = {.x = FIXED(225), .y = FIXED(139)},
		.restitution = MARBLE_RESTITUTION,
		.friction = MARBLE_FRICTION,
		.id = 807U,
	},
	{
		.start = {.x = FIXED(PICOSYSTEM_GAME_PLAYFIELD_LEFT_PIXELS),
			  .y = FIXED(PICOSYSTEM_GAME_PLAYFIELD_TOP_PIXELS)},
		.end = {.x = FIXED(232), .y = FIXED(PICOSYSTEM_GAME_PLAYFIELD_TOP_PIXELS)},
		.restitution = MARBLE_RESTITUTION,
		.friction = MARBLE_FRICTION,
		.id = 808U,
	},
};

static const struct picosystem_physics_box_sensor_config box_sensors[] = {
	{
		.center = {.x = FIXED(20), .y = FIXED(72)},
		.half_extent = {.x = FIXED(14), .y = FIXED(7)},
		.id = 1001U,
	},
};

static const struct picosystem_physics_revolute_joint_config revolute_joints[] = {
	{
		.anchor_b = {.x = FIXED(184), .y = FIXED(115)},
		.motor_speed_per_tick = RATIO(1, 24),
		.maximum_motor_impulse_per_tick = FIXED(2),
		.id = 901U,
		.body_a_id = MARBLE_MACHINE_BODY_PADDLE,
		.body_b_id = PICOSYSTEM_PHYSICS_WORLD_BODY_ID,
		.motor_enabled = 1U,
	},
	{
		.anchor_b = {.x = FIXED(125), .y = FIXED(125)},
		.id = 902U,
		.body_a_id = MARBLE_MACHINE_BODY_LAUNCHER,
		.body_b_id = PICOSYSTEM_PHYSICS_WORLD_BODY_ID,
		.limit_enabled = 1U,
	},
	{
		.anchor_b = {.x = FIXED(195), .y = FIXED(148)},
		.lower_angle_radians = -RATIO(1, 8),
		.upper_angle_radians = RATIO(2, 3),
		.id = 903U,
		.body_a_id = MARBLE_MACHINE_BODY_ACCUMULATOR,
		.body_b_id = PICOSYSTEM_PHYSICS_WORLD_BODY_ID,
		.limit_enabled = 1U,
	},
};

static const struct picosystem_physics_distance_joint_config distance_joints[] = {
	{
		.local_anchor_a = {.x = FIXED(20)},
		.anchor_b = {.x = FIXED(145), .y = FIXED(90)},
		.target_distance = FIXED(30),
		.spring_angular_frequency_per_tick = RATIO(1, 2),
		.spring_damping_ratio = RATIO(1, 20),
		.maximum_spring_impulse_per_tick = FIXED(8),
		.id = 1101U,
		.body_a_id = MARBLE_MACHINE_BODY_LAUNCHER,
		.body_b_id = PICOSYSTEM_PHYSICS_WORLD_BODY_ID,
		.spring_enabled = 1U,
	},
	{
		.local_anchor_a = {.x = FIXED(19)},
		.anchor_b = {.x = FIXED(214), .y = FIXED(126)},
		.target_distance = FIXED(24),
		.spring_angular_frequency_per_tick = RATIO(1, 12),
		.spring_damping_ratio = RATIO(1, 4),
		.maximum_spring_impulse_per_tick = FIXED(2),
		.id = 1102U,
		.body_a_id = MARBLE_MACHINE_BODY_ACCUMULATOR,
		.body_b_id = PICOSYSTEM_PHYSICS_WORLD_BODY_ID,
		.spring_enabled = 1U,
	},
};

static const struct picosystem_game_spring_launcher_config spring_launchers[] = {
	{
		.released_lower_angle_radians = -RATIO(3, 4),
		.rearm_start_angle_radians = -RATIO(1, 2),
		.rearm_stop_angle_radians = -RATIO(1, 32),
		.rearm_motor_speed_per_tick = RATIO(1, 32),
		.maximum_rearm_motor_impulse_per_tick = FIXED(128),
		.trigger_body_mask = UINT16_C(0x01ff),
		.launcher_body_index = MARBLE_MACHINE_BODY_LAUNCHER - MARBLE_MACHINE_BODY_MARBLE_1,
		.revolute_joint_index = 1U,
	},
};

static const struct picosystem_game_velocity_zone_config velocity_zones[] = {
	{
		.center = {.x = FIXED(20), .y = FIXED(143)},
		.half_extent = {.x = FIXED(15), .y = FIXED(90)},
		.target_velocity_per_tick = {.x = RATIO(1, 4), .y = -RATIO(3, 2)},
		.maximum_velocity_change_per_tick = RATIO(1, 2),
		.body_mask = UINT16_C(0x01ff),
	},
};

#define ELEMENT_COUNT(values) ((uint16_t)(sizeof(values) / sizeof((values)[0])))

_Static_assert(ELEMENT_COUNT(bodies) <= PICOSYSTEM_PHYSICS_MAX_BODIES,
	       "Marble Machine bodies must fit physics storage");
_Static_assert(ELEMENT_COUNT(segments) <= PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS,
	       "Marble Machine segments must fit physics storage");
_Static_assert(ELEMENT_COUNT(box_sensors) <= PICOSYSTEM_PHYSICS_MAX_BOX_SENSORS,
	       "Marble Machine sensors must fit physics storage");
_Static_assert(ELEMENT_COUNT(distance_joints) <= PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS,
	       "Marble Machine launcher springs must fit physics storage");
_Static_assert(ELEMENT_COUNT(revolute_joints) <= PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS,
	       "Marble Machine paddle joints must fit physics storage");
_Static_assert(ELEMENT_COUNT(spring_launchers) <= PICOSYSTEM_GAME_MAX_SPRING_LAUNCHERS,
	       "Marble Machine launchers must fit scene storage");
_Static_assert(ELEMENT_COUNT(velocity_zones) <= PICOSYSTEM_GAME_MAX_VELOCITY_ZONES,
	       "Marble Machine velocity zones must fit scene storage");

static const struct picosystem_game_scene_config scene = {
	.bodies = bodies,
	.segments = segments,
	.box_sensors = box_sensors,
	.distance_joints = distance_joints,
	.revolute_joints = revolute_joints,
	.velocity_zones = velocity_zones,
	.spring_launchers = spring_launchers,
	.primary_action_segment_surface_mask = UINT16_C(0x0024),
	.sensor_entry_body_mask = UINT16_C(0x01ff),
	.body_count = ELEMENT_COUNT(bodies),
	.segment_count = ELEMENT_COUNT(segments),
	.box_sensor_count = ELEMENT_COUNT(box_sensors),
	.distance_joint_count = ELEMENT_COUNT(distance_joints),
	.revolute_joint_count = ELEMENT_COUNT(revolute_joints),
	.velocity_zone_count = ELEMENT_COUNT(velocity_zones),
	.spring_launcher_count = ELEMENT_COUNT(spring_launchers),
	.id = PICOSYSTEM_GAME_SCENE_MARBLE_MACHINE,
	.sensor_entry_direction = PICOSYSTEM_GAME_SENSOR_ENTRY_DIRECTION_UP,
};

const struct picosystem_game_scene_config *picosystem_game_scene_marble_machine(void)
{
	return &scene;
}
