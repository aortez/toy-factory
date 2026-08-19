/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_PHYSICS_CHAIN_FIXTURE_H_
#define PICOSYSTEM_PHYSICS_CHAIN_FIXTURE_H_

#include <stdint.h>

#include "game_world.h"

#define PICOSYSTEM_PHYSICS_CHAIN_FIXTURE_MIN_LINKS 1U
#define PICOSYSTEM_PHYSICS_CHAIN_FIXTURE_MAX_LINKS 8U

/* Restore a deterministic world containing one pinned horizontal box chain. */
int picosystem_physics_chain_fixture_reset(struct picosystem_game_world *world,
					   uint16_t link_count);

#endif /* PICOSYSTEM_PHYSICS_CHAIN_FIXTURE_H_ */
