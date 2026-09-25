/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "garden_lifetimes.h"

#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>

int toy_factory_garden_lifetimes_reset(struct toy_factory_garden_lifetimes *ledger)
{
	if (ledger == NULL) {
		return -EINVAL;
	}
	memset(ledger, 0, sizeof(*ledger));
	return 0;
}

int toy_factory_garden_lifetimes_birth(struct toy_factory_garden_lifetimes *ledger,
				       uint32_t lineage_id, uint32_t parent_id, uint8_t species_id,
				       uint32_t tick)
{
	if (ledger == NULL) {
		return -EINVAL;
	}
	if ((lineage_id == 0U) || (lineage_id != ledger->count + 1U) || (parent_id >= lineage_id) ||
	    (species_id >= PICOSYSTEM_GARDEN_SPECIES_COUNT) || (tick < ledger->last_event_tick)) {
		return -ERANGE;
	}
	if (lineage_id > TOY_FACTORY_GARDEN_EVALUATION_MAX_TRACKED_LINEAGES) {
		return -ENOSPC;
	}
	uint8_t founder_index;
	if (parent_id == 0U) {
		if (ledger->founder_count == TOY_FACTORY_GARDEN_EVALUATION_MAX_PLANTS) {
			return -ENOSPC;
		}
		founder_index = ledger->founder_count;
	} else {
		const struct toy_factory_garden_lifetime *const parent =
			&ledger->records[parent_id];
		if (parent->species_id != species_id) {
			return -EINVAL;
		}
		founder_index = parent->founder_index;
	}
	ledger->records[lineage_id] = (struct toy_factory_garden_lifetime){
		.parent_id = parent_id,
		.birth_tick = tick,
		.species_id = species_id,
		.founder_index = founder_index,
		.death_cause = TOY_FACTORY_GARDEN_LIFETIME_CAUSES,
	};
	++ledger->count;
	ledger->last_event_tick = tick;
	if (parent_id == 0U) {
		++ledger->founder_count;
	}
	return 0;
}

int toy_factory_garden_lifetimes_death(struct toy_factory_garden_lifetimes *ledger,
				       uint32_t lineage_id, uint32_t tick, uint8_t plant_flags)
{
	if (ledger == NULL) {
		return -EINVAL;
	}
	if ((lineage_id == 0U) || (lineage_id > ledger->count) ||
	    (tick < ledger->last_event_tick)) {
		return -ERANGE;
	}
	if (((plant_flags & PICOSYSTEM_GARDEN_PLANT_DEAD) == 0U) ||
	    ((plant_flags & (uint8_t)~PICOSYSTEM_GARDEN_PLANT_VALID_FLAGS) != 0U)) {
		return -EINVAL;
	}
	struct toy_factory_garden_lifetime *const record = &ledger->records[lineage_id];
	if (record->death_cause != TOY_FACTORY_GARDEN_LIFETIME_CAUSES) {
		return -EEXIST;
	}
	const uint8_t shortage = plant_flags & (PICOSYSTEM_GARDEN_PLANT_ENERGY_SHORTAGE |
						PICOSYSTEM_GARDEN_PLANT_WATER_SHORTAGE);
	uint8_t cause = 3U;
	if (shortage == PICOSYSTEM_GARDEN_PLANT_ENERGY_SHORTAGE) {
		cause = 0U;
	} else if (shortage == PICOSYSTEM_GARDEN_PLANT_WATER_SHORTAGE) {
		cause = 1U;
	} else if (shortage != 0U) {
		cause = 2U;
	}
	record->death_tick = tick;
	record->death_cause = cause;
	ledger->last_event_tick = tick;
	return 0;
}

static bool survived_cycle(const struct toy_factory_garden_lifetime *record, uint32_t cutoff)
{
	return ((cutoff - record->birth_tick) >= TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS) &&
	       ((record->death_cause == TOY_FACTORY_GARDEN_LIFETIME_CAUSES) ||
		((record->death_tick - record->birth_tick) >
		 TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS));
}

static void record_mortality(struct toy_factory_garden_mortality *metrics,
			     const struct toy_factory_garden_lifetime *record)
{
	static const uint32_t age_limits[] = {
		TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS / 4U,
		TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS / 2U,
		TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS,
		TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS * 2U,
		TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS * 4U,
	};
	const uint32_t age = record->death_tick - record->birth_tick;
	uint8_t bucket = 0U;
	while ((bucket < TOY_FACTORY_GARDEN_LIFETIME_AGE_BUCKETS - 1U) &&
	       (age >= age_limits[bucket])) {
		++bucket;
	}
	const struct picosystem_garden_sun sun = picosystem_garden_sun_at(
		record->death_tick / PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR);
	const uint8_t sun_bucket = sun.phase / (PICOSYSTEM_GARDEN_SUN_CYCLE_TICKS /
						TOY_FACTORY_GARDEN_LIFETIME_SUN_BUCKETS);
	++metrics->age_by_cause[bucket][record->death_cause];
	++metrics->sun_phase_by_cause[sun_bucket][record->death_cause];
	if ((metrics->deaths == 0U) || (age < metrics->minimum_age_ticks)) {
		metrics->minimum_age_ticks = age;
	}
	if (age > metrics->maximum_age_ticks) {
		metrics->maximum_age_ticks = age;
	}
	metrics->age_ticks_sum += age;
	++metrics->deaths;
}

