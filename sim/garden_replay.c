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

#include "garden_evaluation.h"
#include "garden_light.h"
#include "garden_model_file.h"
#include "garden_policy_probe.h"
#include "game_snapshot.h"
#include "graphics_raster.h"

#define GARDEN_REPLAY_MAX_TICKS 100000U

static int parse_u32(const char *text, uint32_t maximum, uint32_t *value)
{
	if ((text == NULL) || (*text < '0') || (*text > '9')) {
		return -EINVAL;
	}
	errno = 0;
	char *end = NULL;
	const unsigned long parsed = strtoul(text, &end, 0);
	if ((errno != 0) || (*end != '\0') || (parsed > maximum)) {
		return -ERANGE;
	}
	*value = (uint32_t)parsed;
	return 0;
}

static int capture(const struct picosystem_garden_world *world, const char *path,
		   uint32_t *framebuffer_crc)
{
	/* Host-only adapter: never reset via a playable scene or advance its default policy.
	 * The shared raster is process-global, so this executable has one renderer owner.
	 */
	const struct picosystem_game_world render_world = {
		.garden = *world,
		.logic_tick_count = world->logic_tick_count,
		.scene_id = PICOSYSTEM_GAME_SCENE_GARDEN,
	};
	struct picosystem_scene_snapshot snapshot;
	int err = picosystem_game_snapshot_build(&render_world, 1U, 0U,
						 (int64_t)world->logic_tick_count, &snapshot);
	if (err == 0) {
		err = picosystem_scene_render_full(&snapshot);
	}
	if (err != 0) {
		return err;
	}
	if (picosystem_garden_world_hash(&render_world.garden) !=
	    picosystem_garden_world_hash(world)) {
		return -EFAULT;
	}
	*framebuffer_crc = picosystem_graphics_raster_crc32();
	FILE *const stream = fopen(path, "wbx");
	if (stream == NULL) {
		return errno != 0 ? -errno : -EIO;
	}
	const size_t length = picosystem_graphics_raster_byte_count();
	const size_t written = fwrite(picosystem_graphics_raster_bytes(), 1U, length, stream);
	const int closed = fclose(stream);
	return ((written == length) && (closed == 0)) ? 0 : -EIO;
}

static int print_result(const struct picosystem_garden_world *world, const char *scenario,
			const char *policy, uint32_t seed, const uint32_t *model_crc,
			const uint32_t *framebuffer_crc)
{
	uint8_t descendants = 0U;
	for (uint8_t index = 0U; index < world->plant_count; ++index) {
		const struct picosystem_garden_plant *const plant = &world->plants[index];
		if ((plant->generation != 0U) &&
		    ((plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) == 0U)) {
			++descendants;
		}
	}
	const struct picosystem_garden_sun sun =
		picosystem_garden_sun_at(world->ecology_tick_count);
	printf("{\"schema_version\":1,\"scenario\":\"%s\",\"policy\":\"%s\","
	       "\"seed\":\"%08" PRIx32 "\",\"tick\":%" PRIu32 ",\"hash\":\"%08" PRIx32
	       "\",\"sun_phase\":%u,\"sun_strength\":%u,\"rain_rate\":%u,"
	       "\"rain_deposited\":%" PRIu32 ",\"rain_runoff\":%" PRIu32
	       ",\"living\":%u,\"descendants\":%u,\"plant_slots\":%u,\"nodes\":%u,"
	       "\"seed_bank\":%u,\"births\":%" PRIu32 ",\"deaths\":%" PRIu32
	       ",\"moisture\":%u,\"model_crc32\":",
	       scenario, policy, seed, world->logic_tick_count, picosystem_garden_world_hash(world),
	       sun.phase, sun.strength,
	       picosystem_garden_rain_at(world->weather_seed, world->ecology_tick_count),
	       world->rain_deposited, world->rain_runoff,
	       picosystem_garden_world_living_plant_count(world), descendants, world->plant_count,
	       world->node_count, world->seed_count, world->germination_count, world->death_count,
	       world->moisture_total);
	if (model_crc != NULL) {
		printf("\"%08" PRIx32 "\"", *model_crc);
	} else {
		printf("null");
	}
	printf(",\"framebuffer_crc32\":");
	if (framebuffer_crc != NULL) {
		printf("\"%08" PRIx32 "\"", *framebuffer_crc);
	} else {
		printf("null");
	}
#if defined(TOY_FACTORY_GARDEN_WIDE_DISPERSAL)
	printf(",\"seed_dispersal\":\"%s\"", PICOSYSTEM_GARDEN_DISPERSAL_NAME);
#endif
#if defined(TOY_FACTORY_GARDEN_WATER_HEADROOM)
	printf(",\"water_uptake\":\"%s\"", PICOSYSTEM_GARDEN_WATER_UPTAKE_NAME);
#endif
	printf("}\n");
	return ((fflush(stdout) == 0) && !ferror(stdout)) ? 0 : -EIO;
}

