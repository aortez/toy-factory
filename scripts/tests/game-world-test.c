/* SPDX-License-Identifier: Apache-2.0 */

#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "game_world.h"
#include "physics_chain_fixture.h"

#define EXPECTED_RESET_HASH            UINT32_C(0x3fc3de22)
#define EXPECTED_RIGHT_15_HASH         UINT32_C(0xfff75d40)
#define EXPECTED_RIGHT_15_UP_8_HASH    UINT32_C(0x1bc0f502)
#define EXPECTED_REPLAY_10000_HASH     UINT32_C(0xc6e1c977)
#define EXPECTED_SLEEP_SMOKE_HASH      UINT32_C(0x7d016466)
#define EXPECTED_SLEEP_SMOKE_TICK      259U
#define EXPECTED_CLOCKWORK_RESET_HASH  UINT32_C(0x13d7f3d0)
#define EXPECTED_CLOCKWORK_INPUT_HASH  UINT32_C(0xe7a7ba97)
#define EXPECTED_CLOCKWORK_3000_HASH   UINT32_C(0x0152ec75)
#define EXPECTED_MARBLE_RESET_HASH     UINT32_C(0xb8ba5cef)
#define EXPECTED_MARBLE_INPUT_HASH     UINT32_C(0xee7a9565)
#define EXPECTED_MARBLE_2400_HASH      UINT32_C(0xa1fb5de3)
#define EXPECTED_MARBLE_NEUTRAL_HASH   UINT32_C(0xfed080d5)
#define MARBLE_BODY_COUNT              9U
#define MARBLE_NEUTRAL_TICK_COUNT      6000U
#define MARBLE_FIRST_BODY_ID           701U
#define MARBLE_ALL_BODY_MASK           UINT16_C(0x01ff)
#define MARBLE_MINIMUM_LATE_TRAVEL     PICOSYSTEM_PHYSICS_FIXED_FROM_INT(140)
#define MARBLE_UPPER_RAMP_INDEX        4U
#define MARBLE_LOWER_RAMP_INDEX        5U
#define MARBLE_PADDLE_BODY_INDEX       MARBLE_BODY_COUNT
#define MARBLE_LAUNCHER_BODY_INDEX     (MARBLE_BODY_COUNT + 1U)
#define MARBLE_ACCUMULATOR_BODY_INDEX  (MARBLE_BODY_COUNT + 2U)
#define MARBLE_HOPPER_MAX_X            PICOSYSTEM_PHYSICS_FIXED_FROM_INT(64)
#define MARBLE_HOPPER_MIN_Y            PICOSYSTEM_PHYSICS_FIXED_FROM_INT(210)
#define MARBLE_ELEVATOR_MAX_X          PICOSYSTEM_PHYSICS_FIXED_FROM_INT(35)
#define MARBLE_ELEVATOR_ADMISSION_Y    PICOSYSTEM_PHYSICS_FIXED_FROM_INT(210)
#define MARBLE_ELEVATOR_REARM_Y        PICOSYSTEM_PHYSICS_FIXED_FROM_INT(222)
#define MARBLE_UPPER_RAMP_MIDDLE_MIN_X PICOSYSTEM_PHYSICS_FIXED_FROM_INT(70)
#define MARBLE_UPPER_RAMP_MIDDLE_MAX_X PICOSYSTEM_PHYSICS_FIXED_FROM_INT(92)
#define MARBLE_LOWER_RAMP_MIDDLE_MIN_X PICOSYSTEM_PHYSICS_FIXED_FROM_INT(140)
#define MARBLE_LOWER_RAMP_MIDDLE_MAX_X PICOSYSTEM_PHYSICS_FIXED_FROM_INT(200)
#define BOUNDARY_TOLERANCE             PICOSYSTEM_PHYSICS_FIXED_FROM_INT(3)
#define ROPE_BOUNDARY_TOLERANCE        PICOSYSTEM_PHYSICS_FIXED_RATIO(1, 64)
#define CHAIN_CONVERGENCE_TOLERANCE    PICOSYSTEM_PHYSICS_FIXED_FROM_INT(2)
#define ANGULAR_BOUNDARY_TOLERANCE     PICOSYSTEM_PHYSICS_FIXED_RATIO(1, 12)
#if defined(CONFIG_TOY_FACTORY_HOURGLASS_GRAINS_96)
#define EXPECTED_HOURGLASS_GRAIN_COUNT 96U
#elif defined(CONFIG_TOY_FACTORY_HOURGLASS_GRAINS_192)
#define EXPECTED_HOURGLASS_GRAIN_COUNT 192U
#elif defined(CONFIG_TOY_FACTORY_HOURGLASS_GRAINS_384)
#define EXPECTED_HOURGLASS_GRAIN_COUNT 384U
#else
#define EXPECTED_HOURGLASS_GRAIN_COUNT 320U
#endif
#define EXPECTED_HOURGLASS_DRAIN_COUNT (EXPECTED_HOURGLASS_GRAIN_COUNT - 20U)
#define CANONICAL_POSSIBLE_PAIR_COUNT                                                              \
	(((PICOSYSTEM_GAME_BODY_COUNT * (PICOSYSTEM_GAME_BODY_COUNT - 1U)) / 2U) +                 \
	 (PICOSYSTEM_GAME_BODY_COUNT * PICOSYSTEM_GAME_STATIC_SEGMENT_COUNT) +                     \
	 (PICOSYSTEM_GAME_BODY_COUNT * PICOSYSTEM_GAME_BOX_SENSOR_COUNT))

static void assert_vector_equal(const struct picosystem_physics_vector *left,
				const struct picosystem_physics_vector *right)
{
	assert(left->x == right->x);
	assert(left->y == right->y);
}

static void assert_world_equal(const struct picosystem_game_world *left,
			       const struct picosystem_game_world *right)
{
	assert(left->logic_tick_count == right->logic_tick_count);
	assert(left->sensor_entry_count == right->sensor_entry_count);
	assert(left->scene_id == right->scene_id);
	assert(left->physics.max_speed_per_tick == right->physics.max_speed_per_tick);
	assert(left->physics.body_count == right->physics.body_count);
	assert(left->physics.static_segment_count == right->physics.static_segment_count);
	assert(left->physics.distance_joint_count == right->physics.distance_joint_count);
	assert(left->physics.revolute_joint_count == right->physics.revolute_joint_count);
	assert(left->physics.prismatic_joint_count == right->physics.prismatic_joint_count);
	assert(left->physics.box_sensor_count == right->physics.box_sensor_count);
	assert(left->physics.rope_count == right->physics.rope_count);
	assert(left->physics.contact_count == right->physics.contact_count);
	assert(left->physics.contact_event_count == right->physics.contact_event_count);
	assert(left->physics.sleeping_body_mask == right->physics.sleeping_body_mask);
	assert_vector_equal(&left->physics.last_global_acceleration_per_tick,
			    &right->physics.last_global_acceleration_per_tick);
	assert(left->physics.last_candidate_pair_count == right->physics.last_candidate_pair_count);
	assert(left->physics.last_possible_pair_count == right->physics.last_possible_pair_count);
	assert(left->physics.last_occupied_grid_cell_count ==
	       right->physics.last_occupied_grid_cell_count);
	assert(left->physics.last_broad_phase_fallback == right->physics.last_broad_phase_fallback);
	assert(left->physics.last_solver_iteration_count ==
	       right->physics.last_solver_iteration_count);
	for (size_t index = 0U; index < PICOSYSTEM_PHYSICS_GRID_CELL_COUNT; ++index) {
		assert(left->physics.grid_cells[index].body_mask ==
		       right->physics.grid_cells[index].body_mask);
		assert(left->physics.grid_cells[index].static_segment_mask ==
		       right->physics.grid_cells[index].static_segment_mask);
		assert(left->physics.grid_cells[index].box_sensor_mask ==
		       right->physics.grid_cells[index].box_sensor_mask);
	}

	for (uint16_t index = 0U; index < left->physics.body_count; ++index) {
		const struct picosystem_physics_body *const left_body =
			&left->physics.bodies[index];
		const struct picosystem_physics_body *const right_body =
			&right->physics.bodies[index];
		assert_vector_equal(&left_body->center, &right_body->center);
		assert_vector_equal(&left_body->velocity_per_tick, &right_body->velocity_per_tick);
		assert_vector_equal(&left_body->half_extent, &right_body->half_extent);
		assert(left_body->radius == right_body->radius);
		assert(left_body->inverse_mass == right_body->inverse_mass);
		assert(left_body->inverse_inertia == right_body->inverse_inertia);
		assert(left_body->restitution == right_body->restitution);
		assert(left_body->friction == right_body->friction);
		assert(left_body->angular_velocity_per_tick ==
		       right_body->angular_velocity_per_tick);
		assert(left_body->angle_turns == right_body->angle_turns);
		assert(left_body->id == right_body->id);
		assert(left_body->shape == right_body->shape);
		assert(left->physics.solver_velocity_revisions[index] ==
		       right->physics.solver_velocity_revisions[index]);
		assert(left->physics.active_body_contact_masks[index] ==
		       right->physics.active_body_contact_masks[index]);
		assert(left->physics.active_segment_contact_masks[index] ==
		       right->physics.active_segment_contact_masks[index]);
		assert(left->physics.active_sensor_contact_masks[index] ==
		       right->physics.active_sensor_contact_masks[index]);
		assert(left->physics.sleep_quiet_tick_counts[index] ==
		       right->physics.sleep_quiet_tick_counts[index]);
	}

	for (uint16_t index = 0U; index < left->physics.box_sensor_count; ++index) {
		const struct picosystem_physics_box_sensor *const left_sensor =
			&left->physics.box_sensors[index];
		const struct picosystem_physics_box_sensor *const right_sensor =
			&right->physics.box_sensors[index];
		assert_vector_equal(&left_sensor->center, &right_sensor->center);
		assert_vector_equal(&left_sensor->half_extent, &right_sensor->half_extent);
		assert(left_sensor->id == right_sensor->id);
	}

	for (uint16_t index = 0U; index < left->physics.rope_count; ++index) {
		const struct picosystem_physics_rope *const left_rope = &left->physics.ropes[index];
		const struct picosystem_physics_rope *const right_rope =
			&right->physics.ropes[index];
		assert_vector_equal(&left_rope->anchor_a, &right_rope->anchor_a);
		assert_vector_equal(&left_rope->anchor_b, &right_rope->anchor_b);
		assert(left_rope->segment_length == right_rope->segment_length);
		assert(left_rope->id == right_rope->id);
		assert(left_rope->body_a_id == right_rope->body_a_id);
		assert(left_rope->body_b_id == right_rope->body_b_id);
		assert(left_rope->body_a_index == right_rope->body_a_index);
		assert(left_rope->body_b_index == right_rope->body_b_index);
		assert(left_rope->particle_count == right_rope->particle_count);
		assert(left_rope->pin_a == right_rope->pin_a);
		assert(left_rope->pin_b == right_rope->pin_b);
		for (uint8_t particle = 0U; particle < left_rope->particle_count; ++particle) {
			assert_vector_equal(&left_rope->particles[particle].position,
					    &right_rope->particles[particle].position);
			assert_vector_equal(&left_rope->particles[particle].previous_position,
					    &right_rope->particles[particle].previous_position);
		}
	}

	for (uint16_t index = 0U; index < left->physics.contact_event_count; ++index) {
		const struct picosystem_physics_contact_event *const left_event =
			&left->physics.contact_events[index];
		const struct picosystem_physics_contact_event *const right_event =
			&right->physics.contact_events[index];
		assert(left_event->body_a_id == right_event->body_a_id);
		assert(left_event->body_b_id == right_event->body_b_id);
		assert(left_event->type == right_event->type);
		assert(left_event->phase == right_event->phase);
	}

	for (uint16_t index = 0U; index < left->physics.static_segment_count; ++index) {
		const struct picosystem_physics_static_segment *const left_segment =
			&left->physics.static_segments[index];
		const struct picosystem_physics_static_segment *const right_segment =
			&right->physics.static_segments[index];
		assert_vector_equal(&left_segment->start, &right_segment->start);
		assert_vector_equal(&left_segment->end, &right_segment->end);
		assert_vector_equal(&left_segment->normal, &right_segment->normal);
		assert(left_segment->restitution == right_segment->restitution);
		assert(left_segment->friction == right_segment->friction);
		assert(left_segment->surface_speed_per_tick ==
		       right_segment->surface_speed_per_tick);
		assert(left_segment->id == right_segment->id);
	}

	for (uint16_t index = 0U; index < left->physics.distance_joint_count; ++index) {
		const struct picosystem_physics_distance_joint *const left_joint =
			&left->physics.distance_joints[index];
		const struct picosystem_physics_distance_joint *const right_joint =
			&right->physics.distance_joints[index];
		assert_vector_equal(&left_joint->local_anchor_a, &right_joint->local_anchor_a);
		assert_vector_equal(&left_joint->anchor_b, &right_joint->anchor_b);
		assert(left_joint->target_distance == right_joint->target_distance);
		assert(left_joint->spring_angular_frequency_per_tick ==
		       right_joint->spring_angular_frequency_per_tick);
		assert(left_joint->spring_damping_ratio == right_joint->spring_damping_ratio);
		assert(left_joint->maximum_spring_impulse_per_tick ==
		       right_joint->maximum_spring_impulse_per_tick);
		assert(left_joint->id == right_joint->id);
		assert(left_joint->body_a_id == right_joint->body_a_id);
		assert(left_joint->body_b_id == right_joint->body_b_id);
		assert(left_joint->body_a_index == right_joint->body_a_index);
		assert(left_joint->body_b_index == right_joint->body_b_index);
		assert(left_joint->spring_enabled == right_joint->spring_enabled);
		assert_vector_equal(&left_joint->world_anchor_a, &right_joint->world_anchor_a);
		assert_vector_equal(&left_joint->world_anchor_b, &right_joint->world_anchor_b);
		assert_vector_equal(&left_joint->normal, &right_joint->normal);
		assert(left_joint->direction_inverse_mass == right_joint->direction_inverse_mass);
		assert(left_joint->accumulated_impulse == right_joint->accumulated_impulse);
		assert(left_joint->spring_softness == right_joint->spring_softness);
		assert(left_joint->spring_bias_velocity == right_joint->spring_bias_velocity);
	}

	for (uint16_t index = 0U; index < left->physics.revolute_joint_count; ++index) {
		const struct picosystem_physics_revolute_joint *const left_joint =
			&left->physics.revolute_joints[index];
		const struct picosystem_physics_revolute_joint *const right_joint =
			&right->physics.revolute_joints[index];
		assert_vector_equal(&left_joint->local_anchor_a, &right_joint->local_anchor_a);
		assert_vector_equal(&left_joint->anchor_b, &right_joint->anchor_b);
		assert(left_joint->id == right_joint->id);
		assert(left_joint->body_a_id == right_joint->body_a_id);
		assert(left_joint->body_b_id == right_joint->body_b_id);
		assert(left_joint->body_a_index == right_joint->body_a_index);
		assert(left_joint->body_b_index == right_joint->body_b_index);
		assert(left_joint->collide_connected == right_joint->collide_connected);
		assert(left_joint->motor_enabled == right_joint->motor_enabled);
		assert(left_joint->limit_enabled == right_joint->limit_enabled);
		assert(left_joint->motor_speed_per_tick == right_joint->motor_speed_per_tick);
		assert(left_joint->maximum_motor_impulse_per_tick ==
		       right_joint->maximum_motor_impulse_per_tick);
		assert(left_joint->lower_angle_radians == right_joint->lower_angle_radians);
		assert(left_joint->upper_angle_radians == right_joint->upper_angle_radians);
		assert(left_joint->reference_angle_turns == right_joint->reference_angle_turns);
		assert_vector_equal(&left_joint->world_anchor_a, &right_joint->world_anchor_a);
		assert_vector_equal(&left_joint->world_anchor_b, &right_joint->world_anchor_b);
		assert_vector_equal(&left_joint->accumulated_impulse,
				    &right_joint->accumulated_impulse);
		assert(left_joint->effective_mass_xx == right_joint->effective_mass_xx);
		assert(left_joint->effective_mass_xy == right_joint->effective_mass_xy);
		assert(left_joint->effective_mass_yy == right_joint->effective_mass_yy);
		assert(left_joint->angular_effective_mass == right_joint->angular_effective_mass);
		assert(left_joint->accumulated_motor_impulse ==
		       right_joint->accumulated_motor_impulse);
		assert(left_joint->accumulated_limit_impulse ==
		       right_joint->accumulated_limit_impulse);
		assert(left_joint->effective_mass_valid == right_joint->effective_mass_valid);
		assert(left_joint->limit_state == right_joint->limit_state);
	}

	for (uint16_t index = 0U; index < left->physics.prismatic_joint_count; ++index) {
		const struct picosystem_physics_prismatic_joint *const left_joint =
			&left->physics.prismatic_joints[index];
		const struct picosystem_physics_prismatic_joint *const right_joint =
			&right->physics.prismatic_joints[index];
		assert_vector_equal(&left_joint->local_anchor_a, &right_joint->local_anchor_a);
		assert_vector_equal(&left_joint->anchor_b, &right_joint->anchor_b);
		assert_vector_equal(&left_joint->axis_b, &right_joint->axis_b);
		assert(left_joint->motor_speed_per_tick == right_joint->motor_speed_per_tick);
		assert(left_joint->maximum_motor_impulse_per_tick ==
		       right_joint->maximum_motor_impulse_per_tick);
		assert(left_joint->lower_translation == right_joint->lower_translation);
		assert(left_joint->upper_translation == right_joint->upper_translation);
		assert(left_joint->reference_translation == right_joint->reference_translation);
		assert(left_joint->reference_angle_turns == right_joint->reference_angle_turns);
		assert(left_joint->id == right_joint->id);
		assert(left_joint->body_a_id == right_joint->body_a_id);
		assert(left_joint->body_b_id == right_joint->body_b_id);
		assert(left_joint->body_a_index == right_joint->body_a_index);
		assert(left_joint->body_b_index == right_joint->body_b_index);
		assert(left_joint->collide_connected == right_joint->collide_connected);
		assert(left_joint->motor_enabled == right_joint->motor_enabled);
		assert(left_joint->limit_enabled == right_joint->limit_enabled);
		assert_vector_equal(&left_joint->world_anchor_a, &right_joint->world_anchor_a);
		assert_vector_equal(&left_joint->world_anchor_b, &right_joint->world_anchor_b);
		assert_vector_equal(&left_joint->world_axis, &right_joint->world_axis);
		assert_vector_equal(&left_joint->world_perpendicular,
				    &right_joint->world_perpendicular);
		assert(left_joint->lateral_effective_mass == right_joint->lateral_effective_mass);
		assert(left_joint->axial_effective_mass == right_joint->axial_effective_mass);
		assert(left_joint->angular_effective_mass == right_joint->angular_effective_mass);
		assert(left_joint->accumulated_lateral_impulse ==
		       right_joint->accumulated_lateral_impulse);
		assert(left_joint->accumulated_angular_impulse ==
		       right_joint->accumulated_angular_impulse);
		assert(left_joint->accumulated_motor_impulse ==
		       right_joint->accumulated_motor_impulse);
		assert(left_joint->accumulated_limit_impulse ==
		       right_joint->accumulated_limit_impulse);
		assert(left_joint->solved_velocity_revision_a ==
		       right_joint->solved_velocity_revision_a);
		assert(left_joint->solved_velocity_revision_b ==
		       right_joint->solved_velocity_revision_b);
		assert(left_joint->limit_state == right_joint->limit_state);
		assert(left_joint->solved_velocity_valid == right_joint->solved_velocity_valid);
	}
}

