/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_capture.h"
#include "garden_climate_cli.h"
#include "garden_landing_model_file.h"
#include "garden_landing_run.h"
#include "garden_lifetimes.h"
#include "garden_model_file.h"

#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_TICKS (256U * TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS)

/* One trial per process; this bounded host ledger outlives compacted slots. */
static struct toy_factory_garden_lifetimes ledger;
static const char *const modes[] = {"off", "current", "history"};

static void usage(FILE *stream)
{
	fputs("Usage: toy-factory-garden-landing\n"
	      "  reference OUT.tgl --mode off|current|history [--omit-dead-only]\n"
	      "  import IN.tgm OUT.tgl --mode off|current|history [--omit-dead-only]\n"
	      "  inspect MODEL.tgl\n"
	      "  replay MODEL.tgl rainfed|rainfed-crowded SEED --ticks N\n"
	      "         --climate steady|winter|drought|seasonal [--framebuffer NEW.rgb565]\n"
	      "Host-only; gardener off; masks are fixed in the model, never load overrides.\n"
	      "Replay supports 0..983040 logic ticks (256 Garden days), nonzero u32 seeds.\n"
	      "Outputs JSON; files must not exist. No training or device defaults change.\n",
	      stream);
}

static int parse_u32(const char *text, uint32_t maximum, uint32_t *value)
{
	if ((*text < '0') || (*text > '9')) {
		return -EINVAL;
	}
	errno = 0;
	char *end = NULL;
	const unsigned long parsed = strtoul(text, &end, 0);
	if ((errno != 0) || (*end != '\0') || (parsed > maximum)) {
		return -ERANGE;
	}
	*value = (uint32_t)parsed;
	return 0;
}

static uint32_t read_le32(const uint8_t *bytes)
{
	return (uint32_t)bytes[0] | ((uint32_t)bytes[1] << 8U) | ((uint32_t)bytes[2] << 16U) |
	       ((uint32_t)bytes[3] << 24U);
}

static int print_model(const struct toy_factory_garden_landing_model *model)
{
	uint8_t bytes[TOY_FACTORY_GARDEN_LANDING_FILE_SIZE];
	const int err = toy_factory_garden_landing_model_encode(model, bytes, sizeof(bytes));
	if (err != 0) {
		return err;
	}
	unsigned int common = 0U;
	unsigned int candidate = 0U;
	for (size_t u = 0U; u < PICOSYSTEM_GARDEN_NEURAL_HIDDEN_UNIT_COUNT; ++u) {
		for (size_t f = 0U; f < TOY_FACTORY_GARDEN_LANDING_COMMON_COUNT; ++f) {
			common += (model->common_weights[u][f] != 0) ? 1U : 0U;
		}
	}
	for (size_t u = 0U; u < PICOSYSTEM_GARDEN_NEURAL_CANDIDATE_UNIT_COUNT; ++u) {
		for (size_t f = 0U; f < TOY_FACTORY_GARDEN_LANDING_CANDIDATE_COUNT; ++f) {
			candidate += (model->candidate_weights[u][f] != 0) ? 1U : 0U;
		}
	}
	printf("{\"format\":\"TGL2\",\"bytes\":%u,\"payload_crc32\":\"%08" PRIx32
	       "\",\"legacy_payload_crc32\":\"%08" PRIx32
	       "\",\"feature_version\":%u,\"mode\":\"%s\",\"omit_dead_only\":%s,"
	       "\"common_nonzero_weights\":%u,\"candidate_nonzero_weights\":%u}",
	       TOY_FACTORY_GARDEN_LANDING_FILE_SIZE, read_le32(&bytes[12]), read_le32(&bytes[28]),
	       model->config.version, modes[model->config.mode],
	       model->config.flags ? "true" : "false", common, candidate);
	return ferror(stdout) ? -EIO : 0;
}

