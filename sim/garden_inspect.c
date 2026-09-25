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

#include "garden_evaluation.h"
#include "garden_light.h"
#include "garden_model_file.h"
#include "garden_policy_probe.h"
#include "garden_reserve_policy.h"
#include "garden_root_bootstrap.h"
#include "garden_focal_policy.h"
#include "garden_topology.h"
#if defined(TOY_FACTORY_GARDEN_WET_GERMINATION)
#include "garden_wet_germination.h"
#endif
static const char *growth_policy_name;
static uint32_t root_bootstrap_after;
static uint32_t focal_founder;
static bool death_audit_enabled;
#if defined(TOY_FACTORY_GARDEN_SEED_ORDER)
static bool seed_order_rotating;
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_SPACING)
static bool seed_spacing_two;
#endif
#if defined(TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION)
static bool canopy_transmission_enabled;
#endif
#if defined(TOY_FACTORY_GARDEN_FULL_POOL)
static bool full_pool_enabled;
#endif
#if defined(TOY_FACTORY_GARDEN_PLANT_SLOTS)
static bool plant_slots_sixteen;
#endif
static uint32_t focal_model_crc;
static uint32_t background_model_crc;
#if defined(TOY_FACTORY_GARDEN_DAWN_FINISH)
static struct picosystem_garden_dawn_finish dawn_finish;
#endif
#if defined(TOY_FACTORY_GARDEN_PURCHASE_VETO)
static enum picosystem_garden_purchase_selection purchase_selection;
#endif
static struct toy_factory_garden_root_bootstrap_context root_bootstrap_context;
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
#include "garden_leaf_policies.h"
#include "garden_gap.h"
#include "garden_disturbance.h"
static const char *leaf_policy_name = "none";
#endif

#define INSPECTION_CYCLE_TICKS                                                                     \
	(PICOSYSTEM_GARDEN_SUN_CYCLE_TICKS * PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR)
#define INSPECTION_CYCLES         24U
#define INSPECTION_TOPOLOGY_LIMIT 16U
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
#define INSPECTION_MAX_TICKS TOY_FACTORY_GARDEN_DISTURBANCE_MAX_TICKS
#else
#define INSPECTION_MAX_TICKS 100000U
#endif

struct inspection_context {
	const struct picosystem_garden_world *world;
	const struct picosystem_garden_agent_policy *policy;
	const struct picosystem_garden_agent_policy *probe_base;
	const struct toy_factory_garden_focal_context *focal_context;
	bool reserve_probe;
	uint32_t previous_births;
	uint32_t previous_deaths;
	uint32_t root_first_lineage;
	uint32_t night_wait_lineage;
	bool every_ecology;
	bool seed_sites;
	bool population_census;
	uint32_t topology_ticks[INSPECTION_TOPOLOGY_LIMIT];
	uint8_t topology_count;
	uint32_t next_disturbance_tick;
	uint32_t last_print_tick;
};

#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
static int trace_leaf(const struct picosystem_garden_leaf_observation *observation,
		      const struct picosystem_garden_agent_memory *memory,
		      struct picosystem_garden_leaf_decision *decision, const void *context)
{
	const struct inspection_context *inspection = context;
	const struct picosystem_garden_leaf_policy *policy = inspection->policy->leaf_policy;
	const int err = policy->decide(observation, memory, decision, policy->context);
	if (err == 0) {
		printf("{\"type\":\"leaf-bid\",\"tick\":%" PRIu32 ",\"id\":%" PRIu32
		       ",\"site_x\":%d,\"site_y\":%d,\"condition\":%u,\"light\":%u,"
		       "\"energy\":%u,\"water\":%u,\"mature_leaves\":%u,\"action\":%u}\n",
		       inspection->world->logic_tick_count,
		       inspection->world->plants[observation->plant_index].lineage_id,
		       observation->base_delta_x, observation->base_delta_y, observation->condition,
		       observation->light, observation->stored_energy, observation->stored_water,
		       observation->mature_leaf_count, decision->action);
	}
	return err;
}
#endif

static void print_plant(const struct picosystem_garden_world *world, uint8_t plant_index)
{
	const struct picosystem_garden_plant *const plant = &world->plants[plant_index];
	uint16_t tips = 0U;
	uint16_t leaves = 0U;
	uint16_t flowers = 0U;
	uint16_t spent_flowers = 0U;
	uint16_t roots = 0U;
	uint16_t active_leaves = 0U;
	for (uint16_t index = 0U; index < world->node_count; ++index) {
		const struct picosystem_garden_node *const node = &world->nodes[index];
		if (node->plant_index != plant_index) {
			continue;
		}
		tips += ((node->flags & PICOSYSTEM_GARDEN_NODE_TIP) != 0U) ? 1U : 0U;
		leaves += ((node->flags & PICOSYSTEM_GARDEN_NODE_LEAF) != 0U) ? 1U : 0U;
		if (((node->flags & PICOSYSTEM_GARDEN_NODE_LEAF) != 0U) &&
		    (node->growth_progress >= PICOSYSTEM_GARDEN_LEAF_ACTIVE_PROGRESS)) {
			++active_leaves;
		}
		flowers += ((node->flags & PICOSYSTEM_GARDEN_NODE_FLOWER) != 0U) ? 1U : 0U;
		spent_flowers +=
			((node->flags & PICOSYSTEM_GARDEN_NODE_FLOWER_SEEDED) != 0U) ? 1U : 0U;
		if (node->kind == PICOSYSTEM_GARDEN_NODE_ROOT) {
			++roots;
		}
	}
	printf("{\"id\":%" PRIu32 ",\"parent\":%" PRIu32 ",\"species\":\"%s\","
	       "\"generation\":%u,\"age_ecology_ticks\":%" PRIu32 ",\"column\":%u,"
	       "\"dead\":%s,\"energy\":%u,\"water\":%u,\"stress\":%u,"
	       "\"nodes\":%u,\"roots\":%u,\"tips\":%u,\"leaves\":%u,"
	       "\"flowers\":%u,\"spent_flowers\":%u,\"genome\":[%d,%d,%d,%d,%d,%d,%d,%d],"
	       "\"vigor\":%d,\"flags\":%u,\"active_leaves\":%u,"
	       "\"energy_income\":%u,\"water_income\":%u,\"reproduction_cooldown\":%u,"
	       "\"agent\":{\"decisions\":%" PRIu32 ",\"extend\":%" PRIu32 ",\"finish\":%" PRIu32
	       ",\"wait\":%" PRIu32 ",\"root_extend\":%" PRIu32 ",\"shoot_extend\":%" PRIu32
	       ",\"last_priority\":%d,\"last_action\":%u,"
	       "\"last_tissue\":%u,\"last_x\":%u,\"last_y\":%u},\"root_cells\":[",
	       plant->lineage_id, plant->parent_lineage_id,
	       picosystem_garden_species_name((enum picosystem_garden_species_id)plant->species_id),
	       plant->generation, plant->age_ecology_ticks, plant->base_column,
	       ((plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) != 0U) ? "true" : "false",
	       plant->stored_energy, plant->stored_water, plant->stress, plant->node_count, roots,
	       tips, leaves, flowers, spent_flowers, plant->genome.growth_rate,
	       plant->genome.shoot_bias, plant->genome.light_seeking, plant->genome.water_seeking,
	       plant->genome.branching, plant->genome.stature, plant->genome.reserve_strategy,
	       plant->genome.dispersal, plant->vigor, plant->flags, active_leaves,
	       plant->last_energy_income, plant->last_water_income, plant->reproduction_cooldown,
	       plant->agent_telemetry.decision_count, plant->agent_telemetry.extend_count,
	       plant->agent_telemetry.finish_count, plant->agent_telemetry.wait_count,
	       plant->agent_telemetry.root_extend_count, plant->agent_telemetry.shoot_extend_count,
	       plant->agent_telemetry.last_priority, plant->agent_telemetry.last_action,
	       plant->agent_telemetry.last_tissue_kind, plant->agent_telemetry.last_tip_x,
	       plant->agent_telemetry.last_tip_y);
	bool first = true;
	for (uint16_t index = 0U; index < world->node_count; ++index) {
		const struct picosystem_garden_node *const node = &world->nodes[index];
		if ((node->plant_index != plant_index) ||
		    (node->kind != PICOSYSTEM_GARDEN_NODE_ROOT)) {
			continue;
		}
		const uint8_t column = (uint8_t)((node->x - PICOSYSTEM_GARDEN_ORIGIN_X_PIXELS) /
						 PICOSYSTEM_GARDEN_CELL_PIXELS);
		const uint8_t row = (uint8_t)((node->y - PICOSYSTEM_GARDEN_SOIL_TOP_PIXELS) /
					      PICOSYSTEM_GARDEN_CELL_PIXELS);
		printf("%s[%u,%u,%u,%u]", first ? "" : ",", column, row, node->depth,
		       world->moisture[row * PICOSYSTEM_GARDEN_GRID_COLUMNS + column]);
		first = false;
	}
	printf("]");
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	printf(",\"leaf\":{\"observations\":%" PRIu32 ",\"proposals\":%" PRIu32
	       ",\"renewals\":%" PRIu32 ",\"restored\":%" PRIu32 ",\"worn\":%" PRIu32
	       ",\"remainder\":%u,\"conditions\":[",
	       plant->leaf_telemetry.observations, plant->leaf_telemetry.proposals,
	       plant->leaf_telemetry.renewals, plant->leaf_telemetry.restored,
	       plant->leaf_telemetry.worn, plant->leaf_energy_remainder);
	first = true;
	for (uint16_t index = 0U; index < world->node_count; ++index) {
		if ((world->nodes[index].plant_index == plant_index) &&
		    (world->nodes[index].flags & PICOSYSTEM_GARDEN_NODE_LEAF)) {
			printf("%s%u", first ? "" : ",", world->leaf_condition[index]);
			first = false;
		}
	}
	printf("]}");
#endif
	printf("}");
}

