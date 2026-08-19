/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "dense_scene.h"

#include <errno.h>
#include <stddef.h>
#include <stdint.h>

#include "graphics.h"

#define DENSE_COLUMNS      8U
#define DENSE_ROWS         8U
#define DENSE_CELL_WIDTH   (PICOSYSTEM_GRAPHICS_WIDTH / DENSE_COLUMNS)
#define DENSE_CELL_HEIGHT  (PICOSYSTEM_GRAPHICS_HEIGHT / DENSE_ROWS)
#define DENSE_BODY_RADIUS  10U
#define DENSE_MOTION_STEPS 7U

struct dense_scene_point {
	int16_t x;
	int16_t y;
};

static const picosystem_color_t dense_colors[] = {
	PICOSYSTEM_COLOR_RED,   PICOSYSTEM_COLOR_GREEN,   PICOSYSTEM_COLOR_BLUE,
	PICOSYSTEM_COLOR_CYAN,  PICOSYSTEM_COLOR_MAGENTA, PICOSYSTEM_COLOR_YELLOW,
	PICOSYSTEM_COLOR_WHITE, PICOSYSTEM_COLOR_NAVY,
};

static struct dense_scene_point dense_body_center(uint8_t row, uint8_t column, uint32_t frame_index)
{
	const int16_t base_x = (int16_t)((column * DENSE_CELL_WIDTH) + (DENSE_CELL_WIDTH / 2U));
	const int16_t base_y = (int16_t)((row * DENSE_CELL_HEIGHT) + (DENSE_CELL_HEIGHT / 2U));
	const int16_t motion_x =
		(int16_t)((frame_index + ((uint32_t)row * 3U) + ((uint32_t)column * 5U)) %
			  DENSE_MOTION_STEPS) -
		(int16_t)(DENSE_MOTION_STEPS / 2U);
	const int16_t motion_y =
		(int16_t)(((frame_index * 2U) + ((uint32_t)row * 5U) + ((uint32_t)column * 3U)) %
			  DENSE_MOTION_STEPS) -
		(int16_t)(DENSE_MOTION_STEPS / 2U);

	return (struct dense_scene_point){
		.x = base_x + motion_x,
		.y = base_y + motion_y,
	};
}

static void draw_dense_background(void)
{
	for (uint8_t row = 0U; row < DENSE_ROWS; ++row) {
		for (uint8_t column = 0U; column < DENSE_COLUMNS; ++column) {
			const picosystem_color_t color = (((row + column) & 1U) == 0U)
								 ? PICOSYSTEM_COLOR_NAVY
								 : PICOSYSTEM_COLOR_DARK_BLUE;
			picosystem_graphics_fill_rect((int16_t)(column * DENSE_CELL_WIDTH),
						      (int16_t)(row * DENSE_CELL_HEIGHT),
						      DENSE_CELL_WIDTH, DENSE_CELL_HEIGHT, color);
		}
	}
}

static void draw_dense_links(uint32_t frame_index)
{
	for (uint8_t row = 0U; row < DENSE_ROWS; ++row) {
		for (uint8_t column = 0U; column < DENSE_COLUMNS; ++column) {
			const struct dense_scene_point center =
				dense_body_center(row, column, frame_index);
			if ((column + 1U) < DENSE_COLUMNS) {
				const struct dense_scene_point right =
					dense_body_center(row, column + 1U, frame_index);
				picosystem_graphics_draw_line(center.x, center.y, right.x, right.y,
							      PICOSYSTEM_COLOR_CYAN);
			}
			if ((row + 1U) < DENSE_ROWS) {
				const struct dense_scene_point below =
					dense_body_center(row + 1U, column, frame_index);
				picosystem_graphics_draw_line(center.x, center.y, below.x, below.y,
							      PICOSYSTEM_COLOR_YELLOW);
			}
		}
	}
}

