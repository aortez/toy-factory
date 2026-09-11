/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "garden_agent_neural.h"

#include <errno.h>
#include <limits.h>
#include <stddef.h>
#include <stdint.h>

struct garden_neural_writer {
	uint8_t *bytes;
	size_t offset;
};

struct garden_neural_reader {
	const uint8_t *bytes;
	size_t offset;
};

_Static_assert(PICOSYSTEM_GARDEN_NEURAL_FILE_SIZE == 1220U, "Garden neural file layout changed");

static void write_u8(struct garden_neural_writer *writer, uint8_t value)
{
	writer->bytes[writer->offset++] = value;
}

static void write_i8(struct garden_neural_writer *writer, int8_t value)
{
	write_u8(writer, (uint8_t)value);
}

static void write_u16(struct garden_neural_writer *writer, uint16_t value)
{
	write_u8(writer, (uint8_t)value);
	write_u8(writer, (uint8_t)(value >> 8U));
}

static void write_u32(struct garden_neural_writer *writer, uint32_t value)
{
	write_u8(writer, (uint8_t)value);
	write_u8(writer, (uint8_t)(value >> 8U));
	write_u8(writer, (uint8_t)(value >> 16U));
	write_u8(writer, (uint8_t)(value >> 24U));
}

static void write_i32(struct garden_neural_writer *writer, int32_t value)
{
	write_u32(writer, (uint32_t)value);
}

static uint8_t read_u8(struct garden_neural_reader *reader)
{
	return reader->bytes[reader->offset++];
}

static int8_t read_i8(struct garden_neural_reader *reader)
{
	const uint8_t value = read_u8(reader);
	return (value <= INT8_MAX) ? (int8_t)value : (int8_t)((int16_t)value - 256);
}

static uint16_t read_u16(struct garden_neural_reader *reader)
{
	uint16_t value = read_u8(reader);
	value |= (uint16_t)((uint16_t)read_u8(reader) << 8U);
	return value;
}

static uint32_t read_u32(struct garden_neural_reader *reader)
{
	uint32_t value = read_u8(reader);
	value |= (uint32_t)read_u8(reader) << 8U;
	value |= (uint32_t)read_u8(reader) << 16U;
	value |= (uint32_t)read_u8(reader) << 24U;
	return value;
}

static int32_t read_i32(struct garden_neural_reader *reader)
{
	const uint32_t value = read_u32(reader);
	if (value <= INT32_MAX) {
		return (int32_t)value;
	}
	return -1 - (int32_t)(UINT32_MAX - value);
}

static uint32_t crc32(const uint8_t *bytes, size_t size)
{
	uint32_t crc = UINT32_MAX;
	for (size_t index = 0U; index < size; ++index) {
		crc ^= bytes[index];
		for (uint8_t bit = 0U; bit < 8U; ++bit) {
			if ((crc & 1U) != 0U) {
				crc = (crc >> 1U) ^ UINT32_C(0xedb88320);
			} else {
				crc >>= 1U;
			}
		}
	}
	return ~crc;
}

