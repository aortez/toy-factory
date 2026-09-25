/* SPDX-License-Identifier: Apache-2.0 */
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "garden_allocation_policy.h"
#include "garden_disturbance.h"
#include "garden_leaf_policies.h"
#include "garden_light.h"
#include "garden_model_file.h"
#include "garden_policy_probe.h"
#include "garden_reserve_policy.h"
#include "garden_root_bootstrap.h"
#include "game_snapshot.h"
#include "graphics_raster.h"

#if !defined(TOY_FACTORY_GARDEN_SEED_RESERVE) || !defined(TOY_FACTORY_GARDEN_LARGE_POOL) ||        \
	defined(TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE)
#error "Allocation challenge requires the undrained 512-node seed-reserve host experiment"
#endif

#define DAY_TICKS  3840U
#define ROOT_AFTER 614400U
#define PATCH_SEED UINT32_C(0xe4d65e6f)

struct policy_stack {
	struct picosystem_garden_agent_policy neural;
	struct picosystem_garden_agent_policy night;
	struct picosystem_garden_agent_policy guarded;
	struct picosystem_garden_agent_policy root;
	struct toy_factory_garden_root_bootstrap_context root_context;
};

struct recording {
	const char *arm;
	const char *directory;
	uint32_t lineage;
	uint32_t birth;
	uint32_t end;
	bool dawn_seen;
};

static int parse_u32(const char *text, uint32_t maximum, uint32_t *value)
{
	if ((*text < '0') || (*text > '9')) {
		return -EINVAL;
	}
	errno = 0;
	char *end;
	const unsigned long result = strtoul(text, &end, 0);
	if ((errno != 0) || (*end != '\0') || (result > maximum)) {
		return -ERANGE;
	}
	*value = (uint32_t)result;
	return 0;
}

static int stack_init(const struct picosystem_garden_neural_model *model,
		      const struct picosystem_garden_world *world, bool reserve,
		      uint32_t root_after, struct policy_stack *stack)
{
	int err = picosystem_garden_neural_policy_init(model, &stack->neural);
	if (err == 0) {
		err = toy_factory_garden_no_night_growth_init(&stack->neural, &stack->night);
	}
	if ((err == 0) && reserve) {
		err = toy_factory_garden_reserve_init(&stack->night, &stack->guarded);
	} else if (err == 0) {
		stack->guarded = stack->night;
	}
	if (err == 0) {
		stack->guarded.leaf_policy = toy_factory_garden_leaf_policy("selective");
		err = toy_factory_garden_root_bootstrap_init(&stack->guarded, world, root_after,
							     &stack->root_context, &stack->root);
	}
	return err;
}

static int wait_decide(const struct picosystem_garden_agent_observation *observation,
		       const struct picosystem_garden_agent_memory *memory,
		       struct picosystem_garden_agent_decision *decision, const void *context)
{
	(void)context;
	*decision = (struct picosystem_garden_agent_decision){
		.next_memory = *memory,
		.proposal = {.tip_index = observation->tip_index,
			     .action = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT}};
	return 0;
}

static const struct picosystem_garden_plant *target(const struct picosystem_garden_world *world,
						    uint32_t lineage, uint8_t *index)
{
	for (uint8_t i = 0U; i < world->plant_count; ++i) {
		if (world->plants[i].lineage_id == lineage) {
			*index = i;
			return &world->plants[i];
		}
	}
	return NULL;
}

