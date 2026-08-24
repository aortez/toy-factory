/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "scene_renderer.h"

#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include <zephyr/sys/util.h>

#include "game_world.h"
#include "render_placement.h"

#define PLAYFIELD_LEFT             PICOSYSTEM_GAME_PLAYFIELD_LEFT_PIXELS
#define PLAYFIELD_RIGHT            PICOSYSTEM_GAME_PLAYFIELD_RIGHT_PIXELS
#define PLAYFIELD_TOP              PICOSYSTEM_GAME_PLAYFIELD_TOP_PIXELS
#define PLAYFIELD_BOTTOM           PICOSYSTEM_GAME_PLAYFIELD_BOTTOM_PIXELS
#define PLAYFIELD_WIDTH            (PLAYFIELD_RIGHT - PLAYFIELD_LEFT + 1U)
#define PLAYFIELD_HEIGHT           (PLAYFIELD_BOTTOM - PLAYFIELD_TOP + 1U)
#define BACKGROUND_TILE_SIZE       12U
#define MACHINE_LAB_HEADER_TEXT    "MACHINE LAB 60HZ"
#define CLOCKWORK_HEADER_TEXT      "CLOCKWORK 60HZ"
#define HOURGLASS_HEADER_TEXT      "HOURGLASS 60HZ"
#define MARBLE_MACHINE_HEADER_TEXT "MARBLE MACHINE 60HZ"
#define MACHINE_LAB_HEADER_X       22
#define CLOCKWORK_HEADER_X         34
#define HOURGLASS_HEADER_X         34
#define MARBLE_MACHINE_HEADER_X    44
#define HEADER_TEXT_Y              7
#define HEADER_TEXT_SCALE          2U
#define SENSOR_COUNT_TEXT_X        2
#define SENSOR_COUNT_TEXT_Y        10
#define SENSOR_COUNT_SCALE         1U

static const picosystem_color_t body_colors[] = {
	PICOSYSTEM_COLOR_YELLOW,  PICOSYSTEM_COLOR_CYAN, PICOSYSTEM_COLOR_GREEN,
	PICOSYSTEM_COLOR_MAGENTA, PICOSYSTEM_COLOR_RED,  PICOSYSTEM_COLOR_WHITE,
};

/* One turn is quantized into 64 render phases and interpolated across this 16-way table. */
static const struct {
	int8_t x;
	int8_t y;
} gear_directions[] = {
	{32, 0},  {30, 12},   {23, 23},   {12, 30},   {0, 32},  {-12, 30}, {-23, 23}, {-30, 12},
	{-32, 0}, {-30, -12}, {-23, -23}, {-12, -30}, {0, -32}, {12, -30}, {23, -23}, {30, -12},
};

_Static_assert(PICOSYSTEM_SCENE_MAX_SEGMENTS <= 32U,
	       "conveyor directions must fit the scene segment masks");

static PICOSYSTEM_RENDER_RAMFUNC void
update_progress(struct picosystem_scene_render_progress *progress,
		enum picosystem_scene_render_stage stage, uint32_t item_index,
		enum picosystem_scene_render_primitive primitive)
{
	if (progress == NULL) {
		return;
	}

	progress->item_index = item_index;
	progress->primitive = primitive;
	progress->stage = stage;
}

static PICOSYSTEM_RENDER_RAMFUNC int32_t absolute_i32(int32_t value)
{
	return (value < 0) ? -value : value;
}

static PICOSYSTEM_RENDER_RAMFUNC int
validate_snapshot(const struct picosystem_scene_snapshot *snapshot)
{
	if (snapshot == NULL) {
		return -EINVAL;
	}
	if (snapshot->scene_id >= PICOSYSTEM_GAME_SCENE_COUNT) {
		return -ERANGE;
	}
	if ((snapshot->body_count > PICOSYSTEM_PHYSICS_MAX_BODIES) ||
	    (snapshot->static_segment_count > PICOSYSTEM_SCENE_MAX_SEGMENTS) ||
	    (snapshot->distance_joint_count > PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS) ||
	    (snapshot->revolute_joint_count > PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS) ||
	    (snapshot->box_sensor_count > PICOSYSTEM_SCENE_MAX_BOX_SENSORS) ||
	    (snapshot->rope_count > PICOSYSTEM_PHYSICS_MAX_ROPES) ||
	    (snapshot->granular_particle_count > PICOSYSTEM_GRANULAR_MAX_PARTICLES) ||
	    (snapshot->granular_lower_particle_count > snapshot->granular_particle_count)) {
		return -ERANGE;
	}
	if ((snapshot->scene_id == PICOSYSTEM_GAME_SCENE_HOURGLASS) !=
	    (snapshot->granular_particle_count != 0U)) {
		return -ERANGE;
	}
	if (snapshot->scene_id == PICOSYSTEM_GAME_SCENE_HOURGLASS) {
		if ((snapshot->body_count != 0U) || (snapshot->distance_joint_count != 0U) ||
		    (snapshot->revolute_joint_count != 0U) || (snapshot->box_sensor_count != 0U) ||
		    (snapshot->rope_count != 0U) ||
		    (snapshot->static_segment_count > PICOSYSTEM_GRANULAR_MAX_BOUNDARIES) ||
		    (snapshot->granular_particle_radius == 0U) ||
		    (snapshot->granular_particle_radius > 4U)) {
			return -ERANGE;
		}
		return 0;
	}

	const struct picosystem_scene_rigid_payload *const rigid = &snapshot->payload.rigid;
	const uint32_t valid_segment_mask =
		(snapshot->static_segment_count == 0U)
			? 0U
			: (UINT32_C(1) << snapshot->static_segment_count) - UINT32_C(1);
	const uint32_t conveyor_mask =
		rigid->conveyor_forward_segment_mask | rigid->conveyor_reverse_segment_mask;
	if (((rigid->conveyor_forward_segment_mask & rigid->conveyor_reverse_segment_mask) != 0U) ||
	    ((conveyor_mask & ~valid_segment_mask) != 0U)) {
		return -ERANGE;
	}
	for (uint16_t index = 0U; index < snapshot->body_count; ++index) {
		if ((rigid->bodies[index].shape > PICOSYSTEM_PHYSICS_SHAPE_CAPSULE) ||
		    (rigid->bodies[index].sleeping > 1U)) {
			return -ERANGE;
		}
		if ((rigid->bodies[index].shape == PICOSYSTEM_PHYSICS_SHAPE_CIRCLE) &&
		    ((rigid->bodies[index].geometry.circle.orientation >= 64U) ||
		     (rigid->bodies[index].geometry.circle.render_style >=
		      PICOSYSTEM_GAME_BODY_RENDER_STYLE_COUNT))) {
			return -ERANGE;
		}
	}
	for (uint16_t index = 0U; index < snapshot->box_sensor_count; ++index) {
		const struct picosystem_rect *const bounds = &rigid->box_sensors[index].bounds;
		if ((bounds->width == 0U) || (bounds->height == 0U) ||
		    (bounds->x >= PICOSYSTEM_GRAPHICS_WIDTH) ||
		    (bounds->y >= PICOSYSTEM_GRAPHICS_HEIGHT) ||
		    (bounds->width > (PICOSYSTEM_GRAPHICS_WIDTH - bounds->x)) ||
		    (bounds->height > (PICOSYSTEM_GRAPHICS_HEIGHT - bounds->y)) ||
		    (rigid->box_sensors[index].active > 1U)) {
			return -ERANGE;
		}
	}
	for (uint16_t index = 0U; index < snapshot->rope_count; ++index) {
		if ((rigid->ropes[index].particle_count < 2U) ||
		    (rigid->ropes[index].particle_count > PICOSYSTEM_PHYSICS_MAX_ROPE_PARTICLES)) {
			return -ERANGE;
		}
	}
	return 0;
}

