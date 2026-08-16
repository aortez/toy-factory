/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "battery.h"

#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stdint.h>

#include <zephyr/drivers/adc.h>
#include <zephyr/drivers/adc/voltage_divider.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/util.h>

LOG_MODULE_REGISTER(picosystem_battery, LOG_LEVEL_INF);

#define BATTERY_SAMPLE_COUNT     16U
#define BATTERY_PLAUSIBLE_MIN_MV 2500U
#define BATTERY_PLAUSIBLE_MAX_MV 4300U

static const struct voltage_divider_dt_spec battery_voltage =
	VOLTAGE_DIVIDER_DT_SPEC_GET(DT_NODELABEL(battery_voltage));
static bool battery_initialized;

BUILD_ASSERT(BATTERY_SAMPLE_COUNT > 0U);
BUILD_ASSERT((BATTERY_SAMPLE_COUNT * BIT(12)) <= UINT32_MAX);

int picosystem_battery_init(void)
{
	if (!adc_is_ready_dt(&battery_voltage.port)) {
		LOG_ERR("Battery ADC controller is not ready");
		return -ENODEV;
	}

	const int err = adc_channel_setup_dt(&battery_voltage.port);
	if (err != 0) {
		LOG_ERR("Failed to configure battery ADC channel (%d)", err);
		return err;
	}

	battery_initialized = true;
	return 0;
}

int picosystem_battery_read(struct picosystem_battery_sample *sample)
{
	if (sample == NULL) {
		return -EINVAL;
	}

	if (!battery_initialized) {
		return -EACCES;
	}

	uint16_t raw_samples[BATTERY_SAMPLE_COUNT];
	const struct adc_sequence_options options = {
		.extra_samplings = BATTERY_SAMPLE_COUNT - 1U,
		.interval_us = 0U,
	};
	struct adc_sequence sequence = {
		.options = &options,
		.buffer = raw_samples,
		.buffer_size = sizeof(raw_samples),
	};

	int err = adc_sequence_init_dt(&battery_voltage.port, &sequence);
	if (err != 0) {
		LOG_ERR("Failed to initialize battery ADC sequence (%d)", err);
		return err;
	}

	err = adc_read_dt(&battery_voltage.port, &sequence);
	if (err != 0) {
		LOG_ERR("Failed to read battery ADC samples (%d)", err);
		return err;
	}

	uint32_t raw_sum = 0U;
	for (size_t i = 0U; i < ARRAY_SIZE(raw_samples); ++i) {
		raw_sum += raw_samples[i];
	}

	const uint16_t raw_average = DIV_ROUND_CLOSEST(raw_sum, BATTERY_SAMPLE_COUNT);
	int32_t sense_microvolts = raw_average;

	err = adc_raw_to_microvolts_dt(&battery_voltage.port, &sense_microvolts);
	if (err != 0) {
		LOG_ERR("Failed to convert battery ADC reading (%d)", err);
		return err;
	}

	int64_t battery_microvolts = sense_microvolts;
	err = voltage_divider_scale64_dt(&battery_voltage, &battery_microvolts);
	if (err != 0) {
		LOG_ERR("Failed to scale battery divider voltage (%d)", err);
		return err;
	}

	if ((battery_microvolts < 0) || (battery_microvolts > ((int64_t)UINT16_MAX * 1000))) {
		LOG_ERR("Converted battery voltage is out of range (%lld uV)", battery_microvolts);
		return -ERANGE;
	}

	const uint16_t millivolts = (uint16_t)((battery_microvolts + 500) / 1000);

	const struct picosystem_battery_sample next_sample = {
		.millivolts = millivolts,
		.raw_average = raw_average,
		.plausible = (millivolts >= BATTERY_PLAUSIBLE_MIN_MV) &&
			     (millivolts <= BATTERY_PLAUSIBLE_MAX_MV),
	};

	*sample = next_sample;
	return 0;
}