static void assert_hash(const char *label, uint32_t actual, uint32_t expected)
{
	if (actual != expected) {
		fprintf(stderr, "%s hash: %08x\n", label, actual);
	}
	assert(actual == expected);
}

static void test_scene_catalog(void)
{
	assert(strcmp(picosystem_game_scene_name(PICOSYSTEM_GAME_SCENE_CLOCKWORK), "clockwork") ==
	       0);
	assert(strcmp(picosystem_game_scene_name(PICOSYSTEM_GAME_SCENE_HOURGLASS), "hourglass") ==
	       0);
	assert(strcmp(picosystem_game_scene_name(PICOSYSTEM_GAME_SCENE_MARBLE_MACHINE),
		      "marble-machine") == 0);
	assert(strcmp(picosystem_game_scene_name(PICOSYSTEM_GAME_SCENE_MACHINE_LAB),
		      "machine-lab") == 0);
	assert(strcmp(picosystem_game_scene_name(PICOSYSTEM_GAME_SCENE_DIAGNOSTIC_CHAIN),
		      "diagnostic-chain") == 0);
	assert(strcmp(picosystem_game_scene_name(PICOSYSTEM_GAME_SCENE_COUNT), "unknown") == 0);

	assert(picosystem_game_scene_is_selectable(PICOSYSTEM_GAME_SCENE_CLOCKWORK));
	assert(picosystem_game_scene_is_selectable(PICOSYSTEM_GAME_SCENE_HOURGLASS));
	assert(picosystem_game_scene_is_selectable(PICOSYSTEM_GAME_SCENE_MARBLE_MACHINE));
	assert(!picosystem_game_scene_is_selectable(PICOSYSTEM_GAME_SCENE_MACHINE_LAB));
	assert(!picosystem_game_scene_is_selectable(PICOSYSTEM_GAME_SCENE_DIAGNOSTIC_CHAIN));

	enum picosystem_game_scene_id next_scene_id = PICOSYSTEM_GAME_SCENE_COUNT;
	assert(picosystem_game_scene_next(PICOSYSTEM_GAME_SCENE_CLOCKWORK, &next_scene_id) == 0);
	assert(next_scene_id == PICOSYSTEM_GAME_SCENE_HOURGLASS);
	assert(picosystem_game_scene_next(PICOSYSTEM_GAME_SCENE_HOURGLASS, &next_scene_id) == 0);
	assert(next_scene_id == PICOSYSTEM_GAME_SCENE_MARBLE_MACHINE);
	assert(picosystem_game_scene_next(PICOSYSTEM_GAME_SCENE_MARBLE_MACHINE, &next_scene_id) ==
	       0);
	assert(next_scene_id == PICOSYSTEM_GAME_SCENE_CLOCKWORK);
	next_scene_id = PICOSYSTEM_GAME_SCENE_HOURGLASS;
	assert(picosystem_game_scene_next(PICOSYSTEM_GAME_SCENE_MACHINE_LAB, &next_scene_id) ==
	       -ENOTSUP);
	assert(next_scene_id == PICOSYSTEM_GAME_SCENE_HOURGLASS);
	assert(picosystem_game_scene_next(PICOSYSTEM_GAME_SCENE_CLOCKWORK, NULL) == -EINVAL);

	enum picosystem_game_scene_id found_scene = PICOSYSTEM_GAME_SCENE_COUNT;
	assert(picosystem_game_scene_find_selectable("marble-machine", &found_scene) == 0);
	assert(found_scene == PICOSYSTEM_GAME_SCENE_MARBLE_MACHINE);
	assert(picosystem_game_scene_find_selectable("machine-lab", &found_scene) == -ENOENT);
	assert(found_scene == PICOSYSTEM_GAME_SCENE_MARBLE_MACHINE);
	assert(picosystem_game_scene_find_selectable(NULL, &found_scene) == -EINVAL);
	assert(picosystem_game_scene_find_selectable("clockwork", NULL) == -EINVAL);
}

static void step_many(struct picosystem_game_world *world,
		      const struct picosystem_game_input *input, uint32_t count)
{
	for (uint32_t step = 0U; step < count; ++step) {
		assert(picosystem_game_world_step(world, input) == 0);
	}
}

static void test_canonical_reset_and_golden_replay(void)
{
	struct picosystem_game_world world;
	assert(picosystem_game_world_reset(&world) == 0);
	assert(world.logic_tick_count == 0U);
	assert(world.physics.body_count == PICOSYSTEM_GAME_BODY_COUNT);
	assert(world.physics.static_segment_count == PICOSYSTEM_GAME_STATIC_SEGMENT_COUNT);
	assert(world.physics.distance_joint_count == PICOSYSTEM_GAME_DISTANCE_JOINT_COUNT);
	assert(world.physics.revolute_joint_count == PICOSYSTEM_GAME_REVOLUTE_JOINT_COUNT);
	assert(world.physics.prismatic_joint_count == PICOSYSTEM_GAME_PRISMATIC_JOINT_COUNT);
	assert(world.physics.box_sensor_count == PICOSYSTEM_GAME_BOX_SENSOR_COUNT);
	assert(world.physics.rope_count == PICOSYSTEM_GAME_ROPE_COUNT);
	assert(world.physics.contact_count == 0U);
	assert(world.physics.contact_event_count == 0U);
	assert(world.sensor_entry_count == 0U);
	assert(world.physics.revolute_joints[0].motor_enabled == 1U);
	assert(world.physics.revolute_joints[0].limit_enabled == 0U);
	for (uint16_t index = 1U; index < (world.physics.revolute_joint_count - 1U); ++index) {
		assert(world.physics.revolute_joints[index].motor_enabled == 0U);
		assert(world.physics.revolute_joints[index].limit_enabled == 0U);
	}
	const struct picosystem_physics_revolute_joint *const final_revolute =
		&world.physics.revolute_joints[world.physics.revolute_joint_count - 1U];
	assert(final_revolute->motor_enabled == 0U);
	assert(final_revolute->limit_enabled == 1U);
	assert(world.physics.prismatic_joints[0].motor_enabled == 1U);
	assert(world.physics.prismatic_joints[0].limit_enabled == 1U);
	assert(world.physics.prismatic_joints[0].motor_speed_per_tick < 0);
	assert(world.physics.distance_joints[0].spring_enabled == 1U);
	assert(world.physics.static_segments[4].surface_speed_per_tick > 0);
	assert(world.physics.ropes[0].particle_count == 8U);
	assert(world.physics.ropes[0].segment_length == PICOSYSTEM_PHYSICS_FIXED_FROM_INT(18));
	assert(world.physics.ropes[0].body_a_id == 4U);
	assert(world.physics.ropes[0].pin_a == 1U);
	assert(world.physics.ropes[0].pin_b == 1U);

	const struct picosystem_physics_body *const focus =
		picosystem_game_world_focus_body(&world);
	assert(focus != NULL);
	assert(focus->id == 1U);
	assert(focus->center.x == PICOSYSTEM_PHYSICS_FIXED_FROM_INT(55));
	assert(focus->center.y == PICOSYSTEM_PHYSICS_FIXED_FROM_INT(55));
	assert(focus->shape == PICOSYSTEM_PHYSICS_SHAPE_BOX);
	assert(focus->half_extent.x == PICOSYSTEM_PHYSICS_FIXED_FROM_INT(10));
	assert(focus->half_extent.y == PICOSYSTEM_PHYSICS_FIXED_FROM_INT(7));
	assert_hash("reset", picosystem_game_world_hash(&world), EXPECTED_RESET_HASH);

	const struct picosystem_game_input right = {.horizontal = 1};
	step_many(&world, &right, 15U);
	assert(world.logic_tick_count == 15U);
	assert_hash("right-15", picosystem_game_world_hash(&world), EXPECTED_RIGHT_15_HASH);

	const struct picosystem_game_input up = {.vertical = -1};
	step_many(&world, &up, 8U);
	assert(world.logic_tick_count == 23U);
	assert_hash("right-15-up-8", picosystem_game_world_hash(&world),
		    EXPECTED_RIGHT_15_UP_8_HASH);

	assert(picosystem_game_world_reset(&world) == 0);
	assert_hash("reset-after-replay", picosystem_game_world_hash(&world), EXPECTED_RESET_HASH);
}