static int sample(const struct picosystem_garden_world *world, const struct recording *recording,
		  const char *stage)
{
	const struct picosystem_garden_sun sun =
		picosystem_garden_sun_at(world->ecology_tick_count);
	printf("{\"type\":\"sample\",\"arm\":\"%s\",\"stage\":\"%s\",\"tick\":%" PRIu32
	       ",\"hash\":\"%08" PRIx32 "\",\"sun_phase\":%u,\"living\":%u,\"births\":%" PRIu32
	       ",\"deaths\":%" PRIu32 ",\"rain_deposited\":%" PRIu32 ",\"rain_runoff\":%" PRIu32
	       ",\"manual_actions\":%" PRIu32 ",\"auto_actions\":%" PRIu32 ",\"new_children\":[",
	       recording->arm, stage, world->logic_tick_count, picosystem_garden_world_hash(world),
	       sun.phase, picosystem_garden_world_living_plant_count(world),
	       world->germination_count, world->death_count, world->rain_deposited,
	       world->rain_runoff, world->manual_action_count, world->auto_action_count);
	bool first_child = true;
	for (uint8_t i = 0U; i < world->plant_count; ++i) {
		const struct picosystem_garden_plant *child = &world->plants[i];
		if ((child->parent_lineage_id == recording->lineage) &&
		    (child->age_ecology_ticks == 1U) &&
		    ((child->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) == 0U)) {
			printf("%s%" PRIu32, first_child ? "" : ",", child->lineage_id);
			first_child = false;
		}
	}
	printf("],\"plant\":");
	uint8_t index = 0U;
	const struct picosystem_garden_plant *p = target(world, recording->lineage, &index);
	if (p == NULL) {
		printf("null}\n");
		return ferror(stdout) ? -EIO : 0;
	}
	unsigned int roots = 0U;
	unsigned int leaves = 0U;
	unsigned int tips = 0U;
	for (uint16_t i = 0U; i < world->node_count; ++i) {
		const struct picosystem_garden_node *n = &world->nodes[i];
		if (n->plant_index == index) {
			roots += n->kind == PICOSYSTEM_GARDEN_NODE_ROOT ? 1U : 0U;
			tips += (n->flags & PICOSYSTEM_GARDEN_NODE_TIP) != 0U ? 1U : 0U;
			leaves += ((n->flags & PICOSYSTEM_GARDEN_NODE_LEAF) != 0U) &&
						  (n->growth_progress >=
						   PICOSYSTEM_GARDEN_LEAF_ACTIVE_PROGRESS)
					  ? 1U
					  : 0U;
		}
	}
	printf("{\"id\":%" PRIu32 ",\"parent\":%" PRIu32 ",\"species\":\"%s\",\"generation\":%u,"
	       "\"age_ecology_ticks\":%" PRIu32
	       ",\"column\":%u,\"dead\":%s,\"energy\":%u,\"water\":%u,"
	       "\"energy_income\":%u,\"water_income\":%u,\"stress\":%u,\"flags\":%u,\"vigor\":%d,"
	       "\"nodes\":%u,\"roots\":%u,\"active_leaves\":%u,\"tips\":%u,"
	       "\"offspring\":%u,\"reproduction_cooldown\":%u,\"leaf\":{\"renewals\":%" PRIu32 "},"
	       "\"agent\":{\"decisions\":%" PRIu32 ",\"extend\":%" PRIu32
	       ",\"root_extend\":%" PRIu32 ",\"shoot_extend\":%" PRIu32 ",\"finish\":%" PRIu32
	       ",\"wait\":%" PRIu32 "}}}\n",
	       p->lineage_id, p->parent_lineage_id,
	       picosystem_garden_species_name((enum picosystem_garden_species_id)p->species_id),
	       p->generation, p->age_ecology_ticks, p->base_column,
	       (p->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) != 0U ? "true" : "false", p->stored_energy,
	       p->stored_water, p->last_energy_income, p->last_water_income, p->stress, p->flags,
	       p->vigor, p->node_count, roots, leaves, tips, p->offspring_count,
	       p->reproduction_cooldown, p->leaf_telemetry.renewals,
	       p->agent_telemetry.decision_count, p->agent_telemetry.extend_count,
	       p->agent_telemetry.root_extend_count, p->agent_telemetry.shoot_extend_count,
	       p->agent_telemetry.finish_count, p->agent_telemetry.wait_count);
	return ferror(stdout) ? -EIO : 0;
}

static int capture(const struct picosystem_garden_world *world, const struct recording *recording,
		   const char *milestone)
{
	if (strcmp(recording->directory, "-") == 0) {
		return 0;
	}
	/* Same native snapshot/raster adapter as garden-replay; one renderer owner. */
	const struct picosystem_game_world render_world = {
		.garden = *world,
		.logic_tick_count = world->logic_tick_count,
		.scene_id = PICOSYSTEM_GAME_SCENE_GARDEN};
	const uint32_t before = picosystem_garden_world_hash(world);
	struct picosystem_scene_snapshot snapshot;
	int err = picosystem_game_snapshot_build(&render_world, 1U, 0U,
						 (int64_t)world->logic_tick_count, &snapshot);
	if (err == 0) {
		err = picosystem_scene_render_full(&snapshot);
	}
	if (err != 0) {
		return err;
	}
	if ((picosystem_garden_world_hash(world) != before) ||
	    (picosystem_garden_world_hash(&render_world.garden) != before)) {
		return -EFAULT;
	}
	char path[1024];
	const int length = snprintf(path, sizeof(path), "%s/%s.%s.rgb565", recording->directory,
				    recording->arm, milestone);
	if ((length < 0) || ((size_t)length >= sizeof(path))) {
		return -ENAMETOOLONG;
	}
	FILE *stream = fopen(path, "wbx");
	if (stream == NULL) {
		return errno != 0 ? -errno : -EIO;
	}
	const size_t bytes = picosystem_graphics_raster_byte_count();
	const size_t written = fwrite(picosystem_graphics_raster_bytes(), 1U, bytes, stream);
	const int closed = fclose(stream);
	if ((written != bytes) || (closed != 0)) {
		return -EIO;
	}
	printf("{\"type\":\"frame\",\"arm\":\"%s\",\"milestone\":\"%s\",\"tick\":%" PRIu32
	       ",\"hash\":\"%08" PRIx32 "\",\"framebuffer_crc32\":\"%08" PRIx32 "\"}\n",
	       recording->arm, milestone, world->logic_tick_count, before,
	       picosystem_graphics_raster_crc32());
	return ferror(stdout) ? -EIO : 0;
}

