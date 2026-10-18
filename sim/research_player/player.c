/* SPDX-License-Identifier: Apache-2.0 */
#define _POSIX_C_SOURCE 200809L
#include "research_session.h"

#include <SDL3/SDL.h>
#include <errno.h>
#include <inttypes.h>
#include <stdbool.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#define SECOND_NS  UINT64_C(1000000000)
#define SLICE_NS   UINT64_C(4000000)
#define FRAME_NS   UINT64_C(33333333)
#define WIDTH      240
#define GARDEN_TOP 74
#define HEIGHT     (GARDEN_TOP + WIDTH)

struct options {
	struct research_options research;
	const char *capture_dir;
	const char *test_view;
	uint32_t stop_tick;
	uint32_t frames;
	uint8_t speed;
	bool paused;
	bool capture_on_exit;
	bool highlight_family;
	bool test_controls;
	bool exit_at_stop;
};

struct player {
	struct options options;
	struct research_session *session;
	SDL_Window *window;
	SDL_Renderer *renderer;
	SDL_Texture *texture;
	uint8_t raw[RESEARCH_FRAME_BYTES];
	uint8_t rgba[WIDTH * WIDTH * 4];
	uint32_t crc;
	uint32_t pending;
	uint32_t measured_hz;
	uint64_t budget;
	bool running;
	bool dirty;
};

static const uint32_t speeds[] = {1U, 16U, 256U, 0U};

static void usage(void)
{
	puts("Usage: research-player [--policy initial|s1-g3-c4|s2-g3-c1]\n"
	     "  [--seed HEX] [--layout rainfed|rainfed-crowded] [--founder ID]\n"
	     "  [--speed 1|16|256|max] [--paused] [--highlight-family] [--capture-dir DIR]\n"
	     "  [--stop-tick TICKS] [--frames COUNT] [--capture-on-exit] [--test-controls]\n"
	     "  [--test-view NEW_PNG (requires --test-controls)]\n"
	     "Space/P pause; N/. step one tick; D step one day (3840 ticks); R reset\n"
	     "-/+ speed; M maximum speed; H family overlay; S screenshot + state; Escape quit\n"
	     "No gardener inputs. Changing policy or conditions requires a fresh launch.");
}

static int number(const char *text, int base, uint32_t maximum, uint32_t *out)
{
	if (*text == '\0') {
		return -EINVAL;
	}
	for (const char *p = text; *p; ++p) {
		if (!((*p >= '0' && *p <= '9') || (base == 16 && *p >= 'a' && *p <= 'f'))) {
			return -EINVAL;
		}
	}
	errno = 0;
	char *end;
	const unsigned long value = strtoul(text, &end, base);
	if ((errno != 0) || (*end != '\0') || (value > maximum)) {
		return -ERANGE;
	}
	*out = (uint32_t)value;
	return 0;
}

