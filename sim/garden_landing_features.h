/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_LANDING_FEATURES_H_
#define TOY_FACTORY_GARDEN_LANDING_FEATURES_H_

#include "garden_agent_neural.h"
#include "garden_landing.h"

#if defined(__ZEPHYR__)
#error "Landing feature encoding is a host-only experiment"
#endif

/* This versions an extension, not the existing neural model/feature/file ABI. */
#define TOY_FACTORY_GARDEN_LANDING_FEATURE_VERSION 1U
#define TOY_FACTORY_GARDEN_LANDING_COMMON_COUNT    9U
#define TOY_FACTORY_GARDEN_LANDING_CANDIDATE_COUNT 8U
#define TOY_FACTORY_GARDEN_LANDING_OMIT_DEAD_ONLY  1U

enum toy_factory_garden_landing_input_mode {
	TOY_FACTORY_GARDEN_LANDING_INPUT_OFF,
	TOY_FACTORY_GARDEN_LANDING_INPUT_CURRENT,
	TOY_FACTORY_GARDEN_LANDING_INPUT_HISTORY,
	TOY_FACTORY_GARDEN_LANDING_INPUT_MODE_COUNT,
};

/* The first eight indexes also describe raw packet fields. */
enum toy_factory_garden_landing_feature {
	TOY_FACTORY_GARDEN_LANDING_SPACE_FREE,
	TOY_FACTORY_GARDEN_LANDING_DEAD_ONLY,
	TOY_FACTORY_GARDEN_LANDING_WATER_NOW,
	TOY_FACTORY_GARDEN_LANDING_LIGHT_NOW,
	TOY_FACTORY_GARDEN_LANDING_WET_EMA,
	TOY_FACTORY_GARDEN_LANDING_LIGHT_EMA,
	TOY_FACTORY_GARDEN_LANDING_WET_LIGHT_EMA,
	TOY_FACTORY_GARDEN_LANDING_OPEN_WET_LIGHT_EMA,
	TOY_FACTORY_GARDEN_LANDING_WARMUP,
};

/* Policy/evaluation metadata, never itself a neural input. Reserved must be zero. */
struct toy_factory_garden_landing_feature_config {
	uint8_t version;
	uint8_t mode;
	uint8_t flags;
	uint8_t reserved;
};

struct toy_factory_garden_landing_inputs {
	int8_t common[TOY_FACTORY_GARDEN_LANDING_COMMON_COUNT];
	int8_t candidates[PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES]
			 [TOY_FACTORY_GARDEN_LANDING_CANDIDATE_COUNT];
};

/* Preserve the complete 77-byte legacy tensor, not a resized legacy struct. */
struct toy_factory_garden_landing_features {
	struct picosystem_garden_neural_features legacy;
	struct toy_factory_garden_landing_inputs landing;
};

/* Pure, caller-owned encoder. Error leaves output unchanged; buffers must not
 * alias. A null packet is allowed only in OFF mode. Supplied packets are always
 * validated, even when masked. Caller binds packet to this observation/phase.
 * No inference, model conversion, policy memory, RNG or cache mutation here.
 */
int toy_factory_garden_landing_features_encode(
	const struct picosystem_garden_agent_observation *observation,
	const struct picosystem_garden_landing_packet *packet,
	const struct toy_factory_garden_landing_feature_config *config,
	struct toy_factory_garden_landing_features *features);

#endif
