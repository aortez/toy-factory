/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "garden_damage.h"
#include "game_snapshot.h"
#include "graphics_raster.h"
#include "portable_util.h"
#include "simulator.h"

#define GARDEN_PROFILE_SCHEMA_VERSION                1U
#define GARDEN_PROFILE_DEFAULT_REPETITIONS           32U
#define GARDEN_PROFILE_MAX_REPETITIONS               128U
#define GARDEN_PROFILE_STEP_WINDOW_TICKS             300U
#define GARDEN_PROFILE_RENDER_SAMPLES_PER_REPETITION 16U
#define GARDEN_PROFILE_DELTA_FRAME_COUNT             60U
#define GARDEN_PROFILE_DELTA_CADENCE_COUNT           3U
#define GARDEN_PROFILE_TILE_PIXELS                   8U
#define GARDEN_PROFILE_TILE_COLUMNS                  (PICOSYSTEM_GRAPHICS_WIDTH / GARDEN_PROFILE_TILE_PIXELS)
#define GARDEN_PROFILE_TILE_ROWS                     (PICOSYSTEM_GRAPHICS_HEIGHT / GARDEN_PROFILE_TILE_PIXELS)
#define GARDEN_PROFILE_MAX_STEP_SAMPLES                                                            \
	(GARDEN_PROFILE_MAX_REPETITIONS * GARDEN_PROFILE_STEP_WINDOW_TICKS)
#define GARDEN_PROFILE_MAX_RENDER_SAMPLES                                                          \
	(GARDEN_PROFILE_MAX_REPETITIONS * GARDEN_PROFILE_RENDER_SAMPLES_PER_REPETITION)

struct garden_profile_checkpoint {
	const char *name;
	uint32_t tick;
	uint32_t expected_hash;
	uint32_t expected_framebuffer_crc32;
	bool apply_smoke_setup;
};

struct timing_samples {
	uint64_t *values;
	size_t capacity;
	size_t count;
};

struct timing_summary {
	uint64_t mean_ns;
	uint64_t minimum_ns;
	uint64_t p50_ns;
	uint64_t p95_ns;
	uint64_t maximum_ns;
	size_t sample_count;
};

struct count_summary {
	uint32_t mean;
	uint32_t minimum;
	uint32_t p50;
	uint32_t p95;
	uint32_t maximum;
};

struct garden_profile_delta_cadence {
	uint32_t presentation_hz;
	uint32_t ticks_per_frame;
	uint32_t zero_change_frame_count;
	uint32_t empty_damage_frame_count;
	uint32_t reconstruction_verified_frame_count;
	struct count_summary changed_pixels;
	struct count_summary changed_tiles;
	struct count_summary bounding_box_pixels;
	struct count_summary damage_tiles;
	struct count_summary damage_regions;
	struct count_summary damage_pixels;
	struct count_summary damage_pixel_writes;
	struct timing_summary damage_plan;
	struct timing_summary damage_raster;
};

struct garden_profile_result {
	const char *name;
	uint32_t tick;
	uint32_t state_hash;
	uint32_t framebuffer_crc32;
	uint32_t plant_count;
	uint32_t living_plant_count;
	uint32_t dead_plant_count;
	uint32_t node_count;
	uint32_t bloom_count;
	uint32_t death_count;
	uint32_t reclaimed_plant_count;
	uint32_t reclaimed_node_count;
	uint32_t seed_count;
	uint32_t seed_creation_count;
	uint32_t germination_count;
	uint32_t seed_expiration_count;
	uint32_t mutation_count;
	uint32_t maximum_generation;
	uint32_t moisture_total;
	struct timing_summary ordinary_step;
	struct timing_summary ecology_step;
	struct timing_summary snapshot;
	struct timing_summary raster;
	struct picosystem_graphics_raster_work raster_work;
	struct garden_profile_delta_cadence frame_deltas[GARDEN_PROFILE_DELTA_CADENCE_COUNT];
};

struct garden_profile_workspace {
	uint64_t ordinary_step[GARDEN_PROFILE_MAX_STEP_SAMPLES];
	uint64_t ecology_step[GARDEN_PROFILE_MAX_STEP_SAMPLES];
	uint64_t snapshot[GARDEN_PROFILE_MAX_RENDER_SAMPLES];
	uint64_t raster[GARDEN_PROFILE_MAX_RENDER_SAMPLES];
	uint16_t previous_frame[PICOSYSTEM_GRAPHICS_WIDTH * PICOSYSTEM_GRAPHICS_HEIGHT];
};

static struct garden_profile_workspace workspace;

static const struct garden_profile_checkpoint checkpoints[] = {
	{
		.name = "initial",
		.tick = 0U,
		.expected_hash = UINT32_C(0xedda4220),
		.expected_framebuffer_crc32 = UINT32_C(0xc515c869),
	},
	{
		.name = "growing",
		.tick = 930U,
		.expected_hash = UINT32_C(0x9b775c1a),
		.expected_framebuffer_crc32 = UINT32_C(0xc96704e4),
		.apply_smoke_setup = true,
	},
	{
		.name = "mature",
		.tick = 3771U,
		.expected_hash = UINT32_C(0xec860825),
		.expected_framebuffer_crc32 = UINT32_C(0xbf6ec1a6),
		.apply_smoke_setup = true,
	},
};

