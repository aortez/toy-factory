/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "game_demo.h"

#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/util.h>

#if defined(CONFIG_TOY_FACTORY_CORE1_RUNTIME)
#include "dense_scene.h"
#endif
#include "display_sync.h"
#include "scene_renderer.h"

LOG_MODULE_REGISTER(picosystem_game_demo, LOG_LEVEL_INF);

#define JOINT_PIXEL_QUANTUM 4
#define MAX_DIRTY_REGIONS                                                                          \
	((2U * (PICOSYSTEM_PHYSICS_MAX_BODIES +                                                    \
		(PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS *                                          \
		 PICOSYSTEM_SCENE_JOINT_DAMAGE_SEGMENT_COUNT) +                                    \
		PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS + PICOSYSTEM_PHYSICS_MAX_ROPES +            \
		PICOSYSTEM_SCENE_MAX_BOX_SENSORS + 1U)) +                                          \
	 PICOSYSTEM_SCENE_MAX_SEGMENTS)
#define RENDER_THREAD_STACK_SIZE 5120U
#if defined(CONFIG_TOY_FACTORY_CORE1_FULL_FRAME_RENDERER)
#define RENDER_THREAD_PRIORITY -1
#else
#define RENDER_THREAD_PRIORITY 2
#endif
#define FRAMEBUFFER_CAPTURE_TIMEOUT_MS 2000

struct game_renderer_metrics {
	struct picosystem_graphics_stats graphics;
	uint32_t published_snapshot_count;
	uint32_t superseded_snapshot_count;
	uint32_t presented_snapshot_sequence;
	uint32_t presented_frame_count;
	uint32_t full_redraw_count;
	uint32_t last_render_time_us;
	uint32_t last_raster_time_us;
	uint32_t maximum_raster_time_us;
	uint32_t core1_raster_frame_count;
	uint32_t max_dirty_render_time_us;
	uint32_t last_dirty_present_time_us;
	uint32_t last_dirty_pixel_count;
	uint16_t last_dirty_region_count;
	uint32_t last_snapshot_age_us;
	uint32_t max_dirty_snapshot_age_us;
	uint32_t render_stack_size_bytes;
	uint32_t render_stack_used_bytes;
	uint16_t presented_focus_x;
	uint16_t presented_focus_y;
	int render_error;
	bool last_raster_on_core1;
	bool render_thread_running;
};

struct game_dirty_render_stats {
	uint32_t raster_time_us;
	uint32_t present_time_us;
	uint32_t pixel_count;
	uint16_t region_count;
	bool raster_on_core1;
};

struct game_renderer_context {
	struct k_spinlock lock;
	struct k_sem snapshot_ready;
	struct k_sem frame_presented;
	struct k_mutex framebuffer_mutex;
	struct picosystem_scene_snapshot snapshots[2];
	struct game_renderer_metrics metrics;
	struct picosystem_graphics_stats live_graphics;
	uint8_t published_index;
	bool core1_available;
	bool snapshot_available;
};

K_THREAD_STACK_DEFINE(render_thread_stack, RENDER_THREAD_STACK_SIZE);
static struct k_thread render_thread;
static struct game_renderer_context renderer;

#if defined(CONFIG_TOY_FACTORY_CORE1_FULL_FRAME_RENDERER)
BUILD_ASSERT(RENDER_THREAD_PRIORITY < CONFIG_MAIN_THREAD_PRIORITY);
BUILD_ASSERT(RENDER_THREAD_PRIORITY < CONFIG_SHELL_THREAD_PRIORITY);
#else
BUILD_ASSERT(RENDER_THREAD_PRIORITY > CONFIG_MAIN_THREAD_PRIORITY);
BUILD_ASSERT(RENDER_THREAD_PRIORITY > CONFIG_SHELL_THREAD_PRIORITY);
#endif
/* Keep two snapshots and the auxiliary-core mailbox bounded after adding packed grains. */
BUILD_ASSERT(sizeof(struct picosystem_scene_snapshot) <= 1152U);
BUILD_ASSERT(PICOSYSTEM_GRANULAR_MAX_PARTICLES <= UINT16_MAX);
BUILD_ASSERT((PICOSYSTEM_GAME_TICK_RATE_HZ % PICOSYSTEM_GAME_REALTIME_SNAPSHOT_RATE_HZ) == 0U);
BUILD_ASSERT(PICOSYSTEM_GAME_BOX_SENSOR_COUNT <= PICOSYSTEM_SCENE_MAX_BOX_SENSORS);

static bool core1_full_frame_renderer_enabled(void)
{
	return IS_ENABLED(CONFIG_TOY_FACTORY_CORE1_FULL_FRAME_RENDERER) && renderer.core1_available;
}

static void increment_saturated(uint32_t *value)
{
	if (*value < UINT32_MAX) {
		++*value;
	}
}

static void add_saturated(uint32_t *value, uint32_t increment)
{
	if (increment > (UINT32_MAX - *value)) {
		*value = UINT32_MAX;
	} else {
		*value += increment;
	}
}

static void add_u64_saturated(uint64_t *value, uint32_t increment)
{
	if (increment > (UINT64_MAX - *value)) {
		*value = UINT64_MAX;
	} else {
		*value += increment;
	}
}

static uint32_t mean_time_us(uint64_t total, uint32_t count)
{
	if (count == 0U) {
		return 0U;
	}
	return (uint32_t)MIN(total / count, UINT32_MAX);
}

static uint32_t cycles_to_us(uint32_t cycles)
{
	return MAX(k_cyc_to_us_floor32(cycles), 1U);
}

static int16_t fixed_to_pixel(int32_t value)
{
	return (int16_t)(value / PICOSYSTEM_GAME_FIXED_ONE);
}

static int32_t fixed_multiply(int32_t left, int32_t right)
{
	return (int32_t)(((int64_t)left * right) / PICOSYSTEM_GAME_FIXED_ONE);
}

static int16_t quantize_joint_pixel(int16_t value)
{
	const int32_t adjusted = (value >= 0) ? (int32_t)value + (JOINT_PIXEL_QUANTUM / 2)
					      : (int32_t)value - (JOINT_PIXEL_QUANTUM / 2);
	return (int16_t)((adjusted / JOINT_PIXEL_QUANTUM) * JOINT_PIXEL_QUANTUM);
}

static int16_t velocity_to_pixels_per_second(int32_t velocity_per_tick)
{
	const int64_t pixels_per_second =
		((int64_t)velocity_per_tick * PICOSYSTEM_GAME_TICK_RATE_HZ) /
		PICOSYSTEM_GAME_FIXED_ONE;
	return (int16_t)CLAMP(pixels_per_second, INT16_MIN, INT16_MAX);
}

static int32_t angular_velocity_to_milliradians_per_second(int32_t angular_velocity_per_tick)
{
	return (int32_t)(((int64_t)angular_velocity_per_tick * PICOSYSTEM_GAME_TICK_RATE_HZ *
			  1000) /
			 PICOSYSTEM_GAME_FIXED_ONE);
}

static bool rectangles_touch_or_intersect(const struct picosystem_rect *left,
					  const struct picosystem_rect *right)
{
	return (left->x <= (right->x + right->width)) && (right->x <= (left->x + left->width)) &&
	       (left->y <= (right->y + right->height)) && (right->y <= (left->y + left->height));
}

static struct picosystem_rect union_rectangles(const struct picosystem_rect *left,
					       const struct picosystem_rect *right)
{
	const uint16_t x = MIN(left->x, right->x);
	const uint16_t y = MIN(left->y, right->y);
	const uint16_t far_x = MAX(left->x + left->width, right->x + right->width);
	const uint16_t far_y = MAX(left->y + left->height, right->y + right->height);

	return (struct picosystem_rect){
		.x = x,
		.y = y,
		.width = far_x - x,
		.height = far_y - y,
	};
}

