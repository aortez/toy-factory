/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "garden_agent.h"
#include "garden_agent_neural.h"
#include "garden_evaluation.h"
#include "garden_model_file.h"
#include "garden_world.h"
#include "portable_util.h"

#define GARDEN_EXPERIMENT_SCHEMA_VERSION       3U
#define GARDEN_EXPERIMENT_DEFAULT_TRIALS       8U
#define GARDEN_EXPERIMENT_MAX_TRIALS           64U
#define GARDEN_EXPERIMENT_DEFAULT_TICKS        7680U
#define GARDEN_EXPERIMENT_MAX_TICKS            100000U
#define GARDEN_EXPERIMENT_DEFAULT_SEED         TOY_FACTORY_GARDEN_EVALUATION_DEFAULT_SEED
#define GARDEN_EXPERIMENT_MAX_PLANTS           TOY_FACTORY_GARDEN_EVALUATION_MAX_PLANTS
#define GARDEN_EXPERIMENT_SCENARIO_COUNT       TOY_FACTORY_GARDEN_EVALUATION_SCENARIO_COUNT
#define GARDEN_EXPERIMENT_POLICY_COUNT         3U
#define GARDEN_EXPERIMENT_MAX_TRACKED_LINEAGES TOY_FACTORY_GARDEN_EVALUATION_MAX_TRACKED_LINEAGES

#define GARDEN_EXPERIMENT_LINEAGE_SEEN            (1U << 0)
#define GARDEN_EXPERIMENT_LINEAGE_DEAD            (1U << 1)
#define GARDEN_EXPERIMENT_LINEAGE_ESTABLISHED     (1U << 2)
#define GARDEN_EXPERIMENT_ESTABLISHED_MINIMUM_AGE TOY_FACTORY_GARDEN_ESTABLISHED_MINIMUM_AGE

struct garden_experiment_death_causes {
	uint32_t energy;
	uint32_t water;
	uint32_t combined;
	uint32_t other;
};

struct garden_experiment_seed_blockers {
	uint32_t samples;
	uint32_t dormant;
	uint32_t ready;
	uint32_t blocked;
	uint32_t moisture;
	uint32_t light;
	uint32_t plant_capacity;
	uint32_t node_capacity;
	uint32_t spacing;
};

struct garden_experiment_group_metrics {
	struct garden_experiment_death_causes death_causes;
	uint64_t living_plant_ticks;
	uint64_t descendant_plant_ticks;
	uint32_t established_offspring;
	uint32_t extinction_tick;
	uint16_t maximum_generation;
	uint8_t final_living;
	uint8_t initial_founders;
};

struct garden_experiment_founder_metrics {
	struct garden_experiment_group_metrics metrics;
	uint32_t lineage_id;
	uint8_t species_id;
	uint8_t column;
};

struct garden_experiment_lineage_tracking {
	uint8_t founder_index;
	uint8_t species_id;
	uint8_t flags;
};

struct garden_experiment_policy {
	const char *name;
	const struct picosystem_garden_agent_policy *(*get_policy)(void);
};

struct garden_experiment_outcome {
	struct picosystem_garden_agent_telemetry agent;
	struct garden_experiment_death_causes death_causes;
	struct garden_experiment_seed_blockers seed_blockers;
	struct garden_experiment_group_metrics species[PICOSYSTEM_GARDEN_SPECIES_COUNT];
	struct garden_experiment_founder_metrics founders[GARDEN_EXPERIMENT_MAX_PLANTS];
	uint64_t living_plant_ticks;
	uint64_t descendant_plant_ticks;
	uint64_t sampled_energy;
	uint64_t sampled_water;
	uint64_t sampled_stress;
	uint32_t random_seed;
	uint32_t state_hash;
	uint32_t ecology_samples;
	uint32_t bloom_count;
	uint32_t death_count;
	uint32_t reclaimed_plant_count;
	uint32_t reclaimed_node_count;
	uint32_t seed_creation_count;
	uint32_t germination_count;
	uint32_t seed_expiration_count;
	uint32_t mutation_count;
	uint32_t lineage_count;
	uint32_t established_offspring;
	uint32_t extinction_tick;
	uint32_t final_energy;
	uint32_t final_water;
	uint32_t final_stress;
	uint16_t final_node_count;
	uint16_t maximum_node_count;
	uint16_t maximum_generation;
	uint16_t moisture_total;
	uint8_t final_plant_count;
	uint8_t final_living_count;
	uint8_t final_dead_count;
	uint8_t final_seed_count;
	uint8_t maximum_living_count;
	uint8_t nonzero_memory_count;
	uint8_t maximum_stress;
	uint8_t founder_count;
};

struct garden_experiment_summary {
	uint64_t living_plant_ticks;
	uint64_t descendant_plant_ticks;
	uint64_t sampled_energy;
	uint64_t sampled_water;
	uint64_t sampled_stress;
	uint64_t agent_decisions;
	uint64_t agent_extend;
	uint64_t agent_wait;
	uint64_t agent_finish;
	uint64_t agent_root;
	uint64_t agent_shoot;
	uint64_t agent_root_extend;
	uint64_t agent_shoot_extend;
	uint64_t blooms;
	uint64_t deaths;
	uint64_t seeds_created;
	uint64_t germinations;
	uint64_t seeds_expired;
	uint64_t mutations;
	uint64_t established_offspring;
	uint64_t death_energy;
	uint64_t death_water;
	uint64_t death_combined;
	uint64_t death_other;
	uint64_t seed_samples;
	uint64_t seed_dormant;
	uint64_t seed_ready;
	uint64_t seed_blocked;
	uint64_t seed_blocked_moisture;
	uint64_t seed_blocked_light;
	uint64_t seed_blocked_plant_capacity;
	uint64_t seed_blocked_node_capacity;
	uint64_t seed_blocked_spacing;
	uint32_t minimum_final_living;
	uint32_t maximum_final_living;
	uint32_t minimum_final_nodes;
	uint32_t maximum_final_nodes;
	uint32_t maximum_generation;
	uint32_t maximum_stress;
	uint32_t extinction_count;
};

static struct picosystem_garden_neural_model candidate_model;
static struct picosystem_garden_agent_policy candidate_policy;
static const struct picosystem_garden_agent_policy *selected_neural_policy;

