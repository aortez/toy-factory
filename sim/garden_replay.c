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
#include "garden_reserve_policy.h"
#include "garden_root_bootstrap.h"
#include "garden_focal_policy.h"
#include "game_snapshot.h"
#include "graphics_raster.h"
static uint32_t root_bootstrap_after;
static uint32_t focal_founder;
#if defined(TOY_FACTORY_GARDEN_SEED_ORDER)
static bool seed_order_rotating;
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_SPACING)
static bool seed_spacing_two;
#endif
#if defined(TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION)
static bool canopy_transmission_enabled;
#endif
#if defined(TOY_FACTORY_GARDEN_FULL_POOL)
static bool full_pool_enabled;
#endif
#if defined(TOY_FACTORY_GARDEN_PLANT_SLOTS)
static bool plant_slots_sixteen;
#endif
#if defined(TOY_FACTORY_GARDEN_DAWN_FINISH)
static struct picosystem_garden_dawn_finish dawn_finish;
#endif
#if defined(TOY_FACTORY_GARDEN_PURCHASE_VETO)
static enum picosystem_garden_purchase_selection purchase_selection;
#endif
static uint32_t focal_model_crc;
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
#include "garden_leaf_policies.h"
#include "garden_gap.h"
#include "garden_disturbance.h"
#include "garden_founder_exit.h"
static const char *leaf_policy_name = "none";
static uint32_t gap_tick;
static uint32_t gap_lineage;
static struct toy_factory_garden_gap gap_result;
static uint32_t disturbance_seed;
static struct toy_factory_garden_disturbance_totals disturbance_totals;
static uint32_t founder_exit_tick;
static struct toy_factory_garden_founder_exit founder_exit_result;
#endif

#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
#define GARDEN_REPLAY_MAX_TICKS TOY_FACTORY_GARDEN_DISTURBANCE_MAX_TICKS
#else
#define GARDEN_REPLAY_MAX_TICKS 100000U
#endif

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
	putchar('{');
#if defined(TOY_FACTORY_GARDEN_FULL_POOL)
	const int full_pool_err =
		picosystem_garden_full_pool_print(&world->full_pool, world->logic_tick_count);
	if (full_pool_err != 0) {
		return full_pool_err;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_PLANT_SLOTS)
	const int slots_err = picosystem_garden_plant_slots_print(world->plant_slots_sixteen,
								  world->logic_tick_count);
	if (slots_err != 0) {
		return slots_err;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION)
	const int transmission_err = picosystem_garden_canopy_transmission_print(
		world->canopy_transmission_enabled, world->logic_tick_count);
	if (transmission_err != 0) {
		return transmission_err;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_SPACING)
	const int spacing_err = picosystem_garden_seed_spacing_print(world->seed_spacing_two,
								     world->logic_tick_count);
	if (spacing_err != 0) {
		return spacing_err;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_ORDER)
	const int order_err = picosystem_garden_seed_order_print(
		world->seed_order_rotating, world->logic_tick_count, world->plant_count);
	if (order_err != 0) {
		return order_err;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_DAWN_FINISH)
	const int dawn_err =
		picosystem_garden_dawn_finish_print(&world->dawn_finish, world->logic_tick_count);
	if (dawn_err != 0) {
		return dawn_err;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_WET_GERMINATION)
	if (world->wet_germination_enabled) {
		printf("\"germination_rule\":\"%s\",", PICOSYSTEM_GARDEN_WET_GERMINATION_NAME);
	}
#endif
#if defined(TOY_FACTORY_GARDEN_NIGHT_CAPACITY)
	const int capacity_err = picosystem_garden_night_print(&world->night_capacity);
	if (capacity_err != 0) {
		return capacity_err;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_PURCHASE_VETO)
	const int purchase_err =
		picosystem_garden_purchase_print(&world->purchase_veto, world->logic_tick_count);
	if (purchase_err != 0) {
		return purchase_err;
	}
