/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef TOY_FACTORY_GARDEN_LIFETIMES_H_
#define TOY_FACTORY_GARDEN_LIFETIMES_H_

#include <stdint.h>

#include "garden_evaluation.h"
#include "garden_light.h"

#define TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS                                                    \
	(PICOSYSTEM_GARDEN_SUN_CYCLE_TICKS * PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR)
#define TOY_FACTORY_GARDEN_LIFETIME_AGE_BUCKETS 6U
#define TOY_FACTORY_GARDEN_LIFETIME_SUN_BUCKETS 8U
#define TOY_FACTORY_GARDEN_LIFETIME_CAUSES      4U

/* Host-only event ledger. Records outlive the world's compacted plant slots. */
struct toy_factory_garden_lifetime {
	uint32_t parent_id;
	uint32_t birth_tick;
	uint32_t death_tick;
	uint8_t species_id;
	uint8_t founder_index;
	/* energy, water, combined, other; CAUSES means still living. */
	uint8_t death_cause;
};

struct toy_factory_garden_lifetimes {
	struct toy_factory_garden_lifetime
		records[TOY_FACTORY_GARDEN_EVALUATION_MAX_TRACKED_LINEAGES + 1U];
	uint32_t count;
	uint32_t last_event_tick;
	uint8_t founder_count;
};

struct toy_factory_garden_mortality {
	uint64_t age_ticks_sum;
	uint32_t deaths;
	uint32_t minimum_age_ticks;
	uint32_t maximum_age_ticks;
	/* Age buckets: <1/4, <1/2, <1, <2, <4, >=4 cycles. Columns follow causes. */
	uint32_t age_by_cause[TOY_FACTORY_GARDEN_LIFETIME_AGE_BUCKETS]
			     [TOY_FACTORY_GARDEN_LIFETIME_CAUSES];
	/* Eight equal sun-phase bins; phase 0 is dawn, 128 is sunset. */
	uint32_t sun_phase_by_cause[TOY_FACTORY_GARDEN_LIFETIME_SUN_BUCKETS]
				   [TOY_FACTORY_GARDEN_LIFETIME_CAUSES];
};

struct toy_factory_garden_lifetime_metrics {
	uint32_t offspring_born;
	uint32_t eligible_offspring;
	uint32_t cycle_survivors;
	uint32_t died_before_cycle;
	uint32_t too_young_alive;
	uint32_t too_young_dead;
	uint32_t offspring_with_surviving_child;
	uint32_t cycle_survivors_with_surviving_child;
	uint32_t founders_with_surviving_child;
	uint32_t offspring_living_at_end;
	uint32_t founders_living_at_end;
	struct toy_factory_garden_mortality offspring_mortality;
	struct toy_factory_garden_mortality founder_mortality;
};

struct toy_factory_garden_lifetime_report {
	struct toy_factory_garden_lifetime_metrics total;
	struct toy_factory_garden_lifetime_metrics species[PICOSYSTEM_GARDEN_SPECIES_COUNT];
	struct toy_factory_garden_lifetime_metrics
		founders[TOY_FACTORY_GARDEN_EVALUATION_MAX_PLANTS];
};

/* Event inputs are chronological; rejected inputs leave the ledger unchanged. */
int toy_factory_garden_lifetimes_reset(struct toy_factory_garden_lifetimes *ledger);
int toy_factory_garden_lifetimes_birth(struct toy_factory_garden_lifetimes *ledger,
				       uint32_t lineage_id, uint32_t parent_id, uint8_t species_id,
				       uint32_t tick);
int toy_factory_garden_lifetimes_death(struct toy_factory_garden_lifetimes *ledger,
				       uint32_t lineage_id, uint32_t tick, uint8_t plant_flags);

/* Require at least a complete cycle of potential follow-up for the rate's cohort.
 * Alive at birth+cycle passes; death exactly on that boundary fails. Recent deaths
 * are known failures but kept outside that cohort alongside recent living births.
 * The cutoff must be at or after the latest event. No world state is accessed.
 */
int toy_factory_garden_lifetimes_summarize(const struct toy_factory_garden_lifetimes *ledger,
					   uint32_t cutoff_tick,
					   struct toy_factory_garden_lifetime_report *report);

/* Merge evaluator-sized groups (at most 64 trials of 4,096 lineages). */
void toy_factory_garden_lifetime_metrics_add(
	struct toy_factory_garden_lifetime_metrics *total,
	const struct toy_factory_garden_lifetime_metrics *part);

#endif /* TOY_FACTORY_GARDEN_LIFETIMES_H_ */