static const struct picosystem_garden_agent_policy *get_selected_neural_policy(void)
{
	return (selected_neural_policy == NULL) ? picosystem_garden_agent_neural_reference_policy()
						: selected_neural_policy;
}

static struct garden_experiment_policy policies[] = {
	{
		.name = "baseline",
		.get_policy = picosystem_garden_agent_baseline_policy,
	},
	{
		.name = "adaptive",
		.get_policy = picosystem_garden_agent_adaptive_policy,
	},
	{
		.name = "neural-reference",
		.get_policy = get_selected_neural_policy,
	},
};

static struct garden_experiment_outcome outcomes[GARDEN_EXPERIMENT_SCENARIO_COUNT]
						[GARDEN_EXPERIMENT_POLICY_COUNT]
						[GARDEN_EXPERIMENT_MAX_TRIALS];
static struct garden_experiment_lineage_tracking
	lineage_tracking[GARDEN_EXPERIMENT_MAX_TRACKED_LINEAGES + 1U];

_Static_assert(TOY_FACTORY_ARRAY_SIZE(toy_factory_garden_evaluation_scenarios) ==
		       GARDEN_EXPERIMENT_SCENARIO_COUNT,
	       "Garden experiment scenario capacity changed");
_Static_assert(TOY_FACTORY_ARRAY_SIZE(policies) == GARDEN_EXPERIMENT_POLICY_COUNT,
	       "Garden experiment policy capacity changed");
_Static_assert(GARDEN_EXPERIMENT_MAX_TRACKED_LINEAGES >= PICOSYSTEM_GARDEN_MAX_PLANTS,
	       "Garden experiment lineage capacity is too small");

static void print_usage(FILE *stream, const char *program)
{
	fprintf(stream,
		"Usage: %s [--trials 1-%u] [--ticks 1-%u] [--seed UINT32] "
		"[--model PATH]\n",
		program, GARDEN_EXPERIMENT_MAX_TRIALS, GARDEN_EXPERIMENT_MAX_TICKS);
}

static int parse_u32(const char *text, int base, uint32_t minimum, uint32_t maximum,
		     uint32_t *value)
{
	if ((text == NULL) || (value == NULL) || (*text == '\0') || (*text == '-')) {
		return -EINVAL;
	}
	errno = 0;
	char *end = NULL;
	const unsigned long parsed = strtoul(text, &end, base);
	if ((errno != 0) || (*end != '\0') || (parsed < minimum) || (parsed > maximum)) {
		return -ERANGE;
	}
	*value = (uint32_t)parsed;
	return 0;
}

static int parse_options(int argc, char **argv, uint32_t *trial_count, uint32_t *tick_count,
			 uint32_t *base_seed, const char **model_path)
{
	*trial_count = GARDEN_EXPERIMENT_DEFAULT_TRIALS;
	*tick_count = GARDEN_EXPERIMENT_DEFAULT_TICKS;
	*base_seed = GARDEN_EXPERIMENT_DEFAULT_SEED;
	*model_path = NULL;
	for (int index = 1; index < argc; ++index) {
		const char *const option = argv[index];
		if (strcmp(option, "--help") == 0) {
			print_usage(stdout, argv[0]);
			return 1;
		}
		if ((strcmp(option, "--trials") != 0) && (strcmp(option, "--ticks") != 0) &&
		    (strcmp(option, "--seed") != 0) && (strcmp(option, "--model") != 0)) {
			fprintf(stderr, "unknown option '%s'\n", option);
			return -EINVAL;
		}
		if ((index + 1) >= argc) {
			fprintf(stderr, "%s requires another argument\n", option);
			return -EINVAL;
		}
		const char *const value = argv[++index];
		int err = 0;
		if (strcmp(option, "--trials") == 0) {
			err = parse_u32(value, 10, 1U, GARDEN_EXPERIMENT_MAX_TRIALS, trial_count);
		} else if (strcmp(option, "--ticks") == 0) {
			err = parse_u32(value, 10, 1U, GARDEN_EXPERIMENT_MAX_TICKS, tick_count);
		} else if (strcmp(option, "--seed") == 0) {
			err = parse_u32(value, 0, 1U, UINT32_MAX, base_seed);
		} else if (*value == '\0') {
			err = -EINVAL;
		} else {
			*model_path = value;
		}
		if (err != 0) {
			fprintf(stderr, "invalid value '%s' for %s\n", value, option);
			return err;
		}
	}
	return 0;
}

static void current_resource_totals(const struct picosystem_garden_world *world, uint32_t *energy,
				    uint32_t *water, uint32_t *stress, uint8_t *maximum_stress)
{
	*energy = 0U;
	*water = 0U;
	*stress = 0U;
	for (uint8_t index = 0U; index < world->plant_count; ++index) {
		const struct picosystem_garden_plant *const plant = &world->plants[index];
		if ((plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) != 0U) {
			continue;
		}
		*energy += plant->stored_energy;
		*water += plant->stored_water;
		*stress += plant->stress;
		if (plant->stress > *maximum_stress) {
			*maximum_stress = plant->stress;
		}
	}
}

static uint8_t nonzero_memory_count(const struct picosystem_garden_world *world)
{
	uint8_t count = 0U;
	for (uint8_t plant_index = 0U; plant_index < world->plant_count; ++plant_index) {
		bool nonzero = false;
		for (uint8_t memory_index = 0U; memory_index < PICOSYSTEM_GARDEN_AGENT_MEMORY_WIDTH;
		     ++memory_index) {
			if (world->plants[plant_index].agent_memory.hidden[memory_index] != 0) {
				nonzero = true;
				break;
			}
		}
		if (nonzero) {
			++count;
		}
	}
	return count;
}

static uint32_t death_cause_total(const struct garden_experiment_death_causes *causes)
{
	return causes->energy + causes->water + causes->combined + causes->other;
}

static void record_death_cause(struct garden_experiment_death_causes *causes, uint8_t flags)
{
	const uint8_t shortage_flags = flags & (PICOSYSTEM_GARDEN_PLANT_ENERGY_SHORTAGE |
						PICOSYSTEM_GARDEN_PLANT_WATER_SHORTAGE);
	if (shortage_flags ==
	    (PICOSYSTEM_GARDEN_PLANT_ENERGY_SHORTAGE | PICOSYSTEM_GARDEN_PLANT_WATER_SHORTAGE)) {
		++causes->combined;
	} else if (shortage_flags == PICOSYSTEM_GARDEN_PLANT_ENERGY_SHORTAGE) {
		++causes->energy;
	} else if (shortage_flags == PICOSYSTEM_GARDEN_PLANT_WATER_SHORTAGE) {
		++causes->water;
	} else {
		++causes->other;
	}
}

