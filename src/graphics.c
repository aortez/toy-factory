/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "graphics.h"

#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <zephyr/device.h>
#include <zephyr/drivers/display.h>
#include <zephyr/drivers/pwm.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/sys/util.h>

#if defined(CONFIG_TOY_FACTORY_DISPLAY_DMA_HIGH_PRIORITY)
#include <hardware/regs/busctrl.h>
#include <hardware/structs/busctrl.h>
#include <hardware/sync.h>
#endif

#include "graphics_raster.h"

LOG_MODULE_REGISTER(picosystem_graphics, LOG_LEVEL_INF);

#define PICOSYSTEM_DISPLAY_NODE   DT_CHOSEN(zephyr_display)
#define PICOSYSTEM_BACKLIGHT_NODE DT_NODELABEL(lcd_backlight)

#define DISPLAY_WIDTH          DT_PROP(PICOSYSTEM_DISPLAY_NODE, width)
#define DISPLAY_HEIGHT         DT_PROP(PICOSYSTEM_DISPLAY_NODE, height)
#define DISPLAY_SPI_HZ         DT_PROP(PICOSYSTEM_DISPLAY_NODE, mipi_max_frequency)
#define BACKLIGHT_DUTY_PERCENT 25U
#define TRANSFER_BUFFER_ROWS   8U
#define TRANSFER_BUFFER_PIXELS (DISPLAY_WIDTH * TRANSFER_BUFFER_ROWS)

static const struct device *const display = DEVICE_DT_GET(PICOSYSTEM_DISPLAY_NODE);
static const struct pwm_dt_spec backlight = PWM_DT_SPEC_GET(PICOSYSTEM_BACKLIGHT_NODE);

static uint16_t transfer_buffer[TRANSFER_BUFFER_PIXELS] __aligned(4);
static bool graphics_initialized;

#if defined(CONFIG_SPI_RPI_PICO_PIO_DMA)
#define DISPLAY_TRANSPORT PICOSYSTEM_GRAPHICS_TRANSPORT_PIO_DMA
#elif defined(CONFIG_SPI_RPI_PICO_PIO)
#define DISPLAY_TRANSPORT PICOSYSTEM_GRAPHICS_TRANSPORT_PIO_POLLING
#elif defined(CONFIG_SPI_PL022_DMA)
#define DISPLAY_TRANSPORT PICOSYSTEM_GRAPHICS_TRANSPORT_PL022_DMA
#else
#define DISPLAY_TRANSPORT PICOSYSTEM_GRAPHICS_TRANSPORT_PL022
#endif

BUILD_ASSERT(DISPLAY_WIDTH == PICOSYSTEM_GRAPHICS_WIDTH);
BUILD_ASSERT(DISPLAY_HEIGHT == PICOSYSTEM_GRAPHICS_HEIGHT);
BUILD_ASSERT((DISPLAY_HEIGHT % TRANSFER_BUFFER_ROWS) == 0U);
BUILD_ASSERT(sizeof(transfer_buffer) <= UINT32_MAX);

static int set_backlight_percent(uint32_t percent)
{
	if (percent > 100U) {
		return -EINVAL;
	}

	const uint32_t pulse = (uint32_t)(((uint64_t)backlight.period * percent) / 100U);

	return pwm_set_pulse_dt(&backlight, pulse);
}

static bool region_is_valid(const struct picosystem_rect *region)
{
	if ((region == NULL) || (region->width == 0U) || (region->height == 0U)) {
		return false;
	}

	return (region->x < DISPLAY_WIDTH) && (region->y < DISPLAY_HEIGHT) &&
	       (region->width <= (DISPLAY_WIDTH - region->x)) &&
	       (region->height <= (DISPLAY_HEIGHT - region->y));
}

static uint32_t throughput_kib_per_second(size_t byte_count, uint32_t elapsed_us)
{
	return (uint32_t)(((uint64_t)byte_count * USEC_PER_SEC) /
			  ((uint64_t)MAX(elapsed_us, 1U) * 1024U));
}

static void increment_saturated(uint32_t *value)
{
	if (*value < UINT32_MAX) {
		++*value;
	}
}

static void record_present_stats(struct picosystem_graphics_stats *stats, uint16_t width,
				 uint16_t height, size_t byte_count, uint16_t write_count,
				 uint32_t start_cycles)
{
	const uint32_t elapsed_cycles = k_cycle_get_32() - start_cycles;
	const uint32_t elapsed_us = MAX(k_cyc_to_us_floor32(elapsed_cycles), 1U);

	stats->last_present_time_us = elapsed_us;
	stats->last_present_throughput_kib_per_second =
		throughput_kib_per_second(byte_count, elapsed_us);
	stats->last_present_byte_count = (uint32_t)byte_count;
	stats->last_present_width = width;
	stats->last_present_height = height;
	stats->last_present_write_count = write_count;
	increment_saturated(&stats->present_count);

	if ((width == DISPLAY_WIDTH) && (height == DISPLAY_HEIGHT)) {
		stats->full_present_time_us = elapsed_us;
		stats->full_present_throughput_kib_per_second =
			throughput_kib_per_second(byte_count, elapsed_us);
		increment_saturated(&stats->full_present_count);
	}
}

