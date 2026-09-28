/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_features.h"

#include <errno.h>
#include <stddef.h>

_Static_assert(sizeof(struct toy_factory_garden_landing_inputs) == 49U, "extension budget");
_Static_assert(sizeof(struct toy_factory_garden_landing_features) == 126U, "combined budget");
_Static_assert(sizeof(struct toy_factory_garden_landing_feature_config) == 4U, "config metadata");
_Static_assert(offsetof(struct toy_factory_garden_landing_features, landing) == 77U,
	       "legacy feature prefix unchanged");
_Static_assert(PICOSYSTEM_GARDEN_LANDING_FIELDS == TOY_FACTORY_GARDEN_LANDING_CANDIDATE_COUNT,
	       "packet field order");
_Static_assert(TOY_FACTORY_GARDEN_LANDING_WARMUP + 1U == TOY_FACTORY_GARDEN_LANDING_COMMON_COUNT,
	       "common field order");
_Static_assert(PICOSYSTEM_GARDEN_DAY_TICKS == 256U, "warmup scale");

static bool config_is_valid(const struct toy_factory_garden_landing_feature_config *config)
{
	return (config->version == TOY_FACTORY_GARDEN_LANDING_FEATURE_VERSION) &&
	       (config->mode < TOY_FACTORY_GARDEN_LANDING_INPUT_MODE_COUNT) &&
	       ((config->flags & (uint8_t)~TOY_FACTORY_GARDEN_LANDING_OMIT_DEAD_ONLY) == 0U) &&
	       (config->reserved == 0U);
}

static bool packet_is_valid(const struct picosystem_garden_agent_observation *observation,
			    const struct picosystem_garden_landing_packet *packet)
{
	if ((packet->version != PICOSYSTEM_GARDEN_LANDING_VERSION) ||
	    (packet->warmup_samples > PICOSYSTEM_GARDEN_DAY_TICKS)) {
		return false;
	}
	uint8_t expected = 0U;
	if (observation->tissue_kind == PICOSYSTEM_GARDEN_NODE_STEM) {
		expected = 1U;
		for (uint8_t i = 0U; i < observation->candidate_count; ++i) {
			if ((observation->candidates[i].flags &
			     PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS) != 0U) {
				expected |= (uint8_t)(1U << (i + 1U));
			}
		}
	}
	if (packet->valid != expected) {
		return false;
	}
	for (uint8_t i = 0U; i < PICOSYSTEM_GARDEN_LANDING_SOURCES; ++i) {
		const uint8_t *const values = packet->values[i];
		for (uint8_t f = 0U; f < PICOSYSTEM_GARDEN_LANDING_FIELDS; ++f) {
			if ((((expected & (1U << i)) == 0U) ||
			     ((packet->warmup_samples == 0U) &&
			      (f >= TOY_FACTORY_GARDEN_LANDING_WET_EMA))) &&
			    (values[f] != 0U)) {
				return false;
			}
		}
		/* Rounded means can sum to 256 for the two mutually exclusive masks. */
		if (((uint16_t)values[TOY_FACTORY_GARDEN_LANDING_SPACE_FREE] +
			     values[TOY_FACTORY_GARDEN_LANDING_DEAD_ONLY] >
		     256U) ||
		    (values[TOY_FACTORY_GARDEN_LANDING_WET_LIGHT_EMA] >
		     values[TOY_FACTORY_GARDEN_LANDING_WET_EMA]) ||
		    (values[TOY_FACTORY_GARDEN_LANDING_WET_LIGHT_EMA] >
		     values[TOY_FACTORY_GARDEN_LANDING_LIGHT_EMA]) ||
		    (values[TOY_FACTORY_GARDEN_LANDING_OPEN_WET_LIGHT_EMA] >
		     values[TOY_FACTORY_GARDEN_LANDING_WET_LIGHT_EMA])) {
			return false;
		}
	}
	return true;
}

static void encode_source(const uint8_t *values, bool history, uint8_t flags, int8_t *output)
{
	const uint8_t count = history ? TOY_FACTORY_GARDEN_LANDING_CANDIDATE_COUNT
				      : TOY_FACTORY_GARDEN_LANDING_WET_EMA;
	for (uint8_t f = 0U; f < count; ++f) {
		if ((f == TOY_FACTORY_GARDEN_LANDING_DEAD_ONLY) &&
		    ((flags & TOY_FACTORY_GARDEN_LANDING_OMIT_DEAD_ONLY) != 0U)) {
			continue;
		}
		/* Bijection: retain one-byte distinctions without saturation or tuning. */
		output[f] = (int8_t)((int16_t)values[f] - 128);
	}
}

int toy_factory_garden_landing_features_encode(
	const struct picosystem_garden_agent_observation *observation,
	const struct picosystem_garden_landing_packet *packet,
	const struct toy_factory_garden_landing_feature_config *config,
	struct toy_factory_garden_landing_features *features)
{
	if ((observation == NULL) || (config == NULL) || (features == NULL)) {
		return -EINVAL;
	}
	if (!config_is_valid(config)) {
		return -ERANGE;
	}
	struct toy_factory_garden_landing_features result = {0};
	const int err = picosystem_garden_neural_encode_features(observation, &result.legacy);
	if (err != 0) {
		return err;
	}
	if (packet == NULL) {
		if (config->mode != TOY_FACTORY_GARDEN_LANDING_INPUT_OFF) {
			return -EINVAL;
		}
	} else if (!packet_is_valid(observation, packet)) {
		return -ERANGE;
	}
	if ((config->mode != TOY_FACTORY_GARDEN_LANDING_INPUT_OFF) &&
	    (observation->tissue_kind == PICOSYSTEM_GARDEN_NODE_STEM)) {
		const bool with_history = config->mode == TOY_FACTORY_GARDEN_LANDING_INPUT_HISTORY;
		const bool sampled = with_history && (packet->warmup_samples > 0U);
		encode_source(packet->values[0], sampled, config->flags, result.landing.common);
		if (with_history) {
			const uint16_t warmup =
				(uint16_t)((packet->warmup_samples * 255U + 128U) / 256U);
			result.landing.common[TOY_FACTORY_GARDEN_LANDING_WARMUP] =
				(int8_t)((int16_t)warmup - 128);
		}
		for (uint8_t i = 0U; i < observation->candidate_count; ++i) {
			if ((packet->valid & (1U << (i + 1U))) != 0U) {
				encode_source(packet->values[i + 1U], sampled, config->flags,
					      result.landing.candidates[i]);
			}
		}
	}
	*features = result;
	return 0;
}
