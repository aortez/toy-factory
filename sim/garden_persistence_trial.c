/* SPDX-License-Identifier: Apache-2.0 */
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#include "garden_disturbance.h"
#include "garden_founder_exit.h"
#include "garden_leaf_policies.h"
#include "garden_model_file.h"
#include "garden_persistence.h"
#include "garden_pilot_parse.h"
#include "garden_policy_probe.h"
#include "garden_reserve_policy.h"
#include "garden_seed_audit.h"

#if !defined(TOY_FACTORY_GARDEN_LARGE_POOL) || defined(TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE) ||      \
	defined(TOY_FACTORY_GARDEN_LARGE_SEED_BANK) || defined(TOY_FACTORY_GARDEN_SEED_RESERVE)
#error "Persistence pilot requires the frozen 512-node, bank-8, undrained host ecology"
#endif

#define MAX_SEEDS 65536U
#define DAY       TOY_FACTORY_GARDEN_PERSISTENCE_DAY
#define STEP      TOY_FACTORY_GARDEN_PERSISTENCE_STEP
#define ALIVE     TOY_FACTORY_GARDEN_PERSISTENCE_ALIVE

struct seed_record {
	uint32_t parent, birth, end, child;
	uint16_t generation;
	uint8_t column;
	uint8_t outcome;
};

/* One process owns these bounded host-only ledgers. Nothing is in world state. */
static struct toy_factory_garden_persistence_lifetime
	records[TOY_FACTORY_GARDEN_PERSISTENCE_MAX_LINEAGES + 1U];
static bool seen[TOY_FACTORY_GARDEN_PERSISTENCE_MAX_LINEAGES + 1U];
static uint32_t present[TOY_FACTORY_GARDEN_PERSISTENCE_MAX_LINEAGES + 1U];
static struct seed_record seeds[MAX_SEEDS];
static uint32_t active[PICOSYSTEM_GARDEN_MAX_SEEDS];
static uint32_t record_count, seed_count, active_count;

static int census(const struct picosystem_garden_world *world, bool patch)
{
	if (world->lineage_sequence > TOY_FACTORY_GARDEN_PERSISTENCE_MAX_LINEAGES) {
		return -ENOSPC;
	}
	for (uint8_t i = 0U; i < world->plant_count; ++i) {
		const struct picosystem_garden_plant *p = &world->plants[i];
		if ((p->lineage_id == 0U) || (p->lineage_id > world->lineage_sequence)) {
			return -EINVAL;
		}
		struct toy_factory_garden_persistence_lifetime *r = &records[p->lineage_id];
		if (!seen[p->lineage_id]) {
			*r = (struct toy_factory_garden_persistence_lifetime){
				.parent = p->parent_lineage_id,
				.birth = world->logic_tick_count,
				.death = ALIVE,
				.generation = p->generation,
				.column = p->base_column,
				.species = p->species_id};
			seen[p->lineage_id] = true;
		}
		present[p->lineage_id] = world->logic_tick_count;
		if ((r->death == ALIVE) && ((p->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) != 0U)) {
			r->death = world->logic_tick_count;
			r->patch = patch;
		}
	}
	for (uint32_t id = 1U; id <= world->lineage_sequence; ++id) {
		if (!seen[id] ||
		    ((records[id].death == ALIVE) && (present[id] != world->logic_tick_count))) {
			return -EFAULT;
		}
	}
	record_count = world->lineage_sequence;
	return 0;
}

static int seed_step(const struct picosystem_garden_world *world,
		     const struct picosystem_garden_seed_audit *audit, uint32_t start)
{
	if (audit->count != active_count) {
		return -EFAULT;
	}
	for (uint8_t i = 0U; i < audit->count; ++i) {
		const struct picosystem_garden_seed_attempt *a = &audit->attempts[i];
		const uint32_t birth = world->logic_tick_count - (uint32_t)a->age * STEP;
		uint32_t slot = 0U;
		while ((slot < active_count) && ((seeds[active[slot]].parent != a->parent) ||
						 (seeds[active[slot]].birth != birth))) {
			++slot;
		}
		if (slot == active_count) {
			return -ENOENT;
		}
		struct seed_record *s = &seeds[active[slot]];
		if ((s->generation != a->generation) || (s->column != a->column)) {
			return -EINVAL;
		}
		if (a->outcome != PICOSYSTEM_GARDEN_SEED_WAIT) {
			s->end = world->logic_tick_count;
			s->child = a->child;
			s->outcome = a->outcome;
			active[slot] = active[--active_count];
		}
	}
	for (uint8_t i = 0U; i < world->seed_count; ++i) {
		const struct picosystem_garden_seed *s = &world->seeds[i];
		if (s->age_ecology_ticks != 0U) {
			continue;
		}
		if ((seed_count == MAX_SEEDS) || (active_count == PICOSYSTEM_GARDEN_MAX_SEEDS) ||
		    (s->parent_lineage_id == 0U) || (s->parent_lineage_id > record_count)) {
			return -ENOSPC;
		}
		seeds[seed_count] = (struct seed_record){.parent = s->parent_lineage_id,
							 .birth = world->logic_tick_count,
							 .generation = s->generation,
							 .column = s->column};
		active[active_count++] = seed_count++;
		++records[s->parent_lineage_id].purchases;
		if (world->logic_tick_count > start) {
			++records[s->parent_lineage_id].closing_purchases;
		}
	}
	return (seed_count == world->seed_creation_count) && (active_count == world->seed_count)
		       ? 0
		       : -EFAULT;
}