static PICOSYSTEM_RENDER_RAMFUNC void
render_playfield_background(const struct picosystem_scene_snapshot *snapshot,
			    const struct picosystem_rect *region)
{
	picosystem_graphics_fill_rect(region->x, region->y, region->width, region->height,
				      PICOSYSTEM_COLOR_BLACK);

	const uint16_t left = MAX(region->x, PLAYFIELD_LEFT);
	const uint16_t top = MAX(region->y, PLAYFIELD_TOP);
	const uint16_t right = MIN(region->x + region->width, PLAYFIELD_RIGHT + 1U);
	const uint16_t bottom = MIN(region->y + region->height, PLAYFIELD_BOTTOM + 1U);

	if ((left >= right) || (top >= bottom)) {
		return;
	}
	if (snapshot->scene_id == PICOSYSTEM_GAME_SCENE_HOURGLASS) {
		picosystem_graphics_fill_rect(left, top, right - left, bottom - top,
					      PICOSYSTEM_COLOR_NAVY);
		return;
	}

	const uint16_t first_tile_x = left / BACKGROUND_TILE_SIZE;
	const uint16_t final_tile_x = (right - 1U) / BACKGROUND_TILE_SIZE;
	const uint16_t first_tile_y = top / BACKGROUND_TILE_SIZE;
	const uint16_t final_tile_y = (bottom - 1U) / BACKGROUND_TILE_SIZE;
	for (uint16_t tile_y = first_tile_y; tile_y <= final_tile_y; ++tile_y) {
		const uint16_t tile_top = MAX(tile_y * BACKGROUND_TILE_SIZE, top);
		const uint16_t tile_bottom = MIN((tile_y + 1U) * BACKGROUND_TILE_SIZE, bottom);
		for (uint16_t tile_x = first_tile_x; tile_x <= final_tile_x; ++tile_x) {
			const uint16_t tile_left = MAX(tile_x * BACKGROUND_TILE_SIZE, left);
			const uint16_t tile_right =
				MIN((tile_x + 1U) * BACKGROUND_TILE_SIZE, right);
			const picosystem_color_t color = (((tile_x + tile_y) & 1U) == 0U)
								 ? PICOSYSTEM_COLOR_NAVY
								 : PICOSYSTEM_COLOR_DARK_BLUE;
			picosystem_graphics_fill_rect(tile_left, tile_top, tile_right - tile_left,
						      tile_bottom - tile_top, color);
		}
	}
}

PICOSYSTEM_RENDER_RAMFUNC bool
picosystem_scene_rectangles_intersect(const struct picosystem_rect *left,
				      const struct picosystem_rect *right)
{
	return (left->x < (right->x + right->width)) && (right->x < (left->x + left->width)) &&
	       (left->y < (right->y + right->height)) && (right->y < (left->y + left->height));
}

PICOSYSTEM_RENDER_RAMFUNC struct picosystem_rect
picosystem_scene_body_bounds(const struct picosystem_scene_body *body)
{
	if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_CAPSULE) {
		const int32_t start_x =
			((int32_t)body->geometry.vertices[0].x + body->geometry.vertices[3].x) / 2;
		const int32_t start_y =
			((int32_t)body->geometry.vertices[0].y + body->geometry.vertices[3].y) / 2;
		const int32_t end_x =
			((int32_t)body->geometry.vertices[1].x + body->geometry.vertices[2].x) / 2;
		const int32_t end_y =
			((int32_t)body->geometry.vertices[1].y + body->geometry.vertices[2].y) / 2;
		const int32_t left = MAX(MIN(start_x, end_x) - body->radius, 0);
		const int32_t top = MAX(MIN(start_y, end_y) - body->radius, 0);
		const int32_t right =
			MIN(MAX(start_x, end_x) + body->radius + 1, PICOSYSTEM_GRAPHICS_WIDTH);
		const int32_t bottom =
			MIN(MAX(start_y, end_y) + body->radius + 1, PICOSYSTEM_GRAPHICS_HEIGHT);
		return (struct picosystem_rect){
			.x = (uint16_t)left,
			.y = (uint16_t)top,
			.width = (uint16_t)(right - left),
			.height = (uint16_t)(bottom - top),
		};
	}
	if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_BOX) {
		int16_t left = body->geometry.vertices[0].x;
		int16_t top = body->geometry.vertices[0].y;
		int16_t right = left;
		int16_t bottom = top;
		for (size_t index = 1U; index < PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT; ++index) {
			left = MIN(left, body->geometry.vertices[index].x);
			top = MIN(top, body->geometry.vertices[index].y);
			right = MAX(right, body->geometry.vertices[index].x);
			bottom = MAX(bottom, body->geometry.vertices[index].y);
		}

		const int32_t clipped_left = MAX((int32_t)left, 0);
		const int32_t clipped_top = MAX((int32_t)top, 0);
		const int32_t clipped_right = MIN((int32_t)right + 1, PICOSYSTEM_GRAPHICS_WIDTH);
		const int32_t clipped_bottom = MIN((int32_t)bottom + 1, PICOSYSTEM_GRAPHICS_HEIGHT);
		return (struct picosystem_rect){
			.x = (uint16_t)clipped_left,
			.y = (uint16_t)clipped_top,
			.width = (uint16_t)(clipped_right - clipped_left),
			.height = (uint16_t)(clipped_bottom - clipped_top),
		};
	}

	const uint16_t margin =
		(body->geometry.circle.render_style == PICOSYSTEM_GAME_BODY_RENDER_STYLE_GEAR) ? 2U
											       : 0U;
	const int32_t left = MAX((int32_t)body->center_x - body->radius - margin, 0);
	const int32_t top = MAX((int32_t)body->center_y - body->radius - margin, 0);
	const int32_t right =
		MIN((int32_t)body->center_x + body->radius + margin + 1, PICOSYSTEM_GRAPHICS_WIDTH);
	const int32_t bottom = MIN((int32_t)body->center_y + body->radius + margin + 1,
				   PICOSYSTEM_GRAPHICS_HEIGHT);

	return (struct picosystem_rect){
		.x = (uint16_t)left,
		.y = (uint16_t)top,
		.width = (uint16_t)(right - left),
		.height = (uint16_t)(bottom - top),
	};
}