static const struct garden_profile_delta_cadence delta_cadences[] = {
	{.presentation_hz = 30U, .ticks_per_frame = 2U},
	{.presentation_hz = 10U, .ticks_per_frame = 6U},
	{.presentation_hz = 4U, .ticks_per_frame = 15U},
};

_Static_assert((PICOSYSTEM_GRAPHICS_WIDTH % GARDEN_PROFILE_TILE_PIXELS) == 0U,
	       "profile tiles must span the framebuffer width");
_Static_assert((PICOSYSTEM_GRAPHICS_HEIGHT % GARDEN_PROFILE_TILE_PIXELS) == 0U,
	       "profile tiles must span the framebuffer height");
_Static_assert(TOY_FACTORY_ARRAY_SIZE(delta_cadences) == GARDEN_PROFILE_DELTA_CADENCE_COUNT,
	       "delta result capacity must match the configured cadences");

static void print_usage(FILE *stream, const char *program)
{
	fprintf(stream, "Usage: %s [--repetitions COUNT]\n", program);
}

static int parse_repetitions(const char *text, uint32_t *repetitions)
{
	if ((text == NULL) || (repetitions == NULL) || (*text == '\0') || (*text == '-')) {
		return -EINVAL;
	}

	errno = 0;
	char *end = NULL;
	const unsigned long parsed = strtoul(text, &end, 10);
	if ((errno != 0) || (*end != '\0') || (parsed == 0UL) ||
	    (parsed > GARDEN_PROFILE_MAX_REPETITIONS)) {
		return -ERANGE;
	}

	*repetitions = (uint32_t)parsed;
	return 0;
}

static int parse_options(int argc, char **argv, uint32_t *repetitions)
{
	*repetitions = GARDEN_PROFILE_DEFAULT_REPETITIONS;
	for (int index = 1; index < argc; ++index) {
		const char *const option = argv[index];
		if (strcmp(option, "--help") == 0) {
			print_usage(stdout, argv[0]);
			return 1;
		}
		if (strcmp(option, "--repetitions") == 0) {
			if ((index + 1) >= argc) {
				fprintf(stderr, "%s requires another argument\n", option);
				return -EINVAL;
			}
			const int err = parse_repetitions(argv[++index], repetitions);
			if (err != 0) {
				fprintf(stderr, "invalid repetition count '%s'\n", argv[index]);
				return err;
			}
			continue;
		}

		fprintf(stderr, "unknown option '%s'\n", option);
		return -EINVAL;
	}
	return 0;
}

static int monotonic_time_ns(uint64_t *timestamp)
{
	struct timespec now;
	if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) {
		return errno != 0 ? -errno : -EIO;
	}
	if (now.tv_sec < 0) {
		return -EIO;
	}
	*timestamp = ((uint64_t)now.tv_sec * UINT64_C(1000000000)) + (uint64_t)now.tv_nsec;
	return 0;
}

static int timing_samples_add(struct timing_samples *samples, uint64_t elapsed_ns)
{
	if ((samples == NULL) || (samples->values == NULL)) {
		return -EINVAL;
	}
	if (samples->count >= samples->capacity) {
		return -ENOSPC;
	}
	samples->values[samples->count++] = elapsed_ns;
	return 0;
}

static int compare_u64(const void *left, const void *right)
{
	const uint64_t left_value = *(const uint64_t *)left;
	const uint64_t right_value = *(const uint64_t *)right;
	return (left_value > right_value) - (left_value < right_value);
}

static int summarize_timing(struct timing_samples *samples, struct timing_summary *summary)
{
	if ((samples == NULL) || (summary == NULL) || (samples->count == 0U)) {
		return -EINVAL;
	}

	qsort(samples->values, samples->count, sizeof(samples->values[0]), compare_u64);
	uint64_t total = 0U;
	for (size_t index = 0U; index < samples->count; ++index) {
		total += samples->values[index];
	}
	const size_t p50_index = ((samples->count * 50U) + 99U) / 100U - 1U;
	const size_t p95_index = ((samples->count * 95U) + 99U) / 100U - 1U;
	*summary = (struct timing_summary){
		.mean_ns = total / samples->count,
		.minimum_ns = samples->values[0],
		.p50_ns = samples->values[p50_index],
		.p95_ns = samples->values[p95_index],
		.maximum_ns = samples->values[samples->count - 1U],
		.sample_count = samples->count,
	};
	return 0;
}

static int profile_clock_overhead(uint32_t repetitions, struct timing_summary *summary)
{
	struct timing_samples samples = {
		.values = workspace.snapshot,
		.capacity = GARDEN_PROFILE_MAX_RENDER_SAMPLES,
	};
	const uint32_t sample_count = repetitions * GARDEN_PROFILE_RENDER_SAMPLES_PER_REPETITION;
	for (uint32_t sample = 0U; sample < sample_count; ++sample) {
		uint64_t start_ns;
		uint64_t end_ns;
		int err = monotonic_time_ns(&start_ns);
		if (err == 0) {
			err = monotonic_time_ns(&end_ns);
		}
		if (err == 0) {
			err = timing_samples_add(&samples, end_ns - start_ns);
		}
		if (err != 0) {
			return err;
		}
	}
	return summarize_timing(&samples, summary);
}

