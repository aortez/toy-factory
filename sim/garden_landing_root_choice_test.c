/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_growth.h"
#include "garden_landing_plant_trace.h"
#include "garden_evaluation.h"
#include "garden_light.h"

#include <assert.h>
#include <errno.h>
#include <string.h>

static void fixture(struct picosystem_garden_world *world,
		    struct picosystem_garden_agent_observation *o,
		    struct picosystem_garden_agent_decision *d)
{
	assert(picosystem_garden_world_reset(world, 3U) == 0);
	world->auto_gardener_enabled = false;
	assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 12U) ==
	       0);
	world->plants[0].generation = 1U;
	world->plants[0].parent_lineage_id = 1U;
	world->maximum_generation = 1U;
	world->plants[0].age_ecology_ticks = 1U;
	world->logic_tick_count = 15U;
	assert(picosystem_garden_agent_observe_tip(world, 0U, 2U, 42U, o) == 0);
	*d = (struct picosystem_garden_agent_decision){
		.next_memory = {.hidden = {3, -7, 12}},
		.proposal = {.tip_index = 2U,
			     .action = PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND,
			     .priority = 21,
			     .candidate_count = o->candidate_count}};
	for (uint8_t i = 0U; i < o->candidate_count; ++i) {
		d->proposal.candidate_order[i] = (uint8_t)(o->candidate_count - i - 1U);
		o->candidates[i].flags = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE |
					 PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS;
	}
	assert(o->root_node_count == 2U && o->sun_phase < PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE);
}

static void priority_only(void)
{
	for (uint8_t fault = 0U; fault < 15U; ++fault) {
		struct picosystem_garden_world world;
		struct picosystem_garden_agent_observation o;
		struct picosystem_garden_agent_decision d;
		fixture(&world, &o, &d);
		struct toy_factory_garden_root_choice choice = {.tick = 15U, .lineage = 1U};
		int expected = 0;
		switch (fault) {
		case 1:
			choice = (struct toy_factory_garden_root_choice){0};
			break;
		case 2:
			choice.tick = 30U;
			break;
		case 3:
			choice.lineage = 2U;
			break;
		case 4:
			world.plants[0].generation = 0U;
			break;
		case 5:
			o.age_ecology_ticks = 0U;
			break;
		case 6:
			o.age_ecology_ticks = 257U;
			break;
		case 7:
			o.root_node_count = 3U;
			break;
		case 8:
			o.tissue_kind = PICOSYSTEM_GARDEN_NODE_STEM;
			break;
		case 9:
			d.proposal.action = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT;
			break;
		case 10:
			o.stored_water = 0U;
			break;
		case 11:
			o.stored_energy = 0U;
			break;
		case 12:
			for (uint8_t c = 0U; c < o.candidate_count; ++c) {
				o.candidates[c].flags = 0U;
			}
			break;
		case 13:
			d.proposal.candidate_order[1] = d.proposal.candidate_order[0];
			expected = -ERANGE;
			break;
		case 14:
			world.node_count = 32U;
			world.plants[0].node_count = 32U;
			o.plant_node_count = 32U;
			o.shoot_node_count = 30U;
			break;
		default:
			break;
		}
		const struct picosystem_garden_world saved_world = world;
		const struct picosystem_garden_agent_observation saved_o = o;
		struct picosystem_garden_agent_decision wanted = d;
		if (fault == 0U) {
			wanted.proposal.priority = INT16_MAX;
		}
		assert(toy_factory_garden_root_choice_apply(&world, &o, &choice,
							    TOY_FACTORY_GARDEN_BUDGET_SHOOT,
							    &d) == expected);
		assert(memcmp(&wanted, &d, sizeof(d)) == 0);
		assert(memcmp(&world, &saved_world, sizeof(world)) == 0);
		assert(memcmp(&o, &saved_o, sizeof(o)) == 0);
	}
}

static int fail_observe(const struct picosystem_garden_world *world,
			const struct picosystem_garden_agent_observation *o,
			const struct picosystem_garden_agent_decision *raw,
			const struct picosystem_garden_agent_decision *applied, void *context)
{
	(void)world;
	(void)o;
	(void)raw;
	(void)applied;
	(void)context;
	return -ECANCELED;
}

