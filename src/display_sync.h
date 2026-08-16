/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_DISPLAY_SYNC_H_
#define PICOSYSTEM_DISPLAY_SYNC_H_

#include <stdbool.h>
#include <stdint.h>

struct picosystem_display_sync_stats {
	uint32_t rising_edges;
	uint32_t falling_edges;
	uint32_t gpio_read_errors;
	uint32_t last_edge_age_us;
	uint32_t period_samples;
	uint32_t period_mean_us;
	uint32_t period_min_us;
	uint32_t period_max_us;
	uint32_t high_samples;
	uint32_t high_mean_us;
	uint32_t high_min_us;
	uint32_t high_max_us;
	uint32_t low_samples;
	uint32_t low_mean_us;
	uint32_t low_min_us;
	uint32_t low_max_us;
	uint32_t synchronized_presents;
	uint32_t bypassed_presents;
	uint32_t timed_out_presents;
	uint32_t last_wait_us;
	uint32_t max_wait_us;
	bool panel_te_enabled;
	bool signal_high;
	bool signal_qualified;
	bool synchronization_requested;
};

/* Enable the panel's vertical-blank TE output and measure both GP8 edges. */
int picosystem_display_sync_init(void);

/* Copy a coherent snapshot of the interrupt-owned TE timing metrics. */
int picosystem_display_sync_get_stats(struct picosystem_display_sync_stats *stats);

/* Enable or disable bounded TE synchronization for subsequent partial presents. */
int picosystem_display_sync_set_enabled(bool enabled);

/* Wait for a fresh vertical-blank edge, falling back safely when unavailable. */
bool picosystem_display_sync_wait_for_vblank(void);

#endif /* PICOSYSTEM_DISPLAY_SYNC_H_ */
