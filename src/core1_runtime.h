/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_CORE1_RUNTIME_H_
#define PICOSYSTEM_CORE1_RUNTIME_H_

#include <stdbool.h>
#include <stdint.h>

#include "dense_scene.h"
#include "scene_renderer.h"

enum picosystem_core1_state {
	PICOSYSTEM_CORE1_STATE_OFFLINE,
	PICOSYSTEM_CORE1_STATE_BOOTING,
	PICOSYSTEM_CORE1_STATE_IDLE,
	PICOSYSTEM_CORE1_STATE_RUNNING,
	PICOSYSTEM_CORE1_STATE_STOPPED,
	PICOSYSTEM_CORE1_STATE_FAULT,
};

struct picosystem_core1_status {
	uint32_t requested_sequence;
	uint32_t completed_sequence;
	uint32_t heartbeat_count;
	uint32_t stack_size_bytes;
	uint32_t stack_used_bytes;
	uint32_t last_scene_raster_time_us;
	uint32_t ready_strip_count;
	uint32_t scene_strip_count;
	uint32_t scene_item_index;
	uint32_t core_id;
	int error;
	enum picosystem_scene_render_stage scene_stage;
	enum picosystem_scene_render_primitive scene_primitive;
	enum picosystem_core1_state state;
	bool ready;
};

struct picosystem_core1_dense_result {
	uint32_t stage_time_us[PICOSYSTEM_DENSE_SCENE_STAGE_COUNT];
	uint32_t total_time_us;
};

struct picosystem_core1_scene_result {
	uint32_t raster_time_us;
	uint16_t strip_count;
};

typedef int (*picosystem_core1_scene_strip_consumer)(const struct picosystem_rect *region,
						     void *context);

/* Launch the bare-metal core-1 worker and verify its shared-memory protocol. */
int picosystem_core1_init(void);

/* Execute one bounded round trip through shared SRAM. */
int picosystem_core1_ping(uint32_t challenge, uint32_t *response);

/* Rasterize one deterministic dense frame and report core-1-only wall times. */
int picosystem_core1_draw_dense(uint32_t frame_index, struct picosystem_core1_dense_result *result);

/* Copy an immutable scene snapshot, rasterize it on core 1, and wait for completion. */
int picosystem_core1_render_scene(const struct picosystem_scene_snapshot *snapshot,
				  struct picosystem_core1_scene_result *result);

/* Rasterize final, non-overlapping strips while core 0 consumes earlier strips. */
int picosystem_core1_render_scene_stream(const struct picosystem_scene_snapshot *snapshot,
					 picosystem_core1_scene_strip_consumer consumer,
					 void *consumer_context,
					 struct picosystem_core1_scene_result *result);

bool picosystem_core1_is_ready(void);

/* Copy health and stack high-water information owned by the two cores. */
int picosystem_core1_get_status(struct picosystem_core1_status *status);

const char *picosystem_core1_state_name(enum picosystem_core1_state state);

#endif /* PICOSYSTEM_CORE1_RUNTIME_H_ */
