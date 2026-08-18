/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "display_profile.h"

#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/sys/util.h>

#include "display_sync.h"

#define PROFILE_TILE_SIZE                   24U
#define PROFILE_TILE_COLUMNS                (PICOSYSTEM_GRAPHICS_WIDTH / PROFILE_TILE_SIZE)
#define PROFILE_TILE_ROWS                   (PICOSYSTEM_GRAPHICS_HEIGHT / PROFILE_TILE_SIZE)
#define PROFILE_TILE_COUNT                  (PROFILE_TILE_COLUMNS * PROFILE_TILE_ROWS)
#define PROFILE_TILE_PERMUTATION_MULTIPLIER 37U
#define PROFILE_DENSE_COLUMNS               8U
#define PROFILE_DENSE_ROWS                  8U
#define PROFILE_DENSE_CELL_WIDTH            (PICOSYSTEM_GRAPHICS_WIDTH / PROFILE_DENSE_COLUMNS)
#define PROFILE_DENSE_CELL_HEIGHT           (PICOSYSTEM_GRAPHICS_HEIGHT / PROFILE_DENSE_ROWS)
#define PROFILE_DENSE_BODY_RADIUS           10U
#define PROFILE_DENSE_MOTION_STEPS          7U

enum display_profile_layout {
	DISPLAY_PROFILE_LAYOUT_BAND,
	DISPLAY_PROFILE_LAYOUT_TILES,
	DISPLAY_PROFILE_LAYOUT_FULL_DIRECT,
	DISPLAY_PROFILE_LAYOUT_DENSE_FULL,
};

struct display_profile_case_spec {
	const char *name;
	enum display_profile_layout layout;
	uint8_t coverage_percent;
};

struct display_profile_frame_result {
	uint32_t stage_cycles[PICOSYSTEM_DISPLAY_PROFILE_STAGE_COUNT];
	uint32_t dense_stage_cycles[PICOSYSTEM_DISPLAY_PROFILE_DENSE_STAGE_COUNT];
	uint16_t region_count;
	uint16_t display_write_count;
	bool synchronized;
};

struct display_profile_workspace {
	uint32_t stage_samples[PICOSYSTEM_DISPLAY_PROFILE_STAGE_COUNT]
			      [PICOSYSTEM_DISPLAY_PROFILE_MAX_SAMPLES];
	uint32_t dense_stage_samples[PICOSYSTEM_DISPLAY_PROFILE_DENSE_STAGE_COUNT]
				    [PICOSYSTEM_DISPLAY_PROFILE_MAX_SAMPLES];
};

struct display_profile_point {
	int16_t x;
	int16_t y;
};

static const struct display_profile_case_spec case_specs[] = {
	{.name = "band-10", .layout = DISPLAY_PROFILE_LAYOUT_BAND, .coverage_percent = 10U},
	{.name = "tiles-10", .layout = DISPLAY_PROFILE_LAYOUT_TILES, .coverage_percent = 10U},
	{.name = "band-25", .layout = DISPLAY_PROFILE_LAYOUT_BAND, .coverage_percent = 25U},
	{.name = "tiles-25", .layout = DISPLAY_PROFILE_LAYOUT_TILES, .coverage_percent = 25U},
	{.name = "band-50", .layout = DISPLAY_PROFILE_LAYOUT_BAND, .coverage_percent = 50U},
	{.name = "tiles-50", .layout = DISPLAY_PROFILE_LAYOUT_TILES, .coverage_percent = 50U},
	{.name = "band-75", .layout = DISPLAY_PROFILE_LAYOUT_BAND, .coverage_percent = 75U},
	{.name = "tiles-75", .layout = DISPLAY_PROFILE_LAYOUT_TILES, .coverage_percent = 75U},
	{.name = "band-100", .layout = DISPLAY_PROFILE_LAYOUT_BAND, .coverage_percent = 100U},
	{.name = "tiles-100", .layout = DISPLAY_PROFILE_LAYOUT_TILES, .coverage_percent = 100U},
	{.name = "full-100",
	 .layout = DISPLAY_PROFILE_LAYOUT_FULL_DIRECT,
	 .coverage_percent = 100U},
	{.name = "dense-100",
	 .layout = DISPLAY_PROFILE_LAYOUT_DENSE_FULL,
	 .coverage_percent = 100U},
};

static const char *const stage_names[] = {
	"draw",
	"te_wait",
	"present",
	"total",
};