static void record_metrics(struct toy_factory_garden_lifetime_metrics *metrics,
			   const struct toy_factory_garden_lifetime *record, uint32_t cutoff,
			   bool has_surviving_child)
{
	const bool alive = record->death_cause == TOY_FACTORY_GARDEN_LIFETIME_CAUSES;
	if (record->parent_id == 0U) {
		metrics->founders_living_at_end += alive ? 1U : 0U;
		metrics->founders_with_surviving_child += has_surviving_child ? 1U : 0U;
		if (!alive) {
			record_mortality(&metrics->founder_mortality, record);
		}
		return;
	}
	++metrics->offspring_born;
	metrics->offspring_living_at_end += alive ? 1U : 0U;
	if ((cutoff - record->birth_tick) < TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS) {
		if (alive) {
			++metrics->too_young_alive;
		} else {
			++metrics->too_young_dead;
		}
	} else {
		++metrics->eligible_offspring;
		if (survived_cycle(record, cutoff)) {
			++metrics->cycle_survivors;
			metrics->cycle_survivors_with_surviving_child +=
				has_surviving_child ? 1U : 0U;
		} else {
			++metrics->died_before_cycle;
		}
	}
	metrics->offspring_with_surviving_child += has_surviving_child ? 1U : 0U;
	if (!alive) {
		record_mortality(&metrics->offspring_mortality, record);
	}
}

int toy_factory_garden_lifetimes_summarize(const struct toy_factory_garden_lifetimes *ledger,
					   uint32_t cutoff_tick,
					   struct toy_factory_garden_lifetime_report *report)
{
	if ((ledger == NULL) || (report == NULL)) {
		return -EINVAL;
	}
	if (cutoff_tick < ledger->last_event_tick) {
		return -ERANGE;
	}
	bool has_surviving_child[TOY_FACTORY_GARDEN_EVALUATION_MAX_TRACKED_LINEAGES + 1U] = {false};
	memset(report, 0, sizeof(*report));
	for (uint32_t id = 1U; id <= ledger->count; ++id) {
		const struct toy_factory_garden_lifetime *const record = &ledger->records[id];
		if ((record->parent_id != 0U) && survived_cycle(record, cutoff_tick)) {
			has_surviving_child[record->parent_id] = true;
		}
	}
	for (uint32_t id = 1U; id <= ledger->count; ++id) {
		const struct toy_factory_garden_lifetime *const record = &ledger->records[id];
		record_metrics(&report->total, record, cutoff_tick, has_surviving_child[id]);
		record_metrics(&report->species[record->species_id], record, cutoff_tick,
			       has_surviving_child[id]);
		record_metrics(&report->founders[record->founder_index], record, cutoff_tick,
			       has_surviving_child[id]);
	}
	return 0;
}

static void add_mortality(struct toy_factory_garden_mortality *total,
			  const struct toy_factory_garden_mortality *part)
{
	if (part->deaths == 0U) {
		return;
	}
	if ((total->deaths == 0U) || (part->minimum_age_ticks < total->minimum_age_ticks)) {
		total->minimum_age_ticks = part->minimum_age_ticks;
	}
	if (part->maximum_age_ticks > total->maximum_age_ticks) {
		total->maximum_age_ticks = part->maximum_age_ticks;
	}
	total->deaths += part->deaths;
	total->age_ticks_sum += part->age_ticks_sum;
	for (uint8_t cause = 0U; cause < TOY_FACTORY_GARDEN_LIFETIME_CAUSES; ++cause) {
		for (uint8_t bucket = 0U; bucket < TOY_FACTORY_GARDEN_LIFETIME_AGE_BUCKETS;
		     ++bucket) {
			total->age_by_cause[bucket][cause] += part->age_by_cause[bucket][cause];
		}
		for (uint8_t bucket = 0U; bucket < TOY_FACTORY_GARDEN_LIFETIME_SUN_BUCKETS;
		     ++bucket) {
			total->sun_phase_by_cause[bucket][cause] +=
				part->sun_phase_by_cause[bucket][cause];
		}
	}
}

void toy_factory_garden_lifetime_metrics_add(struct toy_factory_garden_lifetime_metrics *total,
					     const struct toy_factory_garden_lifetime_metrics *part)
{
	total->offspring_born += part->offspring_born;
	total->eligible_offspring += part->eligible_offspring;
	total->cycle_survivors += part->cycle_survivors;
	total->died_before_cycle += part->died_before_cycle;
	total->too_young_alive += part->too_young_alive;
	total->too_young_dead += part->too_young_dead;
	total->offspring_with_surviving_child += part->offspring_with_surviving_child;
	total->cycle_survivors_with_surviving_child += part->cycle_survivors_with_surviving_child;
	total->founders_with_surviving_child += part->founders_with_surviving_child;
	total->offspring_living_at_end += part->offspring_living_at_end;
	total->founders_living_at_end += part->founders_living_at_end;
	add_mortality(&total->offspring_mortality, &part->offspring_mortality);
	add_mortality(&total->founder_mortality, &part->founder_mortality);
}