static bool snapshot_scene_matches(const struct picosystem_scene_snapshot *left,
				   const struct picosystem_scene_snapshot *right)
{
	if ((left->body_count != right->body_count) || (left->scene_id != right->scene_id) ||
	    (left->static_segment_count != right->static_segment_count) ||
	    (left->distance_joint_count != right->distance_joint_count) ||
	    (left->revolute_joint_count != right->revolute_joint_count) ||
	    (left->box_sensor_count != right->box_sensor_count) ||
	    (left->rope_count != right->rope_count) ||
	    (left->granular_particle_count != right->granular_particle_count) ||
	    (left->granular_particle_radius != right->granular_particle_radius)) {
		return false;
	}

	if (left->scene_id == PICOSYSTEM_GAME_SCENE_HOURGLASS) {
		for (uint16_t index = 0U; index < left->static_segment_count; ++index) {
			const struct picosystem_scene_segment *const left_segment =
				&left->payload.granular.boundaries[index];
			const struct picosystem_scene_segment *const right_segment =
				&right->payload.granular.boundaries[index];
			if ((left_segment->start_x != right_segment->start_x) ||
			    (left_segment->start_y != right_segment->start_y) ||
			    (left_segment->end_x != right_segment->end_x) ||
			    (left_segment->end_y != right_segment->end_y)) {
				return false;
			}
		}
		return true;
	}

	const struct picosystem_scene_rigid_payload *const left_rigid = &left->payload.rigid;
	const struct picosystem_scene_rigid_payload *const right_rigid = &right->payload.rigid;
	if ((left_rigid->conveyor_forward_segment_mask !=
	     right_rigid->conveyor_forward_segment_mask) ||
	    (left_rigid->conveyor_reverse_segment_mask !=
	     right_rigid->conveyor_reverse_segment_mask)) {
		return false;
	}
	for (uint16_t index = 0U; index < left->body_count; ++index) {
		if ((left_rigid->bodies[index].id != right_rigid->bodies[index].id) ||
		    (left_rigid->bodies[index].shape != right_rigid->bodies[index].shape) ||
		    (left_rigid->bodies[index].radius != right_rigid->bodies[index].radius) ||
		    ((left_rigid->bodies[index].shape == PICOSYSTEM_PHYSICS_SHAPE_CIRCLE) &&
		     (left_rigid->bodies[index].geometry.circle.render_style !=
		      right_rigid->bodies[index].geometry.circle.render_style))) {
			return false;
		}
	}
	for (uint16_t index = 0U; index < left->static_segment_count; ++index) {
		const struct picosystem_scene_segment *const left_segment =
			&left_rigid->static_segments[index];
		const struct picosystem_scene_segment *const right_segment =
			&right_rigid->static_segments[index];
		if ((left_segment->start_x != right_segment->start_x) ||
		    (left_segment->start_y != right_segment->start_y) ||
		    (left_segment->end_x != right_segment->end_x) ||
		    (left_segment->end_y != right_segment->end_y)) {
			return false;
		}
	}
	for (uint16_t index = 0U; index < left->rope_count; ++index) {
		if ((left_rigid->ropes[index].id != right_rigid->ropes[index].id) ||
		    (left_rigid->ropes[index].particle_count !=
		     right_rigid->ropes[index].particle_count)) {
			return false;
		}
	}
	for (uint16_t index = 0U; index < left->box_sensor_count; ++index) {
		const struct picosystem_scene_box_sensor *const left_sensor =
			&left_rigid->box_sensors[index];
		const struct picosystem_scene_box_sensor *const right_sensor =
			&right_rigid->box_sensors[index];
		if ((left_sensor->id != right_sensor->id) ||
		    (left_sensor->bounds.x != right_sensor->bounds.x) ||
		    (left_sensor->bounds.y != right_sensor->bounds.y) ||
		    (left_sensor->bounds.width != right_sensor->bounds.width) ||
		    (left_sensor->bounds.height != right_sensor->bounds.height)) {
			return false;
		}
	}
	for (uint16_t index = 0U; index < left->distance_joint_count; ++index) {
		const struct picosystem_scene_joint *const left_joint =
			&left_rigid->distance_joints[index];
		const struct picosystem_scene_joint *const right_joint =
			&right_rigid->distance_joints[index];
		if ((left_joint->id != right_joint->id) ||
		    (left_joint->target_radius != right_joint->target_radius)) {
			return false;
		}
		const bool spring =
			(left_joint->target_radius & PICOSYSTEM_SCENE_JOINT_SPRING_FLAG) != 0U;
		const uint16_t target_radius =
			left_joint->target_radius & PICOSYSTEM_SCENE_JOINT_TARGET_RADIUS_MASK;
		if (!spring && (target_radius != 0U) &&
		    ((left_joint->anchor_b_x != right_joint->anchor_b_x) ||
		     (left_joint->anchor_b_y != right_joint->anchor_b_y))) {
			return false;
		}
	}
	for (uint16_t index = 0U; index < left->revolute_joint_count; ++index) {
		if (left_rigid->revolute_joints[index].id !=
		    right_rigid->revolute_joints[index].id) {
			return false;
		}
	}
	return true;
}

static bool snapshot_requires_full_redraw(const struct picosystem_scene_snapshot *snapshot)
{
	return snapshot->scene_id == PICOSYSTEM_GAME_SCENE_HOURGLASS;
}

static size_t merge_dirty_regions(struct picosystem_rect *regions, size_t count,
				  bool preserve_pixel_area)
{
	while (true) {
		bool merged = false;
		for (size_t left = 0U; left < count; ++left) {
			for (size_t right = left + 1U; right < count; ++right) {
				if (!rectangles_touch_or_intersect(&regions[left],
								   &regions[right])) {
					continue;
				}
				const struct picosystem_rect joined =
					union_rectangles(&regions[left], &regions[right]);
				const uint32_t separate_area =
					((uint32_t)regions[left].width * regions[left].height) +
					((uint32_t)regions[right].width * regions[right].height);
				const uint32_t joined_area = (uint32_t)joined.width * joined.height;
				if (preserve_pixel_area && (joined_area > separate_area)) {
					continue;
				}

				regions[left] = joined;
				for (size_t index = right; (index + 1U) < count; ++index) {
					regions[index] = regions[index + 1U];
				}
				--count;
				merged = true;
				break;
			}
			if (merged) {
				break;
			}
		}
		if (!merged) {
			return count;
		}
	}
}

static bool body_render_state_matches(const struct picosystem_scene_body *left,
				      const struct picosystem_scene_body *right)
{
	if ((left->center_x != right->center_x) || (left->center_y != right->center_y) ||
	    (left->shape != right->shape) || (left->radius != right->radius) ||
	    (left->id != right->id) || (left->sleeping != right->sleeping)) {
		return false;
	}
	if (left->shape == PICOSYSTEM_PHYSICS_SHAPE_CIRCLE) {
		if (left->geometry.circle.render_style != right->geometry.circle.render_style) {
			return false;
		}
		return (left->geometry.circle.render_style !=
			PICOSYSTEM_GAME_BODY_RENDER_STYLE_GEAR) ||
		       (left->geometry.circle.orientation == right->geometry.circle.orientation);
	}

	for (size_t index = 0U; index < PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT; ++index) {
		if ((left->geometry.vertices[index].x != right->geometry.vertices[index].x) ||
		    (left->geometry.vertices[index].y != right->geometry.vertices[index].y)) {
			return false;
		}
	}
	return true;
}

static bool joint_render_state_matches(const struct picosystem_scene_joint *left,
				       const struct picosystem_scene_joint *right)
{
	if ((left->id != right->id) || (left->target_radius != right->target_radius)) {
		return false;
	}
	if ((left->target_radius & PICOSYSTEM_SCENE_JOINT_SPRING_FLAG) != 0U) {
		return (left->anchor_a_x == right->anchor_a_x) &&
		       (left->anchor_a_y == right->anchor_a_y) &&
		       (left->anchor_b_x == right->anchor_b_x) &&
		       (left->anchor_b_y == right->anchor_b_y);
	}
	if ((left->target_radius & PICOSYSTEM_SCENE_JOINT_TARGET_RADIUS_MASK) != 0U) {
		return (left->anchor_b_x == right->anchor_b_x) &&
		       (left->anchor_b_y == right->anchor_b_y);
	}
	return (left->anchor_a_x == right->anchor_a_x) && (left->anchor_a_y == right->anchor_a_y) &&
	       (left->anchor_b_x == right->anchor_b_x) && (left->anchor_b_y == right->anchor_b_y);
}

static bool rope_render_state_matches(const struct picosystem_scene_rope *left,
				      const struct picosystem_scene_rope *right)
{
	if ((left->id != right->id) || (left->particle_count != right->particle_count)) {
		return false;
	}
	for (uint8_t index = 0U; index < left->particle_count; ++index) {
		if ((left->particles[index].x != right->particles[index].x) ||
		    (left->particles[index].y != right->particles[index].y)) {
			return false;
		}
	}
	return true;
}

static int append_prismatic_guides(const struct picosystem_game_demo_state *state,
				   struct picosystem_scene_snapshot *snapshot)
{
	struct picosystem_scene_rigid_payload *const rigid = &snapshot->payload.rigid;

	for (uint16_t index = 0U; index < state->world.physics.prismatic_joint_count; ++index) {
		const struct picosystem_physics_prismatic_joint *const joint =
			&state->world.physics.prismatic_joints[index];
		if ((joint->body_b_id != PICOSYSTEM_PHYSICS_WORLD_BODY_ID) ||
		    (joint->limit_enabled == 0U)) {
			continue;
		}
		if ((snapshot->static_segment_count + 2U) > ARRAY_SIZE(rigid->static_segments)) {
			return -ENOSPC;
		}

		const struct picosystem_physics_body *const body =
			&state->world.physics.bodies[joint->body_a_index];
		int32_t guide_offset = body->radius;
		if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_BOX) {
			guide_offset = MAX(body->half_extent.x, body->half_extent.y);
		} else if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_CAPSULE) {
			guide_offset = body->half_extent.x + body->radius;
		}
		guide_offset += PICOSYSTEM_PHYSICS_FIXED_FROM_INT(4);
		const int32_t lower = joint->reference_translation + joint->lower_translation;
		const int32_t upper = joint->reference_translation + joint->upper_translation;
		const struct picosystem_physics_vector perpendicular = {
			.x = -joint->axis_b.y,
			.y = joint->axis_b.x,
		};
		const struct picosystem_physics_vector lower_center = {
			.x = joint->anchor_b.x + fixed_multiply(joint->axis_b.x, lower),
			.y = joint->anchor_b.y + fixed_multiply(joint->axis_b.y, lower),
		};
		const struct picosystem_physics_vector upper_center = {
			.x = joint->anchor_b.x + fixed_multiply(joint->axis_b.x, upper),
			.y = joint->anchor_b.y + fixed_multiply(joint->axis_b.y, upper),
		};
		const struct picosystem_physics_vector offset = {
			.x = fixed_multiply(perpendicular.x, guide_offset),
			.y = fixed_multiply(perpendicular.y, guide_offset),
		};

		rigid->static_segments[snapshot->static_segment_count++] =
			(struct picosystem_scene_segment){
				.start_x = fixed_to_pixel(lower_center.x + offset.x),
				.start_y = fixed_to_pixel(lower_center.y + offset.y),
				.end_x = fixed_to_pixel(upper_center.x + offset.x),
				.end_y = fixed_to_pixel(upper_center.y + offset.y),
			};
		rigid->static_segments[snapshot->static_segment_count++] =
			(struct picosystem_scene_segment){
				.start_x = fixed_to_pixel(lower_center.x - offset.x),
				.start_y = fixed_to_pixel(lower_center.y - offset.y),
				.end_x = fixed_to_pixel(upper_center.x - offset.x),
				.end_y = fixed_to_pixel(upper_center.y - offset.y),
			};
	}
	return 0;
}