static PICOSYSTEM_RENDER_RAMFUNC struct picosystem_rect
line_bounds_with_margin(int16_t start_x, int16_t start_y, int16_t end_x, int16_t end_y,
			uint16_t margin)
{
	const int32_t left = MAX((int32_t)MIN(start_x, end_x) - margin, 0);
	const int32_t top = MAX((int32_t)MIN(start_y, end_y) - margin, 0);
	const int32_t right =
		MIN((int32_t)MAX(start_x, end_x) + margin, PICOSYSTEM_GRAPHICS_WIDTH - 1);
	const int32_t bottom =
		MIN((int32_t)MAX(start_y, end_y) + margin, PICOSYSTEM_GRAPHICS_HEIGHT - 1);
	if ((right < left) || (bottom < top)) {
		return (struct picosystem_rect){0};
	}

	return (struct picosystem_rect){
		.x = (uint16_t)left,
		.y = (uint16_t)top,
		.width = (uint16_t)(right - left + 1),
		.height = (uint16_t)(bottom - top + 1),
	};
}

static PICOSYSTEM_RENDER_RAMFUNC struct picosystem_rect
line_bounds(int16_t start_x, int16_t start_y, int16_t end_x, int16_t end_y)
{
	return line_bounds_with_margin(start_x, start_y, end_x, end_y, 0U);
}

PICOSYSTEM_RENDER_RAMFUNC struct picosystem_rect
picosystem_scene_rope_bounds(const struct picosystem_scene_rope *rope)
{
	if ((rope == NULL) || (rope->particle_count == 0U) ||
	    (rope->particle_count > PICOSYSTEM_PHYSICS_MAX_ROPE_PARTICLES)) {
		return (struct picosystem_rect){0};
	}
	int16_t left = rope->particles[0].x;
	int16_t top = rope->particles[0].y;
	int16_t right = left;
	int16_t bottom = top;
	for (uint8_t index = 1U; index < rope->particle_count; ++index) {
		left = MIN(left, rope->particles[index].x);
		top = MIN(top, rope->particles[index].y);
		right = MAX(right, rope->particles[index].x);
		bottom = MAX(bottom, rope->particles[index].y);
	}
	return line_bounds_with_margin(left, top, right, bottom, 1U);
}

static PICOSYSTEM_RENDER_RAMFUNC bool
scene_joint_is_spring(const struct picosystem_scene_joint *joint)
{
	return (joint->target_radius & PICOSYSTEM_SCENE_JOINT_SPRING_FLAG) != 0U;
}

PICOSYSTEM_RENDER_RAMFUNC struct picosystem_rect
picosystem_scene_segment_bounds(const struct picosystem_scene_segment *segment)
{
	return line_bounds(segment->start_x, segment->start_y, segment->end_x, segment->end_y);
}

PICOSYSTEM_RENDER_RAMFUNC struct picosystem_rect
picosystem_scene_joint_bounds(const struct picosystem_scene_joint *joint)
{
	if (scene_joint_is_spring(joint)) {
		return line_bounds_with_margin(joint->anchor_a_x, joint->anchor_a_y,
					       joint->anchor_b_x, joint->anchor_b_y, 3U);
	}
	const uint16_t target_radius =
		joint->target_radius & PICOSYSTEM_SCENE_JOINT_TARGET_RADIUS_MASK;
	if (target_radius != 0U) {
		const struct picosystem_scene_body guide = {
			.center_x = joint->anchor_b_x,
			.center_y = joint->anchor_b_y,
			.radius = target_radius,
			.shape = PICOSYSTEM_PHYSICS_SHAPE_CIRCLE,
		};
		return picosystem_scene_body_bounds(&guide);
	}
	return line_bounds(joint->anchor_a_x, joint->anchor_a_y, joint->anchor_b_x,
			   joint->anchor_b_y);
}

PICOSYSTEM_RENDER_RAMFUNC struct picosystem_rect
picosystem_scene_revolute_joint_bounds(const struct picosystem_scene_joint *joint)
{
	const int32_t center_x = ((int32_t)joint->anchor_a_x + joint->anchor_b_x) / 2;
	const int32_t center_y = ((int32_t)joint->anchor_a_y + joint->anchor_b_y) / 2;
	const int32_t left = MAX(MIN(MIN((int32_t)joint->anchor_a_x, joint->anchor_b_x),
				     center_x - PICOSYSTEM_SCENE_REVOLUTE_JOINT_RADIUS),
				 0);
	const int32_t top = MAX(MIN(MIN((int32_t)joint->anchor_a_y, joint->anchor_b_y),
				    center_y - PICOSYSTEM_SCENE_REVOLUTE_JOINT_RADIUS),
				0);
	const int32_t right = MIN(MAX(MAX((int32_t)joint->anchor_a_x, joint->anchor_b_x),
				      center_x + PICOSYSTEM_SCENE_REVOLUTE_JOINT_RADIUS) +
					  1,
				  PICOSYSTEM_GRAPHICS_WIDTH);
	const int32_t bottom = MIN(MAX(MAX((int32_t)joint->anchor_a_y, joint->anchor_b_y),
				       center_y + PICOSYSTEM_SCENE_REVOLUTE_JOINT_RADIUS) +
					   1,
				   PICOSYSTEM_GRAPHICS_HEIGHT);
	if ((right <= left) || (bottom <= top)) {
		return (struct picosystem_rect){0};
	}

	return (struct picosystem_rect){
		.x = (uint16_t)left,
		.y = (uint16_t)top,
		.width = (uint16_t)(right - left),
		.height = (uint16_t)(bottom - top),
	};
}