static int compare_u32(const void *left, const void *right)
{
	const uint32_t left_value = *(const uint32_t *)left;
	const uint32_t right_value = *(const uint32_t *)right;
	return (left_value > right_value) - (left_value < right_value);
}

static int summarize_counts(uint32_t *values, size_t count, struct count_summary *summary)
{
	if ((values == NULL) || (summary == NULL) || (count == 0U)) {
		return -EINVAL;
	}

	qsort(values, count, sizeof(values[0]), compare_u32);
	uint64_t total = 0U;
	for (size_t index = 0U; index < count; ++index) {
		total += values[index];
	}
	const size_t p50_index = ((count * 50U) + 99U) / 100U - 1U;
	const size_t p95_index = ((count * 95U) + 99U) / 100U - 1U;
	*summary = (struct count_summary){
		.mean = (uint32_t)(total / count),
		.minimum = values[0],
		.p50 = values[p50_index],
		.p95 = values[p95_index],
		.maximum = values[count - 1U],
	};
	return 0;
}

static int build_snapshot(const struct picosystem_game_world *world, uint32_t sequence,
			  struct picosystem_scene_snapshot *snapshot)
{
	return picosystem_game_snapshot_build(world, sequence, 0U, world->logic_tick_count,
					      snapshot);
}

static int render_garden_damage(const struct picosystem_scene_snapshot *snapshot,
				const struct picosystem_garden_damage_plan *plan,
				uint32_t *region_count, uint32_t *pixel_count,
				uint32_t *pixel_write_count)
{
	if ((snapshot == NULL) || (plan == NULL) || (region_count == NULL) ||
	    (pixel_count == NULL) || (pixel_write_count == NULL)) {
		return -EINVAL;
	}
	*region_count = 0U;
	*pixel_count = 0U;
	*pixel_write_count = 0U;

	struct picosystem_garden_damage_iterator iterator;
	int err = picosystem_garden_damage_iterator_init(&iterator);
	struct picosystem_graphics_raster_work work;
	picosystem_graphics_raster_work_begin();
	while (err == 0) {
		struct picosystem_rect region;
		const int next = picosystem_garden_damage_next_region(plan, &iterator, &region);
		if (next < 0) {
			err = next;
			break;
		}
		if (next == 0) {
			break;
		}
		err = picosystem_scene_render_region(snapshot, &region);
		if (err == 0) {
			++*region_count;
			*pixel_count += (uint32_t)region.width * region.height;
		}
	}

	const int work_err = picosystem_graphics_raster_work_end(&work);
	if (err == 0) {
		err = work_err;
	}
	if ((err == 0) && (work.pixel_write_count > UINT32_MAX)) {
		err = -ERANGE;
	}
	if (err == 0) {
		*pixel_write_count = (uint32_t)work.pixel_write_count;
	}
	return err;
}

static void measure_frame_delta(const uint16_t *previous, const uint16_t *current,
				uint32_t *changed_pixel_count, uint32_t *changed_tile_count,
				uint32_t *bounding_box_pixels)
{
	bool changed_tiles[GARDEN_PROFILE_TILE_COLUMNS * GARDEN_PROFILE_TILE_ROWS] = {false};
	uint32_t changed = 0U;
	uint32_t tile_count = 0U;
	uint32_t minimum_x = PICOSYSTEM_GRAPHICS_WIDTH;
	uint32_t minimum_y = PICOSYSTEM_GRAPHICS_HEIGHT;
	uint32_t maximum_x = 0U;
	uint32_t maximum_y = 0U;

	for (uint32_t y = 0U; y < PICOSYSTEM_GRAPHICS_HEIGHT; ++y) {
		for (uint32_t x = 0U; x < PICOSYSTEM_GRAPHICS_WIDTH; ++x) {
			const size_t pixel_index = ((size_t)y * PICOSYSTEM_GRAPHICS_WIDTH) + x;
			if (previous[pixel_index] == current[pixel_index]) {
				continue;
			}
			++changed;
			if (x < minimum_x) {
				minimum_x = x;
			}
			if (x > maximum_x) {
				maximum_x = x;
			}
			if (y < minimum_y) {
				minimum_y = y;
			}
			if (y > maximum_y) {
				maximum_y = y;
			}

			const size_t tile_index = ((size_t)(y / GARDEN_PROFILE_TILE_PIXELS) *
						   GARDEN_PROFILE_TILE_COLUMNS) +
						  (x / GARDEN_PROFILE_TILE_PIXELS);
			if (!changed_tiles[tile_index]) {
				changed_tiles[tile_index] = true;
				++tile_count;
			}
		}
	}

	*changed_pixel_count = changed;
	*changed_tile_count = tile_count;
	*bounding_box_pixels =
		(changed == 0U) ? 0U : (maximum_x - minimum_x + 1U) * (maximum_y - minimum_y + 1U);
}