static int parse(int argc, char **argv, struct options *out)
{
	*out = (struct options){.research = {.seed = UINT32_C(0x58d7d6ca), .founder = 1U},
				.capture_dir = "artifacts/garden-research-captures",
				.stop_tick = RESEARCH_STOP_TICK};
	for (int i = 1; i < argc; ++i) {
		const char *const arg = argv[i];
		if (strcmp(arg, "--help") == 0) {
			usage();
			return 1;
		}
		if (strcmp(arg, "--paused") == 0) {
			out->paused = true;
			continue;
		}
		if (strcmp(arg, "--capture-on-exit") == 0) {
			out->capture_on_exit = true;
			continue;
		}
		if (strcmp(arg, "--highlight-family") == 0) {
			out->highlight_family = true;
			continue;
		}
		if (strcmp(arg, "--test-controls") == 0) {
			out->test_controls = true;
			out->paused = true;
			continue;
		}
		if (++i >= argc) {
			return -EINVAL;
		}
		const char *const value = argv[i];
		uint32_t parsed;
		if (strcmp(arg, "--policy") == 0) {
			uint8_t model = 0U;
			while ((model < 3U) && (strcmp(value, research_model_name(model)) != 0)) {
				++model;
			}
			if (model == 3U) {
				return -EINVAL;
			}
			out->research.model = model;
		} else if (strcmp(arg, "--layout") == 0) {
			uint8_t layout = 0U;
			while ((layout < 2U) &&
			       (strcmp(value, research_layout_name(layout)) != 0)) {
				++layout;
			}
			if (layout == 2U) {
				return -EINVAL;
			}
			out->research.layout = layout;
		} else if (strcmp(arg, "--seed") == 0) {
			if ((strlen(value) != 8U) ||
			    (number(value, 16, UINT32_MAX, &out->research.seed) != 0)) {
				return -EINVAL;
			}
		} else if (strcmp(arg, "--founder") == 0) {
			if (number(value, 10, UINT8_MAX, &parsed) != 0) {
				return -EINVAL;
			}
			out->research.founder = (uint8_t)parsed;
		} else if (strcmp(arg, "--speed") == 0) {
			if (strcmp(value, "max") == 0) {
				out->speed = 3U;
			} else {
				if (number(value, 10, 256U, &parsed) != 0) {
					return -EINVAL;
				}
				uint8_t index = 0U;
				while ((index < 3U) && (speeds[index] != parsed)) {
					++index;
				}
				if (index == 3U) {
					return -EINVAL;
				}
				out->speed = index;
			}
		} else if (strcmp(arg, "--stop-tick") == 0) {
			if (number(value, 10, RESEARCH_STOP_TICK, &out->stop_tick) != 0) {
				return -EINVAL;
			}
			out->exit_at_stop = true;
		} else if (strcmp(arg, "--frames") == 0) {
			if (number(value, 10, UINT32_MAX, &out->frames) != 0) {
				return -EINVAL;
			}
		} else if (strcmp(arg, "--capture-dir") == 0) {
			out->capture_dir = value;
		} else if (strcmp(arg, "--test-view") == 0) {
			out->test_view = value;
		} else {
			return -EINVAL;
		}
	}
	return (out->test_view != NULL && !out->test_controls) ? -EINVAL : 0;
}

static int pixels(struct player *player)
{
	const int err = research_session_render(player->session, player->raw, sizeof(player->raw),
						&player->crc);
	if (err != 0) {
		return err;
	}
	for (size_t i = 0U; i < WIDTH * WIDTH; ++i) {
		const uint16_t value = (uint16_t)(((uint16_t)player->raw[i * 2U] << 8U) |
						  player->raw[i * 2U + 1U]);
		const uint8_t r = (uint8_t)((value >> 11U) & 31U);
		const uint8_t g = (uint8_t)((value >> 5U) & 63U);
		const uint8_t b = (uint8_t)(value & 31U);
		player->rgba[i * 4U] = (uint8_t)((r << 3U) | (r >> 2U));
		player->rgba[i * 4U + 1U] = (uint8_t)((g << 2U) | (g >> 4U));
		player->rgba[i * 4U + 2U] = (uint8_t)((b << 3U) | (b >> 2U));
		player->rgba[i * 4U + 3U] = UINT8_MAX;
	}
	return 0;
}

