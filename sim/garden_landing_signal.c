/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_signal.h"
#include "garden_landing_run_internal.h"

#include <errno.h>

_Static_assert(sizeof(struct toy_factory_garden_landing_signal_config) == 4U, "probe identity");

static const uint8_t occupancy_values[TOY_FACTORY_GARDEN_LANDING_OCCUPANCY_COUNT][2] = {
	[TOY_FACTORY_GARDEN_LANDING_OCCUPANCY_NEUTRAL] = {128U, 128U},
	[TOY_FACTORY_GARDEN_LANDING_OCCUPANCY_OCCUPIED] = {0U, 0U},
	[TOY_FACTORY_GARDEN_LANDING_OCCUPANCY_OPEN] = {255U, 0U},
};
static const uint8_t resource_values[TOY_FACTORY_GARDEN_LANDING_RESOURCE_COUNT] = {
	[TOY_FACTORY_GARDEN_LANDING_RESOURCE_MID] = 128U,
	[TOY_FACTORY_GARDEN_LANDING_RESOURCE_LOW] = 0U,
	[TOY_FACTORY_GARDEN_LANDING_RESOURCE_HIGH] = 255U,
};

static int validate_config(const struct toy_factory_garden_landing_signal_config *config)
{
	if (config == NULL) {
		return -EINVAL;
	}
	return ((config->version == TOY_FACTORY_GARDEN_LANDING_SIGNAL_VERSION) &&
		(config->occupancy < TOY_FACTORY_GARDEN_LANDING_OCCUPANCY_COUNT) &&
		(config->resources < TOY_FACTORY_GARDEN_LANDING_RESOURCE_COUNT) &&
		(config->reserved == 0U))
		       ? 0
		       : -ERANGE;
}

static bool supported(const struct toy_factory_garden_landing_model *model)
{
	return (model->config.mode == TOY_FACTORY_GARDEN_LANDING_INPUT_CURRENT) &&
	       (model->config.flags == 0U);
}

int toy_factory_garden_landing_signal_apply(
	const struct picosystem_garden_agent_observation *observation,
	const struct picosystem_garden_landing_packet *packet,
	const struct toy_factory_garden_landing_signal_config *config,
	struct picosystem_garden_landing_packet *output)
{
	if ((observation == NULL) || (packet == NULL) || (output == NULL)) {
		return -EINVAL;
	}
	int err = validate_config(config);
	if (err != 0) {
		return err;
	}
	/* Reuse the authoritative packet/observation validator, including source
	 * gating and trace bounds. The probe never relaxes real-input validation.
	 */
	const struct toy_factory_garden_landing_feature_config features_config = {
		.version = TOY_FACTORY_GARDEN_LANDING_FEATURE_VERSION,
		.mode = TOY_FACTORY_GARDEN_LANDING_INPUT_CURRENT};
	struct toy_factory_garden_landing_features features;
	err = toy_factory_garden_landing_features_encode(observation, packet, &features_config,
							 &features);
	if (err != 0) {
		return err;
	}
	struct picosystem_garden_landing_packet result = *packet;
	for (uint8_t i = 0U; i < PICOSYSTEM_GARDEN_LANDING_SOURCES; ++i) {
		if ((packet->valid & (1U << i)) == 0U) {
			continue;
		}
		uint8_t *const values = result.values[i];
		if (config->occupancy != TOY_FACTORY_GARDEN_LANDING_OCCUPANCY_LIVE) {
			values[TOY_FACTORY_GARDEN_LANDING_SPACE_FREE] =
				occupancy_values[config->occupancy][0];
			values[TOY_FACTORY_GARDEN_LANDING_DEAD_ONLY] =
				occupancy_values[config->occupancy][1];
		}
		if (config->resources != TOY_FACTORY_GARDEN_LANDING_RESOURCE_LIVE) {
			const uint8_t value = resource_values[config->resources];
			values[TOY_FACTORY_GARDEN_LANDING_WATER_NOW] = value;
			values[TOY_FACTORY_GARDEN_LANDING_LIGHT_NOW] = value;
		}
	}
	*output = result;
	return 0;
}

int toy_factory_garden_landing_signal_init(
	const struct picosystem_garden_world *world,
	const struct toy_factory_garden_landing_model *model,
	const struct toy_factory_garden_landing_signal_config *config,
	struct toy_factory_garden_landing_signal_run *run)
{
	if (run == NULL) {
		return -EINVAL;
	}
	int err = validate_config(config);
	if (err != 0) {
		return err;
	}
	struct toy_factory_garden_landing_signal_run result = {.config = *config};
	err = toy_factory_garden_landing_run_init(world, model, &result.base);
	if (err != 0) {
		return err;
	}
	if (!supported(model)) {
		return -ENOTSUP;
	}
	*run = result;
	return 0;
}

static int validate_run(const struct toy_factory_garden_landing_signal_run *run)
{
	if (run == NULL) {
		return -EINVAL;
	}
	const int err = validate_config(&run->config);
	return (err != 0) ? err : (supported(&run->base.model) ? 0 : -ENOTSUP);
}

int toy_factory_garden_landing_signal_step(struct toy_factory_garden_landing_signal_run *run,
					   struct picosystem_garden_death_audit *deaths,
					   struct picosystem_garden_seed_audit *seeds)
{
	if ((deaths == NULL) || (seeds == NULL)) {
		return -EINVAL;
	}
	const int err = validate_run(run);
	return (err != 0) ? err
			  : toy_factory_garden_landing_run_step_signal_internal(
				    &run->base, &run->config, deaths, seeds);
}

int toy_factory_garden_landing_signal_hash(const struct toy_factory_garden_landing_signal_run *run,
					   uint32_t *hash)
{
	if (hash == NULL) {
		return -EINVAL;
	}
	int err = validate_run(run);
	if (err != 0) {
		return err;
	}
	uint32_t base;
	err = toy_factory_garden_landing_run_hash(&run->base, &base);
	if (err != 0) {
		return err;
	}
	const uint8_t bytes[] = {'G',
				 'S',
				 'P',
				 '1',
				 (uint8_t)base,
				 (uint8_t)(base >> 8U),
				 (uint8_t)(base >> 16U),
				 (uint8_t)(base >> 24U),
				 run->config.version,
				 run->config.occupancy,
				 run->config.resources,
				 run->config.reserved};
	uint32_t h = UINT32_C(2166136261);
	for (size_t i = 0U; i < sizeof(bytes); ++i) {
		h = (h ^ bytes[i]) * UINT32_C(16777619);
	}
	*hash = h;
	return 0;
}