static int initialize_lineage_tracking(const struct picosystem_garden_world *world,
				       struct garden_experiment_outcome *outcome)
{
	memset(lineage_tracking, 0, sizeof(lineage_tracking));
	outcome->founder_count = world->plant_count;
	if (outcome->founder_count > GARDEN_EXPERIMENT_MAX_PLANTS) {
		return -ENOSPC;
	}

	for (uint8_t index = 0U; index < world->plant_count; ++index) {
		const struct picosystem_garden_plant *const plant = &world->plants[index];
		if ((plant->lineage_id == 0U) ||
		    (plant->lineage_id > GARDEN_EXPERIMENT_MAX_TRACKED_LINEAGES) ||
		    (plant->generation != 0U) || (plant->parent_lineage_id != 0U) ||
		    (plant->species_id >= PICOSYSTEM_GARDEN_SPECIES_COUNT)) {
			return -ERANGE;
		}
		struct garden_experiment_lineage_tracking *const tracking =
			&lineage_tracking[plant->lineage_id];
		if ((tracking->flags & GARDEN_EXPERIMENT_LINEAGE_SEEN) != 0U) {
			return -EEXIST;
		}
		*tracking = (struct garden_experiment_lineage_tracking){
			.founder_index = index,
			.species_id = plant->species_id,
			.flags = GARDEN_EXPERIMENT_LINEAGE_SEEN,
		};
		outcome->founders[index] = (struct garden_experiment_founder_metrics){
			.metrics.initial_founders = 1U,
			.lineage_id = plant->lineage_id,
			.species_id = plant->species_id,
			.column = plant->base_column,
		};
		++outcome->species[plant->species_id].initial_founders;
	}
	return 0;
}

static int register_lineage(struct garden_experiment_outcome *outcome,
			    const struct picosystem_garden_plant *plant,
			    struct garden_experiment_lineage_tracking **result)
{
	if ((plant->lineage_id == 0U) || (plant->species_id >= PICOSYSTEM_GARDEN_SPECIES_COUNT)) {
		return -ERANGE;
	}
	if (plant->lineage_id > GARDEN_EXPERIMENT_MAX_TRACKED_LINEAGES) {
		return -ENOSPC;
	}
	struct garden_experiment_lineage_tracking *const tracking =
		&lineage_tracking[plant->lineage_id];
	if ((tracking->flags & GARDEN_EXPERIMENT_LINEAGE_SEEN) == 0U) {
		if ((plant->generation == 0U) || (plant->parent_lineage_id == 0U) ||
		    (plant->parent_lineage_id > GARDEN_EXPERIMENT_MAX_TRACKED_LINEAGES)) {
			return -ERANGE;
		}
		const struct garden_experiment_lineage_tracking *const parent =
			&lineage_tracking[plant->parent_lineage_id];
		if (((parent->flags & GARDEN_EXPERIMENT_LINEAGE_SEEN) == 0U) ||
		    (parent->species_id != plant->species_id) ||
		    (parent->founder_index >= outcome->founder_count)) {
			return -EIO;
		}
		*tracking = (struct garden_experiment_lineage_tracking){
			.founder_index = parent->founder_index,
			.species_id = parent->species_id,
			.flags = GARDEN_EXPERIMENT_LINEAGE_SEEN,
		};
	} else if ((tracking->species_id != plant->species_id) ||
		   (tracking->founder_index >= outcome->founder_count)) {
		return -EIO;
	}

	struct garden_experiment_group_metrics *const species =
		&outcome->species[tracking->species_id];
	struct garden_experiment_group_metrics *const founder =
		&outcome->founders[tracking->founder_index].metrics;
	if (plant->generation > species->maximum_generation) {
		species->maximum_generation = plant->generation;
	}
	if (plant->generation > founder->maximum_generation) {
		founder->maximum_generation = plant->generation;
	}
	*result = tracking;
	return 0;
}

static int record_seed_blockers(const struct picosystem_garden_world *world,
				struct garden_experiment_outcome *outcome)
{
	for (uint8_t index = 0U; index < world->seed_count; ++index) {
		uint8_t blockers;
		const int err =
			picosystem_garden_world_seed_germination_blockers(world, index, &blockers);
		if (err != 0) {
			return err;
		}
		++outcome->seed_blockers.samples;
		if ((blockers & PICOSYSTEM_GARDEN_SEED_BLOCKED_DORMANT) != 0U) {
			++outcome->seed_blockers.dormant;
			continue;
		}
		if (blockers == 0U) {
			/* Final light is recomputed after germination and growth. A seed can
			 * become eligible here and wait until the next ecology step.
			 */
			++outcome->seed_blockers.ready;
			continue;
		}
		++outcome->seed_blockers.blocked;
		if ((blockers & PICOSYSTEM_GARDEN_SEED_BLOCKED_MOISTURE) != 0U) {
			++outcome->seed_blockers.moisture;
		}
		if ((blockers & PICOSYSTEM_GARDEN_SEED_BLOCKED_LIGHT) != 0U) {
			++outcome->seed_blockers.light;
		}
		if ((blockers & PICOSYSTEM_GARDEN_SEED_BLOCKED_PLANT_CAPACITY) != 0U) {
			++outcome->seed_blockers.plant_capacity;
		}
		if ((blockers & PICOSYSTEM_GARDEN_SEED_BLOCKED_NODE_CAPACITY) != 0U) {
			++outcome->seed_blockers.node_capacity;
		}
		if ((blockers & PICOSYSTEM_GARDEN_SEED_BLOCKED_SPACING) != 0U) {
			++outcome->seed_blockers.spacing;
		}
	}
	return 0;
}

static int observe_world(const struct picosystem_garden_world *world,
			 struct garden_experiment_outcome *outcome, bool sample_seed_blockers)
{
	bool species_present[PICOSYSTEM_GARDEN_SPECIES_COUNT] = {false};
	bool founder_present[GARDEN_EXPERIMENT_MAX_PLANTS] = {false};
	for (uint8_t index = 0U; index < PICOSYSTEM_GARDEN_SPECIES_COUNT; ++index) {
		outcome->species[index].final_living = 0U;
	}
	for (uint8_t index = 0U; index < outcome->founder_count; ++index) {
		outcome->founders[index].metrics.final_living = 0U;
	}

