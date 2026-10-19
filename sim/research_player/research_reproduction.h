/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_RESEARCH_REPRODUCTION_H_
#define TOY_FACTORY_RESEARCH_REPRODUCTION_H_

#include "garden_landing_growth.h"
#include <stdio.h>

#define RESEARCH_REPRODUCTION_FIRST    (128U * 3840U)
#define RESEARCH_REPRODUCTION_END      (232U * 3840U)
#define RESEARCH_REPRODUCTION_CADENCE  60U
#define RESEARCH_REPRODUCTION_LINEAGES 128U
#define RESEARCH_REPRODUCTION_OPENINGS 512U

/* Session-owned, bounded allocation at open; no step allocation or borrowed
 * pointers retained. Any record failure invalidates the diagnostic; the owner
 * must latch it and refuse publication. Record every cadence tick in (first,end].
 */
struct research_reproduction;
int research_reproduction_open(struct research_reproduction **out);
void research_reproduction_close(struct research_reproduction *trace);
int research_reproduction_record(struct research_reproduction *trace, uint32_t tick,
				 const struct picosystem_garden_reproduction_audit *audit);
int research_reproduction_write(const struct research_reproduction *trace, FILE *stream);
int research_reproduction_growth(const struct picosystem_garden_world *world,
				 const struct picosystem_garden_agent_observation *observation,
				 const struct picosystem_garden_agent_decision *raw,
				 const struct picosystem_garden_agent_decision *applied,
				 void *context);

#endif