static int capture(struct player *player)
{
	int err = pixels(player);
	if (err != 0) {
		return err;
	}
	if ((mkdir(player->options.capture_dir, 0755) != 0) && (errno != EEXIST)) {
		return -errno;
	}
	struct stat status;
	if ((lstat(player->options.capture_dir, &status) != 0) || !S_ISDIR(status.st_mode)) {
		return -EINVAL;
	}
	char folder[1024];
	const int size =
		snprintf(folder, sizeof(folder), "%s/shot-XXXXXX", player->options.capture_dir);
	if ((size < 0) || ((size_t)size >= sizeof(folder))) {
		return -ENAMETOOLONG;
	}
	if (mkdtemp(folder) == NULL) {
		return -errno;
	}
	char path[1100];
	/* The bounded folder leaves room for each fixed suffix below. */
	(void)snprintf(path, sizeof(path), "%s/frame.raw", folder);
	FILE *stream = fopen(path, "wbx");
	if (stream == NULL) {
		return -errno;
	}
	if (fwrite(player->raw, 1U, sizeof(player->raw), stream) != sizeof(player->raw)) {
		err = -EIO;
	}
	if (fclose(stream) != 0) {
		err = -EIO;
	}
	SDL_Surface *surface = NULL;
	if (err == 0) {
		surface = SDL_CreateSurfaceFrom(WIDTH, WIDTH, SDL_PIXELFORMAT_RGBA32, player->rgba,
						WIDTH * 4);
		(void)snprintf(path, sizeof(path), "%s/frame.png", folder);
		if ((surface == NULL) || !SDL_SavePNG(surface, path)) {
			err = -EIO;
		}
		SDL_DestroySurface(surface);
	}
	if (err == 0) {
		(void)snprintf(path, sizeof(path), "%s/state.json", folder);
		stream = fopen(path, "wx");
		if (stream == NULL) {
			err = -errno;
		} else {
			err = research_session_write_json(player->session, stream, &player->crc);
			if (fclose(stream) != 0) {
				err = -EIO;
			}
		}
	}
	/* Manifest written last marks a complete capture, including its runtime. */
	if (err == 0) {
		(void)snprintf(path, sizeof(path), "%s/manifest.tmp", folder);
		stream = fopen(path, "wx");
		if (stream == NULL) {
			err = -errno;
		} else {
			if (fprintf(stream,
				    "{\"archive_sha256\":\"" RESEARCH_ARCHIVE_SHA "\","
				    "\"policy\":\"%s\",\"framebuffer_crc32\":\"%08" PRIx32 "\"}\n",
				    research_model_name(player->options.research.model),
				    player->crc) < 0) {
				err = -EIO;
			}
			if (fclose(stream) != 0) {
				err = -EIO;
			}
		}
	}
	if (err == 0) {
		char completed[1100];
		(void)snprintf(completed, sizeof(completed), "%s/manifest.json", folder);
		if (rename(path, completed) != 0) {
			err = -errno;
		}
	}
	fprintf(stderr, "%s capture: %s\n", err == 0 ? "Saved" : "Incomplete", folder);
	return err;
}

static int queue_steps(struct player *player, uint32_t count)
{
	struct research_status status;
	const int err = research_session_status(player->session, &status);
	if (err != 0) {
		return err;
	}
	if (status.tick > player->options.stop_tick) {
		return -ERANGE;
	}
	const uint32_t remaining = player->options.stop_tick - status.tick;
	const uint64_t requested = (uint64_t)player->pending + count;
	/* Every press contributes work, including while a previous day is stepping. */
	player->pending = requested < remaining ? (uint32_t)requested : remaining;
	player->options.paused = true;
	player->budget = 0U;
	return 0;
}

static int key(struct player *player, SDL_Scancode code)
{
	player->dirty = true;
	switch (code) {
	case SDL_SCANCODE_ESCAPE:
		player->running = false;
		break;
	case SDL_SCANCODE_SPACE:
	case SDL_SCANCODE_P:
		player->options.paused = !player->options.paused;
		player->pending = 0U;
		player->budget = 0U;
		break;
	case SDL_SCANCODE_N:
	case SDL_SCANCODE_PERIOD:
	case SDL_SCANCODE_D:
		return queue_steps(player, code == SDL_SCANCODE_D ? RESEARCH_DAY_TICKS : 1U);
	case SDL_SCANCODE_R:
		player->pending = 0U;
		player->budget = 0U;
		player->measured_hz = 0U;
		return research_session_reset(&player->session);
	case SDL_SCANCODE_MINUS:
		if (player->options.speed > 0U) {
			--player->options.speed;
		}
		player->budget = 0U;
		break;
	case SDL_SCANCODE_EQUALS:
	case SDL_SCANCODE_KP_PLUS:
		if (player->options.speed < 3U) {
			++player->options.speed;
		}
		player->budget = 0U;
		break;
	case SDL_SCANCODE_M:
		player->options.speed = 3U;
		player->budget = 0U;
		break;
	case SDL_SCANCODE_S:
		return capture(player);
	case SDL_SCANCODE_H:
		player->options.highlight_family = !player->options.highlight_family;
		break;
	default:
		break;
	}
	return 0;
}