static void test_validation_preserves_state(void)
{
	struct picosystem_game_world world;
	assert(picosystem_game_world_reset(&world) == 0);

	const struct picosystem_game_world baseline = world;
	const struct picosystem_game_input invalid_horizontal = {.horizontal = 2};
	assert(picosystem_game_world_step(&world, &invalid_horizontal) == -ERANGE);
	assert_world_equal(&world, &baseline);

	const struct picosystem_game_input invalid_vertical = {.vertical = -2};
	assert(picosystem_game_world_step(&world, &invalid_vertical) == -ERANGE);
	assert_world_equal(&world, &baseline);

	const struct picosystem_game_input neutral = {0};
	world.physics.max_speed_per_tick = 0;
	const struct picosystem_game_world invalid_speed = world;
	assert(picosystem_game_world_step(&world, &neutral) == -ERANGE);
	assert_world_equal(&world, &invalid_speed);

	assert(picosystem_game_world_reset(&world) == 0);
	world.physics.bodies[0].id = 0U;
	const struct picosystem_game_world invalid_id = world;
	assert(picosystem_game_world_step(&world, &neutral) == -ERANGE);
	assert_world_equal(&world, &invalid_id);

	assert(picosystem_game_world_reset(NULL) == -EINVAL);
	assert(picosystem_game_world_step(NULL, &neutral) == -EINVAL);
	assert(picosystem_game_world_step(&world, NULL) == -EINVAL);
	assert(picosystem_game_world_focus_body(NULL) == NULL);
	assert(picosystem_game_world_hash(NULL) == 0U);
	assert(picosystem_game_world_reset(&world) == 0);
	world.physics.body_count = PICOSYSTEM_PHYSICS_MAX_BODIES + 1U;
	assert(picosystem_game_world_hash(&world) == 0U);
	assert(picosystem_game_world_reset(&world) == 0);
	world.physics.distance_joint_count = PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS + 1U;
	assert(picosystem_game_world_hash(&world) == 0U);
	assert(picosystem_game_world_reset(&world) == 0);
	world.physics.revolute_joint_count = PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS + 1U;
	assert(picosystem_game_world_hash(&world) == 0U);
	assert(picosystem_game_world_reset(&world) == 0);
	world.physics.prismatic_joint_count = PICOSYSTEM_PHYSICS_MAX_PRISMATIC_JOINTS + 1U;
	assert(picosystem_game_world_hash(&world) == 0U);
	assert(picosystem_game_world_reset(&world) == 0);
	world.physics.rope_count = PICOSYSTEM_PHYSICS_MAX_ROPES + 1U;
	assert(picosystem_game_world_hash(&world) == 0U);
	assert(picosystem_game_world_reset(&world) == 0);
	world.physics.ropes[0].particle_count = 1U;
	assert(picosystem_game_world_hash(&world) == 0U);
}

static uint64_t vector_distance_squared(const struct picosystem_physics_vector *left,
					const struct picosystem_physics_vector *right)
{
	const int64_t x = (int64_t)right->x - left->x;
	const int64_t y = (int64_t)right->y - left->y;
	return (uint64_t)((x * x) + (y * y));
}

static uint64_t maximum_revolute_error_squared(const struct picosystem_game_world *world)
{
	uint64_t maximum = 0U;
	for (uint16_t index = 0U; index < world->physics.revolute_joint_count; ++index) {
		struct picosystem_physics_vector anchor_a;
		struct picosystem_physics_vector anchor_b;
		assert(picosystem_physics_world_revolute_joint_anchors(&world->physics, index,
								       &anchor_a, &anchor_b) == 0);
		const uint64_t distance_squared = vector_distance_squared(&anchor_a, &anchor_b);
		if (distance_squared > maximum) {
			maximum = distance_squared;
		}
	}
	return maximum;
}

static void assert_joint_lengths_bounded(const struct picosystem_game_world *world)
{
	const int32_t tolerance = PICOSYSTEM_PHYSICS_FIXED_FROM_INT(3);
	for (uint16_t index = 0U; index < world->physics.distance_joint_count; ++index) {
		if (world->physics.distance_joints[index].spring_enabled != 0U) {
			continue;
		}
		struct picosystem_physics_vector anchor_a;
		struct picosystem_physics_vector anchor_b;
		assert(picosystem_physics_world_distance_joint_endpoints(
			       &world->physics, index, &anchor_a, &anchor_b) == 0);
		const int32_t target = world->physics.distance_joints[index].target_distance;
		const int64_t minimum = target - tolerance;
		const int64_t maximum = target + tolerance;
		const uint64_t distance_squared = vector_distance_squared(&anchor_a, &anchor_b);
		assert(distance_squared >= (uint64_t)(minimum * minimum));
		assert(distance_squared <= (uint64_t)(maximum * maximum));
	}
	for (uint16_t index = 0U; index < world->physics.revolute_joint_count; ++index) {
		const struct picosystem_physics_revolute_joint *const joint =
			&world->physics.revolute_joints[index];
		struct picosystem_physics_vector anchor_a;
		struct picosystem_physics_vector anchor_b;
		assert(picosystem_physics_world_revolute_joint_anchors(&world->physics, index,
								       &anchor_a, &anchor_b) == 0);
		const uint64_t distance_squared = vector_distance_squared(&anchor_a, &anchor_b);
		const int64_t revolute_tolerance = BOUNDARY_TOLERANCE;
		if (distance_squared > (uint64_t)(revolute_tolerance * revolute_tolerance)) {
			fprintf(stderr,
				"revolute joint %u exceeded tolerance at tick %u: squared "
				"error=%llu\n",
				index, world->logic_tick_count,
				(unsigned long long)distance_squared);
		}
		assert(distance_squared <= (uint64_t)(revolute_tolerance * revolute_tolerance));
		if (joint->limit_enabled != 0U) {
			picosystem_physics_fixed_t angle = 0;
			assert(picosystem_physics_world_revolute_joint_angle(&world->physics, index,
									     &angle) == 0);
			if ((angle < (joint->lower_angle_radians - ANGULAR_BOUNDARY_TOLERANCE)) ||
			    (angle > (joint->upper_angle_radians + ANGULAR_BOUNDARY_TOLERANCE))) {
				const picosystem_physics_fixed_t body_b_angular_velocity =
					(joint->body_b_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID)
						? 0
						: world->physics.bodies[joint->body_b_index]
							  .angular_velocity_per_tick;
				fprintf(stderr,
					"revolute limit %u exceeded at tick %u: angle=%d "
					"range=%d..%d position=%u/%u limit_solver=%u/%u "
					"velocity=%d/%d\n",
					index, world->logic_tick_count, angle,
					joint->lower_angle_radians, joint->upper_angle_radians,
					world->physics.last_work
						.joint_limit_position_correction_changed_count,
					world->physics.last_work
						.joint_limit_position_correction_visit_count,
					world->physics.last_work.joint_limit_solver_changed_count,
					world->physics.last_work.joint_limit_solver_visit_count,
					world->physics.bodies[joint->body_a_index]
						.angular_velocity_per_tick,
					body_b_angular_velocity);
			}
			assert(angle >= (joint->lower_angle_radians - ANGULAR_BOUNDARY_TOLERANCE));
			assert(angle <= (joint->upper_angle_radians + ANGULAR_BOUNDARY_TOLERANCE));
		}
	}
	for (uint16_t index = 0U; index < world->physics.prismatic_joint_count; ++index) {
		const struct picosystem_physics_prismatic_joint *const joint =
			&world->physics.prismatic_joints[index];
		struct picosystem_physics_vector anchor_a;
		struct picosystem_physics_vector anchor_b;
		struct picosystem_physics_vector axis;
		assert(picosystem_physics_world_prismatic_joint_geometry(
			       &world->physics, index, &anchor_a, &anchor_b, &axis) == 0);
		const struct picosystem_physics_vector delta = {
			.x = anchor_a.x - anchor_b.x,
			.y = anchor_a.y - anchor_b.y,
		};
		const int64_t lateral_raw =
			((int64_t)delta.x * -axis.y) + ((int64_t)delta.y * axis.x);
		const picosystem_physics_fixed_t lateral =
			(picosystem_physics_fixed_t)(lateral_raw / PICOSYSTEM_PHYSICS_FIXED_ONE);
		assert(lateral >= -BOUNDARY_TOLERANCE);
		assert(lateral <= BOUNDARY_TOLERANCE);
		if (joint->limit_enabled != 0U) {
			picosystem_physics_fixed_t translation;
			assert(picosystem_physics_world_prismatic_joint_translation(
				       &world->physics, index, &translation) == 0);
			assert(translation >= (joint->lower_translation - BOUNDARY_TOLERANCE));
			assert(translation <= (joint->upper_translation + BOUNDARY_TOLERANCE));
		}
	}
}

static picosystem_physics_fixed_t
maximum_revolute_limit_violation(const struct picosystem_game_world *world)
{
	picosystem_physics_fixed_t maximum = 0;
	for (uint16_t index = 0U; index < world->physics.revolute_joint_count; ++index) {
		const struct picosystem_physics_revolute_joint *const joint =
			&world->physics.revolute_joints[index];
		if (joint->limit_enabled == 0U) {
			continue;
		}
		picosystem_physics_fixed_t angle = 0;
		assert(picosystem_physics_world_revolute_joint_angle(&world->physics, index,
								     &angle) == 0);
		picosystem_physics_fixed_t violation = 0;
		if (angle < joint->lower_angle_radians) {
			violation = joint->lower_angle_radians - angle;
		} else if (angle > joint->upper_angle_radians) {
			violation = angle - joint->upper_angle_radians;
		}
		if (violation > maximum) {
			maximum = violation;
		}
	}
	return maximum;
}

static picosystem_physics_fixed_t
maximum_prismatic_limit_violation(const struct picosystem_game_world *world)
{
	picosystem_physics_fixed_t maximum = 0;
	for (uint16_t index = 0U; index < world->physics.prismatic_joint_count; ++index) {
		const struct picosystem_physics_prismatic_joint *const joint =
			&world->physics.prismatic_joints[index];
		if (joint->limit_enabled == 0U) {
			continue;
		}
		picosystem_physics_fixed_t translation = 0;
		assert(picosystem_physics_world_prismatic_joint_translation(&world->physics, index,
									    &translation) == 0);
		picosystem_physics_fixed_t violation = 0;
		if (translation < joint->lower_translation) {
			violation = joint->lower_translation - translation;
		} else if (translation > joint->upper_translation) {
			violation = translation - joint->upper_translation;
		}
		if (violation > maximum) {
			maximum = violation;
		}
	}
	return maximum;
}

static void test_chain_fixture_boundaries_and_replay(void)
{
	struct picosystem_game_world world;
	assert(picosystem_game_world_reset(&world) == 0);
	const struct picosystem_game_world baseline = world;
	assert(picosystem_physics_chain_fixture_reset(NULL, 4U) == -EINVAL);
	assert(picosystem_physics_chain_fixture_reset(&world, 0U) == -ERANGE);
	assert_world_equal(&world, &baseline);
	assert(picosystem_physics_chain_fixture_reset(
		       &world, PICOSYSTEM_PHYSICS_CHAIN_FIXTURE_MAX_LINKS + 1U) == -ERANGE);
	assert_world_equal(&world, &baseline);

	static const uint16_t link_counts[] = {1U, 4U, 6U, 8U};
	static const struct picosystem_game_input neutral = {0};
	for (size_t count_index = 0U; count_index < sizeof(link_counts) / sizeof(link_counts[0]);
	     ++count_index) {
		const uint16_t link_count = link_counts[count_index];
		assert(picosystem_physics_chain_fixture_reset(&world, link_count) == 0);
		assert(world.logic_tick_count == 0U);
		assert(world.physics.body_count == link_count);
		assert(world.physics.static_segment_count == 0U);
		assert(world.physics.distance_joint_count == 0U);
		assert(world.physics.revolute_joint_count == link_count);
		assert(world.physics.prismatic_joint_count == 0U);
		assert_joint_lengths_bounded(&world);

		uint64_t maximum_error_squared = 0U;
		uint32_t extra_position_sweep_tick_count = 0U;
		for (uint32_t step = 0U; step < 560U; ++step) {
			assert(picosystem_physics_world_wake_body(&world.physics, 0U) == 0);
			assert(picosystem_game_world_step(&world, &neutral) == 0);
			const uint64_t error_squared = maximum_revolute_error_squared(&world);
			if (error_squared > maximum_error_squared) {
				maximum_error_squared = error_squared;
			}
			assert(world.physics.last_broad_phase_fallback == 0U);
			assert(world.physics.last_work.revolute_joint_count == link_count);
			assert(world.physics.last_work.joint_position_correction_visit_count >=
			       link_count);
			assert(world.physics.last_work.joint_position_correction_visit_count <=
			       link_count * PICOSYSTEM_PHYSICS_REVOLUTE_POSITION_ITERATIONS);
			assert((world.physics.last_work.joint_position_correction_visit_count %
				link_count) == 0U);
			if (world.physics.last_work.joint_position_correction_visit_count >
			    link_count) {
				++extra_position_sweep_tick_count;
			}
			assert(world.physics.last_work.joint_solver_visit_count ==
			       link_count * world.physics.last_work.solver_iteration_count);
		}
		assert(world.logic_tick_count == 560U);
		assert(picosystem_game_world_hash(&world) != 0U);
		fprintf(stderr, "chain links=%u maximum squared anchor error=%llu\n", link_count,
			(unsigned long long)maximum_error_squared);
		const int64_t tolerance = CHAIN_CONVERGENCE_TOLERANCE;
		assert(maximum_error_squared <= (uint64_t)(tolerance * tolerance));
		if (link_count == 1U) {
			assert(extra_position_sweep_tick_count == 0U);
		} else {
			assert(extra_position_sweep_tick_count > 0U);
		}

		struct picosystem_game_world replay;
		assert(picosystem_physics_chain_fixture_reset(&replay, link_count) == 0);
		for (uint32_t step = 0U; step < 560U; ++step) {
			assert(picosystem_physics_world_wake_body(&replay.physics, 0U) == 0);
			assert(picosystem_game_world_step(&replay, &neutral) == 0);
		}
		assert_world_equal(&world, &replay);
	}
}

