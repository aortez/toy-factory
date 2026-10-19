/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_RESEARCH_FALLBACK_H_
#define TOY_FACTORY_RESEARCH_FALLBACK_H_

#include "garden_landing_placement.h"

#define RESEARCH_FALLBACK_HEADER_BYTES 12U

struct toy_factory_leaf_family_owners;
struct toy_factory_leaf_replay;
struct toy_factory_maintenance_run;
struct picosystem_garden_leaf_policy;
struct picosystem_garden_death_audit;
struct picosystem_garden_seed_audit;
struct picosystem_garden_resource_audit;
struct toy_factory_garden_growth_observer;
struct toy_factory_leaf_replay_route;

/* Explicit borrowed placement policy, separate from diagnostic observers and
 * leaf routing. The owner table survives slot reclamation; no state is retained
 * by the step. A NULL route preserves the frozen placement behavior.
 */
struct research_fallback_route {
	const struct toy_factory_leaf_family_owners *owners;
};

int research_fallback_decide(const struct picosystem_garden_seed_placement *observation,
			     uint8_t *choice,
			     const struct toy_factory_garden_placement_context *base,
			     const struct research_fallback_route *route);

/* Private owned step, with the frozen replay's rollback/publication semantics.
 * Models/setup must come from checked session initialization, not arbitrary
 * caller-supplied checkpoints. Observer context may be partial after failure.
 */
int research_fallback_step_owned(struct toy_factory_leaf_replay *run,
				 struct picosystem_garden_death_audit *deaths,
				 struct picosystem_garden_seed_audit *seeds,
				 struct picosystem_garden_resource_audit *resources,
				 const struct toy_factory_garden_growth_observer *observer,
				 const struct toy_factory_leaf_replay_route *leaf,
				 const struct research_fallback_route *placement);
int research_fallback_step_internal(struct toy_factory_maintenance_run *run,
				    const struct picosystem_garden_leaf_policy *leaf,
				    struct picosystem_garden_death_audit *deaths,
				    struct picosystem_garden_seed_audit *seeds,
				    struct picosystem_garden_resource_audit *resources,
				    const struct toy_factory_garden_growth_observer *observer,
				    const struct toy_factory_leaf_replay_route *route,
				    const struct research_fallback_route *placement);

#endif
