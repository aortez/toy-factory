/* SPDX-License-Identifier: Apache-2.0 */

#include "garden_agent.h"
#include "garden_climate_cli.h"
#include "garden_light.h"

#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

static void ecology_step(struct picosystem_garden_world *world)
{
	for (uint8_t tick = 0U; tick < PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR; ++tick) {
		assert(picosystem_garden_world_step(world) == 0);
	}
}

static void test_schedule(void)
{
	static const uint32_t seeds[] = {0U, 1U, 123U, UINT32_MAX};
	bool varied = false;
	for (size_t index = 0U; index < sizeof(seeds) / sizeof(seeds[0]); ++index) {
		for (uint32_t year = 0U; year < 4U; ++year) {
			uint32_t drought_ticks = 0U;
			unsigned starts = 0U;
			struct picosystem_garden_climate previous = {0};
			for (uint32_t tick = 0U; tick < PICOSYSTEM_GARDEN_YEAR_TICKS; ++tick) {
				const uint32_t time = year * PICOSYSTEM_GARDEN_YEAR_TICKS + tick;
				const struct picosystem_garden_climate c =
					picosystem_garden_climate_at(seeds[index], time);
				const struct picosystem_garden_climate again =
					picosystem_garden_climate_at(seeds[index], time);
				assert(c.day == tick / PICOSYSTEM_GARDEN_DAY_TICKS);
				assert(c.season == c.day / 4U);
				assert(c.light_percent >= 38U && c.light_percent <= 100U);
				assert(c.cold == (c.light_percent < 65U));
				assert(c.drought == again.drought &&
				       c.light_percent == again.light_percent);
				if (tick != 0U) {
					const int delta =
						(int)c.light_percent - previous.light_percent;
					assert(delta >= -1 && delta <= 1);
				}
				if (c.drought) {
					assert(c.day >= 4U && c.day < 8U && !c.cold);
					++drought_ticks;
					starts += previous.drought ? 0U : 1U;
				}
				if (c.day < 10U) {
					assert(c.light_percent == 100U);
				}
				if (tick == 14U * PICOSYSTEM_GARDEN_DAY_TICKS) {
					assert(c.light_percent <= 58U && c.cold);
				}
				const struct picosystem_garden_climate other =
					picosystem_garden_climate_at(seeds[index] ^ 42U, time);
				varied |= c.light_percent != other.light_percent ||
					  c.drought != other.drought;
				previous = c;
			}
			assert(starts == 1U);
			assert(drought_ticks >= 2U * PICOSYSTEM_GARDEN_DAY_TICKS);
			assert(drought_ticks <= 4U * PICOSYSTEM_GARDEN_DAY_TICKS);
		}
	}
	assert(varied);
	const struct picosystem_garden_climate limit =
		picosystem_garden_climate_at(UINT32_MAX, UINT32_MAX);
	assert(limit.day == 15U && limit.light_percent == 100U && !limit.drought);
}

static void test_modes_and_contracts(void)
{
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	assert(picosystem_garden_world_set_weather(&world, 123U) == 0);
	const struct picosystem_garden_world original = world;
	assert(picosystem_garden_world_set_climate(NULL, PICOSYSTEM_GARDEN_CLIMATE_WINTER) ==
	       -EINVAL);
	assert(picosystem_garden_world_set_climate(&world, PICOSYSTEM_GARDEN_CLIMATE_COUNT) ==
	       -EINVAL);
	assert(picosystem_garden_world_set_climate(&world, (enum picosystem_garden_climate_mode) -
								   1) == -EINVAL);
	assert(memcmp(&world, &original, sizeof(world)) == 0);
	uint32_t hashes[PICOSYSTEM_GARDEN_CLIMATE_COUNT];
	for (int mode = 0; mode < PICOSYSTEM_GARDEN_CLIMATE_COUNT; ++mode) {
		world = original;
		assert(picosystem_garden_world_set_climate(
			       &world, (enum picosystem_garden_climate_mode)mode) == 0);
		hashes[mode] = picosystem_garden_world_hash(&world);
		assert(world.random_state == original.random_state);
		for (uint32_t tick = 0U; tick < PICOSYSTEM_GARDEN_YEAR_TICKS; ++tick) {
			world.ecology_tick_count = tick;
			const struct picosystem_garden_sun base = picosystem_garden_sun_at(tick);
			const struct picosystem_garden_sun actual =
				picosystem_garden_world_sun(&world);
			const struct picosystem_garden_climate c =
				picosystem_garden_world_climate(&world);
			assert(base.phase == actual.phase &&
			       base.ray_step_x_q4 == actual.ray_step_x_q4);
			assert(actual.strength >= PICOSYSTEM_GARDEN_LIGHT_MINIMUM &&
			       actual.strength <= base.strength);
			if ((mode & PICOSYSTEM_GARDEN_CLIMATE_WINTER) == 0) {
				assert(base.strength == actual.strength && !c.cold);
			}
			assert(picosystem_garden_world_rain(&world) ==
			       (c.drought ? 0U : picosystem_garden_rain_at(123U, tick)));
			world.random_state ^= UINT32_C(0x12345678);
			assert(picosystem_garden_world_rain(&world) ==
			       (c.drought ? 0U : picosystem_garden_rain_at(123U, tick)));
		}
		for (int earlier = 0; earlier < mode; ++earlier) {
			assert(hashes[earlier] != hashes[mode]);
		}
	}
	world = original;
	world.logic_tick_count = 1U;
	const struct picosystem_garden_world between = world;
	assert(picosystem_garden_world_set_climate(&world, PICOSYSTEM_GARDEN_CLIMATE_WINTER) ==
	       -EINVAL);
	assert(memcmp(&world, &between, sizeof(world)) == 0);
	enum picosystem_garden_climate_mode mode = PICOSYSTEM_GARDEN_CLIMATE_WINTER;
	assert(toy_factory_garden_climate_parse("bad", &mode) == -EINVAL);
	assert(mode == PICOSYSTEM_GARDEN_CLIMATE_WINTER);
	assert(toy_factory_garden_climate_parse(NULL, &mode) == -EINVAL);
	assert(toy_factory_garden_climate_parse("winter", NULL) == -EINVAL);
	assert(toy_factory_garden_climate_parse("seasonal", &mode) == 0);
	assert(mode == PICOSYSTEM_GARDEN_CLIMATE_SEASONAL);
}