#endif
	printf("\"schema_version\":1,\"scenario\":\"%s\",\"policy\":\"%s\","
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
	if (focal_founder != 0U) {
		printf(",\"focal_policy\":{\"rule\":\"%s\",\"founder\":%" PRIu32
		       ",\"model_crc32\":\"%08" PRIx32 "\"}",
		       TOY_FACTORY_GARDEN_FOCAL_POLICY_RULE, focal_founder, focal_model_crc);
	}
#if defined(TOY_FACTORY_GARDEN_FOCAL_SEED_VETO)
	printf(",\"seed_veto_rule\":\"%s\"", PICOSYSTEM_GARDEN_FOCAL_SEED_VETO_NAME);
#endif
#if defined(TOY_FACTORY_GARDEN_DARK_GUARD)
	printf(",\"dark_guard_rule\":\"%s\"", PICOSYSTEM_GARDEN_DARK_GUARD_NAME);
#endif
#if defined(TOY_FACTORY_GARDEN_WIDE_DISPERSAL)
	printf(",\"seed_dispersal\":\"%s\"", PICOSYSTEM_GARDEN_DISPERSAL_NAME);
#endif
#if defined(TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE)
	printf(",\"drainage_rule\":\"%s\"", PICOSYSTEM_GARDEN_DRAINAGE_NAME);
#endif
#if defined(TOY_FACTORY_GARDEN_WATER_HEADROOM)
	printf(",\"water_uptake\":\"%s\"", PICOSYSTEM_GARDEN_WATER_UPTAKE_NAME);
#endif
#if defined(TOY_FACTORY_GARDEN_LARGE_POOL)
	printf(",\"node_capacity\":%u", PICOSYSTEM_GARDEN_MAX_NODES);
#endif
#if defined(TOY_FACTORY_GARDEN_LARGE_SEED_BANK)
	printf(",\"seed_capacity\":%u", PICOSYSTEM_GARDEN_MAX_SEEDS);
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_RESERVE)
	printf(",\"seed_reserve_rule\":\"%s\"", PICOSYSTEM_GARDEN_SEED_RESERVE_NAME);
#endif
	if (root_bootstrap_after != 0U) {
		printf(",\"root_bootstrap_rule\":\"%s\",\"root_bootstrap_after\":%" PRIu32,
		       TOY_FACTORY_GARDEN_ROOT_BOOTSTRAP_RULE, root_bootstrap_after);
	}
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	printf(",\"leaf_environment\":\"%s\",\"leaf_policy\":\"%s\"",
	       PICOSYSTEM_GARDEN_LEAF_ENVIRONMENT, leaf_policy_name);
	if (gap_tick != 0U) {
		printf(",\"gap_protocol\":\"%s\",\"gap_tick\":%" PRIu32 ",\"removed_id\":%" PRIu32,
		       gap_result.named ? TOY_FACTORY_GARDEN_NAMED_GAP_PROTOCOL
					: TOY_FACTORY_GARDEN_GAP_PROTOCOL,
		       gap_tick, gap_result.lineage_id);
	}
	if (disturbance_seed != 0U) {
		printf(",\"disturbance_protocol\":\"%s\",\"disturbance_seed\":\"%08" PRIx32
		       "\",\"disturbance_events\":%" PRIu32 ",\"environmental_deaths\":%" PRIu32,
		       TOY_FACTORY_GARDEN_DISTURBANCE_PROTOCOL, disturbance_seed,
		       disturbance_totals.events, disturbance_totals.killed);
	}
	if (founder_exit_tick != 0U) {
		printf(",\"founder_exit\":");
		const int printed = toy_factory_garden_founder_exit_print(&founder_exit_result);
		if (printed != 0) {
			return printed;
		}
	}
#endif
	printf("}\n");
	return ((fflush(stdout) == 0) && !ferror(stdout)) ? 0 : -EIO;
}

