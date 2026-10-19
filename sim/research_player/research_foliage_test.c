/* SPDX-License-Identifier: Apache-2.0 */
#include "research_foliage.h"
#include "research_canopy.h"

#include <assert.h>
#include <errno.h>
#include <string.h>

static int forwarded(const struct picosystem_garden_world *world,
		     const struct picosystem_garden_leaf_policy *candidate,
		     const struct picosystem_garden_leaf_observation *observation,
		     const struct picosystem_garden_agent_memory *memory,
		     struct picosystem_garden_leaf_decision *decision, const void *context)
{
	(void)world;
	(void)candidate;
	*decision = (struct picosystem_garden_leaf_decision){.node_index = observation->node_index,
							     .next_memory = *memory,
							     .action = PICOSYSTEM_GARDEN_LEAF_WAIT};
	return *(const int *)context;
}

static void projection_tests(void)
{
	struct picosystem_garden_world before;
	assert(picosystem_garden_world_reset(&before, 123U) == 0);
	assert(picosystem_garden_world_plant_seed(&before, PICOSYSTEM_GARDEN_SPECIES_SHRUB, 4U) ==
	       0);
	before.auto_gardener_enabled = false;
	before.logic_tick_count = 59U;
	before.ecology_tick_count = 3U;
	before.nodes[1].growth_progress = 74U; /* This step crosses the active threshold. */
	before.leaf_condition[1] = 128U;
	struct picosystem_garden_uptake_audit out = {0};
	const struct picosystem_garden_world saved = before;
	assert(research_canopy_project(&before, &out) == 0);
	assert(memcmp(&before, &saved, sizeof(before)) == 0);
	assert(out.source_count == 1U && out.tick == 60U);
	assert(out.sources[0].center == 38U * 127U / 255U);
	assert(out.sources[0].neighbor == 12U * 127U / 255U);
	before.nodes[1].growth_progress = 73U;
	assert(research_canopy_project(&before, &out) == 0 && out.source_count == 0U);
	before = saved;
	before.logic_tick_count = 44U;
	before.ecology_tick_count = 2U;
	assert(research_canopy_project(&before, &out) == 0 && out.source_count == 1U);
	assert(out.sources[0].center == 38U * 128U / 255U);
	before.nodes[1].growth_progress = 1U;
	before.plants[0].flags = PICOSYSTEM_GARDEN_PLANT_DEAD;
	before.plants[0].stress = 8U;
	before.plants[0].stored_energy = 0U;
	before.plants[0].stored_water = 0U;
	assert(research_canopy_project(&before, &out) == 0 && out.source_count == 1U);
	assert(out.sources[0].dead && out.sources[0].center == 38U * 128U / 255U);
	const struct picosystem_garden_uptake_audit unchanged = out;
	assert(research_canopy_project(NULL, &out) == -EINVAL);
	assert(memcmp(&out, &unchanged, sizeof(out)) == 0);
	assert(research_canopy_project(&before, NULL) == -EINVAL);
	before.auto_gardener_enabled = true;
	assert(research_canopy_project(&before, &out) == -EINVAL);
	before = saved;
	++before.logic_tick_count;
	assert(research_canopy_project(&before, &out) == -EINVAL);
	before = saved;
	before.node_count = PICOSYSTEM_GARDEN_MAX_NODES + 1U;
	assert(research_canopy_project(&before, &out) == -EINVAL);
	assert(memcmp(&out, &unchanged, sizeof(out)) == 0);
}

