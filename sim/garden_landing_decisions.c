/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_decisions.h"

#include <errno.h>
#include <inttypes.h>

struct probe_definition {
	const char *name;
	uint8_t fields;
	uint8_t values[4];
};

/* First ten match the prior group panel; last six split water from light. */
static const struct probe_definition probes[TOY_FACTORY_GARDEN_DECISION_PROBES] = {
	{.name = "live", .fields = 0U},
	{.name = "water-light-only", .fields = 3U, .values = {128U, 128U, 0U, 0U}},
	{.name = "occupancy-only", .fields = 12U, .values = {0U, 0U, 128U, 128U}},
	{.name = "neutral", .fields = 15U, .values = {128U, 128U, 128U, 128U}},
	{.name = "occupied", .fields = 3U},
	{.name = "open", .fields = 3U, .values = {255U, 0U, 0U, 0U}},
	{.name = "low-resources", .fields = 12U},
	{.name = "high-resources", .fields = 12U, .values = {0U, 0U, 255U, 255U}},
	{.name = "fixed-occupied", .fields = 15U, .values = {0U, 0U, 128U, 128U}},
	{.name = "fixed-open", .fields = 15U, .values = {255U, 0U, 128U, 128U}},
	{.name = "water-mid", .fields = 4U, .values = {0U, 0U, 128U, 0U}},
	{.name = "water-low", .fields = 4U},
	{.name = "water-high", .fields = 4U, .values = {0U, 0U, 255U, 0U}},
	{.name = "light-mid", .fields = 8U, .values = {0U, 0U, 0U, 128U}},
	{.name = "light-low", .fields = 8U},
	{.name = "light-high", .fields = 8U, .values = {0U, 0U, 0U, 255U}},
};

static int supported(const struct toy_factory_garden_landing_model *model)
{
	const int err = toy_factory_garden_landing_model_validate(model);
	if (err != 0) {
		return err;
	}
	return ((model->config.mode == TOY_FACTORY_GARDEN_LANDING_INPUT_CURRENT) &&
		(model->config.flags == 0U))
		       ? 0
		       : -ENOTSUP;
}

int toy_factory_garden_decision_probe(const struct picosystem_garden_agent_observation *observation,
				      const struct picosystem_garden_agent_memory *memory,
				      const struct picosystem_garden_landing_packet *packet,
				      const struct toy_factory_garden_landing_model *model,
				      uint8_t probe,
				      struct picosystem_garden_agent_decision *decision)
{
	if ((packet == NULL) || (probe >= TOY_FACTORY_GARDEN_DECISION_PROBES)) {
		return -EINVAL;
	}
	int err = supported(model);
	if (err != 0) {
		return err;
	}
	struct toy_factory_garden_landing_features features;
	err = toy_factory_garden_landing_features_encode(observation, packet, &model->config,
							 &features);
	if (err != 0) {
		return err;
	}
	struct picosystem_garden_landing_packet altered = *packet;
	const struct probe_definition *const p = &probes[probe];
	for (uint8_t s = 0U; s < PICOSYSTEM_GARDEN_LANDING_SOURCES; ++s) {
		if ((packet->valid & (1U << s)) == 0U) {
			continue;
		}
		for (uint8_t f = 0U; f < 4U; ++f) {
			if ((p->fields & (1U << f)) != 0U) {
				altered.values[s][f] = p->values[f];
			}
		}
	}
	return toy_factory_garden_landing_neural_decide(observation, memory, &altered, model,
							decision);
}

static void signed_bytes(FILE *stream, const int8_t *values, size_t count)
{
	fputc('[', stream);
	for (size_t i = 0U; i < count; ++i) {
		fprintf(stream, "%s%d", i ? "," : "", values[i]);
	}
	fputc(']', stream);
}

static void unsigned_bytes(FILE *stream, const uint8_t *values, size_t count)
{
	fputc('[', stream);
	for (size_t i = 0U; i < count; ++i) {
		fprintf(stream, "%s%u", i ? "," : "", values[i]);
	}
	fputc(']', stream);
}

