/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_RESEARCH_FOLIAGE_H_
#define TOY_FACTORY_RESEARCH_FOLIAGE_H_

#include "garden_leaf_family.h"
#include "garden_leaf_replay_route.h"
#include "garden_maintenance_step.h"
#include <stdio.h>

#define RESEARCH_FOLIAGE_FIRST  (152U * 3840U)
#define RESEARCH_FOLIAGE_END    (153U * 3840U)
#define RESEARCH_FOLIAGE_ROWS   256U
#define RESEARCH_FOLIAGE_LEAVES 32U

/* One session-owned allocation; borrowed route/world inputs last only for the
 * call. A pending callback must be reconciled after each successful step.
 * Discard on error (the session latches it). No allocation while stepping.
 */
struct research_foliage;
struct research_foliage_context {
	struct research_foliage *trace;
	const struct toy_factory_leaf_replay_route *next;
	const struct picosystem_garden_world *before;
};
int research_foliage_open(uint32_t lineage, struct research_foliage **out);
void research_foliage_close(struct research_foliage *trace);
bool research_foliage_active(uint32_t tick);
int research_foliage_decide(const struct picosystem_garden_world *world,
			    const struct picosystem_garden_leaf_policy *candidate,
			    const struct picosystem_garden_leaf_observation *observation,
			    const struct picosystem_garden_agent_memory *memory,
			    struct picosystem_garden_leaf_decision *decision, const void *context);
int research_foliage_finish(struct research_foliage *trace,
			    const struct picosystem_garden_world *before,
			    const struct toy_factory_maintenance_step *step);
int research_foliage_write(const struct research_foliage *trace, FILE *stream);
int research_foliage_canopy_start(struct research_foliage *trace);
int research_foliage_canopy_write(const struct research_foliage *trace, FILE *stream);

#endif