static void print_soil_totals(const struct picosystem_garden_world *world)
{
#if defined(TOY_FACTORY_GARDEN_WET_GERMINATION)
	if (world->wet_germination_enabled) {
		printf("\"germination_rule\":\"%s\",", PICOSYSTEM_GARDEN_WET_GERMINATION_NAME);
	}
#endif
#if defined(TOY_FACTORY_GARDEN_FOCAL_SEED_VETO)
	printf("\"seed_veto_rule\":\"%s\",", PICOSYSTEM_GARDEN_FOCAL_SEED_VETO_NAME);
#endif
	if (focal_founder != 0U) {
		printf("\"focal_policy\":{\"rule\":\"%s\",\"founder\":%" PRIu32
		       ",\"model_crc32\":\"%08" PRIx32 "\"},",
		       TOY_FACTORY_GARDEN_FOCAL_POLICY_RULE, focal_founder, focal_model_crc);
	}
	if (root_bootstrap_after != 0U) {
		printf("\"root_bootstrap_rule\":\"%s\",\"root_bootstrap_after\":%" PRIu32 ",",
		       TOY_FACTORY_GARDEN_ROOT_BOOTSTRAP_RULE, root_bootstrap_after);
	}
#if defined(TOY_FACTORY_GARDEN_SEED_RESERVE)
	printf("\"seed_reserve_rule\":\"%s\",", PICOSYSTEM_GARDEN_SEED_RESERVE_NAME);
#endif
#if defined(TOY_FACTORY_GARDEN_LARGE_SEED_BANK)
	printf("\"seed_capacity\":%u,", PICOSYSTEM_GARDEN_MAX_SEEDS);
#endif
	if (growth_policy_name != NULL) {
		printf("\"growth_policy\":\"%s\",", growth_policy_name);
	}
#if defined(TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE)
	printf("\"drainage_rule\":\"%s\",", PICOSYSTEM_GARDEN_DRAINAGE_NAME);
#endif
#if defined(TOY_FACTORY_GARDEN_LARGE_POOL)
	printf("\"node_capacity\":%u,", PICOSYSTEM_GARDEN_MAX_NODES);
#endif
	/* The firmware's uint16 summary saturates; host resource audits need the sum. */
	uint32_t total = 0U;
	uint16_t saturated = 0U;
	for (size_t index = 0U; index < PICOSYSTEM_GARDEN_SOIL_CELL_COUNT; ++index) {
		total += world->moisture[index];
		if (world->moisture[index] == UINT8_MAX) {
			++saturated;
		}
	}
	printf("\"soil\":{\"water\":%" PRIu32 ",\"saturated_cells\":%u},", total, saturated);
}

#if defined(TOY_FACTORY_GARDEN_DARK_GUARD)
static void print_dark_budget(const struct picosystem_garden_dark_budget *budget)
{
	printf("{\"supported\":%s,\"energy\":%u,\"stress\":%u,\"peak_stress\":%u,"
	       "\"upkeep\":%u,\"dark_steps\":%u,\"payments\":%u,\"first_shortage_step\":%u,"
	       "\"death_step\":%u}",
	       budget->supported ? "true" : "false", budget->energy, budget->stress,
	       budget->peak_stress, budget->upkeep, budget->dark_steps, budget->payments,
	       budget->first_shortage_step, budget->death_step);
}

static int print_dark_audit(const struct picosystem_garden_dark_audit *audit)
{
	static const char *const kinds[] = {"growth", "renewal", "seeds"};
	printf("\"dark_guard\":{\"rule\":\"%s\",\"overflow\":%s,\"evaluated\":[%" PRIu32 ",%" PRIu32
	       ",%" PRIu32 "],\"denied\":[%" PRIu32 ",%" PRIu32 ",%" PRIu32 "],\"events\":[",
	       PICOSYSTEM_GARDEN_DARK_GUARD_NAME, audit->overflow ? "true" : "false",
	       audit->evaluated[0], audit->evaluated[1], audit->evaluated[2], audit->denied[0],
	       audit->denied[1], audit->denied[2]);
	if (audit->count > PICOSYSTEM_GARDEN_DARK_EVENTS) {
		return -EINVAL;
	}
	for (uint8_t i = 0U; i < audit->count; ++i) {
		const struct picosystem_garden_dark_event *const event = &audit->events[i];
		if (event->kind >= PICOSYSTEM_GARDEN_EXPENSE_COUNT) {
			return -EINVAL;
		}
		printf("%s{\"id\":%" PRIu32 ",\"kind\":\"%s\",\"node\":%u,\"nodes_before\":%u,"
		       "\"nodes_after\":%u,\"energy\":%u,\"water\":%u,\"energy_cost\":%u,"
		       "\"water_cost\":%u,\"stress\":%u,\"denied\":%s,\"invalid\":%s,\"before\":",
		       i == 0U ? "" : ",", event->lineage_id, kinds[event->kind], event->node_index,
		       event->nodes_before, event->nodes_after, event->energy, event->water,
		       event->energy_cost, event->water_cost, event->stress,
		       event->denied ? "true" : "false", event->invalid ? "true" : "false");
		print_dark_budget(&event->before);
		printf(",\"after\":");
		print_dark_budget(&event->after);
		putchar('}');
	}
	printf("]},");
	return 0;
}
#endif

