/* SPDX-License-Identifier: Apache-2.0 */
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "garden_water_audit.h"
#include "garden_light.h"
#include "garden_disturbance.h"
#include "garden_model_file.h"
#include "garden_policy_probe.h"
#include "garden_leaf_policies.h"

#define DAY (PICOSYSTEM_GARDEN_SUN_CYCLE_TICKS * PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR)

struct budget {
	int64_t soil[PICOSYSTEM_GARDEN_WATER_STAGE_COUNT];
	int64_t plants[PICOSYSTEM_GARDEN_WATER_STAGE_COUNT];
	uint64_t soil_samples;
	uint64_t root_samples;
	uint64_t dry_root_samples;
	uint64_t living_samples;
	uint64_t shortage_samples;
	uint64_t saturated_samples;
	uint32_t steps;
	uint32_t capped_steps;
	uint32_t environmental_loss;
	uint32_t events;
	uint32_t drainage;
};

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

static uint32_t roots(const struct picosystem_garden_world *world, uint32_t *count, uint32_t *dry)
{
	bool occupied[PICOSYSTEM_GARDEN_SOIL_CELL_COUNT] = {false};
	for (uint16_t i = 0U; i < world->node_count; ++i) {
		const struct picosystem_garden_node *node = &world->nodes[i];
		if ((node->kind != PICOSYSTEM_GARDEN_NODE_ROOT) ||
		    (world->plants[node->plant_index].flags & PICOSYSTEM_GARDEN_PLANT_DEAD)) {
			continue;
		}
		const unsigned int column = (node->x - PICOSYSTEM_GARDEN_ORIGIN_X_PIXELS) /
					    PICOSYSTEM_GARDEN_CELL_PIXELS;
		const unsigned int row = (node->y - PICOSYSTEM_GARDEN_SOIL_TOP_PIXELS) /
					 PICOSYSTEM_GARDEN_CELL_PIXELS;
		occupied[row * PICOSYSTEM_GARDEN_GRID_COLUMNS + column] = true;
	}
	uint32_t water = 0U;
	*count = 0U;
	*dry = 0U;
	for (uint16_t i = 0U; i < PICOSYSTEM_GARDEN_SOIL_CELL_COUNT; ++i) {
		if (occupied[i]) {
			++*count;
			*dry += world->moisture[i] == 0U;
			water += world->moisture[i];
		}
	}
	return water;
}

static int account(const struct picosystem_garden_world *world,
		   const struct picosystem_garden_water_audit *audit, struct budget *budget)
{
	if (!audit->ecology_step) {
		return 0;
	}
	int64_t soil[PICOSYSTEM_GARDEN_WATER_STAGE_COUNT] = {0};
	int64_t plants[PICOSYSTEM_GARDEN_WATER_STAGE_COUNT] = {0};
	for (unsigned int i = 1U; i < PICOSYSTEM_GARDEN_WATER_STAGE_COUNT; ++i) {
		soil[i] = (int64_t)audit->stages[i].soil - audit->stages[i - 1U].soil;
		plants[i] = (int64_t)audit->stages[i].plants - audit->stages[i - 1U].plants;
	}
	/* Fail closed on an unexpected transfer; these constraints are the audited
	 * headroom/maintenance ecology, not assumptions imposed on default firmware.
	 */
	const int64_t evaporation = -soil[2] - audit->drainage;
	if ((soil[1] < 0) || (plants[1] != 0) || (soil[2] > 0) || (plants[2] != 0) ||
	    (soil[3] > 0) || (plants[3] != -soil[3]) || (soil[4] != 0) || (plants[4] != 0) ||
	    (soil[5] != 0) || (plants[5] > 0) || (soil[6] > 0) || (plants[6] != -2 * soil[6]) ||
	    (soil[7] != 0) || (plants[7] > 0) || (soil[8] != 0) || (plants[8] > 0) ||
	    (evaporation < 0) || (evaporation > 28) ||
	    (((world->ecology_tick_count % 4U) != 0U) && (evaporation != 0)) ||
	    (audit->drainage > 28U) ||
	    (((world->ecology_tick_count % 16U) != 0U) && (audit->drainage != 0U))) {
		return -EFAULT;
	}
	budget->drainage += audit->drainage;
	for (unsigned int i = 1U; i < PICOSYSTEM_GARDEN_WATER_STAGE_COUNT; ++i) {
		budget->soil[i] += soil[i];
		budget->plants[i] += plants[i];
	}
	++budget->steps;
	const uint32_t total = audit->stages[PICOSYSTEM_GARDEN_WATER_REPRODUCTION].soil;
	budget->soil_samples += total;
	budget->capped_steps += total > UINT16_MAX;
	for (uint16_t i = 0U; i < PICOSYSTEM_GARDEN_SOIL_CELL_COUNT; ++i) {
		budget->saturated_samples += world->moisture[i] == UINT8_MAX;
	}
	uint32_t root_count, dry_count;
	(void)roots(world, &root_count, &dry_count);
	budget->root_samples += root_count;
	budget->dry_root_samples += dry_count;
	for (uint8_t i = 0U; i < world->plant_count; ++i) {
		const struct picosystem_garden_plant *plant = &world->plants[i];
		if (!(plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD)) {
			++budget->living_samples;
			budget->shortage_samples +=
				(plant->flags & PICOSYSTEM_GARDEN_PLANT_WATER_SHORTAGE) != 0U;
		}
	}
	return 0;
}