static int create_model(int argc, char **argv, bool importing)
{
	const int first_option = importing ? 4 : 3;
	if (argc < first_option + 2) {
		return -EINVAL;
	}
	struct toy_factory_garden_landing_feature_config config = {
		.version = TOY_FACTORY_GARDEN_LANDING_FEATURE_VERSION};
	bool mode_set = false;
	for (int i = first_option; i < argc; ++i) {
		if ((strcmp(argv[i], "--mode") == 0) && !mode_set && (i + 1 < argc)) {
			++i;
			for (uint8_t m = 0U; m < TOY_FACTORY_GARDEN_LANDING_INPUT_MODE_COUNT; ++m) {
				if (strcmp(argv[i], modes[m]) == 0) {
					config.mode = m;
					mode_set = true;
					break;
				}
			}
			if (!mode_set) {
				return -EINVAL;
			}
		} else if ((strcmp(argv[i], "--omit-dead-only") == 0) && (config.flags == 0U)) {
			config.flags = TOY_FACTORY_GARDEN_LANDING_OMIT_DEAD_ONLY;
		} else {
			return -EINVAL;
		}
	}
	if (!mode_set) {
		return -EINVAL;
	}
	struct picosystem_garden_neural_model legacy = *picosystem_garden_neural_reference_model();
	if (importing) {
		uint32_t crc;
		const int err = toy_factory_garden_model_read(argv[2], &legacy, &crc);
		if (err != 0) {
			return err;
		}
	}
	struct toy_factory_garden_landing_model model;
	int err = toy_factory_garden_landing_model_import(&legacy, &config, &model);
	if (err == 0) {
		err = toy_factory_garden_landing_model_write_new(argv[first_option - 1], &model);
	}
	if (err != 0) {
		return err;
	}
	fputs("{\"schema_version\":1,\"model\":", stdout);
	err = print_model(&model);
	puts("}");
	return err;
}

static int record_births(const struct picosystem_garden_world *world)
{
	for (uint8_t i = 0U; i < world->plant_count; ++i) {
		const struct picosystem_garden_plant *const plant = &world->plants[i];
		if (plant->lineage_id > ledger.count) {
			const int err = toy_factory_garden_lifetimes_birth(
				&ledger, plant->lineage_id, plant->parent_lineage_id,
				plant->species_id, world->logic_tick_count);
			if (err != 0) {
				return err;
			}
		}
		if ((plant->lineage_id == 0U) ||
		    (((plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) != 0U) !=
		     (ledger.records[plant->lineage_id].death_cause !=
		      TOY_FACTORY_GARDEN_LIFETIME_CAUSES))) {
			return -EFAULT;
		}
	}
	return (ledger.count == world->lineage_sequence) ? 0 : -EFAULT;
}

static uint8_t descendants(const struct picosystem_garden_world *world)
{
	uint8_t living = 0U;
	for (uint8_t i = 0U; i < world->plant_count; ++i) {
		if ((world->plants[i].parent_lineage_id != 0U) &&
		    ((world->plants[i].flags & PICOSYSTEM_GARDEN_PLANT_DEAD) == 0U)) {
			++living;
		}
	}
	return living;
}

static void print_lifetimes(const struct toy_factory_garden_lifetime_metrics *m)
{
	printf("{\"offspring_born\":%" PRIu32 ",\"eligible_offspring\":%" PRIu32
	       ",\"cycle_survivors\":%" PRIu32 ",\"died_before_cycle\":%" PRIu32
	       ",\"too_young_alive\":%" PRIu32 ",\"too_young_dead\":%" PRIu32
	       ",\"offspring_with_surviving_child\":%" PRIu32
	       ",\"cycle_survivors_with_surviving_child\":%" PRIu32
	       ",\"founders_with_surviving_child\":%" PRIu32 ",\"offspring_living_at_end\":%" PRIu32
	       ",\"founders_living_at_end\":%" PRIu32 ",\"offspring_deaths\":%" PRIu32
	       ",\"founder_deaths\":%" PRIu32 "}",
	       m->offspring_born, m->eligible_offspring, m->cycle_survivors, m->died_before_cycle,
	       m->too_young_alive, m->too_young_dead, m->offspring_with_surviving_child,
	       m->cycle_survivors_with_surviving_child, m->founders_with_surviving_child,
	       m->offspring_living_at_end, m->founders_living_at_end, m->offspring_mortality.deaths,
	       m->founder_mortality.deaths);
}

