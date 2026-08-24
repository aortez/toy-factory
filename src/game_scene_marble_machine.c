/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "game_scene.h"

#include <stdint.h>

#define MARBLE_RESTITUTION PICOSYSTEM_PHYSICS_FIXED_RATIO(2, 5)
#define MARBLE_FRICTION    PICOSYSTEM_PHYSICS_FIXED_RATIO(7, 8)
#define MACHINE_FRICTION   PICOSYSTEM_PHYSICS_FIXED_ONE
#define FIXED(value)       PICOSYSTEM_PHYSICS_FIXED_FROM_INT(value)
#define RATIO(n, d)        PICOSYSTEM_PHYSICS_FIXED_RATIO(n, d)

enum marble_machine_body_id {
	MARBLE_MACHINE_BODY_MARBLE_1 = 701U,
	MARBLE_MACHINE_BODY_MARBLE_2,
	MARBLE_MACHINE_BODY_MARBLE_3,
	MARBLE_MACHINE_BODY_MARBLE_4,
	MARBLE_MACHINE_BODY_MARBLE_5,
	MARBLE_MACHINE_BODY_MARBLE_6,
	MARBLE_MACHINE_BODY_MARBLE_7,
	MARBLE_MACHINE_BODY_MARBLE_8,
};

static const struct picosystem_game_body_config bodies[] = {
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
		.start = {.x = FIXED(35), .y = FIXED(200)},
		.end = {.x = FIXED(35), .y = FIXED(100)},
		.restitution = MARBLE_RESTITUTION,
		.friction = MACHINE_FRICTION,
		.surface_speed_per_tick = FIXED(1),
		.id = 804U,
	},
	{
		.start = {.x = FIXED(35), .y = FIXED(100)},
		.end = {.x = FIXED(220), .y = FIXED(150)},
		.restitution = MARBLE_RESTITUTION,
		.friction = MARBLE_FRICTION,
		.id = 805U,
	},
	{
		.start = {.x = FIXED(232), .y = FIXED(168)},
		.end = {.x = FIXED(50), .y = FIXED(210)},
		.restitution = MARBLE_RESTITUTION,
		.friction = MACHINE_FRICTION,
		.surface_speed_per_tick = FIXED(2),
		.id = 806U,
	},
};

static const struct picosystem_physics_box_sensor_config box_sensors[] = {
	{
		.center = {.x = FIXED(20), .y = FIXED(102)},
		.half_extent = {.x = FIXED(14), .y = FIXED(7)},
		.id = 1001U,
	},
};

static const struct picosystem_game_velocity_zone_config velocity_zones[] = {
	{
		.center = {.x = FIXED(20), .y = FIXED(157)},
		.half_extent = {.x = FIXED(15), .y = FIXED(73)},
		.target_velocity_per_tick = {.x = RATIO(1, 4), .y = -RATIO(3, 2)},
		.maximum_velocity_change_per_tick = RATIO(1, 2),
		.body_mask = UINT16_C(0x00ff),
	},
};

#define ELEMENT_COUNT(values) ((uint16_t)(sizeof(values) / sizeof((values)[0])))

_Static_assert(ELEMENT_COUNT(bodies) <= PICOSYSTEM_PHYSICS_MAX_BODIES,
	       "Marble Machine bodies must fit physics storage");
_Static_assert(ELEMENT_COUNT(segments) <= PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS,
	       "Marble Machine segments must fit physics storage");
_Static_assert(ELEMENT_COUNT(box_sensors) <= PICOSYSTEM_PHYSICS_MAX_BOX_SENSORS,
	       "Marble Machine sensors must fit physics storage");
_Static_assert(ELEMENT_COUNT(velocity_zones) <= PICOSYSTEM_GAME_MAX_VELOCITY_ZONES,
	       "Marble Machine velocity zones must fit scene storage");

static const struct picosystem_game_scene_config scene = {
	.bodies = bodies,
	.segments = segments,
	.box_sensors = box_sensors,
	.velocity_zones = velocity_zones,
	.primary_action_segment_surface_mask = UINT16_C(0x0024),
	.sensor_entry_body_mask = UINT16_C(0x00ff),
	.body_count = ELEMENT_COUNT(bodies),
	.segment_count = ELEMENT_COUNT(segments),
	.box_sensor_count = ELEMENT_COUNT(box_sensors),
	.velocity_zone_count = ELEMENT_COUNT(velocity_zones),
	.id = PICOSYSTEM_GAME_SCENE_MARBLE_MACHINE,
	.sensor_entry_direction = PICOSYSTEM_GAME_SENSOR_ENTRY_DIRECTION_UP,
};

const struct picosystem_game_scene_config *picosystem_game_scene_marble_machine(void)
{
	return &scene;
}
