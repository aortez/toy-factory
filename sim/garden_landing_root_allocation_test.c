/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_root_allocation.h"
#include "garden_landing_growth.h"
#include "garden_landing_plant_trace.h"
#include "garden_evaluation.h"
#include "garden_seedling_reserve.h"

#include <assert.h>
#include <errno.h>
#include <string.h>

static struct toy_factory_garden_root_choice guards(void)
{
	return (struct toy_factory_garden_root_choice){.all_offspring = true,
						       .energy_reserve = true,
						       .afternoon_reserve = true,
						       .continuous_energy = true,
						       .daylight_energy = true};
}

static void fixture(struct picosystem_garden_world *world,
		    struct picosystem_garden_agent_observation *o,
		    struct picosystem_garden_agent_decision *d,
		    struct toy_factory_garden_root_allocation *c)
{
	assert(picosystem_garden_world_reset(world, 3U) == 0);
	world->auto_gardener_enabled = false;
	assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_SHRUB, 24U) ==
	       0);
	*c = (struct toy_factory_garden_root_allocation)TOY_FACTORY_GARDEN_ROOT_ALLOCATION_FOCAL;
	world->plants[0].lineage_id = c->lineage;
	world->lineage_sequence = c->lineage;
	world->plants[0].parent_lineage_id = c->parent;
	world->plants[0].generation = 1U;
	world->maximum_generation = 1U;
	world->plants[0].age_ecology_ticks = 2U;
	world->logic_tick_count = c->birth_tick + 15U;
	assert(picosystem_garden_agent_observe_tip(world, 0U, 2U, 42U, o) == 0);
	for (uint16_t n = world->node_count; n < 29U; ++n) {
		world->nodes[n] = world->nodes[1];
		world->nodes[n].flags = 0U;
	}
	world->node_count = 29U;
	world->plants[0].node_count = 29U;
	world->nodes[1].flags |= PICOSYSTEM_GARDEN_NODE_FLOWER;
	o->plant_node_count = 29U;
	o->root_node_count = 3U;
	o->shoot_node_count = 26U;
	o->stored_energy = 256U;
	o->stored_water = 290U;
	o->last_water_income = 1U;
	o->last_energy_income = 1U;
	o->sun_phase = 100U;
	o->sun_strength = 255U;
	o->tip_moisture = 0U;
	*d = (struct picosystem_garden_agent_decision){
		.next_memory = {.hidden = {3, -7, 12}},
		.proposal = {.tip_index = 2U,
			     .action = PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND,
			     .priority = 21,
			     .candidate_count = 3U,
			     .candidate_order = {2U, 1U, 0U}}};
	for (uint8_t i = 0U; i < o->candidate_count; ++i) {
		o->candidates[i].flags = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE |
					 PICOSYSTEM_GARDEN_AGENT_CANDIDATE_IN_BOUNDS;
		o->candidates[i].moisture = 18U;
	}
}

