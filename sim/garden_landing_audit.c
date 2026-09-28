/* SPDX-License-Identifier: Apache-2.0 */
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "garden_evaluation.h"
#include "garden_landing.h"
#include "garden_seedling_reserve.h"

#if defined(TOY_FACTORY_GARDEN_FLOWER_DISPERSAL)
#define LANDING_ORIGIN "flower"
#else
#define LANDING_ORIGIN "base"
#endif

struct landing_bid {
	struct picosystem_garden_agent_observation observation;
	struct picosystem_garden_landing_packet packet;
	struct picosystem_garden_agent_decision decision;
};

/* Host collector scratch, not part of the proposed embedded cache budget. */
struct landing_receipts {
	struct landing_bid bids[PICOSYSTEM_GARDEN_MAX_NODES];
	uint16_t count;
	uint32_t total;
};

struct landing_context {
	const struct picosystem_garden_world *world;
	const struct picosystem_garden_landing_cache *cache;
	const struct picosystem_garden_agent_policy *base;
	struct landing_receipts *receipts;
	bool retain;
};

static int observe_decide(const struct picosystem_garden_agent_observation *observation,
			  const struct picosystem_garden_agent_memory *memory,
			  struct picosystem_garden_agent_decision *decision, const void *context)
{
	const struct landing_context *const ctx = context;
	if ((ctx->cache->ecology_tick != ctx->world->ecology_tick_count) ||
	    (ctx->receipts->count >= PICOSYSTEM_GARDEN_MAX_NODES)) {
		return -EOVERFLOW;
	}
	struct picosystem_garden_landing_packet packet;
	int err = picosystem_garden_landing_observe(ctx->cache, observation, &packet);
	if (err != 0) {
		return err;
	}
	err = picosystem_garden_agent_decide(ctx->base, observation, memory, decision);
	if (err != 0) {
		return err;
	}
	if (ctx->retain) {
		ctx->receipts->bids[ctx->receipts->count] = (struct landing_bid){
			.observation = *observation,
			.packet = packet,
			.decision = *decision,
		};
	}
	++ctx->receipts->count;
	++ctx->receipts->total;
	return 0;
}

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

static void print_bytes(const uint8_t *values, size_t length)
{
	putchar('[');
	for (size_t i = 0U; i < length; ++i) {
		printf("%s%u", i ? "," : "", values[i]);
	}
	putchar(']');
}

static int print_step(const struct picosystem_garden_world *world,
		      const struct picosystem_garden_landing_cache *cache,
		      const struct landing_receipts *receipts)
{
	printf("{\"tick\":%" PRIu32 ",\"hash\":\"%08" PRIx32 "\",\"created\":%" PRIu32
	       ",\"cache\":{\"tick\":%" PRIu32 ",\"samples\":%u,\"water\":",
	       world->logic_tick_count, picosystem_garden_world_hash(world),
	       world->seed_creation_count, cache->ecology_tick, cache->warmup_samples);
	print_bytes(cache->water, sizeof(cache->water));
	printf(",\"light\":");
	print_bytes(cache->light, sizeof(cache->light));
	printf(",\"occupied\":");
	print_bytes(cache->occupied, sizeof(cache->occupied));
	printf(",\"traces\":[");
	for (uint8_t i = 0U; i < PICOSYSTEM_GARDEN_LANDING_TRACES; ++i) {
		printf("%s[", i ? "," : "");
		for (uint8_t c = 0U; c < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++c) {
			printf("%s%u", c ? "," : "", cache->traces[i][c]);
		}
		putchar(']');
	}
	printf("]},\"bids\":[");
	for (uint16_t i = 0U; i < receipts->count; ++i) {
		const struct landing_bid *const bid = &receipts->bids[i];
		const struct picosystem_garden_agent_observation *const o = &bid->observation;
		printf("%s{\"tip\":%u,\"kind\":%u,\"x\":%u,\"base_x\":%u,\"dispersal\":%d,"
		       "\"candidates\":[",
		       i ? "," : "", o->tip_index, o->tissue_kind, o->tip_x, o->base_x,
		       o->genome.dispersal);
		for (uint8_t j = 0U; j < o->candidate_count; ++j) {
			printf("%s[%u,%u]", j ? "," : "", o->candidates[j].x,
			       o->candidates[j].flags);
		}
		printf("],\"action\":%u,\"priority\":%d,\"packet\":{\"version\":%u,\"valid\":%u,"
		       "\"samples\":%u,\"values\":[",
		       bid->decision.proposal.action, bid->decision.proposal.priority,
		       bid->packet.version, bid->packet.valid, bid->packet.warmup_samples);
		for (uint8_t j = 0U; j < PICOSYSTEM_GARDEN_LANDING_SOURCES; ++j) {
			if (j > 0U) {
				putchar(',');
			}
			print_bytes(bid->packet.values[j], PICOSYSTEM_GARDEN_LANDING_FIELDS);
		}
		printf("]}}");
	}
	printf("]}\n");
	return ferror(stdout) ? -EIO : 0;
}

