/*
 * Copyright (c) 2026 PicoSystem Playground contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "game_demo.h"

#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/util.h>

#include "display_sync.h"

LOG_MODULE_REGISTER(picosystem_game_demo, LOG_LEVEL_INF);

#define PLAYFIELD_TOP                  24U
#define PLAYFIELD_LEFT                 1U
#define PLAYFIELD_RIGHT                (PICOSYSTEM_GRAPHICS_WIDTH - 1U)
#define PLAYFIELD_BOTTOM               (PICOSYSTEM_GRAPHICS_HEIGHT - 1U)
#define PLAYFIELD_WIDTH                (PLAYFIELD_RIGHT - PLAYFIELD_LEFT)
#define PLAYFIELD_HEIGHT               (PLAYFIELD_BOTTOM - PLAYFIELD_TOP)
#define SPRITE_WIDTH                   16U
#define SPRITE_HEIGHT                  16U
#define SPRITE_STRIDE_BYTES            2U
#define SPRITE_SPEED_PIXELS_PER_SECOND 125
#define SPRITE_MIN_X                   PLAYFIELD_LEFT
#define SPRITE_MAX_X                   (PLAYFIELD_RIGHT - SPRITE_WIDTH)
#define SPRITE_MIN_Y                   (PLAYFIELD_TOP + 1U)
#define SPRITE_MAX_Y                   (PLAYFIELD_BOTTOM - SPRITE_HEIGHT)
#define SPRITE_START_X                 ((SPRITE_MIN_X + SPRITE_MAX_X) / 2U)
#define SPRITE_START_Y                 ((SPRITE_MIN_Y + SPRITE_MAX_Y) / 2U)
#define BACKGROUND_TILE_SIZE           12U
#define HEADER_TEXT                    "SIM 120HZ TE DISPLAY"
#define HEADER_TEXT_X                  8
#define HEADER_TEXT_Y                  7
#define HEADER_TEXT_SCALE              2U
#define FIXED_FRACTION_BITS            16U
#define FIXED_ONE                      (INT32_C(1) << FIXED_FRACTION_BITS)
#define RENDER_THREAD_STACK_SIZE       2048U
#define RENDER_THREAD_PRIORITY         1

struct game_render_snapshot {
	int64_t published_uptime_ticks;
	uint32_t sequence;
	uint32_t logic_tick_count;
	uint32_t redraw_request_sequence;
	uint16_t sprite_x;
	uint16_t sprite_y;
};

struct game_renderer_metrics {
	struct picosystem_graphics_stats graphics;
	uint32_t published_snapshot_count;
	uint32_t superseded_snapshot_count;
	uint32_t presented_frame_count;
	uint32_t full_redraw_count;
	uint32_t last_render_time_us;
	uint32_t max_dirty_render_time_us;
	uint32_t last_snapshot_age_us;
	uint32_t max_dirty_snapshot_age_us;
	uint32_t render_stack_size_bytes;
	uint32_t render_stack_used_bytes;
	uint16_t presented_sprite_x;
	uint16_t presented_sprite_y;
	int render_error;
	bool render_thread_running;
};

struct game_renderer_context {
	struct k_spinlock lock;
	struct k_sem snapshot_ready;
	struct game_render_snapshot snapshots[2];
	struct game_renderer_metrics metrics;
	struct picosystem_graphics_stats live_graphics;
	uint8_t published_index;
	bool snapshot_available;
};

static const uint8_t sprite_data[SPRITE_HEIGHT * SPRITE_STRIDE_BYTES] = {
	0x01U, 0x80U, 0x03U, 0xc0U, 0x07U, 0xe0U, 0x0dU, 0xb0U, 0x1fU, 0xf8U, 0x3fU,
	0xfcU, 0x77U, 0xeeU, 0xffU, 0xffU, 0xbfU, 0xfdU, 0x99U, 0x99U, 0x18U, 0x18U,
	0x3cU, 0x3cU, 0x24U, 0x24U, 0x66U, 0x66U, 0x42U, 0x42U, 0x00U, 0x00U,
};

static const struct picosystem_mono_sprite sprite = {
	.data = sprite_data,
	.data_size = sizeof(sprite_data),
	.width = SPRITE_WIDTH,
	.height = SPRITE_HEIGHT,
	.stride_bytes = SPRITE_STRIDE_BYTES,
};

K_THREAD_STACK_DEFINE(render_thread_stack, RENDER_THREAD_STACK_SIZE);
static struct k_thread render_thread;
static struct game_renderer_context renderer;

BUILD_ASSERT(SPRITE_WIDTH <= PLAYFIELD_WIDTH);
BUILD_ASSERT(SPRITE_HEIGHT < PLAYFIELD_HEIGHT);
BUILD_ASSERT(SPRITE_STRIDE_BYTES >= DIV_ROUND_UP(SPRITE_WIDTH, 8U));
BUILD_ASSERT(sizeof(sprite_data) == (SPRITE_HEIGHT * SPRITE_STRIDE_BYTES));
BUILD_ASSERT((SPRITE_MAX_X * FIXED_ONE) <= INT32_MAX);
BUILD_ASSERT((SPRITE_MAX_Y * FIXED_ONE) <= INT32_MAX);
BUILD_ASSERT((SPRITE_SPEED_PIXELS_PER_SECOND * FIXED_ONE) <= INT32_MAX);
BUILD_ASSERT(RENDER_THREAD_PRIORITY > CONFIG_MAIN_THREAD_PRIORITY);
BUILD_ASSERT(sizeof(struct game_render_snapshot) == 24U);

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

static uint16_t fixed_to_pixel(int32_t value)
{
	return (uint16_t)(value >> FIXED_FRACTION_BITS);
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
	const uint16_t left = MAX(region->x, PLAYFIELD_LEFT);
	const uint16_t top = MAX(region->y, SPRITE_MIN_Y);
	const uint16_t right = MIN(region->x + region->width, PLAYFIELD_RIGHT);
	const uint16_t bottom = MIN(region->y + region->height, PLAYFIELD_BOTTOM);

	for (uint16_t y = top; y < bottom; ++y) {
		for (uint16_t x = left; x < right; ++x) {
			picosystem_graphics_draw_pixel(x, y, background_color(x, y));
		}
	}
}

static int render_sprite(uint16_t x, uint16_t y)
{
	return picosystem_graphics_draw_mono_sprite(x, y, &sprite, PICOSYSTEM_COLOR_YELLOW);
}

static int render_full_scene(const struct game_render_snapshot *snapshot)
{
	const struct picosystem_rect playfield = {
		.x = PLAYFIELD_LEFT,
		.y = SPRITE_MIN_Y,
		.width = PLAYFIELD_WIDTH,
		.height = PLAYFIELD_BOTTOM - SPRITE_MIN_Y,
	};

	picosystem_graphics_clear(PICOSYSTEM_COLOR_BLACK);
	render_playfield_background(&playfield);
	picosystem_graphics_draw_rect(0, PLAYFIELD_TOP, PICOSYSTEM_GRAPHICS_WIDTH,
				      PICOSYSTEM_GRAPHICS_HEIGHT - PLAYFIELD_TOP,
				      PICOSYSTEM_COLOR_CYAN);

	int err = picosystem_graphics_draw_text(HEADER_TEXT_X, HEADER_TEXT_Y, HEADER_TEXT,
						HEADER_TEXT_SCALE, PICOSYSTEM_COLOR_WHITE);
	if (err != 0) {
		return err;
	}

	return render_sprite(snapshot->sprite_x, snapshot->sprite_y);
}

static struct picosystem_rect sprite_movement_region(const struct game_render_snapshot *snapshot,
						     uint16_t presented_x, uint16_t presented_y)
{
	const uint16_t left = MIN(presented_x, snapshot->sprite_x);
	const uint16_t top = MIN(presented_y, snapshot->sprite_y);
	const uint16_t right = MAX(presented_x, snapshot->sprite_x) + SPRITE_WIDTH;
	const uint16_t bottom = MAX(presented_y, snapshot->sprite_y) + SPRITE_HEIGHT;

	return (struct picosystem_rect){
		.x = left,
		.y = top,
		.width = right - left,
		.height = bottom - top,
	};
}

static int32_t move_coordinate(int32_t current, int32_t *velocity, int32_t minimum, int32_t maximum)
{
	const int32_t speed = (*velocity < 0) ? -*velocity : *velocity;
	int32_t requested = current + (*velocity / (int32_t)PICOSYSTEM_GAME_TICK_RATE_HZ);

	if (requested < minimum) {
		requested = minimum;
		*velocity = speed;
	} else if (requested > maximum) {
		requested = maximum;
		*velocity = -speed;
	}

	return requested;
}

static struct game_render_snapshot
snapshot_from_state(const struct picosystem_game_demo_state *state)
{
	return (struct game_render_snapshot){
		.published_uptime_ticks = k_uptime_ticks(),
		.sequence = state->snapshot_sequence,
		.logic_tick_count = state->logic_tick_count,
		.redraw_request_sequence = state->redraw_request_sequence,
		.sprite_x = fixed_to_pixel(state->sprite_x_fixed),
		.sprite_y = fixed_to_pixel(state->sprite_y_fixed),
	};
}

static void publish_snapshot(struct picosystem_game_demo_state *state, bool notify_renderer)
{
	++state->snapshot_sequence;
	const struct game_render_snapshot snapshot = snapshot_from_state(state);
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
			    uint16_t presented_x, uint16_t presented_y)
{
	if (full_redraw) {
		int err = render_full_scene(snapshot);
		if (err != 0) {
			return err;
		}

		return picosystem_graphics_present_full(&renderer.live_graphics);
	}

	const struct picosystem_rect dirty_region =
		sprite_movement_region(snapshot, presented_x, presented_y);
	render_playfield_background(&dirty_region);
	int err = render_sprite(snapshot->sprite_x, snapshot->sprite_y);
	if (err != 0) {
		return err;
	}

	return picosystem_graphics_present_region(&renderer.live_graphics, &dirty_region);
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
	renderer.metrics.presented_sprite_x = snapshot->sprite_x;
	renderer.metrics.presented_sprite_y = snapshot->sprite_y;
	k_spin_unlock(&renderer.lock, key);
}

static void render_thread_entry(void *argument1, void *argument2, void *argument3)
{
	ARG_UNUSED(argument1);
	ARG_UNUSED(argument2);
	ARG_UNUSED(argument3);

	uint32_t consumed_sequence;
	uint32_t consumed_redraw_sequence;
	uint16_t presented_x;
	uint16_t presented_y;
	{
		const k_spinlock_key_t key = k_spin_lock(&renderer.lock);
		const struct game_render_snapshot initial =
			renderer.snapshots[renderer.published_index];
		consumed_sequence = initial.sequence;
		consumed_redraw_sequence = initial.redraw_request_sequence;
		presented_x = renderer.metrics.presented_sprite_x;
		presented_y = renderer.metrics.presented_sprite_y;
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

		struct game_render_snapshot pending_snapshot;
		if (!read_latest_snapshot(&pending_snapshot) ||
		    (pending_snapshot.sequence == consumed_sequence)) {
			continue;
		}

		const bool full_redraw_pending =
			pending_snapshot.redraw_request_sequence != consumed_redraw_sequence;
		const uint32_t start_cycles = k_cycle_get_32();
		if (!full_redraw_pending) {
			(void)picosystem_display_sync_wait_for_vblank();
		}

		/* Late-latch the newest authoritative state after the TE wait. */
		struct game_render_snapshot snapshot;
		if (!read_latest_snapshot(&snapshot) || (snapshot.sequence == consumed_sequence)) {
			continue;
		}

		const uint32_t sequence_delta = snapshot.sequence - consumed_sequence;
		const uint32_t superseded_count = sequence_delta - 1U;
		const bool full_redraw =
			snapshot.redraw_request_sequence != consumed_redraw_sequence;
		const int err = present_snapshot(&snapshot, full_redraw, presented_x, presented_y);
		if (err != 0) {
			LOG_ERR("Renderer failed to present snapshot %u (%d)", snapshot.sequence,
				err);
			record_renderer_failure(err);
			return;
		}

		const uint32_t render_time_us = cycles_to_us(k_cycle_get_32() - start_cycles);
		consumed_sequence = snapshot.sequence;
		consumed_redraw_sequence = snapshot.redraw_request_sequence;
		presented_x = snapshot.sprite_x;
		presented_y = snapshot.sprite_y;
		record_presented_snapshot(&snapshot, full_redraw, superseded_count, render_time_us);

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

	*state = (struct picosystem_game_demo_state){
		.sprite_x_fixed = SPRITE_START_X * FIXED_ONE,
		.sprite_y_fixed = SPRITE_START_Y * FIXED_ONE,
		.velocity_x_fixed_per_second = SPRITE_SPEED_PIXELS_PER_SECOND * FIXED_ONE,
		.velocity_y_fixed_per_second = SPRITE_SPEED_PIXELS_PER_SECOND * FIXED_ONE,
	};
	renderer = (struct game_renderer_context){0};
	k_sem_init(&renderer.snapshot_ready, 0U, 1U);

	int err = picosystem_graphics_init(&renderer.live_graphics);
	if (err != 0) {
		return err;
	}

	state->snapshot_sequence = 1U;
	const struct game_render_snapshot initial_snapshot = snapshot_from_state(state);
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
		.render_stack_size_bytes = K_THREAD_STACK_SIZEOF(render_thread_stack),
		.presented_sprite_x = initial_snapshot.sprite_x,
		.presented_sprite_y = initial_snapshot.sprite_y,
	};

	state->ready = true;
	(void)k_thread_create(&render_thread, render_thread_stack,
			      K_THREAD_STACK_SIZEOF(render_thread_stack), render_thread_entry, NULL,
			      NULL, NULL, K_PRIO_PREEMPT(RENDER_THREAD_PRIORITY), 0U, K_NO_WAIT);

	LOG_INF("120 Hz simulation ready; renderer owns TE-aligned presentation at priority %d",
		RENDER_THREAD_PRIORITY);
	return 0;
}

