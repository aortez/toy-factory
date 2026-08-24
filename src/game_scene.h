/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_GAME_SCENE_H_
#define PICOSYSTEM_GAME_SCENE_H_

#include <stdint.h>

#include "game_world.h"
#include "granular_world.h"

#define PICOSYSTEM_GAME_MAX_VELOCITY_ZONES   4U
#define PICOSYSTEM_GAME_MAX_SPRING_LAUNCHERS 1U

struct picosystem_game_body_config {
	union {
		struct picosystem_physics_circle_config circle;
		struct picosystem_physics_box_config box;
		struct picosystem_physics_capsule_config capsule;
	};
	uint8_t shape;
};

struct picosystem_game_velocity_zone_config {
	struct picosystem_physics_vector center;
	struct picosystem_physics_vector half_extent;
	struct picosystem_physics_vector target_velocity_per_tick;
	picosystem_physics_fixed_t maximum_velocity_change_per_tick;
	/* Selects scene body-array indexes; the actuator runs before each rigid step. */
	uint16_t body_mask;
};

/* A contact-triggered revolute arm that releases a spring, then motor-winds itself. */
struct picosystem_game_spring_launcher_config {
	picosystem_physics_fixed_t armed_angle_radians;
	picosystem_physics_fixed_t released_lower_angle_radians;
	picosystem_physics_fixed_t rearm_start_angle_radians;
	picosystem_physics_fixed_t rearm_stop_angle_radians;
	picosystem_physics_fixed_t rearm_motor_speed_per_tick;
	picosystem_physics_fixed_t maximum_rearm_motor_impulse_per_tick;
	uint16_t trigger_body_mask;
	uint8_t launcher_body_index;
	uint8_t revolute_joint_index;
};

enum picosystem_game_sensor_entry_direction {
	PICOSYSTEM_GAME_SENSOR_ENTRY_DIRECTION_ANY,
	PICOSYSTEM_GAME_SENSOR_ENTRY_DIRECTION_UP,
	PICOSYSTEM_GAME_SENSOR_ENTRY_DIRECTION_DOWN,
	PICOSYSTEM_GAME_SENSOR_ENTRY_DIRECTION_LEFT,
	PICOSYSTEM_GAME_SENSOR_ENTRY_DIRECTION_RIGHT,
	PICOSYSTEM_GAME_SENSOR_ENTRY_DIRECTION_COUNT,
};

/* Immutable flash-resident input consumed while constructing a tick-zero world. */
struct picosystem_game_scene_config {
	const struct picosystem_game_body_config *bodies;
	const struct picosystem_physics_segment_config *segments;
	const struct picosystem_physics_distance_joint_config *distance_joints;
	const struct picosystem_physics_revolute_joint_config *revolute_joints;
	const struct picosystem_physics_prismatic_joint_config *prismatic_joints;
	const struct picosystem_physics_box_sensor_config *box_sensors;
	const struct picosystem_physics_rope_config *ropes;
	const struct picosystem_game_velocity_zone_config *velocity_zones;
	const struct picosystem_game_spring_launcher_config *spring_launchers;
	uint16_t gear_body_mask;
	uint16_t reversing_prismatic_motor_mask;
	uint16_t primary_action_prismatic_motor_mask;
	uint16_t primary_action_segment_surface_mask;
	uint16_t sensor_entry_body_mask;
	uint16_t body_count;
	uint16_t segment_count;
	uint16_t distance_joint_count;
	uint16_t revolute_joint_count;
	uint16_t prismatic_joint_count;
	uint16_t box_sensor_count;
	uint16_t rope_count;
	uint16_t velocity_zone_count;
	uint16_t spring_launcher_count;
	uint8_t id;
	uint8_t sensor_entry_direction;
};

const struct picosystem_game_scene_config *picosystem_game_scene_machine_lab(void);
const struct picosystem_game_scene_config *picosystem_game_scene_clockwork(void);
const struct picosystem_game_scene_config *picosystem_game_scene_marble_machine(void);
int picosystem_game_scene_hourglass_reset(struct picosystem_granular_world *world);

#endif /* PICOSYSTEM_GAME_SCENE_H_ */
