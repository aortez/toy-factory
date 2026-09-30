/* SPDX-License-Identifier: Apache-2.0 */
#ifndef PICOSYSTEM_GARDEN_LANDING_H_
#define PICOSYSTEM_GARDEN_LANDING_H_

#include "garden_agent.h"
#include "garden_death_audit.h"
#include "garden_seed_audit.h"
#include "garden_resource_audit.h"

#if defined(__ZEPHYR__)
#error "Landing observations are restricted to host diagnostics"
#endif

#define PICOSYSTEM_GARDEN_LANDING_VERSION 1U
#define PICOSYSTEM_GARDEN_LANDING_FIELDS  8U
#define PICOSYSTEM_GARDEN_LANDING_SOURCES (1U + PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES)
#define PICOSYSTEM_GARDEN_LANDING_TRACES  4U
#define PICOSYSTEM_GARDEN_LANDING_LIVE    1U
#define PICOSYSTEM_GARDEN_LANDING_DEAD    2U

struct picosystem_garden_landing_cache {
	uint32_t ecology_tick;
	uint16_t warmup_samples;
	uint8_t version;
	uint8_t flags;
	uint16_t traces[PICOSYSTEM_GARDEN_LANDING_TRACES][PICOSYSTEM_GARDEN_GRID_COLUMNS];
	uint8_t water[PICOSYSTEM_GARDEN_GRID_COLUMNS];
	uint8_t light[PICOSYSTEM_GARDEN_GRID_COLUMNS];
	uint8_t occupied[PICOSYSTEM_GARDEN_GRID_COLUMNS];
};

struct picosystem_garden_landing_packet {
	uint8_t version;
	uint8_t valid;
	uint16_t warmup_samples;
	uint8_t values[PICOSYSTEM_GARDEN_LANDING_SOURCES][PICOSYSTEM_GARDEN_LANDING_FIELDS];
};

/* Reset after complete scenario setup at tick zero, gardener off. Caller owns
 * one cache per world. Error leaves output unchanged. No buffers may alias.
 */
int picosystem_garden_landing_reset(const struct picosystem_garden_world *world,
				    struct picosystem_garden_landing_cache *cache);

/* Sample once, after seed admission and before growth, including steps with no
 * bids. The policy may read this cache during the step. Only ordinary ecology
 * and isolated wide/flower dispersal are supported. The cache is restored on
 * error; the world need not roll back an internal error. Replay/reset before
 * continuing if the world advanced. This is not an authoritative world field.
 */
int picosystem_garden_world_step_landing(struct picosystem_garden_world *world,
					 const struct picosystem_garden_agent_policy *policy,
					 struct picosystem_garden_landing_cache *cache);

/* Same step with exact maintenance-death receipts, before slot compaction can
 * hide them from a post-step census. Audit is required, non-aliasing, replaced
 * only on success. World/cache failure semantics match the wrapper above.
 */
int picosystem_garden_world_step_landing_death_audit(
	struct picosystem_garden_world *world, const struct picosystem_garden_agent_policy *policy,
	struct picosystem_garden_landing_cache *cache, struct picosystem_garden_death_audit *audit);

/* Both receipts from one authoritative step; required, disjoint outputs are
 * published together only on success. No second step or observer RNG draws.
 */
int picosystem_garden_world_step_landing_audits(struct picosystem_garden_world *world,
						const struct picosystem_garden_agent_policy *policy,
						struct picosystem_garden_landing_cache *cache,
						struct picosystem_garden_death_audit *deaths,
						struct picosystem_garden_seed_audit *seeds);

/* Same contract, additionally retaining exact resource-stage snapshots. All
 * outputs are required, disjoint and published together only on success.
 */
int picosystem_garden_world_step_landing_resources(
	struct picosystem_garden_world *world, const struct picosystem_garden_agent_policy *policy,
	struct picosystem_garden_landing_cache *cache, struct picosystem_garden_death_audit *deaths,
	struct picosystem_garden_seed_audit *seeds,
	struct picosystem_garden_resource_audit *resources);

/* Pure query using an already frozen cache. No RNG/clock/private memory input.
 * Output unchanged on error; root/OOB sources are explicitly invalid and zero.
 * The caller binds this cache to the correct world and pre-growth phase.
 */
int picosystem_garden_landing_observe(const struct picosystem_garden_landing_cache *cache,
				      const struct picosystem_garden_agent_observation *observation,
				      struct picosystem_garden_landing_packet *packet);

#endif