static int observe(const struct picosystem_garden_world *world, bool ecology, void *opaque)
{
	struct recording *r = opaque;
	if (!ecology) {
		return 0;
	}
	uint8_t index = 0U;
	const struct picosystem_garden_plant *p = target(world, r->lineage, &index);
	if ((world->logic_tick_count == r->birth) &&
	    ((p == NULL) || (p->age_ecology_ticks != 1U) || (p->generation == 0U))) {
		return -ENOENT;
	}
	int err = sample(world, r, "ecology");
	const char *milestone = world->logic_tick_count == r->birth               ? "birth"
				: world->logic_tick_count == r->birth + DAY_TICKS ? "day1"
				: world->logic_tick_count == r->end               ? "day8"
										  : NULL;
	if ((err == 0) && (milestone != NULL)) {
		err = capture(world, r, milestone);
	}
	if (!r->dawn_seen && (world->logic_tick_count > r->birth) &&
	    (picosystem_garden_sun_at(world->ecology_tick_count).phase == 0U)) {
		r->dawn_seen = true;
		if (err == 0) {
			err = capture(world, r, "dawn");
		}
	}
	return err;
}

static int observe_patch(const struct picosystem_garden_world *world,
			 const struct toy_factory_garden_disturbance_event *event, void *opaque)
{
	const int err = toy_factory_garden_disturbance_print(event);
	return err == 0 ? sample(world, opaque, "patch") : err;
}