static const char *const dense_stage_names[] = {
	"background",
	"links",
	"circles",
	"boxes",
};

static const picosystem_color_t profile_colors[] = {
	PICOSYSTEM_COLOR_RED,   PICOSYSTEM_COLOR_GREEN,   PICOSYSTEM_COLOR_BLUE,
	PICOSYSTEM_COLOR_CYAN,  PICOSYSTEM_COLOR_MAGENTA, PICOSYSTEM_COLOR_YELLOW,
	PICOSYSTEM_COLOR_WHITE, PICOSYSTEM_COLOR_NAVY,
};

static struct display_profile_workspace workspace;
K_MUTEX_DEFINE(display_profile_mutex);

BUILD_ASSERT((PICOSYSTEM_GRAPHICS_WIDTH % PROFILE_TILE_SIZE) == 0U);
BUILD_ASSERT((PICOSYSTEM_GRAPHICS_HEIGHT % PROFILE_TILE_SIZE) == 0U);
BUILD_ASSERT(PROFILE_TILE_COUNT == 100U);
BUILD_ASSERT((PICOSYSTEM_GRAPHICS_WIDTH % PROFILE_DENSE_COLUMNS) == 0U);
BUILD_ASSERT((PICOSYSTEM_GRAPHICS_HEIGHT % PROFILE_DENSE_ROWS) == 0U);
BUILD_ASSERT((PROFILE_DENSE_CELL_WIDTH / 2U) >
	     (PROFILE_DENSE_BODY_RADIUS + (PROFILE_DENSE_MOTION_STEPS / 2U)));
BUILD_ASSERT((PROFILE_DENSE_CELL_HEIGHT / 2U) >
	     (PROFILE_DENSE_BODY_RADIUS + (PROFILE_DENSE_MOTION_STEPS / 2U)));
BUILD_ASSERT(ARRAY_SIZE(case_specs) == PICOSYSTEM_DISPLAY_PROFILE_CASE_COUNT);
BUILD_ASSERT(ARRAY_SIZE(stage_names) == PICOSYSTEM_DISPLAY_PROFILE_STAGE_COUNT);
BUILD_ASSERT(ARRAY_SIZE(dense_stage_names) == PICOSYSTEM_DISPLAY_PROFILE_DENSE_STAGE_COUNT);

const char *picosystem_display_profile_case_name(size_t case_index)
{
	return (case_index < ARRAY_SIZE(case_specs)) ? case_specs[case_index].name : NULL;
}

const char *picosystem_display_profile_stage_name(size_t stage_index)
{
	return (stage_index < ARRAY_SIZE(stage_names)) ? stage_names[stage_index] : NULL;
}

const char *picosystem_display_profile_dense_stage_name(size_t stage_index)
{
	return (stage_index < ARRAY_SIZE(dense_stage_names)) ? dense_stage_names[stage_index]
							     : NULL;
}

static struct picosystem_rect band_region(uint8_t coverage_percent)
{
	const uint16_t height = (uint16_t)((PICOSYSTEM_GRAPHICS_HEIGHT * coverage_percent) / 100U);
	return (struct picosystem_rect){
		.x = 0U,
		.y = (PICOSYSTEM_GRAPHICS_HEIGHT - height) / 2U,
		.width = PICOSYSTEM_GRAPHICS_WIDTH,
		.height = height,
	};
}

static uint16_t covered_tile_count(uint8_t coverage_percent)
{
	return (uint16_t)((PROFILE_TILE_COUNT * coverage_percent) / 100U);
}

static struct picosystem_rect tile_region(uint16_t ordered_index)
{
	const uint16_t tile_index =
		(uint16_t)(((uint32_t)ordered_index * PROFILE_TILE_PERMUTATION_MULTIPLIER) %
			   PROFILE_TILE_COUNT);
	return (struct picosystem_rect){
		.x = (uint16_t)((tile_index % PROFILE_TILE_COLUMNS) * PROFILE_TILE_SIZE),
		.y = (uint16_t)((tile_index / PROFILE_TILE_COLUMNS) * PROFILE_TILE_SIZE),
		.width = PROFILE_TILE_SIZE,
		.height = PROFILE_TILE_SIZE,
	};
}

static picosystem_color_t frame_color(size_t case_index, uint32_t frame_index)
{
	return profile_colors[(case_index + frame_index) % ARRAY_SIZE(profile_colors)];
}