	for (uint8_t index = 0U; index < world->plant_count; ++index) {
		const struct picosystem_garden_plant *const plant = &world->plants[index];
		struct garden_experiment_lineage_tracking *tracking;
		int err = register_lineage(outcome, plant, &tracking);
		if (err != 0) {
			return err;
		}
		struct garden_experiment_group_metrics *const species =
			&outcome->species[tracking->species_id];
		struct garden_experiment_group_metrics *const founder =
			&outcome->founders[tracking->founder_index].metrics;
		if ((plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) != 0U) {
			if ((tracking->flags & GARDEN_EXPERIMENT_LINEAGE_DEAD) == 0U) {
				record_death_cause(&outcome->death_causes, plant->flags);
				record_death_cause(&species->death_causes, plant->flags);
				record_death_cause(&founder->death_causes, plant->flags);
				tracking->flags |= GARDEN_EXPERIMENT_LINEAGE_DEAD;
			}
			continue;
		}

		species_present[tracking->species_id] = true;
		founder_present[tracking->founder_index] = true;
		++species->living_plant_ticks;
		++founder->living_plant_ticks;
		++species->final_living;
		++founder->final_living;
		if (plant->generation > 0U) {
			++outcome->descendant_plant_ticks;
			++species->descendant_plant_ticks;
			++founder->descendant_plant_ticks;
		}
		if (((tracking->flags & GARDEN_EXPERIMENT_LINEAGE_ESTABLISHED) == 0U) &&
		    toy_factory_garden_evaluation_plant_is_established(world, index)) {
			tracking->flags |= GARDEN_EXPERIMENT_LINEAGE_ESTABLISHED;
			++outcome->established_offspring;
			++species->established_offspring;
			++founder->established_offspring;
		}
	}

	for (uint8_t index = 0U; index < world->seed_count; ++index) {
		const struct picosystem_garden_seed *const seed = &world->seeds[index];
		if (seed->parent_lineage_id == 0U) {
			return -ERANGE;
		}
		if (seed->parent_lineage_id > GARDEN_EXPERIMENT_MAX_TRACKED_LINEAGES) {
			return -ENOSPC;
		}
		const struct garden_experiment_lineage_tracking *const parent =
			&lineage_tracking[seed->parent_lineage_id];
		if (((parent->flags & GARDEN_EXPERIMENT_LINEAGE_SEEN) == 0U) ||
		    (parent->species_id != seed->species_id) ||
		    (parent->founder_index >= outcome->founder_count)) {
			return -EIO;
		}
		species_present[parent->species_id] = true;
		founder_present[parent->founder_index] = true;
	}

	for (uint8_t index = 0U; index < PICOSYSTEM_GARDEN_SPECIES_COUNT; ++index) {
		struct garden_experiment_group_metrics *const metrics = &outcome->species[index];
		if ((metrics->initial_founders > 0U) && !species_present[index] &&
		    (metrics->extinction_tick == 0U)) {
			metrics->extinction_tick = world->logic_tick_count;
		}
	}
	for (uint8_t index = 0U; index < outcome->founder_count; ++index) {
		struct garden_experiment_group_metrics *const metrics =
			&outcome->founders[index].metrics;
		if (!founder_present[index] && (metrics->extinction_tick == 0U)) {
			metrics->extinction_tick = world->logic_tick_count;
		}
	}
	if ((picosystem_garden_world_living_plant_count(world) == 0U) &&
	    (world->seed_count == 0U) && (outcome->extinction_tick == 0U)) {
		outcome->extinction_tick = world->logic_tick_count;
	}
	return sample_seed_blockers ? record_seed_blockers(world, outcome) : 0;
}

static bool telemetry_totals_are_valid(const struct picosystem_garden_agent_telemetry *telemetry)
{
	const uint64_t action_total =
		(uint64_t)telemetry->extend_count + telemetry->wait_count + telemetry->finish_count;
	const uint64_t tissue_total =
		(uint64_t)telemetry->root_decision_count + telemetry->shoot_decision_count;
	const uint64_t extension_total =
		(uint64_t)telemetry->root_extend_count + telemetry->shoot_extend_count;
	return (action_total == telemetry->decision_count) &&
	       (tissue_total == telemetry->decision_count) &&
	       (extension_total == telemetry->extend_count);
}

static bool group_metrics_are_valid(const struct garden_experiment_group_metrics *metrics,
				    uint32_t tick_count)
{
	return (metrics->descendant_plant_ticks <= metrics->living_plant_ticks) &&
	       ((metrics->extinction_tick == 0U) || (metrics->final_living == 0U)) &&
	       ((metrics->extinction_tick == 0U) || (metrics->extinction_tick <= tick_count));
}

