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

#include "graphics_raster.h"
#include "simulator.h"

#define HOST_SIMULATOR_MAX_STEP_TICKS UINT32_C(1000000)

static int file_error(void)
{
	return errno != 0 ? -errno : -EIO;
}

static void print_usage(FILE *stream, const char *program)
{
	fprintf(stream,
		"Usage: %s [commands...] [output...]\n"
		"\n"
		"Commands execute from left to right:\n"
		"  --scene NAME          Reset to clockwork, hourglass, marble-machine, or garden\n"
		"  --step INPUT TICKS    Advance with none/up/down/left/right or a diagonal\n"
		"  --action NAME         Apply primary, flip, use-tool, or cycle-tool\n"
		"\n"
		"Output and assertions:\n"
		"  --output FILE.ppm     Save the final framebuffer as an RGB PPM image\n"
		"  --framebuffer FILE    Save the native RGB565 big-endian framebuffer\n"
		"  --expect-hash HEX     Fail unless the final authoritative hash matches\n"
		"  --expect-crc HEX      Fail unless the final framebuffer CRC-32 matches\n"
		"  --help                Show this help\n",
		program);
}

static int parse_scene(const char *name, enum picosystem_game_scene_id *scene_id)
{
	return picosystem_game_scene_find_selectable(name, scene_id);
}

static int parse_input(const char *name, struct picosystem_game_input *input)
{
	if ((name == NULL) || (input == NULL)) {
		return -EINVAL;
	}

	*input = (struct picosystem_game_input){0};
	if (strcmp(name, "none") == 0) {
		return 0;
	}
	if (strcmp(name, "up") == 0) {
		input->vertical = -1;
	} else if (strcmp(name, "down") == 0) {
		input->vertical = 1;
	} else if (strcmp(name, "left") == 0) {
		input->horizontal = -1;
	} else if (strcmp(name, "right") == 0) {
		input->horizontal = 1;
	} else if (strcmp(name, "up-left") == 0) {
		input->horizontal = -1;
		input->vertical = -1;
	} else if (strcmp(name, "up-right") == 0) {
		input->horizontal = 1;
		input->vertical = -1;
	} else if (strcmp(name, "down-left") == 0) {
		input->horizontal = -1;
		input->vertical = 1;
	} else if (strcmp(name, "down-right") == 0) {
		input->horizontal = 1;
		input->vertical = 1;
	} else {
		return -ENOENT;
	}

	return 0;
}

static int parse_action(const char *name, enum picosystem_game_scene_action *action)
{
	if ((name == NULL) || (action == NULL)) {
		return -EINVAL;
	}

	if ((strcmp(name, "primary") == 0) || (strcmp(name, "flip") == 0)) {
		*action = PICOSYSTEM_GAME_SCENE_ACTION_PRIMARY;
	} else if (strcmp(name, "use-tool") == 0) {
		*action = PICOSYSTEM_GAME_SCENE_ACTION_USE_TOOL;
	} else if (strcmp(name, "cycle-tool") == 0) {
		*action = PICOSYSTEM_GAME_SCENE_ACTION_CYCLE_TOOL;
	} else {
		return -ENOENT;
	}

	return 0;
}

static int parse_u32(const char *text, uint32_t maximum, uint32_t *value)
{
	if ((text == NULL) || (value == NULL) || (*text == '\0') || (*text == '-')) {
		return -EINVAL;
	}

	errno = 0;
	char *end = NULL;
	const unsigned long parsed = strtoul(text, &end, 10);
	if ((errno != 0) || (*end != '\0') || (parsed > maximum)) {
		return -ERANGE;
	}

	*value = (uint32_t)parsed;
	return 0;
}

static int parse_hex32(const char *text, uint32_t *value)
{
	if ((text == NULL) || (value == NULL) || (strlen(text) != 8U)) {
		return -EINVAL;
	}

	errno = 0;
	char *end = NULL;
	const unsigned long parsed = strtoul(text, &end, 16);
	if ((errno != 0) || (*end != '\0') || (parsed > UINT32_MAX)) {
		return -ERANGE;
	}

	*value = (uint32_t)parsed;
	return 0;
}

static int write_framebuffer(const char *path)
{
	FILE *const file = fopen(path, "wb");
	if (file == NULL) {
		return file_error();
	}

	const size_t byte_count = picosystem_graphics_raster_byte_count();
	const size_t written = fwrite(picosystem_graphics_raster_bytes(), 1U, byte_count, file);
	errno = 0;
	const int close_result = fclose(file);
	if (written != byte_count) {
		return -EIO;
	}
	if (close_result != 0) {
		return file_error();
	}

	return 0;
}