static void predicates(void)
{
	for (unsigned int fault = 0U; fault < 30U; ++fault) {
		struct picosystem_garden_world w;
		struct picosystem_garden_agent_observation o;
		struct picosystem_garden_agent_decision d;
		struct toy_factory_garden_root_allocation c;
		fixture(&w, &o, &d, &c);
		struct toy_factory_garden_root_choice g = guards();
		bool boost = false;
		int error = 0;
		switch (fault) {
		case 0:
			boost = true;
			break; /* Both rate equalities. */
		case 1:
			o.last_water_income = 2U;
			break;
		case 2:
			o.last_energy_income = 0U;
			break;
		case 3:
			o.last_water_income = 0U;
			boost = true;
			break;
		case 4:
			o.candidates[2].moisture = 0U;
			break;
		case 5:
			for (uint8_t i = 0U; i < o.candidate_count; ++i) {
				o.candidates[i].flags = 1U;
			}
			break;
		case 6:
			o.candidates[2].flags = 1U;
			boost = true;
			break;
		case 7:
			o.depth = o.maximum_depth;
			break;
		case 8:
			d.proposal.action = PICOSYSTEM_GARDEN_AGENT_ACTION_FINISH_TIP;
			d.proposal.candidate_count = 0U;
			break;
		case 9:
			o.tissue_kind = PICOSYSTEM_GARDEN_NODE_STEM;
			o.candidate_count = 5U;
			d.proposal.candidate_count = 5U;
			d.proposal.candidate_order[3] = 3U;
			d.proposal.candidate_order[4] = 4U;
			break;
		case 10:
			o.stored_water = 4U;
			break;
		case 11:
			o.stored_water = 5U;
			break; /* Price fits, first-day guard does not. */
		case 12:
			o.stored_energy = 0U;
			break;
		case 13:
			o.stored_energy = 8U;
			o.sun_phase = PICOSYSTEM_GARDEN_SUN_SUNSET_PHASE;
			break;
		case 14:
			o.plant_node_count = 32U;
			o.shoot_node_count = 29U;
			w.node_count = 32U;
			w.plants[0].node_count = 32U;
			break;
		case 15:
			w.nodes[1].flags &= (uint8_t)~PICOSYSTEM_GARDEN_NODE_FLOWER;
			break;
		case 16:
			c.lineage = 10U;
			break;
		case 17:
			c.birth_tick -= 15U;
			break;
		case 18:
			o.age_ecology_ticks = 1U;
			w.plants[0].age_ecology_ticks = 1U;
			w.logic_tick_count = c.birth_tick;
			break;
		case 19:
			w.plants[0].generation = 0U;
			error = -ESTALE;
			break;
		case 20:
			w.plants[0].flags |= PICOSYSTEM_GARDEN_PLANT_DEAD;
			break;
		case 21:
			w.plants[0].age_ecology_ticks = 70000U;
			o.age_ecology_ticks = UINT16_MAX;
			w.logic_tick_count = c.birth_tick + 69999U * 15U;
			boost = true;
			break;
		case 22:
			d.proposal.priority = INT16_MAX;
			break;
		case 23:
			d.proposal.priority = INT16_MAX - 1;
			break;
		case 24:
			c = (struct toy_factory_garden_root_allocation){0};
			break;
		case 25:
			g.wet_direction = true;
			error = -ERANGE;
			break;
		case 26:
			g.all_offspring = false;
			error = -ERANGE;
			break;
		case 27:
			d.proposal.candidate_order[0] = 1U;
			error = -ERANGE;
			break;
		case 28:
			c.version = 2U;
			error = -ERANGE;
			break;
		case 29:
			g.dawn_reserve = true;
			boost = true;
			break;
		default:
			assert(false);
		}
		const struct picosystem_garden_world saved_w = w;
		const struct picosystem_garden_agent_observation saved_o = o;
		const struct toy_factory_garden_root_allocation saved_c = c;
		struct picosystem_garden_agent_decision expected = d;
		if (boost) {
			expected.proposal.priority = INT16_MAX - 2;
		}
		struct toy_factory_garden_root_allocation_receipt receipt = {
			.active = true, .eligible = true, .prefer = true};
		const struct toy_factory_garden_root_allocation_receipt saved_r = receipt;
		const int actual =
			toy_factory_garden_root_allocation_apply(&w, &o, &c, &g, 2U, &d, &receipt);
		if ((actual != error) || (memcmp(&d, &expected, sizeof(d)) != 0)) {
			fprintf(stderr, "allocation case %u: error %d/%d priority %d/%d\n", fault,
				actual, error, d.proposal.priority, expected.proposal.priority);
		}
		assert(actual == error);
		assert(memcmp(&d, &expected, sizeof(d)) == 0);
		assert(memcmp(&w, &saved_w, sizeof(w)) == 0);
		assert(memcmp(&o, &saved_o, sizeof(o)) == 0);
		assert(memcmp(&c, &saved_c, sizeof(c)) == 0);
		if (error) {
			assert(memcmp(&receipt, &saved_r, sizeof(receipt)) == 0);
		}
	}
}