int toy_factory_garden_decision_trace_init(struct toy_factory_garden_decision_trace *trace,
					   FILE *stream,
					   const struct toy_factory_garden_landing_model *model)
{
	if ((trace == NULL) || (stream == NULL)) {
		return -EINVAL;
	}
	const int err = supported(model);
	if (err != 0) {
		return err;
	}
	uint8_t bytes[TOY_FACTORY_GARDEN_LANDING_FILE_SIZE];
	const int encoded = toy_factory_garden_landing_model_encode(model, bytes, sizeof(bytes));
	if (encoded != 0) {
		return encoded;
	}
	fputs("{\"kind\":\"landing-decisions-header\",\"version\":1,"
	      "\"sampling\":\"first-query-per-role-per-day\",\"day_ticks\":3840,\"model\":\"",
	      stream);
	for (size_t i = 0U; i < sizeof(bytes); ++i) {
		fprintf(stream, "%02x", bytes[i]);
	}
	fputs("\",\"probes\":[", stream);
	for (uint8_t i = 0U; i < TOY_FACTORY_GARDEN_DECISION_PROBES; ++i) {
		fprintf(stream, "%s{\"id\":\"%s\",\"fields\":%u,\"values\":", i ? "," : "",
			probes[i].name, probes[i].fields);
		unsigned_bytes(stream, probes[i].values, 4U);
		fputc('}', stream);
	}
	fputs("]}\n", stream);
	if (ferror(stream)) {
		return -EIO;
	}
	*trace = (struct toy_factory_garden_decision_trace){.stream = stream, .model = model};
	return 0;
}

int toy_factory_garden_decision_trace_observe(
	const struct picosystem_garden_agent_observation *observation,
	const struct picosystem_garden_agent_memory *memory,
	const struct picosystem_garden_landing_packet *packet,
	const struct picosystem_garden_agent_decision *decision, void *context)
{
	struct toy_factory_garden_decision_trace *const trace = context;
	if ((trace == NULL) || (observation == NULL) || (memory == NULL) || (packet == NULL) ||
	    (decision == NULL) || (trace->tick == 0U) ||
	    (trace->tick >
	     TOY_FACTORY_GARDEN_DECISION_DAYS * TOY_FACTORY_GARDEN_DECISION_DAY_TICKS)) {
		return -EINVAL;
	}
	if ((observation->tissue_kind != PICOSYSTEM_GARDEN_NODE_ROOT) &&
	    (observation->tissue_kind != PICOSYSTEM_GARDEN_NODE_STEM)) {
		return -ERANGE;
	}
	const uint32_t day = (trace->tick - 1U) / TOY_FACTORY_GARDEN_DECISION_DAY_TICKS;
	const uint8_t role = (uint8_t)(observation->tissue_kind != PICOSYSTEM_GARDEN_NODE_ROOT);
	if (trace->daily_queries[day][role] == UINT32_MAX) {
		return -EOVERFLOW;
	}
	if (trace->daily_queries[day][role]++ == 0U) {
		trace->sample[role] =
			(struct toy_factory_garden_decision_sample){.observation = *observation,
								    .memory = *memory,
								    .packet = *packet,
								    .live = *decision};
		trace->pending[role] = true;
	}
	if ((packet->valid & 1U) != 0U) {
		if (trace->common_valid == UINT32_MAX) {
			return -EOVERFLOW;
		}
		++trace->common_valid;
		for (uint8_t f = 0U; f < 4U; ++f) {
			++trace->histograms[f][packet->values[0][f]];
		}
	}
	return 0;
}

static void print_decision(FILE *stream, const struct picosystem_garden_agent_decision *d)
{
	fprintf(stream,
		"{\"action\":%u,\"priority\":%d,\"count\":%u,\"order\":", d->proposal.action,
		d->proposal.priority, d->proposal.candidate_count);
	unsigned_bytes(stream, d->proposal.candidate_order, PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES);
	fputs(",\"memory\":", stream);
	signed_bytes(stream, d->next_memory.hidden, PICOSYSTEM_GARDEN_AGENT_MEMORY_WIDTH);
	fputc('}', stream);
}

