/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "game_scene_selector.h"

#include <errno.h>
#include <stddef.h>

int picosystem_game_scene_selector_update(struct picosystem_game_scene_selector *selector,
					  int64_t now_ms, bool pressed,
					  enum picosystem_game_scene_selector_action *action)
{
	if ((selector == NULL) || (action == NULL)) {
		return -EINVAL;
	}
	if (selector->initialized && (now_ms < selector->previous_sample_ms)) {
		return -ERANGE;
	}

	*action = PICOSYSTEM_GAME_SCENE_SELECTOR_NONE;
	selector->previous_sample_ms = now_ms;
	selector->initialized = true;

	if (pressed && !selector->pressed) {
		selector->press_start_ms = now_ms;
		selector->pressed = true;
		selector->hold_handled = false;
		return 0;
	}

	if (pressed && !selector->hold_handled &&
	    ((now_ms - selector->press_start_ms) >= PICOSYSTEM_GAME_SCENE_SELECTOR_HOLD_MS)) {
		selector->hold_handled = true;
		*action = PICOSYSTEM_GAME_SCENE_SELECTOR_NEXT;
		return 0;
	}

	if (!pressed && selector->pressed) {
		selector->pressed = false;
		if (!selector->hold_handled) {
			*action = PICOSYSTEM_GAME_SCENE_SELECTOR_RESET;
		}
	}

	return 0;
}
