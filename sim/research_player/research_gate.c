/* SPDX-License-Identifier: Apache-2.0 */
#include "research_gate.h"
#include "research_models.h"

#include <errno.h>
#include <inttypes.h>
#include <stdlib.h>
#include <string.h>

struct research_gate {
	struct toy_factory_leaf_neural_model model;
	uint32_t after_tick;
	uint8_t header[RESEARCH_GATE_HEADER_BYTES];
};

const char *research_gate_name(uint8_t variant)
{
	static const char *const names[] = {"none", "light", "condition", "both"};
	return variant < 4U ? names[variant] : NULL;
}

int research_gate_open(uint8_t variant, uint32_t after_tick, struct research_gate **out)
{
	if ((out == NULL) || (research_gate_name(variant) == NULL) ||
	    ((after_tick != 0U) && (after_tick != RESEARCH_GATE_AFTER))) {
		return -EINVAL;
	}
	struct research_gate *const gate = calloc(1U, sizeof(*gate));
	if (gate == NULL) {
		return -ENOMEM;
	}
	struct toy_factory_leaf_neural_model control;
	int err = toy_factory_leaf_neural_decode(research_model_bytes[0],
						 sizeof(research_model_bytes[0]), &control);
	if (err == 0) {
		err = toy_factory_leaf_neural_decode(research_model_bytes[1],
						     sizeof(research_model_bytes[1]), &gate->model);
	}
	if (err == 0) {
		for (uint8_t unit = 0U; unit < 2U; ++unit) {
			if ((variant & (1U << unit)) != 0U) {
				gate->model.hidden_bias[unit] = control.hidden_bias[unit];
				memcpy(gate->model.hidden_weights[unit],
				       control.hidden_weights[unit],
				       sizeof(gate->model.hidden_weights[unit]));
			}
		}
		err = toy_factory_leaf_neural_encode(&gate->model, gate->header + 12U,
						     TOY_FACTORY_LEAF_NEURAL_FILE_SIZE);
	}
	if (err != 0) {
		free(gate);
		return err;
	}
	memcpy(gate->header, "TGR1", 4U);
	gate->header[4] = variant;
	gate->header[5] = RESEARCH_GATE_FOUNDER;
	gate->after_tick = after_tick;
	for (uint8_t i = 0U; i < 4U; ++i) {
		gate->header[8U + i] = (uint8_t)(after_tick >> (8U * i));
	}
	*out = gate;
	return 0;
}

void research_gate_close(struct research_gate *gate)
{
	free(gate);
}

void research_gate_header(const struct research_gate *gate, uint8_t out[RESEARCH_GATE_HEADER_BYTES])
{
	memcpy(out, gate->header, sizeof(gate->header));
}

int research_gate_write(const struct research_gate *gate, FILE *stream)
{
	if ((gate == NULL) || (stream == NULL)) {
		return -EINVAL;
	}
	fprintf(stream,
		"{\"kind\":\"restore-leaf-gates\",\"variant\":\"%s\","
		"\"founder\":2,\"after_tick\":%" PRIu32 ",\"leaf_model_hex\":\"",
		research_gate_name(gate->header[4]), gate->after_tick);
	for (size_t i = 12U; i < sizeof(gate->header); ++i) {
		fprintf(stream, "%02x", (unsigned int)gate->header[i]);
	}
	fputs("\"}", stream);
	return ferror(stream) ? -EIO : 0;
}

int research_gate_decide(const struct picosystem_garden_world *world,
			 const struct picosystem_garden_leaf_policy *candidate,
			 const struct picosystem_garden_leaf_observation *observation,
			 const struct picosystem_garden_agent_memory *memory,
			 struct picosystem_garden_leaf_decision *decision, const void *opaque)
{
	const struct research_gate_context *const context = opaque;
	if ((context == NULL) || (context->gate == NULL) || (context->owners == NULL) ||
	    (world == NULL) || (candidate == NULL) || (candidate->decide == NULL) ||
	    (observation == NULL) || (memory == NULL) || (decision == NULL) ||
	    (observation->plant_index >= world->plant_count) ||
	    (observation->node_index >= world->node_count) ||
	    (world->nodes[observation->node_index].plant_index != observation->plant_index)) {
		return -EINVAL;
	}
	struct picosystem_garden_leaf_decision result;
	int err;
	if (world->logic_tick_count <= context->gate->after_tick) {
		err = candidate->decide(observation, memory, &result, candidate->context);
	} else {
		const struct picosystem_garden_plant *const plant =
			&world->plants[observation->plant_index];
		const struct toy_factory_leaf_family_owners *const owners = context->owners;
		const uint32_t id = plant->lineage_id, parent = plant->parent_lineage_id;
		if ((id == 0U) || (id > TOY_FACTORY_LEAF_FAMILY_MAX_LINEAGES) ||
		    (owners->count > TOY_FACTORY_LEAF_FAMILY_MAX_LINEAGES)) {
			return -ERANGE;
		}
		/* A newborn can be observed before the session records its birth.
		 * Its parent is in the persistent ledger, even after decomposition.
		 */
		if ((id > owners->count) &&
		    ((parent == 0U) || (parent > owners->count) || (parent >= id))) {
			return -ERANGE;
		}
		const uint8_t root = owners->root[id <= owners->count ? id : parent];
		if ((root == 0U) || (root > owners->founders)) {
			return -ERANGE;
		}
		err = root == RESEARCH_GATE_FOUNDER
			      ? toy_factory_leaf_neural_decide(observation, memory, &result,
							       &context->gate->model)
			      : candidate->decide(observation, memory, &result, candidate->context);
	}
	if (err != 0) {
		return err;
	}
	if ((result.node_index != observation->node_index) ||
	    (result.action > PICOSYSTEM_GARDEN_LEAF_RENEW) ||
	    (memcmp(result.next_memory.hidden, memory->hidden, sizeof(memory->hidden)) != 0)) {
		return -EFAULT;
	}
	*decision = result;
	return 0;
}
