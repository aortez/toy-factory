/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_neural.h"

#include <errno.h>
#include <limits.h>
#include <string.h>

#define CONFIG_OFFSET                                                                              \
	(TOY_FACTORY_GARDEN_LANDING_FILE_HEADER_SIZE + PICOSYSTEM_GARDEN_NEURAL_FILE_SIZE)
#define WEIGHTS_OFFSET (CONFIG_OFFSET + 4U)

_Static_assert(WEIGHTS_OFFSET + 16U * 9U + 8U * 8U == TOY_FACTORY_GARDEN_LANDING_FILE_SIZE,
	       "canonical file size");

static void put32(uint8_t *p, uint32_t value)
{
	for (uint8_t i = 0U; i < 4U; ++i) {
		p[i] = (uint8_t)(value >> (8U * i));
	}
}

static uint32_t get32(const uint8_t *p)
{
	return (uint32_t)p[0] | ((uint32_t)p[1] << 8U) | ((uint32_t)p[2] << 16U) |
	       ((uint32_t)p[3] << 24U);
}

static uint32_t crc32(const uint8_t *p, size_t size)
{
	uint32_t crc = UINT32_MAX;
	for (size_t i = 0U; i < size; ++i) {
		crc ^= p[i];
		for (uint8_t bit = 0U; bit < 8U; ++bit) {
			crc = (crc >> 1U) ^ ((crc & 1U) ? UINT32_C(0xedb88320) : 0U);
		}
	}
	return ~crc;
}

static int8_t signed_byte(uint8_t value)
{
	return (value <= INT8_MAX) ? (int8_t)value : (int8_t)((int16_t)value - 256);
}

int toy_factory_garden_landing_model_encode(const struct toy_factory_garden_landing_model *model,
					    uint8_t *buffer, size_t capacity)
{
	if (buffer == NULL) {
		return -EINVAL;
	}
	int err = toy_factory_garden_landing_model_validate(model);
	if (err != 0) {
		return err;
	}
	if (capacity < TOY_FACTORY_GARDEN_LANDING_FILE_SIZE) {
		return -ENOSPC;
	}
	uint8_t result[TOY_FACTORY_GARDEN_LANDING_FILE_SIZE] = {0};
	err = picosystem_garden_neural_model_encode(
		&model->legacy, &result[TOY_FACTORY_GARDEN_LANDING_FILE_HEADER_SIZE],
		PICOSYSTEM_GARDEN_NEURAL_FILE_SIZE);
	if (err != 0) {
		return err;
	}
	result[CONFIG_OFFSET] = model->config.version;
	result[CONFIG_OFFSET + 1U] = model->config.mode;
	result[CONFIG_OFFSET + 2U] = model->config.flags;
	result[CONFIG_OFFSET + 3U] = model->config.reserved;
	size_t offset = WEIGHTS_OFFSET;
	for (size_t u = 0U; u < PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT; ++u) {
		for (size_t f = 0U; f < TOY_FACTORY_GARDEN_LANDING_COMMON_COUNT; ++f) {
			result[offset++] = (uint8_t)model->common_weights[u][f];
		}
	}
	for (size_t u = 0U; u < PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT; ++u) {
		for (size_t f = 0U; f < TOY_FACTORY_GARDEN_LANDING_CANDIDATE_COUNT; ++f) {
			result[offset++] = (uint8_t)model->candidate_weights[u][f];
		}
	}
	put32(result, TOY_FACTORY_GARDEN_LANDING_FILE_MAGIC);
	/* Two little-endian uint16 fields; both upper bytes are explicitly zero. */
	result[4] = TOY_FACTORY_GARDEN_LANDING_FILE_VERSION;
	result[6] = TOY_FACTORY_GARDEN_LANDING_FILE_HEADER_SIZE;
	put32(&result[8],
	      TOY_FACTORY_GARDEN_LANDING_FILE_SIZE - TOY_FACTORY_GARDEN_LANDING_FILE_HEADER_SIZE);
	put32(&result[12], crc32(&result[16], sizeof(result) - 16U));
	memcpy(buffer, result, sizeof(result));
	return 0;
}

int toy_factory_garden_landing_model_decode(const uint8_t *buffer, size_t size,
					    struct toy_factory_garden_landing_model *model)
{
	if ((buffer == NULL) || (model == NULL)) {
		return -EINVAL;
	}
	if (size != TOY_FACTORY_GARDEN_LANDING_FILE_SIZE) {
		return -ERANGE;
	}
	if ((get32(buffer) != TOY_FACTORY_GARDEN_LANDING_FILE_MAGIC) ||
	    (buffer[4] != TOY_FACTORY_GARDEN_LANDING_FILE_VERSION) || (buffer[5] != 0U) ||
	    (buffer[6] != TOY_FACTORY_GARDEN_LANDING_FILE_HEADER_SIZE) || (buffer[7] != 0U) ||
	    (get32(&buffer[8]) != size - TOY_FACTORY_GARDEN_LANDING_FILE_HEADER_SIZE) ||
	    (get32(&buffer[12]) != crc32(&buffer[16], size - 16U))) {
		return -EILSEQ;
	}
	struct toy_factory_garden_landing_model result = {0};
	int err = picosystem_garden_neural_model_decode(
		&buffer[16], PICOSYSTEM_GARDEN_NEURAL_FILE_SIZE, &result.legacy);
	if (err != 0) {
		return err;
	}
	result.config = (struct toy_factory_garden_landing_feature_config){
		.version = buffer[CONFIG_OFFSET],
		.mode = buffer[CONFIG_OFFSET + 1U],
		.flags = buffer[CONFIG_OFFSET + 2U],
		.reserved = buffer[CONFIG_OFFSET + 3U]};
	size_t offset = WEIGHTS_OFFSET;
	for (size_t u = 0U; u < PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT; ++u) {
		for (size_t f = 0U; f < TOY_FACTORY_GARDEN_LANDING_COMMON_COUNT; ++f) {
			result.common_weights[u][f] = signed_byte(buffer[offset++]);
		}
	}
	for (size_t u = 0U; u < PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT; ++u) {
		for (size_t f = 0U; f < TOY_FACTORY_GARDEN_LANDING_CANDIDATE_COUNT; ++f) {
			result.candidate_weights[u][f] = signed_byte(buffer[offset++]);
		}
	}
	err = toy_factory_garden_landing_model_validate(&result);
	if (err != 0) {
		return err;
	}
	*model = result;
	return 0;
}
