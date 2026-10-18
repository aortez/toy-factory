/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_internal.h"
#include "garden_dispersal.h"

#include <errno.h>
#include <string.h>

#define LANDING_Q_MAX (255U * 256U)
#define LANDING_READY 1U

_Static_assert(sizeof(struct picosystem_garden_landing_cache) == 316U, "landing cache budget");
_Static_assert(sizeof(struct picosystem_garden_landing_packet) == 52U, "landing packet budget");
_Static_assert(PICOSYSTEM_GARDEN_DAY_TICKS == 256U, "trace timescale");

bool picosystem_garden_landing_cache_is_valid(const struct picosystem_garden_landing_cache *cache)
{
	if ((cache == NULL) || (cache->version != PICOSYSTEM_GARDEN_LANDING_VERSION) ||
	    (cache->flags != LANDING_READY) ||
	    (cache->warmup_samples !=
	     ((cache->ecology_tick < 256U) ? cache->ecology_tick : 256U))) {
		return false;
	}
	for (uint8_t c = 0U; c < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++c) {
		if (cache->occupied[c] >
		    (PICOSYSTEM_GARDEN_LANDING_LIVE | PICOSYSTEM_GARDEN_LANDING_DEAD)) {
			return false;
		}
		for (uint8_t i = 0U; i < PICOSYSTEM_GARDEN_LANDING_TRACES; ++i) {
			if ((cache->traces[i][c] > LANDING_Q_MAX) ||
			    ((cache->ecology_tick == 0U) && (cache->traces[i][c] != 0U))) {
				return false;
			}
		}
	}
	return true;
}

static uint16_t trace_step(uint16_t previous, bool active)
{
	const uint32_t target = active ? LANDING_Q_MAX : 0U;
	if (target >= previous) {
		return (uint16_t)(previous + ((target - previous) >> 8U));
	}
	return (uint16_t)(previous - ((previous - target) >> 8U));
}

int picosystem_garden_landing_capture(const struct picosystem_garden_world *world, bool reset,
				      struct picosystem_garden_landing_cache *cache)
{
	if ((world == NULL) || (cache == NULL) || (world->plant_count > 8U) ||
	    (reset && (world->ecology_tick_count != 0U)) ||
	    (!reset && (!picosystem_garden_landing_cache_is_valid(cache) ||
			(cache->ecology_tick == UINT32_MAX) ||
			(world->ecology_tick_count != cache->ecology_tick + 1U)))) {
		return -EINVAL;
	}
	struct picosystem_garden_landing_cache result = {0};
	if (!reset) {
		result = *cache;
	}
	result.version = PICOSYSTEM_GARDEN_LANDING_VERSION;
	result.flags = LANDING_READY;
	result.ecology_tick = world->ecology_tick_count;
	result.warmup_samples =
		(uint16_t)((result.ecology_tick < 256U) ? result.ecology_tick : 256U);
	for (uint8_t c = 0U; c < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++c) {
		result.water[c] = world->moisture[c];
		result.light[c] = world->light[(PICOSYSTEM_GARDEN_CANOPY_ROWS - 1U) *
						       PICOSYSTEM_GARDEN_GRID_COLUMNS +
					       c];
		result.occupied[c] = 0U;
		for (uint8_t i = 0U; i < world->plant_count; ++i) {
			const struct picosystem_garden_plant *const plant = &world->plants[i];
			const int16_t distance = (int16_t)c - plant->base_column;
			if ((distance > -3) && (distance < 3)) {
				result.occupied[c] |= (plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD)
							      ? PICOSYSTEM_GARDEN_LANDING_DEAD
							      : PICOSYSTEM_GARDEN_LANDING_LIVE;
			}
		}
		if (!reset) {
			const bool wet = result.water[c] >= 12U;
			const bool lit = result.light[c] >= 80U;
			const bool values[] = {wet, lit, wet && lit,
					       wet && lit && (result.occupied[c] == 0U)};
			for (uint8_t i = 0U; i < PICOSYSTEM_GARDEN_LANDING_TRACES; ++i) {
				result.traces[i][c] = trace_step(result.traces[i][c], values[i]);
			}
		}
	}
	*cache = result;
	return 0;
}