static void draw_dense_box(const struct dense_scene_point *center, picosystem_color_t color,
			   uint32_t frame_index)
{
	const int16_t radius = DENSE_BODY_RADIUS;
	const int16_t skew = (int16_t)(frame_index % 5U) - 2;
	const struct dense_scene_point vertices[] = {
		{.x = center->x + skew, .y = center->y - radius},
		{.x = center->x + radius, .y = center->y + skew},
		{.x = center->x - skew, .y = center->y + radius},
		{.x = center->x - radius, .y = center->y - skew},
	};

	picosystem_graphics_fill_triangle(vertices[0].x, vertices[0].y, vertices[1].x,
					  vertices[1].y, vertices[2].x, vertices[2].y, color);
	picosystem_graphics_fill_triangle(vertices[0].x, vertices[0].y, vertices[2].x,
					  vertices[2].y, vertices[3].x, vertices[3].y, color);
	for (size_t index = 0U; index < (sizeof(vertices) / sizeof(vertices[0])); ++index) {
		const size_t next = (index + 1U) % (sizeof(vertices) / sizeof(vertices[0]));
		picosystem_graphics_draw_line(vertices[index].x, vertices[index].y,
					      vertices[next].x, vertices[next].y,
					      PICOSYSTEM_COLOR_BLACK);
	}
	picosystem_graphics_draw_line(center->x, center->y, vertices[1].x, vertices[1].y,
				      PICOSYSTEM_COLOR_BLACK);
}

static picosystem_color_t dense_body_color(uint8_t row, uint8_t column, uint32_t frame_index)
{
	const size_t color_count = sizeof(dense_colors) / sizeof(dense_colors[0]);
	return dense_colors[(frame_index + ((uint32_t)row * DENSE_COLUMNS) + column) % color_count];
}

static int draw_dense_circles(uint32_t frame_index)
{
	for (uint8_t row = 0U; row < DENSE_ROWS; ++row) {
		for (uint8_t column = 0U; column < DENSE_COLUMNS; ++column) {
			if (((row + column) & 1U) != 0U) {
				continue;
			}

			const struct dense_scene_point center =
				dense_body_center(row, column, frame_index);
			const picosystem_color_t color = dense_body_color(row, column, frame_index);
			int err = picosystem_graphics_fill_circle(center.x, center.y,
								  DENSE_BODY_RADIUS, color);
			if (err == 0) {
				err = picosystem_graphics_fill_circle(center.x - 3, center.y - 3,
								      2U, PICOSYSTEM_COLOR_WHITE);
			}
			if (err != 0) {
				return err;
			}
		}
	}
	return 0;
}

static void draw_dense_boxes(uint32_t frame_index)
{
	for (uint8_t row = 0U; row < DENSE_ROWS; ++row) {
		for (uint8_t column = 0U; column < DENSE_COLUMNS; ++column) {
			if (((row + column) & 1U) == 0U) {
				continue;
			}

			const struct dense_scene_point center =
				dense_body_center(row, column, frame_index);
			const picosystem_color_t color = dense_body_color(row, column, frame_index);
			draw_dense_box(&center, color, frame_index + row + column);
		}
	}
}

int picosystem_dense_scene_draw_stage(enum picosystem_dense_scene_stage stage, uint32_t frame_index)
{
	switch (stage) {
	case PICOSYSTEM_DENSE_SCENE_STAGE_BACKGROUND:
		draw_dense_background();
		return 0;
	case PICOSYSTEM_DENSE_SCENE_STAGE_LINKS:
		draw_dense_links(frame_index);
		return 0;
	case PICOSYSTEM_DENSE_SCENE_STAGE_CIRCLES:
		return draw_dense_circles(frame_index);
	case PICOSYSTEM_DENSE_SCENE_STAGE_BOXES:
		draw_dense_boxes(frame_index);
		return 0;
	case PICOSYSTEM_DENSE_SCENE_STAGE_COUNT:
	default:
		return -EINVAL;
	}
}

int picosystem_dense_scene_draw(uint32_t frame_index)
{
	for (enum picosystem_dense_scene_stage stage = PICOSYSTEM_DENSE_SCENE_STAGE_BACKGROUND;
	     stage < PICOSYSTEM_DENSE_SCENE_STAGE_COUNT; ++stage) {
		const int err = picosystem_dense_scene_draw_stage(stage, frame_index);
		if (err != 0) {
			return err;
		}
	}
	return 0;
}
