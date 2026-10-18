/* SPDX-License-Identifier: Apache-2.0 */
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "garden_climate_cli.h"
#include "garden_evaluation.h"
#include "garden_seed_audit.h"

#define GARDEN_DAY_TICKS (PICOSYSTEM_GARDEN_DAY_TICKS * PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR)

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
	for (uint8_t column = 0U; column < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++column) {
		printf("%s%u", column ? "," : "", sites[column]);
	}
	putchar(']');
}

static void print_counts(const struct picosystem_garden_world *world)
{
	printf("\"tick\":%" PRIu32 ",\"hash\":\"%08" PRIx32 "\",\"births\":%" PRIu32
	       ",\"expired\":%" PRIu32 ",\"created\":%" PRIu32 ",\"deaths\":%" PRIu32,
	       world->logic_tick_count, picosystem_garden_world_hash(world),
	       world->germination_count, world->seed_expiration_count, world->seed_creation_count,
	       world->death_count);
}

static int print_step(const struct picosystem_garden_world *world,
		      const struct picosystem_garden_seed_audit *audit)
{
	struct picosystem_garden_seed_sites after;
	const int err = picosystem_garden_world_seed_sites(world, &after);
	if (err != 0) {
		return err;
	}
	printf("{\"type\":\"seed-step\",");
	toy_factory_garden_climate_print(stdout, world);
	print_counts(world);
	printf(",\"stages\":[");
	for (unsigned int i = 0U; i < PICOSYSTEM_GARDEN_SEED_STAGE_COUNT; ++i) {
		const struct picosystem_garden_seed_inventory *s = &audit->stages[i];
		printf("%s[%u,%u,%u]", i ? "," : "", s->nodes, s->plants, s->seeds);
	}
	printf("],\"support\":[");
	for (unsigned int i = 0U; i < PICOSYSTEM_GARDEN_SPECIES_COUNT; ++i) {
		printf("%s%" PRIu32, i ? "," : "", audit->dispersal_columns[i]);
	}
	printf("],\"sites_before\":");
	print_sites(audit->sites_before);
	printf(",\"sites_after\":");
	print_sites(after.blockers);
	printf(",\"attempts\":[");
	for (uint8_t i = 0U; i < audit->count; ++i) {
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
	printf("]}\n");
	return ferror(stdout) ? -EIO : 0;
}

int main(int argc, char **argv)
{
	uint32_t seed, early_end, from, end;
	enum picosystem_garden_climate_mode climate;
	if ((argc != 8) || (parse_u32(argv[3], &seed) != 0) || (seed == 0U) ||
	    (toy_factory_garden_climate_parse(argv[4], &climate) != 0) ||
	    (parse_u32(argv[5], &early_end) != 0) || (parse_u32(argv[6], &from) != 0) ||
	    (parse_u32(argv[7], &end) != 0) || (early_end > from) || (from >= end) ||
	    (end > 256U * GARDEN_DAY_TICKS) ||
	    ((early_end % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) != 0U) ||
	    ((from % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) != 0U) ||
	    ((end % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) != 0U)) {
		fprintf(stderr,
			"Usage: %s RAINFED_SCENARIO baseline|adaptive SEED CLIMATE "
			"EARLY_END_TICK LATE_FROM_TICK END_TICK\n",
			argv[0]);
		return 2;
	}
	const struct toy_factory_garden_evaluation_scenario *scenario = NULL;
	for (unsigned int i = 0U; i < TOY_FACTORY_GARDEN_RAINFED_SCENARIO_COUNT; ++i) {
		if (strcmp(argv[1], toy_factory_garden_rainfed_scenarios[i].name) == 0) {
			scenario = &toy_factory_garden_rainfed_scenarios[i];
		}
	}
	const struct picosystem_garden_agent_policy *policy = NULL;
	if (strcmp(argv[2], "baseline") == 0) {
		policy = picosystem_garden_agent_baseline_policy();
	} else if (strcmp(argv[2], "adaptive") == 0) {
		policy = picosystem_garden_agent_adaptive_policy();
	}
	if ((scenario == NULL) || (scenario->irrigation_period_ticks != 0U) || (policy == NULL)) {
		return 2;
	}
	struct picosystem_garden_world world;
	int err = toy_factory_garden_evaluation_reset(&world, scenario, seed);
	if (err == 0) {
		err = picosystem_garden_world_set_climate(&world, climate);
	}
	if (err != 0) {
		return 1;
	}
	printf("{\"type\":\"recruitment-header\",\"version\":1,\"scenario\":\"%s\","
	       "\"policy\":\"%s\",\"seed\":\"%08" PRIx32 "\",\"early_end\":%" PRIu32
	       ",\"from\":%" PRIu32 ",\"end\":%" PRIu32 ",\"node_capacity\":%u,"
	       "\"plant_capacity\":%u,\"seed_capacity\":%u,\"dispersal\":\"%s\",",
	       scenario->name, argv[2], seed, early_end, from, end, PICOSYSTEM_GARDEN_MAX_NODES,
	       PICOSYSTEM_GARDEN_DEFAULT_PLANTS, PICOSYSTEM_GARDEN_MAX_SEEDS,
	       PICOSYSTEM_GARDEN_DISPERSAL_NAME);
	toy_factory_garden_climate_print(stdout, &world);
	printf("\"gardener\":false,\"irrigation\":false}\n");
	for (uint32_t tick = 0U; (err == 0) && (tick <= end); ++tick) {
		if (tick != 0U) {
			if ((tick <= early_end) || (tick > from)) {
				struct picosystem_garden_seed_audit audit;
				err = picosystem_garden_world_step_seed_audit(&world, policy,
									      &audit);
				if ((err == 0) && audit.ecology_step) {
					err = print_step(&world, &audit);
				}
			} else {
				err = picosystem_garden_world_step_with_policy(&world, policy);
			}
		}
		if ((err == 0) && (((tick % GARDEN_DAY_TICKS) == 0U) || (tick == end))) {
			printf("{\"type\":\"checkpoint\",");
			print_counts(&world);
			printf("}\n");
		}
		if (ferror(stdout)) {
			err = -EIO;
		}
	}
	if ((fflush(stdout) != 0) && (err == 0)) {
		err = -EIO;
	}
	if (err != 0) {
		fprintf(stderr, "recruitment audit failed: %d\n", err);
	}
	return err == 0 ? 0 : 1;
}