static int present_contiguous_region(struct picosystem_graphics_stats *stats,
				     const struct picosystem_rect *region)
{
	if ((region->x != 0U) || (region->width != DISPLAY_WIDTH)) {
		return -EINVAL;
	}

	const size_t pixel_offset = (size_t)region->y * DISPLAY_WIDTH;
	const size_t pixel_count = (size_t)region->width * region->height;
	const uint16_t *const pixels = picosystem_graphics_raster_pixels();
	const size_t byte_count = pixel_count * sizeof(pixels[0]);
	const struct display_buffer_descriptor descriptor = {
		.buf_size = byte_count,
		.width = region->width,
		.height = region->height,
		.pitch = region->width,
		.frame_incomplete = false,
	};
	stats->last_present_start_uptime_ticks = k_uptime_ticks();
	const uint32_t start_cycles = k_cycle_get_32();

	const int err =
		display_write(display, region->x, region->y, &descriptor, &pixels[pixel_offset]);
	if (err != 0) {
		LOG_ERR("Contiguous display write failed for %ux%u at (%u,%u) (%d)", region->width,
			region->height, region->x, region->y, err);
		return err;
	}
	increment_saturated(&stats->display_write_count);
	record_present_stats(stats, region->width, region->height, byte_count, 1U, start_cycles);
	return 0;
}

int picosystem_graphics_init(struct picosystem_graphics_stats *stats)
{
	if (stats == NULL) {
		return -EINVAL;
	}

	*stats = (struct picosystem_graphics_stats){
		.framebuffer_bytes = (uint32_t)picosystem_graphics_raster_byte_count(),
		.transfer_buffer_bytes = sizeof(transfer_buffer),
		.configured_spi_frequency_hz = DISPLAY_SPI_HZ,
		.transport = DISPLAY_TRANSPORT,
	};
	graphics_initialized = false;

#if defined(CONFIG_TOY_FACTORY_DISPLAY_DMA_HIGH_PRIORITY)
	hw_set_bits(&busctrl_hw->priority,
		    BUSCTRL_BUS_PRIORITY_DMA_R_BITS | BUSCTRL_BUS_PRIORITY_DMA_W_BITS);
#endif

	if (!pwm_is_ready_dt(&backlight)) {
		LOG_ERR("Backlight PWM controller is not ready");
		return -ENODEV;
	}

	int err = set_backlight_percent(0U);
	if (err != 0) {
		LOG_ERR("Failed to force the backlight off (%d)", err);
		return err;
	}

	if (!device_is_ready(display)) {
		LOG_ERR("Display device is not ready");
		return -ENODEV;
	}

	struct display_capabilities capabilities;
	display_get_capabilities(display, &capabilities);

	if ((capabilities.x_resolution != DISPLAY_WIDTH) ||
	    (capabilities.y_resolution != DISPLAY_HEIGHT)) {
		LOG_ERR("Unexpected display resolution: %ux%u", capabilities.x_resolution,
			capabilities.y_resolution);
		return -ENOTSUP;
	}

	if (capabilities.current_pixel_format != PIXEL_FORMAT_RGB_565X) {
		LOG_ERR("Unexpected display pixel format: 0x%x", capabilities.current_pixel_format);
		return -ENOTSUP;
	}

	err = display_set_pixel_format(display, PIXEL_FORMAT_RGB_565X);
	if (err != 0) {
		LOG_ERR("Failed to select RGB565X pixel format (%d)", err);
		return err;
	}

	err = display_blanking_on(display);
	if (err != 0) {
		LOG_ERR("Failed to blank display output (%d)", err);
		return err;
	}

	graphics_initialized = true;
	LOG_INF("Framebuffer ready: %u bytes plus %u-byte transfer buffer, %s at %u Hz",
		stats->framebuffer_bytes, stats->transfer_buffer_bytes,
		picosystem_graphics_transport_name(stats->transport), DISPLAY_SPI_HZ);
	return 0;
}

