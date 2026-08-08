/*
 * Copyright (c) 2026 PicoSystem Playground contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_DISPLAY_TEST_H_
#define PICOSYSTEM_DISPLAY_TEST_H_

#include <stdint.h>

struct picosystem_display_test_result {
	uint32_t frame_time_us;
	uint32_t throughput_kib_per_second;
};

int picosystem_display_test_run(struct picosystem_display_test_result *result);

#endif /* PICOSYSTEM_DISPLAY_TEST_H_ */