int main(int argc, char **argv)
{
	if (argc < 7) {
		const bool help = (argc == 2) && (strcmp(argv[1], "--help") == 0);
		fprintf(help ? stdout : stderr,
			"Usage: %s MODEL SCENARIO POLICY WORLD_SEED --ticks 0-%u "
			"[--framebuffer NEW_PATH]\n"
			"SCENARIO: rainfed or rainfed-crowded. MODEL must be '-' for\n"
			"baseline, adaptive, neural-reference; a model file for neural-candidate\n"
			"or neural-no-night-growth (host-only no-night-growth-v1 probe).\n"
			"Without --framebuffer, replay is headless (no rasterization).\n",
			argv[0], GARDEN_REPLAY_MAX_TICKS);
		fprintf(help ? stdout : stderr,
			"adaptive-no-night-growth uses MODEL '-' and the same night veto.\n");
		fprintf(help ? stdout : stderr,
			"neural-reserve-growth uses MODEL with energy-reserve-v1.\n");
		fprintf(help ? stdout : stderr,
			"--focal-model MODEL --focal-founder ID: route only that reset founder; "
			"requires neural-no-night-growth, no other overrides.\n");
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
		fprintf(help ? stdout : stderr,
			"--leaf-policy none|all|selective (default none)\n"
			"--gap-at TICK: host-only one-time largest-adult "
			"export; ecology boundary\n"
			"--gap-lineage ID: with --gap-at, export this adult instead; permits focal "
			"routing\n"
			"--disturbance-seed SEED: recurring host-only patch deaths\n"
			"--founder-exit TICK: kill living founders once; requires patch schedule\n"
			"--root-bootstrap-after TICK: explicit wet-root bootstrap for later "
			"offspring\n");
#endif
#if defined(TOY_FACTORY_GARDEN_PURCHASE_VETO)
		fprintf(help ? stdout : stderr,
			"--purchase-veto extension|finish|finish-retry: fixed host diagnostic\n");
#endif
#if defined(TOY_FACTORY_GARDEN_DAWN_FINISH)
		fprintf(help ? stdout : stderr,
			"--dawn-finish defer|reserve: fixed wet-world seedling diagnostic\n");
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_ORDER)
		fprintf(help ? stdout : stderr,
			"--seed-order rotating: post-noon purchase rotation; requires reserve\n");
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_SPACING)
		fprintf(help ? stdout : stderr,
			"--seed-spacing 2: post-noon spacing; requires rotating seed order\n");
#endif
#if defined(TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION)
		fprintf(help ? stdout : stderr,
			"--canopy-transmission fractional: post-noon optics; requires spacing 2\n");
#endif
#if defined(TOY_FACTORY_GARDEN_FULL_POOL)
		fprintf(help ? stdout : stderr, "--full-pool nonallocating: post-noon full-pool "
						"actions; requires plant-slots 16\n");
#endif
#if defined(TOY_FACTORY_GARDEN_PLANT_SLOTS)
		fprintf(help ? stdout : stderr,
			"--plant-slots 16: post-noon admission; requires fractional canopy\n");
#endif
		return help ? 0 : 2;
	}
	uint32_t ticks = 0U;
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	uint32_t wet_tick = 0U;
#endif
	uint32_t seed;
	bool ticks_seen = false;
	const char *framebuffer = NULL;
	const char *focal_model_path = NULL;
	for (int index = 5; index < argc; index += 2) {
		if ((index + 1) >= argc) {
			return 2;
		}
#if defined(TOY_FACTORY_GARDEN_FULL_POOL)
		if (strcmp(argv[index], "--full-pool") == 0) {
			if (picosystem_garden_full_pool_parse(argv[index + 1],
							      &full_pool_enabled) != 0) {
				return 2;
			}
			continue;
		}
#endif
#if defined(TOY_FACTORY_GARDEN_PLANT_SLOTS)
		if (strcmp(argv[index], "--plant-slots") == 0) {
			if ((picosystem_garden_plant_slots_parse(argv[index + 1],
								 &plant_slots_sixteen) != 0)) {
				return 2;
			}
			continue;
		}
#endif
#if defined(TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION)
		if (strcmp(argv[index], "--canopy-transmission") == 0) {
			if (picosystem_garden_canopy_transmission_parse(
				    argv[index + 1], &canopy_transmission_enabled) != 0) {
				return 2;
			}
			continue;
		}
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_SPACING)
		if (strcmp(argv[index], "--seed-spacing") == 0) {
			if (picosystem_garden_seed_spacing_parse(argv[index + 1],
								 &seed_spacing_two) != 0) {
				return 2;
			}
			continue;
		}
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_ORDER)
		if (strcmp(argv[index], "--seed-order") == 0) {
			if (picosystem_garden_seed_order_parse(argv[index + 1],
							       &seed_order_rotating) != 0) {
				return 2;
			}
			continue;
		}
