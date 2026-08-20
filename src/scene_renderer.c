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

#define PLAYFIELD_LEFT       PICOSYSTEM_GAME_PLAYFIELD_LEFT_PIXELS
#define PLAYFIELD_RIGHT      PICOSYSTEM_GAME_PLAYFIELD_RIGHT_PIXELS
#define PLAYFIELD_TOP        PICOSYSTEM_GAME_PLAYFIELD_TOP_PIXELS
#define PLAYFIELD_BOTTOM     PICOSYSTEM_GAME_PLAYFIELD_BOTTOM_PIXELS
#define PLAYFIELD_WIDTH      (PLAYFIELD_RIGHT - PLAYFIELD_LEFT + 1U)
#define PLAYFIELD_HEIGHT     (PLAYFIELD_BOTTOM - PLAYFIELD_TOP + 1U)
#define BACKGROUND_TILE_SIZE 12U
#define HEADER_TEXT          "MACHINE LAB 120HZ"
#define HEADER_TEXT_X        22
#define HEADER_TEXT_Y        7
#define HEADER_TEXT_SCALE    2U
#define SENSOR_COUNT_TEXT_X  2
#define SENSOR_COUNT_TEXT_Y  10
#define SENSOR_COUNT_SCALE   1U

static const picosystem_color_t body_colors[] = {
	PICOSYSTEM_COLOR_YELLOW,  PICOSYSTEM_COLOR_CYAN, PICOSYSTEM_COLOR_GREEN,
	PICOSYSTEM_COLOR_MAGENTA, PICOSYSTEM_COLOR_RED,  PICOSYSTEM_COLOR_WHITE,
};

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

static PICOSYSTEM_RENDER_RAMFUNC int
validate_snapshot(const struct picosystem_scene_snapshot *snapshot)
{
	if (snapshot == NULL) {
		return -EINVAL;
	}
	if ((snapshot->body_count > PICOSYSTEM_PHYSICS_MAX_BODIES) ||
	    (snapshot->static_segment_count > PICOSYSTEM_SCENE_MAX_SEGMENTS) ||
	    (snapshot->distance_joint_count > PICOSYSTEM_PHYSICS_MAX_DISTANCE_JOINTS) ||
	    (snapshot->revolute_joint_count > PICOSYSTEM_PHYSICS_MAX_REVOLUTE_JOINTS) ||
	    (snapshot->box_sensor_count > PICOSYSTEM_SCENE_MAX_BOX_SENSORS)) {
		return -ERANGE;
	}
	for (uint16_t index = 0U; index < snapshot->box_sensor_count; ++index) {
		const struct picosystem_rect *const bounds = &snapshot->box_sensors[index].bounds;
		if ((bounds->width == 0U) || (bounds->height == 0U) ||
		    (bounds->x >= PICOSYSTEM_GRAPHICS_WIDTH) ||
		    (bounds->y >= PICOSYSTEM_GRAPHICS_HEIGHT) ||
		    (bounds->width > (PICOSYSTEM_GRAPHICS_WIDTH - bounds->x)) ||
		    (bounds->height > (PICOSYSTEM_GRAPHICS_HEIGHT - bounds->y)) ||
		    (snapshot->box_sensors[index].active > 1U)) {
			return -ERANGE;
		}
	}
	return 0;
}

