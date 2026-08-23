/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_GAME_SCENE_SELECTOR_H_
#define PICOSYSTEM_GAME_SCENE_SELECTOR_H_

#include <stdbool.h>
#include <stdint.h>

#define PICOSYSTEM_GAME_SCENE_SELECTOR_HOLD_MS INT64_C(750)

enum picosystem_game_scene_selector_action {
	PICOSYSTEM_GAME_SCENE_SELECTOR_NONE,
	PICOSYSTEM_GAME_SCENE_SELECTOR_RESET,
	PICOSYSTEM_GAME_SCENE_SELECTOR_NEXT,
};

struct picosystem_game_scene_selector {
	int64_t press_start_ms;
	int64_t previous_sample_ms;
	bool initialized;
	bool pressed;
	bool hold_handled;
};

/*
 * Turn a short Y press into reset and a 750 ms hold into one scene-change event.
 * The caller supplies monotonic samples, making the gesture independently testable.
 */
int picosystem_game_scene_selector_update(struct picosystem_game_scene_selector *selector,
					  int64_t now_ms, bool pressed,
					  enum picosystem_game_scene_selector_action *action);

#endif /* PICOSYSTEM_GAME_SCENE_SELECTOR_H_ */
