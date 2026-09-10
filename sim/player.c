/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <SDL3/SDL.h>

#include "graphics_raster.h"
#include "simulator.h"

#define PLAYER_INITIAL_SCALE      3
#define PLAYER_NANOSECONDS_SECOND UINT64_C(1000000000)
#define PLAYER_MAX_DELTA_NS       UINT64_C(250000000)
#define PLAYER_MAX_CATCHUP_TICKS  8U
#define PLAYER_MAX_SINGLE_STEPS   64U

struct player_options {
	enum picosystem_game_scene_id scene_id;
	uint32_t frame_limit;
	bool paused;
};

struct player_display {
	SDL_Window *window;
	SDL_Renderer *renderer;
	SDL_Texture *texture;
	uint8_t rgba[PICOSYSTEM_GRAPHICS_WIDTH * PICOSYSTEM_GRAPHICS_HEIGHT * 4U];
};

static void print_usage(FILE *stream, const char *program)
{
	fprintf(stream,
		"Usage: %s [--scene NAME] [--paused] [--frames COUNT]\n"
		"\n"
		"Scenes: clockwork, hourglass, marble-machine, garden\n"
		"\n"
		"Controls:\n"
		"  Arrow keys        D-pad\n"
		"  A                Garden tool\n"
		"  B                Cycle Garden tool\n"
		"  X                Scene action / auto-gardener\n"
		"  Y or R           Reset scene\n"
		"  Tab              Next scene\n"
		"  1-4              Select scene\n"
		"  Space            Pause/resume\n"
		"  N or .           Single-step while paused\n"
		"  Escape           Quit\n",
		program);
}

static int parse_u32(const char *text, uint32_t *value)
{
	if ((text == NULL) || (value == NULL) || (*text == '\0') || (*text == '-')) {
		return -EINVAL;
	}

	errno = 0;
	char *end = NULL;
	const unsigned long parsed = strtoul(text, &end, 10);
	if ((errno != 0) || (*end != '\0') || (parsed > UINT32_MAX)) {
		return -ERANGE;
	}

	*value = (uint32_t)parsed;
	return 0;
}

static int parse_options(int argc, char **argv, struct player_options *options)
{
	if (options == NULL) {
		return -EINVAL;
	}

	*options = (struct player_options){
		.scene_id = PICOSYSTEM_GAME_SCENE_HOURGLASS,
	};
	for (int index = 1; index < argc; ++index) {
		const char *const option = argv[index];
		if (strcmp(option, "--help") == 0) {
			print_usage(stdout, argv[0]);
			return 1;
		}
		if (strcmp(option, "--paused") == 0) {
			options->paused = true;
			continue;
		}
		if ((strcmp(option, "--scene") == 0) || (strcmp(option, "--frames") == 0)) {
			if ((index + 1) >= argc) {
				fprintf(stderr, "%s requires another argument\n", option);
				return -EINVAL;
			}
			const char *const value = argv[++index];
			const int err = (strcmp(option, "--scene") == 0)
						? picosystem_game_scene_find_selectable(
							  value, &options->scene_id)
						: parse_u32(value, &options->frame_limit);
			if (err != 0) {
				fprintf(stderr, "invalid value '%s' for %s\n", value, option);
				return err;
			}
			continue;
		}

		fprintf(stderr, "unknown option '%s'\n", option);
		return -EINVAL;
	}
	return 0;
}

static bool key_is_down(const bool *keys, int key_count, SDL_Scancode scancode)
{
	const int index = (int)scancode;
	return (keys != NULL) && (index >= 0) && (index < key_count) && keys[index];
}

static struct picosystem_game_input current_input(void)
{
	int key_count = 0;
	const bool *const keys = SDL_GetKeyboardState(&key_count);
	const bool left = key_is_down(keys, key_count, SDL_SCANCODE_LEFT);
	const bool right = key_is_down(keys, key_count, SDL_SCANCODE_RIGHT);
	const bool up = key_is_down(keys, key_count, SDL_SCANCODE_UP);
	const bool down = key_is_down(keys, key_count, SDL_SCANCODE_DOWN);

	return (struct picosystem_game_input){
		.horizontal = (int8_t)((right ? 1 : 0) - (left ? 1 : 0)),
		.vertical = (int8_t)((down ? 1 : 0) - (up ? 1 : 0)),
	};
}

