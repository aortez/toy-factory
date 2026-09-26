/* SPDX-License-Identifier: Apache-2.0 */

#ifndef PICOSYSTEM_GARDEN_CLIMATE_H_
#define PICOSYSTEM_GARDEN_CLIMATE_H_

#include <stdbool.h>
#include <stdint.h>

#define PICOSYSTEM_GARDEN_CLIMATE_VERSION 1U
#define PICOSYSTEM_GARDEN_DAY_TICKS       256U
#define PICOSYSTEM_GARDEN_YEAR_DAYS       16U
#define PICOSYSTEM_GARDEN_YEAR_TICKS      (PICOSYSTEM_GARDEN_DAY_TICKS * PICOSYSTEM_GARDEN_YEAR_DAYS)

/* Independent bits allow matched winter-only and drought-only controls. */
enum picosystem_garden_climate_mode {
	PICOSYSTEM_GARDEN_CLIMATE_STEADY = 0,
	PICOSYSTEM_GARDEN_CLIMATE_WINTER = 1,
	PICOSYSTEM_GARDEN_CLIMATE_DROUGHT = 2,
	PICOSYSTEM_GARDEN_CLIMATE_SEASONAL = 3,
	PICOSYSTEM_GARDEN_CLIMATE_COUNT,
};

enum picosystem_garden_season {
	PICOSYSTEM_GARDEN_SPRING,
	PICOSYSTEM_GARDEN_SUMMER,
	PICOSYSTEM_GARDEN_AUTUMN,
	PICOSYSTEM_GARDEN_WINTER,
};

/* Derived from time and weather seed; never stored in the world. */
struct picosystem_garden_climate {
	uint8_t day;
	uint8_t season;
	uint8_t light_percent;
	bool drought;
	bool cold;
};

/* Complete seasonal schedule, independent of plant state and all plant RNGs. */
struct picosystem_garden_climate picosystem_garden_climate_at(uint32_t weather_seed,
							      uint32_t ecology_tick);

const char *picosystem_garden_climate_name(enum picosystem_garden_climate_mode mode);

#endif /* PICOSYSTEM_GARDEN_CLIMATE_H_ */
