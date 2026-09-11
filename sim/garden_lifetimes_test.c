/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "garden_lifetimes.h"

#define CHECK(condition)                                                                           \
	do {                                                                                       \
		if (!(condition)) {                                                                \
			fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #condition);            \
			return 1;                                                                  \
		}                                                                                  \
	} while (0)

static struct toy_factory_garden_lifetimes ledger;
static struct toy_factory_garden_lifetimes saved;
static struct toy_factory_garden_lifetime_report report;

static int test_validation_and_capacity(void)
{
	CHECK(toy_factory_garden_lifetimes_reset(NULL) == -EINVAL);
	CHECK(toy_factory_garden_lifetimes_reset(&ledger) == 0);
	CHECK(toy_factory_garden_lifetimes_summarize(&ledger, 0U, &report) == 0);
	CHECK(report.total.offspring_born == 0U);
	CHECK(report.total.founder_mortality.deaths == 0U);
	CHECK(toy_factory_garden_lifetimes_birth(NULL, 1U, 0U, 0U, 0U) == -EINVAL);
	CHECK(toy_factory_garden_lifetimes_birth(&ledger, 0U, 0U, 0U, 0U) == -ERANGE);
	CHECK(toy_factory_garden_lifetimes_birth(&ledger, 2U, 0U, 0U, 0U) == -ERANGE);
	CHECK(toy_factory_garden_lifetimes_birth(&ledger, 1U, 1U, 0U, 0U) == -ERANGE);
	CHECK(toy_factory_garden_lifetimes_birth(&ledger, 1U, 0U, PICOSYSTEM_GARDEN_SPECIES_COUNT,
						 0U) == -ERANGE);
	CHECK(ledger.count == 0U);
	CHECK(toy_factory_garden_lifetimes_birth(&ledger, 1U, 0U, 0U, 100U) == 0);
	saved = ledger;
	CHECK(toy_factory_garden_lifetimes_birth(&ledger, 1U, 0U, 0U, 100U) == -ERANGE);
	CHECK(toy_factory_garden_lifetimes_birth(&ledger, 2U, 1U, 1U, 100U) == -EINVAL);
	CHECK(toy_factory_garden_lifetimes_birth(&ledger, 2U, 1U, 0U, 99U) == -ERANGE);
	CHECK(toy_factory_garden_lifetimes_death(NULL, 1U, 100U, 1U) == -EINVAL);
	CHECK(toy_factory_garden_lifetimes_death(&ledger, 0U, 100U, 1U) == -ERANGE);
	CHECK(toy_factory_garden_lifetimes_death(&ledger, 2U, 100U, 1U) == -ERANGE);
	CHECK(toy_factory_garden_lifetimes_death(&ledger, 1U, 99U, 1U) == -ERANGE);
	CHECK(toy_factory_garden_lifetimes_death(&ledger, 1U, 100U, 0U) == -EINVAL);
	CHECK(toy_factory_garden_lifetimes_death(&ledger, 1U, 100U, UINT8_MAX) == -EINVAL);
	CHECK(memcmp(&saved, &ledger, sizeof(ledger)) == 0);
	CHECK(toy_factory_garden_lifetimes_summarize(NULL, 100U, &report) == -EINVAL);
	CHECK(toy_factory_garden_lifetimes_summarize(&ledger, 100U, NULL) == -EINVAL);
	memset(&report, 0x5a, sizeof(report));
	const struct toy_factory_garden_lifetime_report untouched = report;
	CHECK(toy_factory_garden_lifetimes_summarize(&ledger, 99U, &report) == -ERANGE);
	CHECK(memcmp(&untouched, &report, sizeof(report)) == 0);
	CHECK(toy_factory_garden_lifetimes_death(&ledger, 1U, 100U, PICOSYSTEM_GARDEN_PLANT_DEAD) ==
	      0);
	saved = ledger;
	CHECK(toy_factory_garden_lifetimes_death(&ledger, 1U, 100U, PICOSYSTEM_GARDEN_PLANT_DEAD) ==
	      -EEXIST);
	CHECK(memcmp(&saved, &ledger, sizeof(ledger)) == 0);
	CHECK(toy_factory_garden_lifetimes_summarize(&ledger, 100U, &report) == 0);
	CHECK(report.total.founder_mortality.deaths == 1U);
	CHECK(report.total.founder_mortality.minimum_age_ticks == 0U);

	CHECK(toy_factory_garden_lifetimes_reset(&ledger) == 0);
	for (uint32_t id = 1U; id <= TOY_FACTORY_GARDEN_EVALUATION_MAX_PLANTS; ++id) {
		CHECK(toy_factory_garden_lifetimes_birth(&ledger, id, 0U, 0U, 0U) == 0);
	}
	saved = ledger;
	CHECK(toy_factory_garden_lifetimes_birth(&ledger, ledger.count + 1U, 0U, 0U, 0U) ==
	      -ENOSPC);
	CHECK(memcmp(&saved, &ledger, sizeof(ledger)) == 0);
	for (uint32_t id = ledger.count + 1U;
	     id <= TOY_FACTORY_GARDEN_EVALUATION_MAX_TRACKED_LINEAGES; ++id) {
		CHECK(toy_factory_garden_lifetimes_birth(&ledger, id, 1U, 0U, 0U) == 0);
	}
	saved = ledger;
	CHECK(toy_factory_garden_lifetimes_birth(&ledger, ledger.count + 1U, 1U, 0U, 0U) ==
	      -ENOSPC);
	CHECK(memcmp(&saved, &ledger, sizeof(ledger)) == 0);
	CHECK(toy_factory_garden_lifetimes_summarize(
		      &ledger, TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS, &report) == 0);
	CHECK(report.total.cycle_survivors == TOY_FACTORY_GARDEN_EVALUATION_MAX_TRACKED_LINEAGES -
						      TOY_FACTORY_GARDEN_EVALUATION_MAX_PLANTS);
	CHECK(report.total.founders_with_surviving_child == 1U);
	return 0;
}