static int replay(int argc, char **argv)
{
	if (argc < 9) {
		return -EINVAL;
	}
	const struct toy_factory_garden_evaluation_scenario *scenario = NULL;
	for (size_t i = 0U; i < TOY_FACTORY_GARDEN_RAINFED_SCENARIO_COUNT; ++i) {
		if (strcmp(argv[3], toy_factory_garden_rainfed_scenarios[i].name) == 0) {
			scenario = &toy_factory_garden_rainfed_scenarios[i];
		}
	}
	uint32_t seed;
	if ((scenario == NULL) || (parse_u32(argv[4], UINT32_MAX, &seed) != 0) || (seed == 0U)) {
		return -EINVAL;
	}
	bool ticks_set = false;
	bool climate_set = false;
	uint32_t ticks = 0U;
	enum picosystem_garden_climate_mode climate = PICOSYSTEM_GARDEN_CLIMATE_STEADY;
	const char *framebuffer = NULL;
	for (int i = 5; i < argc; i += 2) {
		if (i + 1 == argc) {
			return -EINVAL;
		}
		if ((strcmp(argv[i], "--ticks") == 0) && !ticks_set) {
			if (parse_u32(argv[i + 1], MAX_TICKS, &ticks) != 0) {
				return -EINVAL;
			}
			ticks_set = true;
		} else if ((strcmp(argv[i], "--climate") == 0) && !climate_set) {
			if (toy_factory_garden_climate_parse(argv[i + 1], &climate) != 0) {
				return -EINVAL;
			}
			climate_set = true;
		} else if ((strcmp(argv[i], "--framebuffer") == 0) && (framebuffer == NULL) &&
			   (*argv[i + 1] != '\0')) {
			framebuffer = argv[i + 1];
		} else {
			return -EINVAL;
		}
	}
	if (!ticks_set || !climate_set) {
		return -EINVAL;
	}
	struct toy_factory_garden_landing_model model;
	struct picosystem_garden_world initial;
	struct toy_factory_garden_landing_run run;
	int err = toy_factory_garden_landing_model_read(argv[2], &model);
	if (err == 0) {
		err = toy_factory_garden_evaluation_reset(&initial, scenario, seed);
	}
	if (err == 0) {
		err = picosystem_garden_world_set_climate(&initial, climate);
	}
	if (err == 0) {
		err = toy_factory_garden_landing_run_init(&initial, &model, &run);
	}
	if (err == 0) {
		err = toy_factory_garden_lifetimes_reset(&ledger);
	}
	if (err == 0) {
		err = record_births(&initial);
	}
	if (err != 0) {
		return err;
	}
	uint64_t descendant_live_ticks = 0U;
	for (uint32_t tick = 0U; tick < ticks; ++tick) {
		struct picosystem_garden_death_audit deaths;
		err = toy_factory_garden_landing_run_step_death_audit(&run, &deaths);
		if (err != 0) {
			return err;
		}
		for (uint8_t d = 0U; d < deaths.count; ++d) {
			err = toy_factory_garden_lifetimes_death(
				&ledger, deaths.events[d].lineage_id, run.world.logic_tick_count,
				deaths.events[d].flags);
			if (err != 0) {
				return err;
			}
		}
		if (deaths.ecology_step) {
			err = record_births(&run.world);
			if (err != 0) {
				return err;
			}
		}
		descendant_live_ticks += descendants(&run.world);
	}
	struct toy_factory_garden_lifetime_report report;
	err = toy_factory_garden_lifetimes_summarize(&ledger, ticks, &report);
	const struct picosystem_garden_world *const world = &run.world;
	if (err != 0) {
		return err;
	}
	if ((report.total.offspring_born != world->germination_count) ||
	    (report.total.offspring_mortality.deaths + report.total.founder_mortality.deaths !=
	     world->death_count) ||
	    (report.total.offspring_living_at_end + report.total.founders_living_at_end !=
	     picosystem_garden_world_living_plant_count(world))) {
		return -EFAULT;
	}
	uint32_t hash;
	err = toy_factory_garden_landing_run_hash(&run, &hash);
	uint32_t framebuffer_crc = 0U;
	if ((err == 0) && (framebuffer != NULL)) {
		err = toy_factory_garden_capture(world, framebuffer, &framebuffer_crc);
		uint32_t after;
		if ((err == 0) &&
		    ((toy_factory_garden_landing_run_hash(&run, &after) != 0) || (after != hash))) {
			err = -EFAULT;
		}
	}
	if (err != 0) {
		return err;
	}
	printf("{\"schema_version\":1,\"kind\":\"landing-replay\",\"run_version\":%u,"
	       "\"rules\":%" PRIu32 ",\"scenario\":\"%s\",\"seed\":\"%08" PRIx32
	       "\",\"tick\":%" PRIu32 ",\"world_hash\":\"%08" PRIx32 "\",\"run_hash\":\"%08" PRIx32
	       "\",\"model\":",
	       run.version, run.rules, scenario->name, seed, ticks,
	       picosystem_garden_world_hash(world), hash);
	err = print_model(&model);
	putchar(',');
	toy_factory_garden_climate_print(stdout, world);
	printf("\"gardener\":false,\"irrigation\":false,\"warmup_samples\":%u,"
	       "\"living\":%u,\"descendants\":%u,\"plant_slots\":%u,\"nodes\":%u,"
	       "\"seed_bank\":%u,\"births\":%" PRIu32 ",\"deaths\":%" PRIu32
	       ",\"moisture\":%u,\"rain_deposited\":%" PRIu32 ",\"rain_runoff\":%" PRIu32
	       ",\"descendant_live_ticks\":%" PRIu64 ",\"lifetimes\":",
	       run.cache.warmup_samples, picosystem_garden_world_living_plant_count(world),
	       descendants(world), world->plant_count, world->node_count, world->seed_count,
	       world->germination_count, world->death_count, world->moisture_total,
	       world->rain_deposited, world->rain_runoff, descendant_live_ticks);
	print_lifetimes(&report.total);
	fputs(",\"species_lifetimes\":[", stdout);
	for (uint8_t s = 0U; s < PICOSYSTEM_GARDEN_SPECIES_COUNT; ++s) {
		if (s != 0U) {
			putchar(',');
		}
		print_lifetimes(&report.species[s]);
	}
	fputs("],\"framebuffer_crc32\":", stdout);
	if (framebuffer != NULL) {
		printf("\"%08" PRIx32 "\"", framebuffer_crc);
	} else {
		fputs("null", stdout);
	}
	puts("}");
	return err;
}

int main(int argc, char **argv)
{
	if ((argc == 2) && (strcmp(argv[1], "--help") == 0)) {
		usage(stdout);
		return (fflush(stdout) == 0 && !ferror(stdout)) ? 0 : 1;
	}
	int err = -EINVAL;
	if (argc > 1) {
		if (strcmp(argv[1], "reference") == 0 || strcmp(argv[1], "import") == 0) {
			err = create_model(argc, argv, strcmp(argv[1], "import") == 0);
		} else if ((strcmp(argv[1], "inspect") == 0) && (argc == 3)) {
			struct toy_factory_garden_landing_model model;
			err = toy_factory_garden_landing_model_read(argv[2], &model);
			if (err == 0) {
				fputs("{\"schema_version\":1,\"model\":", stdout);
				err = print_model(&model);
				puts("}");
			}
		} else if (strcmp(argv[1], "replay") == 0) {
			err = replay(argc, argv);
		}
	}
	if ((fflush(stdout) != 0) || ferror(stdout)) {
		err = -EIO;
	}
	if (err != 0) {
		fprintf(stderr, "landing command failed: %s (%d)\n", strerror(-err), err);
		if (err == -EINVAL) {
			usage(stderr);
		}
	}
	return (err == 0) ? 0 : 1;
}