static int print_world(const struct picosystem_garden_world *world)
{
	putchar('{');
	if (death_audit_enabled) {
		printf("\"death_audit_version\":%u,", PICOSYSTEM_GARDEN_DEATH_AUDIT_VERSION);
	}
#if defined(TOY_FACTORY_GARDEN_FULL_POOL)
	const int full_pool_err =
		picosystem_garden_full_pool_print(&world->full_pool, world->logic_tick_count);
	if (full_pool_err != 0) {
		return full_pool_err;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_PLANT_SLOTS)
	const int slots_err = picosystem_garden_plant_slots_print(world->plant_slots_sixteen,
								  world->logic_tick_count);
	if (slots_err != 0) {
		return slots_err;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION)
	const int transmission_err = picosystem_garden_canopy_transmission_print(
		world->canopy_transmission_enabled, world->logic_tick_count);
	if (transmission_err != 0) {
		return transmission_err;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_SPACING)
	const int spacing_err = picosystem_garden_seed_spacing_print(world->seed_spacing_two,
								     world->logic_tick_count);
	if (spacing_err != 0) {
		return spacing_err;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_ORDER)
	const int order_err = picosystem_garden_seed_order_print(
		world->seed_order_rotating, world->logic_tick_count, world->plant_count);
	if (order_err != 0) {
		return order_err;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_DAWN_FINISH)
	const int dawn_err =
		picosystem_garden_dawn_finish_print(&world->dawn_finish, world->logic_tick_count);
	if (dawn_err != 0) {
		return dawn_err;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_NIGHT_CAPACITY)
	const int capacity_err = picosystem_garden_night_print(&world->night_capacity);
	if (capacity_err != 0) {
		return capacity_err;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_PURCHASE_VETO)
	const int purchase_err =
		picosystem_garden_purchase_print(&world->purchase_veto, world->logic_tick_count);
	if (purchase_err != 0) {
		return purchase_err;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	printf("\"leaf_environment\":\"%s\",\"leaf_policy\":\"%s\",",
	       PICOSYSTEM_GARDEN_LEAF_ENVIRONMENT, leaf_policy_name);
#endif
	print_soil_totals(world);
#if defined(TOY_FACTORY_GARDEN_DARK_GUARD)
	const int audit_err = print_dark_audit(&world->dark_guard);
	if (audit_err != 0) {
		return audit_err;
	}
#endif
	const struct picosystem_garden_sun sun =
		picosystem_garden_sun_at(world->ecology_tick_count);
	printf("\"type\":\"world\",\"sun_phase\":%u,\"sun_strength\":%u,"
	       "\"tick\":%" PRIu32 ",\"hash\":\"%08" PRIx32 "\",\"living\":%u,"
	       "\"nodes\":%u,\"births\":%" PRIu32 ",\"deaths\":%" PRIu32 ","
	       "\"seeds_created\":%" PRIu32 ",\"seeds_expired\":%" PRIu32 ","
	       "\"max_generation\":%u,\"plants\":[",
	       sun.phase, sun.strength, world->logic_tick_count,
	       picosystem_garden_world_hash(world),
	       picosystem_garden_world_living_plant_count(world), world->node_count,
	       world->germination_count, world->death_count, world->seed_creation_count,
	       world->seed_expiration_count, world->maximum_generation);
	for (uint8_t index = 0U; index < world->plant_count; ++index) {
		if (index != 0U) {
			putchar(',');
		}
		print_plant(world, index);
	}
	printf("],\"seeds\":[");
	for (uint8_t index = 0U; index < world->seed_count; ++index) {
		const struct picosystem_garden_seed *const seed = &world->seeds[index];
		uint8_t blockers;
		const int err =
			picosystem_garden_world_seed_germination_blockers(world, index, &blockers);
		if (err != 0) {
			return err;
		}
		printf("%s{\"parent\":%" PRIu32 ",\"generation\":%u,\"column\":%u,"
		       "\"blockers\":%u}",
		       (index == 0U) ? "" : ",", seed->parent_lineage_id, seed->generation,
		       seed->column, blockers);
	}
	printf("],\"moisture\":%u,\"weather_seed\":\"%08" PRIx32 "\",\"rain_rate\":%u,"
	       "\"rain_deposited\":%" PRIu32 ",\"rain_runoff\":%" PRIu32 "}\n",
	       world->moisture_total, world->weather_seed,
	       picosystem_garden_rain_at(world->weather_seed, world->ecology_tick_count),
	       world->rain_deposited, world->rain_runoff);
	return ferror(stdout) ? -EIO : 0;
}

static int print_seed_sites(const struct picosystem_garden_world *world)
{
	struct picosystem_garden_seed_sites sites;
	const int err = picosystem_garden_world_seed_sites(world, &sites);
	if (err != 0) {
		return err;
	}
	putchar('{');
#if defined(TOY_FACTORY_GARDEN_FULL_POOL)
	const int full_pool_err =
		picosystem_garden_full_pool_print(&world->full_pool, world->logic_tick_count);
	if (full_pool_err != 0) {
		return full_pool_err;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_PLANT_SLOTS)
	const int slots_err = picosystem_garden_plant_slots_print(world->plant_slots_sixteen,
								  world->logic_tick_count);
	if (slots_err != 0) {
		return slots_err;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION)
	const int transmission_err = picosystem_garden_canopy_transmission_print(
		world->canopy_transmission_enabled, world->logic_tick_count);
	if (transmission_err != 0) {
		return transmission_err;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_SPACING)
	const int spacing_err = picosystem_garden_seed_spacing_print(world->seed_spacing_two,
								     world->logic_tick_count);
	if (spacing_err != 0) {
		return spacing_err;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_ORDER)
	const int order_err = picosystem_garden_seed_order_print(
		world->seed_order_rotating, world->logic_tick_count, world->plant_count);
	if (order_err != 0) {
		return order_err;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_DAWN_FINISH)
	const int dawn_err =
		picosystem_garden_dawn_finish_print(&world->dawn_finish, world->logic_tick_count);
	if (dawn_err != 0) {
		return dawn_err;
	}
#endif
	print_soil_totals(world);
	const struct picosystem_garden_sun sun =
		picosystem_garden_sun_at(world->ecology_tick_count);
	printf("\"type\":\"seed-sites\",\"schema_version\":1,\"tick\":%" PRIu32
	       ",\"hash\":\"%08" PRIx32 "\",\"sun_phase\":%u,\"sun_strength\":%u,"
	       "\"rain_rate\":%u,\"nodes\":%u,\"living\":%u,\"births\":%" PRIu32
	       ",\"deaths\":%" PRIu32 ",\"seeds_created\":%" PRIu32 ",\"seeds_expired\":%" PRIu32
	       ",\"sites\":[",
	       world->logic_tick_count, picosystem_garden_world_hash(world), sun.phase,
	       sun.strength,
	       picosystem_garden_rain_at(world->weather_seed, world->ecology_tick_count),
	       world->node_count, picosystem_garden_world_living_plant_count(world),
	       world->germination_count, world->death_count, world->seed_creation_count,
	       world->seed_expiration_count);
	for (uint8_t column = 0U; column < PICOSYSTEM_GARDEN_GRID_COLUMNS; ++column) {
		const size_t surface =
			(PICOSYSTEM_GARDEN_CANOPY_ROWS - 1U) * PICOSYSTEM_GARDEN_GRID_COLUMNS +
			column;
		printf("%s[%u,%u,%u]", column == 0U ? "" : ",", sites.blockers[column],
		       world->moisture[column], world->light[surface]);
	}
	printf("],\"plants\":[");
	for (uint8_t index = 0U; index < world->plant_count; ++index) {
		const struct picosystem_garden_plant *const plant = &world->plants[index];
		printf("%s{\"id\":%" PRIu32 ",\"parent\":%" PRIu32 ",\"column\":%u,"
		       "\"generation\":%u,\"species\":%u,\"dead\":%s,\"dispersal_columns\":%" PRIu32
		       "}",
		       index == 0U ? "" : ",", plant->lineage_id, plant->parent_lineage_id,
		       plant->base_column, plant->generation, plant->species_id,
		       (plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) != 0U ? "true" : "false",
		       sites.dispersal_columns[index]);
	}
	printf("],\"seeds\":[");
	for (uint8_t index = 0U; index < world->seed_count; ++index) {
		const struct picosystem_garden_seed *const seed = &world->seeds[index];
		uint8_t blockers;
		const int seed_err =
			picosystem_garden_world_seed_germination_blockers(world, index, &blockers);
		if (seed_err != 0) {
			return seed_err;
		}
		printf("%s{\"parent\":%" PRIu32 ",\"column\":%u,\"generation\":%u,\"species\":%u,"
		       "\"age\":%u,\"blockers\":%u}",
		       index == 0U ? "" : ",", seed->parent_lineage_id, seed->column,
		       seed->generation, seed->species_id, seed->age_ecology_ticks, blockers);
	}
	printf("]}\n");
	return ferror(stdout) ? -EIO : 0;
}

static int print_sample(const struct picosystem_garden_world *world,
			const struct inspection_context *inspection)
{
	const int err = inspection->seed_sites ? print_seed_sites(world) : print_world(world);
	if (err != 0) {
		return err;
	}
	for (uint8_t i = 0U; i < inspection->topology_count; ++i) {
		if (inspection->topology_ticks[i] == world->logic_tick_count) {
			return toy_factory_garden_topology_print(world, stdout);
		}
	}
	return 0;
}

static int observe(const struct picosystem_garden_world *world, bool ecology_sample, void *context)
{
	if (!ecology_sample) {
		return 0;
	}
	struct inspection_context *const inspection = context;
	bool ready_seed = false;
	for (uint8_t index = 0U; !inspection->population_census && index < world->seed_count;
	     ++index) {
		uint8_t blockers;
		const int err =
			picosystem_garden_world_seed_germination_blockers(world, index, &blockers);
		if (err != 0) {
			return err;
		}
		ready_seed = ready_seed || (blockers == 0U);
	}
	const bool changed = (world->germination_count != inspection->previous_births) ||
			     (world->death_count != inspection->previous_deaths);
	inspection->previous_births = world->germination_count;
	inspection->previous_deaths = world->death_count;
	if (inspection->every_ecology || changed || ready_seed ||
	    (world->logic_tick_count == inspection->next_disturbance_tick) ||
	    ((world->logic_tick_count % INSPECTION_CYCLE_TICKS) == 0U)) {
		inspection->last_print_tick = world->logic_tick_count;
		return print_sample(world, inspection);
	}
	return 0;
}

static int trace_decision(const struct picosystem_garden_agent_observation *observation,
			  const struct picosystem_garden_agent_memory *memory,
			  struct picosystem_garden_agent_decision *decision, const void *context)
{
	const struct inspection_context *const inspection = context;
	const int err =
		picosystem_garden_agent_decide(inspection->policy, observation, memory, decision);
	if (err != 0) {
		return err;
	}
	const struct picosystem_garden_plant *const plant =
		&inspection->world->plants[observation->plant_index];
	/* Explicit host-only counterfactuals. Zero IDs leave the real policy untouched.
	 * Keep the original output visible; these overrides are never model training.
	 */
	struct picosystem_garden_agent_decision unmodified = *decision;
	if (root_bootstrap_after != 0U) {
		const int base_err = picosystem_garden_agent_decide(
			root_bootstrap_context.base, observation, memory, &unmodified);
		if (base_err != 0) {
			return base_err;
		}
	}
	const int16_t original_priority = unmodified.proposal.priority;
	const uint8_t original_action = unmodified.proposal.action;
	if ((plant->lineage_id == inspection->root_first_lineage) && (plant->generation != 0U) &&
	    (observation->age_ecology_ticks == 1U) &&
	    (observation->tissue_kind == PICOSYSTEM_GARDEN_NODE_ROOT) &&
	    (decision->proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND)) {
		decision->proposal.priority = INT16_MAX;
	}
	if ((plant->lineage_id == inspection->night_wait_lineage) &&
	    (observation->sun_phase >= PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE)) {
		decision->proposal.action = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT;
		decision->proposal.candidate_count = 0U;
	}
	printf("{\"type\":\"bid\",\"tick\":%" PRIu32 ",\"id\":%" PRIu32
	       ",\"tip_audit_version\":1,\"tip_index\":%u,\"maximum_depth\":%u,"
	       "\"tissue\":%u,\"x\":%u,\"y\":%u,\"depth\":%u,\"tip_flags\":%u,"
	       "\"energy\":%u,\"water\":%u,\"priority\":%d,\"action\":%u,"
	       "\"original_priority\":%d,\"original_action\":%u,\"candidates\":[",
	       inspection->world->logic_tick_count, plant->lineage_id, observation->tip_index,
	       observation->maximum_depth, observation->tissue_kind, observation->tip_x,
	       observation->tip_y, observation->depth, observation->tip_flags,
	       observation->stored_energy, observation->stored_water, decision->proposal.priority,
	       decision->proposal.action, original_priority, original_action);
	for (uint8_t index = 0U; index < observation->candidate_count; ++index) {
		const struct picosystem_garden_agent_candidate *const candidate =
			&observation->candidates[index];
		printf("%s{\"x\":%u,\"y\":%u,\"moisture\":%u,\"light\":%u,\"flags\":%u}",
		       (index == 0U) ? "" : ",", candidate->x, candidate->y, candidate->moisture,
		       candidate->light, candidate->flags);
	}
	printf("]");
	if (inspection->focal_context != NULL) {
		const struct picosystem_garden_agent_policy *const selected =
			toy_factory_garden_focal_policy_select(inspection->focal_context,
							       observation->plant_index);
		if (selected == NULL) {
			return -EINVAL;
		}
		printf(",\"controller_model_crc32\":\"%08" PRIx32 "\"",
		       selected == inspection->focal_context->focal ? focal_model_crc
								    : background_model_crc);
	}
	if (root_bootstrap_after != 0U) {
		printf(",\"root_bootstrap\":{\"rule\":\"%s\",\"after\":%" PRIu32
		       ",\"age\":%u,\"roots\":%u,\"tip_moisture\":%u,\"original_order\":[",
		       TOY_FACTORY_GARDEN_ROOT_BOOTSTRAP_RULE, root_bootstrap_after,
		       observation->age_ecology_ticks, observation->root_node_count,
		       observation->tip_moisture);
		for (uint8_t i = 0U; i < unmodified.proposal.candidate_count; ++i) {
			printf("%s%u", i == 0U ? "" : ",", unmodified.proposal.candidate_order[i]);
		}
		printf("],\"order\":[");
		for (uint8_t i = 0U; i < decision->proposal.candidate_count; ++i) {
			printf("%s%u", i == 0U ? "" : ",", decision->proposal.candidate_order[i]);
		}
		printf("]}");
	}
	if (inspection->probe_base != NULL) {
		/* Both supported base policies are pure: record the pre-veto
		 * proposal without committing memory or advancing any random stream.
		 */
		struct picosystem_garden_agent_decision original;
		const int probe_err = picosystem_garden_agent_decide(
			inspection->probe_base, observation, memory, &original);
		if (probe_err != 0) {
			return probe_err;
		}
		printf(",\"probe\":\"%s\",\"probe_original_action\":%u,\"sun_phase\":%u",
		       TOY_FACTORY_GARDEN_NIGHT_PROBE_NAME, original.proposal.action,
		       observation->sun_phase);
		if (inspection->reserve_probe) {
			const uint8_t pre_action = observation->sun_phase >= 128U
							   ? PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT
							   : original.proposal.action;
			struct toy_factory_garden_reserve_forecast forecast;
			const int reserve_err = toy_factory_garden_reserve_forecast(
				observation, pre_action, &forecast);
			if (reserve_err != 0) {
				return reserve_err;
			}
			printf(",\"reserve\":{\"rule\":\"%s\",\"nodes\":%u,\"species\":%u,"
			       "\"vigor\":%d,\"income\":%u,\"maintenance_phase\":%u,\"priority\":%"
			       "d,"
			       "\"allowed\":%s,\"post_nodes\":%" PRIu32 ",\"growth_cost\":%" PRIu32
			       ",\"maintenance_cost\":%" PRIu32 ",\"daylight_steps\":%" PRIu32
			       ",\"daylight_credit\":%" PRIu32 ",\"daylight_upkeep\":%" PRIu32
			       ",\"night_upkeep\":%" PRIu32 ",\"projected_sunset\":%" PRId32 "}",
			       TOY_FACTORY_GARDEN_RESERVE_NAME, observation->plant_node_count,
			       observation->species_id, observation->vigor,
			       observation->last_energy_income, observation->maintenance_phase,
			       original.proposal.priority, forecast.allowed ? "true" : "false",
			       forecast.post_nodes, forecast.growth_cost, forecast.maintenance_cost,
			       forecast.daylight_steps, forecast.daylight_credit,
			       forecast.daylight_upkeep, forecast.night_upkeep,
			       forecast.projected_sunset);
		}
	}
	printf("}\n");
	return ferror(stdout) ? -EIO : 0;
}

static void print_death_resource(const struct picosystem_garden_death_resource *resource)
{
	printf("{\"before\":%u,\"income\":%u,\"overflow\":%u,\"upkeep_due\":%u,"
	       "\"upkeep_paid\":%u,\"discarded\":%u}",
	       resource->before, resource->income, resource->overflow, resource->upkeep_due,
	       resource->upkeep_paid, resource->discarded);
}

static int print_deaths(const struct picosystem_garden_world *world,
			const struct picosystem_garden_death_audit *audit, void *context)
{
	(void)context;
	for (uint8_t index = 0U; index < audit->count; ++index) {
		const struct picosystem_garden_death_event *const event = &audit->events[index];
		printf("{\"type\":\"death\",\"version\":%u,\"tick\":%" PRIu32 ",\"id\":%" PRIu32
		       ",\"stress_before\":%u,\"flags\":%u,\"energy\":",
		       PICOSYSTEM_GARDEN_DEATH_AUDIT_VERSION, world->logic_tick_count,
		       event->lineage_id, event->stress_before, event->flags);
		print_death_resource(&event->energy);
		printf(",\"water\":");
		print_death_resource(&event->water);
		printf("}\n");
	}
	return ferror(stdout) ? -EIO : 0;
}

static int parse_positive_u32(const char *text, uint32_t *value)
{
	errno = 0;
	char *end;
	const unsigned long parsed = strtoul(text, &end, 0);
	if ((errno != 0) || (*text == '-') || (*end != '\0') || (parsed == 0U) ||
	    (parsed > UINT32_MAX)) {
		return -EINVAL;
	}
	*value = (uint32_t)parsed;
	return 0;
}

#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
static int observe_disturbance(const struct picosystem_garden_world *world,
			       const struct toy_factory_garden_disturbance_event *event,
			       void *context)
{
	struct inspection_context *inspection = context;
	struct toy_factory_garden_disturbance_event next;
	const int planned =
		toy_factory_garden_disturbance_plan(event->seed, event->index + 1U, &next);
	if ((planned != 0) && (planned != -ENOENT)) {
		return planned;
	}
	inspection->next_disturbance_tick = planned == 0 ? next.tick : 0U;
	const int err = toy_factory_garden_disturbance_print(event);
	return err != 0 ? err : print_sample(world, context);
}
#endif

int main(int argc, char **argv)
{
	if (argc < 5) {
		const bool help = (argc == 2) && (strcmp(argv[1], "--help") == 0);
		fprintf(help ? stdout : stderr,
			"Usage: %s MODEL SCENARIO POLICY WORLD_SEED [--ecology] "
			"[--ticks 1-%u] [--root-first ID] [--night-wait ID] [--seed-sites]\n"
			"--seed-sites: compact post-step site/seed census every ecology tick; no "
			"bids.\n"
			"MODEL may be '-' for baseline, adaptive, or neural-reference.\n"
			"neural-no-night-growth uses MODEL with the no-night-growth-v1 probe.\n",
			argv[0], INSPECTION_MAX_TICKS);
		fprintf(help ? stdout : stderr,
			"adaptive-no-night-growth uses MODEL '-' and the same night veto.\n");
		fprintf(help ? stdout : stderr,
			"--death-audit: exact natural-death receipts and every ecology sample; "
			"not compatible with patch/gap interventions or compact censuses.\n");
		fprintf(help ? stdout : stderr,
			"--topology-at TICK: read-only topology after each census at that tick; "
			"requires --ecology. Up to 16 increasing distinct ecology ticks, including "
			"0.\n");
		fprintf(help ? stdout : stderr,
			"neural-reserve-growth uses MODEL with energy-reserve-v1.\n");
		fprintf(help ? stdout : stderr,
			"--focal-model MODEL --focal-founder ID: route only that reset founder; "
			"requires neural-no-night-growth, no other overrides.\n");
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
		fprintf(help ? stdout : stderr,
			"--leaf-policy none|all|selective (default none)\n"
			"--gap-at TICK: host-only one-time largest-adult "
			"export; ecology boundary\n"
			"--gap-lineage ID: with --gap-at, export this adult instead; permits focal "
			"routing\n"
			"--disturbance-seed SEED: recurring host-only patch deaths\n"
			"--root-bootstrap-after TICK: explicit wet-root bootstrap for later "
			"offspring\n"
			"--population: birth/death, daily and disturbance census; no bids\n");
#endif
#if defined(TOY_FACTORY_GARDEN_PURCHASE_VETO)
		fprintf(help ? stdout : stderr,
			"--purchase-veto extension|finish|finish-retry: fixed host diagnostic\n");
#endif
#if defined(TOY_FACTORY_GARDEN_DAWN_FINISH)
		fprintf(help ? stdout : stderr,
			"--dawn-finish defer|reserve: fixed wet-world seedling diagnostic\n");
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_ORDER)
		fprintf(help ? stdout : stderr,
			"--seed-order rotating: post-noon purchase rotation; requires reserve\n");
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_SPACING)
		fprintf(help ? stdout : stderr,
			"--seed-spacing 2: post-noon spacing; requires rotating seed order\n");
#endif
#if defined(TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION)
		fprintf(help ? stdout : stderr,
			"--canopy-transmission fractional: post-noon optics; requires spacing 2\n");
#endif
#if defined(TOY_FACTORY_GARDEN_FULL_POOL)
		fprintf(help ? stdout : stderr, "--full-pool nonallocating: post-noon full-pool "
						"actions; requires plant-slots 16\n");
#endif
#if defined(TOY_FACTORY_GARDEN_PLANT_SLOTS)
		fprintf(help ? stdout : stderr,
			"--plant-slots 16: post-noon admission; requires fractional canopy\n");
#endif
		return help ? 0 : 2;
	}
	struct inspection_context inspection = {0};
	uint32_t tick_count = 0U;
	const char *focal_model_path = NULL;
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	uint32_t gap_tick = 0U;
	uint32_t wet_tick = 0U;
	uint32_t gap_lineage = 0U;
	uint32_t disturbance_seed = 0U;