static int profile_frame_deltas(const struct picosystem_game_world *baseline,
				struct garden_profile_delta_cadence *results)
{
	const struct picosystem_game_input neutral = {0};
	for (size_t cadence_index = 0U; cadence_index < TOY_FACTORY_ARRAY_SIZE(delta_cadences);
	     ++cadence_index) {
		struct picosystem_game_world world = *baseline;
		uint32_t changed_pixels[GARDEN_PROFILE_DELTA_FRAME_COUNT];
		uint32_t changed_tiles[GARDEN_PROFILE_DELTA_FRAME_COUNT];
		uint32_t bounding_boxes[GARDEN_PROFILE_DELTA_FRAME_COUNT];
		uint32_t damage_tiles[GARDEN_PROFILE_DELTA_FRAME_COUNT];
		uint32_t damage_regions[GARDEN_PROFILE_DELTA_FRAME_COUNT];
		uint32_t damage_pixels[GARDEN_PROFILE_DELTA_FRAME_COUNT];
		uint32_t damage_pixel_writes[GARDEN_PROFILE_DELTA_FRAME_COUNT];
		uint64_t damage_plan_timing[GARDEN_PROFILE_DELTA_FRAME_COUNT];
		uint64_t damage_raster_timing[GARDEN_PROFILE_DELTA_FRAME_COUNT];
		struct garden_profile_delta_cadence *const result = &results[cadence_index];
		*result = delta_cadences[cadence_index];

		struct picosystem_scene_snapshot presented_snapshot;
		int err = build_snapshot(&world, 1U, &presented_snapshot);
		if (err == 0) {
			err = picosystem_scene_render_full(&presented_snapshot);
		}
		if (err != 0) {
			return err;
		}
		memcpy(workspace.previous_frame, picosystem_graphics_raster_pixels(),
		       sizeof(workspace.previous_frame));

		for (uint32_t frame = 0U; frame < GARDEN_PROFILE_DELTA_FRAME_COUNT; ++frame) {
			for (uint32_t tick = 0U; tick < result->ticks_per_frame; ++tick) {
				err = picosystem_game_world_step(&world, &neutral);
				if (err != 0) {
					return err;
				}
			}
			struct picosystem_scene_snapshot current_snapshot;
			err = build_snapshot(&world, frame + 2U, &current_snapshot);
			if (err != 0) {
				return err;
			}
			struct picosystem_garden_damage_plan damage_plan;
			uint64_t start_ns;
			uint64_t end_ns;
			err = monotonic_time_ns(&start_ns);
			if (err != 0) {
				return err;
			}
			err = picosystem_garden_damage_plan_build(&presented_snapshot,
								  &current_snapshot, &damage_plan);
			if (err != 0) {
				return err;
			}
			err = monotonic_time_ns(&end_ns);
			if (err != 0) {
				return err;
			}
			damage_plan_timing[frame] = end_ns - start_ns;
			damage_tiles[frame] = damage_plan.dirty_tile_count;
			if (damage_plan.dirty_tile_count == 0U) {
				++result->empty_damage_frame_count;
			}
			err = monotonic_time_ns(&start_ns);
			if (err == 0) {
				err = render_garden_damage(
					&current_snapshot, &damage_plan, &damage_regions[frame],
					&damage_pixels[frame], &damage_pixel_writes[frame]);
			}
			if (err == 0) {
				err = monotonic_time_ns(&end_ns);
			}
			if (err != 0) {
				return err;
			}
			damage_raster_timing[frame] = end_ns - start_ns;
			const uint32_t damage_crc32 = picosystem_graphics_raster_crc32();
			measure_frame_delta(workspace.previous_frame,
					    picosystem_graphics_raster_pixels(),
					    &changed_pixels[frame], &changed_tiles[frame],
					    &bounding_boxes[frame]);
			if (changed_pixels[frame] == 0U) {
				++result->zero_change_frame_count;
			}
			memcpy(workspace.previous_frame, picosystem_graphics_raster_pixels(),
			       sizeof(workspace.previous_frame));

			err = picosystem_scene_render_full(&current_snapshot);
			if (err != 0) {
				return err;
			}
			const uint32_t full_crc32 = picosystem_graphics_raster_crc32();
			if (memcmp(workspace.previous_frame, picosystem_graphics_raster_pixels(),
				   sizeof(workspace.previous_frame)) != 0) {
				uint32_t missed_pixels;
				uint32_t missed_tiles;
				uint32_t missed_bounds;
				uint32_t first_missed_x = 0U;
				uint32_t first_missed_y = 0U;
				uint16_t first_partial_pixel = 0U;
				uint16_t first_full_pixel = 0U;
				measure_frame_delta(workspace.previous_frame,
						    picosystem_graphics_raster_pixels(),
						    &missed_pixels, &missed_tiles, &missed_bounds);
				for (size_t pixel = 0U;
				     pixel < TOY_FACTORY_ARRAY_SIZE(workspace.previous_frame);
				     ++pixel) {
					if (workspace.previous_frame[pixel] !=
					    picosystem_graphics_raster_pixels()[pixel]) {
						first_missed_x =
							(uint32_t)(pixel %
								   PICOSYSTEM_GRAPHICS_WIDTH);
						first_missed_y =
							(uint32_t)(pixel /
								   PICOSYSTEM_GRAPHICS_WIDTH);
						first_partial_pixel =
							workspace.previous_frame[pixel];
						first_full_pixel =
							picosystem_graphics_raster_pixels()[pixel];
						break;
					}
				}
				fprintf(stderr,
					"damage mismatch: cadence=%" PRIu32 " frame=%" PRIu32
					" tick=%" PRIu32 " tiles=%u partial=%08" PRIx32
					" full=%08" PRIx32 " missed=%" PRIu32 "/%" PRIu32
					" bounds=%" PRIu32 " first=%" PRIu32 ",%" PRIu32
					" marked=%u pixels=%04x/%04x\n",
					result->presentation_hz, frame, world.logic_tick_count,
					damage_plan.dirty_tile_count, damage_crc32, full_crc32,
					missed_pixels, missed_tiles, missed_bounds, first_missed_x,
					first_missed_y,
					(damage_plan
						 .row_masks[first_missed_y /
							    PICOSYSTEM_GARDEN_DAMAGE_TILE_PIXELS] &
					 (UINT32_C(1) << (first_missed_x /
							  PICOSYSTEM_GARDEN_DAMAGE_TILE_PIXELS))) !=
						0U,
					first_partial_pixel, first_full_pixel);
				return -EILSEQ;
			}
			++result->reconstruction_verified_frame_count;
			presented_snapshot = current_snapshot;
		}

		err = summarize_counts(changed_pixels, TOY_FACTORY_ARRAY_SIZE(changed_pixels),
				       &result->changed_pixels);
		if (err == 0) {
			err = summarize_counts(changed_tiles, TOY_FACTORY_ARRAY_SIZE(changed_tiles),
					       &result->changed_tiles);
		}
		if (err == 0) {
			err = summarize_counts(bounding_boxes,
					       TOY_FACTORY_ARRAY_SIZE(bounding_boxes),
					       &result->bounding_box_pixels);
		}
		if (err == 0) {
			err = summarize_counts(damage_tiles, TOY_FACTORY_ARRAY_SIZE(damage_tiles),
					       &result->damage_tiles);
		}
		if (err == 0) {
			err = summarize_counts(damage_regions,
					       TOY_FACTORY_ARRAY_SIZE(damage_regions),
					       &result->damage_regions);
		}
		if (err == 0) {
			err = summarize_counts(damage_pixels, TOY_FACTORY_ARRAY_SIZE(damage_pixels),
					       &result->damage_pixels);
		}
		if (err == 0) {
			err = summarize_counts(damage_pixel_writes,
					       TOY_FACTORY_ARRAY_SIZE(damage_pixel_writes),
					       &result->damage_pixel_writes);
		}
		struct timing_samples damage_plan_samples = {
			.values = damage_plan_timing,
			.capacity = TOY_FACTORY_ARRAY_SIZE(damage_plan_timing),
			.count = TOY_FACTORY_ARRAY_SIZE(damage_plan_timing),
		};
		struct timing_samples damage_raster_samples = {
			.values = damage_raster_timing,
			.capacity = TOY_FACTORY_ARRAY_SIZE(damage_raster_timing),
			.count = TOY_FACTORY_ARRAY_SIZE(damage_raster_timing),
		};
		if (err == 0) {
			err = summarize_timing(&damage_plan_samples, &result->damage_plan);
		}
		if (err == 0) {
			err = summarize_timing(&damage_raster_samples, &result->damage_raster);
		}
		if (err != 0) {
			return err;
		}
	}
	return 0;
}