static size_t build_dirty_regions(const struct picosystem_scene_snapshot *snapshot,
				  const struct picosystem_scene_snapshot *presented,
				  struct picosystem_rect *regions)
{
	const struct picosystem_scene_rigid_payload *const rigid = &snapshot->payload.rigid;
	const struct picosystem_scene_rigid_payload *const presented_rigid =
		&presented->payload.rigid;
	size_t count = 0U;
	for (uint16_t index = 0U; index < snapshot->body_count; ++index) {
		if (body_render_state_matches(&rigid->bodies[index],
					      &presented_rigid->bodies[index])) {
			continue;
		}
		const struct picosystem_rect current =
			picosystem_scene_body_bounds(&rigid->bodies[index]);
		const struct picosystem_rect previous =
			picosystem_scene_body_bounds(&presented_rigid->bodies[index]);
		regions[count++] = previous;
		regions[count++] = current;
	}
	count = merge_dirty_regions(regions, count, false);
	for (uint16_t index = 0U; index < snapshot->distance_joint_count; ++index) {
		if (joint_render_state_matches(&rigid->distance_joints[index],
					       &presented_rigid->distance_joints[index])) {
			continue;
		}
		for (uint8_t segment = 0U; segment < PICOSYSTEM_SCENE_JOINT_DAMAGE_SEGMENT_COUNT;
		     ++segment) {
			const struct picosystem_rect current =
				picosystem_scene_joint_segment_bounds(
					&rigid->distance_joints[index], segment);
			const struct picosystem_rect previous =
				picosystem_scene_joint_segment_bounds(
					&presented_rigid->distance_joints[index], segment);
			regions[count++] = previous;
			regions[count++] = current;
		}
	}
	for (uint16_t index = 0U; index < snapshot->revolute_joint_count; ++index) {
		if (joint_render_state_matches(&rigid->revolute_joints[index],
					       &presented_rigid->revolute_joints[index])) {
			continue;
		}
		regions[count++] = picosystem_scene_revolute_joint_bounds(
			&presented_rigid->revolute_joints[index]);
		regions[count++] =
			picosystem_scene_revolute_joint_bounds(&rigid->revolute_joints[index]);
	}
	for (uint16_t index = 0U; index < snapshot->rope_count; ++index) {
		if (rope_render_state_matches(&rigid->ropes[index],
					      &presented_rigid->ropes[index])) {
			continue;
		}
		regions[count++] = picosystem_scene_rope_bounds(&presented_rigid->ropes[index]);
		regions[count++] = picosystem_scene_rope_bounds(&rigid->ropes[index]);
	}
	for (uint16_t index = 0U; index < snapshot->box_sensor_count; ++index) {
		if (rigid->box_sensors[index].active !=
		    presented_rigid->box_sensors[index].active) {
			regions[count++] = rigid->box_sensors[index].bounds;
		}
	}
	if ((snapshot->logic_tick_count % PICOSYSTEM_SCENE_CONVEYOR_PHASE_COUNT) !=
	    (presented->logic_tick_count % PICOSYSTEM_SCENE_CONVEYOR_PHASE_COUNT)) {
		const uint32_t conveyor_mask =
			rigid->conveyor_forward_segment_mask | rigid->conveyor_reverse_segment_mask;
		for (uint16_t index = 0U; index < snapshot->static_segment_count; ++index) {
			if ((conveyor_mask & (UINT32_C(1) << index)) != 0U) {
				regions[count++] = picosystem_scene_conveyor_bounds(
					&rigid->static_segments[index]);
			}
		}
	}
	if (snapshot->sensor_entry_count != presented->sensor_entry_count) {
		regions[count++] = (struct picosystem_rect){
			.x = 2U,
			.y = 10U,
			.width = 18U,
			.height = 7U,
		};
	}
	return merge_dirty_regions(regions, count, true);
}

static int render_dirty_scene(const struct picosystem_scene_snapshot *snapshot,
			      const struct picosystem_scene_snapshot *presented,
			      struct game_dirty_render_stats *stats)
{
	struct picosystem_rect regions[MAX_DIRTY_REGIONS];
	const size_t region_count = build_dirty_regions(snapshot, presented, regions);
	*stats = (struct game_dirty_render_stats){0};

	for (size_t index = 0U; index < region_count; ++index) {
		const uint32_t raster_start_cycles = k_cycle_get_32();
		int err = picosystem_scene_render_region(snapshot, &regions[index]);
		stats->raster_time_us += cycles_to_us(k_cycle_get_32() - raster_start_cycles);
		if (err == 0) {
			err = picosystem_graphics_present_region(&renderer.live_graphics,
								 &regions[index]);
		}
		if (err != 0) {
			return err;
		}
		stats->present_time_us += renderer.live_graphics.last_present_time_us;
		stats->pixel_count += (uint32_t)regions[index].width * regions[index].height;
		++stats->region_count;
	}
	return 0;
}

