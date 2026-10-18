/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_RESEARCH_TRACE_H_
#define TOY_FACTORY_RESEARCH_TRACE_H_

#include "garden_maintenance_step.h"
#include "garden_seed_audit.h"
#include <stdio.h>

#define RESEARCH_TRACE_STOP (256U * 3840U)

/* Private host diagnostic. Bounded allocation at open, none while recording.
 * No callbacks or mutable simulation pointers are retained. On any record error
 * the owning session must latch failure and refuse publication.
 */
struct research_trace;
int research_trace_open(uint8_t founder, struct research_trace **out);
void research_trace_close(struct research_trace *trace);
int research_trace_record(struct research_trace *trace,
			  const struct picosystem_garden_world *before,
			  const struct picosystem_garden_world *after,
			  const struct picosystem_garden_resource_audit *resources,
			  const struct picosystem_garden_seed_audit *seeds, const uint8_t *roots,
			  uint32_t count);
int research_trace_write(const struct research_trace *trace, FILE *stream, uint32_t tick);

#endif
