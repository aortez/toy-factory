/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "garden_agent_neural.h"
#include "garden_evaluation.h"
#include "garden_model_file.h"
#include "garden_model_mutation.h"
#include "garden_world.h"
#include "portable_util.h"

#define GARDEN_TRAIN_SCHEMA_VERSION      1U
#define GARDEN_TRAIN_DEFAULT_GENERATIONS 8U
#define GARDEN_TRAIN_DEFAULT_POPULATION  16U
#define GARDEN_TRAIN_DEFAULT_TRIALS      2U
#define GARDEN_TRAIN_DEFAULT_TICKS       7680U
#define GARDEN_TRAIN_DEFAULT_MUTATIONS   32U
#define GARDEN_TRAIN_DEFAULT_SEED        UINT32_C(0x74726169)
#define GARDEN_TRAIN_MAX_GENERATIONS     256U
#define GARDEN_TRAIN_MAX_POPULATION      512U
#define GARDEN_TRAIN_MAX_TRIALS          64U
#define GARDEN_TRAIN_MAX_TICKS           100000U
#define GARDEN_TRAIN_MAX_MUTATIONS       4096U
#define GARDEN_TRAIN_DEFAULT_OUTPUT      "artifacts/garden-champion.tgm"
#define GARDEN_TRAIN_DEFAULT_C_OUTPUT    "artifacts/garden-champion.c"
#define GARDEN_TRAIN_DEFAULT_SYMBOL      "toy_factory_garden_champion_model"
#define GARDEN_TRAIN_ESTABLISHED_BYTES                                                             \
	((TOY_FACTORY_GARDEN_EVALUATION_MAX_TRACKED_LINEAGES + 8U) / 8U)

struct garden_train_options {
	const char *input_path;
	const char *output_path;
	const char *c_output_path;
	const char *symbol;
	uint32_t generation_count;
	uint32_t population_count;
	uint32_t trial_count;
	uint32_t tick_count;
	uint32_t mutation_count;
	uint32_t base_seed;
};

struct garden_train_fitness {
	uint64_t living_plant_ticks;
	uint64_t descendant_plant_ticks;
	uint32_t final_living;
	uint32_t final_seeds;
	uint32_t established_offspring;
	uint32_t maximum_generation;
	uint32_t extinctions;
	uint32_t deaths;
	uint32_t seeds_created;
	uint32_t germinations;
	uint32_t state_digest;
};

struct garden_train_observer {
	struct garden_train_fitness *fitness;
	uint8_t established[GARDEN_TRAIN_ESTABLISHED_BYTES];
};

struct garden_train_generation {
	struct garden_train_fitness fitness;
	uint32_t fingerprint;
	bool accepted;
};