static size_t encode_payload(const struct picosystem_garden_neural_model *model, uint8_t *bytes)
{
	struct garden_neural_writer writer = {.bytes = bytes};
	write_u32(&writer, model->magic);
	write_u16(&writer, model->model_version);
	write_u16(&writer, model->feature_version);
	write_u16(&writer, model->model_size);
	write_u8(&writer, model->hidden_shift);
	write_u8(&writer, model->output_shift);
	write_u8(&writer, model->candidate_hidden_shift);
	for (size_t index = 0U; index < sizeof(model->reserved); ++index) {
		write_u8(&writer, model->reserved[index]);
	}
	for (size_t index = 0U; index < PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT; ++index) {
		write_i32(&writer, model->hidden_bias[index]);
	}
	for (size_t unit = 0U; unit < PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT; ++unit) {
		for (size_t input = 0U; input < PICOSYSTEM_GARDEN_NEURAL_HIDDEN_INPUT_COUNT;
		     ++input) {
			write_i8(&writer, model->hidden_weights[unit][input]);
		}
	}
	for (size_t index = 0U; index < PICOSYSTEM_GARDEN_AGENT_ACTION_COUNT; ++index) {
		write_i32(&writer, model->action_bias[index]);
	}
	for (size_t action = 0U; action < PICOSYSTEM_GARDEN_AGENT_ACTION_COUNT; ++action) {
		for (size_t unit = 0U; unit < PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT; ++unit) {
			write_i8(&writer, model->action_weights[action][unit]);
		}
	}
	write_i32(&writer, model->priority_bias);
	for (size_t index = 0U; index < PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT; ++index) {
		write_i8(&writer, model->priority_weights[index]);
	}
	for (size_t index = 0U; index < PICOSYSTEM_GARDEN_AGENT_MEMORY_WIDTH; ++index) {
		write_i32(&writer, model->memory_bias[index]);
	}
	for (size_t memory = 0U; memory < PICOSYSTEM_GARDEN_AGENT_MEMORY_WIDTH; ++memory) {
		for (size_t unit = 0U; unit < PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT; ++unit) {
			write_i8(&writer, model->memory_weights[memory][unit]);
		}
	}
	for (size_t index = 0U; index < PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT; ++index) {
		write_i32(&writer, model->candidate_hidden_bias[index]);
	}
	for (size_t candidate_unit = 0U;
	     candidate_unit < PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT; ++candidate_unit) {
		for (size_t hidden_unit = 0U;
		     hidden_unit < PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT; ++hidden_unit) {
			write_i8(&writer,
				 model->candidate_hidden_weights[candidate_unit][hidden_unit]);
		}
	}
	for (size_t candidate_unit = 0U;
	     candidate_unit < PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT; ++candidate_unit) {
		for (size_t feature = 0U;
		     feature < PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_FEATURE_COUNT; ++feature) {
			write_i8(&writer,
				 model->candidate_feature_weights[candidate_unit][feature]);
		}
	}
	write_i32(&writer, model->candidate_output_bias);
	for (size_t index = 0U; index < PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT; ++index) {
		write_i8(&writer, model->candidate_output_weights[index]);
	}
	return writer.offset;
}

static size_t decode_payload(const uint8_t *bytes, struct picosystem_garden_neural_model *model)
{
	struct garden_neural_reader reader = {.bytes = bytes};
	*model = (struct picosystem_garden_neural_model){0};
	model->magic = read_u32(&reader);
	model->model_version = read_u16(&reader);
	model->feature_version = read_u16(&reader);
	model->model_size = read_u16(&reader);
	model->hidden_shift = read_u8(&reader);
	model->output_shift = read_u8(&reader);
	model->candidate_hidden_shift = read_u8(&reader);
	for (size_t index = 0U; index < sizeof(model->reserved); ++index) {
		model->reserved[index] = read_u8(&reader);
	}
	for (size_t index = 0U; index < PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT; ++index) {
		model->hidden_bias[index] = read_i32(&reader);
	}
	for (size_t unit = 0U; unit < PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT; ++unit) {
		for (size_t input = 0U; input < PICOSYSTEM_GARDEN_NEURAL_HIDDEN_INPUT_COUNT;
		     ++input) {
			model->hidden_weights[unit][input] = read_i8(&reader);
		}
	}
	for (size_t index = 0U; index < PICOSYSTEM_GARDEN_AGENT_ACTION_COUNT; ++index) {
		model->action_bias[index] = read_i32(&reader);
	}
	for (size_t action = 0U; action < PICOSYSTEM_GARDEN_AGENT_ACTION_COUNT; ++action) {
		for (size_t unit = 0U; unit < PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT; ++unit) {
			model->action_weights[action][unit] = read_i8(&reader);
		}
	}
	model->priority_bias = read_i32(&reader);
	for (size_t index = 0U; index < PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT; ++index) {
		model->priority_weights[index] = read_i8(&reader);
	}
	for (size_t index = 0U; index < PICOSYSTEM_GARDEN_AGENT_MEMORY_WIDTH; ++index) {
		model->memory_bias[index] = read_i32(&reader);
	}
	for (size_t memory = 0U; memory < PICOSYSTEM_GARDEN_AGENT_MEMORY_WIDTH; ++memory) {
		for (size_t unit = 0U; unit < PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT; ++unit) {
			model->memory_weights[memory][unit] = read_i8(&reader);
		}
	}
	for (size_t index = 0U; index < PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT; ++index) {
		model->candidate_hidden_bias[index] = read_i32(&reader);
	}
	for (size_t candidate_unit = 0U;
	     candidate_unit < PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT; ++candidate_unit) {
		for (size_t hidden_unit = 0U;
		     hidden_unit < PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT; ++hidden_unit) {
			model->candidate_hidden_weights[candidate_unit][hidden_unit] =
				read_i8(&reader);
		}
	}
	for (size_t candidate_unit = 0U;
	     candidate_unit < PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT; ++candidate_unit) {
		for (size_t feature = 0U;
		     feature < PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_FEATURE_COUNT; ++feature) {
			model->candidate_feature_weights[candidate_unit][feature] =
				read_i8(&reader);
		}
	}
	model->candidate_output_bias = read_i32(&reader);
	for (size_t index = 0U; index < PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT; ++index) {
		model->candidate_output_weights[index] = read_i8(&reader);
	}
	return reader.offset;
}