static void guard_matrix_and_trace(void)
{
	struct picosystem_garden_world w;
	struct picosystem_garden_agent_observation o;
	struct picosystem_garden_agent_decision d;
	struct toy_factory_garden_root_allocation c;
	fixture(&w, &o, &d, &c);
	struct toy_factory_garden_root_choice g = guards();
	g.dawn_reserve = true;
	o.last_water_income = 0U;
	unsigned int denied[4] = {0U};
	for (uint16_t nodes = 24U; nodes <= 29U; nodes += 5U) {
		w.node_count = nodes;
		w.plants[0].node_count = nodes;
		o.plant_node_count = nodes;
		o.shoot_node_count = (uint16_t)(nodes - 3U);
		for (uint16_t phase = 64U; phase < 128U; phase += 3U) {
			for (uint16_t stored = 16U; stored <= 256U; stored += 8U) {
				for (uint16_t income = 1U; income <= 16U; income += 3U) {
					o.sun_phase = (uint8_t)phase;
					o.sun_strength =
						picosystem_garden_sun_at((uint32_t)phase + 192U)
							.strength;
					o.stored_energy = stored;
					o.last_energy_income = (uint8_t)income;
					struct toy_factory_garden_reserve_forecast e;
					struct toy_factory_garden_afternoon_forecast a;
					struct toy_factory_garden_daylight_forecast l;
					struct toy_factory_garden_dawn_forecast dawn;
					assert(toy_factory_garden_reserve_forecast(
						       &o, d.proposal.action, &e) == 0);
					assert(toy_factory_garden_afternoon_forecast(
						       &o, d.proposal.action, &a) == 0);
					assert(toy_factory_garden_daylight_forecast(
						       &o, d.proposal.action, &l) == 0);
					assert(toy_factory_garden_dawn_forecast(
						       &o, d.proposal.action, &dawn) == 0);
					const bool gates[] = {e.allowed, a.allowed, l.allowed,
							      dawn.allowed};
					bool eligible = true;
					for (size_t i = 0U; i < 4U; ++i) {
						denied[i] += eligible && !gates[i] ? 1U : 0U;
						eligible = eligible && gates[i];
					}
					struct picosystem_garden_agent_decision applied = d;
					struct toy_factory_garden_root_allocation_receipt receipt;
					assert(toy_factory_garden_root_allocation_apply(
						       &w, &o, &c, &g, 2U, &applied, &receipt) ==
					       0);
					assert(receipt.prefer == eligible);
					assert(applied.proposal.priority ==
					       (eligible ? INT16_MAX - 2 : d.proposal.priority));
				}
			}
		}
	}
	for (size_t i = 0U; i < 4U; ++i) {
		if (denied[i] == 0U) {
			fprintf(stderr, "allocation guard %zu has no exclusive denial fixture\n",
				i);
		}
		assert(denied[i] > 0U);
	}
	fixture(&w, &o, &d, &c);
	const struct picosystem_garden_agent_decision raw = d;
	assert(toy_factory_garden_root_allocation_apply(&w, &o, &c, &g, 2U, &d, NULL) == 0);
	FILE *stream = tmpfile();
	assert(stream != NULL);
	struct toy_factory_garden_plant_trace trace;
	struct picosystem_garden_world initial = w;
	initial.logic_tick_count = 0U;
	assert(toy_factory_garden_plant_trace_init(&trace, stream, &initial, 32U, 2U,
						   w.logic_tick_count, w.logic_tick_count,
						   TOY_FACTORY_GARDEN_TRACE_DAWN) == 0);
	trace.root_choice = g;
	trace.root_allocation = c;
	assert(toy_factory_garden_plant_trace_observe(&w, &o, &raw, &d, &trace) == 0);
	const uint16_t count = trace.count;
	d.proposal.priority--;
	assert(toy_factory_garden_plant_trace_observe(&w, &o, &raw, &d, &trace) == -EFAULT);
	assert(trace.count == count);
	d.proposal.priority++;
	d.next_memory.hidden[0]++;
	assert(toy_factory_garden_plant_trace_observe(&w, &o, &raw, &d, &trace) == -EFAULT);
	assert(trace.count == count);
	assert(fclose(stream) == 0);
}