#endif
#if defined(TOY_FACTORY_GARDEN_DAWN_FINISH)
		if (strcmp(argv[index], "--dawn-finish") == 0) {
			if (picosystem_garden_dawn_finish_parse(argv[index + 1], &dawn_finish) !=
			    0) {
				return 2;
			}
			continue;
		}
#endif
#if defined(TOY_FACTORY_GARDEN_WET_GERMINATION)
		if (strcmp(argv[index], "--wet-germination-after") == 0) {
			if ((wet_tick != 0U) ||
			    (parse_u32(argv[index + 1], GARDEN_REPLAY_MAX_TICKS, &wet_tick) != 0) ||
			    (wet_tick == 0U)) {
				return 2;
			}
			continue;
		}
#endif
#if defined(TOY_FACTORY_GARDEN_PURCHASE_VETO)
		if (strcmp(argv[index], "--purchase-veto") == 0) {
			if (picosystem_garden_purchase_parse(argv[index + 1],
							     &purchase_selection) != 0) {
				return 2;
			}
			continue;
		}
#endif
		if (strcmp(argv[index], "--focal-model") == 0) {
			if ((focal_model_path != NULL) || (*argv[index + 1] == '\0')) {
				return 2;
			}
			focal_model_path = argv[index + 1];
			continue;
		}
		if (strcmp(argv[index], "--focal-founder") == 0) {
			if ((focal_founder != 0U) ||
			    (parse_u32(argv[index + 1], UINT32_MAX, &focal_founder) != 0) ||
			    (focal_founder == 0U)) {
				return 2;
			}
			continue;
		}
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
		if (strcmp(argv[index], "--founder-exit") == 0) {
			if ((founder_exit_tick != 0U) ||
			    (parse_u32(argv[index + 1], GARDEN_REPLAY_MAX_TICKS,
				       &founder_exit_tick) != 0) ||
			    (founder_exit_tick == 0U)) {
				return 2;
			}
			continue;
		}
		if (strcmp(argv[index], "--root-bootstrap-after") == 0) {
			if ((root_bootstrap_after != 0U) ||
			    (parse_u32(argv[index + 1], GARDEN_REPLAY_MAX_TICKS,
				       &root_bootstrap_after) != 0) ||
			    (root_bootstrap_after == 0U)) {
				return 2;
			}
			continue;
		}
		if (strcmp(argv[index], "--disturbance-seed") == 0) {
			if ((disturbance_seed != 0U) ||
			    (parse_u32(argv[index + 1], UINT32_MAX, &disturbance_seed) != 0) ||
			    (disturbance_seed == 0U)) {
				return 2;
			}
			continue;
		}
		if (strcmp(argv[index], "--gap-lineage") == 0) {
			if ((gap_lineage != 0U) ||
			    (parse_u32(argv[index + 1], UINT32_MAX, &gap_lineage) != 0) ||
			    (gap_lineage == 0U)) {
				return 2;
			}
			continue;
		}
		if (strcmp(argv[index], "--gap-at") == 0) {
			if ((gap_tick != 0U) ||
			    (parse_u32(argv[index + 1], GARDEN_REPLAY_MAX_TICKS, &gap_tick) != 0) ||
			    (gap_tick == 0U)) {
				return 2;
			}
			continue;
		}
		if (strcmp(argv[index], "--leaf-policy") == 0) {
			if (toy_factory_garden_leaf_policy(argv[index + 1]) == NULL) {
				return 2;
			}
			leaf_policy_name = argv[index + 1];
			continue;
		}
