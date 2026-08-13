/*
 * Copyright (c) 2026 PicoSystem Playground contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "fixed_rate_scheduler.h"

#include <errno.h>
#include <limits.h>
#include <stddef.h>
#include <stdint.h>

void picosystem_fixed_rate_scheduler_advance(struct picosystem_fixed_rate_scheduler *scheduler,
					     uint32_t steps)
{
	const uint64_t phase_total =
		(uint64_t)scheduler->phase + ((uint64_t)steps * scheduler->ticks_per_second);

	scheduler->next_deadline_ticks += (int64_t)(phase_total / scheduler->rate_hz);
	scheduler->phase = (uint32_t)(phase_total % scheduler->rate_hz);
}

int picosystem_fixed_rate_scheduler_init(struct picosystem_fixed_rate_scheduler *scheduler,
					 int64_t start_ticks, uint32_t ticks_per_second,
					 uint32_t rate_hz)
{
	if (scheduler == NULL) {
		return -EINVAL;
	}
	if ((rate_hz == 0U) || (ticks_per_second == 0U) || (rate_hz > ticks_per_second)) {
		return -ERANGE;
	}

	*scheduler = (struct picosystem_fixed_rate_scheduler){
		.next_deadline_ticks = start_ticks,
		.ticks_per_second = ticks_per_second,
		.rate_hz = rate_hz,
	};
	picosystem_fixed_rate_scheduler_advance(scheduler, 1U);
	return 0;
}

uint32_t
picosystem_fixed_rate_scheduler_due(const struct picosystem_fixed_rate_scheduler *scheduler,
				    int64_t now_ticks)
{
	if ((scheduler == NULL) || (scheduler->rate_hz == 0U) ||
	    (scheduler->ticks_per_second == 0U) || (now_ticks < scheduler->next_deadline_ticks)) {
		return 0U;
	}

	const uint64_t late_ticks = (uint64_t)(now_ticks - scheduler->next_deadline_ticks);
	const uint64_t whole_seconds = late_ticks / scheduler->ticks_per_second;
	if (whole_seconds >= (UINT32_MAX / scheduler->rate_hz)) {
		return UINT32_MAX;
	}

	const uint64_t partial_ticks = late_ticks % scheduler->ticks_per_second;
	uint64_t due_ticks = (whole_seconds * scheduler->rate_hz) +
			     ((partial_ticks * scheduler->rate_hz) / scheduler->ticks_per_second) +
			     1U;
	struct picosystem_fixed_rate_scheduler probe = *scheduler;
	picosystem_fixed_rate_scheduler_advance(&probe, (uint32_t)due_ticks);

	/* The current phase can put one extra deadline inside the rounded estimate. */
	while ((due_ticks < UINT32_MAX) && (probe.next_deadline_ticks <= now_ticks)) {
		++due_ticks;
		picosystem_fixed_rate_scheduler_advance(&probe, 1U);
	}

	return (uint32_t)due_ticks;
}
