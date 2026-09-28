/* SPDX-License-Identifier: Apache-2.0 */
#include <stdio.h>
#include <string.h>

#include "garden_landing_features.h"

#define PROBE_REQUEST_SIZE  62U
#define PROBE_RESPONSE_SIZE 53U

/* Fixed synthetic context: this probe tests the extension, not reconstruction
 * of the old 77 inputs from incomplete shadow receipts. Native trajectory tests
 * separately compare that prefix using full real observations.
 */
static void process(const uint8_t *request, uint8_t *response,
		    const struct picosystem_garden_agent_observation *fixture)
{
	const struct toy_factory_garden_landing_feature_config config = {
		.version = request[0],
		.mode = request[1],
		.flags = request[2],
		.reserved = request[3],
	};
	struct picosystem_garden_agent_observation observation = *fixture;
	observation.tissue_kind = request[4];
	observation.candidate_count =
		(observation.tissue_kind == PICOSYSTEM_GARDEN_NODE_STEM) ? 5U : 3U;
	for (uint8_t i = 0U; i < PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES; ++i) {
		observation.candidates[i].flags = request[5U + i];
	}
	struct picosystem_garden_landing_packet packet = {
		.version = request[10],
		.valid = request[11],
		.warmup_samples = (uint16_t)(request[12] | ((uint16_t)request[13] << 8U)),
	};
	memcpy(packet.values, &request[14], sizeof(packet.values));
	struct toy_factory_garden_landing_features features;
	memset(&features, 0xa5, sizeof(features));
	const int err = toy_factory_garden_landing_features_encode(&observation, &packet, &config,
								   &features);
	const uint32_t status = (uint32_t)err;
	for (uint8_t i = 0U; i < 4U; ++i) {
		response[i] = (uint8_t)(status >> (i * 8U));
	}
	for (uint8_t i = 0U; i < TOY_FACTORY_GARDEN_LANDING_COMMON_COUNT; ++i) {
		response[4U + i] = (uint8_t)features.landing.common[i];
	}
	for (uint8_t i = 0U; i < PICOSYSTEM_GARDEN_AGENT_MAX_CANDIDATES; ++i) {
		for (uint8_t f = 0U; f < TOY_FACTORY_GARDEN_LANDING_CANDIDATE_COUNT; ++f) {
			response[13U + i * TOY_FACTORY_GARDEN_LANDING_CANDIDATE_COUNT + f] =
				(uint8_t)features.landing.candidates[i][f];
		}
	}
}

int main(int argc, char **argv)
{
	(void)argv;
	if (argc != 1) {
		fprintf(stderr,
			"Read fixed 62-byte requests; write status + 49 signed feature bytes\n");
		return 2;
	}
	struct picosystem_garden_world world;
	struct picosystem_garden_agent_observation fixture;
	if ((picosystem_garden_world_reset(&world, 123U) != 0) ||
	    (picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 3U) !=
	     0) ||
	    (picosystem_garden_agent_observe_tip(&world, 0U, 1U, 0U, &fixture) != 0)) {
		return 1;
	}
	uint8_t request[PROBE_REQUEST_SIZE];
	uint8_t response[PROBE_RESPONSE_SIZE];
	for (;;) {
		const size_t size = fread(request, 1U, sizeof(request), stdin);
		if ((size == 0U) && feof(stdin)) {
			break;
		}
		if (size != sizeof(request)) {
			fprintf(stderr, "Truncated feature probe request or input error\n");
			return 2;
		}
		process(request, response, &fixture);
		if (fwrite(response, 1U, sizeof(response), stdout) != sizeof(response)) {
			return 1;
		}
	}
	return (ferror(stdin) || (fflush(stdout) != 0) || ferror(stdout)) ? 1 : 0;
}
