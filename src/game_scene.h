/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_GAME_SCENE_H_
#define PICOSYSTEM_GAME_SCENE_H_

#include <stdint.h>

#include "game_world.h"

struct picosystem_game_body_config {
	union {
		struct picosystem_physics_circle_config circle;
		struct picosystem_physics_box_config box;
		struct picosystem_physics_capsule_config capsule;
	};
	uint8_t shape;
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
	uint16_t gear_body_mask;
	uint16_t reversing_prismatic_motor_mask;
	uint16_t body_count;
	uint16_t segment_count;
	uint16_t distance_joint_count;
	uint16_t revolute_joint_count;
	uint16_t prismatic_joint_count;
	uint16_t box_sensor_count;
	uint16_t rope_count;
	uint8_t id;
};

const struct picosystem_game_scene_config *picosystem_game_scene_machine_lab(void);
const struct picosystem_game_scene_config *picosystem_game_scene_clockwork(void);

#endif /* PICOSYSTEM_GAME_SCENE_H_ */