static void assert_bodies_inside_arena(const struct picosystem_game_world *world)
{
	const int32_t left =
		PICOSYSTEM_PHYSICS_FIXED_FROM_INT(PICOSYSTEM_GAME_PLAYFIELD_LEFT_PIXELS);
	const int32_t right =
		PICOSYSTEM_PHYSICS_FIXED_FROM_INT(PICOSYSTEM_GAME_PLAYFIELD_RIGHT_PIXELS);
	const int32_t top = PICOSYSTEM_PHYSICS_FIXED_FROM_INT(PICOSYSTEM_GAME_PLAYFIELD_TOP_PIXELS);
	const int32_t bottom =
		PICOSYSTEM_PHYSICS_FIXED_FROM_INT(PICOSYSTEM_GAME_PLAYFIELD_BOTTOM_PIXELS);

	for (uint16_t index = 0U; index < world->physics.body_count; ++index) {
		const struct picosystem_physics_body *const body = &world->physics.bodies[index];
		if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_CIRCLE) {
			if ((body->center.x < (left + body->radius - BOUNDARY_TOLERANCE)) ||
			    (body->center.x > (right - body->radius + BOUNDARY_TOLERANCE)) ||
			    (body->center.y < (top + body->radius - BOUNDARY_TOLERANCE)) ||
			    (body->center.y > (bottom - body->radius + BOUNDARY_TOLERANCE))) {
				fprintf(stderr,
					"circle %u escaped at tick %u: center=(%d,%d), radius=%d\n",
					index, world->logic_tick_count, body->center.x,
					body->center.y, body->radius);
			}
			assert(body->center.x >= (left + body->radius - BOUNDARY_TOLERANCE));
			assert(body->center.x <= (right - body->radius + BOUNDARY_TOLERANCE));
			assert(body->center.y >= (top + body->radius - BOUNDARY_TOLERANCE));
			assert(body->center.y <= (bottom - body->radius + BOUNDARY_TOLERANCE));
			continue;
		}
		if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_CAPSULE) {
			struct picosystem_physics_vector start;
			struct picosystem_physics_vector end;
			assert(picosystem_physics_body_capsule_endpoints(body, &start, &end) == 0);
			const struct picosystem_physics_vector endpoints[] = {start, end};
			for (size_t endpoint = 0U; endpoint < 2U; ++endpoint) {
				if ((endpoints[endpoint].x <
				     (left + body->radius - BOUNDARY_TOLERANCE)) ||
				    (endpoints[endpoint].x >
				     (right - body->radius + BOUNDARY_TOLERANCE)) ||
				    (endpoints[endpoint].y <
				     (top + body->radius - BOUNDARY_TOLERANCE)) ||
				    (endpoints[endpoint].y >
				     (bottom - body->radius + BOUNDARY_TOLERANCE))) {
					fprintf(stderr,
						"capsule %u endpoint %u escaped at tick %u: "
						"point=(%d,%d), "
						"radius=%d\n",
						index, (unsigned int)endpoint,
						world->logic_tick_count, endpoints[endpoint].x,
						endpoints[endpoint].y, body->radius);
				}
				assert(endpoints[endpoint].x >=
				       (left + body->radius - BOUNDARY_TOLERANCE));
				assert(endpoints[endpoint].x <=
				       (right - body->radius + BOUNDARY_TOLERANCE));
				assert(endpoints[endpoint].y >=
				       (top + body->radius - BOUNDARY_TOLERANCE));
				assert(endpoints[endpoint].y <=
				       (bottom - body->radius + BOUNDARY_TOLERANCE));
			}
			continue;
		}

		struct picosystem_physics_vector vertices[PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT];
		assert(picosystem_physics_body_box_vertices(body, vertices) == 0);
		for (size_t vertex = 0U; vertex < PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT; ++vertex) {
			if ((vertices[vertex].x < (left - BOUNDARY_TOLERANCE)) ||
			    (vertices[vertex].x > (right + BOUNDARY_TOLERANCE)) ||
			    (vertices[vertex].y < (top - BOUNDARY_TOLERANCE)) ||
			    (vertices[vertex].y > (bottom + BOUNDARY_TOLERANCE))) {
				fprintf(stderr,
					"box %u vertex %u escaped at tick %u: point=(%d,%d)\n",
					index, (unsigned int)vertex, world->logic_tick_count,
					vertices[vertex].x, vertices[vertex].y);
			}
			assert(vertices[vertex].x >= (left - BOUNDARY_TOLERANCE));
			assert(vertices[vertex].x <= (right + BOUNDARY_TOLERANCE));
			assert(vertices[vertex].y >= (top - BOUNDARY_TOLERANCE));
			assert(vertices[vertex].y <= (bottom + BOUNDARY_TOLERANCE));
		}
	}
}

static void assert_ropes_inside_arena(const struct picosystem_game_world *world)
{
	const int32_t left =
		PICOSYSTEM_PHYSICS_FIXED_FROM_INT(PICOSYSTEM_GAME_PLAYFIELD_LEFT_PIXELS);
	const int32_t right =
		PICOSYSTEM_PHYSICS_FIXED_FROM_INT(PICOSYSTEM_GAME_PLAYFIELD_RIGHT_PIXELS);
	const int32_t top = PICOSYSTEM_PHYSICS_FIXED_FROM_INT(PICOSYSTEM_GAME_PLAYFIELD_TOP_PIXELS);
	const int32_t bottom =
		PICOSYSTEM_PHYSICS_FIXED_FROM_INT(PICOSYSTEM_GAME_PLAYFIELD_BOTTOM_PIXELS);

	for (uint16_t rope_index = 0U; rope_index < world->physics.rope_count; ++rope_index) {
		const struct picosystem_physics_rope *const rope =
			&world->physics.ropes[rope_index];
		for (uint8_t particle_index = 0U; particle_index < rope->particle_count;
		     ++particle_index) {
			const struct picosystem_physics_vector *const position =
				&rope->particles[particle_index].position;
			const int32_t minimum_x =
				left + rope->collision_radius - ROPE_BOUNDARY_TOLERANCE;
			const int32_t maximum_x =
				right - rope->collision_radius + ROPE_BOUNDARY_TOLERANCE;
			const int32_t minimum_y =
				top + rope->collision_radius - ROPE_BOUNDARY_TOLERANCE;
			const int32_t maximum_y =
				bottom - rope->collision_radius + ROPE_BOUNDARY_TOLERANCE;
			if ((position->x < minimum_x) || (position->x > maximum_x) ||
			    (position->y < minimum_y) || (position->y > maximum_y)) {
				fprintf(stderr,
					"rope %u particle %u escaped at tick %u: point=(%d,%d)\n",
					rope_index, particle_index, world->logic_tick_count,
					position->x, position->y);
			}
			assert(position->x >= minimum_x);
			assert(position->x <= maximum_x);
			assert(position->y >= minimum_y);
			assert(position->y <= maximum_y);
		}
	}
}

static void run_clockwork_neutral_replay(struct picosystem_game_world *world, uint32_t tick_count)
{
	const struct picosystem_game_input neutral = {0};
	const int64_t joint_tolerance = PICOSYSTEM_PHYSICS_FIXED_FROM_INT(5);
	for (uint32_t tick = 0U; tick < tick_count; ++tick) {
		assert(picosystem_game_world_step(world, &neutral) == 0);
		assert_bodies_inside_arena(world);
		assert_ropes_inside_arena(world);
		assert(maximum_revolute_error_squared(world) <=
		       (uint64_t)(joint_tolerance * joint_tolerance));
		assert(world->physics.last_broad_phase_fallback == 0U);
	}
}

static void test_clockwork_scene_is_bounded_and_deterministic(void)
{
	struct picosystem_game_world world;
	assert(picosystem_game_world_reset_scene(&world, PICOSYSTEM_GAME_SCENE_CLOCKWORK) == 0);
	assert(world.scene_id == PICOSYSTEM_GAME_SCENE_CLOCKWORK);
	assert(world.physics.body_count == 9U);
	assert(world.physics.static_segment_count == 4U);
	assert(world.physics.distance_joint_count == 1U);
	assert(world.physics.revolute_joint_count == 8U);
	assert(world.physics.prismatic_joint_count == 1U);
	assert(world.physics.box_sensor_count == 1U);
	assert(world.physics.rope_count == 1U);
	assert(world.physics.ropes[0].particle_count == 6U);
	assert_hash("clockwork-reset", picosystem_game_world_hash(&world),
		    EXPECTED_CLOCKWORK_RESET_HASH);
	assert(picosystem_game_world_body_render_style(&world, 0U) ==
	       PICOSYSTEM_GAME_BODY_RENDER_STYLE_GEAR);
	assert(picosystem_game_world_body_render_style(&world, 1U) ==
	       PICOSYSTEM_GAME_BODY_RENDER_STYLE_GEAR);
	assert(picosystem_game_world_body_render_style(&world, 2U) ==
	       PICOSYSTEM_GAME_BODY_RENDER_STYLE_DEFAULT);
	assert(picosystem_game_world_body_render_style(&world, 9U) ==
	       PICOSYSTEM_GAME_BODY_RENDER_STYLE_DEFAULT);

	const struct picosystem_game_world initial = world;
	assert(picosystem_game_world_apply_scene_action(
		       &world, PICOSYSTEM_GAME_SCENE_ACTION_PRIMARY) == -ENOTSUP);
	assert_world_equal(&world, &initial);
	assert(picosystem_game_world_reset_scene(NULL, PICOSYSTEM_GAME_SCENE_CLOCKWORK) == -EINVAL);
	assert(picosystem_game_world_reset_scene(&world, PICOSYSTEM_GAME_SCENE_COUNT) == -ERANGE);
	assert_world_equal(&world, &initial);
	assert(picosystem_game_world_reset_scene(&world, PICOSYSTEM_GAME_SCENE_DIAGNOSTIC_CHAIN) ==
	       -EINVAL);
	assert_world_equal(&world, &initial);
	struct picosystem_game_world input_replay;
	assert(picosystem_game_world_reset_scene(&input_replay, PICOSYSTEM_GAME_SCENE_CLOCKWORK) ==
	       0);
	const struct picosystem_game_input right = {.horizontal = 1};
	const struct picosystem_game_input up = {.vertical = -1};
	step_many(&input_replay, &right, 15U);
	step_many(&input_replay, &up, 8U);
	assert_hash("clockwork-right-15-up-8", picosystem_game_world_hash(&input_replay),
		    EXPECTED_CLOCKWORK_INPUT_HASH);

	picosystem_physics_fixed_t minimum_slider_x = world.physics.bodies[3].center.x;
	picosystem_physics_fixed_t maximum_slider_x = minimum_slider_x;
	const uint32_t initial_drive_angle = world.physics.bodies[0].angle_turns;
	const uint32_t initial_follower_angle = world.physics.bodies[1].angle_turns;
	const picosystem_physics_fixed_t initial_pendulum_x = world.physics.bodies[4].center.x;
	const struct picosystem_game_input neutral = {0};
	const int64_t joint_tolerance = PICOSYSTEM_PHYSICS_FIXED_FROM_INT(5);
	uint64_t maximum_anchor_error_squared = 0U;
	for (uint32_t tick = 0U; tick < 3000U; ++tick) {
		assert(picosystem_game_world_step(&world, &neutral) == 0);
		assert_bodies_inside_arena(&world);
		assert_ropes_inside_arena(&world);
		const uint64_t anchor_error_squared = maximum_revolute_error_squared(&world);
		if (anchor_error_squared > maximum_anchor_error_squared) {
			maximum_anchor_error_squared = anchor_error_squared;
		}
		assert(anchor_error_squared <= (uint64_t)(joint_tolerance * joint_tolerance));
		assert(maximum_revolute_limit_violation(&world) <= ANGULAR_BOUNDARY_TOLERANCE);
		assert(maximum_prismatic_limit_violation(&world) <= BOUNDARY_TOLERANCE);
		if (world.physics.bodies[3].center.x < minimum_slider_x) {
			minimum_slider_x = world.physics.bodies[3].center.x;
		}
		if (world.physics.bodies[3].center.x > maximum_slider_x) {
			maximum_slider_x = world.physics.bodies[3].center.x;
		}
		assert(world.physics.last_broad_phase_fallback == 0U);
		assert(world.physics.last_work.revolute_motor_count == 1U);
		assert(world.physics.last_work.prismatic_motor_count == 0U);
		assert(world.physics.last_work.spring_joint_count == 1U);
		assert(world.physics.last_work.rope_particle_count == 6U);
	}
	assert(world.physics.bodies[0].angle_turns != initial_drive_angle);
	assert(world.physics.bodies[1].angle_turns != initial_follower_angle);
	assert(world.physics.bodies[4].center.x != initial_pendulum_x);
	assert((maximum_slider_x - minimum_slider_x) >= PICOSYSTEM_PHYSICS_FIXED_FROM_INT(8));
	assert(world.sensor_entry_count > 0U);
	assert_hash("clockwork-3000", picosystem_game_world_hash(&world),
		    EXPECTED_CLOCKWORK_3000_HASH);

	struct picosystem_game_world replay;
	assert(picosystem_game_world_reset_scene(&replay, PICOSYSTEM_GAME_SCENE_CLOCKWORK) == 0);
	run_clockwork_neutral_replay(&replay, 3000U);
	assert_world_equal(&world, &replay);
	fprintf(stderr,
		"clockwork hash=%08x slider travel=%d q16 px sensor entries=%u maximum squared "
		"anchor error=%llu\n",
		picosystem_game_world_hash(&world), maximum_slider_x - minimum_slider_x,
		world.sensor_entry_count, (unsigned long long)maximum_anchor_error_squared);
}

static void run_marble_machine_sequence(struct picosystem_game_world *world, uint32_t tick_count)
{
	const struct picosystem_game_input neutral = {0};
	for (uint32_t tick = 0U; tick < tick_count; ++tick) {
		if ((tick == 480U) || (tick == 1320U)) {
			assert(picosystem_game_world_apply_scene_action(
				       world, PICOSYSTEM_GAME_SCENE_ACTION_PRIMARY) == 0);
		}
		assert(picosystem_game_world_step(world, &neutral) == 0);
		assert_bodies_inside_arena(world);
		assert(world->physics.last_broad_phase_fallback == 0U);
	}
}