static bool outcome_totals_are_valid(const struct garden_experiment_outcome *outcome,
				     uint32_t tick_count)
{
	uint64_t species_living = 0U;
	uint64_t species_descendants = 0U;
	uint32_t species_deaths = 0U;
	uint32_t species_established = 0U;
	uint32_t species_final_living = 0U;
	uint32_t species_founders = 0U;
	uint16_t species_maximum_generation = 0U;
	for (uint8_t index = 0U; index < PICOSYSTEM_GARDEN_SPECIES_COUNT; ++index) {
		const struct garden_experiment_group_metrics *const metrics =
			&outcome->species[index];
		if (!group_metrics_are_valid(metrics, tick_count)) {
			return false;
		}
		species_living += metrics->living_plant_ticks;
		species_descendants += metrics->descendant_plant_ticks;
		species_deaths += death_cause_total(&metrics->death_causes);
		species_established += metrics->established_offspring;
		species_final_living += metrics->final_living;
		species_founders += metrics->initial_founders;
		if (metrics->maximum_generation > species_maximum_generation) {
			species_maximum_generation = metrics->maximum_generation;
		}
	}

	uint64_t founder_living = 0U;
	uint64_t founder_descendants = 0U;
	uint32_t founder_deaths = 0U;
	uint32_t founder_established = 0U;
	uint32_t founder_final_living = 0U;
	uint16_t founder_maximum_generation = 0U;
	for (uint8_t index = 0U; index < outcome->founder_count; ++index) {
		const struct garden_experiment_founder_metrics *const founder =
			&outcome->founders[index];
		if ((founder->lineage_id == 0U) || (founder->metrics.initial_founders != 1U) ||
		    (founder->species_id >= PICOSYSTEM_GARDEN_SPECIES_COUNT) ||
		    !group_metrics_are_valid(&founder->metrics, tick_count)) {
			return false;
		}
		founder_living += founder->metrics.living_plant_ticks;
		founder_descendants += founder->metrics.descendant_plant_ticks;
		founder_deaths += death_cause_total(&founder->metrics.death_causes);
		founder_established += founder->metrics.established_offspring;
		founder_final_living += founder->metrics.final_living;
		if (founder->metrics.maximum_generation > founder_maximum_generation) {
			founder_maximum_generation = founder->metrics.maximum_generation;
		}
	}

	const struct garden_experiment_seed_blockers *const blockers = &outcome->seed_blockers;
	const uint64_t blocker_reasons = (uint64_t)blockers->moisture + blockers->light +
					 blockers->plant_capacity + blockers->node_capacity +
					 blockers->spacing;
	const bool globally_extinct =
		(outcome->final_living_count == 0U) && (outcome->final_seed_count == 0U);
	return telemetry_totals_are_valid(&outcome->agent) &&
	       (outcome->founder_count <= GARDEN_EXPERIMENT_MAX_PLANTS) &&
	       (outcome->lineage_count <= GARDEN_EXPERIMENT_MAX_TRACKED_LINEAGES) &&
	       (outcome->lineage_count ==
		(uint32_t)outcome->founder_count + outcome->germination_count) &&
	       (outcome->established_offspring <= outcome->germination_count) &&
	       (death_cause_total(&outcome->death_causes) == outcome->death_count) &&
	       (species_deaths == outcome->death_count) &&
	       (founder_deaths == outcome->death_count) &&
	       (species_living == outcome->living_plant_ticks) &&
	       (founder_living == outcome->living_plant_ticks) &&
	       (species_descendants == outcome->descendant_plant_ticks) &&
	       (founder_descendants == outcome->descendant_plant_ticks) &&
	       (species_established == outcome->established_offspring) &&
	       (founder_established == outcome->established_offspring) &&
	       (species_final_living == outcome->final_living_count) &&
	       (founder_final_living == outcome->final_living_count) &&
	       (species_founders == outcome->founder_count) &&
	       (species_maximum_generation == outcome->maximum_generation) &&
	       (founder_maximum_generation == outcome->maximum_generation) &&
	       (blockers->samples == blockers->dormant + blockers->ready + blockers->blocked) &&
	       (blocker_reasons >= blockers->blocked) &&
	       (blockers->moisture <= blockers->blocked) &&
	       (blockers->light <= blockers->blocked) &&
	       (blockers->plant_capacity <= blockers->blocked) &&
	       (blockers->node_capacity <= blockers->blocked) &&
	       (blockers->spacing <= blockers->blocked) &&
	       ((outcome->extinction_tick == 0U) != globally_extinct) &&
	       ((outcome->extinction_tick == 0U) || (outcome->extinction_tick <= tick_count));
}

static int observe_trial_tick(const struct picosystem_garden_world *world, bool ecology_sample,
			      void *context)
{
	struct garden_experiment_outcome *const outcome = context;
	int err = observe_world(world, outcome, ecology_sample);
	if (err != 0) {
		return err;
	}

	const uint8_t living_count = picosystem_garden_world_living_plant_count(world);
	outcome->living_plant_ticks += living_count;
	if (living_count > outcome->maximum_living_count) {
		outcome->maximum_living_count = living_count;
	}
	if (world->node_count > outcome->maximum_node_count) {
		outcome->maximum_node_count = world->node_count;
	}
	if (ecology_sample) {
		uint32_t energy;
		uint32_t water;
		uint32_t stress;
		current_resource_totals(world, &energy, &water, &stress, &outcome->maximum_stress);
		outcome->sampled_energy += energy;
		outcome->sampled_water += water;
		outcome->sampled_stress += stress;
		++outcome->ecology_samples;
	}
	return 0;
}

static int run_trial(const struct toy_factory_garden_evaluation_scenario *scenario,
		     const struct picosystem_garden_agent_policy *policy, uint32_t random_seed,
		     uint32_t tick_count, struct garden_experiment_outcome *outcome)
{
	if ((scenario == NULL) || (policy == NULL) || (outcome == NULL)) {
		return -EINVAL;
	}
	struct picosystem_garden_world world;
	int err = toy_factory_garden_evaluation_reset(&world, scenario, random_seed);
	if (err != 0) {
		return err;
	}

	*outcome = (struct garden_experiment_outcome){
		.random_seed = random_seed,
		.maximum_node_count = world.node_count,
		.maximum_living_count = picosystem_garden_world_living_plant_count(&world),
	};
	err = initialize_lineage_tracking(&world, outcome);
	if ((err != 0) || (world.plant_count != scenario->plant_count)) {
		return (err != 0) ? err : -EIO;
	}
	err = toy_factory_garden_evaluation_advance(&world, scenario, policy, tick_count,
						    observe_trial_tick, outcome);
	if (err != 0) {
		return err;
	}

	current_resource_totals(&world, &outcome->final_energy, &outcome->final_water,
				&outcome->final_stress, &outcome->maximum_stress);
	outcome->agent = world.agent_telemetry;
	outcome->state_hash = picosystem_garden_world_hash(&world);
	outcome->bloom_count = world.bloom_count;
	outcome->death_count = world.death_count;
	outcome->reclaimed_plant_count = world.reclaimed_plant_count;
	outcome->reclaimed_node_count = world.reclaimed_node_count;
	outcome->seed_creation_count = world.seed_creation_count;
	outcome->germination_count = world.germination_count;
	outcome->seed_expiration_count = world.seed_expiration_count;
	outcome->mutation_count = world.mutation_count;
	outcome->final_node_count = world.node_count;
	outcome->maximum_generation = world.maximum_generation;
	outcome->lineage_count = world.lineage_sequence;
	outcome->moisture_total = world.moisture_total;
	outcome->final_plant_count = world.plant_count;
	outcome->final_living_count = picosystem_garden_world_living_plant_count(&world);
	outcome->final_dead_count = picosystem_garden_world_dead_plant_count(&world);
	outcome->final_seed_count = world.seed_count;
	outcome->nonzero_memory_count = nonzero_memory_count(&world);
	return outcome_totals_are_valid(outcome, tick_count) ? 0 : -EIO;
}

