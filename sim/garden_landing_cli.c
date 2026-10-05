/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_capture.h"
#include "garden_climate_cli.h"
#include "garden_landing_model_file.h"
#include "garden_landing_run.h"
#include "garden_landing_ledger.h"
#include "garden_landing_mutation.h"
#include "garden_landing_signal.h"
#include "garden_landing_decisions.h"
#include "garden_landing_recruitment.h"
#include "garden_landing_reach.h"
#include "garden_landing_water.h"
#include "garden_landing_growth.h"
#include "garden_landing_plant_trace.h"
#include "garden_uptake_trace.h"
#include "garden_landing_vacancy.h"
#include "garden_landing_turnover.h"
#include "garden_lifetimes.h"
#include "garden_model_file.h"
#if defined(TOY_FACTORY_GARDEN_SOIL_WICKING)
#include "garden_wicking.h"
#endif
#if defined(TOY_FACTORY_GARDEN_LATE_UPTAKE_LIMIT)
#include "garden_uptake_limit.h"
#endif
#if defined(TOY_FACTORY_GARDEN_LATE_DISPERSAL)
#include "garden_late_dispersal.h"
#endif

#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Bounded host follow-up only; evaluator/training horizons remain unchanged.
 * Append ledgers retain their independent fail-closed capacity checks.
 */
#define MAX_TICKS (320U * TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS)

/* One trial per process; this bounded host ledger outlives compacted slots. */
static struct toy_factory_garden_lifetimes ledger;
static struct toy_factory_garden_landing_ledger history;
static struct toy_factory_garden_decision_trace decision_trace;
/* Always closed in main, including partial-trace failure paths. */
static FILE *decision_stream;
static FILE *recruitment_stream;
static FILE *reach_stream;
static FILE *water_stream;
static FILE *adult_stream;
static FILE *plant_stream;
static FILE *placement_stream;
static FILE *uptake_stream;
static FILE *direction_stream;
static FILE *replacement_stream;
static struct picosystem_garden_uptake_audit uptake_audit;
static struct toy_factory_garden_plant_trace plant_trace;
static const char *const water_modes[] = {"off", "on"};
static const char *const arbitration_modes[] = {"veto", "eligible"};
static const char *const placement_modes[] = {"off", "spacing"};
static const char *const modes[] = {"off", "current", "history"};
static const char *const occupancy_probes[] = {"live", "neutral", "occupied", "open"};
static const char *const resource_probes[] = {"live", "mid", "low", "high"};