static int snapshot_from_state(const struct picosystem_game_demo_state *state, uint32_t sequence,
			       struct picosystem_scene_snapshot *snapshot)
{
	*snapshot = (struct picosystem_scene_snapshot){
		.published_uptime_ticks = k_uptime_ticks(),
		.sequence = sequence,
		.logic_tick_count = state->world.logic_tick_count,
		.redraw_request_sequence = state->redraw_request_sequence,
		.sensor_entry_count = state->world.sensor_entry_count,
		.scene_id = state->world.scene_id,
	};
	if (state->world.scene_id == PICOSYSTEM_GAME_SCENE_HOURGLASS) {
		struct picosystem_scene_granular_payload *const granular =
			&snapshot->payload.granular;
		if ((state->world.granular.boundary_count > ARRAY_SIZE(granular->boundaries)) ||
		    (state->world.granular.particle_count > ARRAY_SIZE(granular->grains))) {
			return -ENOSPC;
		}
		snapshot->static_segment_count = (uint8_t)state->world.granular.boundary_count;
		snapshot->granular_particle_count = state->world.granular.particle_count;
		snapshot->granular_particle_radius =
			(uint8_t)fixed_to_pixel(state->world.granular.particle_radius);
		snapshot->granular_lower_particle_count =
			picosystem_granular_world_lower_particle_count(&state->world.granular);
		for (uint16_t index = 0U; index < snapshot->static_segment_count; ++index) {
			const struct picosystem_granular_boundary *const boundary =
				&state->world.granular.boundaries[index];
			granular->boundaries[index] = (struct picosystem_scene_segment){
				.start_x = fixed_to_pixel(boundary->start.x),
				.start_y = fixed_to_pixel(boundary->start.y),
				.end_x = fixed_to_pixel(boundary->end.x),
				.end_y = fixed_to_pixel(boundary->end.y),
			};
		}
		for (uint16_t index = 0U; index < snapshot->granular_particle_count; ++index) {
			const struct picosystem_granular_particle *const particle =
				&state->world.granular.particles[index];
			const int16_t particle_x = fixed_to_pixel(particle->position.x);
			const int16_t particle_y = fixed_to_pixel(particle->position.y);
			if ((particle_x < 0) || (particle_x >= PICOSYSTEM_GRAPHICS_WIDTH) ||
			    (particle_y < 0) || (particle_y >= PICOSYSTEM_GRAPHICS_HEIGHT)) {
				return -ERANGE;
			}
			granular->grains[index] = (struct picosystem_scene_grain){
				.x = (uint8_t)particle_x,
				.y = (uint8_t)particle_y,
			};
		}
		return 0;
	}
	struct picosystem_scene_rigid_payload *const rigid = &snapshot->payload.rigid;
	if ((state->world.physics.body_count > ARRAY_SIZE(rigid->bodies)) ||
	    (state->world.physics.static_segment_count > ARRAY_SIZE(rigid->static_segments)) ||
	    (state->world.physics.distance_joint_count > ARRAY_SIZE(rigid->distance_joints)) ||
	    (state->world.physics.revolute_joint_count > ARRAY_SIZE(rigid->revolute_joints)) ||
	    (state->world.physics.box_sensor_count > ARRAY_SIZE(rigid->box_sensors)) ||
	    (state->world.physics.rope_count > ARRAY_SIZE(rigid->ropes))) {
		return -ENOSPC;
	}
	snapshot->body_count = (uint8_t)state->world.physics.body_count;
	snapshot->static_segment_count = (uint8_t)state->world.physics.static_segment_count;
	snapshot->distance_joint_count = (uint8_t)state->world.physics.distance_joint_count;
	snapshot->revolute_joint_count = (uint8_t)state->world.physics.revolute_joint_count;
	snapshot->box_sensor_count = (uint8_t)state->world.physics.box_sensor_count;
	snapshot->rope_count = (uint8_t)state->world.physics.rope_count;
	for (uint16_t index = 0U; index < snapshot->body_count; ++index) {
		const struct picosystem_physics_body *const body =
			&state->world.physics.bodies[index];
		rigid->bodies[index] = (struct picosystem_scene_body){
			.center_x = fixed_to_pixel(body->center.x),
			.center_y = fixed_to_pixel(body->center.y),
			.radius = (uint16_t)fixed_to_pixel(body->radius),
			.id = body->id,
			.shape = body->shape,
			.sleeping = picosystem_physics_world_body_is_sleeping(&state->world.physics,
									      index),
		};
		rigid->bodies[index].geometry.circle.orientation =
			(uint8_t)(body->angle_turns >> 26U);
		rigid->bodies[index].geometry.circle.render_style =
			(uint8_t)picosystem_game_world_body_render_style(&state->world, index);
		if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_BOX) {
			struct picosystem_physics_vector
				vertices[PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT];
			const int err = picosystem_physics_body_box_vertices(body, vertices);
			if (err != 0) {
				return err;
			}
			for (size_t vertex = 0U; vertex < PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT;
			     ++vertex) {
				rigid->bodies[index].geometry.vertices[vertex].x =
					fixed_to_pixel(vertices[vertex].x);
				rigid->bodies[index].geometry.vertices[vertex].y =
					fixed_to_pixel(vertices[vertex].y);
			}
		} else if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_CAPSULE) {
			struct picosystem_physics_vector
				vertices[PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT];
			const int err = picosystem_physics_body_capsule_vertices(body, vertices);
			if (err != 0) {
				return err;
			}
			for (size_t vertex = 0U; vertex < PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT;
			     ++vertex) {
				rigid->bodies[index].geometry.vertices[vertex].x =
					fixed_to_pixel(vertices[vertex].x);
				rigid->bodies[index].geometry.vertices[vertex].y =
					fixed_to_pixel(vertices[vertex].y);
			}
		} else if (body->shape != PICOSYSTEM_PHYSICS_SHAPE_CIRCLE) {
			return -ERANGE;
		}
	}
	for (uint16_t index = 0U; index < state->world.physics.static_segment_count; ++index) {
		const struct picosystem_physics_static_segment *const segment =
			&state->world.physics.static_segments[index];
		rigid->static_segments[index] = (struct picosystem_scene_segment){
			.start_x = fixed_to_pixel(segment->start.x),
			.start_y = fixed_to_pixel(segment->start.y),
			.end_x = fixed_to_pixel(segment->end.x),
			.end_y = fixed_to_pixel(segment->end.y),
		};
		const uint32_t segment_mask = UINT32_C(1) << index;
		if (segment->surface_speed_per_tick > 0) {
			rigid->conveyor_forward_segment_mask |= segment_mask;
		} else if (segment->surface_speed_per_tick < 0) {
			rigid->conveyor_reverse_segment_mask |= segment_mask;
		}
	}
	for (uint16_t index = 0U; index < snapshot->box_sensor_count; ++index) {
		const struct picosystem_physics_box_sensor *const sensor =
			&state->world.physics.box_sensors[index];
		const int16_t left = fixed_to_pixel(sensor->center.x - sensor->half_extent.x);
		const int16_t top = fixed_to_pixel(sensor->center.y - sensor->half_extent.y);
		const int16_t right = fixed_to_pixel(sensor->center.x + sensor->half_extent.x);
		const int16_t bottom = fixed_to_pixel(sensor->center.y + sensor->half_extent.y);
		if ((left < 0) || (top < 0) || (right < left) || (bottom < top) ||
		    (right >= PICOSYSTEM_GRAPHICS_WIDTH) ||
		    (bottom >= PICOSYSTEM_GRAPHICS_HEIGHT)) {
			return -ERANGE;
		}
		bool active = false;
		const uint8_t sensor_mask = (uint8_t)(UINT8_C(1) << index);
		for (uint16_t body = 0U; body < state->world.physics.body_count; ++body) {
			active |= (state->world.physics.active_sensor_contact_masks[body] &
				   sensor_mask) != 0U;
		}
		rigid->box_sensors[index] = (struct picosystem_scene_box_sensor){
			.bounds =
				{
					.x = (uint16_t)left,
					.y = (uint16_t)top,
					.width = (uint16_t)(right - left + 1),
					.height = (uint16_t)(bottom - top + 1),
				},
			.id = sensor->id,
			.active = active ? 1U : 0U,
		};
	}
	for (uint16_t index = 0U; index < snapshot->rope_count; ++index) {
		const struct picosystem_physics_rope *const rope =
			&state->world.physics.ropes[index];
		if (rope->particle_count > PICOSYSTEM_PHYSICS_MAX_ROPE_PARTICLES) {
			return -ERANGE;
		}
		rigid->ropes[index].id = rope->id;
		rigid->ropes[index].particle_count = rope->particle_count;
		for (uint8_t particle = 0U; particle < rope->particle_count; ++particle) {
			rigid->ropes[index].particles[particle].x =
				fixed_to_pixel(rope->particles[particle].position.x);
			rigid->ropes[index].particles[particle].y =
				fixed_to_pixel(rope->particles[particle].position.y);
		}
	}
	int err = append_prismatic_guides(state, snapshot);
	if (err != 0) {
		return err;
	}
	for (uint16_t index = 0U; index < snapshot->distance_joint_count; ++index) {
		struct picosystem_physics_vector anchor_a;
		struct picosystem_physics_vector anchor_b;
		err = picosystem_physics_world_distance_joint_endpoints(
			&state->world.physics, index, &anchor_a, &anchor_b);
		if (err != 0) {
			return err;
		}
		const struct picosystem_physics_distance_joint *const joint =
			&state->world.physics.distance_joints[index];
		const bool world_anchored = joint->body_b_id == PICOSYSTEM_PHYSICS_WORLD_BODY_ID;
		uint16_t target_radius =
			world_anchored ? (uint16_t)fixed_to_pixel(joint->target_distance) : 0U;
		if (joint->spring_enabled != 0U) {
			target_radius |= PICOSYSTEM_SCENE_JOINT_SPRING_FLAG;
		}
		int16_t anchor_a_x = fixed_to_pixel(anchor_a.x);
		int16_t anchor_a_y = fixed_to_pixel(anchor_a.y);
		int16_t anchor_b_x = fixed_to_pixel(anchor_b.x);
		int16_t anchor_b_y = fixed_to_pixel(anchor_b.y);
		if (!world_anchored) {
			anchor_a_x = quantize_joint_pixel(anchor_a_x);
			anchor_a_y = quantize_joint_pixel(anchor_a_y);
			anchor_b_x = quantize_joint_pixel(anchor_b_x);
			anchor_b_y = quantize_joint_pixel(anchor_b_y);
		}
		rigid->distance_joints[index] = (struct picosystem_scene_joint){
			.anchor_a_x = anchor_a_x,
			.anchor_a_y = anchor_a_y,
			.anchor_b_x = anchor_b_x,
			.anchor_b_y = anchor_b_y,
			.id = joint->id,
			.target_radius = target_radius,
		};
	}
	for (uint16_t index = 0U; index < snapshot->revolute_joint_count; ++index) {
		struct picosystem_physics_vector anchor_a;
		struct picosystem_physics_vector anchor_b;
		err = picosystem_physics_world_revolute_joint_anchors(&state->world.physics, index,
								      &anchor_a, &anchor_b);
		if (err != 0) {
			return err;
		}
		const struct picosystem_physics_revolute_joint *const joint =
			&state->world.physics.revolute_joints[index];
		rigid->revolute_joints[index] = (struct picosystem_scene_joint){
			.anchor_a_x = fixed_to_pixel(anchor_a.x),
			.anchor_a_y = fixed_to_pixel(anchor_a.y),
			.anchor_b_x = fixed_to_pixel(anchor_b.x),
			.anchor_b_y = fixed_to_pixel(anchor_b.y),
			.id = joint->id,
		};
	}
	return 0;
}

static int publish_snapshot(struct picosystem_game_demo_state *state, bool notify_renderer)
{
	const uint32_t sequence = state->snapshot_sequence + 1U;
	struct picosystem_scene_snapshot snapshot;
	const int err = snapshot_from_state(state, sequence, &snapshot);
	if (err != 0) {
		return err;
	}
	state->snapshot_sequence = sequence;
	const k_spinlock_key_t key = k_spin_lock(&renderer.lock);
	const uint8_t next_index = renderer.published_index ^ 1U;

	renderer.snapshots[next_index] = snapshot;
	renderer.published_index = next_index;
	renderer.snapshot_available = true;
	increment_saturated(&renderer.metrics.published_snapshot_count);
	k_spin_unlock(&renderer.lock, key);

	if (notify_renderer) {
		k_sem_give(&renderer.snapshot_ready);
	}
	return 0;
}

static bool read_latest_snapshot(struct picosystem_scene_snapshot *snapshot)
{
	const k_spinlock_key_t key = k_spin_lock(&renderer.lock);
	const bool available = renderer.snapshot_available;

	if (available) {
		*snapshot = renderer.snapshots[renderer.published_index];
	}
	k_spin_unlock(&renderer.lock, key);
	return available;
}

static uint32_t snapshot_age_us(const struct picosystem_scene_snapshot *snapshot)
{
	const int64_t age_ticks = renderer.live_graphics.last_present_start_uptime_ticks -
				  snapshot->published_uptime_ticks;
	if (age_ticks <= 0) {
		return 0U;
	}

	const uint64_t age_us = k_ticks_to_us_floor64((uint64_t)age_ticks);
	return (uint32_t)MIN(age_us, UINT32_MAX);
}

static int raster_full_scene(const struct picosystem_scene_snapshot *snapshot,
			     struct game_dirty_render_stats *stats)
{
#if defined(CONFIG_TOY_FACTORY_CORE1_RUNTIME)
	if (renderer.core1_available) {
		struct picosystem_core1_scene_result result;
		const int err = picosystem_core1_render_scene(snapshot, &result);
		if (err != 0) {
			return err;
		}
		stats->raster_time_us = result.raster_time_us;
		stats->raster_on_core1 = true;
		return 0;
	}
#endif

	const uint32_t raster_start_cycles = k_cycle_get_32();
	const int err = picosystem_scene_render_full(snapshot);
	stats->raster_time_us = cycles_to_us(k_cycle_get_32() - raster_start_cycles);
	return err;
}

static int present_snapshot(const struct picosystem_scene_snapshot *snapshot, bool full_redraw,
			    const struct picosystem_scene_snapshot *presented,
			    struct game_dirty_render_stats *dirty_stats)
{
	*dirty_stats = (struct game_dirty_render_stats){0};
	if (full_redraw) {
		int err = raster_full_scene(snapshot, dirty_stats);
		if (err == 0) {
			(void)picosystem_display_sync_wait_for_vblank();
			err = picosystem_graphics_present_full(&renderer.live_graphics);
		}
		if (err == 0) {
			dirty_stats->present_time_us = renderer.live_graphics.last_present_time_us;
			dirty_stats->pixel_count =
				PICOSYSTEM_GRAPHICS_WIDTH * PICOSYSTEM_GRAPHICS_HEIGHT;
			dirty_stats->region_count = 1U;
		}
		return err;
	}