#endif
	for (int index = 5; index < argc; ++index) {
		if (strcmp(argv[index], "--topology-at") == 0) {
			uint32_t tick = 0U;
			if ((++index >= argc) ||
			    (inspection.topology_count == INSPECTION_TOPOLOGY_LIMIT) ||
			    ((strcmp(argv[index], "0") != 0) &&
			     (parse_positive_u32(argv[index], &tick) != 0)) ||
			    ((tick % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) != 0U) ||
			    ((inspection.topology_count != 0U) &&
			     (tick <= inspection.topology_ticks[inspection.topology_count - 1U]))) {
				return 2;
			}
			inspection.topology_ticks[inspection.topology_count++] = tick;
			continue;
		}
#if defined(TOY_FACTORY_GARDEN_FULL_POOL)
		if (strcmp(argv[index], "--full-pool") == 0) {
			if ((++index >= argc) || (picosystem_garden_full_pool_parse(
							  argv[index], &full_pool_enabled) != 0)) {
				return 2;
			}
			continue;
		}
#endif
#if defined(TOY_FACTORY_GARDEN_PLANT_SLOTS)
		if (strcmp(argv[index], "--plant-slots") == 0) {
			if ((++index >= argc) ||
			    (picosystem_garden_plant_slots_parse(argv[index],
								 &plant_slots_sixteen) != 0)) {
				return 2;
			}
			continue;
		}
#endif
#if defined(TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION)
		if (strcmp(argv[index], "--canopy-transmission") == 0) {
			if ((++index >= argc) ||
			    (picosystem_garden_canopy_transmission_parse(
				     argv[index], &canopy_transmission_enabled) != 0)) {
				return 2;
			}
			continue;
		}
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_SPACING)
		if (strcmp(argv[index], "--seed-spacing") == 0) {
			if ((++index >= argc) || (picosystem_garden_seed_spacing_parse(
							  argv[index], &seed_spacing_two) != 0)) {
				return 2;
			}
			continue;
		}
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_ORDER)
		if (strcmp(argv[index], "--seed-order") == 0) {
			if ((++index >= argc) ||
			    (picosystem_garden_seed_order_parse(argv[index],
								&seed_order_rotating) != 0)) {
				return 2;
			}
			continue;
		}