struct marble_machine_metrics {
	struct picosystem_physics_vector launch_origins[MARBLE_BODY_COUNT];
	struct picosystem_physics_vector highest_flight_origin;
	struct picosystem_physics_vector highest_flight_position;
	struct picosystem_physics_vector farthest_flight_origin;
	struct picosystem_physics_vector farthest_flight_position;
	picosystem_physics_fixed_t minimum_late_y[MARBLE_BODY_COUNT];
	picosystem_physics_fixed_t maximum_late_y[MARBLE_BODY_COUNT];
	picosystem_physics_fixed_t maximum_flight_rise;
	picosystem_physics_fixed_t maximum_flight_horizontal_travel;
	picosystem_physics_fixed_t maximum_launch_upward_speed;
	picosystem_physics_fixed_t minimum_launcher_angle;
	picosystem_physics_fixed_t maximum_launcher_angle;
	picosystem_physics_fixed_t minimum_accumulator_angle;
	picosystem_physics_fixed_t maximum_accumulator_angle;
	uint64_t minimum_spring_length_squared;
	uint64_t maximum_spring_length_squared;
	uint32_t upward_sensor_entry_count;
	uint32_t rejected_sensor_entry_count;
	uint32_t midpoint_sensor_entry_count;
	uint32_t upper_ramp_contact_count;
	uint32_t lower_ramp_contact_count;
	uint32_t paddle_contact_count;
	uint32_t launcher_contact_count;
	uint32_t launcher_fire_count;
	uint32_t late_launcher_fire_count;
	uint32_t accumulator_contact_count;
	uint32_t accumulator_loaded_tick_count;
	uint32_t accumulator_dump_count;
	uint32_t late_accumulator_dump_count;
	uint32_t elevator_admission_count;
	uint32_t late_elevator_admission_count;
	uint32_t minimum_elevator_admission_interval;
	uint32_t maximum_elevator_admission_interval;
	uint32_t previous_elevator_admission_tick;
	uint32_t hopper_population_tick_sum;
	uint32_t congested_hopper_tick_count;
	uint32_t hopper_contact_tick_count;
	uint16_t maximum_hopper_contact_count;
	uint16_t returned_body_mask;
	uint16_t late_returned_body_mask;
	uint16_t upper_ramp_body_mask;
	uint16_t lower_ramp_body_mask;
	uint16_t late_upper_ramp_body_mask;
	uint16_t late_lower_ramp_body_mask;
	uint16_t upper_ramp_rightward_body_mask;
	uint16_t late_upper_ramp_rightward_body_mask;
	uint16_t lower_ramp_leftward_body_mask;
	uint16_t late_lower_ramp_leftward_body_mask;
	uint16_t paddle_body_mask;
	uint16_t late_paddle_body_mask;
	uint16_t launcher_body_mask;
	uint16_t late_launcher_body_mask;
	uint16_t accumulator_body_mask;
	uint16_t late_accumulator_body_mask;
	uint16_t upward_launch_body_mask;
	uint16_t high_flight_body_mask;
	uint16_t late_high_flight_body_mask;
	uint16_t long_flight_body_mask;
	uint16_t late_long_flight_body_mask;
	uint16_t elevator_admission_body_mask;
	uint16_t late_elevator_admission_body_mask;
	uint16_t elevator_admission_armed_mask;
	uint8_t maximum_hopper_population;
	uint8_t maximum_accumulator_population;
	uint16_t previous_launcher_contact_mask;
	uint16_t active_flight_mask;
	uint16_t current_high_flight_mask;
	uint8_t flight_age[MARBLE_BODY_COUNT];
	uint8_t launcher_sample_count;
	uint8_t previous_launcher_state;
	uint8_t accumulator_dump_armed;
};

static void observe_marble_sensor_events(const struct picosystem_game_world *world,
					 struct marble_machine_metrics *metrics, bool late)
{
	for (uint16_t event_index = 0U; event_index < world->physics.contact_event_count;
	     ++event_index) {
		const struct picosystem_physics_contact_event *const event =
			picosystem_physics_world_contact_event_at(&world->physics, event_index);
		assert(event != NULL);
		if ((event->type != PICOSYSTEM_PHYSICS_CONTACT_EVENT_BODY_BOX_SENSOR) ||
		    (event->phase != PICOSYSTEM_PHYSICS_CONTACT_EVENT_BEGIN) ||
		    (event->body_a_id < MARBLE_FIRST_BODY_ID) ||
		    (event->body_a_id >= (MARBLE_FIRST_BODY_ID + MARBLE_BODY_COUNT))) {
			continue;
		}
		const uint16_t body_index = (uint16_t)(event->body_a_id - MARBLE_FIRST_BODY_ID);
		assert(world->physics.bodies[body_index].id == event->body_a_id);
		if (world->physics.bodies[body_index].velocity_per_tick.y < 0) {
			++metrics->upward_sensor_entry_count;
			metrics->returned_body_mask |= (uint16_t)(UINT16_C(1) << body_index);
			if (late) {
				metrics->late_returned_body_mask |=
					(uint16_t)(UINT16_C(1) << body_index);
			}
		} else {
			++metrics->rejected_sensor_entry_count;
		}
	}
}

static picosystem_physics_fixed_t fixed_absolute(picosystem_physics_fixed_t value)
{
	return (value < 0) ? -value : value;
}

static uint8_t bit_count_u16(uint16_t value)
{
	uint8_t count = 0U;
	while (value != 0U) {
		count = (uint8_t)(count + (value & UINT8_C(1)));
		value >>= 1U;
	}
	return count;
}

static void observe_marble_machine_contacts(const struct picosystem_game_world *world,
					    struct marble_machine_metrics *metrics, bool late)
{
	uint16_t launcher_contact_mask = 0U;
	uint16_t accumulator_contact_mask = 0U;
	uint16_t static_contact_mask = 0U;
	uint16_t hopper_contact_count = 0U;
	for (uint16_t contact_index = 0U; contact_index < world->physics.contact_count;
	     ++contact_index) {
		const struct picosystem_physics_contact *const contact =
			&world->physics.contacts[contact_index];
		if (contact->type == PICOSYSTEM_PHYSICS_CONTACT_BODY) {
			if ((contact->body_a_index < MARBLE_BODY_COUNT) &&
			    (contact->body_b_index < MARBLE_BODY_COUNT)) {
				const struct picosystem_physics_body *const body_a =
					&world->physics.bodies[contact->body_a_index];
				const struct picosystem_physics_body *const body_b =
					&world->physics.bodies[contact->body_b_index];
				if ((body_a->center.x <= MARBLE_HOPPER_MAX_X) &&
				    (body_a->center.y >= MARBLE_HOPPER_MIN_Y) &&
				    (body_b->center.x <= MARBLE_HOPPER_MAX_X) &&
				    (body_b->center.y >= MARBLE_HOPPER_MIN_Y)) {
					++hopper_contact_count;
				}
			}
			uint8_t paddle_marble_index = UINT8_MAX;
			uint8_t launcher_marble_index = UINT8_MAX;
			uint8_t accumulator_marble_index = UINT8_MAX;
			if ((contact->body_a_index == MARBLE_PADDLE_BODY_INDEX) &&
			    (contact->body_b_index < MARBLE_BODY_COUNT)) {
				paddle_marble_index = contact->body_b_index;
			} else if ((contact->body_b_index == MARBLE_PADDLE_BODY_INDEX) &&
				   (contact->body_a_index < MARBLE_BODY_COUNT)) {
				paddle_marble_index = contact->body_a_index;
			}
			if (paddle_marble_index != UINT8_MAX) {
				const uint16_t body_mask =
					(uint16_t)(UINT16_C(1) << paddle_marble_index);
				++metrics->paddle_contact_count;
				metrics->paddle_body_mask |= body_mask;
				if (late) {
					metrics->late_paddle_body_mask |= body_mask;
				}
			}
			if ((contact->body_a_index == MARBLE_LAUNCHER_BODY_INDEX) &&
			    (contact->body_b_index < MARBLE_BODY_COUNT)) {
				launcher_marble_index = contact->body_b_index;
			} else if ((contact->body_b_index == MARBLE_LAUNCHER_BODY_INDEX) &&
				   (contact->body_a_index < MARBLE_BODY_COUNT)) {
				launcher_marble_index = contact->body_a_index;
			}
			if (launcher_marble_index != UINT8_MAX) {
				const uint16_t body_mask =
					(uint16_t)(UINT16_C(1) << launcher_marble_index);
				++metrics->launcher_contact_count;
				launcher_contact_mask |= body_mask;
				metrics->launcher_body_mask |= body_mask;
				if (late) {
					metrics->late_launcher_body_mask |= body_mask;
				}
			}
			if ((contact->body_a_index == MARBLE_ACCUMULATOR_BODY_INDEX) &&
			    (contact->body_b_index < MARBLE_BODY_COUNT)) {
				accumulator_marble_index = contact->body_b_index;
			} else if ((contact->body_b_index == MARBLE_ACCUMULATOR_BODY_INDEX) &&
				   (contact->body_a_index < MARBLE_BODY_COUNT)) {
				accumulator_marble_index = contact->body_a_index;
			}
			if (accumulator_marble_index != UINT8_MAX) {
				const uint16_t body_mask =
					(uint16_t)(UINT16_C(1) << accumulator_marble_index);
				++metrics->accumulator_contact_count;
				accumulator_contact_mask |= body_mask;
				metrics->accumulator_body_mask |= body_mask;
				if (late) {
					metrics->late_accumulator_body_mask |= body_mask;
				}
			}
			continue;
		}
		if ((contact->type != PICOSYSTEM_PHYSICS_CONTACT_STATIC_SEGMENT) ||
		    (contact->body_a_index >= MARBLE_BODY_COUNT)) {
			continue;
		}
		const uint16_t body_mask = (uint16_t)(UINT16_C(1) << contact->body_a_index);
		static_contact_mask |= body_mask;
		if (contact->segment_index == MARBLE_UPPER_RAMP_INDEX) {
			++metrics->upper_ramp_contact_count;
			metrics->upper_ramp_body_mask |= body_mask;
			const picosystem_physics_fixed_t velocity_x =
				world->physics.bodies[contact->body_a_index].velocity_per_tick.x;
			if ((contact->point.x >= MARBLE_UPPER_RAMP_MIDDLE_MIN_X) &&
			    (contact->point.x <= MARBLE_UPPER_RAMP_MIDDLE_MAX_X) &&
			    (velocity_x > 0)) {
				metrics->upper_ramp_rightward_body_mask |= body_mask;
				if (late) {
					metrics->late_upper_ramp_rightward_body_mask |= body_mask;
				}
			}
			if (late) {
				metrics->late_upper_ramp_body_mask |= body_mask;
			}
		} else if (contact->segment_index == MARBLE_LOWER_RAMP_INDEX) {
			++metrics->lower_ramp_contact_count;
			metrics->lower_ramp_body_mask |= body_mask;
			const picosystem_physics_fixed_t velocity_x =
				world->physics.bodies[contact->body_a_index].velocity_per_tick.x;
			if ((contact->point.x >= MARBLE_LOWER_RAMP_MIDDLE_MIN_X) &&
			    (contact->point.x <= MARBLE_LOWER_RAMP_MIDDLE_MAX_X) &&
			    (velocity_x < 0)) {
				metrics->lower_ramp_leftward_body_mask |= body_mask;
				if (late) {
					metrics->late_lower_ramp_leftward_body_mask |= body_mask;
				}
			}
			if (late) {
				metrics->late_lower_ramp_body_mask |= body_mask;
			}
		}
	}

	for (uint8_t body_index = 0U; body_index < MARBLE_BODY_COUNT; ++body_index) {
		const uint16_t body_mask = (uint16_t)(UINT16_C(1) << body_index);
		const bool contacting_launcher = (launcher_contact_mask & body_mask) != 0U;
		const bool was_contacting_launcher =
			(metrics->previous_launcher_contact_mask & body_mask) != 0U;
		if (!contacting_launcher && was_contacting_launcher) {
			const struct picosystem_physics_body *const body =
				&world->physics.bodies[body_index];
			metrics->launch_origins[body_index] = body->center;
			metrics->flight_age[body_index] = 0U;
			metrics->active_flight_mask |= body_mask;
			metrics->current_high_flight_mask &= (uint16_t)~body_mask;
			if (body->velocity_per_tick.y < 0) {
				const picosystem_physics_fixed_t upward_speed =
					-body->velocity_per_tick.y;
				metrics->upward_launch_body_mask |= body_mask;
				if (upward_speed > metrics->maximum_launch_upward_speed) {
					metrics->maximum_launch_upward_speed = upward_speed;
				}
			}
		}
		if ((metrics->active_flight_mask & body_mask) == 0U) {
			continue;
		}
		const struct picosystem_physics_body *const body =
			&world->physics.bodies[body_index];
		const picosystem_physics_fixed_t rise =
			metrics->launch_origins[body_index].y - body->center.y;
		const picosystem_physics_fixed_t horizontal_travel =
			fixed_absolute(body->center.x - metrics->launch_origins[body_index].x);
		if (rise > metrics->maximum_flight_rise) {
			metrics->maximum_flight_rise = rise;
			metrics->highest_flight_origin = metrics->launch_origins[body_index];
			metrics->highest_flight_position = body->center;
		}
		if (horizontal_travel > metrics->maximum_flight_horizontal_travel) {
			metrics->maximum_flight_horizontal_travel = horizontal_travel;
			metrics->farthest_flight_origin = metrics->launch_origins[body_index];
			metrics->farthest_flight_position = body->center;
		}
		if (rise >= PICOSYSTEM_PHYSICS_FIXED_FROM_INT(8)) {
			metrics->high_flight_body_mask |= body_mask;
			metrics->current_high_flight_mask |= body_mask;
			if (late) {
				metrics->late_high_flight_body_mask |= body_mask;
			}
		}
		if ((horizontal_travel >= PICOSYSTEM_PHYSICS_FIXED_FROM_INT(20)) &&
		    ((metrics->current_high_flight_mask & body_mask) != 0U)) {
			metrics->long_flight_body_mask |= body_mask;
			if (late) {
				metrics->late_long_flight_body_mask |= body_mask;
			}
		}
		++metrics->flight_age[body_index];
		if ((metrics->flight_age[body_index] >= 45U) ||
		    ((metrics->flight_age[body_index] >= 3U) &&
		     ((static_contact_mask & body_mask) != 0U))) {
			metrics->active_flight_mask &= (uint16_t)~body_mask;
			metrics->current_high_flight_mask &= (uint16_t)~body_mask;
		}
	}
	if (hopper_contact_count != 0U) {
		++metrics->hopper_contact_tick_count;
	}
	if (hopper_contact_count > metrics->maximum_hopper_contact_count) {
		metrics->maximum_hopper_contact_count = hopper_contact_count;
	}
	const uint8_t accumulator_population = bit_count_u16(accumulator_contact_mask);
	if (accumulator_population >= 2U) {
		++metrics->accumulator_loaded_tick_count;
	}
	if (accumulator_population > metrics->maximum_accumulator_population) {
		metrics->maximum_accumulator_population = accumulator_population;
	}
	metrics->previous_launcher_contact_mask = launcher_contact_mask;
}