	return render_dirty_scene(snapshot, presented, dirty_stats);
}

static void record_renderer_failure(int err)
{
	const k_spinlock_key_t key = k_spin_lock(&renderer.lock);
	renderer.metrics.render_error = err;
	renderer.metrics.render_thread_running = false;
	k_spin_unlock(&renderer.lock, key);
}

static void record_presented_snapshot(const struct picosystem_scene_snapshot *snapshot,
				      bool full_redraw, uint32_t superseded_count,
				      uint32_t render_time_us,
				      const struct game_dirty_render_stats *dirty_stats)
{
	size_t unused_stack_bytes = 0U;
	const int stack_err = k_thread_stack_space_get(k_current_get(), &unused_stack_bytes);
	const uint32_t stack_size = K_THREAD_STACK_SIZEOF(render_thread_stack);
	const uint32_t stack_used = ((stack_err == 0) && (unused_stack_bytes <= stack_size))
					    ? stack_size - (uint32_t)unused_stack_bytes
					    : 0U;
	const uint32_t age_us = snapshot_age_us(snapshot);
	const k_spinlock_key_t key = k_spin_lock(&renderer.lock);

	renderer.metrics.graphics = renderer.live_graphics;
	add_saturated(&renderer.metrics.superseded_snapshot_count, superseded_count);
	renderer.metrics.presented_snapshot_sequence = snapshot->sequence;
	increment_saturated(&renderer.metrics.presented_frame_count);
	if (full_redraw) {
		increment_saturated(&renderer.metrics.full_redraw_count);
	} else {
		renderer.metrics.max_dirty_render_time_us =
			MAX(renderer.metrics.max_dirty_render_time_us, render_time_us);
		renderer.metrics.max_dirty_snapshot_age_us =
			MAX(renderer.metrics.max_dirty_snapshot_age_us, age_us);
	}
	renderer.metrics.last_render_time_us = render_time_us;
	renderer.metrics.last_raster_time_us = dirty_stats->raster_time_us;
	renderer.metrics.maximum_raster_time_us =
		MAX(renderer.metrics.maximum_raster_time_us, dirty_stats->raster_time_us);
	renderer.metrics.last_raster_on_core1 = dirty_stats->raster_on_core1;
	if (dirty_stats->raster_on_core1) {
		increment_saturated(&renderer.metrics.core1_raster_frame_count);
	}
	renderer.metrics.last_dirty_present_time_us = dirty_stats->present_time_us;
	renderer.metrics.last_dirty_pixel_count = dirty_stats->pixel_count;
	renderer.metrics.last_dirty_region_count = dirty_stats->region_count;
	renderer.metrics.last_snapshot_age_us = age_us;
	renderer.metrics.render_stack_used_bytes =
		MAX(renderer.metrics.render_stack_used_bytes, stack_used);
	if (snapshot->body_count != 0U) {
		renderer.metrics.presented_focus_x =
			(uint16_t)snapshot->payload.rigid.bodies[0].center_x;
		renderer.metrics.presented_focus_y =
			(uint16_t)snapshot->payload.rigid.bodies[0].center_y;
	} else if (snapshot->granular_particle_count != 0U) {
		renderer.metrics.presented_focus_x =
			(uint16_t)snapshot->payload.granular.grains[0].x;
		renderer.metrics.presented_focus_y =
			(uint16_t)snapshot->payload.granular.grains[0].y;
	}
	k_spin_unlock(&renderer.lock, key);
	k_sem_give(&renderer.frame_presented);
}

static void render_thread_entry(void *argument1, void *argument2, void *argument3)
{
	ARG_UNUSED(argument1);
	ARG_UNUSED(argument2);
	ARG_UNUSED(argument3);

	uint32_t consumed_sequence;
	uint32_t consumed_redraw_sequence;
	struct picosystem_scene_snapshot presented;
	struct picosystem_scene_snapshot snapshot;
	{
		const k_spinlock_key_t key = k_spin_lock(&renderer.lock);
		presented = renderer.snapshots[renderer.published_index];
		consumed_sequence = presented.sequence;
		consumed_redraw_sequence = presented.redraw_request_sequence;
		renderer.metrics.render_thread_running = true;
		k_spin_unlock(&renderer.lock, key);
	}

	while (true) {
		const int wait_err = k_sem_take(&renderer.snapshot_ready, K_FOREVER);
		if (wait_err != 0) {
			LOG_ERR("Renderer snapshot wait failed (%d)", wait_err);
			record_renderer_failure(wait_err);
			return;
		}

		if (!read_latest_snapshot(&snapshot) || (snapshot.sequence == consumed_sequence)) {
			continue;
		}

		const bool full_redraw_pending =
			core1_full_frame_renderer_enabled() ||
			snapshot_requires_full_redraw(&snapshot) ||
			(snapshot.redraw_request_sequence != consumed_redraw_sequence) ||
			!snapshot_scene_matches(&snapshot, &presented);
#if defined(CONFIG_TOY_FACTORY_CORE1_FULL_FRAME_RENDERER)
		/* A framebuffer capture can hold this mutex while it drains over USB.
		 * Do not wait as the priority -1 coordinator: mutex priority inheritance
		 * would otherwise promote the shell above the authoritative simulation.
		 */
		int err = k_mutex_lock(&renderer.framebuffer_mutex, K_NO_WAIT);
		if (err == -EBUSY) {
			k_sem_give(&renderer.snapshot_ready);
			k_msleep(2);
			continue;
		}
#else
		int err = k_mutex_lock(&renderer.framebuffer_mutex, K_FOREVER);
#endif
		if (err != 0) {
			LOG_ERR("Renderer framebuffer lock failed (%d)", err);
			record_renderer_failure(err);
			return;
		}
		const uint32_t start_cycles = k_cycle_get_32();
		if (!full_redraw_pending) {
			(void)picosystem_display_sync_wait_for_vblank();
		}

		/* Damage rendering latches after TE. Full rendering latches before the
		 * core-1 raster; present_snapshot() waits for TE after those pixels are ready.
		 */
		if (!read_latest_snapshot(&snapshot) || (snapshot.sequence == consumed_sequence)) {
			k_mutex_unlock(&renderer.framebuffer_mutex);
			continue;
		}

		const uint32_t sequence_delta = snapshot.sequence - consumed_sequence;
		const uint32_t superseded_count = sequence_delta - 1U;
		const bool full_redraw =
			core1_full_frame_renderer_enabled() ||
			snapshot_requires_full_redraw(&snapshot) ||
			(snapshot.redraw_request_sequence != consumed_redraw_sequence) ||
			!snapshot_scene_matches(&snapshot, &presented);

		struct game_dirty_render_stats dirty_stats;
		err = present_snapshot(&snapshot, full_redraw, &presented, &dirty_stats);
		if (err != 0) {
			k_mutex_unlock(&renderer.framebuffer_mutex);
			LOG_ERR("Renderer failed to present snapshot %u (%d)", snapshot.sequence,
				err);
			record_renderer_failure(err);
			return;
		}

		const uint32_t render_time_us = cycles_to_us(k_cycle_get_32() - start_cycles);
		consumed_sequence = snapshot.sequence;
		consumed_redraw_sequence = snapshot.redraw_request_sequence;
		presented = snapshot;
		record_presented_snapshot(&snapshot, full_redraw, superseded_count, render_time_us,
					  &dirty_stats);
		k_mutex_unlock(&renderer.framebuffer_mutex);
#if defined(CONFIG_TOY_FACTORY_CORE1_FULL_FRAME_RENDERER)
		/* Leave a bounded handoff window after each continuous full frame. Without
		 * it, this priority -1 coordinator can reacquire the framebuffer before a
		 * waiting shell capture ever runs.
		 */
		k_msleep(1);
#endif

		if (full_redraw && !core1_full_frame_renderer_enabled()) {
			LOG_INF("Asynchronous full redraw: %u us present, %u us renderer wall time",
				renderer.live_graphics.full_present_time_us, render_time_us);
		}
	}
}

int picosystem_game_demo_init(struct picosystem_game_demo_state *state)
{
	if (state == NULL) {
		return -EINVAL;
	}

	memset(state, 0, sizeof(*state));
	int err = picosystem_game_world_reset_scene(&state->world, PICOSYSTEM_GAME_SCENE_HOURGLASS);
	if (err != 0) {
		return err;
	}

	renderer = (struct game_renderer_context){0};
	k_sem_init(&renderer.snapshot_ready, 0U, 1U);
	k_sem_init(&renderer.frame_presented, 0U, 1U);
	k_mutex_init(&renderer.framebuffer_mutex);
#if defined(CONFIG_TOY_FACTORY_CORE1_RUNTIME)
	renderer.core1_available = picosystem_core1_is_ready();
#endif

	err = picosystem_graphics_init(&renderer.live_graphics);
	if (err != 0) {
		return err;
	}

	state->snapshot_sequence = 1U;
	struct picosystem_scene_snapshot initial_snapshot;
	err = snapshot_from_state(state, state->snapshot_sequence, &initial_snapshot);
	if (err != 0) {
		return err;
	}
	struct game_dirty_render_stats initial_render_stats = {0};
	err = raster_full_scene(&initial_snapshot, &initial_render_stats);
	if (err != 0) {
		return err;
	}

	err = picosystem_graphics_present_full(&renderer.live_graphics);
	if (err != 0) {
		return err;
	}

	err = picosystem_graphics_enable_output(&renderer.live_graphics);
	if (err != 0) {
		return err;
	}

	renderer.snapshots[0] = initial_snapshot;
	renderer.published_index = 0U;
	renderer.snapshot_available = true;
	renderer.metrics = (struct game_renderer_metrics){
		.graphics = renderer.live_graphics,
		.published_snapshot_count = 1U,
		.presented_snapshot_sequence = initial_snapshot.sequence,
		.last_raster_time_us = initial_render_stats.raster_time_us,
		.maximum_raster_time_us = initial_render_stats.raster_time_us,
		.render_stack_size_bytes = K_THREAD_STACK_SIZEOF(render_thread_stack),
		.presented_focus_x =
			(initial_snapshot.body_count != 0U)
				? (uint16_t)initial_snapshot.payload.rigid.bodies[0].center_x
				: (uint16_t)initial_snapshot.payload.granular.grains[0].x,
		.presented_focus_y =
			(initial_snapshot.body_count != 0U)
				? (uint16_t)initial_snapshot.payload.rigid.bodies[0].center_y
				: (uint16_t)initial_snapshot.payload.granular.grains[0].y,
		.last_raster_on_core1 = initial_render_stats.raster_on_core1,
	};

	state->ready = true;
	(void)k_thread_create(&render_thread, render_thread_stack,
			      K_THREAD_STACK_SIZEOF(render_thread_stack), render_thread_entry, NULL,
			      NULL, NULL, K_PRIO_PREEMPT(RENDER_THREAD_PRIORITY), 0U, K_NO_WAIT);

	LOG_INF("%u Hz physics ready; renderer=%s, core1=%s, priority=%d",
		PICOSYSTEM_GAME_TICK_RATE_HZ,
		core1_full_frame_renderer_enabled() ? "full-frame" : "damage-region",
		renderer.core1_available ? "available" : "unavailable", RENDER_THREAD_PRIORITY);
	return 0;
}