static void energy_contract(void)
{
	struct picosystem_garden_world world;
	struct picosystem_garden_agent_observation o;
	struct picosystem_garden_agent_decision d;
	fixture(&world, &o, &d);
	struct toy_factory_garden_root_choice choice = {
		.tick = 15U, .lineage = 1U, .energy_reserve = true};
	bool allowed = false;
	/* Initial root purchase stays unguarded even with an empty reserve. */
	o.stored_energy = 9U;
	assert(!toy_factory_garden_root_energy_active(&world, &o, &choice));
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) == 0);
	assert(allowed);
	world.logic_tick_count = 30U;
	o.age_ecology_ticks = 2U;
	assert(toy_factory_garden_root_energy_active(&world, &o, &choice));
	const struct picosystem_garden_agent_decision saved = d;
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) == 0);
	assert(!allowed && memcmp(&saved, &d, sizeof(d)) == 0);
	o.stored_energy = 256U;
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) == 0);
	assert(allowed);
	o.sun_phase = PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE;
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) == 0);
	assert(!allowed);
	d.proposal.action = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT;
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) == 0);
	assert(allowed);
	d = saved;
	o.age_ecology_ticks = 256U;
	world.logic_tick_count = choice.tick + 255U * 15U;
	assert(toy_factory_garden_root_energy_active(&world, &o, &choice));
	o.age_ecology_ticks++;
	world.logic_tick_count += 15U;
	assert(!toy_factory_garden_root_energy_active(&world, &o, &choice));
	o.age_ecology_ticks = 2U;
	world.logic_tick_count = 30U;
	choice.lineage = 2U;
	assert(!toy_factory_garden_root_energy_active(&world, &o, &choice));
	choice.lineage = 1U;
	world.plants[0].generation = 0U;
	assert(!toy_factory_garden_root_energy_active(&world, &o, &choice));
	world.plants[0].generation = 1U;
	world.plants[0].flags |= PICOSYSTEM_GARDEN_PLANT_DEAD;
	assert(!toy_factory_garden_root_energy_active(&world, &o, &choice));
	world.plants[0].flags &= (uint8_t)~PICOSYSTEM_GARDEN_PLANT_DEAD;
	world.logic_tick_count = 45U;
	assert(!toy_factory_garden_root_energy_active(&world, &o, &choice));
	world.logic_tick_count = 30U;
	choice.energy_reserve = false;
	assert(!toy_factory_garden_root_energy_active(&world, &o, &choice));
	choice.energy_reserve = true;
	d.proposal.action = PICOSYSTEM_GARDEN_AGENT_ACTION_COUNT;
	allowed = true;
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) ==
	       -EINVAL);
	assert(allowed);
	choice.tick = 0U;
	choice.lineage = 0U;
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) ==
	       -ERANGE);
	assert(allowed);
	assert(toy_factory_garden_root_energy_eligible(NULL, &o, &choice, &d, &allowed) == -EINVAL);
	assert(allowed);
}