static int reset_scene(struct toy_factory_simulator *simulator,
		       enum picosystem_game_scene_id scene_id, bool *needs_render)
{
	const int err = toy_factory_simulator_reset(simulator, scene_id);
	if (err == 0) {
		*needs_render = true;
	}
	return err;
}

static int select_next_scene(struct toy_factory_simulator *simulator, bool *needs_render)
{
	enum picosystem_game_scene_id next_scene_id;
	const int err = picosystem_game_scene_next(
		(enum picosystem_game_scene_id)simulator->world.scene_id, &next_scene_id);
	if (err != 0) {
		return err;
	}
	return reset_scene(simulator, next_scene_id, needs_render);
}

static int apply_scene_action(struct toy_factory_simulator *simulator,
			      enum picosystem_game_scene_action action, bool *needs_render)
{
	const int err = toy_factory_simulator_apply_action(simulator, action);
	if (err == 0) {
		*needs_render = true;
	}
	return err;
}

static int handle_key_down(const SDL_KeyboardEvent *event, struct toy_factory_simulator *simulator,
			   bool *running, bool *paused, uint32_t *single_steps, bool *needs_render,
			   bool *reset_clock)
{
	if (event->repeat) {
		return 0;
	}

	const enum picosystem_game_scene_id scene_id =
		(enum picosystem_game_scene_id)simulator->world.scene_id;
	switch (event->scancode) {
	case SDL_SCANCODE_ESCAPE:
		*running = false;
		return 0;
	case SDL_SCANCODE_SPACE:
	case SDL_SCANCODE_P:
		*paused = !*paused;
		*reset_clock = true;
		return 0;
	case SDL_SCANCODE_N:
	case SDL_SCANCODE_PERIOD:
		if (*paused && (*single_steps < PLAYER_MAX_SINGLE_STEPS)) {
			++*single_steps;
		}
		return 0;
	case SDL_SCANCODE_Y:
	case SDL_SCANCODE_R:
		*reset_clock = true;
		return reset_scene(simulator, scene_id, needs_render);
	case SDL_SCANCODE_TAB:
		*reset_clock = true;
		return select_next_scene(simulator, needs_render);
	case SDL_SCANCODE_1:
		*reset_clock = true;
		return reset_scene(simulator, PICOSYSTEM_GAME_SCENE_CLOCKWORK, needs_render);
	case SDL_SCANCODE_2:
		*reset_clock = true;
		return reset_scene(simulator, PICOSYSTEM_GAME_SCENE_HOURGLASS, needs_render);
	case SDL_SCANCODE_3:
		*reset_clock = true;
		return reset_scene(simulator, PICOSYSTEM_GAME_SCENE_MARBLE_MACHINE, needs_render);
	case SDL_SCANCODE_4:
		*reset_clock = true;
		return reset_scene(simulator, PICOSYSTEM_GAME_SCENE_GARDEN, needs_render);
	case SDL_SCANCODE_X:
		return apply_scene_action(simulator, PICOSYSTEM_GAME_SCENE_ACTION_PRIMARY,
					  needs_render);
	case SDL_SCANCODE_A:
		if (scene_id == PICOSYSTEM_GAME_SCENE_GARDEN) {
			return apply_scene_action(simulator, PICOSYSTEM_GAME_SCENE_ACTION_USE_TOOL,
						  needs_render);
		}
		return 0;
	case SDL_SCANCODE_B:
		if (scene_id == PICOSYSTEM_GAME_SCENE_GARDEN) {
			return apply_scene_action(
				simulator, PICOSYSTEM_GAME_SCENE_ACTION_CYCLE_TOOL, needs_render);
		}
		return 0;
	default:
		return 0;
	}
}

static int process_events(struct toy_factory_simulator *simulator, bool *running, bool *paused,
			  uint32_t *single_steps, bool *needs_render, bool *reset_clock)
{
	SDL_Event event;
	while (SDL_PollEvent(&event)) {
		if (event.type == SDL_EVENT_QUIT) {
			*running = false;
		} else if (event.type == SDL_EVENT_WINDOW_EXPOSED) {
			*needs_render = true;
		} else if (event.type == SDL_EVENT_KEY_DOWN) {
			const int err = handle_key_down(&event.key, simulator, running, paused,
							single_steps, needs_render, reset_clock);
			if (err != 0) {
				return err;
			}
		}
	}
	return 0;
}