int main(int argc, char **argv)
{
	uint32_t seed, end;
	const char *const mode = (argc == 7) ? argv[6] : "capture";
	const bool benchmark = (strcmp(mode, "plain") == 0) || (strcmp(mode, "sample") == 0) ||
			       (strcmp(mode, "observe") == 0);
	if (((argc != 5) && !((argc == 7) && (strcmp(argv[5], "--bench") == 0) && benchmark)) ||
	    (parse_u32(argv[3], &seed) != 0) || (seed == 0U) || (parse_u32(argv[4], &end) != 0) ||
	    (end == 0U) || (end > 128U * 3840U) ||
	    ((end % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) != 0U)) {
		fprintf(stderr,
			"Usage: %s RAINFED_SCENARIO baseline|adaptive SEED END_TICK "
			"[--bench plain|sample|observe]\n",
			argv[0]);
		return 2;
	}
	const struct toy_factory_garden_evaluation_scenario *scenario = NULL;
	for (unsigned int i = 0U; i < TOY_FACTORY_GARDEN_RAINFED_SCENARIO_COUNT; ++i) {
		if (strcmp(argv[1], toy_factory_garden_rainfed_scenarios[i].name) == 0) {
			scenario = &toy_factory_garden_rainfed_scenarios[i];
		}
	}
	const struct picosystem_garden_agent_policy *base = NULL;
	if (strcmp(argv[2], "baseline") == 0) {
		base = picosystem_garden_agent_baseline_policy();
	} else if (strcmp(argv[2], "adaptive") == 0) {
		base = picosystem_garden_agent_adaptive_policy();
	}
	if ((scenario == NULL) || (scenario->irrigation_period_ticks != 0U) || (base == NULL)) {
		return 2;
	}
	struct picosystem_garden_world world;
	struct picosystem_garden_landing_cache cache;
	struct toy_factory_garden_seedling_reserve_context reserve;
	struct picosystem_garden_agent_policy guarded;
	int err = toy_factory_garden_evaluation_reset(&world, scenario, seed);
	if (err == 0) {
		err = picosystem_garden_world_set_climate(&world,
							  PICOSYSTEM_GARDEN_CLIMATE_SEASONAL);
	}
	if (err == 0) {
		err = toy_factory_garden_seedling_reserve_offspring_init(base, &world, &reserve,
									 &guarded);
	}
	if (err == 0) {
		err = picosystem_garden_landing_reset(&world, &cache);
	}
	if (err != 0) {
		return 1;
	}
	struct landing_receipts receipts = {0};
	const struct landing_context context = {
		.world = &world,
		.cache = &cache,
		.base = &guarded,
		.receipts = &receipts,
		.retain = !benchmark,
	};
	struct picosystem_garden_agent_policy observed = guarded;
	observed.context = &context;
	observed.decide = observe_decide;
	const struct picosystem_garden_agent_policy *const policy =
		(!benchmark || (strcmp(mode, "observe") == 0)) ? &observed : &guarded;
	if (!benchmark) {
		printf("{\"version\":1,\"observer\":\"landing-shadow-v1\","
		       "\"phase\":\"after-seeds-before-growth\",\"scenario\":\"%s\","
		       "\"policy\":\"%s\",\"seed\":\"%08" PRIx32 "\",\"end\":%" PRIu32
		       ",\"climate\":\"seasonal\",\"guard\":true,\"dispersal\":\"%s\","
		       "\"origin\":\"%s\",\"cache_bytes\":%zu,\"packet_bytes\":%zu}\n",
		       scenario->name, argv[2], seed, end, PICOSYSTEM_GARDEN_DISPERSAL_NAME,
		       LANDING_ORIGIN, sizeof(cache),
		       sizeof(struct picosystem_garden_landing_packet));
		err = print_step(&world, &cache, &receipts);
	}
	const clock_t start = clock();
	for (uint32_t tick = 1U; (err == 0) && (tick <= end); ++tick) {
		receipts.count = 0U;
		err = (strcmp(mode, "plain") == 0)
			      ? picosystem_garden_world_step_with_policy(&world, policy)
			      : picosystem_garden_world_step_landing(&world, policy, &cache);
		if (!benchmark && (err == 0) &&
		    ((tick % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) == 0U)) {
			err = print_step(&world, &cache, &receipts);
		}
	}
	const clock_t finish = clock();
	if ((err == 0) && benchmark && (start != (clock_t)-1) && (finish != (clock_t)-1)) {
		printf("{\"mode\":\"%s\",\"hash\":\"%08" PRIx32 "\",\"created\":%" PRIu32
		       ",\"queries\":%" PRIu32 ",\"cpu_us\":%.0f}\n",
		       mode, picosystem_garden_world_hash(&world), world.seed_creation_count,
		       receipts.total, (double)(finish - start) * 1000000.0 / CLOCKS_PER_SEC);
	} else if (benchmark && (err == 0)) {
		err = -EIO;
	}
	if ((err != 0) || (fflush(stdout) != 0) || ferror(stdout)) {
		fprintf(stderr, "Landing audit failed: %d\n", err);
		return 1;
	}
	return 0;
}
