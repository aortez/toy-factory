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
#include <string.h>

#include "game_scene.h"

#define GAME_MAX_SPEED_PER_TICK     PICOSYSTEM_PHYSICS_FIXED_FROM_INT(5)
#define GAME_GRAVITY_PER_TICK       PICOSYSTEM_PHYSICS_FIXED_RATIO(1, 8)
#define GAME_CONTROL_PER_TICK       PICOSYSTEM_PHYSICS_FIXED_RATIO(3, 16)
#define GAME_PRISMATIC_REVERSE_SLOP PICOSYSTEM_PHYSICS_FIXED_RATIO(1, 32)
#define GAME_WORLD_HASH_VERSION     UINT32_C(15)
#define FNV1A_OFFSET_BASIS          UINT32_C(2166136261)
#define FNV1A_PRIME                 UINT32_C(16777619)

static const struct picosystem_game_scene_config *scene_config(uint8_t scene_id)
{
	switch (scene_id) {
	case PICOSYSTEM_GAME_SCENE_MACHINE_LAB:
		return picosystem_game_scene_machine_lab();
	case PICOSYSTEM_GAME_SCENE_CLOCKWORK:
		return picosystem_game_scene_clockwork();
	default:
		return NULL;
	}
}

static int validate_scene_config(const struct picosystem_game_scene_config *scene)
{
	if (scene == NULL) {
		return -EINVAL;
	}
	if ((scene->id >= PICOSYSTEM_GAME_SCENE_COUNT) || (scene->body_count == 0U) ||
	    (scene->body_count > PICOSYSTEM_PHYSICS_MAX_BODIES) ||
	    (scene->segment_count > PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS) ||
	    (scene->distance_joint_count > PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS) ||
	    (scene->revolute_joint_count > PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS) ||
	    (scene->prismatic_joint_count > PICOSYSTEM_PHYSICS_MAX_PRISMATIC_JOINTS) ||
	    (scene->box_sensor_count > PICOSYSTEM_PHYSICS_MAX_BOX_SENSORS) ||
	    (scene->rope_count > PICOSYSTEM_PHYSICS_MAX_ROPES)) {
		return -ERANGE;
	}
	const uint16_t valid_body_mask = (uint16_t)((UINT16_C(1) << scene->body_count) - 1U);
	const uint16_t valid_prismatic_mask =
		(uint16_t)((scene->prismatic_joint_count == 0U)
				   ? 0U
				   : ((UINT16_C(1) << scene->prismatic_joint_count) - 1U));
	if (((scene->gear_body_mask & (uint16_t)~valid_body_mask) != 0U) ||
	    ((scene->reversing_prismatic_motor_mask & (uint16_t)~valid_prismatic_mask) != 0U)) {
		return -ERANGE;
	}
	if (((scene->body_count != 0U) && (scene->bodies == NULL)) ||
	    ((scene->segment_count != 0U) && (scene->segments == NULL)) ||
	    ((scene->distance_joint_count != 0U) && (scene->distance_joints == NULL)) ||
	    ((scene->revolute_joint_count != 0U) && (scene->revolute_joints == NULL)) ||
	    ((scene->prismatic_joint_count != 0U) && (scene->prismatic_joints == NULL)) ||
	    ((scene->box_sensor_count != 0U) && (scene->box_sensors == NULL)) ||
	    ((scene->rope_count != 0U) && (scene->ropes == NULL))) {
		return -EINVAL;
	}
	return 0;
}

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

static int add_body(struct picosystem_physics_world *world,
		    const struct picosystem_game_body_config *config)
{
	switch (config->shape) {
	case PICOSYSTEM_PHYSICS_SHAPE_CIRCLE:
		return picosystem_physics_world_add_circle(world, &config->circle);
	case PICOSYSTEM_PHYSICS_SHAPE_BOX:
		return picosystem_physics_world_add_box(world, &config->box);
	case PICOSYSTEM_PHYSICS_SHAPE_CAPSULE:
		return picosystem_physics_world_add_capsule(world, &config->capsule);
	default:
		return -ERANGE;
	}
}

static void update_granular_focus_proxy(struct picosystem_game_world *world)
{
	const struct picosystem_granular_particle *const particle =
		picosystem_granular_world_particle_at(&world->granular, 0U);
	if (particle == NULL) {
		world->focus_proxy = (struct picosystem_physics_body){0};
		return;
	}
	world->focus_proxy = (struct picosystem_physics_body){
		.center = particle->position,
		.velocity_per_tick =
			{
				.x = particle->position.x - particle->previous_position.x,
				.y = particle->position.y - particle->previous_position.y,
			},
		.radius = world->granular.particle_radius,
		.id = 1001U,
		.shape = PICOSYSTEM_PHYSICS_SHAPE_CIRCLE,
	};
}

static int reset_hourglass(struct picosystem_game_world *world)
{
	const int err = picosystem_game_scene_hourglass_reset(&world->granular);
	if (err != 0) {
		return err;
	}
	world->logic_tick_count = 0U;
	world->sensor_entry_count = 0U;
	world->scene_id = PICOSYSTEM_GAME_SCENE_HOURGLASS;
	update_granular_focus_proxy(world);
	return 0;
}