static void run_contract(void)
{
	struct picosystem_garden_world world;
	assert(toy_factory_garden_evaluation_reset(&world, &toy_factory_garden_rainfed_scenarios[1],
						   0x940cfdc4U) == 0);
	struct toy_factory_garden_landing_model model;
	const struct toy_factory_garden_landing_feature_config features = {.version = 1U,
									   .mode = 1U};
	assert(toy_factory_garden_landing_model_import(picosystem_garden_neural_reference_model(),
						       &features, &model) == 0);
	struct toy_factory_garden_landing_growth_run plain, probe;
	assert(toy_factory_garden_landing_placement_init(&world, &model, 1U, 1U, &plain) == 0);
	probe = plain;
	probe.root_choice = (struct toy_factory_garden_root_choice){.tick = 30U, .lineage = 1U};
	uint32_t a, b;
	assert(toy_factory_garden_landing_growth_hash(&plain, &a) == 0);
	assert(toy_factory_garden_landing_growth_hash(&probe, &b) == 0 && a != b);
	const uint32_t root_hash = b;
	probe.root_choice.energy_reserve = true;
	assert(toy_factory_garden_landing_growth_hash(&probe, &b) == 0 && root_hash != b);
	const uint32_t energy_hash = b;
	probe.root_choice.afternoon_reserve = true;
	assert(toy_factory_garden_landing_growth_hash(&probe, &b) == 0 && energy_hash != b);
	const uint32_t afternoon_hash = b;
	probe.root_choice.continuous_energy = true;
	assert(toy_factory_garden_landing_growth_hash(&probe, &b) == 0 && afternoon_hash != b);
	const uint32_t continuous_hash = b;
	probe.root_choice.daylight_energy = true;
	assert(toy_factory_garden_landing_growth_hash(&probe, &b) == 0 && continuous_hash != b);
	const uint32_t daylight_hash = b;
	probe.root_choice.dawn_reserve = true;
	assert(toy_factory_garden_landing_growth_hash(&probe, &b) == 0 && daylight_hash != b);
	struct picosystem_garden_death_audit deaths;
	struct picosystem_garden_seed_audit seeds;
	/* Wrong generation at tick 30 stays unchanged too; no latent fired state. */
	for (uint32_t i = 0U; i < 300U; ++i) {
		assert(toy_factory_garden_landing_growth_step(&plain, &deaths, &seeds, NULL) == 0);
		assert(toy_factory_garden_landing_growth_step(&probe, &deaths, &seeds, NULL) == 0);
		assert(memcmp(&plain.base, &probe.base, sizeof(plain.base)) == 0);
	}
	for (uint8_t fault = 0U; fault < 9U; ++fault) {
		probe = plain;
		probe.root_choice =
			(struct toy_factory_garden_root_choice){.tick = 315U, .lineage = 1U};
		if (fault == 0U) {
			probe.root_choice.lineage = 0U;
		}
		if (fault == 1U) {
			probe.root_choice.tick = 316U;
		}
		if (fault == 2U) {
			probe.placement.version = 0U;
			probe.placement.enabled = 0U;
		}
		if (fault == 3U) {
			probe.budget_mode = TOY_FACTORY_GARDEN_BUDGET_ELIGIBLE;
		}
		if (fault == 4U) {
			probe.root_choice =
				(struct toy_factory_garden_root_choice){.energy_reserve = true};
		}
		if (fault == 5U) {
			probe.root_choice.afternoon_reserve = true;
		}
		if (fault == 6U) {
			probe.root_choice.energy_reserve = true;
			probe.root_choice.continuous_energy = true;
		}
		if (fault == 7U) {
			probe.root_choice.energy_reserve = true;
			probe.root_choice.afternoon_reserve = true;
			probe.root_choice.daylight_energy = true;
		}
		if (fault == 8U) {
			probe.root_choice.energy_reserve = true;
			probe.root_choice.afternoon_reserve = true;
			probe.root_choice.continuous_energy = true;
			probe.root_choice.dawn_reserve = true;
		}
		const struct toy_factory_garden_landing_growth_run saved = probe;
		const struct picosystem_garden_death_audit old_deaths = deaths;
		const struct picosystem_garden_seed_audit old_seeds = seeds;
		b = 123U;
		assert(toy_factory_garden_landing_growth_hash(&probe, &b) == -ERANGE && b == 123U);
		assert(toy_factory_garden_landing_growth_step(&probe, &deaths, &seeds, NULL) ==
		       -ERANGE);
		assert(memcmp(&probe, &saved, sizeof(saved)) == 0);
		assert(memcmp(&deaths, &old_deaths, sizeof(deaths)) == 0);
		assert(memcmp(&seeds, &old_seeds, sizeof(seeds)) == 0);
	}
	assert(toy_factory_garden_landing_placement_init(&world, &model, 1U, 1U, &probe) == 0);
	probe.root_choice = (struct toy_factory_garden_root_choice){
		.tick = 15U, .lineage = 1U, .energy_reserve = true};
	probe.base.world.logic_tick_count = 14U;
	probe.base.world.plants[0].generation = 1U;
	probe.base.world.plants[0].parent_lineage_id = 2U;
	probe.base.world.maximum_generation = 1U;
	const struct toy_factory_garden_landing_growth_run saved = probe;
	struct picosystem_garden_resource_audit resources;
	struct picosystem_garden_reproduction_audit reproduction;
	memset(&resources, 0xa5, sizeof(resources));
	memset(&reproduction, 0xa5, sizeof(reproduction));
	const struct picosystem_garden_resource_audit old_resources = resources;
	const struct picosystem_garden_reproduction_audit old_reproduction = reproduction;
	const struct toy_factory_garden_growth_observer observer = {.observe = fail_observe,
								    .reproduction = &reproduction};
	assert(toy_factory_garden_landing_growth_step_observed(&probe, &deaths, &seeds, &resources,
							       &observer) == -ECANCELED);
	assert(memcmp(&probe, &saved, sizeof(saved)) == 0);
	assert(memcmp(&resources, &old_resources, sizeof(resources)) == 0);
	assert(memcmp(&reproduction, &old_reproduction, sizeof(reproduction)) == 0);
}