static int events(struct player *player)
{
	SDL_Event event;
	while (SDL_PollEvent(&event)) {
		if (event.type == SDL_EVENT_QUIT) {
			player->running = false;
		} else if ((event.type == SDL_EVENT_KEY_DOWN) && !event.key.repeat) {
			const int err = key(player, event.key.scancode);
			if (err != 0) {
				return err;
			}
		} else if (event.type == SDL_EVENT_WINDOW_EXPOSED) {
			player->dirty = true;
		}
	}
	return 0;
}

static int advance(struct player *player, uint64_t elapsed, uint32_t *advanced)
{
	*advanced = 0U;
	const uint64_t speed = speeds[player->options.speed];
	if (elapsed > SECOND_NS / 4U) {
		elapsed = SECOND_NS / 4U;
	}
	if (!player->options.paused && (speed != 0U)) {
		player->budget += elapsed * 60U * speed;
		const uint64_t cap = SECOND_NS * 60U * speed;
		if (player->budget > cap) {
			player->budget = cap; /* Drop wall-clock debt, never logical ticks. */
		}
	}
	const uint64_t deadline = SDL_GetTicksNS() + SLICE_NS;
	do {
		struct research_status status;
		int err = research_session_status(player->session, &status);
		if (err != 0) {
			return err;
		}
		uint32_t count = player->pending;
		if (!player->options.paused) {
			count = speed == 0U ? 64U : (uint32_t)(player->budget / SECOND_NS);
		}
		if (count > 64U) {
			count = 64U;
		}
		const uint32_t remaining = player->options.stop_tick - status.tick;
		if (count > remaining) {
			count = remaining;
		}
		if (count == 0U) {
			if (remaining == 0U) {
				player->pending = 0U;
				player->options.paused = true;
			}
			break;
		}
		err = research_session_step(player->session, count);
		if (err != 0) {
			return err;
		}
		if (player->options.paused) {
			player->pending -= count;
		} else if (speed != 0U) {
			player->budget -= (uint64_t)count * SECOND_NS;
		}
		*advanced += count;
		player->dirty = true;
	} while (SDL_GetTicksNS() < deadline);
	return 0;
}

static int render_family(struct player *player)
{
	struct research_family_view family;
	const int err = research_session_family_view(player->session, &family);
	if (err != 0) {
		return err;
	}
	if (!SDL_SetRenderDrawColor(player->renderer, 80U, UINT8_MAX, UINT8_MAX, UINT8_MAX)) {
		return -EIO;
	}
	for (uint16_t i = 0U; i < family.segment_count; ++i) {
		const struct research_family_segment *const segment = &family.segments[i];
		const float x = segment->start_x, y = GARDEN_TOP + segment->start_y;
		if (segment->base) {
			const SDL_FRect marker = {x - 3.0f, y - 3.0f, 7.0f, 7.0f};
			if (!SDL_RenderRect(player->renderer, &marker)) {
				return -EIO;
			}
		} else if (!SDL_RenderLine(player->renderer, x, y, segment->end_x,
					   GARDEN_TOP + segment->end_y)) {
			return -EIO;
		}
	}
	if (!SDL_RenderDebugText(player->renderer, 0.0f, 62.0f, "Cyan:living") ||
	    !SDL_SetRenderDrawColor(player->renderer, UINT8_MAX, 96U, 224U, UINT8_MAX) ||
	    !SDL_RenderDebugText(player->renderer, 112.0f, 62.0f, "Pink:seeds")) {
		return -EIO;
	}
	for (uint8_t i = 0U; i < family.seed_count; ++i) {
		const float x = family.seeds[i].x, y = GARDEN_TOP + family.seeds[i].y;
		const SDL_FPoint marker[] = {
			{x, y - 4.0f}, {x + 4.0f, y}, {x, y + 4.0f}, {x - 4.0f, y}, {x, y - 4.0f}};
		if (!SDL_RenderLines(player->renderer, marker, 5)) {
			return -EIO;
		}
	}
	return 0;
}

