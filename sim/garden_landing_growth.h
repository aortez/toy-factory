/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_LANDING_GROWTH_H_
#define TOY_FACTORY_GARDEN_LANDING_GROWTH_H_

#include "garden_landing_run.h"
#include "garden_reproduction_audit.h"
#include "garden_landing_placement.h"
#include "garden_landing_root_choice.h"
#include "garden_landing_root_allocation.h"
#include "garden_uptake_audit.h"

#define TOY_FACTORY_GARDEN_LANDING_GROWTH_VERSION 1U
#define TOY_FACTORY_GARDEN_LANDING_GROWTH_LIMIT   32U

enum toy_factory_garden_budget_mode {
	TOY_FACTORY_GARDEN_BUDGET_LEGACY,
	TOY_FACTORY_GARDEN_BUDGET_ELIGIBLE,
	TOY_FACTORY_GARDEN_BUDGET_SHOOT,
	TOY_FACTORY_GARDEN_BUDGET_COUNT,
};

/* Host-only construction experiment, always using water-eligible arbitration.
 * Zero disables the cap; 32 blocks allocation, never removes existing tissue.
 * Value copies are independent checkpoints. No device policy or model changes.
 */
struct toy_factory_garden_landing_growth_run {
	struct toy_factory_garden_landing_run base;
	uint8_t version;
	uint8_t node_limit;
	uint8_t budget_mode;
	/* Zero version preserves legacy growth/budget identities and behavior. */
	struct toy_factory_garden_placement_config placement;
	/* Zero is the historical fixed order. Nonzero is maintenance-aligned and
	 * part of run identity; only placement runs may opt in.
	 */
	uint32_t seed_order_after;
	struct toy_factory_garden_root_choice root_choice;
	struct toy_factory_garden_root_allocation root_allocation;
};

/* Pure, same-state budget receipt. No policy evaluation or random draw.
 * leader is the deepest active shoot (lowest node index breaks ties).
 * A formed flower releases the reservation; absent shoots reserve nothing.
 */
struct toy_factory_garden_budget_receipt {
	uint16_t leader;
	uint16_t required;
	uint8_t remaining;
	bool flower;
	bool allocates;
	bool allowed;
};
int toy_factory_garden_landing_budget_assess(
	const struct picosystem_garden_world *world,
	const struct picosystem_garden_agent_observation *observation,
	const struct picosystem_garden_agent_decision *decision, uint8_t mode,
	struct toy_factory_garden_budget_receipt *receipt);

/* Borrowed pre-arbitration inputs. Observer errors roll back the run and audit
 * outputs, but external context may be partial and must be discarded.
 */
typedef int (*toy_factory_garden_growth_observe_fn)(
	const struct picosystem_garden_world *world,
	const struct picosystem_garden_agent_observation *observation,
	const struct picosystem_garden_agent_decision *raw,
	const struct picosystem_garden_agent_decision *applied, void *context);
struct toy_factory_garden_growth_observer {
	toy_factory_garden_growth_observe_fn observe;
	void *context;
	struct picosystem_garden_reproduction_audit *reproduction;
	/* Optional disjoint host output; same publish-on-success contract. */
	struct picosystem_garden_uptake_audit *uptake;
};

int toy_factory_garden_landing_growth_init(const struct picosystem_garden_world *world,
					   const struct toy_factory_garden_landing_model *model,
					   uint8_t node_limit,
					   struct toy_factory_garden_landing_growth_run *run);
/* Separate GLB1 identity; explicit off/on reservation, fixed 32-node cap.
 * Both modes reject over-budget bids before ranking, never project them.
 */
int toy_factory_garden_landing_budget_init(const struct picosystem_garden_world *world,
					   const struct toy_factory_garden_landing_model *model,
					   uint8_t shoot_reserve,
					   struct toy_factory_garden_landing_growth_run *run);
/* Separate GLP1 identity, explicit off/on placement over either budget mode. */
int toy_factory_garden_landing_placement_init(const struct picosystem_garden_world *world,
					      const struct toy_factory_garden_landing_model *model,
					      uint8_t shoot_reserve, uint8_t enabled,
					      struct toy_factory_garden_landing_growth_run *run);
/* Required deaths/seeds and optional resources must not alias the run or each
 * other. All caller-owned state is unchanged on failure.
 */
int toy_factory_garden_landing_growth_step(struct toy_factory_garden_landing_growth_run *run,
					   struct picosystem_garden_death_audit *deaths,
					   struct picosystem_garden_seed_audit *seeds,
					   struct picosystem_garden_resource_audit *resources);
/* Placement receipt is required/disjoint, published only on success. Other
 * outputs and rollback follow growth_step; placement version must be enabled.
 */
int toy_factory_garden_landing_growth_step_placement(
	struct toy_factory_garden_landing_growth_run *run,
	struct picosystem_garden_death_audit *deaths, struct picosystem_garden_seed_audit *seeds,
	struct picosystem_garden_resource_audit *resources,
	struct toy_factory_garden_placement_audit *placement);
/* All outputs and observer/observe/reproduction are required and disjoint.
 * No observer state participates in the run hash or is retained by the run.
 */
int toy_factory_garden_landing_growth_step_observed(
	struct toy_factory_garden_landing_growth_run *run,
	struct picosystem_garden_death_audit *deaths, struct picosystem_garden_seed_audit *seeds,
	struct picosystem_garden_resource_audit *resources,
	const struct toy_factory_garden_growth_observer *observer);
int toy_factory_garden_landing_growth_hash(const struct toy_factory_garden_landing_growth_run *run,
					   uint32_t *hash);
/* Project an allocating EXTEND to WAIT before water eligibility/ranking.
 * Priority, tip, and next_memory are preserved. Nonallocating EXTEND and
 * FINISH_TIP retain normal cleanup/flowering semantics and expenses.
 */
int toy_factory_garden_landing_growth_apply(
	const struct picosystem_garden_agent_observation *observation, uint8_t node_limit,
	struct picosystem_garden_agent_decision *decision);

#endif