int main(int argc, char **argv)
{
	if (argc < 7) {
		const bool help = (argc == 2) && (strcmp(argv[1], "--help") == 0);
		fprintf(help ? stdout : stderr,
			"Usage: %s MODEL SCENARIO POLICY WORLD_SEED --ticks 0-100000 "
			"[--framebuffer NEW_PATH]\n"
			"SCENARIO: rainfed or rainfed-crowded. MODEL must be '-' for\n"
			"baseline, adaptive, neural-reference; a model file for neural-candidate\n"
			"or neural-no-night-growth (host-only no-night-growth-v1 probe).\n"
			"Without --framebuffer, replay is headless (no rasterization).\n",
			argv[0]);
		return help ? 0 : 2;
	}
	uint32_t ticks = 0U;
	uint32_t seed;
	bool ticks_seen = false;
	const char *framebuffer = NULL;
	for (int index = 5; index < argc; index += 2) {
		if ((index + 1) >= argc) {
			return 2;
		}
		if ((strcmp(argv[index], "--ticks") == 0) && !ticks_seen) {
			if (parse_u32(argv[index + 1], GARDEN_REPLAY_MAX_TICKS, &ticks) != 0) {
				return 2;
			}
			ticks_seen = true;
		} else if ((strcmp(argv[index], "--framebuffer") == 0) && (framebuffer == NULL) &&
			   (*argv[index + 1] != '\0')) {
			framebuffer = argv[index + 1];
		} else {
			return 2;
		}
	}
	if (!ticks_seen || (parse_u32(argv[4], UINT32_MAX, &seed) != 0) || (seed == 0U)) {
		return 2;
	}
	const struct toy_factory_garden_evaluation_scenario *scenario = NULL;
	for (size_t index = 0U; index < TOY_FACTORY_GARDEN_RAINFED_SCENARIO_COUNT; ++index) {
		if (strcmp(argv[2], toy_factory_garden_rainfed_scenarios[index].name) == 0) {
			scenario = &toy_factory_garden_rainfed_scenarios[index];
		}
	}
	if (scenario == NULL) {
		return 2;
	}
	struct picosystem_garden_neural_model model;
	struct picosystem_garden_agent_policy neural_policy;
	struct picosystem_garden_agent_policy probe_policy;
	const struct picosystem_garden_agent_policy *policy = NULL;
	uint32_t model_crc = 0U;
	bool has_model = false;
	int err = 0;
	const bool probe = strcmp(argv[3], TOY_FACTORY_GARDEN_NIGHT_PROBE_POLICY) == 0;
	if ((strcmp(argv[3], "neural-candidate") == 0) || probe) {
		err = toy_factory_garden_model_read(argv[1], &model, &model_crc);
		if (err == 0) {
			err = picosystem_garden_neural_policy_init(&model, &neural_policy);
		}
		policy = &neural_policy;
		has_model = true;
		if ((err == 0) && probe) {
			err = toy_factory_garden_no_night_growth_init(&neural_policy,
								      &probe_policy);
			policy = &probe_policy;
		}
	} else if (strcmp(argv[1], "-") != 0) {
		return 2;
	} else if (strcmp(argv[3], "adaptive") == 0) {
		policy = picosystem_garden_agent_adaptive_policy();
	} else if (strcmp(argv[3], "baseline") == 0) {
		policy = picosystem_garden_agent_baseline_policy();
	} else if (strcmp(argv[3], "neural-reference") == 0) {
		policy = picosystem_garden_agent_neural_reference_policy();
		has_model = true;
		err = toy_factory_garden_model_fingerprint(
			picosystem_garden_neural_reference_model(), &model_crc);
	} else {
		return 2;
	}
	struct picosystem_garden_world world;
	if (err == 0) {
		err = toy_factory_garden_evaluation_reset(&world, scenario, seed);
	}
	if (err == 0) {
		err = toy_factory_garden_evaluation_advance(&world, scenario, policy, ticks, NULL,
							    NULL);
	}
	uint32_t framebuffer_crc = 0U;
	if ((err == 0) && (framebuffer != NULL)) {
		const uint32_t before = picosystem_garden_world_hash(&world);
		err = capture(&world, framebuffer, &framebuffer_crc);
		if ((err == 0) && (picosystem_garden_world_hash(&world) != before)) {
			err = -EFAULT;
		}
	}
	if (err == 0) {
		err = print_result(&world, scenario->name, argv[3], seed,
				   has_model ? &model_crc : NULL,
				   framebuffer != NULL ? &framebuffer_crc : NULL);
	}
	if (err != 0) {
		fprintf(stderr, "Garden replay failed (%d)\n", err);
		return 1;
	}
	return 0;
}