int picosystem_game_demo_start_simulation(struct picosystem_game_demo_state *state)
{
	if ((state == NULL) || !state->ready) {
		return -EINVAL;
	}
	if ((state->start_uptime_ms != 0) || (state->logic_tick_count != 0U)) {
		return -EALREADY;
	}

	state->start_uptime_ms = k_uptime_get();
	return 0;
}

int picosystem_game_demo_update(struct picosystem_game_demo_state *state,
				const struct picosystem_game_input *input)
{
	if ((state == NULL) || (input == NULL) || !state->ready) {
		return -EINVAL;
	}

	if ((input->horizontal < -1) || (input->horizontal > 1) || (input->vertical < -1) ||
	    (input->vertical > 1)) {
		return -ERANGE;
	}

	const uint32_t start_cycles = k_cycle_get_32();
	const int32_t speed_fixed = SPRITE_SPEED_PIXELS_PER_SECOND * FIXED_ONE;
	if (input->horizontal != 0) {
		state->velocity_x_fixed_per_second = input->horizontal * speed_fixed;
	}
	if (input->vertical != 0) {
		state->velocity_y_fixed_per_second = input->vertical * speed_fixed;
	}

	state->sprite_x_fixed =
		move_coordinate(state->sprite_x_fixed, &state->velocity_x_fixed_per_second,
				SPRITE_MIN_X * FIXED_ONE, SPRITE_MAX_X * FIXED_ONE);
	state->sprite_y_fixed =
		move_coordinate(state->sprite_y_fixed, &state->velocity_y_fixed_per_second,
				SPRITE_MIN_Y * FIXED_ONE, SPRITE_MAX_Y * FIXED_ONE);
	increment_saturated(&state->logic_tick_count);
	publish_snapshot(state, true);

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
	publish_snapshot(state, true);
	return 0;
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

	const k_spinlock_key_t key = k_spin_lock(&renderer.lock);
	const struct game_renderer_metrics render_metrics = renderer.metrics;
	k_spin_unlock(&renderer.lock, key);

	*stats = (struct picosystem_game_demo_stats){
		.graphics = render_metrics.graphics,
		.logic_tick_count = state->logic_tick_count,
		.skipped_tick_count = state->skipped_tick_count,
		.over_budget_tick_count = state->over_budget_tick_count,
		.last_update_time_us = state->last_update_time_us,
		.max_update_time_us = state->max_update_time_us,
		.max_backlog_ticks = state->max_backlog_ticks,
		.published_snapshot_count = render_metrics.published_snapshot_count,
		.superseded_snapshot_count = render_metrics.superseded_snapshot_count,
		.presented_frame_count = render_metrics.presented_frame_count,
		.full_redraw_count = render_metrics.full_redraw_count,
		.last_render_time_us = render_metrics.last_render_time_us,
		.max_dirty_render_time_us = render_metrics.max_dirty_render_time_us,
		.last_snapshot_age_us = render_metrics.last_snapshot_age_us,
		.max_dirty_snapshot_age_us = render_metrics.max_dirty_snapshot_age_us,
		.render_stack_size_bytes = render_metrics.render_stack_size_bytes,
		.render_stack_used_bytes = render_metrics.render_stack_used_bytes,
		.sprite_x = fixed_to_pixel(state->sprite_x_fixed),
		.sprite_y = fixed_to_pixel(state->sprite_y_fixed),
		.presented_sprite_x = render_metrics.presented_sprite_x,
		.presented_sprite_y = render_metrics.presented_sprite_y,
		.velocity_x_pixels_per_second =
			(int16_t)(state->velocity_x_fixed_per_second / FIXED_ONE),
		.velocity_y_pixels_per_second =
			(int16_t)(state->velocity_y_fixed_per_second / FIXED_ONE),
		.start_uptime_ms = state->start_uptime_ms,
		.render_error = render_metrics.render_error,
		.render_thread_running = render_metrics.render_thread_running,
	};
	return 0;
}

int picosystem_game_demo_renderer_error(void)
{
	const k_spinlock_key_t key = k_spin_lock(&renderer.lock);
	const int err = renderer.metrics.render_error;
	k_spin_unlock(&renderer.lock, key);
	return err;
}
