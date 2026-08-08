/*
 * Copyright (c) 2026 PicoSystem Playground contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_BATTERY_H
#define PICOSYSTEM_BATTERY_H

#include <stdbool.h>
#include <stdint.h>

struct picosystem_battery_sample {
	/* Divider-corrected battery voltage. */
	uint16_t millivolts;
	/* Mean 12-bit ADC code before voltage conversion. */
	uint16_t raw_average;
	/* True when the result is within a broad single-cell LiPo sanity range. */
	bool plausible;
};

/* Configure the battery voltage ADC channel. */
int picosystem_battery_init(void);

/* Read and average a bounded batch of battery voltage samples. */
int picosystem_battery_read(struct picosystem_battery_sample *sample);

#endif /* PICOSYSTEM_BATTERY_H */