static struct garden_experiment_summary
summarize_outcomes(const struct garden_experiment_outcome *values, uint32_t count)
{
	struct garden_experiment_summary summary = {
		.minimum_final_living = values[0].final_living_count,
		.maximum_final_living = values[0].final_living_count,
		.minimum_final_nodes = values[0].final_node_count,
		.maximum_final_nodes = values[0].final_node_count,
	};
	for (uint32_t index = 0U; index < count; ++index) {
		const struct garden_experiment_outcome *const outcome = &values[index];
		summary.living_plant_ticks += outcome->living_plant_ticks;
		summary.descendant_plant_ticks += outcome->descendant_plant_ticks;
		summary.sampled_energy += outcome->sampled_energy;
		summary.sampled_water += outcome->sampled_water;
		summary.sampled_stress += outcome->sampled_stress;
		summary.agent_decisions += outcome->agent.decision_count;
		summary.agent_extend += outcome->agent.extend_count;
		summary.agent_wait += outcome->agent.wait_count;
		summary.agent_finish += outcome->agent.finish_count;
		summary.agent_root += outcome->agent.root_decision_count;
		summary.agent_shoot += outcome->agent.shoot_decision_count;
		summary.agent_root_extend += outcome->agent.root_extend_count;
		summary.agent_shoot_extend += outcome->agent.shoot_extend_count;
		summary.blooms += outcome->bloom_count;
		summary.deaths += outcome->death_count;
		summary.seeds_created += outcome->seed_creation_count;
		summary.germinations += outcome->germination_count;
		summary.seeds_expired += outcome->seed_expiration_count;
		summary.mutations += outcome->mutation_count;
		summary.established_offspring += outcome->established_offspring;
		summary.death_energy += outcome->death_causes.energy;
		summary.death_water += outcome->death_causes.water;
		summary.death_combined += outcome->death_causes.combined;
		summary.death_other += outcome->death_causes.other;
		summary.seed_samples += outcome->seed_blockers.samples;
		summary.seed_dormant += outcome->seed_blockers.dormant;
		summary.seed_ready += outcome->seed_blockers.ready;
		summary.seed_blocked += outcome->seed_blockers.blocked;
		summary.seed_blocked_moisture += outcome->seed_blockers.moisture;
		summary.seed_blocked_light += outcome->seed_blockers.light;
		summary.seed_blocked_plant_capacity += outcome->seed_blockers.plant_capacity;
		summary.seed_blocked_node_capacity += outcome->seed_blockers.node_capacity;
		summary.seed_blocked_spacing += outcome->seed_blockers.spacing;
		if (outcome->extinction_tick != 0U) {
			++summary.extinction_count;
		}
		if (outcome->final_living_count < summary.minimum_final_living) {
			summary.minimum_final_living = outcome->final_living_count;
		}
		if (outcome->final_living_count > summary.maximum_final_living) {
			summary.maximum_final_living = outcome->final_living_count;
		}
		if (outcome->final_node_count < summary.minimum_final_nodes) {
			summary.minimum_final_nodes = outcome->final_node_count;
		}
		if (outcome->final_node_count > summary.maximum_final_nodes) {
			summary.maximum_final_nodes = outcome->final_node_count;
		}
		if (outcome->maximum_generation > summary.maximum_generation) {
			summary.maximum_generation = outcome->maximum_generation;
		}
		if (outcome->maximum_stress > summary.maximum_stress) {
			summary.maximum_stress = outcome->maximum_stress;
		}
	}
	return summary;
}

static void print_summary(const struct garden_experiment_summary *summary)
{
	printf("{\"living_plant_ticks\":%" PRIu64 ",\"descendant_plant_ticks\":%" PRIu64
	       ",\"sampled_energy\":%" PRIu64 ",\"sampled_water\":%" PRIu64
	       ",\"sampled_stress\":%" PRIu64 ",\"blooms\":%" PRIu64 ",\"deaths\":%" PRIu64
	       ",\"seeds_created\":%" PRIu64 ",\"germinations\":%" PRIu64
	       ",\"seeds_expired\":%" PRIu64 ",\"mutations\":%" PRIu64
	       ",\"established_offspring\":%" PRIu64 ",\"extinctions\":%" PRIu32
	       ",\"death_causes\":{\"energy\":%" PRIu64 ",\"water\":%" PRIu64
	       ",\"combined\":%" PRIu64 ",\"other\":%" PRIu64 "}"
	       ",\"seed_germination_blockers\":{\"samples\":%" PRIu64 ",\"dormant\":%" PRIu64
	       ",\"ready\":%" PRIu64 ",\"blocked\":%" PRIu64 ",\"moisture\":%" PRIu64
	       ",\"light\":%" PRIu64 ",\"plant_capacity\":%" PRIu64 ",\"node_capacity\":%" PRIu64
	       ",\"spacing\":%" PRIu64 "}"
	       ",\"agent\":{\"decisions\":%" PRIu64 ",\"extend\":%" PRIu64 ",\"wait\":%" PRIu64
	       ",\"finish\":%" PRIu64 ",\"root\":%" PRIu64 ",\"shoot\":%" PRIu64
	       ",\"root_extend\":%" PRIu64 ",\"shoot_extend\":%" PRIu64
	       "},\"final_living_range\":[%" PRIu32 ",%" PRIu32 "],\"final_node_range\":[%" PRIu32
	       ",%" PRIu32 "],\"maximum_generation\":%" PRIu32 ",\"maximum_stress\":%" PRIu32 "}",
	       summary->living_plant_ticks, summary->descendant_plant_ticks,
	       summary->sampled_energy, summary->sampled_water, summary->sampled_stress,
	       summary->blooms, summary->deaths, summary->seeds_created, summary->germinations,
	       summary->seeds_expired, summary->mutations, summary->established_offspring,
	       summary->extinction_count, summary->death_energy, summary->death_water,
	       summary->death_combined, summary->death_other, summary->seed_samples,
	       summary->seed_dormant, summary->seed_ready, summary->seed_blocked,
	       summary->seed_blocked_moisture, summary->seed_blocked_light,
	       summary->seed_blocked_plant_capacity, summary->seed_blocked_node_capacity,
	       summary->seed_blocked_spacing, summary->agent_decisions, summary->agent_extend,
	       summary->agent_wait, summary->agent_finish, summary->agent_root,
	       summary->agent_shoot, summary->agent_root_extend, summary->agent_shoot_extend,
	       summary->minimum_final_living, summary->maximum_final_living,
	       summary->minimum_final_nodes, summary->maximum_final_nodes,
	       summary->maximum_generation, summary->maximum_stress);
}