int picosystem_graphics_enable_output(struct picosystem_graphics_stats *stats)
{
	if ((stats == NULL) || !graphics_initialized) {
		return -EINVAL;
	}

	int err = display_blanking_off(display);
	if (err != 0) {
		LOG_ERR("Failed to enable display output (%d)", err);
		return err;
	}

	err = set_backlight_percent(BACKLIGHT_DUTY_PERCENT);
	if (err != 0) {
		LOG_ERR("Failed to enable the backlight (%d)", err);
		const int blank_err = display_blanking_on(display);
		if (blank_err != 0) {
			LOG_ERR("Failed to re-blank display after backlight error (%d)", blank_err);
		}
		return err;
	}

	stats->ready = true;
	return 0;
}

int picosystem_graphics_present_region(struct picosystem_graphics_stats *stats,
				       const struct picosystem_rect *region)
{
	if ((stats == NULL) || !graphics_initialized || !region_is_valid(region)) {
		return -EINVAL;
	}

	/* A full-width row range is contiguous in the framebuffer; copying would only add work. */
	if ((region->x == 0U) && (region->width == DISPLAY_WIDTH)) {
		return present_contiguous_region(stats, region);
	}

	const uint16_t rows_per_write = TRANSFER_BUFFER_PIXELS / region->width;
	uint16_t write_count = 0U;
	stats->last_present_start_uptime_ticks = k_uptime_ticks();
	const uint32_t start_cycles = k_cycle_get_32();

	for (uint16_t row_offset = 0U; row_offset < region->height;) {
		const uint16_t write_rows = MIN(rows_per_write, region->height - row_offset);

		for (uint16_t row = 0U; row < write_rows; ++row) {
			const uint16_t *const pixels = picosystem_graphics_raster_pixels();
			const size_t source_index =
				((size_t)(region->y + row_offset + row) * DISPLAY_WIDTH) +
				region->x;
			const size_t destination_index = (size_t)row * region->width;

			memcpy(&transfer_buffer[destination_index], &pixels[source_index],
			       (size_t)region->width * sizeof(pixels[0]));
		}

		const size_t pixel_count = (size_t)region->width * write_rows;
		const struct display_buffer_descriptor descriptor = {
			.buf_size = pixel_count * sizeof(transfer_buffer[0]),
			.width = region->width,
			.height = write_rows,
			.pitch = region->width,
			.frame_incomplete = ((row_offset + write_rows) < region->height),
		};

		const int err = display_write(display, region->x, region->y + row_offset,
					      &descriptor, transfer_buffer);
		if (err != 0) {
			LOG_ERR("Display write failed for %ux%u at (%u,%u) (%d)", region->width,
				region->height, region->x, region->y, err);
			return err;
		}
		increment_saturated(&stats->display_write_count);
		++write_count;

		row_offset += write_rows;
	}

	const size_t byte_count = (size_t)region->width * region->height * sizeof(uint16_t);

	record_present_stats(stats, region->width, region->height, byte_count, write_count,
			     start_cycles);
	return 0;
}

int picosystem_graphics_present_full(struct picosystem_graphics_stats *stats)
{
	if ((stats == NULL) || !graphics_initialized) {
		return -EINVAL;
	}

	const struct picosystem_rect full_region = {
		.x = 0U,
		.y = 0U,
		.width = DISPLAY_WIDTH,
		.height = DISPLAY_HEIGHT,
	};

	return present_contiguous_region(stats, &full_region);
}

const char *picosystem_graphics_transport_name(uint8_t transport)
{
	switch (transport) {
	case PICOSYSTEM_GRAPHICS_TRANSPORT_PL022:
		return "pl022";
	case PICOSYSTEM_GRAPHICS_TRANSPORT_PL022_DMA:
		return "pl022-dma";
	case PICOSYSTEM_GRAPHICS_TRANSPORT_PIO_POLLING:
		return "pio-polling";
	case PICOSYSTEM_GRAPHICS_TRANSPORT_PIO_DMA:
		return "pio-dma";
	default:
		return "unknown";
	}
}

int picosystem_graphics_visit_framebuffer(size_t chunk_bytes,
					  picosystem_graphics_framebuffer_visitor visitor,
					  void *context)
{
	if (!graphics_initialized || (chunk_bytes == 0U) || (visitor == NULL)) {
		return -EINVAL;
	}

	const uint8_t *const bytes = picosystem_graphics_raster_bytes();
	const size_t byte_count = picosystem_graphics_raster_byte_count();
	for (size_t offset = 0U; offset < byte_count; offset += chunk_bytes) {
		const size_t length = MIN(chunk_bytes, byte_count - offset);
		const int err = visitor(offset, &bytes[offset], length, context);
		if (err != 0) {
			return err;
		}
	}

	return 0;
}

int picosystem_graphics_framebuffer_crc32(uint32_t *crc)
{
	if (!graphics_initialized || (crc == NULL)) {
		return -EINVAL;
	}

	*crc = picosystem_graphics_raster_crc32();
	return 0;
}