#endif
#if defined(TOY_FACTORY_GARDEN_DAWN_FINISH)
		if (strcmp(argv[index], "--dawn-finish") == 0) {
			if ((++index >= argc) ||
			    (picosystem_garden_dawn_finish_parse(argv[index], &dawn_finish) != 0)) {
				return 2;
			}
			continue;
		}
#endif
#if defined(TOY_FACTORY_GARDEN_WET_GERMINATION)
		if (strcmp(argv[index], "--wet-germination-after") == 0) {
			if ((wet_tick != 0U) || (++index >= argc) ||
			    (parse_positive_u32(argv[index], &wet_tick) != 0)) {
				return 2;
			}
			continue;
		}
#endif
#if defined(TOY_FACTORY_GARDEN_PURCHASE_VETO)
		if (strcmp(argv[index], "--purchase-veto") == 0) {
			if ((++index >= argc) || (picosystem_garden_purchase_parse(
							  argv[index], &purchase_selection) != 0)) {
				return 2;
			}
			continue;
		}
#endif
		if (strcmp(argv[index], "--focal-model") == 0) {
			if ((focal_model_path != NULL) || (++index >= argc) ||
			    (*argv[index] == '\0')) {
				return 2;
			}
			focal_model_path = argv[index];
			continue;
		}
		if (strcmp(argv[index], "--focal-founder") == 0) {
			if ((focal_founder != 0U) || (++index >= argc) ||
			    (parse_positive_u32(argv[index], &focal_founder) != 0)) {
				return 2;
			}
			continue;
		}
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
		if (strcmp(argv[index], "--root-bootstrap-after") == 0) {
			if ((root_bootstrap_after != 0U) || (++index >= argc) ||
			    (parse_positive_u32(argv[index], &root_bootstrap_after) != 0)) {
				return 2;
			}
			continue;
		}
		if (strcmp(argv[index], "--population") == 0) {
			if (inspection.population_census) {
				return 2;
			}
			inspection.population_census = true;
			continue;
		}
		if (strcmp(argv[index], "--disturbance-seed") == 0) {
			if ((disturbance_seed != 0U) || (++index >= argc) ||
			    (parse_positive_u32(argv[index], &disturbance_seed) != 0)) {
				return 2;
			}
			continue;
		}
		if (strcmp(argv[index], "--gap-lineage") == 0) {
			if ((gap_lineage != 0U) || (++index >= argc) ||
			    (parse_positive_u32(argv[index], &gap_lineage) != 0)) {
				return 2;
			}
			continue;
		}
		if (strcmp(argv[index], "--gap-at") == 0) {
			if ((gap_tick != 0U) || (++index >= argc) ||
			    (parse_positive_u32(argv[index], &gap_tick) != 0)) {
				return 2;
			}
			inspection.every_ecology = true;
			continue;
		}
		if (strcmp(argv[index], "--leaf-policy") == 0) {
			if ((++index >= argc) ||
			    (toy_factory_garden_leaf_policy(argv[index]) == NULL)) {
				return 2;
			}
			leaf_policy_name = argv[index];
			continue;
		}
