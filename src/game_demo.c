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

#include "display_sync.h"

LOG_MODULE_REGISTER(picosystem_game_demo, LOG_LEVEL_INF);

#define PLAYFIELD_LEFT                 PICOSYSTEM_GAME_PLAYFIELD_LEFT_PIXELS
#define PLAYFIELD_RIGHT                PICOSYSTEM_GAME_PLAYFIELD_RIGHT_PIXELS
#define PLAYFIELD_TOP                  PICOSYSTEM_GAME_PLAYFIELD_TOP_PIXELS
#define PLAYFIELD_BOTTOM               PICOSYSTEM_GAME_PLAYFIELD_BOTTOM_PIXELS
#define PLAYFIELD_WIDTH                (PLAYFIELD_RIGHT - PLAYFIELD_LEFT + 1U)
#define PLAYFIELD_HEIGHT               (PLAYFIELD_BOTTOM - PLAYFIELD_TOP + 1U)
#define BACKGROUND_TILE_SIZE           12U
#define HEADER_TEXT                    "RIGID LAB 120HZ"
#define HEADER_TEXT_X                  52
#define HEADER_TEXT_Y                  7
#define HEADER_TEXT_SCALE              2U
#define MAX_DIRTY_REGIONS              (PICOSYSTEM_PHYSICS_MAX_BODIES * 2U)
#define RENDER_THREAD_STACK_SIZE       3072U
#define RENDER_THREAD_PRIORITY         1
#define FRAMEBUFFER_CAPTURE_TIMEOUT_MS 2000

struct game_render_body {
	int16_t center_x;
	int16_t center_y;
	struct {
		int16_t x;
		int16_t y;
	} vertices[PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT];
	uint16_t radius;
	uint16_t id;
	uint8_t shape;
};

struct game_render_segment {
	int16_t start_x;
	int16_t start_y;
	int16_t end_x;
	int16_t end_y;
};

struct game_render_snapshot {
	int64_t published_uptime_ticks;
	uint32_t sequence;
	uint32_t logic_tick_count;
	uint32_t redraw_request_sequence;
	uint16_t body_count;
	uint16_t static_segment_count;
	struct game_render_body bodies[PICOSYSTEM_PHYSICS_MAX_BODIES];
	struct game_render_segment static_segments[PICOSYSTEM_PHYSICS_MAX_STATIC_SEGMENTS];
};

struct game_renderer_metrics {
	struct picosystem_graphics_stats graphics;
	uint32_t published_snapshot_count;
	uint32_t superseded_snapshot_count;
	uint32_t presented_snapshot_sequence;
	uint32_t presented_frame_count;
	uint32_t full_redraw_count;
	uint32_t last_render_time_us;
	uint32_t max_dirty_render_time_us;
	uint32_t last_snapshot_age_us;
	uint32_t max_dirty_snapshot_age_us;
	uint32_t render_stack_size_bytes;
	uint32_t render_stack_used_bytes;
	uint16_t presented_focus_x;
	uint16_t presented_focus_y;
	int render_error;
	bool render_thread_running;
};

struct game_renderer_context {
	struct k_spinlock lock;
	struct k_sem snapshot_ready;
	struct k_sem frame_presented;
	struct k_mutex framebuffer_mutex;
	struct game_render_snapshot snapshots[2];
	struct game_renderer_metrics metrics;
	struct picosystem_graphics_stats live_graphics;
	uint8_t published_index;
	bool snapshot_available;
};

static const picosystem_color_t body_colors[] = {
	PICOSYSTEM_COLOR_YELLOW,  PICOSYSTEM_COLOR_CYAN, PICOSYSTEM_COLOR_GREEN,
	PICOSYSTEM_COLOR_MAGENTA, PICOSYSTEM_COLOR_RED,  PICOSYSTEM_COLOR_WHITE,
};

K_THREAD_STACK_DEFINE(render_thread_stack, RENDER_THREAD_STACK_SIZE);
static struct k_thread render_thread;
static struct game_renderer_context renderer;

BUILD_ASSERT(PLAYFIELD_RIGHT < PICOSYSTEM_GRAPHICS_WIDTH);
BUILD_ASSERT(PLAYFIELD_BOTTOM < PICOSYSTEM_GRAPHICS_HEIGHT);
BUILD_ASSERT(PLAYFIELD_LEFT < PLAYFIELD_RIGHT);
BUILD_ASSERT(PLAYFIELD_TOP < PLAYFIELD_BOTTOM);
BUILD_ASSERT(RENDER_THREAD_PRIORITY > CONFIG_MAIN_THREAD_PRIORITY);
BUILD_ASSERT(sizeof(struct game_render_snapshot) <= 512U);

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