static int draw_frame(struct player *player)
{
	struct research_status status;
	int err = research_session_status(player->session, &status);
	if (err == 0) {
		err = pixels(player);
	}
	if (err != 0) {
		return err;
	}
	const SDL_FRect rectangle = {0.0f, GARDEN_TOP, 240.0f, 240.0f};
	char title[200];
	const int length = snprintf(
		title, sizeof(title), "Toy Factory research | %s | %08" PRIx32 " | %s | founder %u",
		research_model_name(player->options.research.model), player->options.research.seed,
		research_layout_name(player->options.research.layout),
		(unsigned int)player->options.research.founder);
	if ((length < 0) || ((size_t)length >= sizeof(title))) {
		return -EOVERFLOW;
	}
	const char *const speed = player->options.speed == 3U   ? "max"
				  : player->options.speed == 2U ? "256x"
				  : player->options.speed == 1U ? "16x"
								: "1x";
	const uint32_t speed_tenths = (uint32_t)(((uint64_t)player->measured_hz * 10U + 30U) / 60U);
	if (!SDL_UpdateTexture(player->texture, NULL, player->rgba, WIDTH * 4) ||
	    !SDL_SetRenderDrawColor(player->renderer, 12U, 16U, 22U, UINT8_MAX) ||
	    !SDL_RenderClear(player->renderer) ||
	    !SDL_RenderTexture(player->renderer, player->texture, NULL, &rectangle)) {
		return -EIO;
	}
	if (player->options.highlight_family) {
		err = render_family(player);
		if (err != 0) {
			return err;
		}
	}
	if (!SDL_SetRenderDrawColor(player->renderer, 210U, 225U, 230U, UINT8_MAX) ||
	    !SDL_RenderDebugTextFormat(player->renderer, 0.0f, 0.0f, "%s  F%u %s",
				       research_model_name(player->options.research.model),
				       (unsigned int)player->options.research.founder,
				       player->options.paused ? "PAUSED" : "RUNNING") ||
	    !SDL_RenderDebugTextFormat(player->renderer, 0.0f, 10.0f,
				       "Day %" PRIu32 "  %s  ~%" PRIu32 ".%" PRIu32 "x",
				       status.tick / RESEARCH_DAY_TICKS, speed, speed_tenths / 10U,
				       speed_tenths % 10U) ||
	    !SDL_RenderDebugTextFormat(player->renderer, 0.0f, 20.0f,
				       "Family live:%" PRIu32 " bank:%" PRIu32, status.living,
				       status.pending) ||
	    !SDL_RenderDebugText(player->renderer, 0.0f, 32.0f, "Space pause  N tick  D day") ||
	    !SDL_RenderDebugText(player->renderer, 0.0f, 42.0f, "-/+ speed  M max  R reset") ||
	    !SDL_RenderDebugText(player->renderer, 0.0f, 52.0f, "H family  S capture  Esc quit") ||
	    (!player->options.highlight_family &&
	     !SDL_RenderDebugText(player->renderer, 0.0f, 62.0f, "Family overlay: off")) ||
	    !SDL_SetWindowTitle(player->window, title)) {
		return -EIO;
	}
	return 0;
}

static int present(struct player *player)
{
	const int err = draw_frame(player);
	if (err != 0) {
		return err;
	}
	if (!SDL_RenderPresent(player->renderer)) {
		return -EIO;
	}
	player->dirty = false;
	return 0;
}

static int initialize(struct player *player)
{
	int err = research_session_open(&player->options.research, &player->session);
	if (err != 0) {
		return err;
	}
	if (!SDL_Init(SDL_INIT_VIDEO) ||
	    !SDL_CreateWindowAndRenderer("Garden research", WIDTH * 3, HEIGHT * 3,
					 SDL_WINDOW_RESIZABLE, &player->window,
					 &player->renderer) ||
	    !SDL_SetRenderLogicalPresentation(player->renderer, WIDTH, HEIGHT,
					      SDL_LOGICAL_PRESENTATION_INTEGER_SCALE)) {
		return -EIO;
	}
	player->texture = SDL_CreateTexture(player->renderer, SDL_PIXELFORMAT_RGBA32,
					    SDL_TEXTUREACCESS_STREAMING, WIDTH, WIDTH);
	if ((player->texture == NULL) ||
	    !SDL_SetTextureScaleMode(player->texture, SDL_SCALEMODE_NEAREST)) {
		return -EIO;
	}
	player->running = true;
	player->dirty = true;
	return 0;
}