static void print_checkpoint(const struct picosystem_garden_world *world, bool first)
{
	printf("%s{\"tick\":%" PRIu32 ",\"hash\":\"%08" PRIx32
	       "\",\"living\":%u,\"seeds\":%u,\"births\":%" PRIu32 ",\"deaths\":%" PRIu32
	       ",\"nodes\":%u}",
	       first ? "" : ",", world->logic_tick_count, picosystem_garden_world_hash(world),
	       picosystem_garden_world_living_plant_count(world), world->seed_count,
	       world->germination_count, world->death_count, world->node_count);
}

static int print_ledgers(const struct picosystem_garden_world *world, uint32_t start, uint32_t end,
			 const struct toy_factory_garden_founder_exit *exit_result)
{
	struct toy_factory_garden_persistence_score score;
	const int err =
		toy_factory_garden_persistence_score(records, record_count, world->seed_count,
						     start, end, world->logic_tick_count, &score);
	if (err != 0) {
		return err;
	}
	printf("],\"key\":[%" PRId64 ",%" PRId64 ",%" PRId64 ",%" PRId64 ",%" PRId64
	       "],\"lineages\":[",
	       score.key[0], score.key[1], score.key[2], score.key[3], score.key[4]);
	for (uint32_t id = 1U; id <= record_count; ++id) {
		const struct toy_factory_garden_persistence_lifetime *r = &records[id];
		printf("%s{\"id\":%" PRIu32 ",\"parent\":%" PRIu32 ",\"birth_tick\":%" PRIu32
		       ",\"death_tick\":",
		       id == 1U ? "" : ",", id, r->parent, r->birth);
		if (r->death == ALIVE) {
			printf("null");
		} else {
			printf("%" PRIu32, r->death);
		}
		printf(",\"environmental_death\":%s,\"column\":%u,\"generation\":%u,\"species\":%u,"
		       "\"seeds_created\":%" PRIu32 ",\"late_seeds_created\":%" PRIu32 "}",
		       r->patch ? "true" : "false", r->column, r->generation, r->species,
		       r->purchases, r->closing_purchases);
	}
	printf("],\"seeds\":[");
	for (uint32_t i = 0U; i < seed_count; ++i) {
		const struct seed_record *s = &seeds[i];
		printf("%s{\"parent\":%" PRIu32 ",\"birth_tick\":%" PRIu32 ",\"end_tick\":",
		       i == 0U ? "" : ",", s->parent, s->birth);
		if (s->end == 0U) {
			printf("null");
		} else {
			printf("%" PRIu32, s->end);
		}
		printf(",\"child_id\":");
		if (s->child == 0U) {
			printf("null");
		} else {
			printf("%" PRIu32, s->child);
		}
		printf(",\"generation\":%u,\"column\":%u,\"outcome\":\"%s\"}", s->generation,
		       s->column,
		       s->outcome == PICOSYSTEM_GARDEN_SEED_EXPIRED      ? "expired"
		       : s->outcome == PICOSYSTEM_GARDEN_SEED_GERMINATED ? "germinated"
									 : "pending");
	}
	printf("]");
	if (exit_result != NULL) {
		printf(",\"founder_exit\":");
		const int printed = toy_factory_garden_founder_exit_print(exit_result);
		if (printed != 0) {
			return printed;
		}
	}
	printf("}\n");
	return fflush(stdout) == 0 && !ferror(stdout) ? 0 : -EIO;
}