static PICOSYSTEM_RENDER_RAMFUNC void
render_playfield_background(const struct picosystem_rect *region)
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
	if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_BOX) {
		int16_t left = body->vertices[0].x;
		int16_t top = body->vertices[0].y;
		int16_t right = left;
		int16_t bottom = top;
		for (size_t index = 1U; index < PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT; ++index) {
			left = MIN(left, body->vertices[index].x);
			top = MIN(top, body->vertices[index].y);
			right = MAX(right, body->vertices[index].x);
			bottom = MAX(bottom, body->vertices[index].y);
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

	const int32_t left = MAX((int32_t)body->center_x - body->radius, 0);
	const int32_t top = MAX((int32_t)body->center_y - body->radius, 0);
	const int32_t right =
		MIN((int32_t)body->center_x + body->radius + 1, PICOSYSTEM_GRAPHICS_WIDTH);
	const int32_t bottom =
		MIN((int32_t)body->center_y + body->radius + 1, PICOSYSTEM_GRAPHICS_HEIGHT);

	return (struct picosystem_rect){
		.x = (uint16_t)left,
		.y = (uint16_t)top,
		.width = (uint16_t)(right - left),
		.height = (uint16_t)(bottom - top),
	};
}

static PICOSYSTEM_RENDER_RAMFUNC struct picosystem_rect
line_bounds(int16_t start_x, int16_t start_y, int16_t end_x, int16_t end_y)
{
	const int32_t left = MAX((int32_t)MIN(start_x, end_x), 0);
	const int32_t top = MAX((int32_t)MIN(start_y, end_y), 0);
	const int32_t right = MIN((int32_t)MAX(start_x, end_x), PICOSYSTEM_GRAPHICS_WIDTH - 1);
	const int32_t bottom = MIN((int32_t)MAX(start_y, end_y), PICOSYSTEM_GRAPHICS_HEIGHT - 1);
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

PICOSYSTEM_RENDER_RAMFUNC struct picosystem_rect
picosystem_scene_segment_bounds(const struct picosystem_scene_segment *segment)
{
	return line_bounds(segment->start_x, segment->start_y, segment->end_x, segment->end_y);
}

PICOSYSTEM_RENDER_RAMFUNC struct picosystem_rect
picosystem_scene_joint_bounds(const struct picosystem_scene_joint *joint)
{
	if (joint->target_radius != 0U) {
		const struct picosystem_scene_body guide = {
			.center_x = joint->anchor_b_x,
			.center_y = joint->anchor_b_y,
			.radius = joint->target_radius,
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

	return line_bounds((int16_t)start_x, (int16_t)start_y, (int16_t)end_x, (int16_t)end_y);
}

static PICOSYSTEM_RENDER_RAMFUNC int render_body(const struct picosystem_scene_body *body,
						 uint32_t body_index,
						 const struct picosystem_rect *clip,
						 struct picosystem_scene_render_progress *progress)
{
	const picosystem_color_t color = body_colors[(body->id - 1U) % ARRAY_SIZE(body_colors)];
	if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_BOX) {
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BODIES, body_index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_FILL_0);
		picosystem_graphics_fill_triangle_clipped(
			clip, body->vertices[0].x, body->vertices[0].y, body->vertices[1].x,
			body->vertices[1].y, body->vertices[2].x, body->vertices[2].y, color);
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BODIES, body_index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_FILL_1);
		picosystem_graphics_fill_triangle_clipped(
			clip, body->vertices[0].x, body->vertices[0].y, body->vertices[2].x,
			body->vertices[2].y, body->vertices[3].x, body->vertices[3].y, color);
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BODIES, body_index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_OUTLINE);
		for (size_t index = 0U; index < PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT; ++index) {
			const size_t next = (index + 1U) % PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT;
			picosystem_graphics_draw_line_clipped(
				clip, body->vertices[index].x, body->vertices[index].y,
				body->vertices[next].x, body->vertices[next].y,
				PICOSYSTEM_COLOR_BLACK);
		}
		const int16_t face_x = (body->vertices[1].x + body->vertices[2].x) / 2;
		const int16_t face_y = (body->vertices[1].y + body->vertices[2].y) / 2;
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BODIES, body_index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_FACE);
		picosystem_graphics_draw_line_clipped(clip, body->center_x, body->center_y, face_x,
						      face_y, PICOSYSTEM_COLOR_BLACK);
		return 0;
	}

	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BODIES, body_index,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_FILL_0);
	int err = picosystem_graphics_fill_circle_clipped(clip, body->center_x, body->center_y,
							  body->radius, color);
	if ((err != 0) || (body->radius < 4U)) {
		return err;
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
render_static_segments(const struct picosystem_scene_snapshot *snapshot,
		       const struct picosystem_rect *clip,
		       struct picosystem_scene_render_progress *progress)
{
	for (uint16_t index = 0U; index < snapshot->static_segment_count; ++index) {
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_STATIC_SEGMENTS, index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_BOUNDS);
		const struct picosystem_scene_segment *const segment =
			&snapshot->static_segments[index];
		if (clip != NULL) {
			const struct picosystem_rect bounds =
				picosystem_scene_segment_bounds(segment);
			if (!picosystem_scene_rectangles_intersect(&bounds, clip)) {
				continue;
			}
		}
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_STATIC_SEGMENTS, index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_OUTLINE);
		picosystem_graphics_draw_line_clipped(clip, segment->start_x, segment->start_y,
						      segment->end_x, segment->end_y,
						      PICOSYSTEM_COLOR_CYAN);
	}
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
			&snapshot->box_sensors[index];
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
	int err;
	if (clip == NULL) {
		err = picosystem_graphics_draw_text(HEADER_TEXT_X, HEADER_TEXT_Y, HEADER_TEXT,
						    HEADER_TEXT_SCALE, PICOSYSTEM_COLOR_WHITE);
	} else {
		err = picosystem_graphics_draw_text_clipped(clip, HEADER_TEXT_X, HEADER_TEXT_Y,
							    HEADER_TEXT, HEADER_TEXT_SCALE,
							    PICOSYSTEM_COLOR_WHITE);
	}
	if (err != 0) {
		return err;
	}

	const uint32_t displayed_count = snapshot->sensor_entry_count % 100U;
	const char count_text[] = {
		'S',
		(char)('0' + (displayed_count / 10U)),
		(char)('0' + (displayed_count % 10U)),
		'\0',
	};
	if (clip == NULL) {
		return picosystem_graphics_draw_text(SENSOR_COUNT_TEXT_X, SENSOR_COUNT_TEXT_Y,
						     count_text, SENSOR_COUNT_SCALE,
						     PICOSYSTEM_COLOR_GREEN);
	}
	return picosystem_graphics_draw_text_clipped(clip, SENSOR_COUNT_TEXT_X, SENSOR_COUNT_TEXT_Y,
						     count_text, SENSOR_COUNT_SCALE,
						     PICOSYSTEM_COLOR_GREEN);
}