int picosystem_game_demo_start_simulation(struct picosystem_game_demo_state *state)
{
	if ((state == NULL) || !state->ready) {
		return -EINVAL;
	}
	if ((state->start_uptime_ms != 0) || (state->world.logic_tick_count != 0U)) {
		return -EALREADY;
	}

	return picosystem_game_demo_restart_measurement(state);
}

int picosystem_game_demo_restart_measurement(struct picosystem_game_demo_state *state)
{
	if ((state == NULL) || !state->ready) {
		return -EINVAL;
	}

	uint32_t presented_frame_count;
	{
		const k_spinlock_key_t key = k_spin_lock(&renderer.lock);
		presented_frame_count = renderer.metrics.presented_frame_count;
		k_spin_unlock(&renderer.lock, key);
	}

	state->measurement_start_logic_tick_count = state->world.logic_tick_count;
	state->measurement_start_presented_frame_count = presented_frame_count;
	state->start_uptime_ms = k_uptime_get();
	return 0;
}

int picosystem_game_demo_reset_scene(struct picosystem_game_demo_state *state,
				     enum picosystem_game_scene_id scene_id)
{
	if ((state == NULL) || !state->ready) {
		return -EINVAL;
	}
	if (!picosystem_game_scene_is_selectable(scene_id)) {
		return -ENOTSUP;
	}

	const uint32_t snapshot_sequence = state->snapshot_sequence;
	const uint32_t redraw_request_sequence = state->redraw_request_sequence + 1U;
	const int err = picosystem_game_world_reset_scene(&state->world, scene_id);
	if (err != 0) {
		return err;
	}

	state->skipped_tick_count = 0U;
	state->over_budget_tick_count = 0U;
	state->last_update_time_us = 0U;
	state->max_update_time_us = 0U;
	state->last_physics_time_us = 0U;
	state->max_physics_time_us = 0U;
	state->last_snapshot_time_us = 0U;
	state->max_snapshot_time_us = 0U;
	state->total_physics_time_us = 0U;
	state->total_snapshot_time_us = 0U;
	state->measured_update_count = 0U;
	state->max_backlog_ticks = 0U;
	state->redraw_request_sequence = redraw_request_sequence;
	state->snapshot_sequence = snapshot_sequence;
	state->measurement_start_logic_tick_count = 0U;
	state->measurement_start_presented_frame_count = 0U;
	state->start_uptime_ms = 0;
	state->ready = true;

	int restart_err = picosystem_game_demo_restart_measurement(state);
	if (restart_err != 0) {
		return restart_err;
	}
	return publish_snapshot(state, true);
}

int picosystem_game_demo_reset(struct picosystem_game_demo_state *state)
{
	if ((state == NULL) || !state->ready) {
		return -EINVAL;
	}

	return picosystem_game_demo_reset_scene(
		state, (enum picosystem_game_scene_id)state->world.scene_id);
}

int picosystem_game_demo_apply_scene_action(struct picosystem_game_demo_state *state,
					    enum picosystem_game_scene_action action)
{
	if ((state == NULL) || !state->ready) {
		return -EINVAL;
	}
	const int err = picosystem_game_world_apply_scene_action(&state->world, action);
	if (err != 0) {
		return err;
	}
	return publish_snapshot(state, true);
}

static int update_game(struct picosystem_game_demo_state *state,
		       const struct picosystem_game_input *input, bool publish_every_tick)
{
	if ((state == NULL) || (input == NULL) || !state->ready) {
		return -EINVAL;
	}

	const uint32_t start_cycles = k_cycle_get_32();
	int err = picosystem_game_world_step(&state->world, input);
	if (err != 0) {
		return err;
	}
	const uint32_t physics_end_cycles = k_cycle_get_32();

	const uint32_t snapshot_interval =
		PICOSYSTEM_GAME_TICK_RATE_HZ / PICOSYSTEM_GAME_REALTIME_SNAPSHOT_RATE_HZ;
	if (publish_every_tick || ((state->world.logic_tick_count % snapshot_interval) == 0U)) {
		err = publish_snapshot(state, true);
		if (err != 0) {
			return err;
		}
	}

	const uint32_t end_cycles = k_cycle_get_32();
	const uint32_t physics_us = cycles_to_us(physics_end_cycles - start_cycles);
	const uint32_t snapshot_us = cycles_to_us(end_cycles - physics_end_cycles);
	const uint32_t elapsed_us = cycles_to_us(end_cycles - start_cycles);
	state->last_physics_time_us = physics_us;
	state->max_physics_time_us = MAX(state->max_physics_time_us, physics_us);
	state->last_snapshot_time_us = snapshot_us;
	state->max_snapshot_time_us = MAX(state->max_snapshot_time_us, snapshot_us);
	add_u64_saturated(&state->total_physics_time_us, physics_us);
	add_u64_saturated(&state->total_snapshot_time_us, snapshot_us);
	increment_saturated(&state->measured_update_count);
	state->last_update_time_us = elapsed_us;
	state->max_update_time_us = MAX(state->max_update_time_us, elapsed_us);
	if (elapsed_us > (USEC_PER_SEC / PICOSYSTEM_GAME_TICK_RATE_HZ)) {
		increment_saturated(&state->over_budget_tick_count);
	}

	return 0;
}

int picosystem_game_demo_update(struct picosystem_game_demo_state *state,
				const struct picosystem_game_input *input)
{
	return update_game(state, input, true);
}

int picosystem_game_demo_update_realtime(struct picosystem_game_demo_state *state,
					 const struct picosystem_game_input *input)
{
	return update_game(state, input, false);
}

int picosystem_game_demo_publish_current(struct picosystem_game_demo_state *state)
{
	if ((state == NULL) || !state->ready) {
		return -EINVAL;
	}
	return publish_snapshot(state, true);
}

int picosystem_game_demo_request_redraw(struct picosystem_game_demo_state *state)
{
	if ((state == NULL) || !state->ready) {
		return -EINVAL;
	}

	++state->redraw_request_sequence;
	const int err = publish_snapshot(state, true);
	if (err != 0) {
		--state->redraw_request_sequence;
	}
	return err;
}

void picosystem_game_demo_note_backlog(struct picosystem_game_demo_state *state,
				       uint32_t backlog_ticks)
{
	if (state != NULL) {
		state->max_backlog_ticks = MAX(state->max_backlog_ticks, backlog_ticks);
	}
}

void picosystem_game_demo_note_skipped_ticks(struct picosystem_game_demo_state *state,
					     uint32_t skipped_ticks)
{
	if ((state != NULL) && (skipped_ticks != 0U)) {
		add_saturated(&state->skipped_tick_count, skipped_ticks);
	}
}

int picosystem_game_demo_get_stats(const struct picosystem_game_demo_state *state,
				   struct picosystem_game_demo_stats *stats)
{
	if ((state == NULL) || (stats == NULL) || !state->ready) {
		return -EINVAL;
	}
	const struct picosystem_physics_body *const focus =
		picosystem_game_world_focus_body(&state->world);
	if (focus == NULL) {
		return -EIO;
	}