#endif
		if ((strcmp(argv[index], "--seed-sites") == 0) && !inspection.seed_sites) {
			inspection.seed_sites = true;
			inspection.every_ecology = true;
			continue;
		}
		if ((strcmp(argv[index], "--death-audit") == 0) && !death_audit_enabled) {
			death_audit_enabled = true;
			inspection.every_ecology = true;
			continue;
		}
		if (strcmp(argv[index], "--ecology") == 0) {
			inspection.every_ecology = true;
			continue;
		}
		uint32_t *target = NULL;
		if (strcmp(argv[index], "--root-first") == 0) {
			target = &inspection.root_first_lineage;
		} else if (strcmp(argv[index], "--night-wait") == 0) {
			target = &inspection.night_wait_lineage;
		} else if (strcmp(argv[index], "--ticks") == 0) {
			target = &tick_count;
		}
		if ((target == NULL) || (*target != 0U) || (++index >= argc) ||
		    (parse_positive_u32(argv[index], target) != 0)) {
			return 2;
		}
		if (target != &tick_count) {
			inspection.every_ecology = true;
		}
	}
	if (tick_count > INSPECTION_MAX_TICKS) {
		return 2;
	}
	if (death_audit_enabled && (inspection.seed_sites || inspection.population_census ||
				    (inspection.topology_count != 0U))) {
		return 2;
	}
	if (((focal_model_path != NULL) != (focal_founder != 0U)) ||
	    ((focal_founder != 0U) &&
	     ((strcmp(argv[3], TOY_FACTORY_GARDEN_NIGHT_PROBE_POLICY) != 0) ||
	      (root_bootstrap_after != 0U) || (inspection.root_first_lineage != 0U) ||
	      (inspection.night_wait_lineage != 0U)))) {
		return 2;
	}
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	if (death_audit_enabled && ((gap_tick != 0U) || (disturbance_seed != 0U))) {
		return 2;
	}
	if (((wet_tick != 0U) && ((wet_tick != gap_tick) || (gap_lineage == 0U))) ||
	    ((gap_lineage != 0U) && (gap_tick == 0U)) ||
	    ((focal_founder != 0U) && (gap_tick != 0U) && (gap_lineage == 0U))) {
		return 2;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_DAWN_FINISH)
	if (dawn_finish.enabled &&
	    ((wet_tick != 46080U) || (gap_lineage != 1U) || (focal_founder != 5U) ||
	     (strcmp(leaf_policy_name, "selective") != 0))) {
		return 2;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_ORDER)
	if (seed_order_rotating && !dawn_finish.reserve_handoff) {
		return 2;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_SPACING)
	if (seed_spacing_two && !seed_order_rotating) {
		return 2;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION)
	if (canopy_transmission_enabled && !seed_spacing_two) {
		return 2;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_FULL_POOL)
	if (full_pool_enabled && !plant_slots_sixteen) {
		return 2;
	}
