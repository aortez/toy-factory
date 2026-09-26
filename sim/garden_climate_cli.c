/* SPDX-License-Identifier: Apache-2.0 */

#include "garden_climate_cli.h"

#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

int toy_factory_garden_climate_parse(const char *name, enum picosystem_garden_climate_mode *mode)
{
	if ((name == NULL) || (mode == NULL)) {
		return -EINVAL;
	}
	for (int candidate = PICOSYSTEM_GARDEN_CLIMATE_STEADY;
	     candidate < PICOSYSTEM_GARDEN_CLIMATE_COUNT; ++candidate) {
		const enum picosystem_garden_climate_mode value =
			(enum picosystem_garden_climate_mode)candidate;
		if (strcmp(name, picosystem_garden_climate_name(value)) == 0) {
			*mode = value;
			return 0;
		}
	}
	return -EINVAL;
}

void toy_factory_garden_climate_print(FILE *stream, const struct picosystem_garden_world *world)
{
	const struct picosystem_garden_climate climate = picosystem_garden_world_climate(world);
	static const char *const seasons[] = {"spring", "summer", "autumn", "winter"};
	fprintf(stream,
		"\"seed_lifetime_ecology_ticks\":%u,\"climate\":{\"version\":%u,"
		"\"mode\":\"%s\",\"year\":%" PRIu32 ",\"day\":%u,\"season\":\"%s\","
		"\"light_percent\":%u,\"drought\":%s,\"cold\":%s},",
		PICOSYSTEM_GARDEN_SEED_LIFETIME_TICKS, PICOSYSTEM_GARDEN_CLIMATE_VERSION,
		picosystem_garden_climate_name(
			(enum picosystem_garden_climate_mode)world->climate_mode),
		world->ecology_tick_count / PICOSYSTEM_GARDEN_YEAR_TICKS, climate.day,
		seasons[climate.season], climate.light_percent, climate.drought ? "true" : "false",
		climate.cold ? "true" : "false");
}