static void print_nullable_tick(uint32_t tick)
{
	if (tick == 0U) {
		printf("null");
	} else {
		printf("%" PRIu32, tick);
	}
}

static void print_death_causes(const struct garden_experiment_death_causes *causes)
{
	printf("{\"energy\":%" PRIu32 ",\"water\":%" PRIu32 ",\"combined\":%" PRIu32
	       ",\"other\":%" PRIu32 "}",
	       causes->energy, causes->water, causes->combined, causes->other);
}

static void print_seed_blockers(const struct garden_experiment_seed_blockers *blockers)
{
	printf("{\"samples\":%" PRIu32 ",\"dormant\":%" PRIu32 ",\"ready\":%" PRIu32
	       ",\"blocked\":%" PRIu32 ",\"moisture\":%" PRIu32 ",\"light\":%" PRIu32
	       ",\"plant_capacity\":%" PRIu32 ",\"node_capacity\":%" PRIu32 ",\"spacing\":%" PRIu32
	       "}",
	       blockers->samples, blockers->dormant, blockers->ready, blockers->blocked,
	       blockers->moisture, blockers->light, blockers->plant_capacity,
	       blockers->node_capacity, blockers->spacing);
}

static void print_group_metric_fields(const struct garden_experiment_group_metrics *metrics)
{
	printf("\"initial_founders\":%u,\"living_plant_ticks\":%" PRIu64
	       ",\"descendant_plant_ticks\":%" PRIu64 ",\"established_offspring\":%" PRIu32
	       ",\"final_living\":%u,\"maximum_generation\":%u,\"extinction_tick\":",
	       metrics->initial_founders, metrics->living_plant_ticks,
	       metrics->descendant_plant_ticks, metrics->established_offspring,
	       metrics->final_living, metrics->maximum_generation);
	print_nullable_tick(metrics->extinction_tick);
	printf(",\"death_causes\":");
	print_death_causes(&metrics->death_causes);
}

static void print_species_metrics(const struct garden_experiment_outcome *outcome)
{
	putchar('[');
	for (uint8_t index = 0U; index < PICOSYSTEM_GARDEN_SPECIES_COUNT; ++index) {
		if (index != 0U) {
			putchar(',');
		}
		printf("{\"id\":%u,\"name\":\"%s\",", index,
		       picosystem_garden_species_name((enum picosystem_garden_species_id)index));
		print_group_metric_fields(&outcome->species[index]);
		putchar('}');
	}
	putchar(']');
}

static void print_founder_metrics(const struct garden_experiment_outcome *outcome)
{
	putchar('[');
	for (uint8_t index = 0U; index < outcome->founder_count; ++index) {
		const struct garden_experiment_founder_metrics *const founder =
			&outcome->founders[index];
		if (index != 0U) {
			putchar(',');
		}
		printf("{\"index\":%u,\"lineage_id\":%" PRIu32
		       ",\"species_id\":%u,\"species\":\"%s\",\"column\":%u,",
		       index, founder->lineage_id, founder->species_id,
		       picosystem_garden_species_name(
			       (enum picosystem_garden_species_id)founder->species_id),
		       founder->column);
		print_group_metric_fields(&founder->metrics);
		putchar('}');
	}
	putchar(']');
}

static void print_outcome(const struct garden_experiment_outcome *outcome)
{
	printf("{\"seed\":\"%08" PRIx32 "\",\"hash\":\"%08" PRIx32
	       "\",\"living_plant_ticks\":%" PRIu64 ",\"descendant_plant_ticks\":%" PRIu64
	       ",\"resource_samples\":%" PRIu32 ",\"sampled_energy\":%" PRIu64
	       ",\"sampled_water\":%" PRIu64 ",\"sampled_stress\":%" PRIu64
	       ",\"plants\":%u,\"living\":%u,"
	       "\"dead\":%u,\"seed_bank\":%u,\"nodes\":%u,\"maximum_nodes\":%u,\"blooms\":%" PRIu32
	       ",\"deaths\":%" PRIu32 ",\"reclaimed_plants\":%" PRIu32
	       ",\"reclaimed_nodes\":%" PRIu32 ",\"seeds_created\":%" PRIu32
	       ",\"germinations\":%" PRIu32 ",\"seeds_expired\":%" PRIu32 ",\"mutations\":%" PRIu32
	       ",\"established_offspring\":%" PRIu32 ",\"maximum_generation\":%u,"
	       "\"lineages\":%" PRIu32 ",\"moisture\":%u,\"energy\":%" PRIu32 ",\"water\":%" PRIu32
	       ",\"stress\":%" PRIu32 ",\"maximum_stress\":%u,\"nonzero_memory_plants\":%u,"
	       "\"agent\":{\"decisions\":%" PRIu32 ",\"extend\":%" PRIu32 ",\"wait\":%" PRIu32
	       ",\"finish\":%" PRIu32 ",\"root\":%" PRIu32 ",\"shoot\":%" PRIu32
	       ",\"root_extend\":%" PRIu32 ",\"shoot_extend\":%" PRIu32 "}",
	       outcome->random_seed, outcome->state_hash, outcome->living_plant_ticks,
	       outcome->descendant_plant_ticks, outcome->ecology_samples, outcome->sampled_energy,
	       outcome->sampled_water, outcome->sampled_stress, outcome->final_plant_count,
	       outcome->final_living_count, outcome->final_dead_count, outcome->final_seed_count,
	       outcome->final_node_count, outcome->maximum_node_count, outcome->bloom_count,
	       outcome->death_count, outcome->reclaimed_plant_count, outcome->reclaimed_node_count,
	       outcome->seed_creation_count, outcome->germination_count,
	       outcome->seed_expiration_count, outcome->mutation_count,
	       outcome->established_offspring, outcome->maximum_generation, outcome->lineage_count,
	       outcome->moisture_total, outcome->final_energy, outcome->final_water,
	       outcome->final_stress, outcome->maximum_stress, outcome->nonzero_memory_count,
	       outcome->agent.decision_count, outcome->agent.extend_count,
	       outcome->agent.wait_count, outcome->agent.finish_count,
	       outcome->agent.root_decision_count, outcome->agent.shoot_decision_count,
	       outcome->agent.root_extend_count, outcome->agent.shoot_extend_count);
	printf(",\"extinction_tick\":");
	print_nullable_tick(outcome->extinction_tick);
	printf(",\"death_causes\":");
	print_death_causes(&outcome->death_causes);
	printf(",\"seed_germination_blockers\":");
	print_seed_blockers(&outcome->seed_blockers);
	printf(",\"species\":");
	print_species_metrics(outcome);
	printf(",\"founders\":");
	print_founder_metrics(outcome);
	putchar('}');
}