#endif
#if defined(TOY_FACTORY_GARDEN_PLANT_SLOTS)
	if (plant_slots_sixteen && !canopy_transmission_enabled) {
		return 2;
	}
#endif
	if (inspection.seed_sites &&
	    ((inspection.root_first_lineage != 0U) || (inspection.night_wait_lineage != 0U))) {
		fprintf(stderr, "seed-site census cannot be combined with lineage overrides\n");
		return 2;
	}
	if (tick_count == 0U) {
		tick_count = INSPECTION_CYCLES * INSPECTION_CYCLE_TICKS;
	}
	if ((inspection.topology_count != 0U) &&
	    (!inspection.every_ecology || inspection.seed_sites || inspection.population_census ||
	     (inspection.topology_ticks[inspection.topology_count - 1U] > tick_count))) {
		return 2;
	}
	if (root_bootstrap_after != 0U) {
#if defined(TOY_FACTORY_GARDEN_LARGE_POOL) && defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE) &&      \
	!defined(TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE)
		if ((root_bootstrap_after > tick_count) ||
		    ((root_bootstrap_after % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) != 0U) ||
		    (disturbance_seed == 0U) || (gap_tick != 0U) || inspection.seed_sites ||
		    (inspection.root_first_lineage != 0U) ||
		    (inspection.night_wait_lineage != 0U) ||
		    ((strcmp(argv[3], TOY_FACTORY_GARDEN_NIGHT_PROBE_POLICY) != 0) &&
		     (strcmp(argv[3], TOY_FACTORY_GARDEN_RESERVE_POLICY) != 0))) {
			return 2;
		}
#else
		return 2;
#endif
	}
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	if (inspection.population_census && inspection.every_ecology) {
		fprintf(stderr, "population census cannot be combined with other trace modes or "
				"overrides\n");
		return 2;
	}
	if (disturbance_seed != 0U) {
		struct toy_factory_garden_disturbance_event first;
		if (toy_factory_garden_disturbance_plan(disturbance_seed, 0U, &first) != 0) {
			return 2;
		}
		inspection.next_disturbance_tick = first.tick;
		inspection.every_ecology = !inspection.population_census;
	}
	if ((disturbance_seed != 0U) &&
	    ((gap_tick != 0U) || (inspection.root_first_lineage != 0U) ||
	     (inspection.night_wait_lineage != 0U))) {
		return 2;
	}
	if ((gap_tick > tick_count) || (gap_tick % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR != 0U) ||
	    ((gap_tick != 0U) &&
	     ((inspection.root_first_lineage != 0U) || (inspection.night_wait_lineage != 0U)))) {
		return 2;
	}
#endif
	if ((inspection.every_ecology || inspection.population_census) &&
	    ((tick_count % PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR) != 0U)) {
		fprintf(stderr, "ecology traces require a multiple of 15 ticks\n");
		return 2;
	}
	uint32_t random_seed;
	if (parse_positive_u32(argv[4], &random_seed) != 0) {
		return 2;
	}
	const struct toy_factory_garden_evaluation_scenario *scenario = NULL;
	for (size_t index = 0U; index < TOY_FACTORY_GARDEN_EVALUATION_SCENARIO_COUNT; ++index) {
		if (strcmp(argv[2], toy_factory_garden_evaluation_scenarios[index].name) == 0) {
			scenario = &toy_factory_garden_evaluation_scenarios[index];
		}
	}
	if (scenario == NULL) {
		for (size_t index = 0U; index < TOY_FACTORY_GARDEN_RAINFED_SCENARIO_COUNT;
		     ++index) {
			if (strcmp(argv[2], toy_factory_garden_rainfed_scenarios[index].name) ==
			    0) {
				scenario = &toy_factory_garden_rainfed_scenarios[index];
			}
		}
	}
	if (scenario == NULL) {
		return 2;
	}
	struct picosystem_garden_neural_model model;
	struct picosystem_garden_agent_policy neural_policy;
	struct picosystem_garden_agent_policy probe_policy;
	struct picosystem_garden_agent_policy reserve_policy;
	const struct picosystem_garden_agent_policy *policy;
	int err = 0;
	const bool adaptive_probe = strcmp(argv[3], TOY_FACTORY_GARDEN_ADAPTIVE_NIGHT_POLICY) == 0;
	const bool reserve_probe = strcmp(argv[3], TOY_FACTORY_GARDEN_RESERVE_POLICY) == 0;
	const bool neural_probe =
		(strcmp(argv[3], TOY_FACTORY_GARDEN_NIGHT_PROBE_POLICY) == 0) || reserve_probe;
	const bool probe = neural_probe || adaptive_probe;
	if (probe &&
	    ((inspection.root_first_lineage != 0U) || (inspection.night_wait_lineage != 0U))) {
		fprintf(stderr, "cannot combine policy probe with lineage overrides\n");
		return 2;
	}
	if ((strcmp(argv[3], "neural-candidate") == 0) || neural_probe) {
		err = toy_factory_garden_model_read(argv[1], &model, &background_model_crc);
		if (err == 0) {
			err = picosystem_garden_neural_policy_init(&model, &neural_policy);
		}
		policy = &neural_policy;
		if ((err == 0) && probe) {
			err = toy_factory_garden_no_night_growth_init(&neural_policy,
								      &probe_policy);
			policy = &probe_policy;
			inspection.probe_base = &neural_policy;
		}
		if ((err == 0) && reserve_probe) {
			err = toy_factory_garden_reserve_init(&probe_policy, &reserve_policy);
			policy = &reserve_policy;
			inspection.reserve_probe = true;
			growth_policy_name = TOY_FACTORY_GARDEN_RESERVE_POLICY;
		}
	} else if (adaptive_probe) {
		if (strcmp(argv[1], "-") != 0) {
			return 2;
		}
		inspection.probe_base = picosystem_garden_agent_adaptive_policy();
		err = toy_factory_garden_no_night_growth_init(inspection.probe_base, &probe_policy);
		policy = &probe_policy;
		growth_policy_name = TOY_FACTORY_GARDEN_ADAPTIVE_NIGHT_POLICY;
	} else if (strcmp(argv[3], "adaptive") == 0) {
		policy = picosystem_garden_agent_adaptive_policy();
	} else if (strcmp(argv[3], "baseline") == 0) {
		policy = picosystem_garden_agent_baseline_policy();
	} else if (strcmp(argv[3], "neural-reference") == 0) {
		policy = picosystem_garden_agent_neural_reference_policy();
	} else {
		return 2;
	}
	struct picosystem_garden_world world;
	struct picosystem_garden_agent_policy root_policy;
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	struct picosystem_garden_agent_policy maintained_policy = {0};
	if (err == 0) {
		maintained_policy = *policy;
		maintained_policy.leaf_policy = toy_factory_garden_leaf_policy(leaf_policy_name);
		policy = &maintained_policy;
	}