static int test_complete_cohorts_and_death_boundaries(void)
{
	CHECK(toy_factory_garden_lifetimes_reset(&ledger) == 0);
	CHECK(toy_factory_garden_lifetimes_birth(&ledger, 1U, 0U, 1U, 0U) == 0);
	for (uint32_t id = 2U; id <= 5U; ++id) {
		CHECK(toy_factory_garden_lifetimes_birth(&ledger, id, 1U, 1U, 1200U) == 0);
	}
	CHECK(toy_factory_garden_lifetimes_death(
		      &ledger, 3U, 5039U,
		      PICOSYSTEM_GARDEN_PLANT_DEAD | PICOSYSTEM_GARDEN_PLANT_ENERGY_SHORTAGE) == 0);
	CHECK(toy_factory_garden_lifetimes_death(
		      &ledger, 4U, 5040U,
		      PICOSYSTEM_GARDEN_PLANT_DEAD | PICOSYSTEM_GARDEN_PLANT_WATER_SHORTAGE) == 0);
	CHECK(toy_factory_garden_lifetimes_death(&ledger, 5U, 5041U,
						 PICOSYSTEM_GARDEN_PLANT_VALID_FLAGS) == 0);
	CHECK(toy_factory_garden_lifetimes_birth(&ledger, 6U, 1U, 1U, 5161U) == 0);
	CHECK(toy_factory_garden_lifetimes_birth(&ledger, 7U, 1U, 1U, 6000U) == 0);
	CHECK(toy_factory_garden_lifetimes_death(&ledger, 7U, 6001U,
						 PICOSYSTEM_GARDEN_PLANT_DEAD) == 0);
	CHECK(toy_factory_garden_lifetimes_birth(&ledger, 8U, 1U, 1U, 9000U) == 0);
	CHECK(toy_factory_garden_lifetimes_summarize(&ledger, 9000U, &report) == 0);
	CHECK(report.total.offspring_born == 7U);
	CHECK(report.total.eligible_offspring == 4U);
	CHECK(report.total.cycle_survivors == 2U);
	CHECK(report.total.died_before_cycle == 2U);
	CHECK(report.total.too_young_alive == 2U);
	CHECK(report.total.too_young_dead == 1U);
	CHECK(report.total.offspring_living_at_end == 3U);
	CHECK(report.total.founders_living_at_end == 1U);
	CHECK(report.total.offspring_mortality.deaths == 4U);
	CHECK(report.total.offspring_mortality.minimum_age_ticks == 1U);
	CHECK(report.total.offspring_mortality.maximum_age_ticks == 3841U);
	CHECK(report.total.offspring_mortality.age_ticks_sum == 11521U);
	CHECK(report.total.offspring_mortality.age_by_cause[2][0] == 1U);
	CHECK(report.total.offspring_mortality.age_by_cause[3][1] == 1U);
	CHECK(report.total.offspring_mortality.age_by_cause[3][2] == 1U);
	CHECK(report.total.offspring_mortality.age_by_cause[0][3] == 1U);
	CHECK(memcmp(&report.total, &report.species[1], sizeof(report.total)) == 0);
	CHECK(memcmp(&report.total, &report.founders[0], sizeof(report.total)) == 0);
	CHECK(report.species[0].offspring_born == 0U);
	const struct toy_factory_garden_lifetime_report first = report;
	saved = ledger;
	CHECK(toy_factory_garden_lifetimes_summarize(&ledger, 9000U, &report) == 0);
	CHECK(memcmp(&saved, &ledger, sizeof(ledger)) == 0);
	CHECK(memcmp(&first, &report, sizeof(report)) == 0);
	struct toy_factory_garden_lifetime_metrics combined = {0};
	toy_factory_garden_lifetime_metrics_add(&combined, &report.total);
	toy_factory_garden_lifetime_metrics_add(&combined, &report.total);
	CHECK(combined.offspring_born == 14U);
	CHECK(combined.cycle_survivors == 4U);
	CHECK(combined.offspring_mortality.deaths == 8U);
	CHECK(combined.offspring_mortality.minimum_age_ticks == 1U);
	CHECK(combined.offspring_mortality.maximum_age_ticks == 3841U);
	CHECK(combined.offspring_mortality.age_ticks_sum == 23042U);
	CHECK(combined.offspring_mortality.age_by_cause[3][1] == 2U);
	return 0;
}