static int write_ppm(const char *path)
{
	FILE *const file = fopen(path, "wb");
	if (file == NULL) {
		return file_error();
	}

	if (fprintf(file, "P6\n%u %u\n255\n", PICOSYSTEM_GRAPHICS_WIDTH,
		    PICOSYSTEM_GRAPHICS_HEIGHT) < 0) {
		(void)fclose(file);
		return -EIO;
	}

	const uint8_t *const source = picosystem_graphics_raster_bytes();
	for (size_t index = 0U; index < picosystem_graphics_raster_byte_count(); index += 2U) {
		const uint16_t pixel = ((uint16_t)source[index] << 8U) | source[index + 1U];
		const uint8_t red = (uint8_t)((pixel >> 11U) & UINT16_C(0x1f));
		const uint8_t green = (uint8_t)((pixel >> 5U) & UINT16_C(0x3f));
		const uint8_t blue = (uint8_t)(pixel & UINT16_C(0x1f));
		const uint8_t rgb[3] = {
			(uint8_t)((red << 3U) | (red >> 2U)),
			(uint8_t)((green << 2U) | (green >> 4U)),
			(uint8_t)((blue << 3U) | (blue >> 2U)),
		};
		if (fwrite(rgb, sizeof(rgb), 1U, file) != 1U) {
			(void)fclose(file);
			return -EIO;
		}
	}

	errno = 0;
	if (fclose(file) != 0) {
		return file_error();
	}
	return 0;
}

static int missing_argument(const char *option)
{
	fprintf(stderr, "%s requires another argument\n", option);
	return 2;
}