static void usage(FILE *stream)
{
	fputs("Usage: toy-factory-garden-landing\n"
	      "  reference OUT.tgl --mode off|current|history [--omit-dead-only]\n"
	      "  import IN.tgm OUT.tgl --mode off|current|history [--omit-dead-only]\n"
	      "  inspect MODEL.tgl\n"
	      "  ablate IN.tgl NEW.tgl off|current\n"
	      "  mutate IN.tgl NEW.tgl RNG_STATE LEGACY_MUTATIONS LANDING_MUTATIONS\n"
	      "  replay MODEL.tgl rainfed|rainfed-crowded SEED --ticks N\n"
	      "         --climate steady|winter|drought|seasonal [--framebuffer NEW.rgb565] "
	      "[--ledger] [--recruitment-trace NEW.jsonl] [--reach-trace NEW.jsonl]\n"
	      "  probe-replay MODEL.tgl rainfed|rainfed-crowded SEED --ticks N\n"
	      "         --climate steady|winter|drought|seasonal [--framebuffer NEW.rgb565] "
	      "[--ledger]\n"
	      "         --occupancy live|neutral|occupied|open --resources live|mid|low|high\n"
	      "  trace-replay MODEL.tgl rainfed|rainfed-crowded SEED --ticks N\n"
	      "         --climate steady|winter|drought|seasonal --trace NEW.jsonl [--ledger]\n"
	      "         [--framebuffer NEW.rgb565]\n"
	      "  water-replay MODEL.tgl rainfed|rainfed-crowded SEED --ticks N\n"
	      "         --climate steady|winter|drought|seasonal --water-reserve off|on\n"
	      "         [--ledger] [--recruitment-trace NEW.jsonl] [--water-trace NEW.jsonl]\n"
	      "         [--framebuffer NEW.rgb565] (ordinary ecology only)\n"
	      "  arbitration-replay MODEL.tgl rainfed|rainfed-crowded SEED --ticks N\n"
	      "         --climate steady|winter|drought|seasonal --water-arbitration "
	      "veto|eligible\n"
	      "         [--ledger] [--recruitment-trace NEW.jsonl] [--water-trace NEW.jsonl]\n"
	      "         [--framebuffer NEW.rgb565] (ordinary ecology; water reserve enabled)\n"
	      "  growth-replay MODEL.tgl rainfed|rainfed-crowded SEED --ticks N\n"
	      "         --climate steady|winter|drought|seasonal --node-limit off|32\n"
	      "         [--ledger] [--recruitment-trace NEW.jsonl] [--framebuffer NEW.rgb565]\n"
	      "         (ordinary ecology; water-eligible arbitration; host-only cap)\n"
	      "Trace samples first root/stem query per day; alternatives never advance the world.\n"
	      "replay/water-replay/arbitration-replay/growth-replay accept --adult-trace "
	      "NEW.jsonl\n"
	      "  --adult-start TICK --adult-stop TICK (inclusive ecology ticks; requires "
	      "--ledger).\n"
	      "growth-replay also accepts --founder-trace NEW.jsonl --founder-start TICK\n"
	      "  --founder-stop TICK (same bounds; requires --ledger; no policy change).\n"
	      "budget-replay uses --shoot-reserve off|on instead of --node-limit.\n"
	      "  Both use budget-eligible ranking at 32 nodes and accept the same traces.\n"
	      "  budget-replay also accepts --reach-trace NEW.jsonl (requires --ledger).\n"
	      "placement-replay adds required --seed-placement off|spacing to budget-replay.\n"
	      "  Optional --seed-replace-after TICK requires spacing placement and --ledger.\n"
	      "  --replacement-trace NEW.jsonl records production-phase seed replacements.\n"
	      "  Optional --placement-trace NEW.jsonl requires --ledger; no founder trace.\n"
	      "vacancy-replay adds required --vacancy-at TICK --vacancy-lineage ID and --ledger.\n"
	      "  Export one >one-day adult after that ordinary ecology step; no fallback.\n"
	      "placement-replay accepts --turnover-at TICK --turnover-lineage ID with --ledger\n"
	      "  optionally --second-turnover-at TICK --second-turnover-lineage ID (later, "
	      "distinct)\n"
	      "  (post-observation environmental deaths; normal decomposition; TICK <= stop).\n"
	      "placement/vacancy accept --stand-trace NEW.jsonl --stand-start TICK\n"
	      "  --stand-stop TICK (all plants; requires --ledger; not --placement-trace).\n"
	      "  Add --stand-order to retain the unrotated array inventory in a new trace schema.\n"
	      "  Optional --uptake-trace NEW.jsonl and repeated --uptake-window START:STOP\n"
	      "  record passive uptake within --stand-trace bounds (1..64 disjoint windows).\n"
	      "  --direction-trace NEW.jsonl records candidates/rankings with --stand-dawn.\n"
	      "  --root-wet-direction tests affordable wetter root endpoints with "
	      "--root-all-offspring.\n"
	      "  --root-allocation-focal tests root priority for lineage 9 born at 403365;\n"
	      "  requires all-offspring daylight guards; incompatible with wet direction.\n"
	      "  Optional --seed-order rotating --seed-order-after TICK (positive multiple of 60;\n"
	      "  requires --ledger; fixed order through TICK; host-only, separately identified).\n"
	      "Signal probes and traces require current-only, flags=0; model bytes never change.\n"
	      "Host-only; gardener off; masks are fixed in the model, never load overrides.\n"
	      "Replay supports 0..1228800 logic ticks (320 Garden days), nonzero u32 seeds.\n"
	      "Outputs JSON; files must not exist. No device defaults change.\n",
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

static int parse_uptake_window(const char *text, struct toy_factory_garden_uptake_window *window)
{
	const char *colon = strchr(text, ':');
	char start[32];
	if ((colon == NULL) || (colon == text) || ((size_t)(colon - text) >= sizeof(start))) {
		return -EINVAL;
	}
	const size_t length = (size_t)(colon - text);
	memcpy(start, text, length);
	start[length] = '\0';
	struct toy_factory_garden_uptake_window result;
	if ((parse_u32(start, MAX_TICKS, &result.start) != 0) ||
	    (parse_u32(colon + 1, MAX_TICKS, &result.stop) != 0) || (result.start == 0U) ||
	    (result.stop < result.start) ||
	    (result.start % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR != 0U) ||
	    (result.stop % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR != 0U)) {
		return -EINVAL;
	}
	*window = result;
	return 0;
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

static int ablate_model(int argc, char **argv)
{
	if (argc != 5) {
		return -EINVAL;
	}
	uint8_t mode;
	if (strcmp(argv[4], "off") == 0) {
		mode = TOY_FACTORY_GARDEN_LANDING_INPUT_OFF;
	} else if (strcmp(argv[4], "current") == 0) {
		mode = TOY_FACTORY_GARDEN_LANDING_INPUT_CURRENT;
	} else {
		return -EINVAL;
	}
	struct toy_factory_garden_landing_model model;
	int err = toy_factory_garden_landing_model_read(argv[2], &model);
	if (err != 0) {
		return err;
	}
	const uint8_t source_mode = model.config.mode;
	if (mode >= source_mode) {
		return -EINVAL;
	}
	/* An explicit derived file preserves all weights, even those now masked. */
	model.config.mode = mode;
	err = toy_factory_garden_landing_model_write_new(argv[3], &model);
	if (err != 0) {
		return err;
	}
	printf("{\"schema_version\":1,\"source_mode\":\"%s\",\"model\":", modes[source_mode]);
	err = print_model(&model);
	puts("}");
	return err;
}

static int mutate_model(int argc, char **argv)
{
	uint32_t seed, legacy_count, landing_count;
	if ((argc != 7) || (parse_u32(argv[4], UINT32_MAX, &seed) != 0) ||
	    (parse_u32(argv[5], 4096U, &legacy_count) != 0) ||
	    (parse_u32(argv[6], 4096U, &landing_count) != 0)) {
		return -EINVAL;
	}
	struct toy_factory_garden_landing_model model;
	struct toy_factory_garden_mutation_rng rng = {.state = seed};
	int err = toy_factory_garden_landing_model_read(argv[2], &model);
	if (err == 0) {
		err = toy_factory_garden_landing_mutate(&model, &rng, legacy_count, landing_count);
	}
	if (err == 0) {
		err = toy_factory_garden_landing_model_write_new(argv[3], &model);
	}
	if (err != 0) {
		return err;
	}
	printf("{\"schema_version\":1,\"rng_before\":%" PRIu32 ",\"rng_after\":%" PRIu32
	       ",\"legacy_mutations\":%" PRIu32 ",\"landing_mutations\":%" PRIu32 ",\"model\":",
	       seed, rng.state, legacy_count, landing_count);
	err = print_model(&model);
	puts("}");
	return err;
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

static int parse_choice(const char *text, const char *const *names, uint8_t count, uint8_t *value)
{
	for (uint8_t i = 0U; i < count; ++i) {
		if (strcmp(text, names[i]) == 0) {
			*value = i;
			return 0;
		}
	}
	return -EINVAL;
}

static int replay_hash(const struct toy_factory_garden_landing_signal_run *run, bool probing,
		       const struct toy_factory_garden_landing_water_run *water, bool watering,
		       const struct toy_factory_garden_landing_growth_run *growth, bool growing,
		       uint32_t *hash)
{
	if (growing) {
		return toy_factory_garden_landing_growth_hash(growth, hash);
	}
	if (watering) {
		return toy_factory_garden_landing_water_hash(water, hash);
	}
	return probing ? toy_factory_garden_landing_signal_hash(run, hash)
		       : toy_factory_garden_landing_run_hash(&run->base, hash);
}

static int replay(int argc, char **argv, bool probing, bool tracing, bool watering,
		  bool arbitrating, bool growing)
{
	const bool vacancy = strcmp(argv[1], "vacancy-replay") == 0;
	const bool placing = vacancy || (strcmp(argv[1], "placement-replay") == 0);
	const bool budgeting = placing || (strcmp(argv[1], "budget-replay") == 0);
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
	const char *trace_path = NULL;
	const char *recruitment_path = NULL;
	const char *reach_path = NULL;
	const char *placement_path = NULL;
	bool placement_set = false;
	uint8_t seed_placement = 0U;
	uint32_t replace_after = 0U;
	const char *replacement_path = NULL;
	uint32_t vacancy_tick = 0U, vacancy_lineage = 0U;
	struct toy_factory_garden_landing_vacancy vacancy_event = {0};
	uint32_t turnover_tick = 0U, turnover_lineage = 0U;
	struct toy_factory_garden_landing_turnover turnover_event = {0};
	uint32_t second_turnover_tick = 0U, second_turnover_lineage = 0U;
	struct toy_factory_garden_landing_turnover second_turnover_event = {0};
	const char *water_path = NULL;
	const char *adult_path = NULL;
	uint32_t adult_start = 0U, adult_stop = 0U;
	const char *plant_path = NULL;
	uint32_t plant_start = 0U, plant_stop = 0U;
	const char *uptake_path = NULL;
	const char *direction_path = NULL;
	struct toy_factory_garden_uptake_window uptake_windows[TOY_FACTORY_GARDEN_UPTAKE_WINDOWS];
	size_t uptake_count = 0U;
	bool stand_order = false, rotation_set = false;
	bool stand_choice = false;
	bool stand_energy = false;
	bool stand_afternoon = false;
	bool stand_daylight = false;
	bool stand_dawn = false;
	struct toy_factory_garden_root_choice root_choice = {0};
	struct toy_factory_garden_root_allocation root_allocation = {0};
	uint32_t rotation_after = 0U;
	bool water_set = false;
	bool limit_set = false;
	uint8_t node_limit = 0U;
	uint8_t shoot_reserve = 0U;
	struct toy_factory_garden_landing_water_config water_config = {
		.version = arbitrating ? TOY_FACTORY_GARDEN_LANDING_ARBITRATION_VERSION
				       : TOY_FACTORY_GARDEN_LANDING_WATER_VERSION,
		.enabled = arbitrating ? 1U : 0U};
	bool export_ledger = false;
	bool occupancy_set = false;
	bool resources_set = false;
	struct toy_factory_garden_landing_signal_config probe = {
		.version = TOY_FACTORY_GARDEN_LANDING_SIGNAL_VERSION};
	for (int i = 5; i < argc; i += 2) {
		if (placing && !vacancy && (root_allocation.version == 0U) &&
		    (strcmp(argv[i], "--root-allocation-focal") == 0)) {
			root_allocation = (struct toy_factory_garden_root_allocation)
				TOY_FACTORY_GARDEN_ROOT_ALLOCATION_FOCAL;
			--i;
			continue;
		}
		if (placing && !vacancy && !root_choice.wet_direction &&
		    (strcmp(argv[i], "--root-wet-direction") == 0)) {
			root_choice.wet_direction = true;
			--i;
			continue;
		}
		if (placing && !vacancy && !root_choice.all_offspring &&
		    (strcmp(argv[i], "--root-all-offspring") == 0)) {
			root_choice.all_offspring = true;
			--i;
			continue;
		}
		if (placing && !vacancy && !stand_dawn && (strcmp(argv[i], "--stand-dawn") == 0)) {
			stand_dawn = true;
			--i;
			continue;
		}
		if (placing && !vacancy && !root_choice.dawn_reserve &&
		    (strcmp(argv[i], "--root-dawn-reserve") == 0)) {
			root_choice.dawn_reserve = true;
			--i;
			continue;
		}
		if (placing && !vacancy && !stand_daylight &&
		    (strcmp(argv[i], "--stand-daylight") == 0)) {
			stand_daylight = true;
			--i;
			continue;
		}
		if (placing && !vacancy && !root_choice.daylight_energy &&
		    (strcmp(argv[i], "--root-daylight-energy") == 0)) {
			root_choice.daylight_energy = true;
			--i;
			continue;
		}
		if (placing && !vacancy && !stand_afternoon &&
		    (strcmp(argv[i], "--stand-afternoon") == 0)) {
			stand_afternoon = true;
			--i;
			continue;
		}
		if (placing && !vacancy && !root_choice.continuous_energy &&
		    (strcmp(argv[i], "--root-continuous-energy") == 0)) {
			root_choice.continuous_energy = true;
			--i;
			continue;
		}
		if (placing && !vacancy && !root_choice.afternoon_reserve &&
		    (strcmp(argv[i], "--root-afternoon-reserve") == 0)) {
			root_choice.afternoon_reserve = true;
			--i;
			continue;
		}
		if (placing && !vacancy && !stand_energy &&
		    (strcmp(argv[i], "--stand-energy") == 0)) {
			stand_energy = true;
			--i;
			continue;
		}
		if (placing && !vacancy && !root_choice.energy_reserve &&
		    (strcmp(argv[i], "--root-energy-reserve") == 0)) {
			root_choice.energy_reserve = true;
			--i;
			continue;
		}
		if (placing && !vacancy && !stand_choice &&
		    (strcmp(argv[i], "--stand-choice") == 0)) {
			stand_choice = true;
			--i;
			continue;
		}
		if (placing && !stand_order && (strcmp(argv[i], "--stand-order") == 0)) {
			stand_order = true;
			--i;
			continue;
		}
		if ((strcmp(argv[i], "--ledger") == 0) && !export_ledger) {
			export_ledger = true;
			--i;
			continue;
		}
		if (i + 1 == argc) {
			return -EINVAL;
		}
		if ((strcmp(argv[i], "--ticks") == 0) && !ticks_set) {
			if (parse_u32(argv[i + 1], MAX_TICKS, &ticks) != 0) {
				return -EINVAL;
			}
			ticks_set = true;
		} else if (placing && !vacancy && (root_choice.tick == 0U) &&
			   (strcmp(argv[i], "--root-choice-at") == 0)) {
			if ((parse_u32(argv[i + 1], MAX_TICKS, &root_choice.tick) != 0) ||
			    (root_choice.tick == 0U)) {
				return -EINVAL;
			}
		} else if (placing && !vacancy && (root_choice.lineage == 0U) &&
			   (strcmp(argv[i], "--root-choice-lineage") == 0)) {
			if ((parse_u32(argv[i + 1],
				       TOY_FACTORY_GARDEN_EVALUATION_MAX_TRACKED_LINEAGES,
				       &root_choice.lineage) != 0) ||
			    (root_choice.lineage == 0U)) {
				return -EINVAL;
			}
		} else if (placing && !vacancy && (strcmp(argv[i], "--seed-replace-after") == 0) &&
			   (replace_after == 0U)) {
			if ((parse_u32(argv[i + 1], MAX_TICKS, &replace_after) != 0) ||
			    (replace_after == 0U)) {
				return -EINVAL;
			}
		} else if (placing && !vacancy && (strcmp(argv[i], "--replacement-trace") == 0) &&
			   (replacement_path == NULL) && (*argv[i + 1] != '\0')) {
			replacement_path = argv[i + 1];
		} else if (placing && !vacancy && (strcmp(argv[i], "--turnover-at") == 0) &&
			   (turnover_tick == 0U)) {
			if ((parse_u32(argv[i + 1], MAX_TICKS, &turnover_tick) != 0) ||
			    (turnover_tick == 0U)) {
				return -EINVAL;
			}
		} else if (placing && !vacancy && (strcmp(argv[i], "--turnover-lineage") == 0) &&
			   (turnover_lineage == 0U)) {
			if ((parse_u32(argv[i + 1],
				       TOY_FACTORY_GARDEN_EVALUATION_MAX_TRACKED_LINEAGES,
				       &turnover_lineage) != 0) ||
			    (turnover_lineage == 0U)) {
				return -EINVAL;
			}
		} else if (placing && !vacancy && (strcmp(argv[i], "--second-turnover-at") == 0) &&
			   (second_turnover_tick == 0U)) {
			if ((parse_u32(argv[i + 1], MAX_TICKS, &second_turnover_tick) != 0) ||
			    (second_turnover_tick == 0U)) {
				return -EINVAL;
			}
		} else if (placing && !vacancy &&
			   (strcmp(argv[i], "--second-turnover-lineage") == 0) &&
			   (second_turnover_lineage == 0U)) {
			if ((parse_u32(argv[i + 1],
				       TOY_FACTORY_GARDEN_EVALUATION_MAX_TRACKED_LINEAGES,
				       &second_turnover_lineage) != 0) ||
			    (second_turnover_lineage == 0U)) {
				return -EINVAL;
			}
		} else if (vacancy && (strcmp(argv[i], "--vacancy-at") == 0) &&
			   (vacancy_tick == 0U)) {
			if ((parse_u32(argv[i + 1], MAX_TICKS, &vacancy_tick) != 0) ||
			    (vacancy_tick == 0U)) {
				return -EINVAL;
			}
		} else if (vacancy && (strcmp(argv[i], "--vacancy-lineage") == 0) &&
			   (vacancy_lineage == 0U)) {
			if ((parse_u32(argv[i + 1],
				       TOY_FACTORY_GARDEN_EVALUATION_MAX_TRACKED_LINEAGES,
				       &vacancy_lineage) != 0) ||
			    (vacancy_lineage == 0U)) {
				return -EINVAL;
			}
		} else if ((strcmp(argv[i], "--climate") == 0) && !climate_set) {
			if (toy_factory_garden_climate_parse(argv[i + 1], &climate) != 0) {
				return -EINVAL;
			}
			climate_set = true;
		} else if ((strcmp(argv[i], "--framebuffer") == 0) && (framebuffer == NULL) &&
			   (*argv[i + 1] != '\0')) {
			framebuffer = argv[i + 1];
		} else if (tracing && (strcmp(argv[i], "--trace") == 0) && (trace_path == NULL) &&
			   (*argv[i + 1] != '\0')) {
			trace_path = argv[i + 1];
		} else if (!tracing && !probing && (recruitment_path == NULL) &&
			   (strcmp(argv[i], "--recruitment-trace") == 0) &&
			   (*argv[i + 1] != '\0')) {
			recruitment_path = argv[i + 1];
		} else if (!tracing && !probing && (adult_path == NULL) &&
			   (strcmp(argv[i], "--adult-trace") == 0) && (*argv[i + 1] != '\0')) {
			adult_path = argv[i + 1];
		} else if ((strcmp(argv[i], "--adult-start") == 0) && (adult_start == 0U)) {
			if ((parse_u32(argv[i + 1], MAX_TICKS, &adult_start) != 0) ||
			    (adult_start == 0U)) {
				return -EINVAL;
			}
		} else if ((strcmp(argv[i], "--adult-stop") == 0) && (adult_stop == 0U)) {
			if ((parse_u32(argv[i + 1], MAX_TICKS, &adult_stop) != 0) ||
			    (adult_stop == 0U)) {
				return -EINVAL;
			}
		} else if (placing && (direction_path == NULL) &&
			   (strcmp(argv[i], "--direction-trace") == 0) && (*argv[i + 1] != '\0')) {
			direction_path = argv[i + 1];
		} else if (placing && (uptake_path == NULL) &&
			   (strcmp(argv[i], "--uptake-trace") == 0) && (*argv[i + 1] != '\0')) {
			uptake_path = argv[i + 1];
		} else if (placing && (strcmp(argv[i], "--uptake-window") == 0)) {
			if ((uptake_count >= TOY_FACTORY_GARDEN_UPTAKE_WINDOWS) ||
			    (parse_uptake_window(argv[i + 1], &uptake_windows[uptake_count]) !=
			     0) ||
			    ((uptake_count > 0U) && (uptake_windows[uptake_count].start <=
						     uptake_windows[uptake_count - 1U].stop))) {
				return -EINVAL;
			}
			++uptake_count;
		} else if (growing && (plant_path == NULL) &&
			   (strcmp(argv[i], placing ? "--stand-trace" : "--founder-trace") == 0) &&
			   (*argv[i + 1] != '\0')) {
			plant_path = argv[i + 1];
		} else if (growing &&
			   (strcmp(argv[i], placing ? "--stand-start" : "--founder-start") == 0) &&
			   (plant_start == 0U)) {
			if ((parse_u32(argv[i + 1], MAX_TICKS, &plant_start) != 0) ||
			    (plant_start == 0U)) {
				return -EINVAL;
			}
		} else if (growing &&
			   (strcmp(argv[i], placing ? "--stand-stop" : "--founder-stop") == 0) &&
			   (plant_stop == 0U)) {
			if ((parse_u32(argv[i + 1], MAX_TICKS, &plant_stop) != 0) ||
			    (plant_stop == 0U)) {
				return -EINVAL;
			}
		} else if (!tracing && !probing && !watering && (!growing || budgeting) &&
			   (reach_path == NULL) && (strcmp(argv[i], "--reach-trace") == 0) &&
			   (*argv[i + 1] != '\0')) {
			reach_path = argv[i + 1];
		} else if (probing && !occupancy_set && (strcmp(argv[i], "--occupancy") == 0)) {
			if (parse_choice(argv[i + 1], occupancy_probes,
					 TOY_FACTORY_GARDEN_LANDING_OCCUPANCY_COUNT,
					 &probe.occupancy) != 0) {
				return -EINVAL;
			}
			occupancy_set = true;
		} else if (probing && !resources_set && (strcmp(argv[i], "--resources") == 0)) {
			if (parse_choice(argv[i + 1], resource_probes,
					 TOY_FACTORY_GARDEN_LANDING_RESOURCE_COUNT,
					 &probe.resources) != 0) {
				return -EINVAL;
			}
			resources_set = true;
		} else if (watering && !arbitrating && !water_set &&
			   (strcmp(argv[i], "--water-reserve") == 0)) {
			if (parse_choice(argv[i + 1], water_modes, 2U, &water_config.enabled) !=
			    0) {
				return -EINVAL;
			}
			water_set = true;
		} else if (arbitrating && !water_set &&
			   (strcmp(argv[i], "--water-arbitration") == 0)) {
			if (parse_choice(argv[i + 1], arbitration_modes, 2U,
					 &water_config.eligible) != 0) {
				return -EINVAL;
			}
			water_set = true;
		} else if (growing && !budgeting && !limit_set &&
			   (strcmp(argv[i], "--node-limit") == 0)) {
			if (strcmp(argv[i + 1], "32") == 0) {
				node_limit = TOY_FACTORY_GARDEN_LANDING_GROWTH_LIMIT;
			} else if (strcmp(argv[i + 1], "off") != 0) {
				return -EINVAL;
			}
			limit_set = true;
		} else if (budgeting && !limit_set && (strcmp(argv[i], "--shoot-reserve") == 0)) {
			if (parse_choice(argv[i + 1], water_modes, 2U, &shoot_reserve) != 0) {
				return -EINVAL;
			}
			node_limit = TOY_FACTORY_GARDEN_LANDING_GROWTH_LIMIT;
			limit_set = true;
		} else if (placing && !placement_set &&
			   (strcmp(argv[i], "--seed-placement") == 0)) {
			if (parse_choice(argv[i + 1], placement_modes, 2U, &seed_placement) != 0) {
				return -EINVAL;
			}
			placement_set = true;
		} else if (placing && !rotation_set && (strcmp(argv[i], "--seed-order") == 0)) {
			if (strcmp(argv[i + 1], "rotating") != 0) {
				return -EINVAL;
			}
			rotation_set = true;
		} else if (placing && (rotation_after == 0U) &&
			   (strcmp(argv[i], "--seed-order-after") == 0)) {
			if ((parse_u32(argv[i + 1], MAX_TICKS, &rotation_after) != 0) ||
			    (rotation_after == 0U)) {
				return -EINVAL;
			}
		} else if (placing && (placement_path == NULL) &&
			   (strcmp(argv[i], "--placement-trace") == 0) && (*argv[i + 1] != '\0')) {
			placement_path = argv[i + 1];
		} else if (watering && (water_path == NULL) &&
			   (strcmp(argv[i], "--water-trace") == 0) && (*argv[i + 1] != '\0')) {
			water_path = argv[i + 1];
		} else {
			return -EINVAL;
		}
	}
	if (!ticks_set || !climate_set || (probing && (!occupancy_set || !resources_set)) ||
	    (watering && !water_set) || (growing && !limit_set) || (placing && !placement_set) ||
	    (tracing && (trace_path == NULL)) ||
	    (((recruitment_path != NULL) || (reach_path != NULL) || (water_path != NULL) ||
	      (placement_path != NULL)) &&
	     !export_ledger)) {
		return -EINVAL;
	}
	if (vacancy && (!export_ledger || (vacancy_lineage == 0U) ||
			(vacancy_tick <= TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS) ||
			(vacancy_tick % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR != 0U))) {
		return -EINVAL;
	}
	if (((replace_after != 0U) &&
	     (!export_ledger || (seed_placement != 1U) || (replace_after > ticks) ||
	      (replace_after % (PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR *
				PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR) !=
	       0U))) ||
	    ((replacement_path != NULL) && !export_ledger)) {
		return -EINVAL;
	}
	if (((turnover_tick != 0U) != (turnover_lineage != 0U)) ||
	    ((turnover_tick != 0U) &&
	     (!export_ledger || (turnover_tick <= TOY_FACTORY_GARDEN_LIFETIME_CYCLE_TICKS) ||
	      (turnover_tick > ticks) ||
	      (turnover_tick % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR != 0U)))) {
		return -EINVAL;
	}
	if (((second_turnover_tick != 0U) != (second_turnover_lineage != 0U)) ||
	    ((second_turnover_tick != 0U) &&
	     ((turnover_tick == 0U) || (second_turnover_tick <= turnover_tick) ||
	      (second_turnover_tick > ticks) || (second_turnover_lineage == turnover_lineage) ||
	      (second_turnover_tick % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR != 0U)))) {
		return -EINVAL;
	}
	if (((stand_choice || stand_energy || stand_afternoon || stand_daylight || stand_dawn) &&
	     ((plant_path == NULL) || stand_order || !shoot_reserve)) ||
	    (stand_choice && (stand_energy || stand_afternoon || stand_daylight || stand_dawn)) ||
	    (stand_energy && (stand_afternoon || stand_daylight || stand_dawn)) ||
	    (stand_afternoon && (stand_daylight || stand_dawn)) || (stand_daylight && stand_dawn) ||
	    (root_choice.dawn_reserve &&
	     (!root_choice.daylight_energy || ((plant_path != NULL) && !stand_dawn))) ||
	    (root_choice.wet_direction && ((plant_path != NULL) && !stand_dawn)) ||
	    ((root_allocation.version != 0U) && ((plant_path != NULL) && !stand_dawn)) ||
	    (toy_factory_garden_root_allocation_validate(
		     &root_allocation, &root_choice,
		     shoot_reserve ? TOY_FACTORY_GARDEN_BUDGET_SHOOT
				   : TOY_FACTORY_GARDEN_BUDGET_ELIGIBLE) != 0) ||
	    (root_choice.daylight_energy &&
	     (!root_choice.continuous_energy ||
	      ((plant_path != NULL) && !stand_daylight && !stand_dawn))) ||
	    (root_choice.continuous_energy && !root_choice.afternoon_reserve) ||
	    (root_choice.afternoon_reserve &&
	     (!root_choice.energy_reserve ||
	      ((plant_path != NULL) && !stand_afternoon && !stand_daylight && !stand_dawn))) ||
	    (root_choice.energy_reserve && ((plant_path != NULL) && !stand_energy &&
					    !stand_afternoon && !stand_daylight && !stand_dawn)) ||
	    (toy_factory_garden_root_choice_validate(&root_choice) != 0) ||
	    (((root_choice.tick != 0U) || root_choice.all_offspring) &&
	     (!export_ledger || !shoot_reserve ||
	      ((plant_path != NULL) && !stand_choice && !stand_energy && !stand_afternoon &&
	       !stand_daylight && !stand_dawn)))) {
		return -EINVAL;
	}
	if ((stand_order && (plant_path == NULL)) || (rotation_set != (rotation_after != 0U)) ||
	    (rotation_set &&
	     (!export_ledger || (rotation_after % (PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR *
						   PICOSYSTEM_GARDEN_MAINTENANCE_TICK_DIVISOR) !=
				 0U)))) {
		return -EINVAL;
	}
	if (adult_path != NULL) {
		if (!export_ledger || (adult_start == 0U) || (adult_stop < adult_start) ||
		    (adult_stop > ticks) ||
		    (adult_start % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR != 0U) ||
		    (adult_stop % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR != 0U)) {
			return -EINVAL;
		}
	} else if ((adult_start != 0U) || (adult_stop != 0U)) {
		return -EINVAL;
	}
	if (plant_path != NULL) {
		if (!export_ledger || (placement_path != NULL) || (plant_start == 0U) ||
		    (plant_stop < plant_start) || (plant_stop > ticks) ||
		    (plant_start % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR != 0U) ||
		    (plant_stop % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR != 0U)) {
			return -EINVAL;
		}
	} else if ((plant_start != 0U) || (plant_stop != 0U)) {
		return -EINVAL;
	}
	if ((uptake_path != NULL) != (uptake_count != 0U)) {
		return -EINVAL;
	}
	if ((direction_path != NULL) && ((plant_path == NULL) || !stand_dawn)) {
		return -EINVAL;
	}
	if (uptake_count != 0U) {
		if ((plant_path == NULL) || (uptake_windows[0].start < plant_start) ||
		    (uptake_windows[uptake_count - 1U].stop > plant_stop)) {
			return -EINVAL;
		}
	}
	struct toy_factory_garden_landing_model model;
	struct picosystem_garden_world initial;
	struct toy_factory_garden_landing_signal_run signal = {0};
	struct toy_factory_garden_landing_water_run water = {0};
	struct toy_factory_garden_landing_growth_run growth = {0};
	struct toy_factory_garden_landing_run *const run = growing    ? &growth.base
							   : watering ? &water.base
								      : &signal.base;
	int err = toy_factory_garden_landing_model_read(argv[2], &model);
	if (err == 0) {
		err = toy_factory_garden_evaluation_reset(&initial, scenario, seed);
	}
	if (err == 0) {
		err = picosystem_garden_world_set_climate(&initial, climate);
	}
	if (err == 0) {
		err = placing ? toy_factory_garden_landing_placement_init(
					&initial, &model, shoot_reserve, seed_placement, &growth)
		      : budgeting ? toy_factory_garden_landing_budget_init(&initial, &model,
									   shoot_reserve, &growth)
		      : growing   ? toy_factory_garden_landing_growth_init(&initial, &model,
									   node_limit, &growth)
		      : watering  ? toy_factory_garden_landing_water_init(&initial, &model,
									  &water_config, &water)
		      : probing   ? toy_factory_garden_landing_signal_init(&initial, &model, &probe,
									   &signal)
				  : toy_factory_garden_landing_run_init(&initial, &model, run);
	}
	if (err == 0) {
		growth.seed_order_after = rotation_after;
		growth.placement.replace_after = replace_after;
		growth.root_choice = root_choice;
		growth.root_allocation = root_allocation;
		err = toy_factory_garden_lifetimes_reset(&ledger);
	}
	if (err == 0) {
		err = record_births(&initial);
	}
	if ((err == 0) && export_ledger) {
		err = toy_factory_garden_landing_ledger_reset(&history, &initial, &ledger);
	}
	if (err != 0) {
		return err;
	}
	if ((reach_path != NULL) && (run->rules != 0U)) {
		return -ENOTSUP;
	}
	if (tracing) {
		if ((model.config.mode != TOY_FACTORY_GARDEN_LANDING_INPUT_CURRENT) ||
		    (model.config.flags != 0U)) {
			return -ENOTSUP;
		}
		decision_stream = fopen(trace_path, "wx");
		if (decision_stream == NULL) {
			return errno ? -errno : -EIO;
		}
		err = toy_factory_garden_decision_trace_init(&decision_trace, decision_stream,
							     &model);
		if (err != 0) {
			return err;
		}
	}
	uint64_t descendant_live_ticks = 0U;
	if (replacement_path != NULL) {
		replacement_stream = fopen(replacement_path, "wx");
		if (replacement_stream == NULL) {
			return errno ? -errno : -EIO;
		}
		fprintf(replacement_stream,
			"{\"schema\":\"landing-seed-replacement-trace-v1\","
			"\"after\":%" PRIu32 "}\n",
			replace_after);
	}
	if (placement_path != NULL) {
		placement_stream = fopen(placement_path, "wx");
		if (placement_stream == NULL) {
			return errno ? -errno : -EIO;
		}
		fprintf(placement_stream,
			"{\"schema\":\"landing-placement-trace-v1\",\"enabled\":%s}\n",
			seed_placement ? "true" : "false");
	}
	if (water_path != NULL) {
		water_stream = fopen(water_path, "wx");
		if (water_stream == NULL) {
			return errno ? -errno : -EIO;
		}
		if (arbitrating) {
			fprintf(water_stream,
				"{\"schema\":\"landing-arbitration-trace-v1\",\"arbitration\":\"%"
				"s\"}\n",
				arbitration_modes[water_config.eligible]);
		} else {
			fprintf(water_stream,
				"{\"schema\":\"landing-water-trace-v1\",\"enabled\":%s}\n",
				water_config.enabled ? "true" : "false");
		}
	}
	if (recruitment_path != NULL) {
		recruitment_stream = fopen(recruitment_path, "wx");
		if (recruitment_stream == NULL) {
			return errno ? -errno : -EIO;
		}
		fputs("{\"schema\":\"landing-recruitment-trace-v1\"}\n", recruitment_stream);
	}
	if (reach_path != NULL) {
		reach_stream = fopen(reach_path, "wx");
		if (reach_stream == NULL) {
			return errno ? -errno : -EIO;
		}
		fputs("{\"schema\":\"landing-reach-trace-v1\"}\n", reach_stream);
	}
	if (adult_path != NULL) {
		adult_stream = fopen(adult_path, "wx");
		if (adult_stream == NULL) {
			return errno ? -errno : -EIO;
		}
		fprintf(adult_stream,
			"{\"schema\":\"landing-adult-resources-v1\","
			"\"start\":%" PRIu32 ",\"stop\":%" PRIu32 "}\n",
			adult_start, adult_stop);
	}
	if (plant_path != NULL) {
		plant_stream = fopen(plant_path, "wx");
		if (plant_stream == NULL) {
			return errno ? -errno : -EIO;
		}
		err = toy_factory_garden_plant_trace_init(
			&plant_trace, plant_stream, &initial, node_limit, growth.budget_mode,
			plant_start, plant_stop,
			stand_dawn        ? TOY_FACTORY_GARDEN_TRACE_DAWN
			: stand_daylight  ? TOY_FACTORY_GARDEN_TRACE_DAYLIGHT
			: stand_afternoon ? TOY_FACTORY_GARDEN_TRACE_AFTERNOON
			: stand_energy    ? TOY_FACTORY_GARDEN_TRACE_ENERGY
			: stand_choice    ? TOY_FACTORY_GARDEN_TRACE_CHOICE
			: stand_order     ? TOY_FACTORY_GARDEN_TRACE_ORDERED
			: placing         ? TOY_FACTORY_GARDEN_TRACE_ALL
					  : TOY_FACTORY_GARDEN_TRACE_FOUNDERS);
		if (err != 0) {
			return err;
		}
		plant_trace.root_choice = root_choice;
		plant_trace.root_allocation = root_allocation;
	}
	if (direction_path != NULL) {
		direction_stream = fopen(direction_path, "wx");
		if (direction_stream == NULL) {
			return errno ? -errno : -EIO;
		}
		fprintf(direction_stream,
			"{\"schema\":\"%s\",\"start\":%" PRIu32 ",\"stop\":%" PRIu32 "}\n",
			root_choice.wet_direction ? "landing-root-directions-v1"
						  : "landing-directions-v1",
			plant_start, plant_stop);
		if (ferror(direction_stream)) {
			return -EIO;
		}
		plant_trace.directions_enabled = true;
	}
	if (uptake_path != NULL) {
		uptake_stream = fopen(uptake_path, "wx");
		if (uptake_stream == NULL) {
			return errno ? -errno : -EIO;
		}
		err = toy_factory_garden_uptake_header(uptake_stream, uptake_windows, uptake_count,
						       ticks);
		if (err != 0) {
			return err;
		}
	}
	struct toy_factory_garden_growth_observer plant_observer = {
		.observe = toy_factory_garden_plant_trace_observe,
		.context = &plant_trace,
		.reproduction = &plant_trace.reproduction};
	for (uint32_t tick = 0U; tick < ticks; ++tick) {
		struct picosystem_garden_death_audit deaths;
		struct picosystem_garden_seed_audit seeds;
		struct picosystem_garden_resource_audit resources;
		struct toy_factory_garden_landing_water_audit water_audit;
		struct toy_factory_garden_placement_audit placement_audit;
		const bool observe_plants =
			(plant_stream != NULL) && (tick + 1U >= plant_start) &&
			(tick + 1U <= plant_stop) &&
			((tick + 1U) % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR == 0U);
		if (observe_plants) {
			plant_trace.count = 0U;
			plant_observer.uptake = toy_factory_garden_uptake_selected(
							uptake_windows, uptake_count, tick + 1U)
							? &uptake_audit
							: NULL;
			err = toy_factory_garden_landing_growth_step_observed(
				&growth, &deaths, &seeds, &resources, &plant_observer);
		} else if (placement_stream != NULL) {
			err = toy_factory_garden_landing_growth_step_placement(
				&growth, &deaths, &seeds,
				((recruitment_stream != NULL) || (adult_stream != NULL))
					? &resources
					: NULL,
				&placement_audit);
		} else if (growing) {
			err = toy_factory_garden_landing_growth_step(
				&growth, &deaths, &seeds,
				((recruitment_stream != NULL) || (adult_stream != NULL))
					? &resources
					: NULL);
		} else if (watering) {
			err = toy_factory_garden_landing_water_step(
				&water, &deaths, &seeds,
				((recruitment_stream != NULL) || (adult_stream != NULL))
					? &resources
					: NULL,
				(water_stream != NULL) ? &water_audit : NULL);
		} else if ((recruitment_stream != NULL) || (adult_stream != NULL)) {
			err = toy_factory_garden_landing_run_step_resources(run, &deaths, &seeds,
									    &resources);
		} else if (tracing) {
			decision_trace.tick = tick + 1U;
			err = toy_factory_garden_landing_run_step_observed(
				run, &deaths, &seeds, toy_factory_garden_decision_trace_observe,
				&decision_trace);
			if (err == 0) {
				err = toy_factory_garden_decision_trace_publish(&decision_trace);
			}
		} else if (probing) {
			err = toy_factory_garden_landing_signal_step(&signal, &deaths, &seeds);
		} else {
			err = export_ledger
				      ? toy_factory_garden_landing_run_step_audits(run, &deaths,
										   &seeds)
				      : toy_factory_garden_landing_run_step_death_audit(run,
											&deaths);
		}
		if (err != 0) {
			return err;
		}
		for (uint8_t d = 0U; d < deaths.count; ++d) {
			err = toy_factory_garden_lifetimes_death(
				&ledger, deaths.events[d].lineage_id, run->world.logic_tick_count,
				deaths.events[d].flags);
			if (err != 0) {
				return err;
			}
		}
		if (deaths.ecology_step) {
			err = record_births(&run->world);
			if ((err == 0) && export_ledger) {
				err = toy_factory_garden_landing_ledger_step(&history, &run->world,
									     &ledger, &seeds);
			}
			if ((err == 0) && (recruitment_stream != NULL)) {
				err = toy_factory_garden_recruitment_print(recruitment_stream,
									   &run->world, &ledger,
									   &seeds, &resources);
			}
			if ((err == 0) && (reach_stream != NULL)) {
				err = toy_factory_garden_reach_print(reach_stream, &run->world,
								     &seeds);
			}
			if ((err == 0) && (replacement_stream != NULL)) {
				err = toy_factory_garden_landing_replacements_print(
					replacement_stream, run->world.logic_tick_count, &seeds);
			}
			if ((err == 0) && (placement_stream != NULL)) {
				err = toy_factory_garden_placement_print(
					placement_stream, run->world.logic_tick_count,
					&placement_audit);
			}
			if ((err == 0) && (adult_stream != NULL) &&
			    (run->world.logic_tick_count >= adult_start) &&
			    (run->world.logic_tick_count <= adult_stop)) {
				err = toy_factory_garden_adult_resources_print(
					adult_stream, &run->world, &ledger, &seeds, &resources);
			}
			if ((err == 0) && (water_stream != NULL)) {
				err = toy_factory_garden_landing_water_print(water_stream, &water,
									     &water_audit);
			}
			if ((err == 0) && observe_plants) {
				err = toy_factory_garden_plant_trace_publish(&plant_trace,
									     &run->world);
				if ((err == 0) && (direction_stream != NULL)) {
					err = toy_factory_garden_plant_directions_publish(
						&plant_trace, &run->world, direction_stream);
				}
				if ((err == 0) && (plant_observer.uptake != NULL)) {
					err = toy_factory_garden_uptake_print(uptake_stream,
									      &uptake_audit);
				}
			}
			if (err != 0) {
				return err;
			}
		}
		if (vacancy && (run->world.logic_tick_count == vacancy_tick)) {
			err = toy_factory_garden_landing_vacancy_apply(
				&growth, &ledger, vacancy_lineage, &vacancy_event);
			if (err != 0) {
				return err;
			}
		}
		if ((turnover_tick != 0U) && (run->world.logic_tick_count == turnover_tick)) {
			err = toy_factory_garden_landing_turnover_apply(
				&growth, &ledger, turnover_lineage, &turnover_event);
			if (err != 0) {
				return err;
			}
		}
		if ((second_turnover_tick != 0U) &&
		    (run->world.logic_tick_count == second_turnover_tick)) {
			err = toy_factory_garden_landing_turnover_apply(
				&growth, &ledger, second_turnover_lineage, &second_turnover_event);
			if (err != 0) {
				return err;
			}
		}
		descendant_live_ticks += descendants(&run->world);
	}
	struct toy_factory_garden_lifetime_report report;
	err = toy_factory_garden_lifetimes_summarize(&ledger, ticks, &report);
	const struct picosystem_garden_world *const world = &run->world;
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
	err = replay_hash(&signal, probing, &water, watering, &growth, growing, &hash);
	uint32_t base_hash;
	if ((err == 0) && (watering || growing)) {
		err = toy_factory_garden_landing_run_hash(run, &base_hash);
	}
	uint32_t framebuffer_crc = 0U;
	if ((err == 0) && (framebuffer != NULL)) {
		err = toy_factory_garden_capture(world, framebuffer, &framebuffer_crc);
		uint32_t after;
		if ((err == 0) && ((replay_hash(&signal, probing, &water, watering, &growth,
						growing, &after) != 0) ||
				   (after != hash))) {
			err = -EFAULT;
		}
	}
	if (err != 0) {
		return err;
	}
	const uint32_t placement_hash = hash;
	if (vacancy) {
		hash = toy_factory_garden_landing_vacancy_hash(hash, vacancy_tick, vacancy_lineage);
	}
	if (turnover_tick != 0U) {
		hash = toy_factory_garden_landing_turnover_hash(hash, turnover_tick,
								turnover_lineage);
	}
	if (second_turnover_tick != 0U) {
		hash = toy_factory_garden_landing_turnover_hash(hash, second_turnover_tick,
								second_turnover_lineage);
	}
	if (tracing) {
		err = toy_factory_garden_decision_trace_finish(&decision_trace, ticks, hash);
		if (err != 0) {
			return err;
		}
	}
	printf("{\"schema_version\":1,\"kind\":\"%s\",\"run_version\":%u,"
	       "\"rules\":%" PRIu32 ",\"scenario\":\"%s\",\"seed\":\"%08" PRIx32
	       "\",\"tick\":%" PRIu32 ",\"world_hash\":\"%08" PRIx32 "\",\"run_hash\":\"%08" PRIx32
	       "\",\"model\":",
	       second_turnover_tick ? "landing-turnover-pair-replay"
	       : turnover_tick      ? "landing-turnover-replay"
	       : vacancy            ? "landing-vacancy-replay"
	       : placing            ? "landing-placement-replay"
	       : budgeting          ? "landing-budget-replay"
	       : growing            ? "landing-growth-replay"
	       : arbitrating        ? "landing-arbitration-replay"
	       : watering           ? "landing-water-replay"
	       : probing            ? "landing-signal-replay"
				    : "landing-replay",
	       run->version, run->rules, scenario->name, seed, ticks,
	       picosystem_garden_world_hash(world), hash);
	err = print_model(&model);
	putchar(',');
#if defined(TOY_FACTORY_GARDEN_SOIL_WICKING)
	printf("\"soil_wicking_probe\":{\"version\":%u,\"after\":%" PRIu32
	       ",\"period\":%u,\"limit\":1},",
	       PICOSYSTEM_GARDEN_WICKING_VERSION, PICOSYSTEM_GARDEN_WICKING_AFTER_TICK,
	       PICOSYSTEM_GARDEN_WICKING_PERIOD);
#endif
#if defined(TOY_FACTORY_GARDEN_LATE_UPTAKE_LIMIT)
	printf("\"uptake_limit_probe\":{\"version\":%u,\"after\":%" PRIu32 ",\"capacity\":%u},",
	       PICOSYSTEM_GARDEN_UPTAKE_LIMIT_VERSION, PICOSYSTEM_GARDEN_UPTAKE_LIMIT_AFTER_TICK,
	       PICOSYSTEM_GARDEN_UPTAKE_LIMIT_CAPACITY);
#endif
#if defined(TOY_FACTORY_GARDEN_LATE_DISPERSAL)
	printf("\"late_dispersal_probe\":{\"version\":%u,\"after\":%" PRIu32
	       ",\"minimum\":%u,\"distances\":%u},",
	       PICOSYSTEM_GARDEN_LATE_DISPERSAL_VERSION,
	       PICOSYSTEM_GARDEN_LATE_DISPERSAL_AFTER_TICK,
	       PICOSYSTEM_GARDEN_LATE_DISPERSAL_MINIMUM,
	       PICOSYSTEM_GARDEN_LATE_DISPERSAL_DISTANCES);
#endif
	if (root_choice.tick != 0U) {
		printf("\"root_choice_probe\":{\"version\":1,\"tick\":%" PRIu32
		       ",\"lineage\":%" PRIu32 "},",
		       root_choice.tick, root_choice.lineage);
	}
	if (root_choice.all_offspring) {
		fputs("\"root_all_offspring_probe\":{\"version\":1},", stdout);
	}
	if (root_choice.energy_reserve) {
		fputs("\"root_energy_probe\":{\"version\":1},", stdout);
	}
	if (root_choice.afternoon_reserve) {
		fputs("\"root_afternoon_probe\":{\"version\":1},", stdout);
	}
	if (root_choice.continuous_energy) {
		fputs("\"root_continuous_energy_probe\":{\"version\":1},", stdout);
	}
	if (root_choice.daylight_energy) {
		fputs("\"root_daylight_energy_probe\":{\"version\":1},", stdout);
	}
	if (root_choice.dawn_reserve) {
		fputs("\"root_dawn_reserve_probe\":{\"version\":1},", stdout);
	}
	if (root_choice.wet_direction) {
		fputs("\"root_wet_direction_probe\":{\"version\":1},", stdout);
	}
	if (root_allocation.version != 0U) {
		printf("\"root_allocation_probe\":{\"version\":%" PRIu32 ",\"lineage\":%" PRIu32
		       ",\"birth_tick\":%" PRIu32 ",\"parent\":%" PRIu32 ",\"generation\":%" PRIu32
		       ",\"column\":%" PRIu32 ",\"species\":%" PRIu32 "},",
		       root_allocation.version, root_allocation.lineage, root_allocation.birth_tick,
		       root_allocation.parent, root_allocation.generation, root_allocation.column,
		       root_allocation.species);
	}
	if (rotation_set) {
		printf("\"seed_order_probe\":{\"version\":1,\"after\":%" PRIu32 "},",
		       rotation_after);
	}
	if (vacancy && (err == 0)) {
		err = toy_factory_garden_landing_vacancy_print(stdout, vacancy_tick,
							       vacancy_lineage, &vacancy_event);
		printf("\"placement_run_hash\":\"%08" PRIx32 "\",", placement_hash);
	}
	if (replace_after != 0U) {
		printf("\"seed_replacement_probe\":{\"version\":1,\"after\":%" PRIu32 "},",
		       replace_after);
	}
	if ((turnover_tick != 0U) && (err == 0)) {
		err = toy_factory_garden_landing_turnover_print(stdout, &turnover_event);
		printf("\"placement_run_hash\":\"%08" PRIx32 "\",", placement_hash);
	}
	if ((second_turnover_tick != 0U) && (err == 0)) {
		err = toy_factory_garden_landing_turnover_print_second(stdout,
								       &second_turnover_event);
	}
	if (placing) {
		printf("\"placement_probe\":{\"version\":%u,\"enabled\":%s},",
		       growth.placement.version, seed_placement ? "true" : "false");
	}
	if (budgeting) {
		printf("\"budget_probe\":{\"version\":%u,\"node_limit\":%u,"
		       "\"shoot_reserve\":%s,\"water_arbitration\":\"eligible\"},"
		       "\"base_run_hash\":\"%08" PRIx32 "\",",
		       growth.version, growth.node_limit, shoot_reserve ? "true" : "false",
		       base_hash);
	} else if (growing) {
		printf("\"growth_probe\":{\"version\":%u,\"node_limit\":%u,"
		       "\"water_arbitration\":\"eligible\"},\"base_run_hash\":\"%08" PRIx32 "\",",
		       growth.version, growth.node_limit, base_hash);
	}
	if (watering) {
		printf("\"water_probe\":{\"version\":%u,\"enabled\":%s", water_config.version,
		       water_config.enabled ? "true" : "false");
		if (arbitrating) {
			printf(",\"arbitration\":\"%s\"", arbitration_modes[water_config.eligible]);
		}
		printf("},\"base_run_hash\":\"%08" PRIx32 "\",", base_hash);
	}
	if (probing) {
		printf("\"signal_probe\":{\"version\":%u,\"occupancy\":\"%s\",\"resources\":\"%s\"}"
		       ",",
		       probe.version, occupancy_probes[probe.occupancy],
		       resource_probes[probe.resources]);
	}
	toy_factory_garden_climate_print(stdout, world);
	printf("\"gardener\":false,\"irrigation\":false,\"warmup_samples\":%u,"
	       "\"living\":%u,\"descendants\":%u,\"plant_slots\":%u,\"nodes\":%u,"
	       "\"seed_bank\":%u,\"births\":%" PRIu32 ",\"deaths\":%" PRIu32
	       ",\"moisture\":%u,\"rain_deposited\":%" PRIu32 ",\"rain_runoff\":%" PRIu32
	       ",\"descendant_live_ticks\":%" PRIu64 ",\"lifetimes\":",
	       run->cache.warmup_samples, picosystem_garden_world_living_plant_count(world),
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
	if (export_ledger) {
		putchar(',');
		err = toy_factory_garden_landing_ledger_print_environmental_pair(
			stdout, &history, &ledger, turnover_lineage, second_turnover_lineage);
	}
	puts("}");
	if ((err == 0) && (replacement_stream != NULL)) {
		fprintf(replacement_stream, "{\"complete\":true,\"tick\":%" PRIu32 "}\n", ticks);
		if (ferror(replacement_stream)) {
			err = -EIO;
		}
	}
	if ((err == 0) && (placement_stream != NULL)) {
		fprintf(placement_stream, "{\"complete\":true,\"tick\":%" PRIu32 "}\n", ticks);
		if (ferror(placement_stream)) {
			err = -EIO;
		}
	}
	if ((err == 0) && (recruitment_stream != NULL)) {
		fprintf(recruitment_stream, "{\"complete\":true,\"tick\":%" PRIu32 "}\n", ticks);
		if (ferror(recruitment_stream)) {
			err = -EIO;
		}
	}
	if ((err == 0) && (reach_stream != NULL)) {
		fprintf(reach_stream, "{\"complete\":true,\"tick\":%" PRIu32 "}\n", ticks);
		if (ferror(reach_stream)) {
			err = -EIO;
		}
	}
	if ((err == 0) && (water_stream != NULL)) {
		fprintf(water_stream, "{\"complete\":true,\"tick\":%" PRIu32 "}\n", ticks);
		if (ferror(water_stream)) {
			err = -EIO;
		}
	}
	if ((err == 0) && (adult_stream != NULL)) {
		fprintf(adult_stream, "{\"complete\":true,\"tick\":%" PRIu32 "}\n", ticks);
		if (ferror(adult_stream)) {
			err = -EIO;
		}
	}
	if ((err == 0) && (plant_stream != NULL)) {
		fprintf(plant_stream,
			"{\"complete\":true,\"tick\":%" PRIu32 ",\"run_hash\":\"%08" PRIx32 "\"}\n",
			ticks, hash);
		if (ferror(plant_stream)) {
			err = -EIO;
		}
	}
	if ((err == 0) && (direction_stream != NULL)) {
		fprintf(direction_stream,
			"{\"complete\":true,\"tick\":%" PRIu32 ",\"run_hash\":\"%08" PRIx32 "\"}\n",
			ticks, hash);
		if (ferror(direction_stream)) {
			err = -EIO;
		}
	}
	if ((err == 0) && (uptake_stream != NULL)) {
		fprintf(uptake_stream,
			"{\"complete\":true,\"tick\":%" PRIu32 ",\"run_hash\":\"%08" PRIx32 "\"}\n",
			ticks, hash);
		if (ferror(uptake_stream)) {
			err = -EIO;
		}
	}
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
			err = replay(argc, argv, false, false, false, false, false);
		} else if (strcmp(argv[1], "probe-replay") == 0) {
			err = replay(argc, argv, true, false, false, false, false);
		} else if (strcmp(argv[1], "trace-replay") == 0) {
			err = replay(argc, argv, false, true, false, false, false);
		} else if (strcmp(argv[1], "water-replay") == 0) {
			err = replay(argc, argv, false, false, true, false, false);
		} else if (strcmp(argv[1], "arbitration-replay") == 0) {
			err = replay(argc, argv, false, false, true, true, false);
		} else if ((strcmp(argv[1], "growth-replay") == 0) ||
			   (strcmp(argv[1], "budget-replay") == 0) ||
			   (strcmp(argv[1], "placement-replay") == 0) ||
			   (strcmp(argv[1], "vacancy-replay") == 0)) {
			err = replay(argc, argv, false, false, false, false, true);
		} else if (strcmp(argv[1], "mutate") == 0) {
			err = mutate_model(argc, argv);
		} else if (strcmp(argv[1], "ablate") == 0) {
			err = ablate_model(argc, argv);
		}
	}
	if ((decision_stream != NULL) && (fclose(decision_stream) != 0)) {
		err = -EIO;
	}
	if ((recruitment_stream != NULL) && (fclose(recruitment_stream) != 0)) {
		err = -EIO;
	}
	if ((reach_stream != NULL) && (fclose(reach_stream) != 0)) {
		err = -EIO;
	}
	if ((water_stream != NULL) && (fclose(water_stream) != 0)) {
		err = -EIO;
	}
	if ((adult_stream != NULL) && (fclose(adult_stream) != 0)) {
		err = -EIO;
	}
	if ((plant_stream != NULL) && (fclose(plant_stream) != 0)) {
		err = -EIO;
	}
	if ((replacement_stream != NULL) && (fclose(replacement_stream) != 0)) {
		err = -EIO;
	}
	if ((placement_stream != NULL) && (fclose(placement_stream) != 0)) {
		err = -EIO;
	}
	if ((uptake_stream != NULL) && (fclose(uptake_stream) != 0)) {
		err = -EIO;
	}
	if ((direction_stream != NULL) && (fclose(direction_stream) != 0)) {
		err = -EIO;
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