struct picosystem_rect
picosystem_scene_joint_segment_bounds(const struct picosystem_scene_joint *joint,
				      uint8_t segment_index)
{
	const int32_t delta_x = (int32_t)joint->anchor_b_x - joint->anchor_a_x;
	const int32_t delta_y = (int32_t)joint->anchor_b_y - joint->anchor_a_y;
	const int32_t start_x =
		joint->anchor_a_x +
		((delta_x * segment_index) / (int32_t)PICOSYSTEM_SCENE_JOINT_DAMAGE_SEGMENT_COUNT);
	const int32_t start_y =
		joint->anchor_a_y +
		((delta_y * segment_index) / (int32_t)PICOSYSTEM_SCENE_JOINT_DAMAGE_SEGMENT_COUNT);
	const uint8_t next_index = segment_index + 1U;
	const int32_t end_x =
		joint->anchor_a_x +
		((delta_x * next_index) / (int32_t)PICOSYSTEM_SCENE_JOINT_DAMAGE_SEGMENT_COUNT);
	const int32_t end_y =
		joint->anchor_a_y +
		((delta_y * next_index) / (int32_t)PICOSYSTEM_SCENE_JOINT_DAMAGE_SEGMENT_COUNT);

	return line_bounds_with_margin((int16_t)start_x, (int16_t)start_y, (int16_t)end_x,
				       (int16_t)end_y, scene_joint_is_spring(joint) ? 3U : 0U);
}

static PICOSYSTEM_RENDER_RAMFUNC void gear_direction(uint8_t phase, int32_t *x, int32_t *y)
{
	const uint8_t index = phase >> 2U;
	const uint8_t next = (index + 1U) & UINT8_C(0x0f);
	const int32_t fraction = phase & UINT8_C(0x03);
	*x = gear_directions[index].x +
	     (((gear_directions[next].x - gear_directions[index].x) * fraction) / 4);
	*y = gear_directions[index].y +
	     (((gear_directions[next].y - gear_directions[index].y) * fraction) / 4);
}

static PICOSYSTEM_RENDER_RAMFUNC int
render_gear_details(const struct picosystem_scene_body *body, const struct picosystem_rect *clip,
		    picosystem_color_t color, picosystem_color_t detail_color, uint32_t body_index,
		    struct picosystem_scene_render_progress *progress)
{
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BODIES, body_index,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_OUTLINE);
	for (uint8_t tooth = 0U; tooth < 8U; ++tooth) {
		const uint8_t phase =
			(body->geometry.circle.orientation + (tooth * 8U)) & UINT8_C(0x3f);
		int32_t direction_x;
		int32_t direction_y;
		gear_direction(phase, &direction_x, &direction_y);
		const int16_t inner_x =
			body->center_x + (int16_t)((direction_x * (body->radius - 1U)) / 32);
		const int16_t inner_y =
			body->center_y + (int16_t)((direction_y * (body->radius - 1U)) / 32);
		const int16_t outer_x =
			body->center_x + (int16_t)((direction_x * (body->radius + 2U)) / 32);
		const int16_t outer_y =
			body->center_y + (int16_t)((direction_y * (body->radius + 2U)) / 32);
		picosystem_graphics_draw_line_clipped(clip, inner_x, inner_y, outer_x, outer_y,
						      color);
	}

	int32_t direction_x;
	int32_t direction_y;
	gear_direction(body->geometry.circle.orientation, &direction_x, &direction_y);
	const int16_t spoke_x =
		body->center_x + (int16_t)((direction_x * (body->radius - 3U)) / 32);
	const int16_t spoke_y =
		body->center_y + (int16_t)((direction_y * (body->radius - 3U)) / 32);
	picosystem_graphics_draw_line_clipped(clip, body->center_x, body->center_y, spoke_x,
					      spoke_y, detail_color);
	return picosystem_graphics_fill_circle_clipped(clip, body->center_x, body->center_y, 2U,
						       detail_color);
}

static PICOSYSTEM_RENDER_RAMFUNC int render_body(const struct picosystem_scene_body *body,
						 uint32_t body_index,
						 const struct picosystem_rect *clip,
						 struct picosystem_scene_render_progress *progress)
{
	const picosystem_color_t color =
		(body->sleeping != 0U) ? PICOSYSTEM_COLOR_BLUE
				       : body_colors[(body->id - 1U) % ARRAY_SIZE(body_colors)];
	const picosystem_color_t detail_color =
		(body->sleeping != 0U) ? PICOSYSTEM_COLOR_WHITE : PICOSYSTEM_COLOR_BLACK;
	if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_BOX) {
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BODIES, body_index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_FILL_0);
		picosystem_graphics_fill_triangle_clipped(
			clip, body->geometry.vertices[0].x, body->geometry.vertices[0].y,
			body->geometry.vertices[1].x, body->geometry.vertices[1].y,
			body->geometry.vertices[2].x, body->geometry.vertices[2].y, color);
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BODIES, body_index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_FILL_1);
		picosystem_graphics_fill_triangle_clipped(
			clip, body->geometry.vertices[0].x, body->geometry.vertices[0].y,
			body->geometry.vertices[2].x, body->geometry.vertices[2].y,
			body->geometry.vertices[3].x, body->geometry.vertices[3].y, color);
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BODIES, body_index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_OUTLINE);
		for (size_t index = 0U; index < PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT; ++index) {
			const size_t next = (index + 1U) % PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT;
			picosystem_graphics_draw_line_clipped(
				clip, body->geometry.vertices[index].x,
				body->geometry.vertices[index].y, body->geometry.vertices[next].x,
				body->geometry.vertices[next].y, detail_color);
		}
		const int16_t face_x =
			(body->geometry.vertices[1].x + body->geometry.vertices[2].x) / 2;
		const int16_t face_y =
			(body->geometry.vertices[1].y + body->geometry.vertices[2].y) / 2;
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BODIES, body_index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_FACE);
		picosystem_graphics_draw_line_clipped(clip, body->center_x, body->center_y, face_x,
						      face_y, detail_color);
		return 0;
	}
	if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_CAPSULE) {
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BODIES, body_index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_FILL_0);
		picosystem_graphics_fill_triangle_clipped(
			clip, body->geometry.vertices[0].x, body->geometry.vertices[0].y,
			body->geometry.vertices[1].x, body->geometry.vertices[1].y,
			body->geometry.vertices[2].x, body->geometry.vertices[2].y, color);
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BODIES, body_index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_FILL_1);
		picosystem_graphics_fill_triangle_clipped(
			clip, body->geometry.vertices[0].x, body->geometry.vertices[0].y,
			body->geometry.vertices[2].x, body->geometry.vertices[2].y,
			body->geometry.vertices[3].x, body->geometry.vertices[3].y, color);
		const int16_t start_x =
			(body->geometry.vertices[0].x + body->geometry.vertices[3].x) / 2;
		const int16_t start_y =
			(body->geometry.vertices[0].y + body->geometry.vertices[3].y) / 2;
		const int16_t end_x =
			(body->geometry.vertices[1].x + body->geometry.vertices[2].x) / 2;
		const int16_t end_y =
			(body->geometry.vertices[1].y + body->geometry.vertices[2].y) / 2;
		int err = picosystem_graphics_fill_circle_clipped(clip, start_x, start_y,
								  body->radius, color);
		if (err == 0) {
			err = picosystem_graphics_fill_circle_clipped(clip, end_x, end_y,
								      body->radius, color);
		}
		if (err != 0) {
			return err;
		}
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BODIES, body_index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_OUTLINE);
		picosystem_graphics_draw_line_clipped(
			clip, body->geometry.vertices[0].x, body->geometry.vertices[0].y,
			body->geometry.vertices[1].x, body->geometry.vertices[1].y, detail_color);
		picosystem_graphics_draw_line_clipped(
			clip, body->geometry.vertices[3].x, body->geometry.vertices[3].y,
			body->geometry.vertices[2].x, body->geometry.vertices[2].y, detail_color);
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BODIES, body_index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_FACE);
		picosystem_graphics_draw_line_clipped(clip, body->center_x, body->center_y, end_x,
						      end_y, detail_color);
		return 0;
	}

	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BODIES, body_index,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_FILL_0);
	int err = picosystem_graphics_fill_circle_clipped(clip, body->center_x, body->center_y,
							  body->radius, color);
	if ((err != 0) || (body->radius < 4U)) {
		return err;
	}
	if (body->geometry.circle.render_style == PICOSYSTEM_GAME_BODY_RENDER_STYLE_GEAR) {
		return render_gear_details(body, clip, color, detail_color, body_index, progress);
	}

	const uint16_t highlight_radius = MAX(body->radius / 4U, 1U);
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BODIES, body_index,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_HIGHLIGHT);
	err = picosystem_graphics_fill_circle_clipped(clip,
						      body->center_x - (int16_t)(body->radius / 3U),
						      body->center_y - (int16_t)(body->radius / 3U),
						      highlight_radius, PICOSYSTEM_COLOR_WHITE);
	return err;
}