static PICOSYSTEM_RENDER_RAMFUNC void
render_world_joint_guide(const struct picosystem_scene_joint *joint,
			 const struct picosystem_rect *clip)
{
	int32_t x = joint->target_radius;
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

static PICOSYSTEM_RENDER_RAMFUNC void
render_distance_joints(const struct picosystem_scene_snapshot *snapshot,
		       const struct picosystem_rect *clip,
		       struct picosystem_scene_render_progress *progress)
{
	for (uint16_t index = 0U; index < snapshot->distance_joint_count; ++index) {
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_DISTANCE_JOINTS, index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_BOUNDS);
		const struct picosystem_scene_joint *const joint =
			&snapshot->distance_joints[index];
		if (clip != NULL) {
			const struct picosystem_rect bounds = picosystem_scene_joint_bounds(joint);
			if (!picosystem_scene_rectangles_intersect(&bounds, clip)) {
				continue;
			}
		}
		update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_DISTANCE_JOINTS, index,
				PICOSYSTEM_SCENE_RENDER_PRIMITIVE_OUTLINE);
		if (joint->target_radius != 0U) {
			render_world_joint_guide(joint, clip);
		} else {
			picosystem_graphics_draw_line_clipped(
				clip, joint->anchor_a_x, joint->anchor_a_y, joint->anchor_b_x,
				joint->anchor_b_y, PICOSYSTEM_COLOR_YELLOW);
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
			&snapshot->revolute_joints[index];
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
			const struct picosystem_rect bounds =
				picosystem_scene_body_bounds(&snapshot->bodies[index]);
			if (!picosystem_scene_rectangles_intersect(&bounds, clip)) {
				continue;
			}
		}
		const int err = render_body(&snapshot->bodies[index], index, clip, progress);
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
	render_playfield_background(&playfield);
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BOX_SENSORS, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	render_box_sensors(snapshot, NULL, progress);
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_STATIC_SEGMENTS, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	render_static_segments(snapshot, NULL, progress);
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_DISTANCE_JOINTS, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	render_distance_joints(snapshot, NULL, progress);
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BODIES, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	int err = render_bodies(snapshot, NULL, progress);
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
	render_playfield_background(region);
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BOX_SENSORS, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	render_box_sensors(snapshot, region, progress);
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_STATIC_SEGMENTS, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	render_static_segments(snapshot, region, progress);
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_DISTANCE_JOINTS, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	render_distance_joints(snapshot, region, progress);
	update_progress(progress, PICOSYSTEM_SCENE_RENDER_STAGE_BODIES, 0U,
			PICOSYSTEM_SCENE_RENDER_PRIMITIVE_NONE);
	int err = render_bodies(snapshot, region, progress);
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
	case PICOSYSTEM_SCENE_RENDER_STAGE_BOX_SENSORS:
		return "sensors";
	case PICOSYSTEM_SCENE_RENDER_STAGE_STATIC_SEGMENTS:
		return "segments";
	case PICOSYSTEM_SCENE_RENDER_STAGE_DISTANCE_JOINTS:
		return "joints";
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