int picosystem_garden_neural_model_encode(const struct picosystem_garden_neural_model *model,
					  uint8_t *buffer, size_t capacity)
{
	if ((model == NULL) || (buffer == NULL)) {
		return -EINVAL;
	}
	const int err = picosystem_garden_neural_model_validate(model);
	if (err != 0) {
		return err;
	}
	if (capacity < PICOSYSTEM_GARDEN_NEURAL_FILE_SIZE) {
		return -ENOSPC;
	}

	uint8_t *const payload = &buffer[PICOSYSTEM_GARDEN_NEURAL_FILE_HEADER_SIZE];
	if (encode_payload(model, payload) != PICOSYSTEM_GARDEN_NEURAL_MODEL_SIZE) {
		return -EIO;
	}
	struct garden_neural_writer header = {.bytes = buffer};
	write_u32(&header, PICOSYSTEM_GARDEN_NEURAL_FILE_MAGIC);
	write_u16(&header, PICOSYSTEM_GARDEN_NEURAL_FILE_VERSION);
	write_u16(&header, PICOSYSTEM_GARDEN_NEURAL_FILE_HEADER_SIZE);
	write_u32(&header, PICOSYSTEM_GARDEN_NEURAL_MODEL_SIZE);
	write_u32(&header, crc32(payload, PICOSYSTEM_GARDEN_NEURAL_MODEL_SIZE));
	return 0;
}

int picosystem_garden_neural_model_decode(const uint8_t *buffer, size_t size,
					  struct picosystem_garden_neural_model *model)
{
	if ((buffer == NULL) || (model == NULL)) {
		return -EINVAL;
	}
	if (size != PICOSYSTEM_GARDEN_NEURAL_FILE_SIZE) {
		return -ERANGE;
	}

	struct garden_neural_reader header = {.bytes = buffer};
	const uint32_t magic = read_u32(&header);
	const uint16_t version = read_u16(&header);
	const uint16_t header_size = read_u16(&header);
	const uint32_t payload_size = read_u32(&header);
	const uint32_t expected_crc = read_u32(&header);
	if ((magic != PICOSYSTEM_GARDEN_NEURAL_FILE_MAGIC) ||
	    (version != PICOSYSTEM_GARDEN_NEURAL_FILE_VERSION) ||
	    (header_size != PICOSYSTEM_GARDEN_NEURAL_FILE_HEADER_SIZE) ||
	    (payload_size != PICOSYSTEM_GARDEN_NEURAL_MODEL_SIZE)) {
		return -EILSEQ;
	}
	const uint8_t *const payload = &buffer[header_size];
	if (crc32(payload, payload_size) != expected_crc) {
		return -EILSEQ;
	}

	struct picosystem_garden_neural_model decoded;
	if (decode_payload(payload, &decoded) != payload_size) {
		return -EIO;
	}
	const int err = picosystem_garden_neural_model_validate(&decoded);
	if (err != 0) {
		return err;
	}
	*model = decoded;
	return 0;
}