static PICOSYSTEM_RENDER_RAMFUNC void
render_conveyor_chevrons(const struct picosystem_scene_segment *segment, int32_t direction,
			 const struct picosystem_rect *clip)
{
	const int32_t delta_x = (int32_t)segment->end_x - segment->start_x;
	const int32_t delta_y = (int32_t)segment->end_y - segment->start_y;
	const int32_t maximum_axis = MAX(absolute_i32(delta_x), absolute_i32(delta_y));
	if (maximum_axis == 0) {
		return;
	}

	const int32_t forward_x = (direction * delta_x * 3) / maximum_axis;
	const int32_t forward_y = (direction * delta_y * 3) / maximum_axis;
	const int32_t side_x = (-delta_y * 2) / maximum_axis;
	const int32_t side_y = (delta_x * 2) / maximum_axis;
	for (int32_t marker = 1; marker <= 3; ++marker) {
		const int32_t center_x = segment->start_x + ((delta_x * marker) / 4);
		const int32_t center_y = segment->start_y + ((delta_y * marker) / 4);
		const int16_t tip_x = (int16_t)(center_x + forward_x);
		const int16_t tip_y = (int16_t)(center_y + forward_y);
		const int32_t base_x = center_x - (forward_x / 2);
		const int32_t base_y = center_y - (forward_y / 2);
		picosystem_graphics_draw_line_clipped(
			clip, tip_x, tip_y, (int16_t)(base_x + side_x), (int16_t)(base_y + side_y),
			PICOSYSTEM_COLOR_YELLOW);
		picosystem_graphics_draw_line_clipped(
			clip, tip_x, tip_y, (int16_t)(base_x - side_x), (int16_t)(base_y - side_y),
			PICOSYSTEM_COLOR_YELLOW);
	}
}

static PICOSYSTEM_RENDER_RAMFUNC int32_t
conveyor_direction(const struct picosystem_scene_snapshot *snapshot, uint16_t segment_index)
{
	const uint32_t mask = UINT32_C(1) << segment_index;
	if ((snapshot->payload.rigid.conveyor_forward_segment_mask & mask) != 0U) {
		return 1;
	}
	return ((snapshot->payload.rigid.conveyor_reverse_segment_mask & mask) != 0U) ? -1 : 0;
}

static PICOSYSTEM_RENDER_RAMFUNC void
render_static_segments(const struct picosystem_scene_snapshot *snapshot,
		       const struct picosystem_rect *clip,
		       struct picosystem_scene_render_progress *progress)
{
	for (uint16_t index = 0U; index < snapshot->static_segment_count; ++index) {
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_STATIC_SEGMENTS, index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_BOUNDS);
		const bool hourglass = snapshot->scene_id == PICOSYSTEM_GAME_SCENE_HOURGLASS;
		const struct picosystem_scene_segment *const segment =
			hourglass ? &snapshot->payload.granular.boundaries[index]
				  : &snapshot->payload.rigid.static_segments[index];
		const int32_t direction = hourglass ? 0 : conveyor_direction(snapshot, index);
		if (clip != NULL) {
			const struct picosystem_rect bounds =
				(direction == 0)
					? picosystem_scene_segment_bounds(segment)
					: line_bounds_with_margin(segment->start_x,
								  segment->start_y, segment->end_x,
								  segment->end_y, 4U);
			if (!picosystem_scene_rectangles_intersect(&bounds, clip)) {
				continue;
			}
		}
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_STATIC_SEGMENTS, index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_OUTLINE);
		const picosystem_color_t segment_color =
			hourglass ? PICOSYSTEM_COLOR_WHITE
				  : ((direction == 0) ? PICOSYSTEM_COLOR_CYAN
						      : PICOSYSTEM_COLOR_GREEN);
		picosystem_graphics_draw_line_clipped(clip, segment->start_x, segment->start_y,
						      segment->end_x, segment->end_y,
						      segment_color);
		if (direction != 0) {
			render_conveyor_chevrons(segment, direction, clip);
		}
	}
}

static PICOSYSTEM_RENDER_RAMFUNC int
render_granules(const struct picosystem_scene_snapshot *snapshot,
		const struct picosystem_rect *clip,
		struct picosystem_scene_render_progress *progress)
{
	for (uint16_t index = 0U; index < snapshot->granular_particle_count; ++index) {
		const struct picosystem_scene_grain *const grain =
			&snapshot->payload.granular.grains[index];
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_GRANULES, index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_FILL_0);
		const picosystem_color_t color =
			((index % 7U) == 0U) ? PICOSYSTEM_COLOR_WHITE : PICOSYSTEM_COLOR_YELLOW;
		const int err = picosystem_graphics_fill_circle_clipped(
			clip, grain->x, grain->y, snapshot->granular_particle_radius, color);
		if (err != 0) {
			return err;
		}
	}
	return 0;
}

