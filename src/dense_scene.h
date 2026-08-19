/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_DENSE_SCENE_H_
#define PICOSYSTEM_DENSE_SCENE_H_

#include <stdint.h>

enum picosystem_dense_scene_stage {
	PICOSYSTEM_DENSE_SCENE_STAGE_BACKGROUND,
	PICOSYSTEM_DENSE_SCENE_STAGE_LINKS,
	PICOSYSTEM_DENSE_SCENE_STAGE_CIRCLES,
	PICOSYSTEM_DENSE_SCENE_STAGE_BOXES,
	PICOSYSTEM_DENSE_SCENE_STAGE_COUNT,
};

/* Draw one deterministic stage into the shared framebuffer without using Zephyr services. */
int picosystem_dense_scene_draw_stage(enum picosystem_dense_scene_stage stage,
				      uint32_t frame_index);

/* Draw the complete deterministic scene in canonical stage order. */
int picosystem_dense_scene_draw(uint32_t frame_index);

#endif /* PICOSYSTEM_DENSE_SCENE_H_ */
