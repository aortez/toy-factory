/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_FIXED_RATE_SCHEDULER_H_
#define PICOSYSTEM_FIXED_RATE_SCHEDULER_H_

#include <stdint.h>

struct picosystem_fixed_rate_scheduler {
	int64_t next_deadline_ticks;
	uint32_t phase;
	uint32_t ticks_per_second;
	uint32_t rate_hz;
};

/* Start with the first exact rational deadline after start_ticks. */
int picosystem_fixed_rate_scheduler_init(struct picosystem_fixed_rate_scheduler *scheduler,
					 int64_t start_ticks, uint32_t ticks_per_second,
					 uint32_t rate_hz);

/* Consume or discard a bounded number of scheduled deadlines. */
void picosystem_fixed_rate_scheduler_advance(struct picosystem_fixed_rate_scheduler *scheduler,
					     uint32_t steps);

/* Return the number of deadlines at or before now_ticks, saturating at UINT32_MAX. */
uint32_t
picosystem_fixed_rate_scheduler_due(const struct picosystem_fixed_rate_scheduler *scheduler,
				    int64_t now_ticks);

#endif /* PICOSYSTEM_FIXED_RATE_SCHEDULER_H_ */