static int reject(const struct picosystem_garden_world *w,
		  const struct picosystem_garden_agent_observation *o,
		  const struct picosystem_garden_agent_decision *raw,
		  const struct picosystem_garden_agent_decision *applied, void *context)
{
	(void)w;
	(void)o;
	(void)raw;
	(void)applied;
	(void)context;
	return -ECANCELED;
}

static void rollback_and_identity(void)
{
	struct picosystem_garden_world w;
	assert(toy_factory_garden_evaluation_reset(&w, &toy_factory_garden_rainfed_scenarios[1],
						   3U) == 0);
	struct toy_factory_garden_landing_model model;
	const struct toy_factory_garden_landing_feature_config features = {.version = 1U,
									   .mode = 1U};
	assert(toy_factory_garden_landing_model_import(picosystem_garden_neural_reference_model(),
						       &features, &model) == 0);
	struct toy_factory_garden_landing_growth_run run;
	assert(toy_factory_garden_landing_placement_init(&w, &model, 1U, 1U, &run) == 0);
	run.root_choice = guards();
	uint32_t control, enabled, other;
	assert(toy_factory_garden_landing_growth_hash(&run, &control) == 0);
	run.root_allocation =
		(struct toy_factory_garden_root_allocation)TOY_FACTORY_GARDEN_ROOT_ALLOCATION_FOCAL;
	assert(toy_factory_garden_landing_growth_hash(&run, &enabled) == 0);
	assert(control != enabled);
	run.root_allocation.lineage++;
	assert(toy_factory_garden_landing_growth_hash(&run, &other) == 0);
	assert(enabled != other);
	run.root_allocation.lineage--;
	struct picosystem_garden_death_audit deaths;
	struct picosystem_garden_seed_audit seeds;
	struct picosystem_garden_resource_audit resources;
	struct picosystem_garden_reproduction_audit reproduction;
	for (unsigned int i = 0U; i < 14U; ++i) {
		assert(toy_factory_garden_landing_growth_step(&run, &deaths, &seeds, &resources) ==
		       0);
	}
	const struct toy_factory_garden_landing_growth_run before = run;
	memset(&deaths, 0xa5, sizeof(deaths));
	memset(&seeds, 0xa5, sizeof(seeds));
	memset(&resources, 0xa5, sizeof(resources));
	memset(&reproduction, 0xa5, sizeof(reproduction));
	const struct picosystem_garden_death_audit saved_deaths = deaths;
	const struct picosystem_garden_seed_audit saved_seeds = seeds;
	const struct picosystem_garden_resource_audit saved_resources = resources;
	const struct picosystem_garden_reproduction_audit saved_reproduction = reproduction;
	const struct toy_factory_garden_growth_observer observer = {.observe = reject,
								    .reproduction = &reproduction};
	assert(toy_factory_garden_landing_growth_step_observed(&run, &deaths, &seeds, &resources,
							       &observer) == -ECANCELED);
	assert(memcmp(&run, &before, sizeof(run)) == 0);
	assert(memcmp(&deaths, &saved_deaths, sizeof(deaths)) == 0);
	assert(memcmp(&seeds, &saved_seeds, sizeof(seeds)) == 0);
	assert(memcmp(&resources, &saved_resources, sizeof(resources)) == 0);
	assert(memcmp(&reproduction, &saved_reproduction, sizeof(reproduction)) == 0);
	assert(toy_factory_garden_landing_growth_step(&run, &deaths, &seeds, &resources) == 0);
	struct toy_factory_garden_landing_growth_run repeat = before;
	assert(toy_factory_garden_landing_growth_step(&repeat, &deaths, &seeds, &resources) == 0);
	assert(memcmp(&run, &repeat, sizeof(run)) == 0);
}

int main(void)
{
	predicates();
	guard_matrix_and_trace();
	rollback_and_identity();
	return 0;
}