#endif
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
	if (((focal_model_path != NULL) != (focal_founder != 0U)) ||
	    ((focal_founder != 0U) &&
	     ((strcmp(argv[3], TOY_FACTORY_GARDEN_NIGHT_PROBE_POLICY) != 0) ||
	      (root_bootstrap_after != 0U)))) {
		return 2;
	}
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	if (((wet_tick != 0U) && ((wet_tick != gap_tick) || (gap_lineage == 0U))) ||
	    ((gap_lineage != 0U) && (gap_tick == 0U)) ||
	    ((focal_founder != 0U) &&
	     (((gap_tick != 0U) && (gap_lineage == 0U)) || (founder_exit_tick != 0U)))) {
		return 2;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_DAWN_FINISH)
	if (dawn_finish.enabled &&
	    ((wet_tick != 46080U) || (gap_lineage != 1U) || (focal_founder != 5U) ||
	     (strcmp(leaf_policy_name, "selective") != 0))) {
		return 2;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_ORDER)
	if (seed_order_rotating && !dawn_finish.reserve_handoff) {
		return 2;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_SPACING)
	if (seed_spacing_two && !seed_order_rotating) {
		return 2;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION)
	if (canopy_transmission_enabled && !seed_spacing_two) {
		return 2;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_FULL_POOL)
	if (full_pool_enabled && !plant_slots_sixteen) {
		return 2;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_PLANT_SLOTS)
	if (plant_slots_sixteen && !canopy_transmission_enabled) {
		return 2;
	}
#endif
	if (root_bootstrap_after != 0U) {
#if defined(TOY_FACTORY_GARDEN_LARGE_POOL) && defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE) &&      \
	!defined(TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE)
		if ((root_bootstrap_after > ticks) ||
		    ((root_bootstrap_after % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) != 0U) ||
		    (disturbance_seed == 0U) || (gap_tick != 0U) ||
		    ((strcmp(argv[3], TOY_FACTORY_GARDEN_NIGHT_PROBE_POLICY) != 0) &&
		     (strcmp(argv[3], TOY_FACTORY_GARDEN_RESERVE_POLICY) != 0))) {
			return 2;
		}
#else
		return 2;
#endif
	}
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	if ((gap_tick > ticks) || (gap_tick % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR != 0U) ||
	    ((gap_tick != 0U) && (disturbance_seed != 0U))) {
		return 2;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	if ((founder_exit_tick != 0U) &&
	    ((founder_exit_tick > ticks) || (founder_exit_tick % 15U != 0U) ||
	     (disturbance_seed == 0U) || (gap_tick != 0U) || (root_bootstrap_after != 0U))) {
		return 2;
	}
#endif
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
	struct picosystem_garden_agent_policy reserve_policy;
	const struct picosystem_garden_agent_policy *policy = NULL;
	uint32_t model_crc = 0U;
	bool has_model = false;
	int err = 0;
	const bool reserve_probe = strcmp(argv[3], TOY_FACTORY_GARDEN_RESERVE_POLICY) == 0;
	const bool probe =
		(strcmp(argv[3], TOY_FACTORY_GARDEN_NIGHT_PROBE_POLICY) == 0) || reserve_probe;
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
		if ((err == 0) && reserve_probe) {
			err = toy_factory_garden_reserve_init(&probe_policy, &reserve_policy);
			policy = &reserve_policy;
		}
	} else if (strcmp(argv[1], "-") != 0) {
		return 2;
	} else if (strcmp(argv[3], TOY_FACTORY_GARDEN_ADAPTIVE_NIGHT_POLICY) == 0) {
		err = toy_factory_garden_no_night_growth_init(
			picosystem_garden_agent_adaptive_policy(), &probe_policy);
		policy = &probe_policy;
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
	struct picosystem_garden_agent_policy root_policy;
	struct toy_factory_garden_root_bootstrap_context root_context;
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	struct picosystem_garden_agent_policy maintained_policy = {0};
	if (err == 0) {
		maintained_policy = *policy;
		maintained_policy.leaf_policy = toy_factory_garden_leaf_policy(leaf_policy_name);
		policy = &maintained_policy;
	}
#endif
	if ((err == 0) && (root_bootstrap_after != 0U)) {
		err = toy_factory_garden_root_bootstrap_init(policy, &world, root_bootstrap_after,
							     &root_context, &root_policy);
		policy = &root_policy;
	}
	if (err == 0) {
		err = toy_factory_garden_evaluation_reset(&world, scenario, seed);
	}
	struct picosystem_garden_neural_model focal_model;
	struct picosystem_garden_agent_policy focal_neural, focal_probe, routed;
	struct toy_factory_garden_focal_context focal_context;
	if ((err == 0) && (focal_founder != 0U)) {
		err = toy_factory_garden_model_read(focal_model_path, &focal_model,
						    &focal_model_crc);
		if (err == 0) {
			err = picosystem_garden_neural_policy_init(&focal_model, &focal_neural);
		}
		if (err == 0) {
			err = toy_factory_garden_no_night_growth_init(&focal_neural, &focal_probe);
		}
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
		if (err == 0) {
			focal_probe.leaf_policy = policy->leaf_policy;
		}
#endif
		if (err == 0) {
			err = toy_factory_garden_focal_policy_init(&world, policy, &focal_probe,
								   focal_founder, &focal_context,
								   &routed);
		}
		if (err == 0) {
			policy = &routed;
		}
	}
#if defined(TOY_FACTORY_GARDEN_PURCHASE_VETO)
	world.purchase_veto.selection = purchase_selection;
#endif
#if defined(TOY_FACTORY_GARDEN_DAWN_FINISH)
	world.dawn_finish = dawn_finish;
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_ORDER)
	world.seed_order_rotating = seed_order_rotating;
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_SPACING)
	world.seed_spacing_two = seed_spacing_two;
