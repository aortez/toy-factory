/* SPDX-License-Identifier: Apache-2.0 */
#include "research_purchase.h"
#include "research_fallback.h"
#include "garden_daylight_policy.h"

#include <errno.h>
#include <inttypes.h>
#include <stdlib.h>

struct purchase_record {
	struct picosystem_garden_seed_placement observation;
	struct toy_factory_placement_scores scores;
	struct picosystem_garden_seed_sites sites;
	struct picosystem_garden_plant plants[PICOSYSTEM_GARDEN_MAX_PLANTS];
	uint16_t nodes;
	uint8_t count;
	uint8_t seeds;
	uint8_t ordinary;
	uint8_t selected;
};

struct research_purchase {
	struct purchase_record records[RESEARCH_PURCHASE_LIMIT];
	uint16_t count;
};

int research_purchase_open(struct research_purchase **out)
{
	if (out == NULL) {
		return -EINVAL;
	}
	struct research_purchase *const result = calloc(1U, sizeof(*result));
	if (result == NULL) {
		return -ENOMEM;
	}
	*out = result;
	return 0;
}

void research_purchase_close(struct research_purchase *trace)
{
	free(trace);
}

int research_purchase_growth(const struct picosystem_garden_world *world,
			     const struct picosystem_garden_agent_observation *observation,
			     const struct picosystem_garden_agent_decision *raw,
			     const struct picosystem_garden_agent_decision *applied, void *context)
{
	return world != NULL && observation != NULL && raw != NULL && applied != NULL &&
			       context != NULL
		       ? 0
		       : -EINVAL;
}

int research_purchase_decide(const struct picosystem_garden_seed_placement *observation,
			     uint8_t *choice, const void *opaque)
{
	const struct research_purchase_context *const context = opaque;
	if (context == NULL || context->base == NULL || observation == NULL || choice == NULL) {
		return -EINVAL;
	}
	const struct toy_factory_garden_growth_observer *const observer = context->observer;
	if (observer == NULL || observer->observe != research_purchase_growth ||
	    observation->logic_tick < RESEARCH_PURCHASE_BEGIN ||
	    observation->logic_tick >= RESEARCH_PURCHASE_END) {
		return research_fallback_decide(observation, choice, context->base,
						context->fallback);
	}
	struct research_purchase *const trace = observer->context;
	const struct picosystem_garden_world *const world = context->base->world;
	if (trace == NULL || world == NULL || context->base->config == NULL ||
	    world->plant_count > PICOSYSTEM_GARDEN_MAX_PLANTS ||
	    world->logic_tick_count != observation->logic_tick) {
		return -EINVAL;
	}
	if (trace->count == RESEARCH_PURCHASE_LIMIT) {
		return -ENOSPC;
	}
	struct purchase_record result = {.observation = *observation,
					 .count = world->plant_count,
					 .seeds = world->seed_count,
					 .nodes = world->node_count};
	struct toy_factory_placement_scene scene = {.tick = observation->logic_tick,
						    .count = world->plant_count};
	for (uint8_t i = 0U; i < world->plant_count; ++i) {
		result.plants[i] = world->plants[i];
		const struct picosystem_garden_plant *const p = &world->plants[i];
		scene.plants[i] = (struct toy_factory_placement_plant){
			.lineage = p->lineage_id,
			.column = p->base_column,
			.trait = p->genome.dispersal,
			.dead = (p->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) != 0U};
	}
	int err = toy_factory_garden_placement_choose(observation, context->base->config->enabled,
						      &result.ordinary);
	if (err == 0) {
		err = toy_factory_placement_rank(&scene, observation, result.ordinary,
						 &result.scores);
	}
	if (err == 0) {
		err = picosystem_garden_world_seed_sites(world, &result.sites);
	}
	if (err == 0) {
		err = research_fallback_decide(observation, &result.selected, context->base,
					       context->fallback);
	}
	if (err != 0) {
		return err;
	}
	trace->records[trace->count++] = result;
	*choice = result.selected;
	return 0;
}

int research_purchase_write(const struct research_purchase *trace, uint32_t tick, FILE *stream)
{
	if (trace == NULL || stream == NULL) {
		return -EINVAL;
	}
	if (tick < RESEARCH_PURCHASE_END) {
		return -ERANGE;
	}
	fprintf(stream,
		"{\"schema\":\"garden-purchase-trace-v1\",\"first_tick\":%u,"
		"\"end_tick_exclusive\":%u,\"limit\":%u,\"purchases\":[",
		RESEARCH_PURCHASE_BEGIN, RESEARCH_PURCHASE_END, RESEARCH_PURCHASE_LIMIT);
	for (uint16_t i = 0U; i < trace->count; ++i) {
		const struct purchase_record *const r = &trace->records[i];
		const struct picosystem_garden_seed_placement *const o = &r->observation;
		fprintf(stream,
			"%s{\"tick\":%" PRIu32 ",\"parent\":%" PRIu32 ",\"random\":%" PRIu32
			",\"origin\":%u,\"dispersal\":%d,"
			"\"blocked_choices\":%u,\"ordinary\":%u,\"selected\":%u,"
			"\"clear\":%" PRIu32 ",\"legal\":%" PRIu32
			",\"node_count\":%u,\"seed_count\":%u,\"columns\":[",
			i ? "," : "", o->logic_tick, o->parent, o->random, o->origin, o->dispersal,
			o->blocked_choices, r->ordinary, r->selected, r->scores.clear,
			r->scores.legal, r->nodes, r->seeds);
		for (uint8_t j = 0U; j < PICOSYSTEM_GARDEN_PLACEMENT_CHOICES; ++j) {
			fprintf(stream, "%s%u", j ? "," : "", o->columns[j]);
		}
		fputs("],\"site_blockers\":[", stream);
		for (uint8_t j = 0U; j < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++j) {
			fprintf(stream, "%s%u", j ? "," : "", r->sites.blockers[j]);
		}
		fputs("],\"plants\":[", stream);
		for (uint8_t j = 0U; j < r->count; ++j) {
			const struct picosystem_garden_plant *const p = &r->plants[j];
			fprintf(stream,
				"%s{\"id\":%" PRIu32 ",\"parent\":%" PRIu32
				",\"age_ecology_ticks\":%" PRIu32 ",\"column\":%u,"
				"\"species\":%u,\"dead\":%s,\"energy\":%u,\"water\":%u,"
				"\"stress\":%u,\"nodes\":%u,\"last_energy_income\":%u,"
				"\"last_water_income\":%u}",
				j ? "," : "", p->lineage_id, p->parent_lineage_id,
				p->age_ecology_ticks, p->base_column, p->species_id,
				p->flags & PICOSYSTEM_GARDEN_PLANT_DEAD ? "true" : "false",
				p->stored_energy, p->stored_water, p->stress, p->node_count,
				p->last_energy_income, p->last_water_income);
		}
		fputs("]}", stream);
	}
	fputs("]}\n", stream);
	return ferror(stream) || fflush(stream) != 0 ? -EIO : 0;
}