int main(int argc, char **argv)
{
	if (argc != 10) {
		const bool help = argc == 2 && strcmp(argv[1], "--help") == 0;
		fprintf(help ? stdout : stderr,
			"Usage: %s REFERENCE_MODEL CANDIDATE_MODEL WORLD_SEED neural|reserve "
			"ROOT_AFTER LINEAGE BIRTH_TICK END_TICK FRAME_DIRECTORY|-\n"
			"Fork one seedling from birth; fixed eight-day follow-up, patch schedule, "
			"rainfed-crowded ecology. ROOT_AFTER must be 0 or 614400.\n"
			"Arms: reference, wet-root, wait, candidate. Existing frame paths fail.\n",
			argv[0]);
		return help ? 0 : 2;
	}
	uint32_t seed, root_after, lineage, birth, end;
	if ((parse_u32(argv[3], UINT32_MAX, &seed) != 0) || (seed == 0U) ||
	    ((strcmp(argv[4], "neural") != 0) && (strcmp(argv[4], "reserve") != 0)) ||
	    (parse_u32(argv[5], ROOT_AFTER, &root_after) != 0) ||
	    ((root_after != 0U) && (root_after != ROOT_AFTER)) ||
	    (parse_u32(argv[6], UINT32_MAX, &lineage) != 0) || (lineage == 0U) ||
	    (parse_u32(argv[7], TOY_FACTORY_GARDEN_DISTURBANCE_MAX_TICKS, &birth) != 0) ||
	    (parse_u32(argv[8], TOY_FACTORY_GARDEN_DISTURBANCE_MAX_TICKS, &end) != 0) ||
	    (birth <= ROOT_AFTER) || ((birth % 15U) != 0U) || (end != birth + 8U * DAY_TICKS) ||
	    (*argv[9] == '\0')) {
		return 2;
	}
	struct picosystem_garden_neural_model reference_model, candidate_model;
	uint32_t reference_crc, candidate_crc;
	int err = toy_factory_garden_model_read(argv[1], &reference_model, &reference_crc);
	if (err == 0) {
		err = toy_factory_garden_model_read(argv[2], &candidate_model, &candidate_crc);
	}
	struct picosystem_garden_world world;
	struct policy_stack reference, wet_root, candidate;
	const bool reserve = strcmp(argv[4], "reserve") == 0;
	if (err == 0) {
		err = stack_init(&reference_model, &world, reserve, root_after, &reference);
	}
	if (err == 0) {
		err = stack_init(&reference_model, &world, reserve, ROOT_AFTER, &wet_root);
	}
	if (err == 0) {
		err = stack_init(&candidate_model, &world, reserve, 0U, &candidate);
	}
	const struct toy_factory_garden_evaluation_scenario *scenario =
		&toy_factory_garden_rainfed_scenarios[1];
	if (err == 0) {
		err = toy_factory_garden_evaluation_reset(&world, scenario, seed);
	}
	struct toy_factory_garden_disturbance_totals totals;
	if (err == 0) {
		err = toy_factory_garden_disturbance_advance(&world, scenario, &reference.root,
							     birth - 15U, PATCH_SEED, NULL, NULL,
							     NULL, &totals);
	}
	uint8_t index = 0U;
	if ((err == 0) && (target(&world, lineage, &index) != NULL)) {
		err = -EEXIST;
	}
	if (err != 0) {
		fprintf(stderr, "Allocation setup failed (%d)\n", err);
		return 1;
	}
	/* World owns all mutable state, no internal pointers. Policies are rebound to
	 * the working world, never to this immutable checkpoint. No on-disk ABI.
	 */
	const struct picosystem_garden_world checkpoint = world;
	printf("{\"type\":\"identity\",\"rule\":\"allocation-challenge-v1\",\"seed\":\"%08" PRIx32
	       "\",\"growth\":\"%s\",\"root_after\":%" PRIu32 ",\"lineage\":%" PRIu32
	       ",\"birth\":%" PRIu32 ",\"end\":%" PRIu32 ",\"checkpoint_tick\":%" PRIu32
	       ",\"checkpoint_hash\":\"%08" PRIx32 "\",\"reference_crc32\":\"%08" PRIx32
	       "\",\"candidate_crc32\":\"%08" PRIx32 "\",\"node_capacity\":%u,\"seed_capacity\":%u,"
	       "\"patch_seed\":\"%08" PRIx32 "\",\"seed_reserve_rule\":\"%s\","
	       "\"leaf_policy\":\"selective\",\"water_uptake\":\"%s\",\"seed_dispersal\":\"%s\","
	       "\"scenario\":\"rainfed-crowded\",\"gardener\":false,\"drainage\":false}\n",
	       seed, argv[4], root_after, lineage, birth, end, checkpoint.logic_tick_count,
	       picosystem_garden_world_hash(&checkpoint), reference_crc, candidate_crc,
	       PICOSYSTEM_GARDEN_MAX_NODES, PICOSYSTEM_GARDEN_MAX_SEEDS, PATCH_SEED,
	       PICOSYSTEM_GARDEN_SEED_RESERVE_NAME, PICOSYSTEM_GARDEN_WATER_UPTAKE_NAME,
	       PICOSYSTEM_GARDEN_DISPERSAL_NAME);
	const struct picosystem_garden_agent_policy wait = {
		.decide = wait_decide, .arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS};
	const struct picosystem_garden_agent_policy *choices[] = {&reference.root, &wet_root.root,
								  &wait, &candidate.guarded};
	const char *names[] = {"reference", "wet-root", "wait", "candidate"};
	for (size_t i = 0U; (err == 0) && (i < 4U); ++i) {
		world = checkpoint;
		struct toy_factory_garden_allocation_context context;
		struct picosystem_garden_agent_policy policy;
		err = toy_factory_garden_allocation_init(&world, &reference.root, choices[i],
							 lineage, birth, &context, &policy);
		struct recording recording = {.arm = names[i],
					      .directory = argv[9],
					      .lineage = lineage,
					      .birth = birth,
					      .end = end};
		if (err == 0) {
			err = sample(&world, &recording, "checkpoint");
		}
		if (err == 0) {
			err = toy_factory_garden_disturbance_advance(
				&world, scenario, &policy, end, PATCH_SEED, observe, observe_patch,
				&recording, &totals);
		}
	}
	if ((err == 0) && ((fflush(stdout) != 0) || ferror(stdout))) {
		err = -EIO;
	}
	if (err != 0) {
		fprintf(stderr, "Allocation continuation failed (%d)\n", err);
	}
	return err == 0 ? 0 : 1;
}