static void make_seed_bank(struct picosystem_garden_world *world)
{
	assert(picosystem_garden_world_reset(world, 123U) == 0);
	world->lineage_sequence = 1U;
	world->seed_count = 1U;
	world->seed_creation_count = 1U;
	world->seeds[0] = (struct picosystem_garden_seed){
		.parent_lineage_id = 1U,
		.generation = 1U,
		.column = 4U,
		.species_id = PICOSYSTEM_GARDEN_SPECIES_FLOWER,
	};
}

static void test_seed_viability_and_thaw(void)
{
	struct picosystem_garden_world world;
	make_seed_bank(&world);
	for (uint32_t tick = 0U; tick < 2U * PICOSYSTEM_GARDEN_DAY_TICKS; ++tick) {
		ecology_step(&world);
	}
	assert(world.seed_count == 1U && world.seed_expiration_count == 0U);
	assert(world.seeds[0].age_ecology_ticks == 512U);
	world.seeds[0].age_ecology_ticks = PICOSYSTEM_GARDEN_SEED_LIFETIME_TICKS - 2U;
	ecology_step(&world);
	assert(world.seed_count == 1U);
	ecology_step(&world);
	assert(world.seed_count == 0U && world.seed_expiration_count == 1U);

	make_seed_bank(&world);
	world.ecology_tick_count = 14U * PICOSYSTEM_GARDEN_DAY_TICKS;
	world.logic_tick_count = world.ecology_tick_count * PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR;
	world.seeds[0].age_ecology_ticks = 512U;
	assert(picosystem_garden_world_set_climate(&world, PICOSYSTEM_GARDEN_CLIMATE_WINTER) == 0);
	assert(picosystem_garden_world_water(&world, 4U, 128U) == 0);
	uint8_t blockers;
	assert(picosystem_garden_world_seed_germination_blockers(&world, 0U, &blockers) == 0);
	assert(blockers == PICOSYSTEM_GARDEN_SEED_BLOCKED_COLD);
	ecology_step(&world);
	assert(world.seed_count == 1U && world.germination_count == 0U);
	/* Controlled thaw fixture: retain the old seed and its lineage, not a new founder. */
	world.ecology_tick_count = PICOSYSTEM_GARDEN_YEAR_TICKS;
	world.logic_tick_count = world.ecology_tick_count * PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR;
	assert(picosystem_garden_world_set_climate(&world, PICOSYSTEM_GARDEN_CLIMATE_WINTER) == 0);
	ecology_step(&world);
	assert(world.seed_count == 0U && world.germination_count == 1U);
	assert(world.plants[0].parent_lineage_id == 1U && world.plants[0].generation == 1U);
}

static void test_drought_recovery_and_rain_accounting(void)
{
	struct picosystem_garden_world world;
	make_seed_bank(&world);
	assert(picosystem_garden_world_set_weather(&world, 123U) == 0);
	assert(picosystem_garden_world_set_climate(&world, PICOSYSTEM_GARDEN_CLIMATE_DROUGHT) == 0);
	world.ecology_tick_count = 4U * PICOSYSTEM_GARDEN_DAY_TICKS;
	while (!picosystem_garden_world_climate(&world).drought) {
		++world.ecology_tick_count;
	}
	world.logic_tick_count = world.ecology_tick_count * PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR;
	world.seeds[0].age_ecology_ticks = 512U;
	while (picosystem_garden_world_climate(&world).drought) {
		ecology_step(&world);
		assert(world.germination_count == 0U && world.seed_count == 1U);
		assert(world.rain_deposited == 0U && world.rain_runoff == 0U);
	}
	uint32_t offered = 0U;
	for (uint32_t step = 0U;
	     step < 2U * PICOSYSTEM_GARDEN_DAY_TICKS && world.germination_count == 0U; ++step) {
		ecology_step(&world);
		offered += (uint32_t)picosystem_garden_world_rain(&world) *
			   PICOSYSTEM_GARDEN_GRID_COLUMNS;
	}
	assert(world.rain_deposited + world.rain_runoff == offered);
	assert(world.germination_count == 1U && world.seed_expiration_count == 0U);
}

int main(void)
{
	test_schedule();
	test_modes_and_contracts();
	test_seed_viability_and_thaw();
	test_drought_recovery_and_rain_accounting();
	printf("Garden climate tests passed; world=%zu plant=%zu observation=%zu bytes\n",
	       sizeof(struct picosystem_garden_world), sizeof(struct picosystem_garden_plant),
	       sizeof(struct picosystem_garden_agent_observation));
	return 0;
}