	const k_spinlock_key_t key = k_spin_lock(&renderer.lock);
	const struct game_renderer_metrics render_metrics = renderer.metrics;
	k_spin_unlock(&renderer.lock, key);
	uint64_t total_update_time_us = state->total_physics_time_us;
	if (state->total_snapshot_time_us > (UINT64_MAX - total_update_time_us)) {
		total_update_time_us = UINT64_MAX;
	} else {
		total_update_time_us += state->total_snapshot_time_us;
	}
	*stats = (struct picosystem_game_demo_stats){
		.graphics = render_metrics.graphics,
		.logic_tick_count = state->world.logic_tick_count,
		.measured_logic_tick_count =
			state->world.logic_tick_count - state->measurement_start_logic_tick_count,
		.skipped_tick_count = state->skipped_tick_count,
		.over_budget_tick_count = state->over_budget_tick_count,
		.last_update_time_us = state->last_update_time_us,
		.mean_update_time_us =
			mean_time_us(total_update_time_us, state->measured_update_count),
		.max_update_time_us = state->max_update_time_us,
		.last_physics_time_us = state->last_physics_time_us,
		.mean_physics_time_us =
			mean_time_us(state->total_physics_time_us, state->measured_update_count),
		.max_physics_time_us = state->max_physics_time_us,
		.last_snapshot_time_us = state->last_snapshot_time_us,
		.mean_snapshot_time_us =
			mean_time_us(state->total_snapshot_time_us, state->measured_update_count),
		.max_snapshot_time_us = state->max_snapshot_time_us,
		.max_backlog_ticks = state->max_backlog_ticks,
		.published_snapshot_count = render_metrics.published_snapshot_count,
		.superseded_snapshot_count = render_metrics.superseded_snapshot_count,
		.presented_snapshot_sequence = render_metrics.presented_snapshot_sequence,
		.presented_frame_count = render_metrics.presented_frame_count,
		.measured_presented_frame_count = render_metrics.presented_frame_count -
						  state->measurement_start_presented_frame_count,
		.full_redraw_count = render_metrics.full_redraw_count,
		.last_render_time_us = render_metrics.last_render_time_us,
		.last_raster_time_us = render_metrics.last_raster_time_us,
		.maximum_raster_time_us = render_metrics.maximum_raster_time_us,
		.core1_raster_frame_count = render_metrics.core1_raster_frame_count,
		.max_dirty_render_time_us = render_metrics.max_dirty_render_time_us,
		.last_dirty_present_time_us = render_metrics.last_dirty_present_time_us,
		.last_dirty_pixel_count = render_metrics.last_dirty_pixel_count,
		.last_dirty_region_count = render_metrics.last_dirty_region_count,
		.last_snapshot_age_us = render_metrics.last_snapshot_age_us,
		.max_dirty_snapshot_age_us = render_metrics.max_dirty_snapshot_age_us,
		.render_stack_size_bytes = render_metrics.render_stack_size_bytes,
		.render_stack_used_bytes = render_metrics.render_stack_used_bytes,
		.sensor_entry_count = state->world.sensor_entry_count,
		.focus_angle_turns = focus->angle_turns,
		.focus_angular_velocity_milliradians_per_second =
			angular_velocity_to_milliradians_per_second(
				focus->angular_velocity_per_tick),
		.focus_body_id = focus->id,
		.focus_x = (uint16_t)fixed_to_pixel(focus->center.x),
		.focus_y = (uint16_t)fixed_to_pixel(focus->center.y),
		.presented_focus_x = render_metrics.presented_focus_x,
		.presented_focus_y = render_metrics.presented_focus_y,
		.focus_velocity_x_pixels_per_second =
			velocity_to_pixels_per_second(focus->velocity_per_tick.x),
		.focus_velocity_y_pixels_per_second =
			velocity_to_pixels_per_second(focus->velocity_per_tick.y),
		.focus_shape = focus->shape,
		.scene_id = state->world.scene_id,
		.start_uptime_ms = state->start_uptime_ms,
		.render_error = render_metrics.render_error,
		.last_raster_on_core1 = render_metrics.last_raster_on_core1,
		.core1_renderer_available = renderer.core1_available,
		.full_frame_renderer_enabled = core1_full_frame_renderer_enabled(),
		.render_thread_running = render_metrics.render_thread_running,
	};
	if (state->world.scene_id == PICOSYSTEM_GAME_SCENE_HOURGLASS) {
		const struct picosystem_granular_world *const granular = &state->world.granular;

		stats->granular_possible_pair_count = granular->last_work.possible_pair_count;
		stats->granular_candidate_pair_count = granular->last_work.candidate_pair_count;
		stats->granular_contact_count = granular->last_work.contact_count;
		stats->granular_position_correction_count =
			granular->last_work.position_correction_count;
		stats->granular_boundary_test_count = granular->last_work.boundary_test_count;
		stats->granular_boundary_contact_count = granular->last_work.boundary_contact_count;
		stats->granular_occupied_grid_cell_count =
			granular->last_work.occupied_grid_cell_count;
		stats->granular_maximum_grid_cell_occupancy =
			granular->last_work.maximum_grid_cell_occupancy;
		stats->granular_passage_count = granular->passage_count;
		stats->granular_particle_count = granular->particle_count;
		stats->granular_lower_particle_count =
			picosystem_granular_world_lower_particle_count(granular);
		stats->granular_boundary_count = granular->boundary_count;
		return 0;
	}

	const struct picosystem_physics_world *const physics = &state->world.physics;
	const struct picosystem_physics_work_counters *const work = &physics->last_work;
	const uint32_t sleeping_body_count =
		(uint32_t)__builtin_popcount((unsigned int)physics->sleeping_body_mask);
	stats->candidate_pair_count = physics->last_candidate_pair_count;
	stats->possible_pair_count = physics->last_possible_pair_count;
	stats->active_contact_pair_count = work->active_contact_pair_count;
	stats->sensor_overlap_count = work->sensor_overlap_count;
	stats->contact_begin_event_count = work->contact_begin_event_count;
	stats->contact_stay_event_count = work->contact_stay_event_count;
	stats->contact_end_event_count = work->contact_end_event_count;
	stats->solver_contact_visit_count = work->solver_contact_visit_count;
	stats->solver_cached_contact_count = work->solver_cached_contact_count;
	stats->solver_changed_contact_count = work->solver_changed_contact_count;
	stats->awake_body_count = (uint32_t)physics->body_count - sleeping_body_count;
	stats->sleeping_body_count = sleeping_body_count;
	stats->body_sleep_transition_count = work->body_sleep_transition_count;
	stats->body_wake_transition_count = work->body_wake_transition_count;
	stats->sleeping_contact_count = work->sleeping_contact_count;
	stats->sleeping_joint_count = work->sleeping_joint_count;
	stats->spring_joint_count = work->spring_joint_count;
	stats->spring_solver_visit_count = work->spring_solver_visit_count;
	stats->spring_solver_changed_count = work->spring_solver_changed_count;
	stats->conveyor_contact_count = work->conveyor_contact_count;
	stats->conveyor_solver_visit_count = work->conveyor_solver_visit_count;
	stats->conveyor_solver_changed_count = work->conveyor_solver_changed_count;
	stats->rope_particle_count = work->rope_particle_count;
	stats->rope_constraint_visit_count = work->rope_constraint_visit_count;
	stats->rope_constraint_changed_count = work->rope_constraint_changed_count;
	stats->rope_body_correction_visit_count = work->rope_body_correction_visit_count;
	stats->rope_body_correction_changed_count = work->rope_body_correction_changed_count;
	stats->rope_body_velocity_visit_count = work->rope_body_velocity_visit_count;
	stats->rope_body_velocity_changed_count = work->rope_body_velocity_changed_count;
	stats->rope_collision_possible_pair_count = work->rope_collision_possible_pair_count;
	stats->rope_collision_candidate_pair_count = work->rope_collision_candidate_pair_count;
	stats->rope_collision_contact_count = work->rope_collision_contact_count;
	stats->rope_collision_position_changed_count = work->rope_collision_position_changed_count;
	stats->rope_collision_velocity_changed_count = work->rope_collision_velocity_changed_count;
	stats->body_count = physics->body_count;
	stats->static_segment_count = physics->static_segment_count;
	stats->distance_joint_count = physics->distance_joint_count;
	stats->revolute_joint_count = physics->revolute_joint_count;
	stats->prismatic_joint_count = physics->prismatic_joint_count;
	stats->box_sensor_count = physics->box_sensor_count;
	stats->rope_count = physics->rope_count;
	stats->contact_count = physics->contact_count;
	stats->contact_event_count = physics->contact_event_count;
	stats->occupied_grid_cell_count = physics->last_occupied_grid_cell_count;
	stats->solver_iteration_count = physics->last_solver_iteration_count;
	stats->focus_sleeping = picosystem_physics_world_body_is_sleeping(
		physics, PICOSYSTEM_GAME_FOCUS_BODY_INDEX);
	stats->broad_phase_fallback = physics->last_broad_phase_fallback != 0U;
	return 0;
}

uint32_t picosystem_game_demo_state_hash(const struct picosystem_game_demo_state *state)
{
	if ((state == NULL) || !state->ready) {
		return 0U;
	}

	return picosystem_game_world_hash(&state->world);
}

static bool sequence_reached(uint32_t current, uint32_t target)
{
	return (current - target) < UINT32_C(0x80000000);
}

static int wait_for_latest_frame(void)
{
	uint32_t target_sequence;
	{
		const k_spinlock_key_t key = k_spin_lock(&renderer.lock);
		if (!renderer.snapshot_available || !renderer.metrics.graphics.ready) {
			k_spin_unlock(&renderer.lock, key);
			return -EAGAIN;
		}
		target_sequence = renderer.snapshots[renderer.published_index].sequence;
		k_spin_unlock(&renderer.lock, key);
	}

	const int64_t deadline_ms = k_uptime_get() + FRAMEBUFFER_CAPTURE_TIMEOUT_MS;
	while (true) {
		uint32_t presented_sequence;
		int render_error;
		{
			const k_spinlock_key_t key = k_spin_lock(&renderer.lock);
			presented_sequence = renderer.metrics.presented_snapshot_sequence;
			render_error = renderer.metrics.render_error;
			k_spin_unlock(&renderer.lock, key);
		}

		if (render_error != 0) {
			return render_error;
		}
		if (sequence_reached(presented_sequence, target_sequence)) {
			return 0;
		}

		const int64_t remaining_ms = deadline_ms - k_uptime_get();
		if (remaining_ms <= 0) {
			return -ETIMEDOUT;
		}

		const int err = k_sem_take(&renderer.frame_presented, K_MSEC(remaining_ms));
		if (err != 0) {
			return err;
		}
	}
}

int picosystem_game_demo_capture_framebuffer(picosystem_graphics_framebuffer_visitor visitor,
					     void *context,
					     struct picosystem_game_framebuffer_capture *capture)
{
	if (capture == NULL) {
		return -EINVAL;
	}

	int err = wait_for_latest_frame();
	if (err != 0) {
		return err;
	}