static void print_report(uint32_t trial_count, uint32_t tick_count, uint32_t base_seed,
			 bool has_candidate_model, uint32_t candidate_fingerprint)
{
	printf("{\n  \"schema_version\": %u,\n", GARDEN_EXPERIMENT_SCHEMA_VERSION);
	printf("  \"trial_count\": %" PRIu32 ",\n", trial_count);
	printf("  \"tick_count\": %" PRIu32 ",\n", tick_count);
	printf("  \"base_seed\": \"%08" PRIx32 "\",\n", base_seed);
	if (has_candidate_model) {
		printf("  \"candidate_model_crc32\": \"%08" PRIx32 "\",\n", candidate_fingerprint);
	}
	printf("  \"integral_units\": {\"living\": \"plant-ticks\", "
	       "\"descendants\": \"plant-ticks\", \"resources\": \"ecology-samples\"},\n");
	printf("  \"tracked_lineage_capacity\": %u,\n", GARDEN_EXPERIMENT_MAX_TRACKED_LINEAGES);
	printf("  \"establishment\": {\"minimum_age_ecology_ticks\": %u, "
	       "\"requires_active_leaf\": true, \"requires_zero_stress\": true},\n",
	       GARDEN_EXPERIMENT_ESTABLISHED_MINIMUM_AGE);
	printf("  \"scenarios\": [\n");
	for (size_t scenario_index = 0U;
	     scenario_index < TOY_FACTORY_ARRAY_SIZE(toy_factory_garden_evaluation_scenarios);
	     ++scenario_index) {
		const struct toy_factory_garden_evaluation_scenario *const scenario =
			&toy_factory_garden_evaluation_scenarios[scenario_index];
		printf("    {\"name\":\"%s\",\"plants\":%u,\"initial_water_per_plant\":%u,"
		       "\"irrigation_pattern\":\"%s\","
		       "\"irrigation_period_ticks\":%" PRIu32
		       ",\"irrigation_water_per_column\":%u,\"policies\":[\n",
		       scenario->name, scenario->plant_count, scenario->initial_water,
		       (scenario->irrigation_period_ticks == 0U) ? "none" : "whole-plot",
		       scenario->irrigation_period_ticks, scenario->irrigation_water);
		for (size_t policy_index = 0U; policy_index < TOY_FACTORY_ARRAY_SIZE(policies);
		     ++policy_index) {
			const struct garden_experiment_summary summary = summarize_outcomes(
				outcomes[scenario_index][policy_index], trial_count);
			printf("      {\"name\":\"%s\",\"totals\":", policies[policy_index].name);
			print_summary(&summary);
			printf(",\"trials\":[");
			for (uint32_t trial = 0U; trial < trial_count; ++trial) {
				if (trial != 0U) {
					putchar(',');
				}
				print_outcome(&outcomes[scenario_index][policy_index][trial]);
			}
			printf("]}%s\n",
			       (policy_index + 1U < TOY_FACTORY_ARRAY_SIZE(policies)) ? "," : "");
		}
		printf("    ]}%s\n",
		       (scenario_index + 1U <
			TOY_FACTORY_ARRAY_SIZE(toy_factory_garden_evaluation_scenarios))
			       ? ","
			       : "");
	}
	printf("  ]\n}\n");
}

int main(int argc, char **argv)
{
	uint32_t trial_count;
	uint32_t tick_count;
	uint32_t base_seed;
	const char *model_path;
	const int option_result =
		parse_options(argc, argv, &trial_count, &tick_count, &base_seed, &model_path);
	if (option_result > 0) {
		return 0;
	}
	if (option_result < 0) {
		print_usage(stderr, argv[0]);
		return 2;
	}
	uint32_t candidate_fingerprint = 0U;
	if (model_path != NULL) {
		int err = toy_factory_garden_model_read(model_path, &candidate_model,
							&candidate_fingerprint);
		if (err == 0) {
			err = picosystem_garden_neural_policy_init(&candidate_model,
								   &candidate_policy);
		}
		if (err != 0) {
			fprintf(stderr, "failed to load candidate model '%s' (%d)\n", model_path,
				err);
			return 1;
		}
		selected_neural_policy = &candidate_policy;
		policies[2].name = "neural-candidate";
	}

	for (size_t scenario_index = 0U;
	     scenario_index < TOY_FACTORY_ARRAY_SIZE(toy_factory_garden_evaluation_scenarios);
	     ++scenario_index) {
		for (size_t policy_index = 0U; policy_index < TOY_FACTORY_ARRAY_SIZE(policies);
		     ++policy_index) {
			const struct picosystem_garden_agent_policy *const policy =
				policies[policy_index].get_policy();
			for (uint32_t trial = 0U; trial < trial_count; ++trial) {
				const uint32_t random_seed =
					toy_factory_garden_evaluation_trial_seed(base_seed, trial);
				const int err = run_trial(
					&toy_factory_garden_evaluation_scenarios[scenario_index],
					policy, random_seed, tick_count,
					&outcomes[scenario_index][policy_index][trial]);
				if (err != 0) {
					fprintf(stderr,
						"%s/%s trial %" PRIu32 " failed at seed %08" PRIx32
						" (%d)\n",
						toy_factory_garden_evaluation_scenarios
							[scenario_index]
								.name,
						policies[policy_index].name, trial, random_seed,
						err);
					return 1;
				}
			}
		}
	}

	print_report(trial_count, tick_count, base_seed, model_path != NULL, candidate_fingerprint);
	return 0;
}
