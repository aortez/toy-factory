/* SPDX-License-Identifier: Apache-2.0 */
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "garden_seed_audit.h"
#include "garden_disturbance.h"
#include "garden_leaf_policies.h"
#include "garden_light.h"
#include "garden_model_file.h"
#include "garden_policy_probe.h"
#include "garden_reserve_policy.h"
#include "garden_focal_policy.h"
#include "garden_gap.h"
#if defined(TOY_FACTORY_GARDEN_WET_GERMINATION)
#include "garden_wet_germination.h"
#endif

static int parse_u32(const char *text, uint32_t *value)
{
	if ((*text < '0') || (*text > '9')) {
		return -EINVAL;
	}
	errno = 0;
	char *end;
	const unsigned long parsed = strtoul(text, &end, 0);
	if ((errno != 0) || (*end != '\0') || (parsed > UINT32_MAX)) {
		return -EINVAL;
	}
	*value = (uint32_t)parsed;
	return 0;
}

static void print_sites(const uint8_t *sites)
{
	putchar('[');
	for (unsigned int i = 0U; i < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++i) {
		printf("%s%u", i ? "," : "", sites[i]);
	}
	putchar(']');
}

static int print_step(const struct picosystem_garden_world *world,
		      const struct picosystem_garden_seed_audit *audit)
{
	const struct picosystem_garden_sun sun =
		picosystem_garden_sun_at(world->ecology_tick_count);
	printf("{\"type\":\"seed-step\",\"tick\":%" PRIu32 ",\"hash\":\"%08" PRIx32
	       "\",\"sun_phase\":%u,\"sun_strength\":%u,\"nodes\":%u,\"plants\":%u,"
	       "\"seeds\":%u,\"births\":%" PRIu32 ",\"expired\":%" PRIu32 ",\"created\":%" PRIu32
	       ",\"stages\":[",
	       world->logic_tick_count, picosystem_garden_world_hash(world), sun.phase,
	       sun.strength, world->node_count, world->plant_count, world->seed_count,
	       world->germination_count, world->seed_expiration_count, world->seed_creation_count);
	if (audit != NULL) {
		for (unsigned int i = 0U; i < PICOSYSTEM_GARDEN_SEED_STAGE_COUNT; ++i) {
			const struct picosystem_garden_seed_inventory *s = &audit->stages[i];
			printf("%s[%u,%u,%u]", i ? "," : "", s->nodes, s->plants, s->seeds);
		}
	}
	printf("],\"sites_before\":");
	if (audit != NULL) {
		print_sites(audit->sites_before);
	} else {
		printf("[]");
	}
	printf(",\"attempts\":[");
	for (uint8_t i = 0U; (audit != NULL) && (i < audit->count); ++i) {
		const struct picosystem_garden_seed_attempt *a = &audit->attempts[i];
		printf("%s{\"parent\":%" PRIu32 ",\"child\":%" PRIu32
		       ",\"age\":%u,\"generation\":%u,\"column\":%u,\"species\":%u,"
		       "\"nodes\":%u,\"plants\":%u,\"moisture\":%u,\"light\":%u,"
		       "\"blockers\":%u,\"outcome\":%u,\"sites\":",
		       i ? "," : "", a->parent, a->child, a->age, a->generation, a->column,
		       a->species, a->nodes, a->plants, a->moisture, a->light, a->blockers,
		       a->outcome);
		print_sites(a->sites);
		putchar('}');
	}
	putchar(']');
#if defined(TOY_FACTORY_GARDEN_WET_GERMINATION)
	if (world->wet_germination_enabled) {
		printf(",\"germination_rule\":\"%s\"", PICOSYSTEM_GARDEN_WET_GERMINATION_NAME);
	}
#endif
	printf("}\n");
	return ferror(stdout) ? -EIO : 0;
}