static void trace_contract(void)
{
	struct picosystem_garden_world world;
	struct picosystem_garden_agent_observation o;
	struct picosystem_garden_agent_decision raw;
	fixture(&world, &o, &raw);
	const struct toy_factory_garden_root_choice choice = {.tick = 15U, .lineage = 1U};
	struct picosystem_garden_agent_decision applied = raw;
	assert(toy_factory_garden_root_choice_apply(
		       &world, &o, &choice, TOY_FACTORY_GARDEN_BUDGET_SHOOT, &applied) == 0);
	FILE *stream = tmpfile();
	assert(stream != NULL);
	struct toy_factory_garden_plant_trace trace;
	world.logic_tick_count = 0U;
	assert(toy_factory_garden_plant_trace_init(&trace, stream, &world, 32U,
						   TOY_FACTORY_GARDEN_BUDGET_SHOOT, 15U, 30U,
						   TOY_FACTORY_GARDEN_TRACE_CHOICE) == 0);
	assert(!trace.directions_enabled);
	assert(toy_factory_garden_plant_directions_publish(&trace, &world, stream) == -EINVAL);
	trace.directions_enabled = true;
	/* Include both ends of the 308-cell bitmap; padding must remain clear. */
	world.nodes[2].x = 8U;
	world.nodes[2].y = 144U;
	world.nodes[3].x = 231U;
	world.nodes[3].y = 231U;
	assert(toy_factory_garden_plant_trace_observe(&world, &o, &raw, &applied, &trace) == 0);
	assert(memcmp(&trace.bids[0].direction, &applied.proposal, sizeof(applied.proposal)) == 0);
	for (size_t c = 0U; c < sizeof(trace.bids[0].root_cells); ++c) {
		assert(trace.bids[0].root_cells[c] == ((c == 0U) ? 1U : (c == 38U) ? 8U : 0U));
	}
	assert(toy_factory_garden_plant_directions_publish(&trace, &world, stream) == -EINVAL);
	trace.reproduction.ecology_step = true;
	assert(toy_factory_garden_plant_directions_publish(&trace, &world, stream) == 0);
	assert(toy_factory_garden_plant_directions_publish(&trace, &world, NULL) == -EINVAL);
	trace.count = PICOSYSTEM_GARDEN_MAX_NODES + 1U;
	assert(toy_factory_garden_plant_directions_publish(&trace, &world, stream) == -EINVAL);
	trace.count = 1U;
	assert(trace.bids[0].raw_priority == 21 && trace.bids[0].priority == INT16_MAX);
	assert(trace.bids[0].water_active && trace.bids[0].water.water_allowed);
	applied.next_memory.hidden[0]++;
	assert(toy_factory_garden_plant_trace_observe(&world, &o, &raw, &applied, &trace) ==
	       -EFAULT);
	applied = raw;
	applied.proposal.candidate_order[0] = raw.proposal.candidate_order[1];
	assert(toy_factory_garden_plant_trace_observe(&world, &o, &raw, &applied, &trace) ==
	       -EFAULT);
	applied = raw;
	applied.proposal.priority++;
	trace.scope = TOY_FACTORY_GARDEN_TRACE_ORDERED;
	assert(toy_factory_garden_plant_trace_observe(&world, &o, &raw, &applied, &trace) ==
	       -EFAULT);
	assert(fclose(stream) == 0);
}

static void afternoon_contract(void)
{
	struct picosystem_garden_world world;
	struct picosystem_garden_agent_observation o;
	struct picosystem_garden_agent_decision d;
	fixture(&world, &o, &d);
	o.sun_phase = 64U;
	o.maintenance_phase = 0U;
	o.last_energy_income = 255U;
	struct toy_factory_garden_afternoon_forecast f;
	for (uint16_t nodes = 8U; nodes <= 24U; nodes += 8U) {
		for (uint8_t species = 0U; species < 3U; ++species) {
			for (int8_t vigor = 0; vigor <= 1; ++vigor) {
				o.plant_node_count = nodes;
				o.species_id = species;
				o.vigor = vigor;
				/* At noon: 16 remaining daylight and 32 night payments. */
				o.stored_energy = (uint16_t)(48U * (nodes / 8U + 1U) + 9U -
							     species - (vigor > 0 ? 1U : 0U));
				assert(toy_factory_garden_afternoon_forecast(&o, 1U, &f) == 0);
				assert(f.applies && f.allowed && f.margin == 0 &&
				       f.maintenance_before == nodes / 8U);
				--o.stored_energy;
				assert(toy_factory_garden_afternoon_forecast(&o, 1U, &f) == 0);
				assert(f.applies && !f.allowed && f.margin == -1);
				struct toy_factory_garden_reserve_forecast original;
				assert(toy_factory_garden_reserve_forecast(&o, 1U, &original) ==
					       0 &&
				       original.allowed);
			}
		}
	}
	o.plant_node_count = 8U;
	o.stored_energy = 30U;
	o.species_id = 0U;
	o.vigor = 0;
	const struct picosystem_garden_agent_observation before = o;
	const uint8_t phases[] = {0U, 63U, 64U, 127U, 128U, 255U};
	for (size_t i = 0U; i < sizeof(phases); ++i) {
		o.sun_phase = phases[i];
		assert(toy_factory_garden_afternoon_forecast(&o, 1U, &f) == 0);
		assert(f.applies == ((phases[i] >= 64U) && (phases[i] < 128U)));
		assert(f.allowed == !f.applies);
	}
	o = before;
	for (uint8_t action = 0U; action < PICOSYSTEM_GARDEN_AGENT_ACTION_COUNT; ++action) {
		assert(toy_factory_garden_afternoon_forecast(&o, action, &f) == 0);
		assert(f.applies == (action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND));
	}
	for (uint16_t nodes = 7U; nodes <= 9U; ++nodes) {
		o.plant_node_count = nodes;
		assert(toy_factory_garden_afternoon_forecast(&o, 1U, &f) == 0);
		assert(f.applies == (nodes == 8U));
	}
	o = before;
	for (uint8_t i = 0U; i < o.candidate_count; ++i) {
		o.candidates[i].flags = 0U;
	}
	assert(toy_factory_garden_afternoon_forecast(&o, 1U, &f) == 0 && !f.applies && f.allowed);
	o = before;
	const struct toy_factory_garden_afternoon_forecast saved_forecast = f;
	assert(toy_factory_garden_afternoon_forecast(NULL, 1U, &f) == -EINVAL);
	assert(toy_factory_garden_afternoon_forecast(&o, 3U, &f) == -EINVAL);
	assert(memcmp(&f, &saved_forecast, sizeof(f)) == 0);
	assert(toy_factory_garden_afternoon_forecast(&o, 1U, NULL) == -EINVAL);
	struct toy_factory_garden_root_choice choice = {
		.tick = 15U, .lineage = 1U, .energy_reserve = true, .afternoon_reserve = true};
	bool allowed;
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) == 0 &&
	       allowed); /* Birth/root purchase remains identical. */
	world.logic_tick_count = 30U;
	o.age_ecology_ticks = 2U;
	const struct picosystem_garden_agent_decision saved_decision = d;
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) == 0 &&
	       !allowed);
	assert(memcmp(&d, &saved_decision, sizeof(d)) == 0);
	choice.afternoon_reserve = false;
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) == 0 &&
	       allowed);
	choice.afternoon_reserve = true;
	o.age_ecology_ticks = 256U;
	world.logic_tick_count = 15U + 255U * 15U;
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) == 0 &&
	       !allowed);
	o.age_ecology_ticks = 257U;
	world.logic_tick_count += 15U;
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) == 0 &&
	       allowed);
	choice.continuous_energy = true;
	world.plants[0].age_ecology_ticks = o.age_ecology_ticks;
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) == 0 &&
	       !allowed);
	assert(memcmp(&d, &saved_decision, sizeof(d)) == 0);
}

