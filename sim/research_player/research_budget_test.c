/* SPDX-License-Identifier: Apache-2.0 */
#include "research_budget.h"

#include <assert.h>
#include <errno.h>
#include <string.h>

static struct toy_factory_maintenance_step sample(uint32_t tick)
{
	struct toy_factory_maintenance_step step = {
		.tick = tick, .count = 1U, .maintenance = tick % 60U == 0U};
	struct toy_factory_resource_sample *const budget = &step.plants[0].budget;
	budget->lineage = RESEARCH_BUDGET_LINEAGE;
	budget->point_mask = 63U;
	budget->energy.before = budget->energy.after = 220U;
	budget->water.before = budget->water.after = 400U;
	for (uint8_t i = 0U; i < TOY_FACTORY_RESOURCE_POINT_COUNT; ++i) {
		budget->energy.points[i] = 220U;
		budget->water.points[i] = 400U;
	}
	return step;
}

void research_budget_tests(void)
{
	struct research_budget *trace = NULL;
	assert(research_budget_open(NULL) == -EINVAL);
	assert(research_budget_open(&trace) == 0);
	FILE *const output = tmpfile();
	assert(output != NULL);
	assert(research_budget_write(NULL, output) == -EINVAL);
	assert(research_budget_write(trace, output) == -ERANGE && ftell(output) == 0L);
	const uint32_t first = RESEARCH_BUDGET_FIRST;
	assert(research_budget_active(first) && !research_budget_active(first - 15U));
	assert(!research_budget_active(first + 1U));
	assert(research_budget_active(RESEARCH_BUDGET_END) &&
	       !research_budget_active(RESEARCH_BUDGET_END + 15U));
	struct toy_factory_maintenance_step step = sample(first);
	assert(research_budget_record(NULL, &step, NULL) == -EINVAL);
	assert(research_budget_record(trace, NULL, NULL) == -EINVAL);
	struct toy_factory_maintenance_step bad = sample(first + 15U);
	assert(research_budget_record(trace, &bad, NULL) == -ERANGE);
	bad = step;
	bad.count = 0U;
	assert(research_budget_record(trace, &bad, NULL) == -EFAULT);
	bad = step;
	bad.count = 2U;
	bad.plants[1] = bad.plants[0];
	assert(research_budget_record(trace, &bad, NULL) == -EFAULT);
	bad = step;
	bad.plants[0].budget.point_mask = 31U;
	assert(research_budget_record(trace, &bad, NULL) == -EFAULT);
	bad = step;
	bad.plants[0].budget.died = true;
	assert(research_budget_record(trace, &bad, NULL) == -EFAULT);
	const struct picosystem_garden_reproduction_audit audit = {
		.ecology_step = true,
		.count = 1U,
		.visits = {{.lineage = RESEARCH_BUDGET_LINEAGE,
			    .energy = 220U,
			    .water = 400U,
			    .energy_required = 208,
			    .water_required = 184,
			    .seed_count = 8U,
			    .blockers = 4U}}};
	assert(research_budget_record(trace, &step, &audit) == -EINVAL);
	uint32_t count = 0U;
	for (uint32_t tick = first; tick <= RESEARCH_BUDGET_END; tick += 15U) {
		if (!research_budget_active(tick)) {
			continue;
		}
		step = sample(tick);
		if (tick == first + 45U) {
			assert(step.maintenance);
			assert(research_budget_record(trace, &step, NULL) == -EINVAL);
			struct picosystem_garden_reproduction_audit invalid = audit;
			invalid.visits[0].energy = 219U;
			assert(research_budget_record(trace, &step, &invalid) == -EFAULT);
			invalid = audit;
			invalid.count = 2U;
			invalid.visits[1] = invalid.visits[0];
			assert(research_budget_record(trace, &step, &invalid) == -EFAULT);
		}
		const struct toy_factory_maintenance_step saved = step;
		assert(research_budget_record(trace, &step, step.maintenance ? &audit : NULL) == 0);
		assert(memcmp(&step, &saved, sizeof(step)) == 0);
		assert(research_budget_record(trace, &step, step.maintenance ? &audit : NULL) ==
		       -ERANGE);
		++count;
	}
	assert(count == 2244U);
	assert(research_budget_write(trace, output) == 0 && ftell(output) > 0L);
	assert(fclose(output) == 0);
	FILE *const full = fopen("/dev/full", "w");
	assert(full != NULL && research_budget_write(trace, full) == -EIO);
	(void)fclose(full);
	research_budget_close(trace);
	research_budget_close(NULL);
}