int main(int argc, char **argv)
{
	struct toy_factory_simulator simulator;
	int err = toy_factory_simulator_init(&simulator, PICOSYSTEM_GAME_SCENE_HOURGLASS);
	if (err != 0) {
		fprintf(stderr, "could not initialize simulator: %d\n", err);
		return 1;
	}

	const char *output_path = NULL;
	const char *framebuffer_path = NULL;
	uint32_t expected_hash = 0U;
	uint32_t expected_crc = 0U;
	bool check_hash = false;
	bool check_crc = false;

	for (int index = 1; index < argc; ++index) {
		const char *const option = argv[index];
		if (strcmp(option, "--help") == 0) {
			print_usage(stdout, argv[0]);
			return 0;
		}
		if (strcmp(option, "--scene") == 0) {
			if ((index + 1) >= argc) {
				return missing_argument(option);
			}
			enum picosystem_game_scene_id scene_id;
			err = parse_scene(argv[++index], &scene_id);
			if (err == 0) {
				err = toy_factory_simulator_reset(&simulator, scene_id);
			}
			if (err != 0) {
				fprintf(stderr, "invalid scene '%s' (%d)\n", argv[index], err);
				return 2;
			}
			continue;
		}
		if (strcmp(option, "--step") == 0) {
			if ((index + 2) >= argc) {
				return missing_argument(option);
			}
			struct picosystem_game_input input;
			err = parse_input(argv[++index], &input);
			const char *const input_name = argv[index];
			uint32_t tick_count = 0U;
			if (err == 0) {
				err = parse_u32(argv[++index], HOST_SIMULATOR_MAX_STEP_TICKS,
						&tick_count);
			}
			if (err == 0) {
				err = toy_factory_simulator_step(&simulator, &input, tick_count);
			}
			if (err != 0) {
				fprintf(stderr, "invalid step '%s' (%d)\n", input_name, err);
				return 2;
			}
			continue;
		}
		if (strcmp(option, "--action") == 0) {
			if ((index + 1) >= argc) {
				return missing_argument(option);
			}
			enum picosystem_game_scene_action action;
			err = parse_action(argv[++index], &action);
			if (err == 0) {
				err = toy_factory_simulator_apply_action(&simulator, action);
			}
			if (err != 0) {
				fprintf(stderr, "invalid action '%s' (%d)\n", argv[index], err);
				return 2;
			}
			continue;
		}
		if ((strcmp(option, "--output") == 0) || (strcmp(option, "--framebuffer") == 0) ||
		    (strcmp(option, "--expect-hash") == 0) ||
		    (strcmp(option, "--expect-crc") == 0)) {
			if ((index + 1) >= argc) {
				return missing_argument(option);
			}
			const char *const value = argv[++index];
			err = 0;
			if (strcmp(option, "--output") == 0) {
				output_path = value;
			} else if (strcmp(option, "--framebuffer") == 0) {
				framebuffer_path = value;
			} else if (strcmp(option, "--expect-hash") == 0) {
				err = parse_hex32(value, &expected_hash);
				check_hash = err == 0;
			} else {
				err = parse_hex32(value, &expected_crc);
				check_crc = err == 0;
			}
			if (err != 0) {
				fprintf(stderr, "invalid value '%s' for %s\n", value, option);
				return 2;
			}
			continue;
		}

		fprintf(stderr, "unknown option '%s'\n", option);
		print_usage(stderr, argv[0]);
		return 2;
	}

	err = toy_factory_simulator_render(&simulator);
	if (err != 0) {
		fprintf(stderr, "could not render final state: %d\n", err);
		return 1;
	}

	const uint32_t state_hash = toy_factory_simulator_state_hash(&simulator);
	const uint32_t framebuffer_crc = toy_factory_simulator_framebuffer_crc32(&simulator);
	printf("{\"scene\":\"%s\",\"tick\":%" PRIu32 ",\"hash\":\"%08" PRIx32
	       "\",\"framebuffer_crc32\":\"%08" PRIx32 "\"",
	       picosystem_game_scene_name((enum picosystem_game_scene_id)simulator.world.scene_id),
	       simulator.world.logic_tick_count, state_hash, framebuffer_crc);
	if (simulator.world.scene_id == PICOSYSTEM_GAME_SCENE_GARDEN) {
		const struct picosystem_garden_world *const garden = &simulator.world.garden;
		printf(",\"garden\":{\"plants\":%u,\"living\":%u,\"dead\":%u,\"nodes\":%u,"
		       "\"blooms\":%" PRIu32 ",\"deaths\":%" PRIu32 ",\"reclaimed_plants\":%" PRIu32
		       ",\"reclaimed_nodes\":%" PRIu32 ",\"seeds\":%u,\"seeds_created\":%" PRIu32
		       ",\"germinations\":%" PRIu32 ",\"seeds_expired\":%" PRIu32
		       ",\"mutations\":%" PRIu32 ",\"max_generation\":%u,\"moisture\":%u,"
		       "\"lineages\":[",
		       garden->plant_count, picosystem_garden_world_living_plant_count(garden),
		       picosystem_garden_world_dead_plant_count(garden), garden->node_count,
		       garden->bloom_count, garden->death_count, garden->reclaimed_plant_count,
		       garden->reclaimed_node_count, garden->seed_count,
		       garden->seed_creation_count, garden->germination_count,
		       garden->seed_expiration_count, garden->mutation_count,
		       garden->maximum_generation, garden->moisture_total);
		for (uint8_t index = 0U; index < garden->plant_count; ++index) {
			const struct picosystem_garden_plant *const plant = &garden->plants[index];
			printf("%s{\"id\":%" PRIu32 ",\"parent\":%" PRIu32
			       ",\"generation\":%u,\"offspring\":%u,\"species\":%u,"
			       "\"traits\":[%d,%d,%d,%d,%d,%d,%d,%d]}",
			       (index == 0U) ? "" : ",", plant->lineage_id,
			       plant->parent_lineage_id, plant->generation, plant->offspring_count,
			       plant->species_id, plant->genome.growth_rate,
			       plant->genome.shoot_bias, plant->genome.light_seeking,
			       plant->genome.water_seeking, plant->genome.branching,
			       plant->genome.stature, plant->genome.reserve_strategy,
			       plant->genome.dispersal);
		}
		printf("]}");
	}
	puts("}");

	if (output_path != NULL) {
		err = write_ppm(output_path);
	}
	if ((err == 0) && (framebuffer_path != NULL)) {
		err = write_framebuffer(framebuffer_path);
	}
	if (err != 0) {
		fprintf(stderr, "could not write output: %d\n", err);
		return 1;
	}
	if (check_hash && (state_hash != expected_hash)) {
		fprintf(stderr, "state hash mismatch: expected %08" PRIx32 ", got %08" PRIx32 "\n",
			expected_hash, state_hash);
		return 3;
	}
	if (check_crc && (framebuffer_crc != expected_crc)) {
		fprintf(stderr,
			"framebuffer CRC mismatch: expected %08" PRIx32 ", got %08" PRIx32 "\n",
			expected_crc, framebuffer_crc);
		return 3;
	}

	return 0;
}