static int apply_garden_smoke_setup(struct toy_factory_simulator *simulator, uint32_t target_tick)
{
	if (target_tick < 30U) {
		return -ERANGE;
	}

	int err = toy_factory_simulator_apply_action(simulator,
						     PICOSYSTEM_GAME_SCENE_ACTION_USE_TOOL);
	if (err == 0) {
		err = toy_factory_simulator_apply_action(simulator,
							 PICOSYSTEM_GAME_SCENE_ACTION_CYCLE_TOOL);
	}
	if (err == 0) {
		err = toy_factory_simulator_apply_action(simulator,
							 PICOSYSTEM_GAME_SCENE_ACTION_CYCLE_TOOL);
	}
	const struct picosystem_game_input left = {.horizontal = -1};
	if (err == 0) {
		err = toy_factory_simulator_step(simulator, &left, 30U);
	}
	if (err == 0) {
		err = toy_factory_simulator_apply_action(simulator,
							 PICOSYSTEM_GAME_SCENE_ACTION_USE_TOOL);
	}
	if (err == 0) {
		err = toy_factory_simulator_apply_action(simulator,
							 PICOSYSTEM_GAME_SCENE_ACTION_PRIMARY);
	}
	const struct picosystem_game_input neutral = {0};
	if (err == 0) {
		err = toy_factory_simulator_step(simulator, &neutral, target_tick - 30U);
	}
	return err;
}

static int prepare_checkpoint(const struct garden_profile_checkpoint *checkpoint,
			      struct toy_factory_simulator *simulator)
{
	int err = toy_factory_simulator_init(simulator, PICOSYSTEM_GAME_SCENE_GARDEN);
	if ((err == 0) && checkpoint->apply_smoke_setup) {
		err = apply_garden_smoke_setup(simulator, checkpoint->tick);
	}
	if ((err == 0) && (simulator->world.logic_tick_count != checkpoint->tick)) {
		return -EILSEQ;
	}
	if ((err == 0) &&
	    (toy_factory_simulator_state_hash(simulator) != checkpoint->expected_hash)) {
		return -EILSEQ;
	}
	return err;
}