static void print_usage(FILE *stream, const char *program)
{
	fprintf(stream,
		"Usage: %s [OPTIONS]\n"
		"  --generations 0-%u   Evolutionary generations (default %u)\n"
		"  --population 2-%u    Candidates per generation, including elite (default %u)\n"
		"  --trials 1-%u        Matched trials per scenario (default %u)\n"
		"  --ticks 1-%u         Authoritative ticks per trial (default %u)\n"
		"  --mutations 1-%u     Parameter mutations per offspring (default %u)\n"
		"  --seed UINT32        Search and world batch seed\n"
		"  --input PATH         Start from a canonical model file\n"
		"  --output PATH        Write canonical champion model\n"
		"  --c-output PATH      Write linkable champion C definition\n"
		"  --symbol IDENTIFIER  Symbol used by the generated C definition\n",
		program, GARDEN_TRAIN_MAX_GENERATIONS, GARDEN_TRAIN_DEFAULT_GENERATIONS,
		GARDEN_TRAIN_MAX_POPULATION, GARDEN_TRAIN_DEFAULT_POPULATION,
		GARDEN_TRAIN_MAX_TRIALS, GARDEN_TRAIN_DEFAULT_TRIALS, GARDEN_TRAIN_MAX_TICKS,
		GARDEN_TRAIN_DEFAULT_TICKS, GARDEN_TRAIN_MAX_MUTATIONS,
		GARDEN_TRAIN_DEFAULT_MUTATIONS);
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

static int parse_options(int argc, char **argv, struct garden_train_options *options)
{
	if (options == NULL) {
		return -EINVAL;
	}
	*options = (struct garden_train_options){
		.output_path = GARDEN_TRAIN_DEFAULT_OUTPUT,
		.c_output_path = GARDEN_TRAIN_DEFAULT_C_OUTPUT,
		.symbol = GARDEN_TRAIN_DEFAULT_SYMBOL,
		.generation_count = GARDEN_TRAIN_DEFAULT_GENERATIONS,
		.population_count = GARDEN_TRAIN_DEFAULT_POPULATION,
		.trial_count = GARDEN_TRAIN_DEFAULT_TRIALS,
		.tick_count = GARDEN_TRAIN_DEFAULT_TICKS,
		.mutation_count = GARDEN_TRAIN_DEFAULT_MUTATIONS,
		.base_seed = GARDEN_TRAIN_DEFAULT_SEED,
	};
	for (int index = 1; index < argc; ++index) {
		const char *const option = argv[index];
		if (strcmp(option, "--help") == 0) {
			print_usage(stdout, argv[0]);
			return 1;
		}
		if ((index + 1) >= argc) {
			fprintf(stderr, "%s requires another argument\n", option);
			return -EINVAL;
		}
		const char *const value = argv[++index];
		int err = 0;
		if (strcmp(option, "--generations") == 0) {
			err = parse_u32(value, 10, 0U, GARDEN_TRAIN_MAX_GENERATIONS,
					&options->generation_count);
		} else if (strcmp(option, "--population") == 0) {
			err = parse_u32(value, 10, 2U, GARDEN_TRAIN_MAX_POPULATION,
					&options->population_count);
		} else if (strcmp(option, "--trials") == 0) {
			err = parse_u32(value, 10, 1U, GARDEN_TRAIN_MAX_TRIALS,
					&options->trial_count);
		} else if (strcmp(option, "--ticks") == 0) {
			err = parse_u32(value, 10, 1U, GARDEN_TRAIN_MAX_TICKS,
					&options->tick_count);
		} else if (strcmp(option, "--mutations") == 0) {
			err = parse_u32(value, 10, 1U, GARDEN_TRAIN_MAX_MUTATIONS,
					&options->mutation_count);
		} else if (strcmp(option, "--seed") == 0) {
			err = parse_u32(value, 0, 1U, UINT32_MAX, &options->base_seed);
		} else if (strcmp(option, "--input") == 0) {
			options->input_path = value;
		} else if (strcmp(option, "--output") == 0) {
			options->output_path = value;
		} else if (strcmp(option, "--c-output") == 0) {
			options->c_output_path = value;
		} else if (strcmp(option, "--symbol") == 0) {
			options->symbol = value;
		} else {
			fprintf(stderr, "unknown option '%s'\n", option);
			return -EINVAL;
		}
		if (err != 0) {
			fprintf(stderr, "invalid value '%s' for %s\n", value, option);
			return err;
		}
	}
	if ((*options->output_path == '\0') || (*options->c_output_path == '\0') ||
	    (*options->symbol == '\0') ||
	    ((options->input_path != NULL) && (*options->input_path == '\0'))) {
		return -EINVAL;
	}
	return 0;
}

static int mark_established(struct garden_train_observer *observer, uint32_t lineage_id)
{
	if ((lineage_id == 0U) ||
	    (lineage_id > TOY_FACTORY_GARDEN_EVALUATION_MAX_TRACKED_LINEAGES)) {
		return -ENOSPC;
	}
	const size_t byte_index = lineage_id / 8U;
	const uint8_t mask = (uint8_t)(1U << (lineage_id % 8U));
	if ((observer->established[byte_index] & mask) == 0U) {
		observer->established[byte_index] |= mask;
		++observer->fitness->established_offspring;
	}
	return 0;
}

static int observe_tick(const struct picosystem_garden_world *world, bool ecology_sample,
			void *context)
{
	(void)ecology_sample;
	struct garden_train_observer *const observer = context;
	const uint8_t living = picosystem_garden_world_living_plant_count(world);
	observer->fitness->living_plant_ticks += living;
	for (uint8_t index = 0U; index < world->plant_count; ++index) {
		const struct picosystem_garden_plant *const plant = &world->plants[index];
		if ((plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) != 0U) {
			continue;
		}
		if (plant->generation > 0U) {
			++observer->fitness->descendant_plant_ticks;
		}
		if (plant->generation > observer->fitness->maximum_generation) {
			observer->fitness->maximum_generation = plant->generation;
		}
		if (toy_factory_garden_evaluation_plant_is_established(world, index)) {
			const int err = mark_established(observer, plant->lineage_id);
			if (err != 0) {
				return err;
			}
		}
	}
	return 0;
}

static uint32_t mix_digest(uint32_t digest, uint32_t value)
{
	digest ^= value + UINT32_C(0x9e3779b9) + (digest << 6U) + (digest >> 2U);
	return digest;
}

static int evaluate_model(const struct picosystem_garden_neural_model *model,
			  const struct garden_train_options *options,
			  struct garden_train_fitness *fitness)
{
	struct picosystem_garden_agent_policy policy;
	int err = picosystem_garden_neural_policy_init(model, &policy);
	if (err != 0) {
		return err;
	}
	*fitness = (struct garden_train_fitness){0};
	for (size_t scenario_index = 0U;
	     scenario_index < TOY_FACTORY_ARRAY_SIZE(toy_factory_garden_rainfed_scenarios);
	     ++scenario_index) {
		const struct toy_factory_garden_evaluation_scenario *const scenario =
			&toy_factory_garden_rainfed_scenarios[scenario_index];
		for (uint32_t trial = 0U; trial < options->trial_count; ++trial) {
			const uint32_t random_seed =
				toy_factory_garden_evaluation_trial_seed(options->base_seed, trial);
			struct picosystem_garden_world world;
			err = toy_factory_garden_evaluation_reset(&world, scenario, random_seed);
			if (err != 0) {
				return err;
			}
			struct garden_train_observer observer = {.fitness = fitness};
			err = toy_factory_garden_evaluation_advance(&world, scenario, &policy,
								    options->tick_count,
								    observe_tick, &observer);
			if (err != 0) {
				return err;
			}
			if (world.auto_gardener_enabled || (world.auto_action_count != 0U) ||
			    (world.manual_action_count != 0U)) {
				return -EINVAL;
			}
			const uint8_t living = picosystem_garden_world_living_plant_count(&world);
			fitness->final_living += living;
			fitness->final_seeds += world.seed_count;
			if ((living == 0U) && (world.seed_count == 0U)) {
				++fitness->extinctions;
			}
			fitness->deaths += world.death_count;
			fitness->seeds_created += world.seed_creation_count;
			fitness->germinations += world.germination_count;
			fitness->state_digest = mix_digest(fitness->state_digest,
							   picosystem_garden_world_hash(&world));
		}
	}
	return 0;
}

static bool fitness_is_better(const struct garden_train_fitness *candidate,
			      const struct garden_train_fitness *champion)
{
	if (candidate->extinctions != champion->extinctions) {
		return candidate->extinctions < champion->extinctions;
	}
	const uint32_t candidate_viable = candidate->final_living + candidate->final_seeds;
	const uint32_t champion_viable = champion->final_living + champion->final_seeds;
	if (candidate_viable != champion_viable) {
		return candidate_viable > champion_viable;
	}
	if (candidate->final_living != champion->final_living) {
		return candidate->final_living > champion->final_living;
	}
	if (candidate->established_offspring != champion->established_offspring) {
		return candidate->established_offspring > champion->established_offspring;
	}
	if (candidate->descendant_plant_ticks != champion->descendant_plant_ticks) {
		return candidate->descendant_plant_ticks > champion->descendant_plant_ticks;
	}
	if (candidate->maximum_generation != champion->maximum_generation) {
		return candidate->maximum_generation > champion->maximum_generation;
	}
	if (candidate->living_plant_ticks != champion->living_plant_ticks) {
		return candidate->living_plant_ticks > champion->living_plant_ticks;
	}
	return candidate->deaths < champion->deaths;
}

static void print_fitness(const struct garden_train_fitness *fitness)
{
	printf("{\"extinctions\":%" PRIu32 ",\"final_viable\":%" PRIu32 ",\"final_living\":%" PRIu32
	       ",\"final_seeds\":%" PRIu32 ",\"established_offspring\":%" PRIu32
	       ",\"descendant_plant_ticks\":%" PRIu64 ",\"maximum_generation\":%" PRIu32
	       ",\"living_plant_ticks\":%" PRIu64 ",\"deaths\":%" PRIu32
	       ",\"seeds_created\":%" PRIu32 ",\"germinations\":%" PRIu32
	       ",\"state_digest\":\"%08" PRIx32 "\"}",
	       fitness->extinctions, fitness->final_living + fitness->final_seeds,
	       fitness->final_living, fitness->final_seeds, fitness->established_offspring,
	       fitness->descendant_plant_ticks, fitness->maximum_generation,
	       fitness->living_plant_ticks, fitness->deaths, fitness->seeds_created,
	       fitness->germinations, fitness->state_digest);
}

static void print_report(const struct garden_train_options *options,
			 const struct garden_train_fitness *initial, uint32_t initial_fingerprint,
			 const struct garden_train_generation *generations,
			 const struct garden_train_fitness *final, uint32_t final_fingerprint)
{
	printf("{\n  \"schema_version\": %u,\n", GARDEN_TRAIN_SCHEMA_VERSION);
	printf("  \"algorithm\": \"deterministic-(1+lambda)\",\n");
	printf("  \"environment\": {\"rain_version\":%u,\"gardener\":false,"
	       "\"irrigation\":false,\"climate\":\"steady\",\"seed_lifetime_ecology_ticks\":%u,"
	       "\"scenarios\":[\"rainfed\",\"rainfed-crowded\"]},\n",
	       PICOSYSTEM_GARDEN_RAIN_VERSION, PICOSYSTEM_GARDEN_SEED_LIFETIME_TICKS);
	printf("  \"base_seed\": \"%08" PRIx32 "\",\n", options->base_seed);
	printf("  \"settings\": {\"generations\":%" PRIu32 ",\"population\":%" PRIu32
	       ",\"trials_per_scenario\":%" PRIu32 ",\"ticks_per_trial\":%" PRIu32
	       ",\"mutations_per_offspring\":%" PRIu32 ",\"scenario_count\":%u},\n",
	       options->generation_count, options->population_count, options->trial_count,
	       options->tick_count, options->mutation_count,
	       TOY_FACTORY_GARDEN_RAINFED_SCENARIO_COUNT);
	printf("  \"fitness_order\": [\"minimum_extinctions\",\"maximum_final_viable\","
	       "\"maximum_final_living\",\"maximum_established_offspring\","
	       "\"maximum_descendant_plant_ticks\",\"maximum_generation\","
	       "\"maximum_living_plant_ticks\",\"minimum_deaths\"],\n");
	printf("  \"initial\": {\"model_crc32\":\"%08" PRIx32 "\",\"fitness\":",
	       initial_fingerprint);
	print_fitness(initial);
	printf("},\n  \"generations\": [");
	for (uint32_t index = 0U; index < options->generation_count; ++index) {
		const struct garden_train_generation *const generation = &generations[index];
		printf("%s\n    {\"index\":%" PRIu32 ",\"accepted\":%s,"
		       "\"model_crc32\":\"%08" PRIx32 "\",\"fitness\":",
		       (index == 0U) ? "" : ",", index + 1U,
		       generation->accepted ? "true" : "false", generation->fingerprint);
		print_fitness(&generation->fitness);
		putchar('}');
	}
	if (options->generation_count != 0U) {
		putchar('\n');
	}
	printf("  ],\n  \"evaluations\":%" PRIu32 ",\n",
	       1U + options->generation_count * (options->population_count - 1U));
	printf("  \"final\": {\"model_crc32\":\"%08" PRIx32 "\",\"fitness\":", final_fingerprint);
	print_fitness(final);
	printf("}\n}\n");
}

static int write_champion(const struct garden_train_options *options,
			  const struct picosystem_garden_neural_model *champion,
			  uint32_t *fingerprint)
{
	int err =
		toy_factory_garden_model_write_binary(options->output_path, champion, fingerprint);
	if (err != 0) {
		fprintf(stderr, "failed to write model '%s' (%d)\n", options->output_path, err);
		return err;
	}
	err = toy_factory_garden_model_write_c(options->c_output_path, champion, options->symbol,
					       *fingerprint);
	if (err != 0) {
		fprintf(stderr, "failed to write C model '%s' (%d)\n", options->c_output_path, err);
		return err;
	}
	return 0;
}

int main(int argc, char **argv)
{
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	fprintf(stderr,
		"Training is disabled in leaf-maintenance-v1; use the scripted host experiment.\n");
	return 2;
#endif
	struct garden_train_options options;
	const int option_result = parse_options(argc, argv, &options);
	if (option_result > 0) {
		return 0;
	}
	if (option_result < 0) {
		print_usage(stderr, argv[0]);
		return 2;
	}

	struct picosystem_garden_neural_model champion;
	uint32_t input_fingerprint;
	int err;
	if (options.input_path == NULL) {
		champion = *picosystem_garden_neural_reference_model();
		err = toy_factory_garden_model_fingerprint(&champion, &input_fingerprint);
	} else {
		err = toy_factory_garden_model_read(options.input_path, &champion,
						    &input_fingerprint);
	}
	if (err != 0) {
		if (options.input_path == NULL) {
			fprintf(stderr, "failed to load the reference model (%d)\n", err);
		} else {
			fprintf(stderr, "failed to load initial model '%s' (%d)\n",
				options.input_path, err);
		}
		return 1;
	}

	struct garden_train_fitness champion_fitness;
	err = evaluate_model(&champion, &options, &champion_fitness);
	if (err != 0) {
		fprintf(stderr, "initial model evaluation failed (%d)\n", err);
		return 1;
	}
	const struct garden_train_fitness initial_fitness = champion_fitness;
	struct garden_train_generation generations[GARDEN_TRAIN_MAX_GENERATIONS];
	struct toy_factory_garden_mutation_rng search_rng = {
		.state = options.base_seed ^ UINT32_C(0xa511e9b3),
	};
	if (search_rng.state == 0U) {
		search_rng.state = GARDEN_TRAIN_DEFAULT_SEED;
	}

	for (uint32_t generation = 0U; generation < options.generation_count; ++generation) {
		const struct picosystem_garden_neural_model parent = champion;
		struct picosystem_garden_neural_model generation_best = champion;
		struct garden_train_fitness generation_best_fitness = champion_fitness;
		bool accepted = false;
		for (uint32_t member = 1U; member < options.population_count; ++member) {
			struct picosystem_garden_neural_model candidate = parent;
			err = toy_factory_garden_model_mutate(&candidate, &search_rng,
							      options.mutation_count);
			if (err != 0) {
				return 1;
			}
			struct garden_train_fitness candidate_fitness;
			err = evaluate_model(&candidate, &options, &candidate_fitness);
			if (err != 0) {
				fprintf(stderr,
					"generation %" PRIu32 " member %" PRIu32
					" evaluation failed (%d)\n",
					generation + 1U, member, err);
				return 1;
			}
			if (fitness_is_better(&candidate_fitness, &generation_best_fitness)) {
				generation_best = candidate;
				generation_best_fitness = candidate_fitness;
				accepted = true;
			}
		}
		champion = generation_best;
		champion_fitness = generation_best_fitness;
		uint32_t fingerprint;
		err = toy_factory_garden_model_fingerprint(&champion, &fingerprint);
		if (err != 0) {
			fprintf(stderr, "generation fingerprint failed (%d)\n", err);
			return 1;
		}
		generations[generation] = (struct garden_train_generation){
			.fitness = champion_fitness,
			.fingerprint = fingerprint,
			.accepted = accepted,
		};
	}

	uint32_t final_fingerprint;
	err = write_champion(&options, &champion, &final_fingerprint);
	if (err != 0) {
		return 1;
	}
	print_report(&options, &initial_fitness, input_fingerprint, generations, &champion_fitness,
		     final_fingerprint);
	if ((fflush(stdout) != 0) || ferror(stdout)) {
		fprintf(stderr, "failed to write training report to stdout\n");
		return 1;
	}
	fprintf(stderr, "wrote model %08" PRIx32 " to %s and %s\n", final_fingerprint,
		options.output_path, options.c_output_path);
	return 0;
}