static void continuous_contract(void)
{
	struct picosystem_garden_world world;
	struct picosystem_garden_agent_observation o;
	struct picosystem_garden_agent_decision d;
	fixture(&world, &o, &d);
	struct toy_factory_garden_root_choice choice = {.tick = 15U,
							.lineage = 1U,
							.energy_reserve = true,
							.afternoon_reserve = true,
							.continuous_energy = true};
	const uint32_t ages[] = {1U, 2U, 256U, 257U, 8192U, UINT16_MAX, UINT16_MAX + 1U};
	for (size_t i = 0U; i < sizeof(ages) / sizeof(ages[0]); ++i) {
		world.logic_tick_count = choice.tick + (ages[i] - 1U) * 15U;
		world.plants[0].age_ecology_ticks = ages[i];
		o.age_ecology_ticks = (uint16_t)(ages[i] > UINT16_MAX ? UINT16_MAX : ages[i]);
		assert(toy_factory_garden_root_energy_active(&world, &o, &choice) ==
		       (ages[i] > 1U));
		++world.logic_tick_count;
		assert(!toy_factory_garden_root_energy_active(&world, &o, &choice));
	}
	world.logic_tick_count = choice.tick + 256U * 15U;
	o.age_ecology_ticks = 257U;
	world.plants[0].age_ecology_ticks = o.age_ecology_ticks;
	for (uint8_t fault = 0U; fault < 9U; ++fault) {
		struct picosystem_garden_world w = world;
		struct picosystem_garden_agent_observation observation = o;
		struct toy_factory_garden_root_choice config = choice;
		switch (fault) {
		case 0:
			w.plants[0].generation = 0U;
			break;
		case 1:
			w.plants[0].flags |= PICOSYSTEM_GARDEN_PLANT_DEAD;
			break;
		case 2:
			++w.plants[0].lineage_id;
			break;
		case 3:
			observation.plant_index = PICOSYSTEM_GARDEN_MAX_PLANTS;
			break;
		case 4:
			w.plant_count = 0U;
			break;
		case 5:
			--observation.age_ecology_ticks;
			break;
		case 6:
			config.tick += 15U;
			break;
		case 7:
			config.afternoon_reserve = false;
			break;
		case 8:
			++w.plants[0].age_ecology_ticks;
			break;
		}
		assert(!toy_factory_garden_root_energy_active(&w, &observation, &config));
	}
	bool allowed = true;
	o.sun_phase = 128U;
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) == 0 &&
	       !allowed); /* Original paid-night rule remains active beyond day one. */
	d.proposal.action = PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT;
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) == 0 &&
	       allowed);
	choice.afternoon_reserve = false;
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) ==
	       -ERANGE);
	assert(allowed);
}