static void observe_marble_elevator_admission(const struct picosystem_game_world *world,
					      struct marble_machine_metrics *metrics, uint32_t tick,
					      bool late)
{
	uint8_t hopper_population = 0U;

	for (uint8_t body_index = 0U; body_index < MARBLE_BODY_COUNT; ++body_index) {
		const struct picosystem_physics_body *const body =
			&world->physics.bodies[body_index];
		const uint16_t body_mask = (uint16_t)(UINT16_C(1) << body_index);
		if ((body->center.x <= MARBLE_HOPPER_MAX_X) &&
		    (body->center.y >= MARBLE_HOPPER_MIN_Y)) {
			++hopper_population;
		}
		if (body->center.y >= MARBLE_ELEVATOR_REARM_Y) {
			metrics->elevator_admission_armed_mask |= body_mask;
		}
		if (((metrics->elevator_admission_armed_mask & body_mask) != 0U) &&
		    (body->center.y <= MARBLE_ELEVATOR_ADMISSION_Y) &&
		    (body->center.x <= MARBLE_ELEVATOR_MAX_X) && (body->velocity_per_tick.y < 0)) {
			if (metrics->elevator_admission_count != 0U) {
				const uint32_t interval =
					tick - metrics->previous_elevator_admission_tick;
				if (interval < metrics->minimum_elevator_admission_interval) {
					metrics->minimum_elevator_admission_interval = interval;
				}
				if (interval > metrics->maximum_elevator_admission_interval) {
					metrics->maximum_elevator_admission_interval = interval;
				}
			}
			metrics->previous_elevator_admission_tick = tick;
			++metrics->elevator_admission_count;
			metrics->elevator_admission_body_mask |= body_mask;
			metrics->elevator_admission_armed_mask &= (uint16_t)~body_mask;
			if (late) {
				++metrics->late_elevator_admission_count;
				metrics->late_elevator_admission_body_mask |= body_mask;
			}
		}
	}

	metrics->hopper_population_tick_sum += hopper_population;
	if (hopper_population > metrics->maximum_hopper_population) {
		metrics->maximum_hopper_population = hopper_population;
	}
	if (hopper_population >= 3U) {
		++metrics->congested_hopper_tick_count;
	}
}

static void observe_marble_launcher_motion(const struct picosystem_game_world *world,
					   struct marble_machine_metrics *metrics, bool late)
{
	picosystem_physics_fixed_t angle;
	picosystem_physics_fixed_t accumulator_angle;
	struct picosystem_physics_vector spring_anchor_a;
	struct picosystem_physics_vector spring_anchor_b;
	assert(picosystem_physics_world_revolute_joint_angle(&world->physics, 1U, &angle) == 0);
	assert(picosystem_physics_world_revolute_joint_angle(&world->physics, 2U,
							     &accumulator_angle) == 0);
	assert(picosystem_physics_world_distance_joint_endpoints(
		       &world->physics, 0U, &spring_anchor_a, &spring_anchor_b) == 0);
	const uint64_t spring_length_squared =
		vector_distance_squared(&spring_anchor_a, &spring_anchor_b);
	const struct picosystem_physics_revolute_joint *const launcher_joint =
		&world->physics.revolute_joints[1];
	const uint8_t launcher_state = (uint8_t)((launcher_joint->motor_enabled != 0U)
							 ? 2U
							 : ((launcher_joint->lower_angle_radians ==
							     launcher_joint->upper_angle_radians)
								    ? 0U
								    : 1U));
	if (metrics->launcher_sample_count == 0U) {
		metrics->minimum_launcher_angle = angle;
		metrics->maximum_launcher_angle = angle;
		metrics->minimum_accumulator_angle = accumulator_angle;
		metrics->maximum_accumulator_angle = accumulator_angle;
		metrics->minimum_spring_length_squared = spring_length_squared;
		metrics->maximum_spring_length_squared = spring_length_squared;
		metrics->previous_launcher_state = launcher_state;
		metrics->accumulator_dump_armed = 1U;
		metrics->launcher_sample_count = 1U;
		return;
	}
	if ((metrics->previous_launcher_state == 0U) && (launcher_state == 1U)) {
		++metrics->launcher_fire_count;
		if (late) {
			++metrics->late_launcher_fire_count;
		}
	}
	metrics->previous_launcher_state = launcher_state;
	if (angle < metrics->minimum_launcher_angle) {
		metrics->minimum_launcher_angle = angle;
	}
	if (angle > metrics->maximum_launcher_angle) {
		metrics->maximum_launcher_angle = angle;
	}
	if (accumulator_angle < metrics->minimum_accumulator_angle) {
		metrics->minimum_accumulator_angle = accumulator_angle;
	}
	if (accumulator_angle > metrics->maximum_accumulator_angle) {
		metrics->maximum_accumulator_angle = accumulator_angle;
	}
	if (accumulator_angle <= PICOSYSTEM_PHYSICS_FIXED_RATIO(1, 8)) {
		metrics->accumulator_dump_armed = 1U;
	} else if ((metrics->accumulator_dump_armed != 0U) &&
		   (accumulator_angle >= PICOSYSTEM_PHYSICS_FIXED_RATIO(1, 3))) {
		++metrics->accumulator_dump_count;
		if (late) {
			++metrics->late_accumulator_dump_count;
		}
		metrics->accumulator_dump_armed = 0U;
	}
	if (spring_length_squared < metrics->minimum_spring_length_squared) {
		metrics->minimum_spring_length_squared = spring_length_squared;
	}
	if (spring_length_squared > metrics->maximum_spring_length_squared) {
		metrics->maximum_spring_length_squared = spring_length_squared;
	}
}

static void run_marble_machine_neutral(struct picosystem_game_world *world, uint32_t tick_count,
				       struct marble_machine_metrics *metrics)
{
	const struct picosystem_game_input neutral = {0};
	assert(metrics != NULL);
	*metrics = (struct marble_machine_metrics){0};
	metrics->minimum_elevator_admission_interval = UINT32_MAX;
	for (uint32_t tick = 0U; tick < tick_count; ++tick) {
		assert(picosystem_game_world_step(world, &neutral) == 0);
		assert_bodies_inside_arena(world);
		assert(world->physics.last_broad_phase_fallback == 0U);
		const bool late = (tick + 1U) >= (tick_count / 2U);
		observe_marble_sensor_events(world, metrics, late);
		observe_marble_machine_contacts(world, metrics, late);
		observe_marble_launcher_motion(world, metrics, late);
		observe_marble_elevator_admission(world, metrics, tick + 1U, late);
		if ((tick + 1U) == (tick_count / 2U)) {
			metrics->midpoint_sensor_entry_count = world->sensor_entry_count;
		}
		if ((tick + 1U) < (tick_count / 2U)) {
			continue;
		}
		for (uint16_t body = 0U; body < MARBLE_BODY_COUNT; ++body) {
			const picosystem_physics_fixed_t y = world->physics.bodies[body].center.y;
			if ((tick + 1U) == (tick_count / 2U)) {
				metrics->minimum_late_y[body] = y;
				metrics->maximum_late_y[body] = y;
			} else {
				if (y < metrics->minimum_late_y[body]) {
					metrics->minimum_late_y[body] = y;
				}
				if (y > metrics->maximum_late_y[body]) {
					metrics->maximum_late_y[body] = y;
				}
			}
		}
	}
}