void research_foliage_tests(void)
{
	projection_tests();
	struct research_foliage *trace = NULL;
	assert(research_foliage_open(18U, &trace) == -EINVAL);
	assert(research_foliage_open(19U, NULL) == -EINVAL);
	assert(research_foliage_open(19U, &trace) == 0);
	assert(!research_foliage_active(RESEARCH_FOLIAGE_FIRST));
	assert(research_foliage_active(RESEARCH_FOLIAGE_FIRST + 15U));
	assert(!research_foliage_active(RESEARCH_FOLIAGE_FIRST + 16U));
	assert(!research_foliage_active(RESEARCH_FOLIAGE_END + 15U));
	FILE *const output = tmpfile();
	assert(output != NULL && research_foliage_write(trace, output) == -ERANGE);
	assert(research_foliage_canopy_write(trace, output) == -EINVAL);
	int downstream_error = 0;
	const struct toy_factory_leaf_replay_route next = {.decide = forwarded,
							   .context = &downstream_error};
	const struct research_foliage_context context = {.trace = trace, .next = &next};
	const struct picosystem_garden_leaf_policy candidate = {0};
	const struct picosystem_garden_agent_memory memory = {0};
	struct picosystem_garden_leaf_decision decision;
	const struct picosystem_garden_leaf_observation observation = {
		.plant_index = 0U, .node_index = 0U, .mature_leaf_count = 2U};
	for (uint32_t tick = RESEARCH_FOLIAGE_FIRST + 15U; tick <= RESEARCH_FOLIAGE_END;
	     tick += 15U) {
		const bool maintenance = tick % 60U == 0U;
		/* Two focal leaves retain body order after another plant is reclaimed. */
		struct picosystem_garden_world before = {
			.logic_tick_count = tick - 1U, .plant_count = 2U, .node_count = 3U};
		before.plants[0].lineage_id = 1U;
		before.plants[1].lineage_id = 19U;
		before.nodes[1] =
			(struct picosystem_garden_node){.plant_index = 1U,
							.kind = PICOSYSTEM_GARDEN_NODE_STEM,
							.flags = PICOSYSTEM_GARDEN_NODE_LEAF,
							.growth_progress = UINT8_MAX,
							.x = 0U,
							.y = 0U};
		before.nodes[2] = before.nodes[1];
		before.nodes[2].x = UINT8_MAX;
		before.nodes[2].y = UINT8_MAX;
		before.leaf_condition[1] = UINT8_MAX;
		struct picosystem_garden_world current = {.logic_tick_count = tick,
							  .ecology_tick_count = tick / 15U,
							  .plant_count = 1U,
							  .node_count = 2U};
		current.plants[0].lineage_id = 19U;
		current.plants[0].stored_energy = 220U;
		current.plants[0].leaf_energy_remainder = maintenance ? 251U : 254U;
		current.nodes[0] = before.nodes[1];
		current.nodes[1] = before.nodes[2];
		current.nodes[0].plant_index = current.nodes[1].plant_index = 0U;
		current.leaf_condition[0] = maintenance ? 254U : 255U;
		memset(current.light, UINT8_MAX, sizeof(current.light));
		struct toy_factory_maintenance_step step = {
			.tick = tick, .count = 1U, .maintenance = maintenance};
		struct toy_factory_maintenance_sample *const s = &step.plants[0];
		s->budget.lineage = 19U;
		s->budget.point_mask = 63U;
		s->leaves_before = s->leaves_after = 2U;
		s->condition_before = 255U;
		s->worn = maintenance ? 1U : 0U;
		s->observations = 1U;
		s->remainder_before = 254U;
		s->remainder_uptake = current.plants[0].leaf_energy_remainder;
		s->budget.energy.income = 3U;
		s->budget.energy.points[TOY_FACTORY_RESOURCE_GERMINATION] = 220U;
		assert(research_foliage_finish(trace, &before, &step) == -ERANGE);
		if (tick == RESEARCH_FOLIAGE_FIRST + 15U) {
			downstream_error = -EIO;
			assert(research_foliage_decide(&current, &candidate, &observation, &memory,
						       &decision, &context) == -EIO);
			assert(research_foliage_finish(trace, &before, &step) == -ERANGE);
			downstream_error = 0;
		}
		const struct picosystem_garden_world saved = current;
		assert(research_foliage_decide(&current, &candidate, &observation, &memory,
					       &decision, &context) == 0);
		assert(memcmp(&current, &saved, sizeof(saved)) == 0);
		assert(decision.action == PICOSYSTEM_GARDEN_LEAF_WAIT && decision.node_index == 0U);
		assert(research_foliage_decide(&current, &candidate, &observation, &memory,
					       &decision, &context) == -ERANGE);
		if (tick == RESEARCH_FOLIAGE_FIRST + 15U) {
			++s->budget.energy.income;
			assert(research_foliage_finish(trace, &before, &step) == -EFAULT);
			--s->budget.energy.income;
			before.leaf_condition[1] = 254U;
			assert(research_foliage_finish(trace, &before, &step) == -EFAULT);
			before.leaf_condition[1] = 255U;
		}
		assert(research_foliage_finish(trace, &before, &step) == 0);
	}
	assert(research_foliage_write(trace, output) == 0 && ftell(output) > 0L);
	assert(fclose(output) == 0);
	FILE *const full = fopen("/dev/full", "w");
	assert(full != NULL && research_foliage_write(trace, full) == -EIO);
	(void)fclose(full);
	research_foliage_close(trace);
	research_foliage_close(NULL);
}