static void daylight_contract(void)
{
	struct picosystem_garden_world world;
	struct picosystem_garden_agent_observation o;
	struct picosystem_garden_agent_decision d;
	fixture(&world, &o, &d);
	o.species_id = 0U;
	o.vigor = 0;
	o.plant_node_count = 31U;
	o.stored_energy = 95U;
	o.maintenance_phase = 1U;
	o.sun_phase = 97U;
	o.sun_strength = 82U;
	o.last_energy_income = 5U;
	struct toy_factory_garden_daylight_forecast f;
	assert(toy_factory_garden_daylight_forecast(&o, 1U, &f) == 0);
	assert(f.applies && !f.allowed && f.useful_steps == 9U && f.daylight_credit == 22U &&
	       f.projected_sunset == 76);
	/* Independent integer oracle, including the strength-64 boundary, no dusk
	 * division, WAIT, both paid actions and every byte-sized phase/strength.
	 */
	for (uint32_t phase = 0U; phase < 256U; ++phase) {
		o.sun_phase = (uint8_t)phase;
		for (uint32_t strength = 24U; strength <= 255U; ++strength) {
			o.sun_strength = (uint8_t)strength;
			for (uint8_t action = 0U; action < 3U; ++action) {
				const struct picosystem_garden_agent_observation before = o;
				struct toy_factory_garden_reserve_forecast base;
				assert(toy_factory_garden_reserve_forecast(&o, action, &base) == 0);
				assert(toy_factory_garden_daylight_forecast(&o, action, &f) == 0);
				assert(memcmp(&o, &before, sizeof(o)) == 0);
				const bool applies =
					(action != 0U) && (phase >= 64U) && (phase < 128U);
				assert(f.applies == applies);
				if (!applies) {
					assert(f.allowed && f.useful_steps == 0U &&
					       f.daylight_credit == 0U && f.projected_sunset == 0);
					continue;
				}
				const uint32_t beam = ((128U - phase) * 231U + 32U) / 64U;
				uint32_t useful = 0U;
				for (uint32_t q = phase + 1U; q < 128U; ++q) {
					const uint32_t future = ((128U - q) * 231U + 32U) / 64U;
					useful += (24U + future * (strength - 24U) / beam >= 64U)
							  ? 1U
							  : 0U;
				}
				const uint32_t credit = 5U * useful / 2U;
				const int32_t after =
					(int32_t)o.stored_energy - (int32_t)base.growth_cost;
				const int32_t sunset =
					after + (int32_t)credit - (int32_t)base.daylight_upkeep;
				assert(f.useful_steps == useful && f.daylight_credit == credit &&
				       f.daylight_credit <= base.daylight_credit);
				assert(f.projected_sunset == (sunset > 256 ? 256 : sunset));
				assert(f.allowed ==
				       ((after >= (int32_t)base.maintenance_cost) &&
					(f.projected_sunset >= (int32_t)base.night_upkeep)));
				assert(!f.allowed || base.allowed);
			}
		}
	}
	const struct toy_factory_garden_daylight_forecast saved = f;
	assert(toy_factory_garden_daylight_forecast(NULL, 1U, &f) == -EINVAL);
	assert(toy_factory_garden_daylight_forecast(&o, 3U, &f) == -EINVAL);
	assert(toy_factory_garden_daylight_forecast(&o, 1U, NULL) == -EINVAL);
	assert(memcmp(&f, &saved, sizeof(f)) == 0);
	o.sun_phase = 97U;
	o.sun_strength = 82U;
	struct toy_factory_garden_root_choice choice = {.tick = 15U,
							.lineage = 1U,
							.energy_reserve = true,
							.afternoon_reserve = true,
							.continuous_energy = true};
	world.logic_tick_count = 30U;
	o.age_ecology_ticks = 2U;
	world.plants[0].age_ecology_ticks = 2U;
	bool allowed = false;
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) == 0 &&
	       allowed);
	choice.daylight_energy = true;
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) == 0 &&
	       !allowed);
	choice.lineage = 2U;
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) == 0 &&
	       allowed);
	choice.lineage = 1U;
	world.logic_tick_count = 15U;
	o.age_ecology_ticks = 1U;
	world.plants[0].age_ecology_ticks = 1U;
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) == 0 &&
	       allowed);
	choice.continuous_energy = false;
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) ==
	       -ERANGE);
	assert(allowed);
	/* Large observations saturate only the projection, not arithmetic intermediates. */
	o.sun_phase = 64U;
	o.sun_strength = 255U;
	o.last_energy_income = 255U;
	o.stored_energy = 256U;
	assert(toy_factory_garden_daylight_forecast(&o, 1U, &f) == 0 && f.projected_sunset == 256);
	o.plant_node_count = UINT16_MAX;
	assert(toy_factory_garden_daylight_forecast(&o, 1U, &f) == 0 && !f.allowed);
}

