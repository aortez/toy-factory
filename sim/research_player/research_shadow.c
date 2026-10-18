/* SPDX-License-Identifier: Apache-2.0 */
#include "research_shadow.h"
#include "research_models.h"
#include "research_session.h"

#include <errno.h>
#include <inttypes.h>
#include <stdlib.h>
#include <string.h>

#define SHADOW_ROWS (16U * 256U * PICOSYSTEM_GARDEN_MAX_PLANTS)

struct shadow_row {
	uint32_t tick;
	uint32_t lineage;
	uint32_t parent;
	struct picosystem_garden_leaf_observation observation;
	struct picosystem_garden_agent_memory memory;
	uint8_t actions[3];
};

struct research_shadow {
	uint32_t first_tick;
	uint32_t end_tick;
	uint32_t count;
	uint8_t model;
	uint8_t founder;
	struct toy_factory_leaf_neural_model models[3];
	struct shadow_row rows[SHADOW_ROWS];
};

int research_shadow_open(uint8_t model, uint8_t founder, uint16_t first_day, uint16_t end_day,
			 struct research_shadow **out)
{
	if ((out == NULL) || (model >= 3U) || (founder == 0U) ||
	    (founder > PICOSYSTEM_GARDEN_MAX_PLANTS) || (end_day <= first_day) ||
	    (end_day > 256U) || (end_day - first_day > 16)) {
		return -EINVAL;
	}
	struct research_shadow *const shadow = calloc(1U, sizeof(*shadow));
	if (shadow == NULL) {
		return -ENOMEM;
	}
	shadow->model = model;
	shadow->founder = founder;
	shadow->first_tick = (uint32_t)first_day * RESEARCH_DAY_TICKS;
	shadow->end_tick = (uint32_t)end_day * RESEARCH_DAY_TICKS;
	for (uint8_t i = 0U; i < 3U; ++i) {
		const int err = toy_factory_leaf_neural_decode(research_model_bytes[i],
							       sizeof(research_model_bytes[i]),
							       &shadow->models[i]);
		if (err != 0) {
			free(shadow);
			return err;
		}
	}
	*out = shadow;
	return 0;
}

void research_shadow_close(struct research_shadow *shadow)
{
	free(shadow);
}