static void convert_framebuffer_to_rgba(uint8_t *destination)
{
	const uint8_t *const source = picosystem_graphics_raster_bytes();
	const size_t pixel_count = (size_t)PICOSYSTEM_GRAPHICS_WIDTH * PICOSYSTEM_GRAPHICS_HEIGHT;
	for (size_t index = 0U; index < pixel_count; ++index) {
		const uint16_t pixel =
			((uint16_t)source[index * 2U] << 8U) | source[(index * 2U) + 1U];
		const uint8_t red = (uint8_t)((pixel >> 11U) & UINT16_C(0x1f));
		const uint8_t green = (uint8_t)((pixel >> 5U) & UINT16_C(0x3f));
		const uint8_t blue = (uint8_t)(pixel & UINT16_C(0x1f));
		destination[index * 4U] = (uint8_t)((red << 3U) | (red >> 2U));
		destination[(index * 4U) + 1U] = (uint8_t)((green << 2U) | (green >> 4U));
		destination[(index * 4U) + 2U] = (uint8_t)((blue << 3U) | (blue >> 2U));
		destination[(index * 4U) + 3U] = UINT8_MAX;
	}
}

static int present_simulator(struct player_display *display,
			     struct toy_factory_simulator *simulator, bool paused)
{
	const int err = toy_factory_simulator_render(simulator);
	if (err != 0) {
		return err;
	}

	convert_framebuffer_to_rgba(display->rgba);
	const int pitch = (int)(PICOSYSTEM_GRAPHICS_WIDTH * 4U);
	if (!SDL_UpdateTexture(display->texture, NULL, display->rgba, pitch) ||
	    !SDL_SetRenderDrawColor(display->renderer, 0U, 0U, 0U, UINT8_MAX) ||
	    !SDL_RenderClear(display->renderer) ||
	    !SDL_RenderTexture(display->renderer, display->texture, NULL, NULL) ||
	    !SDL_RenderPresent(display->renderer)) {
		return -EIO;
	}

	char title[160];
	const char *const scene_name = picosystem_game_scene_name(
		(enum picosystem_game_scene_id)simulator->world.scene_id);
	(void)snprintf(title, sizeof(title),
		       "Toy Factory | %s | tick %" PRIu32 " | %s | hash %08" PRIx32, scene_name,
		       simulator->world.logic_tick_count, paused ? "PAUSED" : "RUNNING",
		       toy_factory_simulator_state_hash(simulator));
	return SDL_SetWindowTitle(display->window, title) ? 0 : -EIO;
}

static int initialize_display(struct player_display *display)
{
	*display = (struct player_display){0};
	if (!SDL_SetAppMetadata("Toy Factory", "0.1.0", "pizza.allan.toy-factory") ||
	    !SDL_Init(SDL_INIT_VIDEO)) {
		return -EIO;
	}

	const int width = (int)PICOSYSTEM_GRAPHICS_WIDTH * PLAYER_INITIAL_SCALE;
	const int height = (int)PICOSYSTEM_GRAPHICS_HEIGHT * PLAYER_INITIAL_SCALE;
	if (!SDL_CreateWindowAndRenderer("Toy Factory", width, height, SDL_WINDOW_RESIZABLE,
					 &display->window, &display->renderer)) {
		return -EIO;
	}
	if (!SDL_SetRenderLogicalPresentation(display->renderer, (int)PICOSYSTEM_GRAPHICS_WIDTH,
					      (int)PICOSYSTEM_GRAPHICS_HEIGHT,
					      SDL_LOGICAL_PRESENTATION_INTEGER_SCALE)) {
		return -EIO;
	}

	display->texture = SDL_CreateTexture(
		display->renderer, SDL_PIXELFORMAT_RGBA32, SDL_TEXTUREACCESS_STREAMING,
		(int)PICOSYSTEM_GRAPHICS_WIDTH, (int)PICOSYSTEM_GRAPHICS_HEIGHT);
	if ((display->texture == NULL) ||
	    !SDL_SetTextureScaleMode(display->texture, SDL_SCALEMODE_NEAREST)) {
		return -EIO;
	}
	return 0;
}