static void dawn_contract(void)
{
	struct picosystem_garden_world world;
	struct picosystem_garden_agent_observation o;
	struct picosystem_garden_agent_decision d;
	fixture(&world, &o, &d);
	o.species_id = 0U;
	o.vigor = 0;
	o.plant_node_count = 24U;
	o.stored_energy = 190U;
	o.maintenance_phase = 1U;
	o.last_energy_income = 5U;
	struct toy_factory_garden_dawn_forecast f;
	/* Independent integer sun-curve oracle covers WAIT, both paid actions,
	 * every phase/strength, and unavailable productive mornings.
	 */
	for (uint32_t phase = 0U; phase < 256U; ++phase) {
		o.sun_phase = (uint8_t)phase;
		for (uint32_t strength = 24U; strength <= 255U; ++strength) {
			o.sun_strength = (uint8_t)strength;
			for (uint8_t action = 0U; action < 3U; ++action) {
				const struct picosystem_garden_agent_observation saved = o;
				assert(toy_factory_garden_dawn_forecast(&o, action, &f) == 0);
				assert(memcmp(&o, &saved, sizeof(o)) == 0);
				const bool applies = action != 0U && phase >= 64U && phase < 128U;
				assert(f.applies == applies);
				if (!applies) {
					assert(f.allowed && !f.estimate_available &&
					       !f.stores_applies && f.reserve == 0U &&
					       f.first_light_phase == 0U && f.payment_phase == 0U &&
					       f.projected_margin == 0 && f.stores_margin == 0);
					continue;
				}
				struct toy_factory_garden_reserve_forecast base;
				struct toy_factory_garden_daylight_forecast light;
				struct toy_factory_garden_afternoon_forecast afternoon;
				assert(toy_factory_garden_reserve_forecast(&o, action, &base) == 0);
				assert(toy_factory_garden_daylight_forecast(&o, action, &light) ==
				       0);
				assert(toy_factory_garden_afternoon_forecast(&o, action,
									     &afternoon) == 0);
				const uint32_t beam = ((128U - phase) * 231U + 32U) / 64U;
				uint32_t first = 0U;
				for (uint32_t q = 1U; q <= 64U; ++q) {
					if (24U + ((q * 231U + 32U) / 64U) * (strength - 24U) /
							    beam >=
					    64U) {
						first = q;
						break;
					}
				}
				assert(f.stores_applies == afternoon.applies);
				assert(f.estimate_available == (first != 0U));
				assert(f.first_light_phase == first);
				if (first == 0U) {
					assert(!f.allowed && f.reserve == 0U &&
					       f.payment_phase == 0U && f.projected_margin == 0 &&
					       f.stores_margin == 0);
					continue;
				}
				const uint32_t payments = (first + 3U) / 4U;
				assert(f.payment_phase == payments * 4U);
				assert(f.reserve == payments * base.maintenance_cost);
				assert(f.projected_margin == light.projected_sunset -
								     (int32_t)base.night_upkeep -
								     (int32_t)f.reserve);
				assert(f.stores_margin ==
				       (afternoon.applies ? afternoon.margin - (int32_t)f.reserve
							  : 0));
				assert(f.allowed == ((f.projected_margin >= 0) &&
						     (!f.stores_applies || f.stores_margin >= 0)));
			}
		}
	}
	const struct toy_factory_garden_dawn_forecast saved = f;
	assert(toy_factory_garden_dawn_forecast(NULL, 1U, &f) == -EINVAL);
	assert(toy_factory_garden_dawn_forecast(&o, 3U, &f) == -EINVAL);
	assert(toy_factory_garden_dawn_forecast(&o, 1U, NULL) == -EINVAL);
	o.sun_strength = 23U;
	assert(toy_factory_garden_dawn_forecast(&o, 1U, &f) == -EINVAL);
	assert(memcmp(&f, &saved, sizeof(f)) == 0);
	o.sun_phase = 124U;
	o.sun_strength = 32U;
	o.plant_node_count = 24U;
	o.stored_energy = 200U;
	assert(toy_factory_garden_dawn_forecast(&o, 1U, &f) == 0 && f.reserve == 20U &&
	       f.first_light_phase == 20U && f.payment_phase == 20U && f.allowed);
	o.stored_energy = 161U;
	assert(toy_factory_garden_dawn_forecast(&o, 1U, &f) == 0 && f.allowed &&
	       f.projected_margin == 0 && f.stores_applies && f.stores_margin == 0);
	o.stored_energy = 160U;
	assert(toy_factory_garden_dawn_forecast(&o, 1U, &f) == 0 && !f.allowed &&
	       f.projected_margin == -1 && f.stores_margin == -1);
	o.stored_energy = 123U;
	assert(toy_factory_garden_dawn_forecast(&o, 2U, &f) == 0 && f.allowed &&
	       f.projected_margin == 0 && !f.stores_applies && f.stores_margin == 0);
	o.stored_energy = 122U;
	assert(toy_factory_garden_dawn_forecast(&o, 2U, &f) == 0 && !f.allowed &&
	       f.projected_margin == -1 && !f.stores_applies);
	o.plant_node_count = UINT16_MAX;
	assert(toy_factory_garden_dawn_forecast(&o, 1U, &f) == 0 && f.reserve == 40960U &&
	       !f.allowed);
	/* Only the configured living offspring after its birth step is restricted. */
	o.plant_node_count = 24U;
	o.stored_energy = 190U;
	o.sun_strength = 24U;
	world.logic_tick_count = 30U;
	o.age_ecology_ticks = 2U;
	world.plants[0].age_ecology_ticks = 2U;
	struct toy_factory_garden_root_choice choice = {.tick = 15U,
							.lineage = 1U,
							.energy_reserve = true,
							.afternoon_reserve = true,
							.continuous_energy = true,
							.daylight_energy = true};
	bool allowed = false;
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) == 0 &&
	       allowed);
	choice.dawn_reserve = true;
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) == 0 &&
	       !allowed);
	choice.lineage = 2U;
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) == 0 &&
	       allowed);
	choice.lineage = 1U;
	world.logic_tick_count = 15U;
	o.age_ecology_ticks = 1U;
	world.plants[0].age_ecology_ticks = 1U;
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) == 0 &&
	       allowed);
	choice.daylight_energy = false;
	assert(toy_factory_garden_root_energy_eligible(&world, &o, &choice, &d, &allowed) ==
		       -ERANGE &&
	       allowed);
}