#endif
#if defined(TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION)
	world.canopy_transmission_enabled = canopy_transmission_enabled;
#endif
#if defined(TOY_FACTORY_GARDEN_FULL_POOL)
	world.full_pool.enabled = full_pool_enabled;
#endif
#if defined(TOY_FACTORY_GARDEN_PLANT_SLOTS)
	world.plant_slots_sixteen = plant_slots_sixteen;
#endif
	if (err == 0) {
		uint32_t first_ticks = ticks;
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
		if (gap_tick != 0U) {
			first_ticks = gap_tick;
		}
		if (founder_exit_tick != 0U) {
			first_ticks = founder_exit_tick;
		}
#endif
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
		if (disturbance_seed != 0U) {
			err = toy_factory_garden_disturbance_advance(
				&world, scenario, policy, first_ticks, disturbance_seed, NULL, NULL,
				NULL, &disturbance_totals);
		} else
#endif
		{
			err = toy_factory_garden_evaluation_advance(&world, scenario, policy,
								    first_ticks, NULL, NULL);
		}
	}
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	if ((err == 0) && (founder_exit_tick != 0U)) {
		err = toy_factory_garden_founder_exit_apply(&world, &founder_exit_result);
		if (err == 0) {
			err = toy_factory_garden_disturbance_advance(
				&world, scenario, policy, ticks, disturbance_seed, NULL, NULL, NULL,
				&disturbance_totals);
		}
	}
	if ((err == 0) && (gap_tick != 0U)) {
		err = gap_lineage != 0U
			      ? toy_factory_garden_gap_apply_named(&world, gap_lineage, &gap_result)
			      : toy_factory_garden_gap_apply(&world, &gap_result);
#if defined(TOY_FACTORY_GARDEN_WET_GERMINATION)
		if ((err == 0) && (wet_tick != 0U)) {
			err = picosystem_garden_world_enable_wet_germination(&world);
		}
#endif
		if (err == 0) {
			err = toy_factory_garden_evaluation_advance(&world, scenario, policy,
								    ticks - gap_tick, NULL, NULL);
		}
	}
#endif
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