static void destroy_display(struct player_display *display)
{
	SDL_DestroyTexture(display->texture);
	SDL_DestroyRenderer(display->renderer);
	SDL_DestroyWindow(display->window);
	SDL_Quit();
}

static int run_player(const struct player_options *options)
{
	struct toy_factory_simulator simulator;
	int err = toy_factory_simulator_init(&simulator, options->scene_id);
	if (err != 0) {
		fprintf(stderr, "could not initialize simulator: %d\n", err);
		return 1;
	}

	struct player_display display;
	err = initialize_display(&display);
	if (err != 0) {
		fprintf(stderr, "could not initialize SDL: %s\n", SDL_GetError());
		destroy_display(&display);
		return 1;
	}

	bool running = true;
	bool paused = options->paused;
	bool needs_render = true;
	uint32_t single_steps = 0U;
	uint32_t frame_count = 0U;
	uint64_t previous_time = SDL_GetTicksNS();
	uint64_t accumulator = 0U;

	while (running) {
		bool reset_clock = false;
		err = process_events(&simulator, &running, &paused, &single_steps, &needs_render,
				     &reset_clock);
		if (err != 0) {
			fprintf(stderr, "could not apply input: %d\n", err);
			break;
		}
		if (!running) {
			break;
		}

		const uint64_t now = SDL_GetTicksNS();
		if (reset_clock) {
			previous_time = now;
			accumulator = 0U;
		}
		uint64_t delta = now - previous_time;
		previous_time = now;
		if (delta > PLAYER_MAX_DELTA_NS) {
			delta = PLAYER_MAX_DELTA_NS;
		}

		const struct picosystem_game_input input = current_input();
		if (paused) {
			accumulator = 0U;
			if (single_steps != 0U) {
				err = toy_factory_simulator_step(&simulator, &input, single_steps);
				if (err != 0) {
					fprintf(stderr, "could not single-step simulator: %d\n",
						err);
					break;
				}
				needs_render = true;
				single_steps = 0U;
			}
		} else {
			accumulator += delta * PICOSYSTEM_GAME_TICK_RATE_HZ;
			uint32_t catchup_ticks = 0U;
			while ((accumulator >= PLAYER_NANOSECONDS_SECOND) &&
			       (catchup_ticks < PLAYER_MAX_CATCHUP_TICKS)) {
				err = toy_factory_simulator_step(&simulator, &input, 1U);
				if (err != 0) {
					fprintf(stderr, "could not advance simulator: %d\n", err);
					running = false;
					break;
				}
				accumulator -= PLAYER_NANOSECONDS_SECOND;
				++catchup_ticks;
				needs_render = true;
			}
			if (catchup_ticks == PLAYER_MAX_CATCHUP_TICKS) {
				accumulator %= PLAYER_NANOSECONDS_SECOND;
			}
		}

		if (running && needs_render) {
			err = present_simulator(&display, &simulator, paused);
			if (err != 0) {
				fprintf(stderr, "could not render or present simulator: %d (%s)\n",
					err, SDL_GetError());
				break;
			}
			needs_render = false;
			++frame_count;
			if ((options->frame_limit != 0U) && (frame_count >= options->frame_limit)) {
				break;
			}
		}

		SDL_DelayNS(UINT64_C(1000000));
	}

	if (!simulator.rendered) {
		(void)toy_factory_simulator_render(&simulator);
	}
	printf("{\"scene\":\"%s\",\"tick\":%" PRIu32 ",\"hash\":\"%08" PRIx32
	       "\",\"framebuffer_crc32\":\"%08" PRIx32 "\"}\n",
	       picosystem_game_scene_name((enum picosystem_game_scene_id)simulator.world.scene_id),
	       simulator.world.logic_tick_count, toy_factory_simulator_state_hash(&simulator),
	       toy_factory_simulator_framebuffer_crc32(&simulator));
	destroy_display(&display);
	return err == 0 ? 0 : 1;
}

int main(int argc, char **argv)
{
	struct player_options options;
	const int err = parse_options(argc, argv, &options);
	if (err > 0) {
		return 0;
	}
	if (err < 0) {
		print_usage(stderr, argv[0]);
		return 2;
	}
	return run_player(&options);
}
