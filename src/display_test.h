/*
 * Copyright (c) 2026 PicoSystem Playground contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_DISPLAY_TEST_H_
#define PICOSYSTEM_DISPLAY_TEST_H_

#include <stdbool.h>
#include <stdint.h>

struct picosystem_display_test_state {
	uint32_t full_frame_time_us;
	uint32_t full_frame_throughput_kib_per_second;
	uint32_t last_partial_time_us;
	uint32_t last_partial_throughput_kib_per_second;
	uint32_t partial_update_count;
	uint16_t last_partial_width;
	uint16_t last_partial_height;
	uint16_t sprite_x;
	uint16_t sprite_y;
	bool ready;
};

int picosystem_display_test_run(struct picosystem_display_test_state *state);
int picosystem_display_test_move(struct picosystem_display_test_state *state, int8_t horizontal,
				 int8_t vertical);
int picosystem_display_test_redraw(struct picosystem_display_test_state *state);

#endif /* PICOSYSTEM_DISPLAY_TEST_H_ */