	err = k_mutex_lock(&renderer.framebuffer_mutex, K_FOREVER);
	if (err != 0) {
		return err;
	}

	uint32_t presented_sequence;
	{
		const k_spinlock_key_t key = k_spin_lock(&renderer.lock);
		presented_sequence = renderer.metrics.presented_snapshot_sequence;
		k_spin_unlock(&renderer.lock, key);
	}

	uint32_t crc32;
	err = picosystem_graphics_framebuffer_crc32(&crc32);
	if ((err == 0) && (visitor != NULL)) {
		err = picosystem_graphics_visit_framebuffer(PICOSYSTEM_GAME_FRAMEBUFFER_CHUNK_BYTES,
							    visitor, context);
	}

	if (err == 0) {
		*capture = (struct picosystem_game_framebuffer_capture){
			.byte_count = PICOSYSTEM_GRAPHICS_FRAMEBUFFER_BYTES,
			.crc32 = crc32,
			.presented_snapshot_sequence = presented_sequence,
			.width = PICOSYSTEM_GRAPHICS_WIDTH,
			.height = PICOSYSTEM_GRAPHICS_HEIGHT,
		};
	}

	k_mutex_unlock(&renderer.framebuffer_mutex);
	return err;
}

#if defined(CONFIG_TOY_FACTORY_CORE1_RUNTIME)
static int accept_rendered_strip(const struct picosystem_rect *region, void *context)
{
	ARG_UNUSED(region);
	ARG_UNUSED(context);
	return 0;
}

int picosystem_game_demo_verify_core1_raster(
	uint32_t frame_index, struct picosystem_game_core1_raster_verification *verification)
{
	if (verification == NULL) {
		return -EINVAL;
	}
	*verification = (struct picosystem_game_core1_raster_verification){
		.frame_index = frame_index,
	};

	int err = wait_for_latest_frame();
	if (err != 0) {
		return err;
	}

	err = k_mutex_lock(&renderer.framebuffer_mutex, K_FOREVER);
	if (err != 0) {
		return err;
	}

	struct picosystem_scene_snapshot restore_snapshot;
	uint32_t presented_sequence;
	{
		const k_spinlock_key_t key = k_spin_lock(&renderer.lock);
		restore_snapshot = renderer.snapshots[renderer.published_index];
		presented_sequence = renderer.metrics.presented_snapshot_sequence;
		k_spin_unlock(&renderer.lock, key);
	}
	if (restore_snapshot.sequence != presented_sequence) {
		err = -EBUSY;
		goto unlock;
	}

	/* Use the same canonical full-scene baseline as the destructive display profiler. */
	err = picosystem_scene_render_full(&restore_snapshot);
	if (err == 0) {
		err = picosystem_graphics_present_full(&renderer.live_graphics);
	}
	if (err == 0) {
		err = picosystem_graphics_framebuffer_crc32(&verification->original_crc32);
	}
	if (err == 0) {
		err = picosystem_dense_scene_draw(frame_index);
	}
	if (err == 0) {
		err = picosystem_graphics_framebuffer_crc32(&verification->core0_crc32);
	}
	if (err == 0) {
		err = picosystem_core1_draw_dense(frame_index, &verification->timing);
	}
	if (err == 0) {
		err = picosystem_graphics_framebuffer_crc32(&verification->core1_crc32);
	}
	verification->pixels_match =
		(err == 0) && (verification->core0_crc32 == verification->core1_crc32);
	const int verify_err = (err != 0) ? err : (verification->pixels_match ? 0 : -EILSEQ);

	int restore_err = picosystem_scene_render_full(&restore_snapshot);
	if (restore_err == 0) {
		restore_err = picosystem_graphics_present_full(&renderer.live_graphics);
	}
	if (restore_err == 0) {
		restore_err = picosystem_graphics_framebuffer_crc32(&verification->restored_crc32);
	}
	verification->framebuffer_restored = (restore_err == 0) && (verification->original_crc32 ==
								    verification->restored_crc32);
	{
		const k_spinlock_key_t key = k_spin_lock(&renderer.lock);
		renderer.metrics.graphics = renderer.live_graphics;
		k_spin_unlock(&renderer.lock, key);
	}

	if (verify_err != 0) {
		err = verify_err;
	} else if (restore_err != 0) {
		err = restore_err;
	} else if (!verification->framebuffer_restored) {
		err = -EILSEQ;
	} else {
		err = 0;
	}

unlock:
	k_mutex_unlock(&renderer.framebuffer_mutex);
	return err;
}

int picosystem_game_demo_verify_core1_scene(
	struct picosystem_game_core1_scene_verification *verification)
{
	if (verification == NULL) {
		return -EINVAL;
	}
	*verification = (struct picosystem_game_core1_scene_verification){0};

	int err = wait_for_latest_frame();
	if (err != 0) {
		return err;
	}
	err = k_mutex_lock(&renderer.framebuffer_mutex, K_FOREVER);
	if (err != 0) {
		return err;
	}

	struct picosystem_scene_snapshot snapshot;
	uint32_t presented_sequence;
	{
		const k_spinlock_key_t key = k_spin_lock(&renderer.lock);
		snapshot = renderer.snapshots[renderer.published_index];
		presented_sequence = renderer.metrics.presented_snapshot_sequence;
		k_spin_unlock(&renderer.lock, key);
	}
	if (snapshot.sequence != presented_sequence) {
		err = -EBUSY;
		goto unlock;
	}

	err = picosystem_scene_render_full(&snapshot);
	if (err == 0) {
		err = picosystem_graphics_framebuffer_crc32(&verification->core0_crc32);
	}
	if (err == 0) {
		err = picosystem_core1_render_scene_stream(&snapshot, accept_rendered_strip, NULL,
							   &verification->timing);
	}
	if (err == 0) {
		err = picosystem_graphics_framebuffer_crc32(&verification->core1_crc32);
	}
	verification->pixels_match =
		(err == 0) && (verification->core0_crc32 == verification->core1_crc32);
	const int verify_err = (err != 0) ? err : (verification->pixels_match ? 0 : -EILSEQ);

	int restore_err = picosystem_scene_render_full(&snapshot);
	if (restore_err == 0) {
		restore_err = picosystem_graphics_present_full(&renderer.live_graphics);
	}
	if (restore_err == 0) {
		restore_err = picosystem_graphics_framebuffer_crc32(&verification->restored_crc32);
	}
	verification->framebuffer_restored =
		(restore_err == 0) && (verification->core0_crc32 == verification->restored_crc32);
	{
		const k_spinlock_key_t key = k_spin_lock(&renderer.lock);
		renderer.metrics.graphics = renderer.live_graphics;
		k_spin_unlock(&renderer.lock, key);
	}

	if (verify_err != 0) {
		err = verify_err;
	} else if (restore_err != 0) {
		err = restore_err;
	} else if (!verification->framebuffer_restored) {
		err = -EILSEQ;
	} else {
		err = 0;
	}

unlock:
	k_mutex_unlock(&renderer.framebuffer_mutex);
	return err;
}
#endif

int picosystem_game_demo_profile_display(uint32_t measured_sample_count,
					 struct picosystem_display_profile_result *result)
{
	if (result == NULL) {
		return -EINVAL;
	}
	*result = (struct picosystem_display_profile_result){0};

	int err = wait_for_latest_frame();
	if (err != 0) {
		return err;
	}

	err = k_mutex_lock(&renderer.framebuffer_mutex, K_FOREVER);
	if (err != 0) {
		return err;
	}

	struct picosystem_scene_snapshot restore_snapshot;
	uint32_t presented_sequence;
	{
		const k_spinlock_key_t key = k_spin_lock(&renderer.lock);
		restore_snapshot = renderer.snapshots[renderer.published_index];
		presented_sequence = renderer.metrics.presented_snapshot_sequence;
		k_spin_unlock(&renderer.lock, key);
	}
	if (restore_snapshot.sequence != presented_sequence) {
		err = -EBUSY;
		goto unlock;
	}

	/* Establish a reproducible full-scene baseline without allocating a second frame. */
	err = picosystem_scene_render_full(&restore_snapshot);
	if (err == 0) {
		err = picosystem_graphics_present_full(&renderer.live_graphics);
	}
	uint32_t original_crc32;
	if (err == 0) {
		err = picosystem_graphics_framebuffer_crc32(&original_crc32);
	}
	if (err != 0) {
		goto unlock;
	}

	err = picosystem_display_profile_run(&renderer.live_graphics, measured_sample_count,
					     result);
	const int profile_err = err;

	int restore_err = picosystem_scene_render_full(&restore_snapshot);
	if (restore_err == 0) {
		restore_err = picosystem_graphics_present_full(&renderer.live_graphics);
	}
	uint32_t restored_crc32 = 0U;
	if (restore_err == 0) {
		restore_err = picosystem_graphics_framebuffer_crc32(&restored_crc32);
	}

	result->original_framebuffer_crc32 = original_crc32;
	result->restored_framebuffer_crc32 = restored_crc32;
	result->framebuffer_restored = (restore_err == 0) && (original_crc32 == restored_crc32);
	{
		const k_spinlock_key_t key = k_spin_lock(&renderer.lock);
		renderer.metrics.graphics = renderer.live_graphics;
		k_spin_unlock(&renderer.lock, key);
	}

	if (profile_err != 0) {
		err = profile_err;
	} else if (restore_err != 0) {
		err = restore_err;
	} else if (!result->framebuffer_restored) {
		err = -EILSEQ;
	} else {
		err = 0;
	}

unlock:
	k_mutex_unlock(&renderer.framebuffer_mutex);
	return err;
}

int picosystem_game_demo_renderer_error(void)
{
	const k_spinlock_key_t key = k_spin_lock(&renderer.lock);
	const int err = renderer.metrics.render_error;
	k_spin_unlock(&renderer.lock, key);
	return err;
}
