/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_GARDEN_AGENT_NEURAL_H_
#define PICOSYSTEM_GARDEN_AGENT_NEURAL_H_

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "garden_agent.h"

#define PICOSYSTEM_GARDEN_NEURAL_MODEL_MAGIC             UINT32_C(0x314e4e47)
#define PICOSYSTEM_GARDEN_NEURAL_MODEL_VERSION           1U
#define PICOSYSTEM_GARDEN_NEURAL_FEATURE_VERSION         1U
#define PICOSYSTEM_GARDEN_NEURAL_COMMON_FEATURE_COUNT    32U
#define PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT       16U
#define PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_FEATURE_COUNT 9U
#define PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT    8U
#define PICOSYSTEM_GARDEN_NEURAL_MODEL_SIZE              1204U
#define PICOSYSTEM_GARDEN_NEURAL_MAX_SHIFT               15U
#define PICOSYSTEM_GARDEN_NEURAL_MAX_ABSOLUTE_BIAS       INT32_C(1000000)
#define PICOSYSTEM_GARDEN_NEURAL_FILE_MAGIC              UINT32_C(0x314d4754)
#define PICOSYSTEM_GARDEN_NEURAL_FILE_VERSION            1U
#define PICOSYSTEM_GARDEN_NEURAL_FILE_HEADER_SIZE        16U
#define PICOSYSTEM_GARDEN_NEURAL_FILE_SIZE                                                         \
	(PICOSYSTEM_GARDEN_NEURAL_FILE_HEADER_SIZE + PICOSYSTEM_GARDEN_NEURAL_MODEL_SIZE)

#define PICOSYSTEM_GARDEN_NEURAL_HIDDEN_INPUT_COUNT                                                \
	(PICOSYSTEM_GARDEN_NEURAL_COMMON_FEATURE_COUNT + PICOSYSTEM_GARDEN_AGENT_MEMORY_WIDTH)

enum picosystem_garden_neural_common_feature {
	PICOSYSTEM_GARDEN_NEURAL_COMMON_SPECIES_FLOWER = 0,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_SPECIES_SHRUB = 1,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_SPECIES_GROUND_COVER = 2,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_TISSUE = 3,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_DEPTH = 4,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_REMAINING_DEPTH = 5,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_TIP_FROM_BASE_X = 6,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_PARENT_DELTA_X = 7,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_PARENT_DELTA_Y = 8,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_TIP_LIGHT = 9,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_TIP_MOISTURE = 10,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_ENERGY = 11,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_WATER = 12,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_ENERGY_RESERVE = 13,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_WATER_RESERVE = 14,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_STRESS = 15,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_ENERGY_INCOME = 16,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_WATER_INCOME = 17,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_ROOT_SHOOT_BALANCE = 18,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_LEAF_COUNT = 19,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_ACTIVE_TIP_COUNT = 20,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_VIGOR = 21,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_SUN_STRENGTH = 22,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_SUN_RAY_STEP = 23,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_MAINTENANCE_PHASE = 24,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_SHAPE_TENDENCY = 25,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_FLOWER_REMAINING = 26,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_TIP_STATE = 27,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_GROWTH_RATE = 28,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_SHOOT_BIAS = 29,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_LIGHT_SEEKING = 30,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_WATER_SEEKING = 31,
	PICOSYSTEM_GARDEN_NEURAL_COMMON_FEATURE_ENUM_COUNT = 32,
};

enum picosystem_garden_neural_candidate_feature {
	PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_DELTA_X = 0,
	PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_DELTA_Y = 1,
	PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_LIGHT = 2,
	PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_MOISTURE = 3,
	PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_CLEARANCE = 4,
	PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_IN_BOUNDS = 5,
	PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_AVAILABLE = 6,
	PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_OWN_NEAR = 7,
	PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_FOREIGN_NEAR = 8,
	PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_FEATURE_ENUM_COUNT = 9,
};

/* Canonical signed-byte input shared by firmware and host-side model tooling. */
struct picosystem_garden_neural_features {
	int8_t common[PICOSYSTEM_GARDEN_NEURAL_COMMON_FEATURE_COUNT];
	int8_t candidates[PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES]
			 [PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_FEATURE_COUNT];
};

/*
 * Immutable, position-independent model data. Integer widths and array order are
 * part of the versioned ABI so host-produced models can be linked into flash.
 */
struct picosystem_garden_neural_model {
	uint32_t magic;
	uint16_t model_version;
	uint16_t feature_version;
	uint16_t model_size;
	uint8_t hidden_shift;
	uint8_t output_shift;
	uint8_t candidate_hidden_shift;
	uint8_t reserved[3];
	int32_t hidden_bias[PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT];
	int8_t hidden_weights[PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT]
			     [PICOSYSTEM_GARDEN_NEURAL_HIDDEN_INPUT_COUNT];
	int32_t action_bias[PICOSYSTEM_GARDEN_AGENT_ACTION_COUNT];
	int8_t action_weights[PICOSYSTEM_GARDEN_AGENT_ACTION_COUNT]
			     [PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT];
	int32_t priority_bias;
	int8_t priority_weights[PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT];
	int32_t memory_bias[PICOSYSTEM_GARDEN_AGENT_MEMORY_WIDTH];
	int8_t memory_weights[PICOSYSTEM_GARDEN_AGENT_MEMORY_WIDTH]
			     [PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT];
	int32_t candidate_hidden_bias[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT];
	int8_t candidate_hidden_weights[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT]
				       [PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT];
	int8_t candidate_feature_weights[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT]
					[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_FEATURE_COUNT];
	int32_t candidate_output_bias;
	int8_t candidate_output_weights[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT];
};

/* Convert a validated observation into the stable feature representation. */
int picosystem_garden_neural_encode_features(
	const struct picosystem_garden_agent_observation *observation,
	struct picosystem_garden_neural_features *features);

/* Reject incompatible or arithmetically unsafe flash-resident model data. */
int picosystem_garden_neural_model_validate(const struct picosystem_garden_neural_model *model);

/* Encode or transactionally decode the canonical little-endian, CRC-protected file format. */
int picosystem_garden_neural_model_encode(const struct picosystem_garden_neural_model *model,
					  uint8_t *buffer, size_t capacity);
int picosystem_garden_neural_model_decode(const uint8_t *buffer, size_t size,
					  struct picosystem_garden_neural_model *model);

/* Build a caller-owned all-tip policy around one immutable model. */
int picosystem_garden_neural_policy_init(const struct picosystem_garden_neural_model *model,
					 struct picosystem_garden_agent_policy *policy);

/* Policy callback used by initialized neural policies. */
int picosystem_garden_agent_neural_decide(
	const struct picosystem_garden_agent_observation *observation,
	const struct picosystem_garden_agent_memory *memory,
	struct picosystem_garden_agent_decision *decision, const void *context);

/* Fixed, deliberately untrained model used to exercise the complete inference path. */
const struct picosystem_garden_neural_model *picosystem_garden_neural_reference_model(void);
const struct picosystem_garden_agent_policy *picosystem_garden_agent_neural_reference_policy(void);

#endif /* PICOSYSTEM_GARDEN_AGENT_NEURAL_H_ */