static int test_step_queue(struct player *player)
{
	static const struct {
		SDL_Scancode codes[3];
		uint32_t limit;
		uint32_t expected;
	} cases[] = {
		{{SDL_SCANCODE_N, SDL_SCANCODE_PERIOD, SDL_SCANCODE_N}, RESEARCH_STOP_TICK, 3U},
		{{SDL_SCANCODE_D, SDL_SCANCODE_D, SDL_SCANCODE_N},
		 RESEARCH_STOP_TICK,
		 2U * RESEARCH_DAY_TICKS + 1U},
		{{SDL_SCANCODE_D, SDL_SCANCODE_N, SDL_SCANCODE_D}, 7U, 7U},
		{{SDL_SCANCODE_D, SDL_SCANCODE_N, SDL_SCANCODE_D}, 0U, 0U},
		{{SDL_SCANCODE_D, SDL_SCANCODE_SPACE, SDL_SCANCODE_P}, RESEARCH_STOP_TICK, 0U},
		{{SDL_SCANCODE_D, SDL_SCANCODE_R, SDL_SCANCODE_UNKNOWN}, RESEARCH_STOP_TICK, 0U},
	};
	for (size_t i = 0U; i < sizeof(cases) / sizeof(cases[0]); ++i) {
		int err = key(player, SDL_SCANCODE_R);
		if (err != 0) {
			return err;
		}
		player->options.paused = true;
		player->options.stop_tick = cases[i].limit;
		for (size_t j = 0U; j < sizeof(cases[i].codes) / sizeof(cases[i].codes[0]); ++j) {
			SDL_Event event = {.type = SDL_EVENT_KEY_DOWN};
			event.key.scancode = cases[i].codes[j];
			if (!SDL_PushEvent(&event)) {
				return -EIO;
			}
		}
		SDL_Event repeat = {.type = SDL_EVENT_KEY_DOWN};
		repeat.key.scancode = SDL_SCANCODE_N;
		repeat.key.repeat = true;
		if (!SDL_PushEvent(&repeat)) {
			return -EIO;
		}
		err = events(player);
		if ((err != 0) || (player->pending != cases[i].expected) ||
		    !player->options.paused) {
			fprintf(stderr,
				"Step-queue case %zu: pending %" PRIu32 ", expected %" PRIu32 "\n",
				i, player->pending, cases[i].expected);
			return -EFAULT;
		}
		uint32_t expected = cases[i].expected;
		if (i == 1U) {
			uint32_t advanced;
			err = advance(player, 0U, &advanced);
			SDL_Event event = {.type = SDL_EVENT_KEY_DOWN};
			event.key.scancode = SDL_SCANCODE_N;
			if ((err != 0) || !SDL_PushEvent(&event) || (events(player) != 0)) {
				return -EFAULT;
			}
			struct research_status status;
			++expected;
			if ((research_session_status(player->session, &status) != 0) ||
			    (status.tick + player->pending != expected)) {
				return -EFAULT;
			}
		}
		for (unsigned int slice = 0U;
		     (err == 0) && (player->pending != 0U) && (slice < 1000U); ++slice) {
			uint32_t advanced;
			err = advance(player, 0U, &advanced);
		}
		struct research_status status;
		if ((err != 0) || (player->pending != 0U) ||
		    (research_session_status(player->session, &status) != 0) ||
		    (status.tick != expected)) {
			return -EFAULT;
		}
	}
	player->options.stop_tick = RESEARCH_STOP_TICK;
	return key(player, SDL_SCANCODE_R);
}

static SDL_Surface *test_frame(struct player *player)
{
	if (draw_frame(player) != 0) {
		return NULL;
	}
	SDL_Surface *const raw = SDL_RenderReadPixels(player->renderer, NULL);
	if (raw == NULL) {
		return NULL;
	}
	SDL_Surface *const rgba = SDL_ConvertSurface(raw, SDL_PIXELFORMAT_RGBA32);
	SDL_DestroySurface(raw);
	return rgba;
}

