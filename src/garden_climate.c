/* SPDX-License-Identifier: Apache-2.0 */

#include "garden_climate.h"

static uint32_t climate_bits(uint32_t seed, uint32_t year, uint32_t domain)
{
	uint32_t bits = seed ^ (year * UINT32_C(0x9e3779b9)) ^ domain;
	bits ^= bits >> 16U;
	bits *= UINT32_C(0x7feb352d);
	bits ^= bits >> 15U;
	bits *= UINT32_C(0x846ca68b);
	return bits ^ (bits >> 16U);
}

struct picosystem_garden_climate picosystem_garden_climate_at(uint32_t weather_seed,
							      uint32_t ecology_tick)
{
	const uint32_t year = ecology_tick / PICOSYSTEM_GARDEN_YEAR_TICKS;
	const uint32_t phase = ecology_tick % PICOSYSTEM_GARDEN_YEAR_TICKS;
	const uint32_t day = phase / PICOSYSTEM_GARDEN_DAY_TICKS;
	const uint32_t dry = climate_bits(weather_seed, year, UINT32_C(0x64727931));
	const uint32_t winter = climate_bits(weather_seed, year, UINT32_C(0x77696e31));
	const uint32_t dry_start = 4U + (dry % 2U);
	const uint32_t dry_days = 2U + ((dry >> 8U) % (7U - dry_start));
	uint32_t light_percent = 100U;
	/* Gradual cooling from day 10 to day 14, then thaw before the next spring.
	 * Scale only direct light; preserve the ambient floor and daily ray geometry.
	 */
	if (phase >= (10U * PICOSYSTEM_GARDEN_DAY_TICKS)) {
		const uint32_t peak = 14U * PICOSYSTEM_GARDEN_DAY_TICKS;
		const uint32_t ramp = phase <= peak ? phase - (10U * PICOSYSTEM_GARDEN_DAY_TICKS)
						    : 2U * (PICOSYSTEM_GARDEN_YEAR_TICKS - phase);
		const uint32_t minimum = 38U + (winter % 21U);
		light_percent -= ((100U - minimum) * ramp) / (4U * PICOSYSTEM_GARDEN_DAY_TICKS);
	}
	return (struct picosystem_garden_climate){
		.day = (uint8_t)day,
		.season = (uint8_t)(day / 4U),
		.light_percent = (uint8_t)light_percent,
		.drought = (day >= dry_start) && (day < (dry_start + dry_days)),
		/* Cold delays germination, not aging: seeds can still expire in winter. */
		.cold = light_percent < 65U,
	};
}

const char *picosystem_garden_climate_name(enum picosystem_garden_climate_mode mode)
{
	switch (mode) {
	case PICOSYSTEM_GARDEN_CLIMATE_STEADY:
		return "steady";
	case PICOSYSTEM_GARDEN_CLIMATE_WINTER:
		return "winter";
	case PICOSYSTEM_GARDEN_CLIMATE_DROUGHT:
		return "drought";
	case PICOSYSTEM_GARDEN_CLIMATE_SEASONAL:
		return "seasonal";
	default:
		return "unknown";
	}
}