static int print_budget(const struct picosystem_garden_world *world, const struct budget *budget,
			uint32_t model_crc, uint32_t schedule)
{
	uint32_t plant_water = 0U;
	for (uint8_t i = 0U; i < world->plant_count; ++i) {
		plant_water += world->plants[i].stored_water;
	}
	putchar('{');
#if defined(TOY_FACTORY_GARDEN_LARGE_SEED_BANK)
	printf("\"seed_capacity\":%u,", PICOSYSTEM_GARDEN_MAX_SEEDS);
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_RESERVE)
	printf("\"seed_reserve_rule\":\"%s\",", PICOSYSTEM_GARDEN_SEED_RESERVE_NAME);
#endif
	printf("\"schema_version\":1,\"tick\":%" PRIu32 ",\"hash\":\"%08" PRIx32
	       "\",\"model_crc32\":\"%08" PRIx32 "\",\"schedule\":%" PRIu32
	       ",\"node_capacity\":%u,\"plants\":%" PRIu32 ",\"soil_rows\":[",
	       world->logic_tick_count, picosystem_garden_world_hash(world), model_crc, schedule,
	       PICOSYSTEM_GARDEN_MAX_NODES, plant_water);
	for (unsigned int row = 0U; row < PICOSYSTEM_GARDEN_SOIL_ROWS; ++row) {
		uint32_t total = 0U;
		for (unsigned int col = 0U; col < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++col) {
			total += world->moisture[row * PICOSYSTEM_GARDEN_GRID_COLUMNS + col];
		}
		printf("%s%" PRIu32, row ? "," : "", total);
	}
	printf("],\"stage_soil\":[");
	for (unsigned int i = 0U; i < PICOSYSTEM_GARDEN_WATER_STAGE_COUNT; ++i) {
		printf("%s%" PRId64, i ? "," : "", budget->soil[i]);
	}
	printf("],\"stage_plants\":[");
	for (unsigned int i = 0U; i < PICOSYSTEM_GARDEN_WATER_STAGE_COUNT; ++i) {
		printf("%s%" PRId64, i ? "," : "", budget->plants[i]);
	}
	uint32_t root_count, dry_count;
	const uint32_t root_water = roots(world, &root_count, &dry_count);
#if defined(TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE)
	printf("],\"drainage_rule\":\"%s\",\"drainage\":%" PRIu32 ",\"rain\":%" PRIu32,
	       PICOSYSTEM_GARDEN_DRAINAGE_NAME, budget->drainage, world->rain_deposited);
#else
	printf("],\"rain\":%" PRIu32, world->rain_deposited);