int toy_factory_garden_decision_trace_publish(struct toy_factory_garden_decision_trace *trace)
{
	if ((trace == NULL) || (trace->stream == NULL)) {
		return -EINVAL;
	}
	FILE *const stream = trace->stream;
	for (uint8_t role = 0U; role < 2U; ++role) {
		if (!trace->pending[role]) {
			continue;
		}
		const struct toy_factory_garden_decision_sample *const sample =
			&trace->sample[role];
		const struct picosystem_garden_agent_observation *const o = &sample->observation;
		struct toy_factory_garden_landing_features features;
		int err = toy_factory_garden_landing_features_encode(
			o, &sample->packet, &trace->model->config, &features);
		if (err != 0) {
			return err;
		}
		fprintf(stream,
			"{\"kind\":\"sample\",\"tick\":%" PRIu32
			",\"role\":%u,\"plant_slot\":%u,\"tip\":%u,"
			"\"depth\":%u,\"maximum\":%u,\"nonce\":%" PRIu32
			",\"count\":%u,\"flags\":[",
			trace->tick, role, o->plant_index, o->tip_index, o->depth, o->maximum_depth,
			o->decision_nonce, o->candidate_count);
		for (uint8_t i = 0U; i < o->candidate_count; ++i) {
			fprintf(stream, "%s%u", i ? "," : "", o->candidates[i].flags);
		}
		fputs("],\"common\":", stream);
		signed_bytes(stream, features.legacy.common,
			     PICOSYSTEM_GARDEN_NEURAL_COMMON_FEATURE_COUNT);
		fputs(",\"memory\":", stream);
		signed_bytes(stream, sample->memory.hidden, PICOSYSTEM_GARDEN_AGENT_MEMORY_WIDTH);
		fputs(",\"candidates\":[", stream);
		for (uint8_t i = 0U; i < o->candidate_count; ++i) {
			if (i > 0U) {
				fputc(',', stream);
			}
			signed_bytes(stream, features.legacy.candidates[i],
				     PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_FEATURE_COUNT);
		}
		fprintf(stream, "],\"valid\":%u,\"warmup\":%u,\"packet\":[", sample->packet.valid,
			sample->packet.warmup_samples);
		for (uint8_t i = 0U; i < PICOSYSTEM_GARDEN_LANDING_SOURCES; ++i) {
			if (i > 0U) {
				fputc(',', stream);
			}
			unsigned_bytes(stream, sample->packet.values[i],
				       PICOSYSTEM_GARDEN_LANDING_FIELDS);
		}
		fputs("],\"live\":", stream);
		print_decision(stream, &sample->live);
		fputs(",\"probes\":[", stream);
		for (uint8_t p = 0U; p < TOY_FACTORY_GARDEN_DECISION_PROBES; ++p) {
			struct picosystem_garden_agent_decision decision;
			err = toy_factory_garden_decision_probe(o, &sample->memory, &sample->packet,
								trace->model, p, &decision);
			if (err != 0) {
				return err;
			}
			if (p > 0U) {
				fputc(',', stream);
			}
			print_decision(stream, &decision);
		}
		fputs("]}\n", stream);
		trace->pending[role] = false;
		++trace->samples;
	}
	return ferror(stream) ? -EIO : 0;
}

int toy_factory_garden_decision_trace_finish(struct toy_factory_garden_decision_trace *trace,
					     uint32_t tick, uint32_t run_hash)
{
	if ((trace == NULL) || (trace->stream == NULL) || trace->pending[0] || trace->pending[1] ||
	    (trace->tick != tick) ||
	    (tick > TOY_FACTORY_GARDEN_DECISION_DAYS * TOY_FACTORY_GARDEN_DECISION_DAY_TICKS)) {
		return -EINVAL;
	}
	FILE *const stream = trace->stream;
	fprintf(stream,
		"{\"kind\":\"complete\",\"tick\":%" PRIu32 ",\"run_hash\":\"%08" PRIx32 "\","
		"\"samples\":%" PRIu32 ",\"common_valid\":%" PRIu32 ",\"daily_queries\":[",
		tick, run_hash, trace->samples, trace->common_valid);
	for (uint16_t d = 0U; d < TOY_FACTORY_GARDEN_DECISION_DAYS; ++d) {
		fprintf(stream, "%s[%" PRIu32 ",%" PRIu32 "]", d ? "," : "",
			trace->daily_queries[d][0], trace->daily_queries[d][1]);
	}
	fputs("],\"histograms\":[", stream);
	for (uint8_t f = 0U; f < 4U; ++f) {
		fprintf(stream, "%s[", f ? "," : "");
		for (uint16_t v = 0U; v < 256U; ++v) {
			fprintf(stream, "%s%" PRIu32, v ? "," : "", trace->histograms[f][v]);
		}
		fputc(']', stream);
	}
	fputs("]}\n", stream);
	return (fflush(stream) != 0 || ferror(stream)) ? -EIO : 0;
}