static uint32_t cycles_to_us(uint32_t cycles)
{
	return MAX(k_cyc_to_us_floor32(cycles), 1U);
}

static int16_t fixed_to_pixel(int32_t value)
{
	return (int16_t)(value / PICOSYSTEM_GAME_FIXED_ONE);
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

static picosystem_color_t background_color(uint16_t x, uint16_t y)
{
	const uint16_t tile_x = x / BACKGROUND_TILE_SIZE;
	const uint16_t tile_y = y / BACKGROUND_TILE_SIZE;

	return (((tile_x + tile_y) & 1U) == 0U) ? PICOSYSTEM_COLOR_NAVY
						: PICOSYSTEM_COLOR_DARK_BLUE;
}

static void render_playfield_background(const struct picosystem_rect *region)
{
	picosystem_graphics_fill_rect(region->x, region->y, region->width, region->height,
				      PICOSYSTEM_COLOR_BLACK);

	const uint16_t left = MAX(region->x, PLAYFIELD_LEFT);
	const uint16_t top = MAX(region->y, PLAYFIELD_TOP);
	const uint16_t right = MIN(region->x + region->width, PLAYFIELD_RIGHT + 1U);
	const uint16_t bottom = MIN(region->y + region->height, PLAYFIELD_BOTTOM + 1U);

	for (uint16_t y = top; y < bottom; ++y) {
		for (uint16_t x = left; x < right; ++x) {
			picosystem_graphics_draw_pixel(x, y, background_color(x, y));
		}
	}
}

static bool rectangles_intersect(const struct picosystem_rect *left,
				 const struct picosystem_rect *right)
{
	return (left->x < (right->x + right->width)) && (right->x < (left->x + left->width)) &&
	       (left->y < (right->y + right->height)) && (right->y < (left->y + left->height));
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

static struct picosystem_rect body_bounds(const struct game_render_body *body)
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

static struct picosystem_rect segment_bounds(const struct game_render_segment *segment)
{
	const int16_t left = MIN(segment->start_x, segment->end_x);
	const int16_t top = MIN(segment->start_y, segment->end_y);
	const int16_t right = MAX(segment->start_x, segment->end_x);
	const int16_t bottom = MAX(segment->start_y, segment->end_y);

	return (struct picosystem_rect){
		.x = (uint16_t)left,
		.y = (uint16_t)top,
		.width = (uint16_t)(right - left + 1),
		.height = (uint16_t)(bottom - top + 1),
	};
}

static bool snapshot_scene_matches(const struct game_render_snapshot *left,
				   const struct game_render_snapshot *right)
{
	if ((left->body_count != right->body_count) ||
	    (left->static_segment_count != right->static_segment_count)) {
		return false;
	}

	for (uint16_t index = 0U; index < left->body_count; ++index) {
		if ((left->bodies[index].id != right->bodies[index].id) ||
		    (left->bodies[index].shape != right->bodies[index].shape) ||
		    (left->bodies[index].radius != right->bodies[index].radius)) {
			return false;
		}
	}
	for (uint16_t index = 0U; index < left->static_segment_count; ++index) {
		const struct game_render_segment *const left_segment =
			&left->static_segments[index];
		const struct game_render_segment *const right_segment =
			&right->static_segments[index];
		if ((left_segment->start_x != right_segment->start_x) ||
		    (left_segment->start_y != right_segment->start_y) ||
		    (left_segment->end_x != right_segment->end_x) ||
		    (left_segment->end_y != right_segment->end_y)) {
			return false;
		}
	}
	return true;
}

static size_t merge_dirty_regions(struct picosystem_rect *regions, size_t count)
{
	while (true) {
		bool merged = false;
		for (size_t left = 0U; left < count; ++left) {
			for (size_t right = left + 1U; right < count; ++right) {
				if (!rectangles_touch_or_intersect(&regions[left],
								   &regions[right])) {
					continue;
				}

				regions[left] = union_rectangles(&regions[left], &regions[right]);
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

static bool body_render_state_matches(const struct game_render_body *left,
				      const struct game_render_body *right)
{
	if ((left->center_x != right->center_x) || (left->center_y != right->center_y) ||
	    (left->shape != right->shape) || (left->radius != right->radius) ||
	    (left->id != right->id)) {
		return false;
	}
	if (left->shape != PICOSYSTEM_PHYSICS_SHAPE_BOX) {
		return true;
	}

	for (size_t index = 0U; index < PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT; ++index) {
		if ((left->vertices[index].x != right->vertices[index].x) ||
		    (left->vertices[index].y != right->vertices[index].y)) {
			return false;
		}
	}
	return true;
}

static size_t build_dirty_regions(const struct game_render_snapshot *snapshot,
				  const struct game_render_snapshot *presented,
				  struct picosystem_rect *regions)
{
	size_t count = 0U;
	for (uint16_t index = 0U; index < snapshot->body_count; ++index) {
		if (body_render_state_matches(&snapshot->bodies[index],
					      &presented->bodies[index])) {
			continue;
		}
		const struct picosystem_rect current = body_bounds(&snapshot->bodies[index]);
		const struct picosystem_rect previous = body_bounds(&presented->bodies[index]);
		regions[count++] = previous;
		regions[count++] = current;
	}
	return merge_dirty_regions(regions, count);
}

static int render_body(const struct game_render_body *body)
{
	const picosystem_color_t color = body_colors[(body->id - 1U) % ARRAY_SIZE(body_colors)];
	if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_BOX) {
		picosystem_graphics_fill_triangle(body->vertices[0].x, body->vertices[0].y,
						  body->vertices[1].x, body->vertices[1].y,
						  body->vertices[2].x, body->vertices[2].y, color);
		picosystem_graphics_fill_triangle(body->vertices[0].x, body->vertices[0].y,
						  body->vertices[2].x, body->vertices[2].y,
						  body->vertices[3].x, body->vertices[3].y, color);
		for (size_t index = 0U; index < PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT; ++index) {
			const size_t next = (index + 1U) % PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT;
			picosystem_graphics_draw_line(
				body->vertices[index].x, body->vertices[index].y,
				body->vertices[next].x, body->vertices[next].y,
				PICOSYSTEM_COLOR_BLACK);
		}
		const int16_t face_x = (body->vertices[1].x + body->vertices[2].x) / 2;
		const int16_t face_y = (body->vertices[1].y + body->vertices[2].y) / 2;
		picosystem_graphics_draw_line(body->center_x, body->center_y, face_x, face_y,
					      PICOSYSTEM_COLOR_BLACK);
		return 0;
	}

	int err = picosystem_graphics_fill_circle(body->center_x, body->center_y, body->radius,
						  color);
	if ((err != 0) || (body->radius < 4U)) {
		return err;
	}

	const uint16_t highlight_radius = MAX(body->radius / 4U, 1U);
	err = picosystem_graphics_fill_circle(body->center_x - (int16_t)(body->radius / 3U),
					      body->center_y - (int16_t)(body->radius / 3U),
					      highlight_radius, PICOSYSTEM_COLOR_WHITE);
	return err;
}

static void render_static_segments(const struct game_render_snapshot *snapshot,
				   const struct picosystem_rect *clip)
{
	for (uint16_t index = 0U; index < snapshot->static_segment_count; ++index) {
		const struct game_render_segment *const segment = &snapshot->static_segments[index];
		const struct picosystem_rect bounds = segment_bounds(segment);
		if ((clip == NULL) || rectangles_intersect(&bounds, clip)) {
			picosystem_graphics_draw_line(segment->start_x, segment->start_y,
						      segment->end_x, segment->end_y,
						      PICOSYSTEM_COLOR_CYAN);
		}
	}
}

static int render_bodies(const struct game_render_snapshot *snapshot,
			 const struct picosystem_rect *clip)
{
	for (uint16_t index = 0U; index < snapshot->body_count; ++index) {
		const struct picosystem_rect bounds = body_bounds(&snapshot->bodies[index]);
		if ((clip != NULL) && !rectangles_intersect(&bounds, clip)) {
			continue;
		}
		const int err = render_body(&snapshot->bodies[index]);
		if (err != 0) {
			return err;
		}
	}
	return 0;
}

static int render_full_scene(const struct game_render_snapshot *snapshot)
{
	const struct picosystem_rect playfield = {
		.x = PLAYFIELD_LEFT,
		.y = PLAYFIELD_TOP,
		.width = PLAYFIELD_WIDTH,
		.height = PLAYFIELD_HEIGHT,
	};

	picosystem_graphics_clear(PICOSYSTEM_COLOR_BLACK);
	render_playfield_background(&playfield);
	render_static_segments(snapshot, NULL);
	int err = render_bodies(snapshot, NULL);
	if (err != 0) {
		return err;
	}

	err = picosystem_graphics_draw_text(HEADER_TEXT_X, HEADER_TEXT_Y, HEADER_TEXT,
					    HEADER_TEXT_SCALE, PICOSYSTEM_COLOR_WHITE);
	return err;
}

static int render_dirty_scene(const struct game_render_snapshot *snapshot,
			      const struct game_render_snapshot *presented)
{
	struct picosystem_rect regions[MAX_DIRTY_REGIONS];
	const size_t region_count = build_dirty_regions(snapshot, presented, regions);

	for (size_t index = 0U; index < region_count; ++index) {
		render_playfield_background(&regions[index]);
		render_static_segments(snapshot, &regions[index]);
		int err = render_bodies(snapshot, &regions[index]);
		if (err == 0) {
			err = picosystem_graphics_present_region(&renderer.live_graphics,
								 &regions[index]);
		}
		if (err != 0) {
			return err;
		}
	}
	return 0;
}

static int snapshot_from_state(const struct picosystem_game_demo_state *state, uint32_t sequence,
			       struct game_render_snapshot *snapshot)
{
	*snapshot = (struct game_render_snapshot){
		.published_uptime_ticks = k_uptime_ticks(),
		.sequence = sequence,
		.logic_tick_count = state->world.logic_tick_count,
		.redraw_request_sequence = state->redraw_request_sequence,
		.body_count = state->world.physics.body_count,
		.static_segment_count = state->world.physics.static_segment_count,
	};

	for (uint16_t index = 0U; index < snapshot->body_count; ++index) {
		const struct picosystem_physics_body *const body =
			&state->world.physics.bodies[index];
		snapshot->bodies[index] = (struct game_render_body){
			.center_x = fixed_to_pixel(body->center.x),
			.center_y = fixed_to_pixel(body->center.y),
			.radius = (uint16_t)fixed_to_pixel(body->radius),
			.id = body->id,
			.shape = body->shape,
		};
		if (body->shape == PICOSYSTEM_PHYSICS_SHAPE_BOX) {
			struct picosystem_physics_vector
				vertices[PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT];
			const int err = picosystem_physics_body_box_vertices(body, vertices);
			if (err != 0) {
				return err;
			}
			for (size_t vertex = 0U; vertex < PICOSYSTEM_PHYSICS_BOX_VERTEX_COUNT;
			     ++vertex) {
				snapshot->bodies[index].vertices[vertex].x =
					fixed_to_pixel(vertices[vertex].x);
				snapshot->bodies[index].vertices[vertex].y =
					fixed_to_pixel(vertices[vertex].y);
			}
		} else if (body->shape != PICOSYSTEM_PHYSICS_SHAPE_CIRCLE) {
			return -ERANGE;
		}
	}
	for (uint16_t index = 0U; index < snapshot->static_segment_count; ++index) {
		const struct picosystem_physics_static_segment *const segment =
			&state->world.physics.static_segments[index];
		snapshot->static_segments[index] = (struct game_render_segment){
			.start_x = fixed_to_pixel(segment->start.x),
			.start_y = fixed_to_pixel(segment->start.y),
			.end_x = fixed_to_pixel(segment->end.x),
			.end_y = fixed_to_pixel(segment->end.y),
		};
	}
	return 0;
}

static int publish_snapshot(struct picosystem_game_demo_state *state, bool notify_renderer)
{
	const uint32_t sequence = state->snapshot_sequence + 1U;
	struct game_render_snapshot snapshot;
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

static bool read_latest_snapshot(struct game_render_snapshot *snapshot)
{
	const k_spinlock_key_t key = k_spin_lock(&renderer.lock);
	const bool available = renderer.snapshot_available;

	if (available) {
		*snapshot = renderer.snapshots[renderer.published_index];
	}
	k_spin_unlock(&renderer.lock, key);
	return available;
}

static uint32_t snapshot_age_us(const struct game_render_snapshot *snapshot)
{
	const int64_t age_ticks = renderer.live_graphics.last_present_start_uptime_ticks -
				  snapshot->published_uptime_ticks;
	if (age_ticks <= 0) {
		return 0U;
	}

	const uint64_t age_us = k_ticks_to_us_floor64((uint64_t)age_ticks);
	return (uint32_t)MIN(age_us, UINT32_MAX);
}

static int present_snapshot(const struct game_render_snapshot *snapshot, bool full_redraw,
			    const struct game_render_snapshot *presented)
{
	if (full_redraw) {
		int err = render_full_scene(snapshot);
		if (err == 0) {
			err = picosystem_graphics_present_full(&renderer.live_graphics);
		}
		return err;
	}

	return render_dirty_scene(snapshot, presented);
}

static void record_renderer_failure(int err)
{
	const k_spinlock_key_t key = k_spin_lock(&renderer.lock);
	renderer.metrics.render_error = err;
	renderer.metrics.render_thread_running = false;
	k_spin_unlock(&renderer.lock, key);
}

static void record_presented_snapshot(const struct game_render_snapshot *snapshot, bool full_redraw,
				      uint32_t superseded_count, uint32_t render_time_us)
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
	renderer.metrics.last_snapshot_age_us = age_us;
	renderer.metrics.render_stack_used_bytes =
		MAX(renderer.metrics.render_stack_used_bytes, stack_used);
	if (snapshot->body_count != 0U) {
		renderer.metrics.presented_focus_x = (uint16_t)snapshot->bodies[0].center_x;
		renderer.metrics.presented_focus_y = (uint16_t)snapshot->bodies[0].center_y;
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
	struct game_render_snapshot presented;
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

		struct game_render_snapshot pending;
		if (!read_latest_snapshot(&pending) || (pending.sequence == consumed_sequence)) {
			continue;
		}

		const bool full_redraw_pending =
			(pending.redraw_request_sequence != consumed_redraw_sequence) ||
			!snapshot_scene_matches(&pending, &presented);
		int err = k_mutex_lock(&renderer.framebuffer_mutex, K_FOREVER);
		if (err != 0) {
			LOG_ERR("Renderer framebuffer lock failed (%d)", err);
			record_renderer_failure(err);
			return;
		}
		const uint32_t start_cycles = k_cycle_get_32();
		if (!full_redraw_pending) {
			(void)picosystem_display_sync_wait_for_vblank();
		}

		/* Late-latch only after capture contention and the TE wait have ended. */
		struct game_render_snapshot snapshot;
		if (!read_latest_snapshot(&snapshot) || (snapshot.sequence == consumed_sequence)) {
			k_mutex_unlock(&renderer.framebuffer_mutex);
			continue;
		}

		const uint32_t sequence_delta = snapshot.sequence - consumed_sequence;
		const uint32_t superseded_count = sequence_delta - 1U;
		const bool full_redraw =
			(snapshot.redraw_request_sequence != consumed_redraw_sequence) ||
			!snapshot_scene_matches(&snapshot, &presented);

		err = present_snapshot(&snapshot, full_redraw, &presented);
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
		record_presented_snapshot(&snapshot, full_redraw, superseded_count, render_time_us);
		k_mutex_unlock(&renderer.framebuffer_mutex);

		if (full_redraw) {
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
	int err = picosystem_game_world_reset(&state->world);
	if (err != 0) {
		return err;
	}

	renderer = (struct game_renderer_context){0};
	k_sem_init(&renderer.snapshot_ready, 0U, 1U);
	k_sem_init(&renderer.frame_presented, 0U, 1U);
	k_mutex_init(&renderer.framebuffer_mutex);

	err = picosystem_graphics_init(&renderer.live_graphics);
	if (err != 0) {
		return err;
	}

	state->snapshot_sequence = 1U;
	struct game_render_snapshot initial_snapshot;
	err = snapshot_from_state(state, state->snapshot_sequence, &initial_snapshot);
	if (err != 0) {
		return err;
	}
	err = render_full_scene(&initial_snapshot);
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
		.render_stack_size_bytes = K_THREAD_STACK_SIZEOF(render_thread_stack),
		.presented_focus_x = (uint16_t)initial_snapshot.bodies[0].center_x,
		.presented_focus_y = (uint16_t)initial_snapshot.bodies[0].center_y,
	};

	state->ready = true;
	(void)k_thread_create(&render_thread, render_thread_stack,
			      K_THREAD_STACK_SIZEOF(render_thread_stack), render_thread_entry, NULL,
			      NULL, NULL, K_PRIO_PREEMPT(RENDER_THREAD_PRIORITY), 0U, K_NO_WAIT);

	LOG_INF("120 Hz physics ready; renderer owns TE-aligned presentation at priority %d",
		RENDER_THREAD_PRIORITY);
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

int picosystem_game_demo_reset(struct picosystem_game_demo_state *state)
{
	if ((state == NULL) || !state->ready) {
		return -EINVAL;
	}

	const uint32_t snapshot_sequence = state->snapshot_sequence;
	const uint32_t redraw_request_sequence = state->redraw_request_sequence + 1U;
	const int err = picosystem_game_world_reset(&state->world);
	if (err != 0) {
		return err;
	}

	state->skipped_tick_count = 0U;
	state->over_budget_tick_count = 0U;
	state->last_update_time_us = 0U;
	state->max_update_time_us = 0U;
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

int picosystem_game_demo_update(struct picosystem_game_demo_state *state,
				const struct picosystem_game_input *input)
{
	if ((state == NULL) || (input == NULL) || !state->ready) {
		return -EINVAL;
	}

	const uint32_t start_cycles = k_cycle_get_32();
	int err = picosystem_game_world_step(&state->world, input);
	if (err != 0) {
		return err;
	}

	err = publish_snapshot(state, true);
	if (err != 0) {
		return err;
	}

	const uint32_t elapsed_us = cycles_to_us(k_cycle_get_32() - start_cycles);
	state->last_update_time_us = elapsed_us;
	state->max_update_time_us = MAX(state->max_update_time_us, elapsed_us);
	if (elapsed_us > (USEC_PER_SEC / PICOSYSTEM_GAME_TICK_RATE_HZ)) {
		increment_saturated(&state->over_budget_tick_count);
	}

	return 0;
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

	*stats = (struct picosystem_game_demo_stats){
		.graphics = render_metrics.graphics,
		.logic_tick_count = state->world.logic_tick_count,
		.measured_logic_tick_count =
			state->world.logic_tick_count - state->measurement_start_logic_tick_count,
		.skipped_tick_count = state->skipped_tick_count,
		.over_budget_tick_count = state->over_budget_tick_count,
		.last_update_time_us = state->last_update_time_us,
		.max_update_time_us = state->max_update_time_us,
		.max_backlog_ticks = state->max_backlog_ticks,
		.published_snapshot_count = render_metrics.published_snapshot_count,
		.superseded_snapshot_count = render_metrics.superseded_snapshot_count,
		.presented_snapshot_sequence = render_metrics.presented_snapshot_sequence,
		.presented_frame_count = render_metrics.presented_frame_count,
		.measured_presented_frame_count = render_metrics.presented_frame_count -
						  state->measurement_start_presented_frame_count,
		.full_redraw_count = render_metrics.full_redraw_count,
		.last_render_time_us = render_metrics.last_render_time_us,
		.max_dirty_render_time_us = render_metrics.max_dirty_render_time_us,
		.last_snapshot_age_us = render_metrics.last_snapshot_age_us,
		.max_dirty_snapshot_age_us = render_metrics.max_dirty_snapshot_age_us,
		.render_stack_size_bytes = render_metrics.render_stack_size_bytes,
		.render_stack_used_bytes = render_metrics.render_stack_used_bytes,
		.candidate_pair_count = state->world.physics.last_candidate_pair_count,
		.focus_angle_turns = focus->angle_turns,
		.focus_angular_velocity_milliradians_per_second =
			angular_velocity_to_milliradians_per_second(
				focus->angular_velocity_per_tick),
		.body_count = state->world.physics.body_count,
		.static_segment_count = state->world.physics.static_segment_count,
		.contact_count = state->world.physics.contact_count,
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
		.start_uptime_ms = state->start_uptime_ms,
		.render_error = render_metrics.render_error,
		.render_thread_running = render_metrics.render_thread_running,
	};
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

int picosystem_game_demo_renderer_error(void)
{
	const k_spinlock_key_t key = k_spin_lock(&renderer.lock);
	const int err = renderer.metrics.render_error;
	k_spin_unlock(&renderer.lock, key);
	return err;
}