static uint8_t pixel_column(uint8_t x)
{
	if (x <= PICOSYSTEM_GARDEN_ORIGIN_X_PIXELS) {
		return 0U;
	}
	const uint8_t column =
		(uint8_t)((x - PICOSYSTEM_GARDEN_ORIGIN_X_PIXELS) / PICOSYSTEM_GARDEN_CELL_PIXELS);
	return (column < PICOSYSTEM_GARDEN_GRID_COLUMNS) ? column
							 : PICOSYSTEM_GARDEN_GRID_COLUMNS - 1U;
}

static bool source_x_valid(uint8_t x)
{
	return (x >= PICOSYSTEM_GARDEN_ORIGIN_X_PIXELS) &&
	       (x < PICOSYSTEM_GARDEN_ORIGIN_X_PIXELS +
			    PICOSYSTEM_GARDEN_GRID_COLUMNS * PICOSYSTEM_GARDEN_CELL_PIXELS);
}

static void project(const struct picosystem_garden_landing_cache *cache, uint8_t origin,
		    int8_t trait, uint8_t *values)
{
	uint16_t sums[PICOSYSTEM_GARDEN_LANDING_FIELDS] = {0};
	const uint16_t branches = 2U * PICOSYSTEM_GARDEN_DISPERSAL_CHOICES;
	for (uint16_t i = 0U; i < branches; ++i) {
		const uint8_t c = picosystem_garden_dispersed_column(origin, trait, i);
		sums[0] = (uint16_t)(sums[0] + ((cache->occupied[c] == 0U) ? 255U : 0U));
		sums[1] = (uint16_t)(sums[1] +
				     ((cache->occupied[c] == PICOSYSTEM_GARDEN_LANDING_DEAD) ? 255U
											     : 0U));
		sums[2] += cache->water[c];
		sums[3] += cache->light[c];
		for (uint8_t j = 0U; j < PICOSYSTEM_GARDEN_LANDING_TRACES; ++j) {
			sums[4U + j] += (uint16_t)((cache->traces[j][c] + 128U) >> 8U);
		}
	}
	for (uint8_t i = 0U; i < PICOSYSTEM_GARDEN_LANDING_FIELDS; ++i) {
		values[i] = (uint8_t)((sums[i] + branches / 2U) / branches);
	}
}

int picosystem_garden_landing_observe(const struct picosystem_garden_landing_cache *cache,
				      const struct picosystem_garden_agent_observation *observation,
				      struct picosystem_garden_landing_packet *packet)
{
	if ((packet == NULL) || !picosystem_garden_landing_cache_is_valid(cache) ||
	    !picosystem_garden_agent_observation_is_valid(observation) ||
	    !source_x_valid(observation->tip_x) || !source_x_valid(observation->base_x)) {
		return -EINVAL;
	}
	struct picosystem_garden_landing_packet result = {
		.version = PICOSYSTEM_GARDEN_LANDING_VERSION,
		.warmup_samples = cache->warmup_samples,
	};
	uint8_t origins[PICOSYSTEM_GARDEN_LANDING_SOURCES] = {0};
	if (observation->tissue_kind == PICOSYSTEM_GARDEN_NODE_STEM) {
		for (uint8_t i = 0U; i < PICOSYSTEM_GARDEN_LANDING_SOURCES; ++i) {
			if ((i > 0U) && ((observation->candidates[i - 1U].flags &
					  PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS) == 0U)) {
				continue;
			}
			const uint8_t x =
				(i == 0U) ? observation->tip_x : observation->candidates[i - 1U].x;
			if (!source_x_valid(x)) {
				return -EINVAL;
			}
#if defined(TOY_FACTORY_GARDEN_FLOWER_DISPERSAL)
			origins[i] = pixel_column(x);
#else
			origins[i] = pixel_column(observation->base_x);
#endif
			bool copied = false;
			for (uint8_t j = 0U; j < i; ++j) {
				if ((result.valid & (1U << j)) && (origins[j] == origins[i])) {
					memcpy(result.values[i], result.values[j],
					       sizeof(result.values[i]));
					copied = true;
					break;
				}
			}
			if (!copied) {
				project(cache, origins[i], observation->genome.dispersal,
					result.values[i]);
			}
			result.valid |= (uint8_t)(1U << i);
		}
	}
	*packet = result;
	return 0;
}