static bool test_pixel(const SDL_Surface *surface, const SDL_FRect *viewport, int x, int y,
		       uint8_t r, uint8_t g, uint8_t b)
{
	const int px = (int)(viewport->x + ((float)x + 0.5f) * viewport->w / WIDTH);
	const int py = (int)(viewport->y + ((float)y + 0.5f) * viewport->h / HEIGHT);
	if ((px < 0) || (py < 0) || (px >= surface->w) || (py >= surface->h)) {
		return false;
	}
	const uint8_t *const pixel = (const uint8_t *)surface->pixels +
				     (size_t)py * (size_t)surface->pitch + (size_t)px * 4U;
	return pixel[0] == r && pixel[1] == g && pixel[2] == b;
}

static int test_highlight(struct player *player)
{
	const bool requested = player->options.highlight_family;
	int err = research_session_step(player->session, 16U * RESEARCH_DAY_TICKS);
	struct research_family_view family;
	if (err == 0) {
		err = research_session_family_view(player->session, &family);
	}
	if (err != 0) {
		return err;
	}
	player->options.highlight_family = false;
	player->pending = 17U;
	player->budget = 123U;
	SDL_Surface *before = test_frame(player), *highlighted = NULL, *restored = NULL;
	const uint32_t crc = player->crc;
	SDL_FRect viewport;
	if ((before == NULL) ||
	    !SDL_GetRenderLogicalPresentationRect(player->renderer, &viewport)) {
		err = -EIO;
	}
	for (unsigned int press = 0U; (err == 0) && (press < 2U); ++press) {
		SDL_Event event = {.type = SDL_EVENT_KEY_DOWN};
		event.key.scancode = SDL_SCANCODE_H;
		if (!SDL_PushEvent(&event) || (events(player) != 0) ||
		    (player->options.highlight_family != (press == 0U)) ||
		    (player->pending != 17U) || (player->budget != 123U)) {
			err = -EFAULT;
			break;
		}
		SDL_Surface *const frame = test_frame(player);
		if (press == 0U) {
			highlighted = frame;
		} else {
			restored = frame;
		}
		if ((frame == NULL) || (player->crc != crc)) {
			err = -EFAULT;
		}
	}
	if (err == 0) {
		if ((before->w != restored->w) || (before->h != restored->h)) {
			err = -EFAULT;
		}
		for (int row = 0; (err == 0) && (row < before->h); ++row) {
			if (memcmp((const uint8_t *)before->pixels +
					   (size_t)row * (size_t)before->pitch,
				   (const uint8_t *)restored->pixels +
					   (size_t)row * (size_t)restored->pitch,
				   (size_t)before->w * 4U) != 0) {
				err = -EFAULT;
			}
		}
		for (uint16_t i = 0U; (err == 0) && (i < family.segment_count); ++i) {
			const struct research_family_segment *const segment = &family.segments[i];
			if (segment->base &&
			    !test_pixel(highlighted, &viewport, segment->start_x - 3,
					GARDEN_TOP + segment->start_y - 3, 80U, UINT8_MAX,
					UINT8_MAX)) {
				err = -EFAULT;
			}
		}
		for (uint8_t i = 0U; (err == 0) && (i < family.seed_count); ++i) {
			if (!test_pixel(highlighted, &viewport, family.seeds[i].x,
					GARDEN_TOP + family.seeds[i].y - 4, UINT8_MAX, 96U, 224U)) {
				err = -EFAULT;
			}
		}
	}
	if ((err == 0) && (player->options.test_view != NULL)) {
		SDL_IOStream *const stream = SDL_IOFromFile(player->options.test_view, "wbx");
		if (stream == NULL) {
			err = -EIO;
		} else {
			if (!SDL_SavePNG_IO(highlighted, stream, false)) {
				err = -EIO;
			}
			if (!SDL_CloseIO(stream)) {
				err = -EIO;
			}
		}
	}
	SDL_DestroySurface(before);
	SDL_DestroySurface(highlighted);
	SDL_DestroySurface(restored);
	player->options.highlight_family = requested;
	return err == 0 ? key(player, SDL_SCANCODE_R) : err;
}

