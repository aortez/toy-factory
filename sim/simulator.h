/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef TOY_FACTORY_HOST_SIMULATOR_H_
#define TOY_FACTORY_HOST_SIMULATOR_H_

#include <stdbool.h>
#include <stdint.h>

#include "game_snapshot.h"

/* One caller-owned deterministic simulation. Rendering uses the shared global raster buffer. */
struct toy_factory_simulator {
	struct picosystem_game_world world;
	struct picosystem_scene_snapshot snapshot;
	uint32_t snapshot_sequence;
	bool rendered;
};

int toy_factory_simulator_init(struct toy_factory_simulator *simulator,
			       enum picosystem_game_scene_id scene_id);
int toy_factory_simulator_reset(struct toy_factory_simulator *simulator,
				enum picosystem_game_scene_id scene_id);
int toy_factory_simulator_step(struct toy_factory_simulator *simulator,
			       const struct picosystem_game_input *input, uint32_t tick_count);
int toy_factory_simulator_apply_action(struct toy_factory_simulator *simulator,
				       enum picosystem_game_scene_action action);
int toy_factory_simulator_render(struct toy_factory_simulator *simulator);
uint32_t toy_factory_simulator_state_hash(const struct toy_factory_simulator *simulator);
uint32_t toy_factory_simulator_framebuffer_crc32(const struct toy_factory_simulator *simulator);

#endif /* TOY_FACTORY_HOST_SIMULATOR_H_ */
