/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_LANDING_RUN_H_
#define TOY_FACTORY_GARDEN_LANDING_RUN_H_

#include "garden_landing_neural.h"

#define TOY_FACTORY_GARDEN_LANDING_RUN_VERSION 1U

/* Complete same-build checkpoint, including recurrent memory inside the world.
 * No retained pointers: a value copy can resume independently on another thread.
 * Treat fields as read-only; mutate only through init/step. This is NOT a disk
 * format or a decoder/validator for arbitrary untrusted world bytes. Model and
 * mask are fixed for a run. Reinitializing is an explicit new evaluation.
 */
struct toy_factory_garden_landing_run {
	uint32_t version;
	uint32_t rules;
	struct picosystem_garden_world world;
	struct picosystem_garden_landing_cache cache;
	struct toy_factory_garden_landing_model model;
};

/* Initialize from a fully configured tick-zero world, gardener off. Output
 * cannot alias either input. Every failure leaves output unchanged.
 */
int toy_factory_garden_landing_run_init(const struct picosystem_garden_world *world,
					const struct toy_factory_garden_landing_model *model,
					struct toy_factory_garden_landing_run *run);

/* Single-owner operation; unlike the lower-level diagnostic wrapper, rollback
 * covers BOTH world and cache on error. Scratch copies are host-only stack cost.
 */
int toy_factory_garden_landing_run_step(struct toy_factory_garden_landing_run *run);

/* Exact natural-death accounting for evaluation. Required audit cannot alias
 * run. Failure leaves BOTH the complete run and audit unchanged.
 */
int toy_factory_garden_landing_run_step_death_audit(struct toy_factory_garden_landing_run *run,
						    struct picosystem_garden_death_audit *audit);

/* Diagnostic fingerprint for initialized runs: schema/build rules, legacy world
 * hash, every cache field and canonical model bytes. Not collision-free/authentic
 * identity. Record source/build hashes separately for cross-build experiments.
 */
int toy_factory_garden_landing_run_hash(const struct toy_factory_garden_landing_run *run,
					uint32_t *hash);

#endif
