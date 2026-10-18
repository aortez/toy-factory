/* SPDX-License-Identifier: Apache-2.0 */
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "garden_evaluation.h"
#include "garden_reproduction_audit.h"
#include "garden_flower_audit.h"
#include "garden_seed_audit.h"
#include "garden_light.h"
#include "garden_seedling_reserve.h"

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

static void print_flower_sites(const struct picosystem_garden_flower_audit *audit)
{
	printf(",\"purchases\":[");
	for (uint8_t i = 0U; i < audit->count; ++i) {
		const struct picosystem_garden_flower_purchase *const p = &audit->purchases[i];
		printf("%s{\"id\":%" PRIu32 ",\"selected\":%u,\"base\":%u,\"origin\":%u,"
		       "\"species\":%u,\"dispersal\":%d,\"choice\":%u,\"column\":%u,"
		       "\"columns\":%" PRIu32 ",\"flowers\":[",
		       i ? "," : "", p->lineage, p->selected_flower, p->base_column, p->origin,
		       p->species, p->dispersal, p->choice, p->landed_column, p->columns);
		for (uint16_t j = 0U; j < p->flower_count; ++j) {
			const struct picosystem_garden_flower_reach *const f =
				&audit->flowers[p->flower_offset + j];
			printf("%s[%u,%u,%u,%" PRIu32 "]", j ? "," : "", f->node_index, f->x, f->y,
			       f->columns);
		}
		printf("]}");
	}
	printf("],\"sites\":[");
	for (uint8_t i = 0U; (audit->count > 0U) && (i < PICOSYSTEM_GARDEN_GRID_COLUMNS); ++i) {
		const struct picosystem_garden_flower_site *const s = &audit->sites[i];
		printf("%s[%u,%u,%u]", i ? "," : "", s->moisture, s->light, s->blockers);
	}
	printf("]");
}

static int print_step(const struct picosystem_garden_world *world,
		      const struct picosystem_garden_reproduction_audit *audit,
		      const struct picosystem_garden_flower_audit *flowers)
{
	printf("{\"tick\":%" PRIu32 ",\"hash\":\"%08" PRIx32 "\",\"created\":%" PRIu32
	       ",\"visits\":[",
	       world->logic_tick_count, picosystem_garden_world_hash(world),
	       world->seed_creation_count);
	for (uint8_t i = 0U; i < audit->count; ++i) {
		const struct picosystem_garden_reproduction_visit *const v = &audit->visits[i];
		printf("%s[%" PRIu32 ",%u,%u,%u,%" PRId32 ",%" PRId32
		       ",%u,%u,%u,%u,%u,%u,%u,%u,%s]",
		       i ? "," : "", v->lineage, v->blockers, v->energy, v->water,
		       v->energy_required, v->water_required, v->immature_flowers, v->spent_flowers,
		       v->ready_flowers, v->flower_index, v->cooldown, v->seed_count, v->stress,
		       v->sun_strength, v->produced ? "true" : "false");
	}
	printf("]");
	if (flowers != NULL) {
		print_flower_sites(flowers);
	}
	printf("}\n");
	return ferror(stdout) ? -EIO : 0;
}

static int print_seed_waits(const struct picosystem_garden_world *world,
			    const struct picosystem_garden_seed_audit *audit)
{
	const struct picosystem_garden_sun sun = picosystem_garden_world_sun(world);
	printf("{\"tick\":%" PRIu32 ",\"hash\":\"%08" PRIx32 "\",\"created\":%" PRIu32
	       ",\"sun\":[%u,%u,%d],\"stages\":[",
	       world->logic_tick_count, picosystem_garden_world_hash(world),
	       world->seed_creation_count, sun.phase, sun.strength, sun.ray_step_x_q4);
	for (uint8_t i = 0U; i < PICOSYSTEM_GARDEN_SEED_STAGE_COUNT; ++i) {
		const struct picosystem_garden_seed_inventory *const s = &audit->stages[i];
		printf("%s[%u,%u,%u]", i ? "," : "", s->nodes, s->plants, s->seeds);
	}
	printf("],\"attempts\":[");
	for (uint8_t i = 0U; i < audit->count; ++i) {
		const struct picosystem_garden_seed_attempt *const a = &audit->attempts[i];
		printf("%s[%" PRIu32 ",%" PRIu32 ",%u,%u,%u,%u,%u,%u,%u,%u,%u,%u]", i ? "," : "",
		       a->parent, a->child, a->age, a->generation, a->column, a->species, a->nodes,
		       a->plants, a->moisture, a->light, a->blockers, a->outcome);
	}
	printf("]}\n");
	return ferror(stdout) ? -EIO : 0;
}