static struct display_profile_point dense_body_center(uint8_t row, uint8_t column,
						      uint32_t frame_index)
{
	const int16_t base_x =
		(int16_t)((column * PROFILE_DENSE_CELL_WIDTH) + (PROFILE_DENSE_CELL_WIDTH / 2U));
	const int16_t base_y =
		(int16_t)((row * PROFILE_DENSE_CELL_HEIGHT) + (PROFILE_DENSE_CELL_HEIGHT / 2U));
	const int16_t motion_x =
		(int16_t)((frame_index + ((uint32_t)row * 3U) + ((uint32_t)column * 5U)) %
			  PROFILE_DENSE_MOTION_STEPS) -
		(int16_t)(PROFILE_DENSE_MOTION_STEPS / 2U);
	const int16_t motion_y =
		(int16_t)(((frame_index * 2U) + ((uint32_t)row * 5U) + ((uint32_t)column * 3U)) %
			  PROFILE_DENSE_MOTION_STEPS) -
		(int16_t)(PROFILE_DENSE_MOTION_STEPS / 2U);

	return (struct display_profile_point){
		.x = base_x + motion_x,
		.y = base_y + motion_y,
	};
}

static void draw_dense_background(void)
{
	for (uint8_t row = 0U; row < PROFILE_DENSE_ROWS; ++row) {
		for (uint8_t column = 0U; column < PROFILE_DENSE_COLUMNS; ++column) {
			const picosystem_color_t color = (((row + column) & 1U) == 0U)
								 ? PICOSYSTEM_COLOR_NAVY
								 : PICOSYSTEM_COLOR_DARK_BLUE;
			picosystem_graphics_fill_rect((int16_t)(column * PROFILE_DENSE_CELL_WIDTH),
						      (int16_t)(row * PROFILE_DENSE_CELL_HEIGHT),
						      PROFILE_DENSE_CELL_WIDTH,
						      PROFILE_DENSE_CELL_HEIGHT, color);
		}
	}
}

static void draw_dense_links(uint32_t frame_index)
{
	for (uint8_t row = 0U; row < PROFILE_DENSE_ROWS; ++row) {
		for (uint8_t column = 0U; column < PROFILE_DENSE_COLUMNS; ++column) {
			const struct display_profile_point center =
				dense_body_center(row, column, frame_index);
			if ((column + 1U) < PROFILE_DENSE_COLUMNS) {
				const struct display_profile_point right =
					dense_body_center(row, column + 1U, frame_index);
				picosystem_graphics_draw_line(center.x, center.y, right.x, right.y,
							      PICOSYSTEM_COLOR_CYAN);
			}
			if ((row + 1U) < PROFILE_DENSE_ROWS) {
				const struct display_profile_point below =
					dense_body_center(row + 1U, column, frame_index);
				picosystem_graphics_draw_line(center.x, center.y, below.x, below.y,
							      PICOSYSTEM_COLOR_YELLOW);
			}
		}
	}
}

static void draw_dense_box(const struct display_profile_point *center, picosystem_color_t color,
			   uint32_t frame_index)
{
	const int16_t radius = PROFILE_DENSE_BODY_RADIUS;
	const int16_t skew = (int16_t)(frame_index % 5U) - 2;
	const struct display_profile_point vertices[] = {
		{.x = center->x + skew, .y = center->y - radius},
		{.x = center->x + radius, .y = center->y + skew},
		{.x = center->x - skew, .y = center->y + radius},
		{.x = center->x - radius, .y = center->y - skew},
	};

	picosystem_graphics_fill_triangle(vertices[0].x, vertices[0].y, vertices[1].x,
					  vertices[1].y, vertices[2].x, vertices[2].y, color);
	picosystem_graphics_fill_triangle(vertices[0].x, vertices[0].y, vertices[2].x,
					  vertices[2].y, vertices[3].x, vertices[3].y, color);
	for (size_t index = 0U; index < ARRAY_SIZE(vertices); ++index) {
		const size_t next = (index + 1U) % ARRAY_SIZE(vertices);
		picosystem_graphics_draw_line(vertices[index].x, vertices[index].y,
					      vertices[next].x, vertices[next].y,
					      PICOSYSTEM_COLOR_BLACK);
	}
	picosystem_graphics_draw_line(center->x, center->y, vertices[1].x, vertices[1].y,
				      PICOSYSTEM_COLOR_BLACK);
}