#endif
	printf(",\"runoff\":%" PRIu32 ",\"births\":%" PRIu32 ",\"seeds_created\":%" PRIu32
	       ",\"seeds_expired\":%" PRIu32 ",\"seeds\":%u,\"events\":%" PRIu32
	       ",\"environmental_loss\":%" PRIu32 ",\"steps\":%" PRIu32 ",\"soil_samples\":%" PRIu64
	       ",\"capped_steps\":%" PRIu32 ",\"saturated_samples\":%" PRIu64
	       ",\"root_samples\":%" PRIu64 ",\"dry_root_samples\":%" PRIu64
	       ",\"living_samples\":%" PRIu64 ",\"shortage_samples\":%" PRIu64
	       ",\"root_cells\":%" PRIu32 ",\"root_water\":%" PRIu32 ",\"dry_root_cells\":%" PRIu32
	       "}\n",
	       world->rain_runoff, world->germination_count, world->seed_creation_count,
	       world->seed_expiration_count, world->seed_count, budget->events,
	       budget->environmental_loss, budget->steps, budget->soil_samples,
	       budget->capped_steps, budget->saturated_samples, budget->root_samples,
	       budget->dry_root_samples, budget->living_samples, budget->shortage_samples,
	       root_count, root_water, dry_count);
	return ferror(stdout) ? -EIO : 0;
}

int main(int argc, char **argv)
{
	/* Deliberately narrow assay: fixed saved-NN veto + selective renewal,
	 * rainfed scenarios only; schedule zero is the untouched control.
	 */
	uint32_t seed, schedule, ticks;
	if ((argc != 6) || (parse_u32(argv[3], &seed) != 0) || (seed == 0U) ||
	    (parse_u32(argv[4], &schedule) != 0) || (parse_u32(argv[5], &ticks) != 0) ||
	    (ticks > TOY_FACTORY_GARDEN_DISTURBANCE_MAX_TICKS) || (ticks % DAY != 0U)) {
		fprintf(stderr,
			"Usage: %s MODEL RAINFED_SCENARIO WORLD_SEED SCHEDULE_OR_ZERO TICKS\n",
			argv[0]);
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
	struct picosystem_garden_agent_policy base, policy;
	uint32_t crc;
	int err = toy_factory_garden_model_read(argv[1], &model, &crc);
	if (err == 0) {
		err = picosystem_garden_neural_policy_init(&model, &base);
	}
	if (err == 0) {
		err = toy_factory_garden_no_night_growth_init(&base, &policy);
	}
	struct picosystem_garden_world world;
	if (err == 0) {
		policy.leaf_policy = toy_factory_garden_leaf_policy("selective");
		err = toy_factory_garden_evaluation_reset(&world, scenario, seed);
	}
	struct budget budget = {0};
	struct toy_factory_garden_disturbance_event event = {0};
	if ((err == 0) && (schedule != 0U)) {
		err = toy_factory_garden_disturbance_plan(schedule, 0U, &event);
	}
	if (err == 0) {
		err = print_budget(&world, &budget, crc, schedule);
	}
	for (uint32_t i = 0U; (err == 0) && (i < ticks); ++i) {
		struct picosystem_garden_water_audit audit;
		err = picosystem_garden_world_step_water_audit(&world, &policy, &audit);
		if (err == 0) {
			err = account(&world, &audit, &budget);
		}
		if ((err == 0) && (event.tick != 0U) && (world.logic_tick_count == event.tick)) {
			err = toy_factory_garden_disturbance_apply(&world, &event);
			if (err == 0) {
				budget.environmental_loss += event.lost_water;
				++budget.events;
				err = toy_factory_garden_disturbance_plan(schedule,
									  event.index + 1U, &event);
				if (err == -ENOENT) {
					event.tick = 0U;
					err = 0;
				}
			}
		}
		if ((err == 0) && (world.logic_tick_count % DAY == 0U)) {
			err = print_budget(&world, &budget, crc, schedule);
		}
	}
	if ((err == 0) && (fflush(stdout) != 0)) {
		err = -EIO;
	}
	if (err != 0) {
		fprintf(stderr, "Water audit failed: %d\n", err);
	}
	return err == 0 ? 0 : 1;
}