static int profile_model_steps(const struct picosystem_game_world *baseline, uint32_t repetitions,
			       struct timing_summary *ordinary_summary,
			       struct timing_summary *ecology_summary)
{
	struct timing_samples ordinary = {
		.values = workspace.ordinary_step,
		.capacity = GARDEN_PROFILE_MAX_STEP_SAMPLES,
	};
	struct timing_samples ecology = {
		.values = workspace.ecology_step,
		.capacity = GARDEN_PROFILE_MAX_STEP_SAMPLES,
	};
	const struct picosystem_game_input neutral = {0};

	for (uint32_t repetition = 0U; repetition < repetitions; ++repetition) {
		struct picosystem_game_world world = *baseline;
		for (uint32_t tick = 0U; tick < GARDEN_PROFILE_STEP_WINDOW_TICKS; ++tick) {
			const bool ecology_due = ((world.logic_tick_count + 1U) %
						  PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) == 0U;
			uint64_t start_ns;
			uint64_t end_ns;
			int err = monotonic_time_ns(&start_ns);
			if (err == 0) {
				err = picosystem_game_world_step(&world, &neutral);
			}
			if (err == 0) {
				err = monotonic_time_ns(&end_ns);
			}
			if (err == 0) {
				err = timing_samples_add(ecology_due ? &ecology : &ordinary,
							 end_ns - start_ns);
			}
			if (err != 0) {
				return err;
			}
		}
	}

	int err = summarize_timing(&ordinary, ordinary_summary);
	if (err == 0) {
		err = summarize_timing(&ecology, ecology_summary);
	}
	return err;
}

static int profile_snapshot_and_raster(const struct picosystem_game_world *world,
				       uint32_t repetitions, struct garden_profile_result *result)
{
	struct timing_samples snapshot_samples = {
		.values = workspace.snapshot,
		.capacity = GARDEN_PROFILE_MAX_RENDER_SAMPLES,
	};
	struct timing_samples raster_samples = {
		.values = workspace.raster,
		.capacity = GARDEN_PROFILE_MAX_RENDER_SAMPLES,
	};
	struct picosystem_scene_snapshot snapshot;
	const uint32_t sample_count = repetitions * GARDEN_PROFILE_RENDER_SAMPLES_PER_REPETITION;

	for (uint32_t sample = 0U; sample < sample_count; ++sample) {
		uint64_t start_ns;
		uint64_t end_ns;
		int err = monotonic_time_ns(&start_ns);
		if (err == 0) {
			err = picosystem_game_snapshot_build(world, sample + 1U, 0U,
							     world->logic_tick_count, &snapshot);
		}
		if (err == 0) {
			err = monotonic_time_ns(&end_ns);
		}
		if (err == 0) {
			err = timing_samples_add(&snapshot_samples, end_ns - start_ns);
		}
		if (err != 0) {
			return err;
		}
	}

	for (uint32_t sample = 0U; sample < sample_count; ++sample) {
		uint64_t start_ns;
		uint64_t end_ns;
		int err = monotonic_time_ns(&start_ns);
		if (err == 0) {
			err = picosystem_scene_render_full(&snapshot);
		}
		if (err == 0) {
			err = monotonic_time_ns(&end_ns);
		}
		if (err == 0) {
			err = timing_samples_add(&raster_samples, end_ns - start_ns);
		}
		if (err != 0) {
			return err;
		}
	}

	int err = summarize_timing(&snapshot_samples, &result->snapshot);
	if (err == 0) {
		err = summarize_timing(&raster_samples, &result->raster);
	}
	if (err != 0) {
		return err;
	}

	picosystem_graphics_raster_work_begin();
	err = picosystem_scene_render_full(&snapshot);
	if (err == 0) {
		err = picosystem_graphics_raster_work_end(&result->raster_work);
	} else {
		(void)picosystem_graphics_raster_work_end(&result->raster_work);
	}
	if (err == 0) {
		result->framebuffer_crc32 = picosystem_graphics_raster_crc32();
	}
	return err;
}

static int profile_checkpoint(const struct garden_profile_checkpoint *checkpoint,
			      uint32_t repetitions, struct garden_profile_result *result)
{
	struct toy_factory_simulator simulator;
	int err = prepare_checkpoint(checkpoint, &simulator);
	if (err != 0) {
		return err;
	}

	*result = (struct garden_profile_result){
		.name = checkpoint->name,
		.tick = simulator.world.logic_tick_count,
		.state_hash = toy_factory_simulator_state_hash(&simulator),
		.plant_count = simulator.world.garden.plant_count,
		.living_plant_count =
			picosystem_garden_world_living_plant_count(&simulator.world.garden),
		.dead_plant_count =
			picosystem_garden_world_dead_plant_count(&simulator.world.garden),
		.node_count = simulator.world.garden.node_count,
		.bloom_count = simulator.world.garden.bloom_count,
		.death_count = simulator.world.garden.death_count,
		.reclaimed_plant_count = simulator.world.garden.reclaimed_plant_count,
		.reclaimed_node_count = simulator.world.garden.reclaimed_node_count,
		.seed_count = simulator.world.garden.seed_count,
		.seed_creation_count = simulator.world.garden.seed_creation_count,
		.germination_count = simulator.world.garden.germination_count,
		.seed_expiration_count = simulator.world.garden.seed_expiration_count,
		.mutation_count = simulator.world.garden.mutation_count,
		.maximum_generation = simulator.world.garden.maximum_generation,
		.moisture_total = simulator.world.garden.moisture_total,
	};
	err = profile_model_steps(&simulator.world, repetitions, &result->ordinary_step,
				  &result->ecology_step);
	if (err == 0) {
		err = profile_snapshot_and_raster(&simulator.world, repetitions, result);
	}
	if (err == 0) {
		err = profile_frame_deltas(&simulator.world, result->frame_deltas);
	}
	if ((err == 0) && (result->framebuffer_crc32 != checkpoint->expected_framebuffer_crc32)) {
		return -EILSEQ;
	}
	return err;
}

