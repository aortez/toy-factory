/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef TOY_FACTORY_GAME_SNAPSHOT_H_
#define TOY_FACTORY_GAME_SNAPSHOT_H_

#include <stdint.h>

#include "game_world.h"
#include "scene_renderer.h"

/* Build the immutable renderer input for one authoritative world state. */
int picosystem_game_snapshot_build(const struct picosystem_game_world *world, uint32_t sequence,
				   uint32_t redraw_request_sequence, int64_t published_uptime_ticks,
				   struct picosystem_scene_snapshot *snapshot);

#endif /* TOY_FACTORY_GAME_SNAPSHOT_H_ */