static void test_marble_machine_scene_is_bounded_and_deterministic(void)
{
	struct picosystem_game_world world;
	assert(picosystem_game_world_reset_scene(&world, PICOSYSTEM_GAME_SCENE_MARBLE_MACHINE) ==
	       0);
	assert(world.scene_id == PICOSYSTEM_GAME_SCENE_MARBLE_MACHINE);
	assert(world.physics.body_count == (MARBLE_BODY_COUNT + 3U));
	assert(world.physics.static_segment_count == 8U);
	assert(world.physics.distance_joint_count == 2U);
	assert(world.physics.revolute_joint_count == 3U);
	assert(world.physics.prismatic_joint_count == 0U);
	assert(world.physics.box_sensor_count == 1U);
	assert(world.physics.rope_count == 0U);
	assert(world.physics.bodies[8].id == 709U);
	assert(world.physics.bodies[9].id == 710U);
	assert(world.physics.bodies[9].shape == PICOSYSTEM_PHYSICS_SHAPE_CAPSULE);
	assert(world.physics.bodies[10].id == 711U);
	assert(world.physics.bodies[10].shape == PICOSYSTEM_PHYSICS_SHAPE_CAPSULE);
	assert(world.physics.bodies[11].id == 712U);
	assert(world.physics.bodies[11].shape == PICOSYSTEM_PHYSICS_SHAPE_CAPSULE);
	assert(world.physics.distance_joints[0].spring_enabled != 0U);
	assert(world.physics.distance_joints[1].spring_enabled != 0U);
	assert(world.physics.revolute_joints[0].motor_enabled != 0U);
	assert(world.physics.revolute_joints[1].limit_enabled != 0U);
	assert(world.physics.revolute_joints[2].limit_enabled != 0U);
	assert(world.physics.static_segments[2].surface_speed_per_tick > 0);
	assert(world.physics.static_segments[5].surface_speed_per_tick > 0);
	assert_hash("marble-machine-reset", picosystem_game_world_hash(&world),
		    EXPECTED_MARBLE_RESET_HASH);

	const struct picosystem_game_world initial = world;
	assert(picosystem_game_world_apply_scene_action(&world,
							PICOSYSTEM_GAME_SCENE_ACTION_PRIMARY) == 0);
	assert(world.physics.static_segments[2].surface_speed_per_tick < 0);
	assert(world.physics.static_segments[5].surface_speed_per_tick < 0);
	assert(picosystem_game_world_apply_scene_action(&world,
							PICOSYSTEM_GAME_SCENE_ACTION_PRIMARY) == 0);
	assert_world_equal(&world, &initial);

	run_marble_machine_sequence(&world, 2400U);
	assert_hash("marble-machine-2400", picosystem_game_world_hash(&world),
		    EXPECTED_MARBLE_2400_HASH);

	struct picosystem_game_world replay;
	assert(picosystem_game_world_reset_scene(&replay, PICOSYSTEM_GAME_SCENE_MARBLE_MACHINE) ==
	       0);
	run_marble_machine_sequence(&replay, 2400U);
	assert_world_equal(&world, &replay);

	struct picosystem_game_world circulation;
	struct marble_machine_metrics metrics;
	assert(picosystem_game_world_reset_scene(&circulation,
						 PICOSYSTEM_GAME_SCENE_MARBLE_MACHINE) == 0);
	run_marble_machine_neutral(&circulation, MARBLE_NEUTRAL_TICK_COUNT, &metrics);
	picosystem_physics_fixed_t final_launcher_angle;
	assert(picosystem_physics_world_revolute_joint_angle(&circulation.physics, 1U,
							     &final_launcher_angle) == 0);
	fprintf(stderr,
		"marble-machine neutral entries=%u (%u late), rejected=%u, "
		"returned=%02x/%02x, ramps=%02x/%02x late=%02x/%02x "
		"flow=%02x/%02x late=%02x/%02x, paddle=%02x/%02x (%u contacts), "
		"launcher=%02x/%02x (%u contacts, %u/%u fires), "
		"admit=%02x/%02x (%u/%u events, %u..%u tick gaps), "
		"hopper=%u max/%u.%03u mean (%u congested, %u contact ticks, %u max contacts), "
		"launch=%02x high=%02x/%02x long=%02x/%02x, "
		"angle=%d..%d q16 rad, spring=%llu..%llu px2, "
		"flight rise=%d (%d,%d)->(%d,%d), dx=%d (%d,%d)->(%d,%d), "
		"speed=%d q16, final=%d/%d/%u, ramps=%u/%u contacts, hash=%08x\n",
		circulation.sensor_entry_count,
		circulation.sensor_entry_count - metrics.midpoint_sensor_entry_count,
		metrics.rejected_sensor_entry_count, metrics.returned_body_mask,
		metrics.late_returned_body_mask, metrics.upper_ramp_body_mask,
		metrics.lower_ramp_body_mask, metrics.late_upper_ramp_body_mask,
		metrics.late_lower_ramp_body_mask, metrics.upper_ramp_rightward_body_mask,
		metrics.lower_ramp_leftward_body_mask, metrics.late_upper_ramp_rightward_body_mask,
		metrics.late_lower_ramp_leftward_body_mask, metrics.paddle_body_mask,
		metrics.late_paddle_body_mask, metrics.paddle_contact_count,
		metrics.launcher_body_mask, metrics.late_launcher_body_mask,
		metrics.launcher_contact_count, metrics.launcher_fire_count,
		metrics.late_launcher_fire_count, metrics.elevator_admission_body_mask,
		metrics.late_elevator_admission_body_mask, metrics.elevator_admission_count,
		metrics.late_elevator_admission_count,
		(metrics.minimum_elevator_admission_interval == UINT32_MAX)
			? 0U
			: metrics.minimum_elevator_admission_interval,
		metrics.maximum_elevator_admission_interval, metrics.maximum_hopper_population,
		metrics.hopper_population_tick_sum / MARBLE_NEUTRAL_TICK_COUNT,
		((metrics.hopper_population_tick_sum % MARBLE_NEUTRAL_TICK_COUNT) * 1000U) /
			MARBLE_NEUTRAL_TICK_COUNT,
		metrics.congested_hopper_tick_count, metrics.hopper_contact_tick_count,
		metrics.maximum_hopper_contact_count, metrics.upward_launch_body_mask,
		metrics.high_flight_body_mask, metrics.late_high_flight_body_mask,
		metrics.long_flight_body_mask, metrics.late_long_flight_body_mask,
		metrics.minimum_launcher_angle, metrics.maximum_launcher_angle,
		(unsigned long long)(metrics.minimum_spring_length_squared >> 32U),
		(unsigned long long)(metrics.maximum_spring_length_squared >> 32U),
		metrics.maximum_flight_rise, metrics.highest_flight_origin.x,
		metrics.highest_flight_origin.y, metrics.highest_flight_position.x,
		metrics.highest_flight_position.y, metrics.maximum_flight_horizontal_travel,
		metrics.farthest_flight_origin.x, metrics.farthest_flight_origin.y,
		metrics.farthest_flight_position.x, metrics.farthest_flight_position.y,
		metrics.maximum_launch_upward_speed, final_launcher_angle,
		circulation.physics.bodies[MARBLE_LAUNCHER_BODY_INDEX].angular_velocity_per_tick,
		circulation.physics.revolute_joints[1].motor_enabled,
		metrics.upper_ramp_contact_count, metrics.lower_ramp_contact_count,
		picosystem_game_world_hash(&circulation));
	fprintf(stderr,
		"  accumulator=%03x/%03x (%u contacts, %u loaded ticks, %u max, %u/%u dumps), "
		"angle=%d..%d q16 rad\n",
		metrics.accumulator_body_mask, metrics.late_accumulator_body_mask,
		metrics.accumulator_contact_count, metrics.accumulator_loaded_tick_count,
		metrics.maximum_accumulator_population, metrics.accumulator_dump_count,
		metrics.late_accumulator_dump_count, metrics.minimum_accumulator_angle,
		metrics.maximum_accumulator_angle);
	assert(metrics.upward_sensor_entry_count == circulation.sensor_entry_count);
	assert(metrics.returned_body_mask == MARBLE_ALL_BODY_MASK);
	assert(metrics.late_returned_body_mask == MARBLE_ALL_BODY_MASK);
	assert(metrics.upper_ramp_body_mask == MARBLE_ALL_BODY_MASK);
	assert(metrics.lower_ramp_body_mask == MARBLE_ALL_BODY_MASK);
	assert(metrics.late_upper_ramp_body_mask == MARBLE_ALL_BODY_MASK);
	assert(metrics.late_lower_ramp_body_mask == MARBLE_ALL_BODY_MASK);
	assert(metrics.upper_ramp_rightward_body_mask == MARBLE_ALL_BODY_MASK);
	assert(metrics.late_upper_ramp_rightward_body_mask == MARBLE_ALL_BODY_MASK);
	assert(metrics.lower_ramp_leftward_body_mask == MARBLE_ALL_BODY_MASK);
	assert(metrics.late_lower_ramp_leftward_body_mask == MARBLE_ALL_BODY_MASK);
	assert(metrics.paddle_body_mask != 0U);
	assert(metrics.late_paddle_body_mask != 0U);
	assert(metrics.launcher_body_mask == MARBLE_ALL_BODY_MASK);
	assert(metrics.late_launcher_body_mask == MARBLE_ALL_BODY_MASK);
	assert(metrics.accumulator_body_mask == MARBLE_ALL_BODY_MASK);
	assert(metrics.late_accumulator_body_mask == MARBLE_ALL_BODY_MASK);
	assert(metrics.accumulator_loaded_tick_count >= 300U);
	assert(metrics.maximum_accumulator_population >= 2U);
	assert(metrics.accumulator_dump_count >= 20U);
	assert(metrics.late_accumulator_dump_count >= 10U);
	assert(metrics.minimum_accumulator_angle <= -PICOSYSTEM_PHYSICS_FIXED_RATIO(1, 10));
	assert(metrics.maximum_accumulator_angle >= PICOSYSTEM_PHYSICS_FIXED_RATIO(3, 5));
	assert(metrics.elevator_admission_body_mask == MARBLE_ALL_BODY_MASK);
	assert(metrics.late_elevator_admission_body_mask == MARBLE_ALL_BODY_MASK);
	assert(metrics.elevator_admission_count >= 48U);
	assert(metrics.late_elevator_admission_count >= 24U);
	assert(metrics.minimum_elevator_admission_interval >= 5U);
	assert(metrics.maximum_elevator_admission_interval <= 600U);
	assert(metrics.hopper_population_tick_sum <= MARBLE_NEUTRAL_TICK_COUNT);
	assert(metrics.congested_hopper_tick_count <= 1200U);
	assert(metrics.hopper_contact_tick_count <= 600U);
	assert(metrics.maximum_hopper_contact_count <= 2U);
	assert(metrics.launcher_fire_count >= 48U);
	assert(metrics.late_launcher_fire_count >= 24U);
	assert(metrics.upward_launch_body_mask == MARBLE_ALL_BODY_MASK);
	assert(bit_count_u16(metrics.high_flight_body_mask) >= 6U);
	assert(bit_count_u16(metrics.late_high_flight_body_mask) >= 4U);
	assert(bit_count_u16(metrics.long_flight_body_mask) >= 6U);
	assert(bit_count_u16(metrics.late_long_flight_body_mask) >= 4U);
	assert(metrics.maximum_flight_rise >= PICOSYSTEM_PHYSICS_FIXED_FROM_INT(24));
	assert(metrics.maximum_flight_horizontal_travel >= PICOSYSTEM_PHYSICS_FIXED_FROM_INT(60));
	assert(metrics.maximum_launch_upward_speed >= PICOSYSTEM_PHYSICS_FIXED_FROM_INT(2));
	assert(metrics.minimum_launcher_angle <= -PICOSYSTEM_PHYSICS_FIXED_RATIO(2, 3));
	assert((metrics.maximum_spring_length_squared - metrics.minimum_spring_length_squared) >=
	       (UINT64_C(400) << 32U));
	assert(circulation.sensor_entry_count >= 32U);
	assert((circulation.sensor_entry_count - metrics.midpoint_sensor_entry_count) >= 16U);
	for (uint16_t body = 0U; body < MARBLE_BODY_COUNT; ++body) {
		assert((metrics.maximum_late_y[body] - metrics.minimum_late_y[body]) >=
		       MARBLE_MINIMUM_LATE_TRAVEL);
	}
	assert_hash("marble-machine-neutral", picosystem_game_world_hash(&circulation),
		    EXPECTED_MARBLE_NEUTRAL_HASH);

	struct picosystem_game_world input_replay;
	assert(picosystem_game_world_reset_scene(&input_replay,
						 PICOSYSTEM_GAME_SCENE_MARBLE_MACHINE) == 0);
	const struct picosystem_game_input neutral = {0};
	const struct picosystem_game_input right = {.horizontal = 1};
	step_many(&input_replay, &neutral, 180U);
	assert(picosystem_game_world_apply_scene_action(&input_replay,
							PICOSYSTEM_GAME_SCENE_ACTION_PRIMARY) == 0);
	step_many(&input_replay, &right, 120U);
	step_many(&input_replay, &neutral, 180U);
	assert_hash("marble-machine-input", picosystem_game_world_hash(&input_replay),
		    EXPECTED_MARBLE_INPUT_HASH);
	fprintf(stderr, "marble-machine hash=%08x sensor entries=%u candidates=%u/%u contacts=%u\n",
		picosystem_game_world_hash(&world), world.sensor_entry_count,
		world.physics.last_candidate_pair_count, world.physics.last_possible_pair_count,
		world.physics.contact_count);
}

static void test_bounded_motion_contacts_and_saturated_tick(void)
{
	struct picosystem_game_world world;
	assert(picosystem_game_world_reset(&world) == 0);
	const struct picosystem_game_input inputs[] = {
		{0},
		{.horizontal = 1},
		{.vertical = -1},
		{.horizontal = -1, .vertical = 1},
	};
	bool saw_body_contact = false;
	bool saw_static_contact = false;
	bool saw_candidate_reduction = false;
	uint32_t minimum_candidate_count = UINT32_MAX;
	uint32_t maximum_candidate_count = 0U;
	picosystem_physics_fixed_t maximum_limit_violation = 0;
	picosystem_physics_fixed_t maximum_prismatic_violation = 0;
	uint16_t maximum_contact_count = 0U;
	uint32_t maximum_rope_collision_candidate_count = 0U;
	uint32_t maximum_rope_collision_contact_count = 0U;
	uint8_t maximum_solver_iteration_count = 0U;
	bool saw_positive_prismatic_motor = false;
	bool saw_negative_prismatic_motor = false;
	bool saw_sensor_stay = false;
	bool saw_sensor_end = false;
	bool saw_sleep = false;
	bool saw_wake = false;
	bool saw_rope_collision = false;
	uint32_t observed_sensor_begin_count = 0U;
	uint32_t maximum_sleeping_body_count = 0U;
	uint16_t maximum_quiet_tick_count = 0U;
	uint32_t first_sleep_tick = UINT32_MAX;
	uint32_t first_wake_tick = UINT32_MAX;

	for (uint32_t step = 0U; step < 10000U; ++step) {
		const size_t input_index = (step / 125U) % (sizeof(inputs) / sizeof(inputs[0]));
		const int err = picosystem_game_world_step(&world, &inputs[input_index]);
		if (err != 0) {
			fprintf(stderr, "bounded replay failed at step %u: %d\n", step, err);
			for (uint16_t index = 0U; index < world.physics.body_count; ++index) {
				const struct picosystem_physics_body *const body =
					&world.physics.bodies[index];
				fprintf(stderr, "body %u p=(%d,%d) v=(%d,%d)\n", index,
					body->center.x, body->center.y, body->velocity_per_tick.x,
					body->velocity_per_tick.y);
			}
		}
		assert(err == 0);
		assert_bodies_inside_arena(&world);
		assert_ropes_inside_arena(&world);
		assert_joint_lengths_bounded(&world);
		assert(world.physics.last_possible_pair_count == CANONICAL_POSSIBLE_PAIR_COUNT);
		assert(world.physics.last_candidate_pair_count <=
		       world.physics.last_possible_pair_count);
		assert(world.physics.last_occupied_grid_cell_count > 0U);
		assert(world.physics.last_broad_phase_fallback == 0U);
		assert(world.physics.last_work.revolute_motor_count == 1U);
		assert(world.physics.last_work.revolute_limit_count == 1U);
		assert(world.physics.last_work.prismatic_joint_count == 1U);
		assert(world.physics.last_work.prismatic_motor_count == 1U);
		assert(world.physics.last_work.prismatic_limit_count == 1U);
		assert(world.physics.last_work.spring_joint_count == 1U);
		assert(world.physics.last_work.rope_count == PICOSYSTEM_GAME_ROPE_COUNT);
		assert(world.physics.last_work.rope_particle_count == 8U);
		assert(world.physics.last_work.rope_solver_iteration_count ==
		       PICOSYSTEM_PHYSICS_ROPE_SOLVER_ITERATIONS);
		assert(world.physics.last_work.rope_collision_possible_pair_count ==
		       6U * (PICOSYSTEM_GAME_BODY_COUNT + PICOSYSTEM_GAME_STATIC_SEGMENT_COUNT) *
			       PICOSYSTEM_PHYSICS_ROPE_COLLISION_ITERATIONS);
		assert(world.physics.last_work.rope_collision_candidate_pair_count <=
		       world.physics.last_work.rope_collision_possible_pair_count);
		assert(world.physics.last_work.rope_collision_contact_count <=
		       world.physics.last_work.rope_collision_candidate_pair_count);
		assert(world.physics.last_work.rope_collision_position_changed_count <=
		       world.physics.last_work.rope_collision_contact_count);
		assert(world.physics.last_work.rope_collision_velocity_changed_count <=
		       world.physics.last_work.rope_collision_contact_count);
		if (world.physics.last_work.rope_collision_contact_count > 0U) {
			saw_rope_collision = true;
		}
		if (world.physics.last_work.rope_collision_candidate_pair_count >
		    maximum_rope_collision_candidate_count) {
			maximum_rope_collision_candidate_count =
				world.physics.last_work.rope_collision_candidate_pair_count;
		}
		if (world.physics.last_work.rope_collision_contact_count >
		    maximum_rope_collision_contact_count) {
			maximum_rope_collision_contact_count =
				world.physics.last_work.rope_collision_contact_count;
		}
		assert(world.physics.last_work.joint_motor_solver_visit_count >= 1U);
		if (world.physics.last_work.sleeping_body_count > 0U) {
			saw_sleep = true;
			if (first_sleep_tick == UINT32_MAX) {
				first_sleep_tick = world.logic_tick_count;
			}
		}
		if (world.physics.last_work.body_wake_transition_count > 0U) {
			saw_wake = true;
			if (first_wake_tick == UINT32_MAX) {
				first_wake_tick = world.logic_tick_count;
			}
		}
		if (world.physics.last_work.sleeping_body_count > maximum_sleeping_body_count) {
			maximum_sleeping_body_count = world.physics.last_work.sleeping_body_count;
		}
		for (uint16_t index = 0U; index < world.physics.body_count; ++index) {
			if (world.physics.sleep_quiet_tick_counts[index] >
			    maximum_quiet_tick_count) {
				maximum_quiet_tick_count =
					world.physics.sleep_quiet_tick_counts[index];
			}
		}
		const picosystem_physics_fixed_t limit_violation =
			maximum_revolute_limit_violation(&world);
		if (limit_violation > maximum_limit_violation) {
			maximum_limit_violation = limit_violation;
		}
		const picosystem_physics_fixed_t prismatic_violation =
			maximum_prismatic_limit_violation(&world);
		if (prismatic_violation > maximum_prismatic_violation) {
			maximum_prismatic_violation = prismatic_violation;
		}
		if (world.physics.prismatic_joints[0].motor_speed_per_tick > 0) {
			saw_positive_prismatic_motor = true;
		} else if (world.physics.prismatic_joints[0].motor_speed_per_tick < 0) {
			saw_negative_prismatic_motor = true;
		}
		if (world.physics.last_candidate_pair_count <
		    world.physics.last_possible_pair_count) {
			saw_candidate_reduction = true;
		}
		if (world.physics.last_candidate_pair_count < minimum_candidate_count) {
			minimum_candidate_count = world.physics.last_candidate_pair_count;
		}
		if (world.physics.last_candidate_pair_count > maximum_candidate_count) {
			maximum_candidate_count = world.physics.last_candidate_pair_count;
		}
		if (world.physics.contact_count > maximum_contact_count) {
			maximum_contact_count = world.physics.contact_count;
		}
		if (world.physics.last_solver_iteration_count > maximum_solver_iteration_count) {
			maximum_solver_iteration_count = world.physics.last_solver_iteration_count;
		}

		for (uint16_t index = 0U; index < world.physics.contact_count; ++index) {
			if (world.physics.contacts[index].type == PICOSYSTEM_PHYSICS_CONTACT_BODY) {
				saw_body_contact = true;
			} else {
				saw_static_contact = true;
			}
		}
		for (uint16_t index = 0U; index < world.physics.contact_event_count; ++index) {
			const struct picosystem_physics_contact_event *const event =
				&world.physics.contact_events[index];
			if (event->type != PICOSYSTEM_PHYSICS_CONTACT_EVENT_BODY_BOX_SENSOR) {
				continue;
			}
			if (event->phase == PICOSYSTEM_PHYSICS_CONTACT_EVENT_BEGIN) {
				++observed_sensor_begin_count;
			} else if (event->phase == PICOSYSTEM_PHYSICS_CONTACT_EVENT_STAY) {
				saw_sensor_stay = true;
			} else if (event->phase == PICOSYSTEM_PHYSICS_CONTACT_EVENT_END) {
				saw_sensor_end = true;
			}
		}
	}

	assert(saw_body_contact);
	assert(saw_static_contact);
	assert(saw_candidate_reduction);
	assert(saw_positive_prismatic_motor);
	assert(saw_negative_prismatic_motor);
	assert(observed_sensor_begin_count > 0U);
	assert(world.sensor_entry_count == observed_sensor_begin_count);
	assert(saw_sensor_stay);
	assert(saw_sensor_end);
	assert(saw_rope_collision);
	fprintf(stderr,
		"candidate range: %u-%u/%u, max contacts: %u, max solver: %u, max angular "
		"limit violation: %d q16 rad, max prismatic violation: %d q16 px, max "
		"sleeping: %u, max quiet: %u, rope collision max=%u/%u, first sleep/wake: "
		"%u/%u, observed=%s/%s\n",
		minimum_candidate_count, maximum_candidate_count, CANONICAL_POSSIBLE_PAIR_COUNT,
		maximum_contact_count, maximum_solver_iteration_count, maximum_limit_violation,
		maximum_prismatic_violation, maximum_sleeping_body_count, maximum_quiet_tick_count,
		maximum_rope_collision_candidate_count, maximum_rope_collision_contact_count,
		first_sleep_tick, first_wake_tick, saw_sleep ? "yes" : "no",
		saw_wake ? "yes" : "no");
	world.logic_tick_count = UINT32_MAX;
	assert(picosystem_game_world_step(&world, &inputs[0]) == 0);
	assert(world.logic_tick_count == UINT32_MAX);
}