static int test_posthumous_parent_credit_and_large_ticks(void)
{
	CHECK(toy_factory_garden_lifetimes_reset(&ledger) == 0);
	CHECK(toy_factory_garden_lifetimes_birth(&ledger, 1U, 0U, 2U, 0U) == 0);
	CHECK(toy_factory_garden_lifetimes_birth(&ledger, 2U, 1U, 2U, 60U) == 0);
	CHECK(toy_factory_garden_lifetimes_birth(&ledger, 3U, 2U, 2U, 120U) == 0);
	CHECK(toy_factory_garden_lifetimes_death(&ledger, 2U, 180U, PICOSYSTEM_GARDEN_PLANT_DEAD) ==
	      0);
	CHECK(toy_factory_garden_lifetimes_death(&ledger, 1U, 195U, PICOSYSTEM_GARDEN_PLANT_DEAD) ==
	      0);
	/* A banked seed can germinate after its parent has died and been reclaimed. */
	CHECK(toy_factory_garden_lifetimes_birth(&ledger, 4U, 2U, 2U, 210U) == 0);
	CHECK(toy_factory_garden_lifetimes_birth(&ledger, 5U, 3U, 2U, 240U) == 0);
	CHECK(toy_factory_garden_lifetimes_summarize(&ledger, 7680U, &report) == 0);
	CHECK(report.total.offspring_with_surviving_child == 2U);
	CHECK(report.total.cycle_survivors_with_surviving_child == 1U);
	CHECK(report.total.founders_with_surviving_child == 0U);
	CHECK(report.total.cycle_survivors == 3U);
	CHECK(report.total.founder_mortality.deaths == 1U);
	CHECK(memcmp(&report.total, &report.species[2], sizeof(report.total)) == 0);

	CHECK(toy_factory_garden_lifetimes_reset(&ledger) == 0);
	CHECK(toy_factory_garden_lifetimes_birth(
		      &ledger, 1U, 0U, 0U,
		      UINT32_MAX - (2U * TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS)) == 0);
	CHECK(toy_factory_garden_lifetimes_birth(
		      &ledger, 2U, 1U, 0U, UINT32_MAX - TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS) ==
	      0);
	CHECK(toy_factory_garden_lifetimes_summarize(&ledger, UINT32_MAX - 1U, &report) == 0);
	CHECK(report.total.too_young_alive == 1U);
	CHECK(report.total.eligible_offspring == 0U);
	CHECK(toy_factory_garden_lifetimes_summarize(&ledger, UINT32_MAX, &report) == 0);
	CHECK(report.total.cycle_survivors == 1U);
	CHECK(toy_factory_garden_lifetimes_death(&ledger, 2U, UINT32_MAX,
						 PICOSYSTEM_GARDEN_PLANT_DEAD) == 0);
	CHECK(toy_factory_garden_lifetimes_summarize(&ledger, UINT32_MAX, &report) == 0);
	CHECK(report.total.cycle_survivors == 0U);
	CHECK(report.total.died_before_cycle == 1U);
	return 0;
}