static PICOSYSTEM_RENDER_RAMFUNC void
render_box_sensors(const struct picosystem_scene_snapshot *snapshot,
		   const struct picosystem_rect *clip,
		   struct picosystem_scene_render_progress *progress)
{
	for (uint16_t index = 0U; index < snapshot->box_sensor_count; ++index) {
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BOX_SENSORS, index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_BOUNDS);
		const struct picosystem_scene_box_sensor *const sensor =
			&snapshot->payload.rigid.box_sensors[index];
		if ((clip != NULL) &&
		    !picosystem_scene_rectangles_intersect(&sensor->bounds, clip)) {
			continue;
		}

		const int16_t left = (int16_t)sensor->bounds.x;
		const int16_t top = (int16_t)sensor->bounds.y;
		const int16_t right = (int16_t)(sensor->bounds.x + sensor->bounds.width - 1U);
		const int16_t bottom = (int16_t)(sensor->bounds.y + sensor->bounds.height - 1U);
		const picosystem_color_t color =
			(sensor->active != 0U) ? PICOSYSTEM_COLOR_GREEN : PICOSYSTEM_COLOR_MAGENTA;
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BOX_SENSORS, index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_OUTLINE);
		picosystem_graphics_draw_line_clipped(clip, left, top, right, top, color);
		picosystem_graphics_draw_line_clipped(clip, right, top, right, bottom, color);
		picosystem_graphics_draw_line_clipped(clip, right, bottom, left, bottom, color);
		picosystem_graphics_draw_line_clipped(clip, left, bottom, left, top, color);
	}
}

static PICOSYSTEM_RENDER_RAMFUNC int render_header(const struct picosystem_scene_snapshot *snapshot,
						   const struct picosystem_rect *clip)
{
	const char *header_text = MACHINE_LAB_HEADER_TEXT;
	int16_t header_x = MACHINE_LAB_HEADER_X;
	char counter_prefix = 'S';
	switch (snapshot->scene_id) {
	case PICOSYSTEM_GAME_SCENE_CLOCKWORK:
		header_text = CLOCKWORK_HEADER_TEXT;
		header_x = CLOCKWORK_HEADER_X;
		break;
	case PICOSYSTEM_GAME_SCENE_HOURGLASS:
		header_text = HOURGLASS_HEADER_TEXT;
		header_x = HOURGLASS_HEADER_X;
		counter_prefix = 'D';
		break;
	case PICOSYSTEM_GAME_SCENE_MARBLE_MACHINE:
		header_text = MARBLE_MACHINE_HEADER_TEXT;
		header_x = MARBLE_MACHINE_HEADER_X;
		counter_prefix = 'M';
		break;
	default:
		break;
	}
	int err;
	if (clip == NULL) {
		err = picosystem_graphics_draw_text(header_x, HEADER_TEXT_Y, header_text,
						    HEADER_TEXT_SCALE, PICOSYSTEM_COLOR_WHITE);
	} else {
		err = picosystem_graphics_draw_text_clipped(clip, header_x, HEADER_TEXT_Y,
							    header_text, HEADER_TEXT_SCALE,
							    PICOSYSTEM_COLOR_WHITE);
	}
	if (err != 0) {
		return err;
	}

	const bool hourglass = snapshot->scene_id == PICOSYSTEM_GAME_SCENE_HOURGLASS;
	const uint32_t displayed_count = (hourglass ? snapshot->granular_lower_particle_count
						    : snapshot->sensor_entry_count) %
					 100U;
	const char count_text[] = {
		counter_prefix,
		(char)('0' + (displayed_count / 10U)),
		(char)('0' + (displayed_count % 10U)),
		'\0',
	};
	if (clip == NULL) {
		return picosystem_graphics_draw_text(
			SENSOR_COUNT_TEXT_X, SENSOR_COUNT_TEXT_Y, count_text, SENSOR_COUNT_SCALE,
			hourglass ? PICOSYSTEM_COLOR_YELLOW : PICOSYSTEM_COLOR_GREEN);
	}
	return picosystem_graphics_draw_text_clipped(
		clip, SENSOR_COUNT_TEXT_X, SENSOR_COUNT_TEXT_Y, count_text, SENSOR_COUNT_SCALE,
		hourglass ? PICOSYSTEM_COLOR_YELLOW : PICOSYSTEM_COLOR_GREEN);
}

static PICOSYSTEM_RENDER_RAMFUNC void
render_world_joint_guide(const struct picosystem_scene_joint *joint,
			 const struct picosystem_rect *clip)
{
	int32_t x = joint->target_radius & PICOSYSTEM_SCENE_JOINT_TARGET_RADIUS_MASK;
	int32_t y = 0;
	int32_t decision = 1 - x;

	while (y <= x) {
		picosystem_graphics_draw_pixel_clipped(clip, joint->anchor_b_x + (int16_t)x,
						       joint->anchor_b_y + (int16_t)y,
						       PICOSYSTEM_COLOR_YELLOW);
		picosystem_graphics_draw_pixel_clipped(clip, joint->anchor_b_x + (int16_t)y,
						       joint->anchor_b_y + (int16_t)x,
						       PICOSYSTEM_COLOR_YELLOW);
		picosystem_graphics_draw_pixel_clipped(clip, joint->anchor_b_x - (int16_t)y,
						       joint->anchor_b_y + (int16_t)x,
						       PICOSYSTEM_COLOR_YELLOW);
		picosystem_graphics_draw_pixel_clipped(clip, joint->anchor_b_x - (int16_t)x,
						       joint->anchor_b_y + (int16_t)y,
						       PICOSYSTEM_COLOR_YELLOW);
		picosystem_graphics_draw_pixel_clipped(clip, joint->anchor_b_x - (int16_t)x,
						       joint->anchor_b_y - (int16_t)y,
						       PICOSYSTEM_COLOR_YELLOW);
		picosystem_graphics_draw_pixel_clipped(clip, joint->anchor_b_x - (int16_t)y,
						       joint->anchor_b_y - (int16_t)x,
						       PICOSYSTEM_COLOR_YELLOW);
		picosystem_graphics_draw_pixel_clipped(clip, joint->anchor_b_x + (int16_t)y,
						       joint->anchor_b_y - (int16_t)x,
						       PICOSYSTEM_COLOR_YELLOW);
		picosystem_graphics_draw_pixel_clipped(clip, joint->anchor_b_x + (int16_t)x,
						       joint->anchor_b_y - (int16_t)y,
						       PICOSYSTEM_COLOR_YELLOW);

		++y;
		if (decision <= 0) {
			decision += (2 * y) + 1;
		} else {
			--x;
			decision += (2 * (y - x)) + 1;
		}
	}
	picosystem_graphics_draw_pixel_clipped(clip, joint->anchor_b_x, joint->anchor_b_y,
					       PICOSYSTEM_COLOR_WHITE);
}

