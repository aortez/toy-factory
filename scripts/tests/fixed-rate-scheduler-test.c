/* SPDX-License-Identifier: Apache-2.0 */

#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>

#include "fixed_rate_scheduler.h"

#define TEST_TICKS_PER_SECOND 10000U
#define TEST_RATE_HZ          120U

static void test_exact_deadline_pattern(void)
{
	struct picosystem_fixed_rate_scheduler scheduler;
	assert(picosystem_fixed_rate_scheduler_init(&scheduler, 0, TEST_TICKS_PER_SECOND,
						    TEST_RATE_HZ) == 0);
	assert(scheduler.next_deadline_ticks == 83);

	picosystem_fixed_rate_scheduler_advance(&scheduler, 1U);
	assert(scheduler.next_deadline_ticks == 166);
	picosystem_fixed_rate_scheduler_advance(&scheduler, 1U);
	assert(scheduler.next_deadline_ticks == 250);
	picosystem_fixed_rate_scheduler_advance(&scheduler, 117U);
	assert(scheduler.next_deadline_ticks == TEST_TICKS_PER_SECOND);
	assert(scheduler.phase == 0U);
}

static void test_due_boundaries_and_catch_up(void)
{
	struct picosystem_fixed_rate_scheduler scheduler;
	assert(picosystem_fixed_rate_scheduler_init(&scheduler, 0, TEST_TICKS_PER_SECOND,
						    TEST_RATE_HZ) == 0);
	assert(picosystem_fixed_rate_scheduler_due(&scheduler, 82) == 0U);
	assert(picosystem_fixed_rate_scheduler_due(&scheduler, 83) == 1U);
	assert(picosystem_fixed_rate_scheduler_due(&scheduler, 165) == 1U);
	assert(picosystem_fixed_rate_scheduler_due(&scheduler, 166) == 2U);
	assert(picosystem_fixed_rate_scheduler_due(&scheduler, 1000) == 12U);

	picosystem_fixed_rate_scheduler_advance(&scheduler, 4U);
	assert(scheduler.next_deadline_ticks == 416);
	picosystem_fixed_rate_scheduler_advance(&scheduler, 8U);
	assert(scheduler.next_deadline_ticks == 1083);
	assert(picosystem_fixed_rate_scheduler_due(&scheduler, 1082) == 0U);
	assert(picosystem_fixed_rate_scheduler_due(&scheduler, 1083) == 1U);
}

static uint32_t reference_due(const struct picosystem_fixed_rate_scheduler *scheduler,
			      int64_t now_ticks)
{
	struct picosystem_fixed_rate_scheduler probe = *scheduler;
	uint32_t due_ticks = 0U;

	while (probe.next_deadline_ticks <= now_ticks) {
		++due_ticks;
		picosystem_fixed_rate_scheduler_advance(&probe, 1U);
	}

	return due_ticks;
}

static void test_due_matches_iterative_reference(void)
{
	struct picosystem_fixed_rate_scheduler scheduler;
	assert(picosystem_fixed_rate_scheduler_init(&scheduler, 19, TEST_TICKS_PER_SECOND,
						    TEST_RATE_HZ) == 0);

	for (uint32_t consumed = 0U; consumed < TEST_RATE_HZ; ++consumed) {
		for (int64_t offset = -1; offset <= 2000; ++offset) {
			const int64_t now_ticks = scheduler.next_deadline_ticks + offset;
			assert(picosystem_fixed_rate_scheduler_due(&scheduler, now_ticks) ==
			       reference_due(&scheduler, now_ticks));
		}
		picosystem_fixed_rate_scheduler_advance(&scheduler, 1U);
	}
}

static void test_validation(void)
{
	struct picosystem_fixed_rate_scheduler scheduler;
	assert(picosystem_fixed_rate_scheduler_init(NULL, 0, TEST_TICKS_PER_SECOND, TEST_RATE_HZ) ==
	       -EINVAL);
	assert(picosystem_fixed_rate_scheduler_init(&scheduler, 0, 0U, TEST_RATE_HZ) == -ERANGE);
	assert(picosystem_fixed_rate_scheduler_init(&scheduler, 0, TEST_TICKS_PER_SECOND, 0U) ==
	       -ERANGE);
	assert(picosystem_fixed_rate_scheduler_init(&scheduler, 0, 100U, 120U) == -ERANGE);
}

int main(void)
{
	test_exact_deadline_pattern();
	test_due_boundaries_and_catch_up();
	test_due_matches_iterative_reference();
	test_validation();
	puts("fixed-rate scheduler tests passed");
	return 0;
}