#endif
	if ((err == 0) && (root_bootstrap_after != 0U)) {
		err = toy_factory_garden_root_bootstrap_init(policy, &world, root_bootstrap_after,
							     &root_bootstrap_context, &root_policy);
		policy = &root_policy;
	}
	inspection.world = &world;
	inspection.policy = policy;
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	const struct picosystem_garden_leaf_policy traced_leaf = {.decide = trace_leaf,
								  .context = &inspection};
#endif
	const struct picosystem_garden_agent_policy traced_policy = {
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
		.leaf_policy = (err == 0) ? &traced_leaf : NULL,
#endif
		.decide = trace_decision,
		.context = &inspection,
		.arbitration = (err == 0) ? policy->arbitration
					  : PICOSYSTEM_GARDEN_AGENT_ARBITRATION_PHASED,
	};
	if (err == 0) {
		err = toy_factory_garden_evaluation_reset(&world, scenario, random_seed);
	}
	struct picosystem_garden_neural_model focal_model;
	struct picosystem_garden_agent_policy focal_neural, focal_probe, routed, routed_raw;
	struct toy_factory_garden_focal_context focal_context, raw_context;
	if ((err == 0) && (focal_founder != 0U)) {
		err = toy_factory_garden_model_read(focal_model_path, &focal_model,
						    &focal_model_crc);
		if (err == 0) {
			err = picosystem_garden_neural_policy_init(&focal_model, &focal_neural);
		}
		if (err == 0) {
			err = toy_factory_garden_no_night_growth_init(&focal_neural, &focal_probe);
		}
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
		if (err == 0) {
			focal_probe.leaf_policy = policy->leaf_policy;
		}
#endif
		if (err == 0) {
			err = toy_factory_garden_focal_policy_init(&world, policy, &focal_probe,
								   focal_founder, &focal_context,
								   &routed);
		}
		if (err == 0) {
			err = toy_factory_garden_focal_policy_init(&world, inspection.probe_base,
								   &focal_neural, focal_founder,
								   &raw_context, &routed_raw);
		}
		if (err == 0) {
			policy = &routed;
			inspection.policy = policy;
			inspection.probe_base = &routed_raw;
			inspection.focal_context = &focal_context;
		}
	}
#if defined(TOY_FACTORY_GARDEN_PURCHASE_VETO)
	world.purchase_veto.selection = purchase_selection;
#endif
#if defined(TOY_FACTORY_GARDEN_DAWN_FINISH)
	world.dawn_finish = dawn_finish;
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_ORDER)
	world.seed_order_rotating = seed_order_rotating;
#endif
#if defined(TOY_FACTORY_GARDEN_SEED_SPACING)
	world.seed_spacing_two = seed_spacing_two;
#endif
#if defined(TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION)
	world.canopy_transmission_enabled = canopy_transmission_enabled;
#endif
#if defined(TOY_FACTORY_GARDEN_FULL_POOL)
	world.full_pool.enabled = full_pool_enabled;
#endif
#if defined(TOY_FACTORY_GARDEN_PLANT_SLOTS)
	world.plant_slots_sixteen = plant_slots_sixteen;
#endif
	if (err == 0) {
		err = print_sample(&world, &inspection);
	}
	if (err == 0) {
		uint32_t first_ticks = tick_count;
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
		if (gap_tick != 0U) {
			first_ticks = gap_tick;
		}
#endif
		const struct picosystem_garden_agent_policy *active_policy =
			(inspection.every_ecology && !inspection.seed_sites) ? &traced_policy
									     : policy;
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
		if (disturbance_seed != 0U) {
			struct toy_factory_garden_disturbance_totals totals = {0};
			err = toy_factory_garden_disturbance_advance(
				&world, scenario, active_policy, tick_count, disturbance_seed,
				observe, observe_disturbance, &inspection, &totals);
		} else
#endif
		{
			if (death_audit_enabled) {
				err = toy_factory_garden_evaluation_advance_death_audit(
					&world, scenario, active_policy, first_ticks, observe,
					print_deaths, &inspection);
			} else {
				err = toy_factory_garden_evaluation_advance(
					&world, scenario, active_policy, first_ticks, observe,
					&inspection);
			}
		}
	}
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	if ((err == 0) && (gap_tick != 0U)) {
		struct toy_factory_garden_gap gap;
		err = gap_lineage != 0U
			      ? toy_factory_garden_gap_apply_named(&world, gap_lineage, &gap)
			      : toy_factory_garden_gap_apply(&world, &gap);
		if (err == 0) {
			err = toy_factory_garden_gap_print(&gap);
		}
		if (err == 0) {
			/* A second sample at the same tick is explicitly bracketed by the event. */
			err = print_sample(&world, &inspection);
		}
#if defined(TOY_FACTORY_GARDEN_WET_GERMINATION)
		if ((err == 0) && (wet_tick != 0U)) {
			err = toy_factory_garden_wet_germination_activate(&world);
			if (err == 0) {
				err = print_sample(&world, &inspection);
			}
		}
#endif
		if (err == 0) {
			err = toy_factory_garden_evaluation_advance(
				&world, scenario, inspection.seed_sites ? policy : &traced_policy,
				tick_count - gap_tick, observe, &inspection);
		}
	}
#endif
	if ((err == 0) && (inspection.last_print_tick != world.logic_tick_count)) {
		err = print_sample(&world, &inspection);
	}
	if ((err == 0) && (fflush(stdout) != 0)) {
		err = -EIO;
	}
	if (err != 0) {
		fprintf(stderr, "Garden inspection failed (%d)\n", err);
		return 1;
	}
	return 0;
}