static PICOSYSTEM_RENDER_RAMFUNC void render_spring(const struct picosystem_scene_joint *joint,
						    const struct picosystem_rect *clip)
{
	const int32_t delta_x = (int32_t)joint->anchor_b_x - joint->anchor_a_x;
	const int32_t delta_y = (int32_t)joint->anchor_b_y - joint->anchor_a_y;
	const int32_t maximum_axis = MAX(absolute_i32(delta_x), absolute_i32(delta_y));
	if (maximum_axis == 0) {
		picosystem_graphics_draw_pixel_clipped(clip, joint->anchor_a_x, joint->anchor_a_y,
						       PICOSYSTEM_COLOR_YELLOW);
		return;
	}

	const int32_t perpendicular_x = (-delta_y * 3) / maximum_axis;
	const int32_t perpendicular_y = (delta_x * 3) / maximum_axis;
	int16_t previous_x = joint->anchor_a_x;
	int16_t previous_y = joint->anchor_a_y;
	for (int32_t coil = 1; coil <= 8; ++coil) {
		const int32_t offset = (coil == 8) ? 0 : ((coil & 1) != 0 ? 1 : -1);
		const int16_t current_x = (int16_t)(joint->anchor_a_x + ((delta_x * coil) / 8) +
						    (perpendicular_x * offset));
		const int16_t current_y = (int16_t)(joint->anchor_a_y + ((delta_y * coil) / 8) +
						    (perpendicular_y * offset));
		picosystem_graphics_draw_line_clipped(clip, previous_x, previous_y, current_x,
						      current_y, PICOSYSTEM_COLOR_YELLOW);
		previous_x = current_x;
		previous_y = current_y;
	}
}

static PICOSYSTEM_RENDER_RAMFUNC void
render_distance_joints(const struct picosystem_scene_snapshot *snapshot,
		       const struct picosystem_rect *clip,
		       struct picosystem_scene_render_progress *progress)
{
	for (uint16_t index = 0U; index < snapshot->distance_joint_count; ++index) {
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_DISTANCE_JOINTS, index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_BOUNDS);
		const struct picosystem_scene_joint *const joint =
			&snapshot->payload.rigid.distance_joints[index];
		if (clip != NULL) {
			const struct picosystem_rect bounds = picosystem_scene_joint_bounds(joint);
			if (!picosystem_scene_rectangles_intersect(&bounds, clip)) {
				continue;
			}
		}
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_DISTANCE_JOINTS, index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_OUTLINE);
		if (scene_joint_is_spring(joint)) {
			render_spring(joint, clip);
		} else if ((joint->target_radius & PICOSYSTEM_SCENE_JOINT_TARGET_RADIUS_MASK) !=
			   0U) {
			render_world_joint_guide(joint, clip);
		} else {
			picosystem_graphics_draw_line_clipped(
				clip, joint->anchor_a_x, joint->anchor_a_y, joint->anchor_b_x,
				joint->anchor_b_y, PICOSYSTEM_COLOR_YELLOW);
		}
	}
}

static PICOSYSTEM_RENDER_RAMFUNC void
render_ropes(const struct picosystem_scene_snapshot *snapshot, const struct picosystem_rect *clip,
	     struct picosystem_scene_render_progress *progress)
{
	for (uint16_t rope_index = 0U; rope_index < snapshot->rope_count; ++rope_index) {
		const struct picosystem_scene_rope *const rope =
			&snapshot->payload.rigid.ropes[rope_index];
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_ROPES, rope_index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_BOUNDS);
		if (clip != NULL) {
			const struct picosystem_rect bounds = picosystem_scene_rope_bounds(rope);
			if (!picosystem_scene_rectangles_intersect(&bounds, clip)) {
				continue;
			}
		}
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_ROPES, rope_index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_OUTLINE);
		for (uint8_t index = 0U; index < (rope->particle_count - 1U); ++index) {
			picosystem_graphics_draw_line_clipped(
				clip, rope->particles[index].x, rope->particles[index].y,
				rope->particles[index + 1U].x, rope->particles[index + 1U].y,
				PICOSYSTEM_COLOR_CYAN);
		}
		for (uint8_t index = 0U; index < rope->particle_count; ++index) {
			picosystem_graphics_draw_pixel_clipped(
				clip, rope->particles[index].x, rope->particles[index].y,
				(index == 0U) || (index == (rope->particle_count - 1U))
					? PICOSYSTEM_COLOR_WHITE
					: PICOSYSTEM_COLOR_CYAN);
		}
	}
}

static PICOSYSTEM_RENDER_RAMFUNC int
render_revolute_joints(const struct picosystem_scene_snapshot *snapshot,
		       const struct picosystem_rect *clip,
		       struct picosystem_scene_render_progress *progress)
{
	for (uint16_t index = 0U; index < snapshot->revolute_joint_count; ++index) {
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_REVOLUTE_JOINTS, index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_BOUNDS);
		const struct picosystem_scene_joint *const joint =
			&snapshot->payload.rigid.revolute_joints[index];
		if (clip != NULL) {
			const struct picosystem_rect bounds =
				picosystem_scene_revolute_joint_bounds(joint);
			if (!picosystem_scene_rectangles_intersect(&bounds, clip)) {
				continue;
			}
		}

		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_REVOLUTE_JOINTS, index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_OUTLINE);
		picosystem_graphics_draw_line_clipped(clip, joint->anchor_a_x, joint->anchor_a_y,
						      joint->anchor_b_x, joint->anchor_b_y,
						      PICOSYSTEM_COLOR_YELLOW);
		const int16_t center_x =
			(int16_t)(((int32_t)joint->anchor_a_x + joint->anchor_b_x) / 2);
		const int16_t center_y =
			(int16_t)(((int32_t)joint->anchor_a_y + joint->anchor_b_y) / 2);
		int err = picosystem_graphics_fill_circle_clipped(
			clip, center_x, center_y, PICOSYSTEM_SCENE_REVOLUTE_JOINT_RADIUS,
			PICOSYSTEM_COLOR_YELLOW);
		if (err == 0) {
			err = picosystem_graphics_fill_circle_clipped(clip, center_x, center_y, 1U,
								      PICOSYSTEM_COLOR_BLACK);
		}
		if (err != 0) {
			return err;
		}
	}
	return 0;
}

