/* SPDX-License-Identifier: Apache-2.0 */
#include <assert.h>
#include <errno.h>
#include <string.h>
#include "garden_water_audit.h"
#include "garden_evaluation.h"
#include "garden_leaf_policies.h"
#include "garden_model_file.h"

int main(int argc, char **argv)
{
	if (argc > 2) {
		return 2;
	}
	struct picosystem_garden_world world, plain;
	assert(toy_factory_garden_evaluation_reset(&world, &toy_factory_garden_rainfed_scenarios[0],
						   123U) == 0);
	plain = world;
	struct picosystem_garden_agent_policy policy = *picosystem_garden_agent_adaptive_policy();
	policy.leaf_policy = toy_factory_garden_leaf_policy("selective");
	struct picosystem_garden_water_audit audit;
	memset(&audit, 0x5a, sizeof(audit));
	const struct picosystem_garden_water_audit before = audit;
	assert(picosystem_garden_world_step_water_audit(NULL, &policy, &audit) == -EINVAL);
	assert(picosystem_garden_world_step_water_audit(&world, NULL, &audit) == -EINVAL);
	assert(picosystem_garden_world_step_water_audit(&world, &policy, NULL) == -EINVAL);
	assert(memcmp(&audit, &before, sizeof(audit)) == 0);
	assert(memcmp(&world, &plain, sizeof(world)) == 0);
	world.auto_gardener_enabled = true;
	assert(picosystem_garden_world_step_water_audit(&world, &policy, &audit) == -EINVAL);
	assert(memcmp(&audit, &before, sizeof(audit)) == 0);
	world = plain;
	for (uint32_t i = 1U; i <= 92160U; ++i) {
		assert(picosystem_garden_world_step_water_audit(&world, &policy, &audit) == 0);
		assert(picosystem_garden_world_step_with_policy(&plain, &policy) == 0);
		assert(memcmp(&world, &plain, sizeof(world)) == 0);
		assert(audit.ecology_step == (i % 15U == 0U));
		if (!audit.ecology_step) {
			assert(audit.drainage == 0U);
			for (unsigned int j = 0U; j < PICOSYSTEM_GARDEN_WATER_STAGE_COUNT; ++j) {
				assert(audit.stages[j].soil == 0U && audit.stages[j].plants == 0U);
			}
		}
	}
	/* Empty dry-weather soil: transport conserves water except scheduled surface
	 * evaporation, including the full-cell boundary and no plant uptake.
	 */
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	world.auto_gardener_enabled = false;
	memset(world.moisture, UINT8_MAX, sizeof(world.moisture));
	for (uint32_t i = 1U; i <= 60U; ++i) {
		assert(picosystem_garden_world_step_water_audit(&world, &policy, &audit) == 0);
		if (audit.ecology_step) {
			assert(audit.stages[1].soil - audit.stages[2].soil ==
			       (i == 60U ? 28U : 0U));
			assert(audit.stages[2].soil == audit.stages[3].soil);
		}
	}
#if defined(TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE)
	/* Isolated lower boundary, no roots/rain or downward supply. */
	const uint8_t amounts[] = {0U, 1U, UINT8_MAX};
	for (unsigned int mode = 0U; mode < sizeof(amounts); ++mode) {
		assert(picosystem_garden_world_reset(&world, 123U) == 0);
		world.auto_gardener_enabled = false;
		memset(world.moisture, 0, sizeof(world.moisture));
		const unsigned int bottom =
			PICOSYSTEM_GARDEN_SOIL_CELL_COUNT - PICOSYSTEM_GARDEN_GRID_COLUMNS;
		memset(&world.moisture[bottom], amounts[mode], PICOSYSTEM_GARDEN_GRID_COLUMNS);
		for (uint32_t i = 1U; i <= 240U; ++i) {
			assert(picosystem_garden_world_step_water_audit(&world, &policy, &audit) ==
			       0);
			assert(audit.drainage == ((i == 240U && amounts[mode] != 0U) ? 28U : 0U));
		}
		for (unsigned int i = bottom; i < PICOSYSTEM_GARDEN_SOIL_CELL_COUNT; ++i) {
			assert(world.moisture[i] == (amounts[mode] ? amounts[mode] - 1U : 0U));
		}
	}
	/* At the scheduled step, transport arrives before the drain. */
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	world.auto_gardener_enabled = false;
	memset(world.moisture, 0, sizeof(world.moisture));
	memset(&world.moisture[(PICOSYSTEM_GARDEN_SOIL_ROWS - 2U) * PICOSYSTEM_GARDEN_GRID_COLUMNS],
	       2, PICOSYSTEM_GARDEN_GRID_COLUMNS);
	world.logic_tick_count = 239U;
	world.ecology_tick_count = 15U;
	assert(picosystem_garden_world_step_water_audit(&world, &policy, &audit) == 0);
	assert(audit.drainage == 28U);
	assert(audit.stages[1].soil - audit.stages[2].soil == 28U);
#endif
	if (argc == 2) {
		uint32_t crc;
		assert(toy_factory_garden_model_write_binary(
			       argv[1], picosystem_garden_neural_reference_model(), &crc) == 0);
	}
	return 0;
}