static int test_controls(struct player *player)
{
	static const SDL_Scancode keys[] = {SDL_SCANCODE_N, SDL_SCANCODE_D,      SDL_SCANCODE_R,
					    SDL_SCANCODE_A, SDL_SCANCODE_X,      SDL_SCANCODE_SPACE,
					    SDL_SCANCODE_P, SDL_SCANCODE_EQUALS, SDL_SCANCODE_MINUS,
					    SDL_SCANCODE_M};
	static const uint32_t ticks[] = {1U, 3841U, 0U, 0U, 0U, 0U, 0U, 0U, 0U, 0U};
	player->options.stop_tick = RESEARCH_STOP_TICK;
	player->options.speed = 0U;
	for (size_t i = 0U; i < sizeof(keys) / sizeof(keys[0]); ++i) {
		SDL_Event event = {.type = SDL_EVENT_KEY_DOWN};
		event.key.scancode = keys[i];
		if (!SDL_PushEvent(&event)) {
			return -EIO;
		}
		int err = events(player);
		for (unsigned int slice = 0U;
		     (err == 0) && (player->pending != 0U) && (slice < 1000U); ++slice) {
			uint32_t advanced;
			err = advance(player, 0U, &advanced);
		}
		struct research_status status;
		if ((err != 0) || (player->pending != 0U) ||
		    (research_session_status(player->session, &status) != 0) ||
		    (status.tick != ticks[i]) || (player->options.paused != (i != 5U)) ||
		    (present(player) != 0)) {
			return -EFAULT;
		}
	}
	int err = player->options.speed == 3U ? test_step_queue(player) : -EFAULT;
	return err == 0 ? test_highlight(player) : err;
}

int main(int argc, char **argv)
{
	static struct player player;
	if (signal(SIGPIPE, SIG_IGN) == SIG_ERR) {
		return 1;
	}
	int err = parse(argc, argv, &player.options);
	if (err > 0) {
		return 0;
	}
	if (err < 0) {
		usage();
		return 2;
	}
	err = initialize(&player);
	if ((err == 0) && player.options.test_controls) {
		err = test_controls(&player);
		player.running = false;
	}
	uint64_t previous = SDL_GetTicksNS(), rendered = 0U, measured = previous;
	uint32_t frames = 0U, measured_ticks = 0U;
	while ((err == 0) && player.running) {
		err = events(&player);
		if ((err != 0) || !player.running) {
			break;
		}
		const uint64_t now = SDL_GetTicksNS();
		uint32_t advanced;
		err = advance(&player, now - previous, &advanced);
		previous = now;
		measured_ticks += advanced;
		if (now - measured >= SECOND_NS) {
			player.measured_hz =
				(uint32_t)((uint64_t)measured_ticks * SECOND_NS / (now - measured));
			measured_ticks = 0U;
			measured = now;
			player.dirty = true;
		}
		struct research_status status;
		if (err == 0) {
			err = research_session_status(player.session, &status);
		}
		if ((err == 0) && player.dirty &&
		    ((rendered == 0U) || (now - rendered >= FRAME_NS))) {
			err = present(&player);
			rendered = now;
			++frames;
		}
		if ((err == 0) &&
		    (((status.tick == player.options.stop_tick) && player.options.exit_at_stop) ||
		     ((player.options.frames != 0U) && (frames >= player.options.frames)))) {
			player.running = false;
		}
		SDL_DelayNS(UINT64_C(1000000));
	}
	if ((err == 0) && player.options.capture_on_exit) {
		err = capture(&player);
	}
	if (err == 0) {
		err = pixels(&player);
	}
	if (err == 0) {
		err = research_session_write_json(player.session, stdout, &player.crc);
	}
	if (err != 0) {
		fprintf(stderr,
			"Research player stopped: %d (%s). Partial captures are not complete.\n",
			err, SDL_GetError());
	}
	SDL_DestroyTexture(player.texture);
	SDL_DestroyRenderer(player.renderer);
	SDL_DestroyWindow(player.window);
	SDL_Quit();
	research_session_close(player.session);
	return err == 0 ? 0 : 1;
}
