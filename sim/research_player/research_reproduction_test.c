/* SPDX-License-Identifier: Apache-2.0 */
#include "research_reproduction.h"
#include "research_budget.h"
#include "research_foliage.h"
#include "research_session.h"
#include "research_fallback.h"
#include "garden_leaf_family.h"

#include <assert.h>
#include <errno.h>
#include <string.h>

static uint32_t tick_at(uint32_t sample)
{
	return RESEARCH_REPRODUCTION_FIRST + sample * RESEARCH_REPRODUCTION_CADENCE;
}

static void record_tests(void)
{
	struct research_reproduction *trace = NULL;
	struct picosystem_garden_reproduction_audit audit = {
		.ecology_step = true,
		.count = 1U,
		.visits = {{.lineage = 1U,
			    .blockers = PICOSYSTEM_GARDEN_REPRODUCTION_BANK,
			    .seed_count = 8U}}};
	FILE *const output = tmpfile();
	assert(output != NULL);
	assert(research_reproduction_open(NULL) == -EINVAL);
	assert(research_reproduction_open(&trace) == 0);
	assert(research_reproduction_write(trace, output) == -ERANGE && ftell(output) == 0L);
	assert(research_reproduction_record(NULL, tick_at(1U), &audit) == -EINVAL);
	assert(research_reproduction_record(trace, tick_at(1U), NULL) == -EINVAL);
	assert(research_reproduction_record(trace, tick_at(0U), &audit) == -ERANGE);
	assert(research_reproduction_record(trace, tick_at(2U), &audit) == -ERANGE);
	struct picosystem_garden_reproduction_audit bad = audit;
	bad.count = PICOSYSTEM_GARDEN_MAX_PLANTS + 1U;
	assert(research_reproduction_record(trace, tick_at(1U), &bad) == -EINVAL);
	bad = audit;
	bad.ecology_step = false;
	assert(research_reproduction_record(trace, tick_at(1U), &bad) == -EINVAL);
	const uint16_t bad_masks[] = {0U, 1024U, PICOSYSTEM_GARDEN_REPRODUCTION_CADENCE};
	for (size_t i = 0U; i < sizeof(bad_masks) / sizeof(bad_masks[0]); ++i) {
		bad = audit;
		bad.visits[0].blockers = bad_masks[i];
		assert(research_reproduction_record(trace, tick_at(1U), &bad) == -EFAULT);
	}
	bad = audit;
	bad.visits[0].produced = true;
	assert(research_reproduction_record(trace, tick_at(1U), &bad) == -EFAULT);
	bad = audit;
	bad.count = 2U;
	bad.visits[1] = bad.visits[0];
	assert(research_reproduction_record(trace, tick_at(1U), &bad) == -EFAULT);
	bad.visits[1].lineage = 2U;
	bad.visits[1].seed_count = 7U;
	bad.visits[1].blockers = PICOSYSTEM_GARDEN_REPRODUCTION_ENERGY;
	assert(research_reproduction_record(trace, tick_at(1U), &bad) == -EFAULT);
	struct picosystem_garden_reproduction_audit opening = audit;
	opening.count = 2U;
	opening.visits[0].seed_count = 7U;
	opening.visits[0].blockers = 0U;
	opening.visits[0].produced = true;
	opening.visits[1] = audit.visits[0];
	opening.visits[1].lineage = 2U;
	const struct picosystem_garden_reproduction_audit saved = opening;
	assert(research_reproduction_record(trace, tick_at(1U), &opening) == 0);
	assert(memcmp(&opening, &saved, sizeof(saved)) == 0);
	assert(research_reproduction_record(trace, tick_at(1U), &audit) == -ERANGE);
	const uint32_t samples = (RESEARCH_REPRODUCTION_END - RESEARCH_REPRODUCTION_FIRST) /
				 RESEARCH_REPRODUCTION_CADENCE;
	for (uint32_t i = 2U; i <= samples; ++i) {
		assert(research_reproduction_record(trace, tick_at(i), &audit) == 0);
	}
	assert(research_reproduction_record(trace, tick_at(samples + 1U), &audit) == -ERANGE);
	assert(research_reproduction_write(trace, output) == 0 && ftell(output) > 0L);
	assert(fclose(output) == 0);
	FILE *const full = fopen("/dev/full", "w");
	assert(full != NULL && research_reproduction_write(trace, full) == -EIO);
	(void)fclose(full);
	research_reproduction_close(trace);
	assert(research_reproduction_open(&trace) == 0);
	for (uint32_t i = 1U; i <= RESEARCH_REPRODUCTION_OPENINGS; ++i) {
		assert(research_reproduction_record(trace, tick_at(i), &opening) == 0);
	}
	assert(research_reproduction_record(trace, tick_at(RESEARCH_REPRODUCTION_OPENINGS + 1U),
					    &opening) == -ENOSPC);
	research_reproduction_close(trace);
	assert(research_reproduction_open(&trace) == 0);
	for (uint32_t i = 1U; i <= RESEARCH_REPRODUCTION_LINEAGES; ++i) {
		audit.visits[0].lineage = i;
		assert(research_reproduction_record(trace, tick_at(i), &audit) == 0);
	}
	audit.visits[0].lineage = RESEARCH_REPRODUCTION_LINEAGES + 1U;
	assert(research_reproduction_record(trace, tick_at(RESEARCH_REPRODUCTION_LINEAGES + 1U),
					    &audit) == -ENOSPC);
	research_reproduction_close(trace);
	research_reproduction_close(NULL);
}