int main(int argc, char **argv)
{
	uint32_t seed, end;
	const bool flowers_enabled = (argc == 7) && (strcmp(argv[6], "--flower-sites") == 0);
	const bool seeds_enabled = (argc == 7) && (strcmp(argv[6], "--seed-waits") == 0);
	if (((argc != 6) && !flowers_enabled && !seeds_enabled) ||
	    (parse_u32(argv[3], &seed) != 0) || (seed == 0U) || (parse_u32(argv[5], &end) != 0) ||
	    (end == 0U) ||
	    (end > 128U * PICOSYSTEM_GARDEN_DAY_TICKS * PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) ||
	    ((end % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) != 0U) ||
	    ((strcmp(argv[4], "control") != 0) && (strcmp(argv[4], "guard") != 0))) {
		fprintf(stderr,
			"Usage: %s RAINFED_SCENARIO baseline|adaptive SEED control|guard "
			"END_TICK [--flower-sites|--seed-waits]\n",
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
		err = picosystem_garden_world_set_climate(&world,
							  PICOSYSTEM_GARDEN_CLIMATE_SEASONAL);
	}
	struct toy_factory_garden_seedling_reserve_context context;
	struct picosystem_garden_agent_policy guarded;
	if ((err == 0) && (strcmp(argv[4], "guard") == 0)) {
		err = toy_factory_garden_seedling_reserve_offspring_init(policy, &world, &context,
									 &guarded);
		policy = &guarded;
	}
	if (err != 0) {
		return 1;
	}
	printf("{\"version\":%u,", seeds_enabled ? 3U : flowers_enabled ? 2U : 1U);
	if (seeds_enabled) {
		printf("\"seed_audit\":\"seed-waits-v1\",\"site_phase\":\"sequential-check\","
		       "\"attempt_fields\":[\"parent\",\"child\",\"age\",\"generation\",\"column\","
		       "\"species\",\"nodes\",\"plants\",\"moisture\",\"light\",\"blockers\","
		       "\"outcome\"],"
		       "\"sun_fields\":[\"phase\",\"strength\",\"ray_step_x_q4\"],");
	}
	if (flowers_enabled) {
		printf("\"flower_audit\":\"flower-sites-v1\",\"site_phase\":\"post-light-refresh\","
		       "\"flower_fields\":[\"node\",\"x\",\"y\",\"columns\"],"
		       "\"site_fields\":[\"moisture\",\"light\",\"blockers\"],");
	}
#if defined(TOY_FACTORY_GARDEN_SEASONAL_SEED_BANK)
	printf("\"seed_capacity\":%u,", PICOSYSTEM_GARDEN_MAX_SEEDS);
#endif
#if defined(TOY_FACTORY_GARDEN_FLOWER_DISPERSAL)
	printf("\"seed_origin\":\"%s\",", PICOSYSTEM_GARDEN_SEED_ORIGIN_NAME);
#endif
	printf("\"scenario\":\"%s\",\"policy\":\"%s\",\"seed\":\"%08" PRIx32
	       "\",\"arm\":\"%s\",\"end\":%" PRIu32 ",\"climate\":\"seasonal\","
	       "\"dispersal\":\"%s\"",
	       scenario->name, argv[2], seed, argv[4], end, PICOSYSTEM_GARDEN_DISPERSAL_NAME);
	if (!seeds_enabled) {
		printf(",\"fields\":[\"id\",\"blockers\",\"energy\",\"water\","
		       "\"energy_required\",\"water_required\",\"immature\",\"spent\",\"ready\","
		       "\"flower_index\",\"cooldown\",\"bank\",\"stress\",\"light\",\"produced\"]");
	}
	printf("}\n");
	struct picosystem_garden_reproduction_audit audit = {0};
	struct picosystem_garden_flower_audit flowers = {0};
	struct picosystem_garden_seed_audit seeds = {0};
	err = seeds_enabled ? print_seed_waits(&world, &seeds)
			    : print_step(&world, &audit, flowers_enabled ? &flowers : NULL);
	for (uint32_t tick = 1U; (err == 0) && (tick <= end); ++tick) {
		if (seeds_enabled) {
			err = picosystem_garden_world_step_seed_audit(&world, policy, &seeds);
			if ((err == 0) && seeds.ecology_step) {
				err = print_seed_waits(&world, &seeds);
			}
			continue;
		}
		const struct picosystem_garden_reproduction_audit *receipt;
		if (flowers_enabled) {
			err = picosystem_garden_world_step_flower_audit(&world, policy, &flowers);
			receipt = &flowers.production;
		} else {
			err = picosystem_garden_world_step_reproduction_audit(&world, policy,
									      &audit);
			receipt = &audit;
		}
		if ((err == 0) && receipt->ecology_step) {
			err = print_step(&world, receipt, flowers_enabled ? &flowers : NULL);
		}
	}
	if ((fflush(stdout) != 0) && (err == 0)) {
		err = -EIO;
	}
	if (err != 0) {
		fprintf(stderr, "production audit failed: %d\n", err);
	}
	return err == 0 ? 0 : 1;
}