static PICOSYSTEM_RENDER_RAMFUNC int
render_bodies(const struct picosystem_scene_snapshot *snapshot, const struct picosystem_rect *clip,
	      struct picosystem_scene_render_progress *progress)
{
	for (uint16_t index = 0U; index < snapshot->body_count; ++index) {
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BODIES, index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_BOUNDS);
		if (clip != NULL) {
			const struct picosystem_rect bounds = picosystem_scene_body_bounds(
				&snapshot->payload.rigid.bodies[index]);
			if (!picosystem_scene_rectangles_intersect(&bounds, clip)) {
				continue;
			}
		}
		const int err =
			render_body(&snapshot->payload.rigid.bodies[index], index, clip, progress);
		if (err != 0) {
			return err;
		}
	}
	return 0;
}

PICOSYSTEM_RENDER_RAMFUNC int
picosystem_scene_render_full_observed(const struct picosystem_scene_snapshot *snapshot,
				      struct picosystem_scene_render_progress *progress)
{
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_VALIDATE, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	const int validate_err = validate_snapshot(snapshot);
	if (validate_err != 0) {
		return validate_err;
	}

	const struct picosystem_rect playfield = {
		.x = PLAYFIELD_LEFT,
		.y = PLAYFIELD_TOP,
		.width = PLAYFIELD_WIDTH,
		.height = PLAYFIELD_HEIGHT,
	};

	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_CLEAR, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	picosystem_graphics_clear(PICOSYSTEM_COLOR_BLACK);
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BACKGROUND, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	render_playfield_background(snapshot, &playfield);
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_GRANULES, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	int err = render_granules(snapshot, NULL, progress);
	if (err != 0) {
		return err;
	}
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BOX_SENSORS, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	render_box_sensors(snapshot, NULL, progress);
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_STATIC_SEGMENTS, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	render_static_segments(snapshot, NULL, progress);
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_DISTANCE_JOINTS, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	render_distance_joints(snapshot, NULL, progress);
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_ROPES, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	render_ropes(snapshot, NULL, progress);
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BODIES, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	err = render_bodies(snapshot, NULL, progress);
	if (err != 0) {
		return err;
	}
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_REVOLUTE_JOINTS, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	err = render_revolute_joints(snapshot, NULL, progress);
	if (err != 0) {
		return err;
	}

	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_HEADER, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	err = render_header(snapshot, NULL);
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_COMPLETE, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	return err;
}

int picosystem_scene_render_full(const struct picosystem_scene_snapshot *snapshot)
{
	return picosystem_scene_render_full_observed(snapshot, NULL);
}

PICOSYSTEM_RENDER_RAMFUNC int
picosystem_scene_render_region_observed(const struct picosystem_scene_snapshot *snapshot,
					const struct picosystem_rect *region,
					struct picosystem_scene_render_progress *progress)
{
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_VALIDATE, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	const int validate_err = validate_snapshot(snapshot);
	if (validate_err != 0) {
		return validate_err;
	}
	if ((region == NULL) || (region->width == 0U) || (region->height == 0U)) {
		return -EINVAL;
	}
	if ((region->x >= PICOSYSTEM_GRAPHICS_WIDTH) || (region->y >= PICOSYSTEM_GRAPHICS_HEIGHT) ||
	    (region->width > (PICOSYSTEM_GRAPHICS_WIDTH - region->x)) ||
	    (region->height > (PICOSYSTEM_GRAPHICS_HEIGHT - region->y))) {
		return -ERANGE;
	}

	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BACKGROUND, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	render_playfield_background(snapshot, region);
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_GRANULES, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	int err = render_granules(snapshot, region, progress);
	if (err != 0) {
		return err;
	}
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BOX_SENSORS, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	render_box_sensors(snapshot, region, progress);
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_STATIC_SEGMENTS, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	render_static_segments(snapshot, region, progress);
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_DISTANCE_JOINTS, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	render_distance_joints(snapshot, region, progress);
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_ROPES, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	render_ropes(snapshot, region, progress);
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BODIES, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	err = render_bodies(snapshot, region, progress);
	if (err != 0) {
		return err;
	}
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_REVOLUTE_JOINTS, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	err = render_revolute_joints(snapshot, region, progress);
	if (err != 0) {
		return err;
	}

	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_HEADER, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	err = render_header(snapshot, region);
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_COMPLETE, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	return err;
}

int picosystem_scene_render_region(const struct picosystem_scene_snapshot *snapshot,
				   const struct picosystem_rect *region)
{
	return picosystem_scene_render_region_observed(snapshot, region, NULL);
}

const char *picosystem_scene_render_stage_name(enum picosystem_scene_render_stage stage)
{
	switch (stage) {
	case PICOSYSTEM_SCENE_RENDER_STAGE_IDLE:
		return "idle";
	case PICOSYSTEM_SCENE_RENDER_STAGE_VALIDATE:
		return "validate";
	case PICOSYSTEM_SCENE_RENDER_STAGE_CLEAR:
		return "clear";
	case PICOSYSTEM_SCENE_RENDER_STAGE_BACKGROUND:
		return "background";
	case PICOSYSTEM_SCENE_RENDER_STAGE_GRANULES:
		return "granules";
	case PICOSYSTEM_SCENE_RENDER_STAGE_BOX_SENSORS:
		return "sensors";
	case PICOSYSTEM_SCENE_RENDER_STAGE_STATIC_SEGMENTS:
		return "segments";
	case PICOSYSTEM_SCENE_RENDER_STAGE_DISTANCE_JOINTS:
		return "joints";
	case PICOSYSTEM_SCENE_RENDER_STAGE_ROPES:
		return "ropes";
	case PICOSYSTEM_SCENE_RENDER_STAGE_BODIES:
		return "bodies";
	case PICOSYSTEM_SCENE_RENDER_STAGE_REVOLUTE_JOINTS:
		return "hinges";
	case PICOSYSTEM_SCENE_RENDER_STAGE_HEADER:
		return "header";
	case PICOSYSTEM_SCENE_RENDER_STAGE_COMPLETE:
		return "complete";
	default:
		return "unknown";
	}
}

const char *picosystem_scene_render_primitive_name(enum picosystem_scene_render_primitive primitive)
{
	switch (primitive) {
	case PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE:
		return "none";
	case PICOSYSTEM_SCENE_RENDER_PRIMITIVE_BOUNDS:
		return "bounds";
	case PICOSYSTEM_SCENE_RENDER_PRIMITIVE_FILL_0:
		return "fill-0";
	case PICOSYSTEM_SCENE_RENDER_PRIMITIVE_FILL_1:
		return "fill-1";
	case PICOSYSTEM_SCENE_RENDER_PRIMITIVE_OUTLINE:
		return "outline";
	case PICOSYSTEM_SCENE_RENDER_PRIMITIVE_FACE:
		return "face";
	case PICOSYSTEM_SCENE_RENDER_PRIMITIVE_HIGHLIGHT:
		return "highlight";
	default:
		return "unknown";
	}
}