static void print_timing_summary(const char *name, const struct timing_summary *summary,
				 bool trailing_comma)
{
	printf("      \"%s\": {\"samples\": %zu, \"mean\": %" PRIu64 ", \"min\": %" PRIu64
	       ", \"p50\": %" PRIu64 ", \"p95\": %" PRIu64 ", \"max\": %" PRIu64 "}%s\n",
	       name, summary->sample_count, summary->mean_ns, summary->minimum_ns, summary->p50_ns,
	       summary->p95_ns, summary->maximum_ns, trailing_comma ? "," : "");
}

static void print_count_summary(const char *name, const struct count_summary *summary,
				bool trailing_comma)
{
	printf("          \"%s\": {\"mean\": %" PRIu32 ", \"min\": %" PRIu32 ", \"p50\": %" PRIu32
	       ", \"p95\": %" PRIu32 ", \"max\": %" PRIu32 "}%s\n",
	       name, summary->mean, summary->minimum, summary->p50, summary->p95, summary->maximum,
	       trailing_comma ? "," : "");
}

static void print_damage_timing_summary(const char *name, const struct timing_summary *summary)
{
	printf("            \"%s\": {\"samples\": %zu, \"mean\": %" PRIu64 ", \"min\": %" PRIu64
	       ", \"p50\": %" PRIu64 ", \"p95\": %" PRIu64 ", \"max\": %" PRIu64 "},\n",
	       name, summary->sample_count, summary->mean_ns, summary->minimum_ns, summary->p50_ns,
	       summary->p95_ns, summary->maximum_ns);
}

static void print_frame_deltas(const struct garden_profile_result *result)
{
	printf("      \"frame_deltas\": [\n");
	for (size_t index = 0U; index < TOY_FACTORY_ARRAY_SIZE(result->frame_deltas); ++index) {
		const struct garden_profile_delta_cadence *const cadence =
			&result->frame_deltas[index];
		printf("        {\n");
		printf("          \"presentation_hz\": %" PRIu32 ",\n", cadence->presentation_hz);
		printf("          \"ticks_per_frame\": %" PRIu32 ",\n", cadence->ticks_per_frame);
		printf("          \"frames\": %u,\n", GARDEN_PROFILE_DELTA_FRAME_COUNT);
		printf("          \"zero_change_frames\": %" PRIu32 ",\n",
		       cadence->zero_change_frame_count);
		print_count_summary("changed_pixels", &cadence->changed_pixels, true);
		print_count_summary("changed_tiles_8x8", &cadence->changed_tiles, true);
		print_count_summary("bounding_box_pixels", &cadence->bounding_box_pixels, true);
		printf("          \"damage_reconstruction\": {\n");
		printf("            \"verified_frames\": %" PRIu32 ",\n",
		       cadence->reconstruction_verified_frame_count);
		printf("            \"empty_plan_frames\": %" PRIu32 ",\n",
		       cadence->empty_damage_frame_count);
		print_damage_timing_summary("plan_timing_ns", &cadence->damage_plan);
		print_damage_timing_summary("raster_timing_ns", &cadence->damage_raster);
		print_count_summary("tiles_8x8", &cadence->damage_tiles, true);
		print_count_summary("regions", &cadence->damage_regions, true);
		print_count_summary("transfer_pixels", &cadence->damage_pixels, true);
		print_count_summary("raster_pixel_writes", &cadence->damage_pixel_writes, false);
		printf("          }\n");
		printf("        }%s\n",
		       (index + 1U) < TOY_FACTORY_ARRAY_SIZE(result->frame_deltas) ? "," : "");
	}
	printf("      ]\n");
}