static int test_mortality_buckets(void)
{
	static const uint32_t ages[] = {
		0U, 959U, 960U, 1919U, 1920U, 3839U, 3840U, 7679U, 7680U, 15359U, 15360U,
	};
	for (uint8_t index = 0U; index < sizeof(ages) / sizeof(ages[0]); ++index) {
		CHECK(toy_factory_garden_lifetimes_reset(&ledger) == 0);
		CHECK(toy_factory_garden_lifetimes_birth(&ledger, 1U, 0U, 0U, 0U) == 0);
		CHECK(toy_factory_garden_lifetimes_birth(&ledger, 2U, 1U, 0U, 0U) == 0);
		CHECK(toy_factory_garden_lifetimes_death(&ledger, 2U, ages[index],
							 PICOSYSTEM_GARDEN_PLANT_DEAD) == 0);
		CHECK(toy_factory_garden_lifetimes_summarize(&ledger, ages[index], &report) == 0);
		CHECK(report.total.offspring_mortality.age_by_cause[index / 2U][3] == 1U);
	}
	/* Reset is noon (bin 2). Exercise both sides of each eight-second boundary,
	 * including wraparound at dawn, independently of sun_at().
	 */
	for (uint32_t boundary = 1U; boundary <= 8U; ++boundary) {
		for (uint32_t before = 0U; before <= 1U; ++before) {
			const uint32_t tick = boundary * 480U - before;
			const uint32_t bucket = (boundary + 2U - before) % 8U;
			CHECK(toy_factory_garden_lifetimes_reset(&ledger) == 0);
			CHECK(toy_factory_garden_lifetimes_birth(&ledger, 1U, 0U, 0U, 0U) == 0);
			CHECK(toy_factory_garden_lifetimes_death(
				      &ledger, 1U, tick, PICOSYSTEM_GARDEN_PLANT_DEAD) == 0);
			CHECK(toy_factory_garden_lifetimes_summarize(&ledger, tick, &report) == 0);
			CHECK(report.total.founder_mortality.sun_phase_by_cause[bucket][3] == 1U);
		}
	}
	CHECK(toy_factory_garden_lifetimes_reset(&ledger) == 0);
	CHECK(toy_factory_garden_lifetimes_birth(&ledger, 1U, 0U, 0U, 0U) == 0);
	CHECK(toy_factory_garden_lifetimes_birth(&ledger, 2U, 1U, 0U, 0U) == 0);
	CHECK(toy_factory_garden_lifetimes_birth(&ledger, 3U, 1U, 0U, 0U) == 0);
	CHECK(toy_factory_garden_lifetimes_death(&ledger, 2U, UINT32_MAX,
						 PICOSYSTEM_GARDEN_PLANT_DEAD) == 0);
	CHECK(toy_factory_garden_lifetimes_death(&ledger, 3U, UINT32_MAX,
						 PICOSYSTEM_GARDEN_PLANT_DEAD) == 0);
	CHECK(toy_factory_garden_lifetimes_summarize(&ledger, UINT32_MAX, &report) == 0);
	CHECK(report.total.offspring_mortality.age_ticks_sum == (uint64_t)UINT32_MAX * 2U);
	CHECK(report.total.cycle_survivors == 2U);
	return 0;
}

int main(void)
{
	CHECK(test_validation_and_capacity() == 0);
	CHECK(test_complete_cohorts_and_death_boundaries() == 0);
	CHECK(test_posthumous_parent_credit_and_large_ticks() == 0);
	CHECK(test_mortality_buckets() == 0);
	puts("Garden lifetime tests passed");
	return 0;
}
