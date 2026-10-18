/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_LANDING_DECISIONS_H_
#define TOY_FACTORY_GARDEN_LANDING_DECISIONS_H_

#include "garden_landing_run.h"
#include <stdio.h>

#define TOY_FACTORY_GARDEN_DECISION_PROBES    16U
#define TOY_FACTORY_GARDEN_DECISION_DAYS      256U
#define TOY_FACTORY_GARDEN_DECISION_DAY_TICKS 3840U

struct toy_factory_garden_decision_sample {
	struct picosystem_garden_agent_observation observation;
	struct picosystem_garden_agent_memory memory;
	struct picosystem_garden_landing_packet packet;
	struct picosystem_garden_agent_decision live;
};

/* Host-only bounded collector. One owner, borrowed stream/model outlive it.
 * Failed steps/I/O leave an incomplete trace that must be discarded. A footer
 * plus successful process exit and matching replay are required for acceptance.
 * Samples are first root/stem query per day, never chosen by probe outcome.
 */
struct toy_factory_garden_decision_trace {
	FILE *stream;
	const struct toy_factory_garden_landing_model *model;
	uint32_t tick;
	uint32_t daily_queries[TOY_FACTORY_GARDEN_DECISION_DAYS][2];
	uint32_t histograms[4][256];
	uint32_t common_valid;
	uint32_t samples;
	bool pending[2];
	struct toy_factory_garden_decision_sample sample[2];
};

/* Pure one-shot counterfactual; current-only/flags=0. Output unchanged on error. */
int toy_factory_garden_decision_probe(const struct picosystem_garden_agent_observation *observation,
				      const struct picosystem_garden_agent_memory *memory,
				      const struct picosystem_garden_landing_packet *packet,
				      const struct toy_factory_garden_landing_model *model,
				      uint8_t probe,
				      struct picosystem_garden_agent_decision *decision);
int toy_factory_garden_decision_trace_init(struct toy_factory_garden_decision_trace *trace,
					   FILE *stream,
					   const struct toy_factory_garden_landing_model *model);
int toy_factory_garden_decision_trace_observe(
	const struct picosystem_garden_agent_observation *observation,
	const struct picosystem_garden_agent_memory *memory,
	const struct picosystem_garden_landing_packet *packet,
	const struct picosystem_garden_agent_decision *decision, void *context);
/* Publish pending samples only after a successful world step. */
int toy_factory_garden_decision_trace_publish(struct toy_factory_garden_decision_trace *trace);
int toy_factory_garden_decision_trace_finish(struct toy_factory_garden_decision_trace *trace,
					     uint32_t tick, uint32_t run_hash);

#endif