static void print_result(const struct garden_profile_result *result, bool trailing_comma)
{
	printf("    {\n");
	printf("      \"name\": \"%s\",\n", result->name);
	printf("      \"tick\": %" PRIu32 ",\n", result->tick);
	printf("      \"state_hash\": \"%08" PRIx32 "\",\n", result->state_hash);
	printf("      \"framebuffer_crc32\": \"%08" PRIx32 "\",\n", result->framebuffer_crc32);
	printf("      \"state\": {\"plants\": %" PRIu32 ", \"living\": %" PRIu32
	       ", \"dead\": %" PRIu32 ", \"nodes\": %" PRIu32 ", \"blooms\": %" PRIu32
	       ", \"deaths\": %" PRIu32 ", \"reclaimed_plants\": %" PRIu32
	       ", \"reclaimed_nodes\": %" PRIu32 ", \"seeds\": %" PRIu32
	       ", \"seeds_created\": %" PRIu32 ", \"germinations\": %" PRIu32
	       ", \"seeds_expired\": %" PRIu32 ", \"mutations\": %" PRIu32
	       ", \"max_generation\": %" PRIu32 ", \"moisture\": %" PRIu32 "},\n",
	       result->plant_count, result->living_plant_count, result->dead_plant_count,
	       result->node_count, result->bloom_count, result->death_count,
	       result->reclaimed_plant_count, result->reclaimed_node_count, result->seed_count,
	       result->seed_creation_count, result->germination_count,
	       result->seed_expiration_count, result->mutation_count, result->maximum_generation,
	       result->moisture_total);
	printf("      \"timing_ns\": {\n");
	print_timing_summary("ordinary_step", &result->ordinary_step, true);
	print_timing_summary("ecology_step", &result->ecology_step, true);
	print_timing_summary("snapshot", &result->snapshot, true);
	print_timing_summary("raster", &result->raster, false);
	printf("      },\n");
	printf("      \"raster_work\": {\"pixel_writes\": %" PRIu64 ", \"clear_calls\": %" PRIu32
	       ", \"draw_pixel_calls\": %" PRIu32 ", \"fill_rect_calls\": %" PRIu32
	       ", \"draw_rect_calls\": %" PRIu32 ", \"draw_line_calls\": %" PRIu32
	       ", \"fill_triangle_calls\": %" PRIu32 ", \"fill_circle_calls\": %" PRIu32
	       ", \"draw_mono_sprite_calls\": %" PRIu32 ", \"draw_text_calls\": %" PRIu32 "},\n",
	       result->raster_work.pixel_write_count, result->raster_work.clear_call_count,
	       result->raster_work.draw_pixel_call_count, result->raster_work.fill_rect_call_count,
	       result->raster_work.draw_rect_call_count, result->raster_work.draw_line_call_count,
	       result->raster_work.fill_triangle_call_count,
	       result->raster_work.fill_circle_call_count,
	       result->raster_work.draw_mono_sprite_call_count,
	       result->raster_work.draw_text_call_count);
	print_frame_deltas(result);
	printf("    }%s\n", trailing_comma ? "," : "");
}

int main(int argc, char **argv)
{
	uint32_t repetitions;
	int err = parse_options(argc, argv, &repetitions);
	if (err > 0) {
		return 0;
	}
	if (err < 0) {
		print_usage(stderr, argv[0]);
		return 2;
	}
	struct timing_summary clock_overhead;
	err = profile_clock_overhead(repetitions, &clock_overhead);
	if (err != 0) {
		fprintf(stderr, "could not profile clock overhead: %d\n", err);
		return 1;
	}

	struct garden_profile_result results[TOY_FACTORY_ARRAY_SIZE(checkpoints)];
	for (size_t index = 0U; index < TOY_FACTORY_ARRAY_SIZE(checkpoints); ++index) {
		err = profile_checkpoint(&checkpoints[index], repetitions, &results[index]);
		if (err != 0) {
			fprintf(stderr, "could not profile %s checkpoint: %d\n",
				checkpoints[index].name, err);
			return 1;
		}
	}

	printf("{\n");
	printf("  \"schema_version\": %u,\n", GARDEN_PROFILE_SCHEMA_VERSION);
	printf("  \"timing_unit\": \"nanoseconds\",\n");
	printf("  \"repetitions\": %" PRIu32 ",\n", repetitions);
	printf("  \"step_window_ticks\": %u,\n", GARDEN_PROFILE_STEP_WINDOW_TICKS);
	printf("  \"render_samples_per_checkpoint\": %" PRIu32 ",\n",
	       repetitions * GARDEN_PROFILE_RENDER_SAMPLES_PER_REPETITION);
	printf("  \"clock_overhead_ns\": {\"samples\": %zu, \"mean\": %" PRIu64
	       ", \"min\": %" PRIu64 ", \"p50\": %" PRIu64 ", \"p95\": %" PRIu64
	       ", \"max\": %" PRIu64 "},\n",
	       clock_overhead.sample_count, clock_overhead.mean_ns, clock_overhead.minimum_ns,
	       clock_overhead.p50_ns, clock_overhead.p95_ns, clock_overhead.maximum_ns);
	printf("  \"memory_bytes\": {\"garden_world\": %zu, \"game_world\": %zu, "
	       "\"snapshot\": %zu, \"framebuffer\": %zu},\n",
	       sizeof(struct picosystem_garden_world), sizeof(struct picosystem_game_world),
	       sizeof(struct picosystem_scene_snapshot), picosystem_graphics_raster_byte_count());
	printf("  \"scenarios\": [\n");
	for (size_t index = 0U; index < TOY_FACTORY_ARRAY_SIZE(results); ++index) {
		print_result(&results[index], (index + 1U) < TOY_FACTORY_ARRAY_SIZE(results));
	}
	printf("  ]\n");
	printf("}\n");
	return 0;
}