static picosystem_color_t dense_body_color(uint8_t row, uint8_t column, uint32_t frame_index)
{
	return profile_colors[(frame_index + ((uint32_t)row * PROFILE_DENSE_COLUMNS) + column) %
			      ARRAY_SIZE(profile_colors)];
}

static int draw_dense_circles(uint32_t frame_index)
{
	for (uint8_t row = 0U; row < PROFILE_DENSE_ROWS; ++row) {
		for (uint8_t column = 0U; column < PROFILE_DENSE_COLUMNS; ++column) {
			if (((row + column) & 1U) != 0U) {
				continue;
			}

			const struct display_profile_point center =
				dense_body_center(row, column, frame_index);
			const picosystem_color_t color = dense_body_color(row, column, frame_index);
			int err = picosystem_graphics_fill_circle(center.x, center.y,
								  PROFILE_DENSE_BODY_RADIUS, color);
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
	for (uint8_t row = 0U; row < PROFILE_DENSE_ROWS; ++row) {
		for (uint8_t column = 0U; column < PROFILE_DENSE_COLUMNS; ++column) {
			if (((row + column) & 1U) == 0U) {
				continue;
			}

			const struct display_profile_point center =
				dense_body_center(row, column, frame_index);
			const picosystem_color_t color = dense_body_color(row, column, frame_index);
			draw_dense_box(&center, color, frame_index + row + column);
		}
	}
}

static int draw_dense_scene(uint32_t frame_index, uint32_t *stage_cycles)
{
	uint32_t stage_start = k_cycle_get_32();
	draw_dense_background();
	stage_cycles[PICOSYSTEM_DISPLAY_PROFILE_DENSE_STAGE_BACKGROUND] =
		k_cycle_get_32() - stage_start;

	stage_start = k_cycle_get_32();
	draw_dense_links(frame_index);
	stage_cycles[PICOSYSTEM_DISPLAY_PROFILE_DENSE_STAGE_LINKS] = k_cycle_get_32() - stage_start;

	stage_start = k_cycle_get_32();
	const int circle_err = draw_dense_circles(frame_index);
	stage_cycles[PICOSYSTEM_DISPLAY_PROFILE_DENSE_STAGE_CIRCLES] =
		k_cycle_get_32() - stage_start;
	if (circle_err != 0) {
		return circle_err;
	}

	stage_start = k_cycle_get_32();
	draw_dense_boxes(frame_index);
	stage_cycles[PICOSYSTEM_DISPLAY_PROFILE_DENSE_STAGE_BOXES] = k_cycle_get_32() - stage_start;
	return 0;
}

static int draw_case(const struct display_profile_case_spec *spec, size_t case_index,
		     uint32_t frame_index, uint32_t *dense_stage_cycles)
{
	const picosystem_color_t color = frame_color(case_index, frame_index);

	if (spec->layout == DISPLAY_PROFILE_LAYOUT_FULL_DIRECT) {
		picosystem_graphics_clear(color);
		return 0;
	}
	if (spec->layout == DISPLAY_PROFILE_LAYOUT_DENSE_FULL) {
		return draw_dense_scene(frame_index, dense_stage_cycles);
	}
	if (spec->layout == DISPLAY_PROFILE_LAYOUT_BAND) {
		const struct picosystem_rect region = band_region(spec->coverage_percent);
		picosystem_graphics_fill_rect(region.x, region.y, region.width, region.height,
					      color);
		return 0;
	}

	const uint16_t tile_count = covered_tile_count(spec->coverage_percent);
	for (uint16_t tile = 0U; tile < tile_count; ++tile) {
		const struct picosystem_rect region = tile_region(tile);
		picosystem_graphics_fill_rect(region.x, region.y, region.width, region.height,
					      color);
	}
	return 0;
}

static int present_case(const struct display_profile_case_spec *spec,
			struct picosystem_graphics_stats *graphics, uint16_t *region_count)
{
	*region_count = 0U;
	if ((spec->layout == DISPLAY_PROFILE_LAYOUT_FULL_DIRECT) ||
	    (spec->layout == DISPLAY_PROFILE_LAYOUT_DENSE_FULL)) {
		const int err = picosystem_graphics_present_full(graphics);
		if (err == 0) {
			*region_count = 1U;
		}
		return err;
	}
	if (spec->layout == DISPLAY_PROFILE_LAYOUT_BAND) {
		const struct picosystem_rect region = band_region(spec->coverage_percent);
		const int err = picosystem_graphics_present_region(graphics, &region);
		if (err == 0) {
			*region_count = 1U;
		}
		return err;
	}

	const uint16_t tile_count = covered_tile_count(spec->coverage_percent);
	for (uint16_t tile = 0U; tile < tile_count; ++tile) {
		const struct picosystem_rect region = tile_region(tile);
		const int err = picosystem_graphics_present_region(graphics, &region);
		if (err != 0) {
			return err;
		}
		++*region_count;
	}
	return 0;
}

static int run_frame(const struct display_profile_case_spec *spec, size_t case_index,
		     uint32_t frame_index, struct picosystem_graphics_stats *graphics,
		     struct display_profile_frame_result *frame)
{
	const uint32_t total_start = k_cycle_get_32();
	const uint32_t draw_start = k_cycle_get_32();
	const int draw_err = draw_case(spec, case_index, frame_index, frame->dense_stage_cycles);
	frame->stage_cycles[PICOSYSTEM_DISPLAY_PROFILE_STAGE_DRAW] = k_cycle_get_32() - draw_start;
	if (draw_err != 0) {
		return draw_err;
	}

	const uint32_t wait_start = k_cycle_get_32();
	frame->synchronized = picosystem_display_sync_wait_for_vblank();
	frame->stage_cycles[PICOSYSTEM_DISPLAY_PROFILE_STAGE_TE_WAIT] =
		k_cycle_get_32() - wait_start;

	const uint32_t write_count_before = graphics->display_write_count;
	const uint32_t present_start = k_cycle_get_32();
	const int err = present_case(spec, graphics, &frame->region_count);
	frame->stage_cycles[PICOSYSTEM_DISPLAY_PROFILE_STAGE_PRESENT] =
		k_cycle_get_32() - present_start;
	frame->stage_cycles[PICOSYSTEM_DISPLAY_PROFILE_STAGE_TOTAL] =
		k_cycle_get_32() - total_start;
	if (err != 0) {
		return err;
	}

	const uint32_t write_count = graphics->display_write_count - write_count_before;
	if (write_count > UINT16_MAX) {
		return -EOVERFLOW;
	}
	frame->display_write_count = (uint16_t)write_count;
	return 0;
}

static void insertion_sort(uint32_t *values, uint32_t count)
{
	for (uint32_t index = 1U; index < count; ++index) {
		const uint32_t value = values[index];
		uint32_t position = index;
		while ((position > 0U) && (values[position - 1U] > value)) {
			values[position] = values[position - 1U];
			--position;
		}
		values[position] = value;
	}
}

static uint32_t percentile(const uint32_t *sorted_values, uint32_t count, uint32_t percent)
{
	const uint32_t rank = ((count * percent) + 99U) / 100U;
	return sorted_values[rank - 1U];
}

static void summarize_stage(const uint32_t *samples, uint32_t sample_count,
			    struct picosystem_display_profile_stage_summary *summary)
{
	uint32_t sorted[PICOSYSTEM_DISPLAY_PROFILE_MAX_SAMPLES];
	uint64_t total = 0U;
	for (uint32_t sample = 0U; sample < sample_count; ++sample) {
		sorted[sample] = samples[sample];
		total += samples[sample];
	}
	insertion_sort(sorted, sample_count);

	*summary = (struct picosystem_display_profile_stage_summary){
		.sample_count = sample_count,
		.mean_cycles = (uint32_t)(total / sample_count),
		.minimum_cycles = sorted[0],
		.percentile_50_cycles = percentile(sorted, sample_count, 50U),
		.percentile_95_cycles = percentile(sorted, sample_count, 95U),
		.percentile_99_cycles = percentile(sorted, sample_count, 99U),
		.maximum_cycles = sorted[sample_count - 1U],
	};
}

static uint32_t case_payload_bytes(const struct display_profile_case_spec *spec)
{
	const uint32_t pixel_count =
		(PICOSYSTEM_GRAPHICS_WIDTH * PICOSYSTEM_GRAPHICS_HEIGHT * spec->coverage_percent) /
		100U;
	return pixel_count * sizeof(picosystem_color_t);
}

static int run_case(size_t case_index, uint32_t measured_sample_count,
		    struct picosystem_graphics_stats *graphics,
		    struct picosystem_display_profile_case_result *result,
		    struct picosystem_display_profile_stage_summary *dense_stages)
{
	const struct display_profile_case_spec *const spec = &case_specs[case_index];
	memset(&workspace, 0, sizeof(workspace));
	memset(result, 0, sizeof(*result));
	result->coverage_percent = spec->coverage_percent;
	result->payload_bytes = case_payload_bytes(spec);

	const uint32_t total_samples =
		PICOSYSTEM_DISPLAY_PROFILE_WARMUP_SAMPLES + measured_sample_count;
	for (uint32_t sample = 0U; sample < total_samples; ++sample) {
		struct display_profile_frame_result frame = {0};
		const int err = run_frame(spec, case_index, sample, graphics, &frame);
		if (err != 0) {
			return err;
		}
		if (sample < PICOSYSTEM_DISPLAY_PROFILE_WARMUP_SAMPLES) {
			continue;
		}

		const uint32_t measured_index = sample - PICOSYSTEM_DISPLAY_PROFILE_WARMUP_SAMPLES;
		for (size_t stage = 0U; stage < PICOSYSTEM_DISPLAY_PROFILE_STAGE_COUNT; ++stage) {
			workspace.stage_samples[stage][measured_index] = frame.stage_cycles[stage];
		}
		if (spec->layout == DISPLAY_PROFILE_LAYOUT_DENSE_FULL) {
			for (size_t stage = 0U;
			     stage < PICOSYSTEM_DISPLAY_PROFILE_DENSE_STAGE_COUNT; ++stage) {
				workspace.dense_stage_samples[stage][measured_index] =
					frame.dense_stage_cycles[stage];
			}
		}
		if (frame.synchronized) {
			++result->synchronized_wait_count;
		}
		if (measured_index == 0U) {
			result->region_count = frame.region_count;
			result->display_write_count = frame.display_write_count;
		} else if ((result->region_count != frame.region_count) ||
			   (result->display_write_count != frame.display_write_count)) {
			return -EIO;
		}
	}

	for (size_t stage = 0U; stage < PICOSYSTEM_DISPLAY_PROFILE_STAGE_COUNT; ++stage) {
		summarize_stage(workspace.stage_samples[stage], measured_sample_count,
				&result->stages[stage]);
	}
	if (spec->layout == DISPLAY_PROFILE_LAYOUT_DENSE_FULL) {
		for (size_t stage = 0U; stage < PICOSYSTEM_DISPLAY_PROFILE_DENSE_STAGE_COUNT;
		     ++stage) {
			summarize_stage(workspace.dense_stage_samples[stage], measured_sample_count,
					&dense_stages[stage]);
		}
	}
	return picosystem_graphics_framebuffer_crc32(&result->framebuffer_crc32);
}

int picosystem_display_profile_run(struct picosystem_graphics_stats *graphics,
				   uint32_t measured_sample_count,
				   struct picosystem_display_profile_result *result)
{
	if ((graphics == NULL) || (result == NULL)) {
		return -EINVAL;
	}
	if ((measured_sample_count == 0U) ||
	    (measured_sample_count > PICOSYSTEM_DISPLAY_PROFILE_MAX_SAMPLES)) {
		return -ERANGE;
	}
	if (!graphics->ready) {
		return -EAGAIN;
	}

	const int lock_err = k_mutex_lock(&display_profile_mutex, K_FOREVER);
	if (lock_err != 0) {
		return lock_err;
	}

	memset(result, 0, sizeof(*result));
	result->schema_version = PICOSYSTEM_DISPLAY_PROFILE_SCHEMA_VERSION;
	result->measured_sample_count = measured_sample_count;
	result->warmup_sample_count = PICOSYSTEM_DISPLAY_PROFILE_WARMUP_SAMPLES;
	result->clock_frequency_hz = CONFIG_SYS_CLOCK_HW_CYCLES_PER_SEC;
	result->configured_spi_frequency_hz = graphics->configured_spi_frequency_hz;
	result->width = PICOSYSTEM_GRAPHICS_WIDTH;
	result->height = PICOSYSTEM_GRAPHICS_HEIGHT;
	result->bytes_per_pixel = sizeof(picosystem_color_t);
	result->transport = graphics->transport;

	int err = 0;
	for (size_t case_index = 0U; case_index < ARRAY_SIZE(case_specs); ++case_index) {
		err = run_case(case_index, measured_sample_count, graphics,
			       &result->cases[case_index], result->dense_stages);
		if (err != 0) {
			break;
		}
	}

	k_mutex_unlock(&display_profile_mutex);
	return err;
}