int research_shadow_decide(const struct picosystem_garden_world *world,
			   const struct picosystem_garden_leaf_policy *candidate,
			   const struct picosystem_garden_leaf_observation *observation,
			   const struct picosystem_garden_agent_memory *memory,
			   struct picosystem_garden_leaf_decision *decision, const void *opaque)
{
	const struct research_shadow_context *const context = opaque;
	if ((context == NULL) || (context->shadow == NULL) || (context->owners == NULL) ||
	    (world == NULL) || (candidate == NULL) || (candidate->decide == NULL) ||
	    (observation == NULL) || (memory == NULL) || (decision == NULL) ||
	    (observation->plant_index >= world->plant_count) ||
	    (observation->node_index >= world->node_count) ||
	    (world->nodes[observation->node_index].plant_index != observation->plant_index)) {
		return -EINVAL;
	}
	/* Always call the original policy, even outside the recording window. */
	struct picosystem_garden_leaf_decision actual;
	int err = candidate->decide(observation, memory, &actual, candidate->context);
	if (err != 0) {
		return err;
	}
	struct research_shadow *const shadow = context->shadow;
	const uint32_t tick = world->logic_tick_count;
	if ((tick <= shadow->first_tick) || (tick > shadow->end_tick)) {
		*decision = actual;
		return 0;
	}
	const struct picosystem_garden_plant *const plant =
		&world->plants[observation->plant_index];
	const struct toy_factory_leaf_family_owners *const owners = context->owners;
	const uint32_t id = plant->lineage_id, parent = plant->parent_lineage_id;
	if ((id == 0U) || (id > TOY_FACTORY_LEAF_FAMILY_MAX_LINEAGES)) {
		return -ERANGE;
	}
	/* Newborns can be observed before the end-of-step ancestry update. */
	uint8_t root;
	if (id <= owners->count) {
		root = owners->root[id];
	} else {
		if ((parent == 0U) || (parent > owners->count) || (parent >= id)) {
			return -ERANGE;
		}
		root = owners->root[parent];
	}
	if ((root == 0U) || (root > owners->founders)) {
		return -ERANGE;
	}
	if (root != shadow->founder) {
		*decision = actual;
		return 0;
	}
	if (shadow->count >= SHADOW_ROWS) {
		return -ENOSPC;
	}
	struct shadow_row row = {.tick = tick,
				 .lineage = id,
				 .parent = parent,
				 .observation = *observation,
				 .memory = *memory};
	for (uint8_t i = 0U; i < 3U; ++i) {
		struct picosystem_garden_leaf_decision predicted;
		err = toy_factory_leaf_neural_decide(observation, memory, &predicted,
						     &shadow->models[i]);
		if (err != 0) {
			return err;
		}
		if ((predicted.node_index != observation->node_index) ||
		    (memcmp(predicted.next_memory.hidden, memory->hidden, sizeof(memory->hidden)) !=
		     0) ||
		    ((i == shadow->model) &&
		     ((actual.action != predicted.action) ||
		      (actual.node_index != predicted.node_index) ||
		      (memcmp(actual.next_memory.hidden, predicted.next_memory.hidden,
			      sizeof(memory->hidden)) != 0)))) {
			return -EFAULT;
		}
		row.actions[i] = predicted.action;
	}
	shadow->rows[shadow->count++] = row;
	*decision = actual;
	return 0;
}

int research_shadow_write(const struct research_shadow *shadow, FILE *stream, uint32_t tick)
{
	if ((shadow == NULL) || (stream == NULL)) {
		return -EINVAL;
	}
	if ((tick < shadow->end_tick) || (tick > 256U * RESEARCH_DAY_TICKS)) {
		return -ERANGE;
	}
	fprintf(stream,
		"{\"schema\":\"garden-population-shadow-v1\",\"complete\":true,"
		"\"ticks\":%" PRIu32 ",\"first_tick\":%" PRIu32 ",\"end_tick\":%" PRIu32
		",\"founder\":%u,\"applied_model\":\"%s\","
		"\"models\":[\"initial\",\"s1-g3-c4\",\"s2-g3-c1\"],\"rows\":[",
		tick, shadow->first_tick, shadow->end_tick, shadow->founder,
		research_model_names[shadow->model]);
	for (uint32_t i = 0U; i < shadow->count; ++i) {
		const struct shadow_row *const row = &shadow->rows[i];
		const struct picosystem_garden_leaf_observation *const o = &row->observation;
		fprintf(stream,
			"%s{\"tick\":%" PRIu32 ",\"lineage\":%" PRIu32 ",\"parent\":%" PRIu32
			",\"node\":%u,\"plant\":%u,"
			"\"inputs\":[%u,%u,%u,%u,%u,%d,%d,%u,%u,%u,%u],\"memory\":[",
			i == 0U ? "" : ",", row->tick, row->lineage, row->parent, o->node_index,
			o->plant_index, o->condition, o->light, o->stored_energy, o->stored_water,
			o->mature_leaf_count, o->base_delta_x, o->base_delta_y,
			o->maintenance_energy, o->maintenance_water, o->renewal_energy,
			o->renewal_water);
		for (size_t m = 0U; m < sizeof(row->memory.hidden); ++m) {
			fprintf(stream, "%s%d", m == 0U ? "" : ",", row->memory.hidden[m]);
		}
		fprintf(stream, "],\"actions\":[%u,%u,%u]}", row->actions[0], row->actions[1],
			row->actions[2]);
	}
	fputs("]}\n", stream);
	return ferror(stream) ? -EIO : 0;
}
