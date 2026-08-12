/*
 * Copyright (c) 2026 PicoSystem Playground contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "game_demo.h"

#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/util.h>

LOG_MODULE_REGISTER(picosystem_game_demo, LOG_LEVEL_INF);

#define PLAYFIELD_TOP        24U
#define PLAYFIELD_LEFT       1U
#define PLAYFIELD_RIGHT      (PICOSYSTEM_GRAPHICS_WIDTH - 1U)
#define PLAYFIELD_BOTTOM     (PICOSYSTEM_GRAPHICS_HEIGHT - 1U)
#define PLAYFIELD_WIDTH      (PLAYFIELD_RIGHT - PLAYFIELD_LEFT)
#define PLAYFIELD_HEIGHT     (PLAYFIELD_BOTTOM - PLAYFIELD_TOP)
#define SPRITE_WIDTH         16U
#define SPRITE_HEIGHT        16U
#define SPRITE_STRIDE_BYTES  2U
#define SPRITE_SPEED_PIXELS  2
#define SPRITE_MIN_X         PLAYFIELD_LEFT
#define SPRITE_MAX_X         (PLAYFIELD_RIGHT - SPRITE_WIDTH)
#define SPRITE_MIN_Y         (PLAYFIELD_TOP + 1U)
#define SPRITE_MAX_Y         (PLAYFIELD_BOTTOM - SPRITE_HEIGHT)
#define SPRITE_START_X       ((SPRITE_MIN_X + SPRITE_MAX_X) / 2U)
#define SPRITE_START_Y       ((SPRITE_MIN_Y + SPRITE_MAX_Y) / 2U)
#define BACKGROUND_TILE_SIZE 12U
#define HEADER_TEXT          "FRAMEBUFFER DIRTY 16MS"
#define HEADER_TEXT_X        8
#define HEADER_TEXT_Y        7
#define HEADER_TEXT_SCALE    2U

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

BUILD_ASSERT(SPRITE_WIDTH <= PLAYFIELD_WIDTH);
BUILD_ASSERT(SPRITE_HEIGHT < PLAYFIELD_HEIGHT);
BUILD_ASSERT(SPRITE_STRIDE_BYTES >= DIV_ROUND_UP(SPRITE_WIDTH, 8U));
BUILD_ASSERT(sizeof(sprite_data) == (SPRITE_HEIGHT * SPRITE_STRIDE_BYTES));

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

static int render_full_scene(const struct picosystem_game_demo_state *state)
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

	err = render_sprite(state->sprite_x, state->sprite_y);
	if (err != 0) {
		return err;
	}

	return 0;
}

static struct picosystem_rect sprite_movement_region(const struct picosystem_game_demo_state *state)
{
	const uint16_t left = MIN(state->presented_sprite_x, state->sprite_x);
	const uint16_t top = MIN(state->presented_sprite_y, state->sprite_y);
	const uint16_t right = MAX(state->presented_sprite_x, state->sprite_x) + SPRITE_WIDTH;
	const uint16_t bottom = MAX(state->presented_sprite_y, state->sprite_y) + SPRITE_HEIGHT;

	return (struct picosystem_rect){
		.x = left,
		.y = top,
		.width = right - left,
		.height = bottom - top,
	};
}

static uint16_t move_coordinate(uint16_t current, int8_t *velocity, uint16_t minimum,
				uint16_t maximum)
{
	const int8_t speed = (*velocity < 0) ? (int8_t) - *velocity : *velocity;
	int32_t requested = (int32_t)current + *velocity;

	if (requested < minimum) {
		requested = minimum;
		*velocity = speed;
	} else if (requested > maximum) {
		requested = maximum;
		*velocity = -speed;
	}

	return (uint16_t)requested;
}

static void record_render_time(struct picosystem_game_demo_state *state, uint32_t start_cycles,
			       bool dirty_region)
{
	const uint32_t elapsed_cycles = k_cycle_get_32() - start_cycles;
	const uint32_t elapsed_us = MAX(k_cyc_to_us_floor32(elapsed_cycles), 1U);

	state->last_render_time_us = elapsed_us;
	if (dirty_region) {
		state->max_dirty_render_time_us = MAX(state->max_dirty_render_time_us, elapsed_us);
	}
	if (state->presented_frame_count < UINT32_MAX) {
		++state->presented_frame_count;
	}
}

int picosystem_game_demo_init(struct picosystem_game_demo_state *state)
{
	if (state == NULL) {
		return -EINVAL;
	}

	*state = (struct picosystem_game_demo_state){
		.sprite_x = SPRITE_START_X,
		.sprite_y = SPRITE_START_Y,
		.presented_sprite_x = SPRITE_START_X,
		.presented_sprite_y = SPRITE_START_Y,
		.velocity_x = SPRITE_SPEED_PIXELS,
		.velocity_y = SPRITE_SPEED_PIXELS,
	};

	int err = picosystem_graphics_init(&state->graphics);
	if (err != 0) {
		return err;
	}

	const uint32_t start_cycles = k_cycle_get_32();
	err = render_full_scene(state);
	if (err != 0) {
		return err;
	}

	err = picosystem_graphics_present_full(&state->graphics);
	if (err != 0) {
		return err;
	}

	err = picosystem_graphics_enable_output(&state->graphics);
	if (err != 0) {
		return err;
	}

	state->start_uptime_ms = k_uptime_get();
	record_render_time(state, start_cycles, false);
	state->ready = true;
	LOG_INF("Game framebuffer visible: full present %u us, render %u us",
		state->graphics.full_present_time_us, state->last_render_time_us);
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

	if (input->horizontal != 0) {
		state->velocity_x = input->horizontal * SPRITE_SPEED_PIXELS;
	}
	if (input->vertical != 0) {
		state->velocity_y = input->vertical * SPRITE_SPEED_PIXELS;
	}

	const uint16_t next_x =
		move_coordinate(state->sprite_x, &state->velocity_x, SPRITE_MIN_X, SPRITE_MAX_X);
	const uint16_t next_y =
		move_coordinate(state->sprite_y, &state->velocity_y, SPRITE_MIN_Y, SPRITE_MAX_Y);

	state->sprite_x = next_x;
	state->sprite_y = next_y;
	state->present_pending = (state->sprite_x != state->presented_sprite_x) ||
				 (state->sprite_y != state->presented_sprite_y);
	if (state->logic_tick_count < UINT32_MAX) {
		++state->logic_tick_count;
	}

	return 0;
}

int picosystem_game_demo_present(struct picosystem_game_demo_state *state)
{
	if ((state == NULL) || !state->ready) {
		return -EINVAL;
	}

	if (!state->present_pending) {
		return 0;
	}

	const uint32_t start_cycles = k_cycle_get_32();
	const struct picosystem_rect dirty_region = sprite_movement_region(state);

	render_playfield_background(&dirty_region);
	int err = render_sprite(state->sprite_x, state->sprite_y);
	if (err != 0) {
		return err;
	}

	err = picosystem_graphics_present_region(&state->graphics, &dirty_region);
	if (err != 0) {
		return err;
	}

	state->presented_sprite_x = state->sprite_x;
	state->presented_sprite_y = state->sprite_y;
	state->present_pending = false;
	record_render_time(state, start_cycles, true);
	return 0;
}

int picosystem_game_demo_redraw(struct picosystem_game_demo_state *state)
{
	if ((state == NULL) || !state->ready) {
		return -EINVAL;
	}

	const uint32_t start_cycles = k_cycle_get_32();
	int err = render_full_scene(state);
	if (err != 0) {
		return err;
	}

	err = picosystem_graphics_present_full(&state->graphics);
	if (err != 0) {
		return err;
	}

	state->presented_sprite_x = state->sprite_x;
	state->presented_sprite_y = state->sprite_y;
	state->present_pending = false;
	record_render_time(state, start_cycles, false);
	return 0;
}

void picosystem_game_demo_note_skipped_ticks(struct picosystem_game_demo_state *state,
					     uint32_t skipped_ticks)
{
	if ((state == NULL) || (skipped_ticks == 0U)) {
		return;
	}

	if (skipped_ticks > (UINT32_MAX - state->skipped_tick_count)) {
		state->skipped_tick_count = UINT32_MAX;
	} else {
		state->skipped_tick_count += skipped_ticks;
	}
}