int picosystem_game_world_reset_scene(struct picosystem_game_world *world,
				      enum picosystem_game_scene_id scene_id)
{
	if (world == NULL) {
		return -EINVAL;
	}
	if ((unsigned int)scene_id >= PICOSYSTEM_GAME_SCENE_COUNT) {
		return -ERANGE;
	}
	if (scene_id == PICOSYSTEM_GAME_SCENE_HOURGLASS) {
		return reset_hourglass(world);
	}
	const struct picosystem_game_scene_config *const scene = scene_config((uint8_t)scene_id);
	int err = validate_scene_config(scene);
	if (err != 0) {
		return err;
	}

	err = picosystem_physics_world_init(&world->physics, GAME_MAX_SPEED_PER_TICK);
	if (err != 0) {
		return err;
	}
	world->logic_tick_count = 0U;
	world->sensor_entry_count = 0U;
	world->scene_id = scene->id;
	world->focus_proxy = (struct picosystem_physics_body){0};

	for (uint16_t index = 0U; index < scene->body_count; ++index) {
		err = add_body(&world->physics, &scene->bodies[index]);
		if (err != 0) {
			return err;
		}
	}
	for (uint16_t index = 0U; index < scene->segment_count; ++index) {
		err = picosystem_physics_world_add_static_segment(&world->physics,
								  &scene->segments[index]);
		if (err != 0) {
			return err;
		}
	}
	for (uint16_t index = 0U; index < scene->box_sensor_count; ++index) {
		err = picosystem_physics_world_add_box_sensor(&world->physics,
							      &scene->box_sensors[index]);
		if (err != 0) {
			return err;
		}
	}
	for (uint16_t index = 0U; index < scene->distance_joint_count; ++index) {
		err = picosystem_physics_world_add_distance_joint(&world->physics,
								  &scene->distance_joints[index]);
		if (err != 0) {
			return err;
		}
	}
	for (uint16_t index = 0U; index < scene->revolute_joint_count; ++index) {
		err = picosystem_physics_world_add_revolute_joint(&world->physics,
								  &scene->revolute_joints[index]);
		if (err != 0) {
			return err;
		}
	}
	for (uint16_t index = 0U; index < scene->prismatic_joint_count; ++index) {
		err = picosystem_physics_world_add_prismatic_joint(&world->physics,
								   &scene->prismatic_joints[index]);
		if (err != 0) {
			return err;
		}
	}
	for (uint16_t index = 0U; index < scene->rope_count; ++index) {
		err = picosystem_physics_world_add_rope(&world->physics, &scene->ropes[index]);
		if (err != 0) {
			return err;
		}
	}
	return 0;
}

int picosystem_game_world_reset(struct picosystem_game_world *world)
{
	return picosystem_game_world_reset_scene(world, PICOSYSTEM_GAME_SCENE_MACHINE_LAB);
}

