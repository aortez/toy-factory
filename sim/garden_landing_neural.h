/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_LANDING_NEURAL_H_
#define TOY_FACTORY_GARDEN_LANDING_NEURAL_H_

#include "garden_landing_features.h"

#define TOY_FACTORY_GARDEN_LANDING_MODEL_SIZE       1416U
#define TOY_FACTORY_GARDEN_LANDING_FILE_MAGIC       UINT32_C(0x324c4754) /* TGL2 */
#define TOY_FACTORY_GARDEN_LANDING_FILE_VERSION     2U
#define TOY_FACTORY_GARDEN_LANDING_FILE_HEADER_SIZE 16U
#define TOY_FACTORY_GARDEN_LANDING_FILE_SIZE        1448U

/* Immutable per evaluation. No implicit cast/import from the legacy model.
 * Extra dot products enter BEFORE the original shifts and activations.
 */
struct toy_factory_garden_landing_model {
	struct picosystem_garden_neural_model legacy;
	struct toy_factory_garden_landing_feature_config config;
	int8_t common_weights[PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT]
			     [TOY_FACTORY_GARDEN_LANDING_COMMON_COUNT];
	int8_t candidate_weights[PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT]
				[TOY_FACTORY_GARDEN_LANDING_CANDIDATE_COUNT];
};

/* All APIs are caller-owned, non-aliasing, and preserve outputs on failure. */
int toy_factory_garden_landing_model_validate(const struct toy_factory_garden_landing_model *model);
int toy_factory_garden_landing_model_import(
	const struct picosystem_garden_neural_model *legacy,
	const struct toy_factory_garden_landing_feature_config *config,
	struct toy_factory_garden_landing_model *model);

/* Canonical LE container: header, complete legacy file, config, row-major weights.
 * Decode requires EXACT size. Legacy files require explicit decode + import.
 * CRC detects accidental corruption; it does not authenticate a model.
 */
int toy_factory_garden_landing_model_encode(const struct toy_factory_garden_landing_model *model,
					    uint8_t *buffer, size_t capacity);
int toy_factory_garden_landing_model_decode(const uint8_t *buffer, size_t size,
					    struct toy_factory_garden_landing_model *model);

/* Pure inference; no world/RNG/memory/cache mutation. A null packet is allowed
 * only with the off mask. The caller binds a real packet to its observation.
 */
int toy_factory_garden_landing_neural_decide(
	const struct picosystem_garden_agent_observation *observation,
	const struct picosystem_garden_agent_memory *memory,
	const struct picosystem_garden_landing_packet *packet,
	const struct toy_factory_garden_landing_model *model,
	struct picosystem_garden_agent_decision *decision);

#endif