static void population_contract(void)
{
	struct picosystem_garden_world world;
	struct picosystem_garden_agent_observation o;
	struct picosystem_garden_agent_decision d;
	fixture(&world, &o, &d);
	struct toy_factory_garden_root_choice choice = {.all_offspring = true,
							.energy_reserve = true,
							.afternoon_reserve = true,
							.continuous_energy = true,
							.daylight_energy = true,
							.dawn_reserve = true};
	assert(toy_factory_garden_root_choice_validate(NULL) == -EINVAL);
	assert(toy_factory_garden_root_choice_validate(&choice) == 0);
	const struct picosystem_garden_agent_decision original = d;
	assert(toy_factory_garden_root_choice_apply(&world, &o, &choice,
						    TOY_FACTORY_GARDEN_BUDGET_SHOOT, &d) == 0);
	assert(d.proposal.priority == INT16_MAX);
	assert(!toy_factory_garden_root_energy_active(&world, &o, &choice));
	/* Age 1 is the only boost, at any birth tick. Age 2 starts protection. */
	world.logic_tick_count = 3000U;
	world.plants[0].lineage_id = 400U;
	world.plants[0].generation = 9U;
	world.lineage_sequence = 400U;
	world.maximum_generation = 9U;
	d = original;
	assert(toy_factory_garden_root_choice_apply(&world, &o, &choice,
						    TOY_FACTORY_GARDEN_BUDGET_SHOOT, &d) == 0 &&
	       d.proposal.priority == INT16_MAX);
	world.logic_tick_count += 15U;
	world.plants[0].age_ecology_ticks = 2U;
	o.age_ecology_ticks = 2U;
	d = original;
	assert(toy_factory_garden_root_energy_active(&world, &o, &choice));
	assert(toy_factory_garden_root_choice_apply(&world, &o, &choice,
						    TOY_FACTORY_GARDEN_BUDGET_SHOOT, &d) == 0 &&
	       memcmp(&d, &original, sizeof(d)) == 0);
	/* Slot movement, lineage changes and saturated observations do not expire it. */
	world.plants[1] = world.plants[0];
	world.plant_count = 2U;
	o.plant_index = 1U;
	world.plants[1].lineage_id++;
	assert(toy_factory_garden_root_energy_active(&world, &o, &choice));
	world.logic_tick_count = 65536U * 15U;
	world.plants[1].age_ecology_ticks = 65536U;
	o.age_ecology_ticks = UINT16_MAX;
	assert(toy_factory_garden_root_energy_active(&world, &o, &choice));
	world.plants[1].generation = 0U;
	assert(!toy_factory_garden_root_energy_active(&world, &o, &choice));
	world.plants[1].generation = 1U;
	world.plants[1].flags |= PICOSYSTEM_GARDEN_PLANT_DEAD;
	assert(!toy_factory_garden_root_energy_active(&world, &o, &choice));
	world.plants[1].flags &= (uint8_t)~PICOSYSTEM_GARDEN_PLANT_DEAD;
	o.age_ecology_ticks--;
	assert(!toy_factory_garden_root_energy_active(&world, &o, &choice));
	o.age_ecology_ticks = UINT16_MAX;
	world.logic_tick_count++;
	assert(!toy_factory_garden_root_energy_active(&world, &o, &choice));
	world.logic_tick_count--;
	o.plant_index = PICOSYSTEM_GARDEN_MAX_PLANTS;
	assert(!toy_factory_garden_root_energy_active(&world, &o, &choice));
	fixture(&world, &o, &d);
	bool allowed = false;
	for (uint8_t fault = 0U; fault < 5U; ++fault) {
		struct toy_factory_garden_root_choice bad = choice;
		switch (fault) {
		case 0:
			bad.tick = 15U;
			bad.lineage = 1U;
			break;
		case 1:
			bad.daylight_energy = false;
			break;
		case 2:
			bad.continuous_energy = false;
			break;
		case 3:
			bad.afternoon_reserve = false;
			break;
		default:
			bad.energy_reserve = false;
			break;
		}
		assert(toy_factory_garden_root_energy_eligible(&world, &o, &bad, &d, &allowed) ==
		       -ERANGE);
		assert(!allowed);
		assert(toy_factory_garden_root_choice_apply(
			       &world, &o, &bad, TOY_FACTORY_GARDEN_BUDGET_SHOOT, &d) == -ERANGE);
		assert(memcmp(&d, &original, sizeof(d)) == 0);
	}
}

int main(void)
{
	priority_only();
	energy_contract();
	run_contract();
	trace_contract();
	afternoon_contract();
	continuous_contract();
	daylight_contract();
	dawn_contract();
	population_contract();
	return 0;
}
