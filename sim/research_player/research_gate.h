/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_RESEARCH_GATE_H_
#define TOY_FACTORY_RESEARCH_GATE_H_

#include "garden_leaf_family.h"
#include "garden_leaf_replay_route.h"
#include <stdio.h>

#define RESEARCH_GATE_AFTER        (208U * 3840U)
#define RESEARCH_GATE_FOUNDER      2U
#define RESEARCH_GATE_HEADER_BYTES (12U + TOY_FACTORY_LEAF_NEURAL_FILE_SIZE)

/* Fixed-case intervention owned by the host session. One bounded allocation,
 * immutable derived model and identity, no step allocation or retained world.
 */
struct research_gate;
struct research_gate_context {
	const struct research_gate *gate;
	const struct toy_factory_leaf_family_owners *owners;
};
const char *research_gate_name(uint8_t variant);
/* Only the fixed day-zero and day-208 activation times are supported. */
int research_gate_open(uint8_t variant, uint32_t after_tick, struct research_gate **out);
void research_gate_close(struct research_gate *gate);
void research_gate_header(const struct research_gate *gate,
			  uint8_t out[RESEARCH_GATE_HEADER_BYTES]);
int research_gate_write(const struct research_gate *gate, FILE *stream);
int research_gate_decide(const struct picosystem_garden_world *world,
			 const struct picosystem_garden_leaf_policy *candidate,
			 const struct picosystem_garden_leaf_observation *observation,
			 const struct picosystem_garden_agent_memory *memory,
			 struct picosystem_garden_leaf_decision *decision, const void *context);

#endif