static int update_reversing_prismatic_drives(struct picosystem_game_world *world)
{
	if (world->physics.prismatic_joint_count == 0U) {
		return 0;
	}
	const struct picosystem_game_scene_config *const scene = scene_config(world->scene_id);
	if ((scene == NULL) ||
	    (scene->prismatic_joint_count != world->physics.prismatic_joint_count)) {
		return -ERANGE;
	}

	for (uint16_t index = 0U; index < world->physics.prismatic_joint_count; ++index) {
		if ((scene->reversing_prismatic_motor_mask & (UINT16_C(1) << index)) == 0U) {
			continue;
		}
		struct picosystem_physics_prismatic_joint *const joint =
			&world->physics.prismatic_joints[index];
		if ((joint->motor_enabled == 0U) || (joint->limit_enabled == 0U) ||
		    (joint->motor_speed_per_tick == 0)) {
			return -ERANGE;
		}

		picosystem_physics_fixed_t translation;
		int err = picosystem_physics_world_prismatic_joint_translation(&world->physics,
									       index, &translation);
		if (err != 0) {
			return err;
		}
		const bool at_lower =
			(joint->motor_speed_per_tick < 0) &&
			(translation <= (joint->lower_translation + GAME_PRISMATIC_REVERSE_SLOP));
		const bool at_upper =
			(joint->motor_speed_per_tick > 0) &&
			(translation >= (joint->upper_translation - GAME_PRISMATIC_REVERSE_SLOP));
		if (at_lower || at_upper) {
			err = picosystem_physics_world_set_prismatic_motor_speed(
				&world->physics, index, -joint->motor_speed_per_tick);
			if (err != 0) {
				return err;
			}
		}
	}
	return 0;
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

static int step_granular_world(struct picosystem_game_world *world,
			       const struct picosystem_physics_vector *acceleration,
			       const struct picosystem_physics_clock *clock,
			       struct picosystem_granular_step_profile *profile)
{
	const int err = picosystem_granular_world_step_profiled(&world->granular, acceleration,
								clock, profile);
	if (err != 0) {
		return err;
	}
	world->sensor_entry_count = world->granular.passage_count;
	update_granular_focus_proxy(world);
	increment_saturated(&world->logic_tick_count);
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
	const struct picosystem_physics_vector acceleration = {
		.x = input->horizontal * GAME_CONTROL_PER_TICK,
		.y = GAME_GRAVITY_PER_TICK + (input->vertical * GAME_CONTROL_PER_TICK),
	};
	if (world->scene_id == PICOSYSTEM_GAME_SCENE_HOURGLASS) {
		if ((mode != PICOSYSTEM_PHYSICS_STEP_MODE_GRID) || (clock != NULL) ||
		    (profile != NULL)) {
			return -ENOTSUP;
		}
		return step_granular_world(world, &acceleration, NULL, NULL);
	}
	int err = update_reversing_prismatic_drives(world);
	if (err != 0) {
		return err;
	}

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

int picosystem_game_world_flip(struct picosystem_game_world *world)
{
	if (world == NULL) {
		return -EINVAL;
	}
	if (world->scene_id != PICOSYSTEM_GAME_SCENE_HOURGLASS) {
		return -ENOTSUP;
	}
	const int err = picosystem_granular_world_flip(&world->granular);
	if (err == 0) {
		update_granular_focus_proxy(world);
	}
	return err;
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

int picosystem_game_world_step_granular_profiled(struct picosystem_game_world *world,
						 const struct picosystem_game_input *input,
						 const struct picosystem_physics_clock *clock,
						 struct picosystem_granular_step_profile *profile)
{
	if ((world == NULL) || (input == NULL)) {
		return -EINVAL;
	}
	if ((input->horizontal < -1) || (input->horizontal > 1) || (input->vertical < -1) ||
	    (input->vertical > 1)) {
		return -ERANGE;
	}
	if (world->scene_id != PICOSYSTEM_GAME_SCENE_HOURGLASS) {
		return -ENOTSUP;
	}
	const struct picosystem_physics_vector acceleration = {
		.x = input->horizontal * GAME_CONTROL_PER_TICK,
		.y = GAME_GRAVITY_PER_TICK + (input->vertical * GAME_CONTROL_PER_TICK),
	};
	return step_granular_world(world, &acceleration, clock, profile);
}

const struct picosystem_physics_body *
picosystem_game_world_focus_body(const struct picosystem_game_world *world)
{
	if (world == NULL) {
		return NULL;
	}
	if (world->scene_id == PICOSYSTEM_GAME_SCENE_HOURGLASS) {
		return (world->granular.particle_count != 0U) ? &world->focus_proxy : NULL;
	}
	return picosystem_physics_world_body_at(&world->physics, PICOSYSTEM_GAME_FOCUS_BODY_INDEX);
}

enum picosystem_game_body_render_style
picosystem_game_world_body_render_style(const struct picosystem_game_world *world, size_t index)
{
	if ((world == NULL) || (world->scene_id == PICOSYSTEM_GAME_SCENE_HOURGLASS) ||
	    (index >= world->physics.body_count) || (index >= 16U)) {
		return PICOSYSTEM_GAME_BODY_RENDER_STYLE_DEFAULT;
	}
	const struct picosystem_game_scene_config *const scene = scene_config(world->scene_id);
	if ((scene != NULL) && ((scene->gear_body_mask & (UINT16_C(1) << index)) != 0U)) {
		return PICOSYSTEM_GAME_BODY_RENDER_STYLE_GEAR;
	}
	return PICOSYSTEM_GAME_BODY_RENDER_STYLE_DEFAULT;
}

uint32_t picosystem_game_world_hash(const struct picosystem_game_world *world)
{
	if ((world == NULL) || (world->scene_id >= PICOSYSTEM_GAME_SCENE_COUNT)) {
		return 0U;
	}

	uint32_t hash = fnv1a_u32(FNV1A_OFFSET_BASIS, GAME_WORLD_HASH_VERSION);
	hash = fnv1a_u32(hash, world->scene_id);
	hash = fnv1a_u32(hash, world->logic_tick_count);
	hash = fnv1a_u32(hash, world->sensor_entry_count);
	if (world->scene_id == PICOSYSTEM_GAME_SCENE_HOURGLASS) {
		const uint32_t granular_hash = picosystem_granular_world_hash(&world->granular);
		return (granular_hash != 0U) ? fnv1a_u32(hash, granular_hash) : 0U;
	}
	if ((world->physics.body_count > PICOSYSTEM_PHYSICS_MAX_BODIES) ||
	    (world->physics.static_segment_count > PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS) ||
	    (world->physics.distance_joint_count > PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS) ||
	    (world->physics.revolute_joint_count > PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS) ||
	    (world->physics.prismatic_joint_count > PICOSYSTEM_PHYSICS_MAX_PRISMATIC_JOINTS) ||
	    (world->physics.box_sensor_count > PICOSYSTEM_PHYSICS_MAX_BOX_SENSORS) ||
	    (world->physics.rope_count > PICOSYSTEM_PHYSICS_MAX_ROPES)) {
		return 0U;
	}
	const uint32_t physics_hash = picosystem_physics_world_hash(&world->physics);
	return (physics_hash != 0U) ? fnv1a_u32(hash, physics_hash) : 0U;
}
