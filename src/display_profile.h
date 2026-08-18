/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_DISPLAY_PROFILE_H_
#define PICOSYSTEM_DISPLAY_PROFILE_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "graphics.h"

#define PICOSYSTEM_DISPLAY_PROFILE_SCHEMA_VERSION  1U
#define PICOSYSTEM_DISPLAY_PROFILE_DEFAULT_SAMPLES 16U
#define PICOSYSTEM_DISPLAY_PROFILE_MAX_SAMPLES     64U
#define PICOSYSTEM_DISPLAY_PROFILE_WARMUP_SAMPLES  2U
#define PICOSYSTEM_DISPLAY_PROFILE_CASE_COUNT      11U

enum picosystem_display_profile_stage {
	PICOSYSTEM_DISPLAY_PROFILE_STAGE_DRAW,
	PICOSYSTEM_DISPLAY_PROFILE_STAGE_TE_WAIT,
	PICOSYSTEM_DISPLAY_PROFILE_STAGE_PRESENT,
	PICOSYSTEM_DISPLAY_PROFILE_STAGE_TOTAL,
	PICOSYSTEM_DISPLAY_PROFILE_STAGE_COUNT,
};

struct picosystem_display_profile_stage_summary {
	uint32_t sample_count;
	uint32_t mean_cycles;
	uint32_t minimum_cycles;
	uint32_t percentile_50_cycles;
	uint32_t percentile_95_cycles;
	uint32_t percentile_99_cycles;
	uint32_t maximum_cycles;
};

struct picosystem_display_profile_case_result {
	struct picosystem_display_profile_stage_summary
		stages[PICOSYSTEM_DISPLAY_PROFILE_STAGE_COUNT];
	uint32_t payload_bytes;
	uint16_t region_count;
	uint16_t display_write_count;
	uint16_t synchronized_wait_count;
	uint8_t coverage_percent;
};

struct picosystem_display_profile_result {
	struct picosystem_display_profile_case_result cases[PICOSYSTEM_DISPLAY_PROFILE_CASE_COUNT];
	uint32_t schema_version;
	uint32_t measured_sample_count;
	uint32_t warmup_sample_count;
	uint32_t clock_frequency_hz;
	uint32_t configured_spi_frequency_hz;
	uint32_t original_framebuffer_crc32;
	uint32_t restored_framebuffer_crc32;
	uint16_t width;
	uint16_t height;
	uint8_t bytes_per_pixel;
	uint8_t transport;
	bool framebuffer_restored;
};

/* Run destructive display workloads. The caller owns the framebuffer and display exclusively. */
int picosystem_display_profile_run(struct picosystem_graphics_stats *graphics,
				   uint32_t measured_sample_count,
				   struct picosystem_display_profile_result *result);

const char *picosystem_display_profile_case_name(size_t case_index);
const char *picosystem_display_profile_stage_name(size_t stage_index);

#endif /* PICOSYSTEM_DISPLAY_PROFILE_H_ */