int main(int argc, char **argv)
{
	uint32_t seed, schedule, from, ticks;
	if ((argc < 8) || (parse_u32(argv[4], &seed) != 0) || (seed == 0U) ||
	    (parse_u32(argv[5], &schedule) != 0) || (parse_u32(argv[6], &from) != 0) ||
	    (parse_u32(argv[7], &ticks) != 0) || (from >= ticks) ||
	    (ticks > TOY_FACTORY_GARDEN_DISTURBANCE_MAX_TICKS) || ((from % 15U) != 0U) ||
	    ((ticks % 15U) != 0U)) {
		fprintf(stderr,
			"Usage: %s MODEL RAINFED_SCENARIO POLICY WORLD_SEED "
			"SCHEDULE_OR_ZERO FROM_TICK END_TICK "
			"[--focal-model MODEL --focal-founder ID] "
			"[--gap-at TICK --gap-lineage ID]\n"
			"In-window exports have explicit post-export snapshots; no recurring "
			"patches with "
			"export or focal routing. Focal routing requires neural-no-night-growth.\n",
			argv[0]);
		return 2;
	}
	const bool reserve = strcmp(argv[3], TOY_FACTORY_GARDEN_RESERVE_POLICY) == 0;
	if (!reserve && (strcmp(argv[3], TOY_FACTORY_GARDEN_NIGHT_PROBE_POLICY) != 0)) {
		return 2;
	}
	const char *focal_path = NULL;
	uint32_t focal_founder = 0U, gap_tick = 0U, gap_lineage = 0U, wet_tick = 0U;
	for (int i = 8; i < argc; ++i) {
		if (strcmp(argv[i], "--focal-model") == 0) {
			if ((focal_path != NULL) || (++i >= argc) || (*argv[i] == '\0')) {
				return 2;
			}
			focal_path = argv[i];
			continue;
		}
		uint32_t *value = NULL;
		if (strcmp(argv[i], "--focal-founder") == 0) {
			value = &focal_founder;
		} else if (strcmp(argv[i], "--gap-at") == 0) {
			value = &gap_tick;
		} else if (strcmp(argv[i], "--gap-lineage") == 0) {
			value = &gap_lineage;
		}
#if defined(TOY_FACTORY_GARDEN_WET_GERMINATION)
		else if (strcmp(argv[i], "--wet-germination-after") == 0) {
			value = &wet_tick;
		}
#endif
		if ((value == NULL) || (*value != 0U) || (++i >= argc) ||
		    (parse_u32(argv[i], value) != 0) || (*value == 0U)) {
			return 2;
		}
	}
	if (((focal_path != NULL) != (focal_founder != 0U)) ||
	    ((wet_tick != 0U) && ((wet_tick != gap_tick) || (gap_lineage == 0U))) ||
	    ((gap_tick != 0U) != (gap_lineage != 0U)) ||
	    ((focal_founder != 0U) && (reserve || (schedule != 0U))) ||
	    ((gap_tick != 0U) && ((schedule != 0U) || (gap_tick > ticks) ||
				  ((gap_tick % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) != 0U)))) {
		return 2;
	}
	const struct toy_factory_garden_evaluation_scenario *scenario = NULL;
	for (unsigned int i = 0U; i < TOY_FACTORY_GARDEN_RAINFED_SCENARIO_COUNT; ++i) {
		if (strcmp(argv[2], toy_factory_garden_rainfed_scenarios[i].name) == 0) {
			scenario = &toy_factory_garden_rainfed_scenarios[i];
		}
	}
	if ((scenario == NULL) || (scenario->irrigation_period_ticks != 0U)) {
		return 2;
	}
	struct picosystem_garden_neural_model model;
	struct picosystem_garden_agent_policy base, night, policy;
	uint32_t crc;
	int err = toy_factory_garden_model_read(argv[1], &model, &crc);
	if (err == 0) {
		err = picosystem_garden_neural_policy_init(&model, &base);
	}
	if (err == 0) {
		err = toy_factory_garden_no_night_growth_init(&base, &night);
	}
	if (err == 0) {
		policy = night;
		if (reserve) {
			err = toy_factory_garden_reserve_init(&night, &policy);
		}
	}
	struct picosystem_garden_world world;
	struct toy_factory_garden_disturbance_event event = {0};
	if (err == 0) {
		policy.leaf_policy = toy_factory_garden_leaf_policy("selective");
		err = toy_factory_garden_evaluation_reset(&world, scenario, seed);
	}
	/* Keep both wrapped policies and their caller-owned routing context alive
	 * through the entire replay, including slot compaction at the export.
	 */
	struct picosystem_garden_neural_model focal_model;
	struct picosystem_garden_agent_policy focal_base, focal_night, routed;
	struct toy_factory_garden_focal_context focal_context;
	const struct picosystem_garden_agent_policy *active_policy = &policy;
	uint32_t focal_crc = 0U;
	if ((err == 0) && (focal_founder != 0U)) {
		err = toy_factory_garden_model_read(focal_path, &focal_model, &focal_crc);
		if (err == 0) {
			err = picosystem_garden_neural_policy_init(&focal_model, &focal_base);
		}
		if (err == 0) {
			err = toy_factory_garden_no_night_growth_init(&focal_base, &focal_night);
		}
		if (err == 0) {
			focal_night.leaf_policy = policy.leaf_policy;
			err = toy_factory_garden_focal_policy_init(&world, &policy, &focal_night,
								   focal_founder, &focal_context,
								   &routed);
		}
		active_policy = &routed;
	}
	if ((err == 0) && (schedule != 0U)) {
		err = toy_factory_garden_disturbance_plan(schedule, 0U, &event);
	}
	if (err == 0) {
		printf("{\"type\":\"seed-audit-header\",\"schema_version\":1,"
		       "\"rule\":\"seed-attempt-v1\",\"scenario\":\"%s\",\"policy\":\"%s\","
		       "\"seed\":\"%08" PRIx32 "\",\"model_crc32\":\"%08" PRIx32 "\","
		       "\"schedule\":%" PRIu32 ",\"from\":%" PRIu32 ",\"end\":%" PRIu32
		       ",\"node_capacity\":%u,\"leaf_environment\":\"%s\","
		       "\"leaf_policy\":\"selective\",\"drainage_rule\":",
		       scenario->name, argv[3], seed, crc, schedule, from, ticks,
		       PICOSYSTEM_GARDEN_MAX_NODES, PICOSYSTEM_GARDEN_LEAF_ENVIRONMENT);
#if defined(TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE)
		printf("\"%s\"", PICOSYSTEM_GARDEN_DRAINAGE_NAME);
#else
		printf("null");
#endif
#if defined(TOY_FACTORY_GARDEN_LARGE_SEED_BANK)
		printf(",\"seed_capacity\":%u", PICOSYSTEM_GARDEN_MAX_SEEDS);
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_RESERVE)
		printf(",\"seed_reserve_rule\":\"%s\"", PICOSYSTEM_GARDEN_SEED_RESERVE_NAME);
#endif
		if (focal_founder != 0U) {
			printf(",\"focal_policy\":{\"rule\":\"%s\",\"founder\":%" PRIu32
			       ",\"model_crc32\":\"%08" PRIx32 "\"}",
			       TOY_FACTORY_GARDEN_FOCAL_POLICY_RULE, focal_founder, focal_crc);
		}
		if (gap_tick != 0U) {
			printf(",\"gap\":{\"protocol\":\"%s\",\"tick\":%" PRIu32 ",\"id\":%" PRIu32
			       "}",
			       TOY_FACTORY_GARDEN_NAMED_GAP_PROTOCOL, gap_tick, gap_lineage);
		}
		if (wet_tick != 0U) {
			printf(",\"wet_germination_after\":%" PRIu32, wet_tick);
		}
		printf("}\n");
		if (from == 0U) {
			err = print_step(&world, NULL);
		}
	}
	for (uint32_t i = 0U; (err == 0) && (i < ticks); ++i) {
		struct picosystem_garden_seed_audit audit;
		if (i < from) {
			err = picosystem_garden_world_step_with_policy(&world, active_policy);
		} else {
			err = picosystem_garden_world_step_seed_audit(&world, active_policy,
								      &audit);
		}
		if ((err == 0) && (world.logic_tick_count >= from) &&
		    ((world.logic_tick_count % 15U) == 0U)) {
			err = print_step(&world, i < from ? NULL : &audit);
		}
		if ((err == 0) && (gap_tick != 0U) && (world.logic_tick_count == gap_tick)) {
			struct toy_factory_garden_gap gap;
			err = toy_factory_garden_gap_apply_named(&world, gap_lineage, &gap);
			if (err == 0) {
				err = toy_factory_garden_gap_print(&gap);
			}
			if ((err == 0) && (world.logic_tick_count >= from)) {
				err = print_step(&world, NULL);
			}
#if defined(TOY_FACTORY_GARDEN_WET_GERMINATION)
			if ((err == 0) && (wet_tick != 0U)) {
				err = toy_factory_garden_wet_germination_activate(&world);
				if ((err == 0) && (world.logic_tick_count >= from)) {
					err = print_step(&world, NULL);
				}
			}
#endif
		}
		if ((err == 0) && (event.tick != 0U) && (world.logic_tick_count == event.tick)) {
			err = toy_factory_garden_disturbance_apply(&world, &event);
			if (err == 0) {
				err = toy_factory_garden_disturbance_print(&event);
			}
			if (err == 0) {
				err = toy_factory_garden_disturbance_plan(schedule,
									  event.index + 1U, &event);
				if (err == -ENOENT) {
					event.tick = 0U;
					err = 0;
				}
			}
		}
	}
	if ((err == 0) && (fflush(stdout) != 0)) {
		err = -EIO;
	}
	if (err != 0) {
		fprintf(stderr, "Seed attempt audit failed: %d\n", err);
	}
	return err == 0 ? 0 : 1;
}