static void replay_pattern(struct picosystem_game_world *world)
{
	static const struct picosystem_game_input inputs[] = {
		{.horizontal = 1},
		{.vertical = -1},
		{.horizontal = -1, .vertical = 1},
		{0},
	};

	for (uint32_t step = 0U; step < 10000U; ++step) {
		const size_t input_index = step % (sizeof(inputs) / sizeof(inputs[0]));
		assert(picosystem_game_world_step(world, &inputs[input_index]) == 0);
	}
}

static void test_reset_replay_is_bit_exact(void)
{
	struct picosystem_game_world first;
	assert(picosystem_game_world_reset(&first) == 0);
	replay_pattern(&first);

	struct picosystem_game_world second;
	assert(picosystem_game_world_reset(&second) == 0);
	replay_pattern(&second);

	assert_world_equal(&first, &second);
	assert_hash("replay-10000", picosystem_game_world_hash(&first), EXPECTED_REPLAY_10000_HASH);
}

static void test_sleep_smoke_golden(void)
{
	struct picosystem_game_world world;
	assert(picosystem_game_world_reset(&world) == 0);
	const struct picosystem_game_input neutral = {0};
	while ((world.logic_tick_count < 5000U) && (world.physics.sleeping_body_mask == 0U)) {
		assert(picosystem_game_world_step(&world, &neutral) == 0);
	}
	if (world.physics.sleeping_body_mask == 0U) {
		for (uint16_t index = 0U; index < world.physics.body_count; ++index) {
			const struct picosystem_physics_body *const body =
				&world.physics.bodies[index];
			fprintf(stderr, "awake body %u: velocity=(%d,%d), angular=%d, quiet=%u\n",
				index, body->velocity_per_tick.x, body->velocity_per_tick.y,
				body->angular_velocity_per_tick,
				world.physics.sleep_quiet_tick_counts[index]);
		}
	}
	assert(world.physics.sleeping_body_mask != 0U);
	if (world.logic_tick_count != EXPECTED_SLEEP_SMOKE_TICK) {
		fprintf(stderr, "sleep-smoke tick: %u\n", world.logic_tick_count);
	}
	assert(world.logic_tick_count == EXPECTED_SLEEP_SMOKE_TICK);
	assert_hash("sleep-smoke", picosystem_game_world_hash(&world), EXPECTED_SLEEP_SMOKE_HASH);
}

static void test_canonical_neutral_sleep_and_input_wake(void)
{
	struct picosystem_game_world world;
	assert(picosystem_game_world_reset(&world) == 0);
	const struct picosystem_game_input neutral = {0};
	uint32_t first_sleep_tick = 0U;
	for (uint32_t tick = 0U; tick < 5000U; ++tick) {
		assert(picosystem_game_world_step(&world, &neutral) == 0);
		if (world.physics.sleeping_body_mask != 0U) {
			first_sleep_tick = world.logic_tick_count;
			break;
		}
	}
	assert(first_sleep_tick != 0U);
	const uint32_t sleeping_body_count =
		(uint32_t)__builtin_popcount((unsigned int)world.physics.sleeping_body_mask);
	assert(sleeping_body_count > 0U);
	const struct picosystem_game_input right = {.horizontal = 1};
	assert(picosystem_game_world_step(&world, &right) == 0);
	assert(world.physics.sleeping_body_mask == 0U);
	assert(world.physics.last_work.body_wake_transition_count == sleeping_body_count);
	fprintf(stderr, "neutral first sleep/wake: %u/%u (%u bodies)\n", first_sleep_tick,
		world.logic_tick_count, sleeping_body_count);
}

static int32_t granular_boundary_distance(const struct picosystem_granular_particle *particle,
					  const struct picosystem_granular_boundary *boundary)
{
	const int64_t delta_x = (int64_t)particle->position.x - boundary->start.x;
	const int64_t delta_y = (int64_t)particle->position.y - boundary->start.y;
	return (int32_t)(((delta_x * boundary->inward_normal.x) +
			  (delta_y * boundary->inward_normal.y)) /
			 PICOSYSTEM_PHYSICS_FIXED_ONE);
}

static void assert_grains_inside_hourglass(const struct picosystem_game_world *world)
{
	const int32_t boundary_tolerance = PICOSYSTEM_PHYSICS_FIXED_RATIO(1, 8);
	assert(world->scene_id == PICOSYSTEM_GAME_SCENE_HOURGLASS);
	for (uint16_t particle_index = 0U; particle_index < world->granular.particle_count;
	     ++particle_index) {
		const struct picosystem_granular_particle *const particle =
			&world->granular.particles[particle_index];
		for (uint16_t boundary_index = 0U; boundary_index < world->granular.boundary_count;
		     ++boundary_index) {
			const struct picosystem_granular_boundary *const boundary =
				&world->granular.boundaries[boundary_index];
			if ((particle->position.y < boundary->active_minimum_y) ||
			    (particle->position.y > boundary->active_maximum_y)) {
				continue;
			}
			const int32_t distance = granular_boundary_distance(particle, boundary);
			if (distance < world->granular.particle_radius - boundary_tolerance) {
				fprintf(stderr,
					"escaped grain=%u boundary=%u position=(%d,%d) distance=%d "
					"radius=%d tick=%u\n",
					particle_index, boundary_index, particle->position.x,
					particle->position.y, distance,
					world->granular.particle_radius, world->logic_tick_count);
			}
			assert(distance >= world->granular.particle_radius - boundary_tolerance);
		}
	}
}

static void run_hourglass_neutral(struct picosystem_game_world *world, uint32_t tick_count)
{
	const struct picosystem_game_input neutral = {0};
	for (uint32_t tick = 0U; tick < tick_count; ++tick) {
		assert(picosystem_game_world_step(world, &neutral) == 0);
		assert_grains_inside_hourglass(world);
		assert(world->granular.last_work.candidate_pair_count <=
		       world->granular.last_work.possible_pair_count);
	}
}

static uint32_t fake_granular_clock_now(void *context)
{
	uint32_t *const next_cycle = context;
	return (*next_cycle)++;
}

static void run_hourglass_neutral_with_unfiltered_reference(struct picosystem_game_world *world,
							    uint32_t tick_count)
{
	struct picosystem_game_world unfiltered;
	assert(picosystem_game_world_reset_scene(&unfiltered, PICOSYSTEM_GAME_SCENE_HOURGLASS) ==
	       0);
	memset(unfiltered.granular.grid_boundary_masks, UINT8_MAX,
	       sizeof(unfiltered.granular.grid_boundary_masks));

	const struct picosystem_game_input neutral = {0};
	uint32_t next_cycle = 0U;
	const struct picosystem_physics_clock clock = {
		.now = fake_granular_clock_now,
		.context = &next_cycle,
	};
	for (uint32_t tick = 0U; tick < tick_count; ++tick) {
		assert(picosystem_game_world_step(world, &neutral) == 0);
		struct picosystem_granular_step_profile profile;
		assert(picosystem_game_world_step_granular_profiled(&unfiltered, &neutral, &clock,
								    &profile) == 0);
		assert(profile.clock_read_count ==
		       (10U + (6U * PICOSYSTEM_GRANULAR_SOLVER_ITERATIONS)));
		assert(profile.work.candidate_pair_count > 0U);
		assert_grains_inside_hourglass(world);
		assert_grains_inside_hourglass(&unfiltered);
		assert(picosystem_game_world_hash(world) ==
		       picosystem_game_world_hash(&unfiltered));
	}
}

static void test_hourglass_scene_flow_flip_and_replay(void)
{
	struct picosystem_game_world world;
	assert(picosystem_game_world_reset_scene(&world, PICOSYSTEM_GAME_SCENE_HOURGLASS) == 0);
	assert(world.granular.particle_count == EXPECTED_HOURGLASS_GRAIN_COUNT);
	assert(world.granular.boundary_count == 6U);
	assert(picosystem_game_world_focus_body(&world) != NULL);
	assert(picosystem_game_world_hash(&world) != 0U);
	const struct picosystem_game_world initial = world;
	assert(picosystem_game_world_apply_scene_action(
		       NULL, PICOSYSTEM_GAME_SCENE_ACTION_PRIMARY) == -EINVAL);
	assert(picosystem_game_world_apply_scene_action(
		       &world, PICOSYSTEM_GAME_SCENE_ACTION_COUNT) == -ERANGE);
	assert(memcmp(&world, &initial, sizeof(world)) == 0);

	assert(picosystem_game_world_apply_scene_action(&world,
							PICOSYSTEM_GAME_SCENE_ACTION_PRIMARY) == 0);
	assert(picosystem_granular_world_lower_particle_count(&world.granular) ==
	       EXPECTED_HOURGLASS_GRAIN_COUNT);
	assert(picosystem_game_world_apply_scene_action(&world,
							PICOSYSTEM_GAME_SCENE_ACTION_PRIMARY) == 0);
	assert(picosystem_game_world_hash(&world) == picosystem_game_world_hash(&initial));

	run_hourglass_neutral_with_unfiltered_reference(&world, 3000U);
	const uint16_t first_lower_count =
		picosystem_granular_world_lower_particle_count(&world.granular);
	assert(first_lower_count >= EXPECTED_HOURGLASS_DRAIN_COUNT);
	assert(world.sensor_entry_count == world.granular.passage_count);
	assert(world.sensor_entry_count >= first_lower_count);

	assert(picosystem_game_world_apply_scene_action(&world,
							PICOSYSTEM_GAME_SCENE_ACTION_PRIMARY) == 0);
	assert(picosystem_granular_world_lower_particle_count(&world.granular) <= 10U);
	run_hourglass_neutral(&world, 3000U);
	const uint16_t second_lower_count =
		picosystem_granular_world_lower_particle_count(&world.granular);
	assert(second_lower_count >= EXPECTED_HOURGLASS_DRAIN_COUNT);
	assert(world.sensor_entry_count >= (2U * EXPECTED_HOURGLASS_DRAIN_COUNT));
	fprintf(stderr,
		"hourglass hash=%08x lower=%u/%u passages=%u candidates=%u/%u contacts=%u\n",
		picosystem_game_world_hash(&world), second_lower_count,
		world.granular.particle_count, world.sensor_entry_count,
		world.granular.last_work.candidate_pair_count,
		world.granular.last_work.possible_pair_count,
		world.granular.last_work.contact_count);
}

int main(void)
{
	test_scene_catalog();
	test_clockwork_scene_is_bounded_and_deterministic();
	test_marble_machine_scene_is_bounded_and_deterministic();
	test_hourglass_scene_flow_flip_and_replay();
	test_bounded_motion_contacts_and_saturated_tick();
	test_canonical_reset_and_golden_replay();
	test_validation_preserves_state();
	test_chain_fixture_boundaries_and_replay();
	test_reset_replay_is_bit_exact();
	test_sleep_smoke_golden();
	test_canonical_neutral_sleep_and_input_wake();
	puts("game-world tests passed");
	return 0;
}
