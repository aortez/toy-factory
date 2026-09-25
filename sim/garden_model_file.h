/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef TOY_FACTORY_GARDEN_MODEL_FILE_H_
#define TOY_FACTORY_GARDEN_MODEL_FILE_H_

#include <stdint.h>

#include "garden_agent_neural.h"

/* The fingerprint is the CRC-32 of the canonical model payload. */
int toy_factory_garden_model_fingerprint(const struct picosystem_garden_neural_model *model,
					 uint32_t *fingerprint);

/* Read or atomically write one canonical binary model container. */
int toy_factory_garden_model_read(const char *path, struct picosystem_garden_neural_model *model,
				  uint32_t *fingerprint);
int toy_factory_garden_model_write_binary(const char *path,
					  const struct picosystem_garden_neural_model *model,
					  uint32_t *fingerprint);

/* Atomically emit a flash-linkable const model definition. */
int toy_factory_garden_model_write_c(const char *path,
				     const struct picosystem_garden_neural_model *model,
				     const char *symbol, uint32_t fingerprint);

#endif /* TOY_FACTORY_GARDEN_MODEL_FILE_H_ */