void research_reproduction_tests(void)
{
	record_tests();
	const struct research_options options = {
		.seed = UINT32_C(0x9a903368), .model = 1U, .scope = RESEARCH_SCOPE_POPULATION};
	assert(research_session_reproduction_start(NULL) == -EINVAL);
	for (uint8_t fallback = 0U; fallback < 2U; ++fallback) {
		struct research_session *on = NULL, *off = NULL;
		assert(research_session_open(&options, &on) == 0);
		assert(research_session_foliage_start(on) == -EINVAL);
		assert(research_session_canopy_start(on) == -EINVAL);
		assert(research_session_reproduction_start(on) == -EINVAL);
		assert(research_session_gate_start_early(on, 1U) == 0);
		assert(research_session_reproduction_start(on) == -EINVAL);
		assert(research_session_reset(&on) == 0);
		assert(research_session_gate_start_early(on, 2U) == 0);
		assert(research_session_reproduction_start(on) == 0);
		assert(research_session_reproduction_start(on) == -EINVAL);
		assert(research_session_open(&options, &off) == 0);
		assert(research_session_gate_start_early(off, 2U) == 0);
		if (fallback != 0U) {
			assert(research_session_fallback_start(on) == 0);
			assert(research_session_fallback_start(off) == 0);
			assert(research_session_budget_start(on) == 0);
			assert(research_session_budget_start(on) == -EINVAL);
		} else {
			assert(research_session_budget_start(on) == -EINVAL);
		}
		assert(research_session_foliage_start(on) == 0);
		assert(research_session_canopy_start(on) == 0);
		assert(research_session_canopy_start(on) == -EINVAL);
		FILE *const incomplete = tmpfile();
		assert(incomplete != NULL &&
		       research_session_canopy_write(on, incomplete) == -ERANGE);
		assert(ftell(incomplete) == 0L && fclose(incomplete) == 0);
		assert(research_session_foliage_start(on) == -EINVAL);
		assert(research_session_fallback_start(on) == -EINVAL);
		const uint32_t stop = RESEARCH_FOLIAGE_END;
		assert(research_session_step(on, stop) == 0);
		assert(research_session_step(off, stop) == 0);
		uint8_t a[TOY_FACTORY_LEAF_FAMILY_MAX_STATE_BYTES + 184U +
			  RESEARCH_FALLBACK_HEADER_BYTES],
			b[sizeof(a)];
		size_t sa, sb;
		assert(research_session_encode(on, a, sizeof(a), &sa) == 0);
		assert(research_session_encode(off, b, sizeof(b), &sb) == 0);
		assert(sa == sb && memcmp(a, b, sa) == 0);
		FILE *const output = tmpfile();
		assert(output != NULL);
		FILE *const foliage = tmpfile();
		assert(foliage != NULL);
		assert(research_session_foliage_write(on, foliage) == 0 && ftell(foliage) > 0L);
		assert(fclose(foliage) == 0);
		FILE *const canopy = tmpfile();
		assert(canopy != NULL);
		assert(research_session_canopy_write(on, canopy) == 0 && ftell(canopy) > 0L);
		assert(fclose(canopy) == 0);
		FILE *const full = fopen("/dev/full", "w");
		assert(full != NULL && research_session_canopy_write(on, full) == -EIO);
		(void)fclose(full);
		assert(research_session_reproduction_write(on, output) == -ERANGE);
		assert(research_session_budget_write(on, output) == (fallback ? -ERANGE : -EINVAL));
		assert(research_session_reset(&on) == 0);
		assert(research_session_reproduction_write(on, output) == -EINVAL);
		assert(research_session_budget_write(on, output) == -EINVAL);
		assert(research_session_foliage_write(on, output) == -EINVAL);
		assert(research_session_canopy_write(on, output) == -EINVAL);
		assert(ftell(output) == 0L && fclose(output) == 0);
		research_session_close(on);
		research_session_close(off);
	}
}