int main(int argc, char **argv)
{
	uint32_t seed, patch, start, end;
	uint32_t exit_tick = 0U;
	if (((argc != 7) && (argc != 9)) ||
	    (toy_factory_garden_pilot_u32(argv[3], UINT32_MAX, &seed) != 0) || (seed == 0U) ||
	    (toy_factory_garden_pilot_u32(argv[4], UINT32_MAX, &patch) != 0) || (patch == 0U) ||
	    (toy_factory_garden_pilot_u32(argv[5], 729600U, &start) != 0) ||
	    (toy_factory_garden_pilot_u32(argv[6], 729600U, &end) != 0) || (start >= end) ||
	    ((start % STEP) != 0U) || ((end % STEP) != 0U) ||
	    ((strcmp(argv[2], "neural") != 0) && (strcmp(argv[2], "reserve") != 0))) {
		fprintf(stderr,
			"Usage: %s MODEL neural|reserve WORLD_SEED PATCH_SEED START END "
			"[--founder-exit TICK]\n",
			argv[0]);
		return 2;
	}
	if ((argc == 9) && ((strcmp(argv[7], "--founder-exit") != 0) ||
			    (toy_factory_garden_pilot_u32(argv[8], end, &exit_tick) != 0) ||
			    (exit_tick == 0U) || (exit_tick % STEP != 0U))) {
		return 2;
	}
	struct toy_factory_garden_founder_exit exit_result = {0};
	const uint32_t stop = end + 2U * DAY;
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
	}
	if ((err == 0) && (strcmp(argv[2], "reserve") == 0)) {
		err = toy_factory_garden_reserve_init(&night, &policy);
	}
	struct picosystem_garden_world world;
	struct toy_factory_garden_disturbance_event event;
	if (err == 0) {
		policy.leaf_policy = toy_factory_garden_leaf_policy("selective");
		err = toy_factory_garden_evaluation_reset(
			&world, &toy_factory_garden_rainfed_scenarios[1], seed);
	}
	if (err == 0) {
		err = census(&world, false);
	}
	if (err == 0) {
		err = toy_factory_garden_disturbance_plan(patch, 0U, &event);
	}
	if (err == 0) {
		printf("{\"rule\":\"garden-persistence-trial-v1\",\"seed\":\"%08" PRIx32
		       "\",\"patch_seed\":\"%08" PRIx32 "\",\"model_crc32\":\"%08" PRIx32
		       "\",\"policy\":\"%s\",\"start\":%" PRIu32 ",\"end\":%" PRIu32
		       ",\"stop\":%" PRIu32 ",\"node_capacity\":%u,\"seed_capacity\":%u,"
		       "\"scenario\":\"rainfed-crowded\",\"gardener\":false,\"drainage\":false,"
		       "\"seed_reserve\":false,\"leaf_policy\":\"selective\",\"checkpoints\":[",
		       seed, patch, crc, argv[2], start, end, stop, PICOSYSTEM_GARDEN_MAX_NODES,
		       PICOSYSTEM_GARDEN_MAX_SEEDS);
		print_checkpoint(&world, true);
	}
	for (uint32_t tick = 0U; (err == 0) && (tick < stop); ++tick) {
		struct picosystem_garden_seed_audit audit;
		err = picosystem_garden_world_step_seed_audit(&world, &policy, &audit);
		if ((err == 0) && audit.ecology_step) {
			err = census(&world, false);
			if (err == 0) {
				err = seed_step(&world, &audit, start);
			}
		}
		if ((err == 0) && (event.tick != 0U) && (world.logic_tick_count == event.tick)) {
			err = toy_factory_garden_disturbance_apply(&world, &event);
			if (err == 0) {
				err = census(&world, true);
			}
			if (err == 0) {
				err = toy_factory_garden_disturbance_plan(patch, event.index + 1U,
									  &event);
				if (err == -ENOENT) {
					event.tick = 0U;
					err = 0;
				}
			}
		}
		if ((err == 0) && (exit_tick != 0U) && (world.logic_tick_count == exit_tick)) {
			err = toy_factory_garden_founder_exit_apply(&world, &exit_result);
			if (err == 0) {
				err = census(&world, true);
			}
		}
		if ((err == 0) &&
		    ((world.logic_tick_count == 480U) || (world.logic_tick_count == 2880U) ||
		     (world.logic_tick_count == start) || (world.logic_tick_count == end) ||
		     (world.logic_tick_count == stop) ||
		     ((exit_tick != 0U) && (world.logic_tick_count % DAY == 0U)))) {
			print_checkpoint(&world, false);
		}
	}
	if ((err == 0) && (world.auto_gardener_enabled || (world.manual_action_count != 0U) ||
			   (world.auto_action_count != 0U))) {
		err = -EFAULT;
	}
	if (err == 0) {
		err = print_ledgers(&world, start, end, exit_tick != 0U ? &exit_result : NULL);
	}
	if (err != 0) {
		fprintf(stderr, "Persistence trial failed (%d)\n", err);
	}
	return err == 0 ? 0 : 1;
}
