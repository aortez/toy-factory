/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_landing_growth.h"
#include "garden_landing_water.h"
#include "garden_evaluation.h"

#include <assert.h>
#include <errno.h>
#include <string.h>

static void projection(void)
{
	struct picosystem_garden_agent_observation o = {.plant_node_count = 31U,
							.candidate_count = 2U};
	o.candidates[1].flags = PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE;
	struct picosystem_garden_agent_decision original = {
		.proposal = {.action = PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND,
			     .tip_index = 17U,
			     .priority = 45,
			     .candidate_count = 2U,
			     .candidate_order = {0U, 1U}},
		.next_memory = {.hidden = {3, -7, 12}}};
	for (uint16_t n = 31U; n <= 33U; ++n) {
		o.plant_node_count = n;
		struct picosystem_garden_agent_decision d = original;
		assert(toy_factory_garden_landing_growth_apply(&o, 0U, &d) == 0);
		assert(memcmp(&d, &original, sizeof(d)) == 0);
		assert(toy_factory_garden_landing_growth_apply(&o, 32U, &d) == 0);
		if (n == 31U) {
			assert(memcmp(&d, &original, sizeof(d)) == 0);
		} else {
			assert(d.proposal.action == PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT);
			assert(d.proposal.candidate_count == 0U);
			for (size_t c = 0U; c < sizeof(d.proposal.candidate_order); ++c) {
				assert(d.proposal.candidate_order[c] ==
				       PICOSYSTEM_GARDEN_AGENT_CANDIDATE_NONE);
			}
			assert(d.proposal.priority == original.proposal.priority);
			assert(d.proposal.tip_index == original.proposal.tip_index);
			assert(memcmp(&d.next_memory, &original.next_memory,
				      sizeof(d.next_memory)) == 0);
		}
	}
	/* No available destination must still execute normal tip cleanup. */
	o.candidates[1].flags = 0U;
	struct picosystem_garden_agent_decision d = original;
	assert(toy_factory_garden_landing_growth_apply(&o, 32U, &d) == 0);
	assert(memcmp(&d, &original, sizeof(d)) == 0);
	for (uint8_t action = 0U; action < PICOSYSTEM_GARDEN_AGENT_ACTION_COUNT; action += 2U) {
		d = original;
		d.proposal.action = action;
		d.proposal.candidate_count = 0U;
		const struct picosystem_garden_agent_decision saved = d;
		assert(toy_factory_garden_landing_growth_apply(&o, 32U, &d) == 0);
		assert(memcmp(&d, &saved, sizeof(d)) == 0);
	}
	d = original;
	assert(toy_factory_garden_landing_growth_apply(&o, 31U, &d) == -ERANGE);
	assert(memcmp(&d, &original, sizeof(d)) == 0);
	d.proposal.candidate_order[1] = 0U;
	const struct picosystem_garden_agent_decision bad = d;
	assert(toy_factory_garden_landing_growth_apply(&o, 32U, &d) == -ERANGE);
	assert(memcmp(&d, &bad, sizeof(d)) == 0);
	assert(toy_factory_garden_landing_growth_apply(NULL, 32U, &d) == -EINVAL);
	assert(toy_factory_garden_landing_growth_apply(&o, 32U, NULL) == -EINVAL);
}

struct observer_counts {
	uint32_t queries;
	uint32_t projected;
	uint8_t limit;
	uint8_t budget_mode;
	bool fail;
};

static int observe(const struct picosystem_garden_world *world,
		   const struct picosystem_garden_agent_observation *observation,
		   const struct picosystem_garden_agent_decision *raw,
		   const struct picosystem_garden_agent_decision *applied, void *context)
{
	struct observer_counts *const counts = context;
	assert(observation->plant_index < world->plant_count);
	assert(world->plants[observation->plant_index].node_count == observation->plant_node_count);
	struct picosystem_garden_agent_decision expected = *raw;
	if (counts->budget_mode == 0U) {
		assert(toy_factory_garden_landing_growth_apply(observation, counts->limit,
							       &expected) == 0);
	} else {
		struct toy_factory_garden_budget_receipt budget;
		assert(toy_factory_garden_landing_budget_assess(world, observation, raw,
								counts->budget_mode, &budget) == 0);
	}
	assert(memcmp(&expected, applied, sizeof(expected)) == 0);
	++counts->queries;
	counts->projected += (raw->proposal.action != applied->proposal.action) ? 1U : 0U;
	return counts->fail ? -ECANCELED : 0;
}

static void check_uptake(const struct picosystem_garden_uptake_audit *a,
			 const struct picosystem_garden_resource_audit *resources)
{
	assert(a->ecology_step == resources->uptake.ecology_step);
	assert(a->source_count <= PICOSYSTEM_GARDEN_MAX_NODES);
	assert(a->root_count <= PICOSYSTEM_GARDEN_MAX_NODES);
	assert(a->leaf_count <= PICOSYSTEM_GARDEN_MAX_NODES);
	uint8_t moisture[PICOSYSTEM_GARDEN_SOIL_CELL_COUNT];
	memcpy(moisture, a->soil_before, sizeof(moisture));
	for (uint16_t i = 0U; i < a->root_count; ++i) {
		const struct picosystem_garden_root_uptake *r = &a->roots[i];
		const size_t cell = (size_t)r->row * PICOSYSTEM_GARDEN_GRID_COLUMNS + r->column;
		assert(cell < sizeof(moisture));
		assert(moisture[cell] == r->before);
		assert(r->taken == ((r->before < r->limit) ? r->before : r->limit));
		assert(r->after == r->before - r->taken);
		assert(r->stored_after ==
		       ((r->stored_before + r->taken > 512U) ? 512U : r->stored_before + r->taken));
		assert((i == 0U) || (a->roots[i - 1U].slot < r->slot) ||
		       ((a->roots[i - 1U].slot == r->slot) && (a->roots[i - 1U].node < r->node)));
		moisture[cell] = r->after;
	}
	assert(memcmp(moisture, a->soil_after, sizeof(moisture)) == 0);
	for (uint8_t p = 0U; p < resources->uptake.count; ++p) {
		const struct picosystem_garden_death_event *event = &resources->uptake.events[p];
		uint32_t energy = 0U, water = 0U;
		for (uint16_t i = 0U; i < a->root_count; ++i) {
			if (a->roots[i].lineage == event->lineage_id) {
				water += a->roots[i].taken;
			}
		}
		for (uint16_t i = 0U; i < a->leaf_count; ++i) {
			const struct picosystem_garden_leaf_uptake *l = &a->leaves[i];
			assert(l->income == l->light / 64U);
			assert(l->light ==
			       a->light[(size_t)l->row * PICOSYSTEM_GARDEN_GRID_COLUMNS +
					l->column]);
			if (l->lineage == event->lineage_id) {
				energy += l->income;
			}
		}
		assert(energy == event->energy.income && water == event->water.income);
	}
}

static void observed(const struct picosystem_garden_world *initial,
		     const struct toy_factory_garden_landing_model *model)
{
	for (uint8_t variant = 0U; variant < 4U; ++variant) {
		const uint8_t limit = variant ? 32U : 0U;
		struct toy_factory_garden_landing_growth_run traced, plain;
		assert((variant < 2U
				? toy_factory_garden_landing_growth_init(initial, model, limit,
									 &traced)
				: toy_factory_garden_landing_budget_init(
					  initial, model, (uint8_t)(variant - 2U), &traced)) == 0);
		const struct toy_factory_garden_landing_growth_run start = traced;
		plain = traced;
		struct picosystem_garden_death_audit deaths, other_deaths;
		struct picosystem_garden_seed_audit seeds, other_seeds;
		struct picosystem_garden_resource_audit resources, other_resources;
		struct picosystem_garden_reproduction_audit reproduction;
		struct picosystem_garden_uptake_audit uptake;
		struct observer_counts counts = {.limit = limit, .budget_mode = traced.budget_mode};
		struct toy_factory_garden_growth_observer observer = {
			.observe = observe, .context = &counts, .reproduction = &reproduction};
#if !defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE) &&                                               \
	!defined(TOY_FACTORY_GARDEN_CANOPY_TRANSMISSION) &&                                        \
	!defined(TOY_FACTORY_GARDEN_SEED_RESERVE) &&                                               \
	!defined(TOY_FACTORY_GARDEN_FOCAL_SEED_VETO) && !defined(TOY_FACTORY_GARDEN_DARK_GUARD) && \
	!defined(TOY_FACTORY_GARDEN_SEED_ORDER)
		observer.uptake = &uptake;
#endif
		uint32_t purchases = 0U;
		for (uint32_t t = 0U; t < 2U * 3840U; ++t) {
			assert(toy_factory_garden_landing_growth_step(
				       &plain, &other_deaths, &other_seeds, &other_resources) == 0);
			assert(toy_factory_garden_landing_growth_step_observed(
				       &traced, &deaths, &seeds, &resources, &observer) == 0);
			assert(memcmp(&traced, &plain, sizeof(traced)) == 0);
			assert(memcmp(&deaths, &other_deaths, sizeof(deaths)) == 0);
			assert(memcmp(&seeds, &other_seeds, sizeof(seeds)) == 0);
			assert(memcmp(&resources, &other_resources, sizeof(resources)) == 0);
			if (observer.uptake != NULL) {
				check_uptake(&uptake, &resources);
			}
			if (limit != 0U) {
				for (uint8_t p = 0U; p < traced.base.world.plant_count; ++p) {
					assert(traced.base.world.plants[p].node_count <= 32U);
				}
			}
			assert(reproduction.ecology_step == deaths.ecology_step);
			for (uint8_t p = 0U; p < reproduction.count; ++p) {
				const struct picosystem_garden_reproduction_visit *const v =
					&reproduction.visits[p];
				assert(v->produced == (v->blockers == 0U));
				purchases += v->produced ? 1U : 0U;
			}
		}
		assert(counts.queries > 0U);
		assert((variant != 1U) == (counts.projected == 0U));
		assert(purchases == traced.base.world.seed_creation_count);
		traced = start;
		traced.base.world.logic_tick_count = 14U;
		plain = traced;
		counts.fail = true;
		memset(&deaths, 0xa5, sizeof(deaths));
		memset(&seeds, 0xa5, sizeof(seeds));
		memset(&resources, 0xa5, sizeof(resources));
		memset(&reproduction, 0xa5, sizeof(reproduction));
		memset(&uptake, 0xa5, sizeof(uptake));
		const struct picosystem_garden_uptake_audit saved_uptake = uptake;
		other_deaths = deaths;
		other_seeds = seeds;
		other_resources = resources;
		const struct picosystem_garden_reproduction_audit saved = reproduction;
		assert(toy_factory_garden_landing_growth_step_observed(
			       &traced, &deaths, &seeds, &resources, &observer) == -ECANCELED);
		assert(memcmp(&traced, &plain, sizeof(traced)) == 0);
		assert(memcmp(&deaths, &other_deaths, sizeof(deaths)) == 0);
		assert(memcmp(&seeds, &other_seeds, sizeof(seeds)) == 0);
		assert(memcmp(&resources, &other_resources, sizeof(resources)) == 0);
		assert(memcmp(&reproduction, &saved, sizeof(reproduction)) == 0);
		assert(memcmp(&uptake, &saved_uptake, sizeof(uptake)) == 0);
		assert(toy_factory_garden_landing_growth_step_observed(&traced, &deaths, &seeds,
								       NULL, &observer) == -EINVAL);
		assert(toy_factory_garden_landing_growth_step_observed(
			       &traced, &deaths, &seeds, &resources, NULL) == -EINVAL);
		observer.observe = NULL;
		assert(toy_factory_garden_landing_growth_step_observed(
			       &traced, &deaths, &seeds, &resources, &observer) == -EINVAL);
		observer.observe = observe;
		observer.reproduction = NULL;
		assert(toy_factory_garden_landing_growth_step_observed(
			       &traced, &deaths, &seeds, &resources, &observer) == -EINVAL);
		observer.reproduction = &reproduction;
		counts.fail = false;
		assert(toy_factory_garden_landing_growth_step_observed(&traced, &deaths, &seeds,
								       &resources, &observer) == 0);
	}
}

static struct picosystem_garden_world budget_world(uint16_t count)
{
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, 3U) == 0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 3U) ==
	       0);
	world.plants[0].genome.stature = 0;
	world.nodes[1].depth = 10U;
	assert(world.nodes[1].kind == PICOSYSTEM_GARDEN_NODE_STEM);
	assert(world.nodes[2].kind == PICOSYSTEM_GARDEN_NODE_ROOT);
	for (uint16_t i = world.node_count; i < count; ++i) {
		world.nodes[i] =
			(struct picosystem_garden_node){.parent_index = PICOSYSTEM_GARDEN_NODE_NONE,
							.kind = PICOSYSTEM_GARDEN_NODE_ROOT,
							.x = 230U,
							.y = 220U};
	}
	world.node_count = count;
	world.plants[0].node_count = count;
	return world;
}

static struct toy_factory_garden_budget_receipt assess(const struct picosystem_garden_world *world,
						       uint16_t tip, uint8_t mode, uint8_t action)
{
	struct picosystem_garden_agent_observation o;
	assert(picosystem_garden_agent_observe_tip(world, 0U, tip, 42U, &o) == 0);
	struct picosystem_garden_agent_decision d = {
		.proposal = {.tip_index = tip, .action = action}};
	if (action == PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND) {
		d.proposal.candidate_count = o.candidate_count;
		for (uint8_t c = 0U; c < o.candidate_count; ++c) {
			d.proposal.candidate_order[c] = c;
			o.candidates[c].flags |= PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE;
		}
	}
	const struct picosystem_garden_world before = *world;
	const struct picosystem_garden_agent_observation input = o;
	const struct picosystem_garden_agent_decision decision = d;
	struct toy_factory_garden_budget_receipt result;
	assert(toy_factory_garden_landing_budget_assess(world, &o, &d, mode, &result) == 0);
	assert(memcmp(world, &before, sizeof(before)) == 0);
	assert(memcmp(&o, &input, sizeof(o)) == 0);
	assert(memcmp(&d, &decision, sizeof(d)) == 0);
	const struct toy_factory_garden_budget_receipt saved = result;
	assert(toy_factory_garden_landing_budget_assess(world, &o, &d, 0U, &result) == -ERANGE);
	assert(memcmp(&result, &saved, sizeof(result)) == 0);
	assert(toy_factory_garden_landing_budget_assess(NULL, &o, &d, mode, &result) == -EINVAL);
	assert(memcmp(&result, &saved, sizeof(result)) == 0);
	d.proposal.tip_index = UINT16_MAX;
	assert(toy_factory_garden_landing_budget_assess(world, &o, &d, mode, &result) == -ERANGE);
	assert(memcmp(&result, &saved, sizeof(result)) == 0);
	return result;
}

static void budget_boundaries(void)
{
	for (uint16_t n = 26U; n <= 33U; ++n) {
		struct picosystem_garden_world world = budget_world(n);
		const struct toy_factory_garden_budget_receipt root = assess(&world, 2U, 2U, 1U);
		const struct toy_factory_garden_budget_receipt stem = assess(&world, 1U, 2U, 1U);
		assert(root.leader == 1U && root.remaining == 5U && root.required == n + 6U);
		assert(root.allowed == (n <= 26U));
		assert(stem.required == n + 5U && stem.allowed == (n <= 27U));
		assert(assess(&world, 2U, 1U, 1U).allowed == (n < 32U));
		assert(assess(&world, 1U, 2U, 2U).allowed); /* FINISH is not invented or denied. */
		assert(assess(&world, 2U, 2U, 0U).allowed);
		world.nodes[0].flags |= PICOSYSTEM_GARDEN_NODE_FLOWER;
		assert(assess(&world, 2U, 2U, 1U).remaining == 0U);
		assert(assess(&world, 2U, 2U, 1U).allowed == (n < 32U));
		world.nodes[0].flags &= (uint8_t)~PICOSYSTEM_GARDEN_NODE_FLOWER;
		world.nodes[1].flags &= (uint8_t)~PICOSYSTEM_GARDEN_NODE_TIP;
		assert(assess(&world, 2U, 2U, 1U).leader == PICOSYSTEM_GARDEN_NODE_NONE);
		assert(assess(&world, 2U, 2U, 1U).allowed == (n < 32U));
	}
	struct picosystem_garden_world world = budget_world(27U);
	world.plants[0].genome.stature = 2;
	assert(assess(&world, 2U, 2U, 1U).remaining == 7U);
	world.nodes[4] = world.nodes[1];
	assert(assess(&world, 4U, 2U, 1U).leader == 1U); /* Equal depths use lowest index. */
	world.nodes[4].depth = 11U;
	assert(assess(&world, 4U, 2U, 1U).leader == 4U);
	assert(assess(&world, 4U, 2U, 1U).remaining == 6U);
	struct picosystem_garden_agent_observation o;
	assert(picosystem_garden_agent_observe_tip(&world, 0U, 2U, 0U, &o) == 0);
	struct picosystem_garden_agent_decision d = {
		.proposal = {.tip_index = 2U,
			     .action = PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND,
			     .candidate_count = o.candidate_count}};
	for (uint8_t c = 0U; c < o.candidate_count; ++c) {
		o.candidates[c].flags &= (uint8_t)~PICOSYSTEM_GARDEN_AGENT_CANDIDATE_AVAILABLE;
		d.proposal.candidate_order[c] = c;
	}
	struct toy_factory_garden_budget_receipt cleanup;
	assert(toy_factory_garden_landing_budget_assess(&world, &o, &d, 2U, &cleanup) == 0);
	assert(cleanup.allowed && !cleanup.allocates && cleanup.required == 27U);
}

static int scripted_budget(const struct picosystem_garden_agent_observation *o,
			   const struct picosystem_garden_agent_memory *memory,
			   struct picosystem_garden_agent_decision *d, const void *context)
{
	(void)context;
	*d = (struct picosystem_garden_agent_decision){
		.proposal = {.tip_index = o->tip_index,
			     .action = PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND,
			     .priority = o->tissue_kind ? 100 : 1,
			     .candidate_count = o->candidate_count},
		.next_memory = *memory};
	for (uint8_t c = 0U; c < o->candidate_count; ++c) {
		d->proposal.candidate_order[c] = c;
	}
	d->next_memory.hidden[0] = (int8_t)(o->tissue_kind + 1U);
	return 0;
}

static int eligible_budget(const struct picosystem_garden_agent_observation *o,
			   const struct picosystem_garden_agent_decision *d, bool *allowed,
			   const void *context)
{
	struct toy_factory_garden_budget_receipt receipt;
	const int err = toy_factory_garden_landing_budget_assess(context, o, d, 2U, &receipt);
	if (err == 0) {
		*allowed = receipt.allowed;
	}
	return err;
}

static void budget_selection(void)
{
	/* A high-priority refused root must not become an eligible WAIT. */
	struct picosystem_garden_world world = budget_world(27U);
	world.logic_tick_count = 14U;
	world.auto_gardener_enabled = false;
	const uint32_t random = world.plants[0].random_state;
	struct picosystem_garden_agent_policy policy = {
		.decide = scripted_budget,
		.arbitration = PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS,
		.eligible = eligible_budget,
		.eligibility_context = &world};
	assert(picosystem_garden_world_step_with_policy(&world, &policy) == 0);
	assert(world.plants[0].agent_telemetry.last_tissue_kind == PICOSYSTEM_GARDEN_NODE_STEM);
	assert(world.plants[0].agent_telemetry.last_action ==
	       PICOSYSTEM_GARDEN_AGENT_ACTION_EXTEND);
	assert(world.node_count == 28U && world.plants[0].agent_memory.hidden[0] == 1);
	assert(world.plants[0].random_state != random);
	world = budget_world(32U);
	world.logic_tick_count = 14U;
	world.auto_gardener_enabled = false;
	assert(picosystem_garden_world_step_with_policy(&world, &policy) == 0);
	assert(world.plants[0].agent_telemetry.last_tissue_kind == PICOSYSTEM_GARDEN_NODE_ROOT);
	assert(world.plants[0].agent_telemetry.last_action == PICOSYSTEM_GARDEN_AGENT_ACTION_WAIT);
	assert(world.node_count == 32U && world.plants[0].agent_memory.hidden[0] == 2);
}

int main(void)
{
	projection();
	budget_boundaries();
	budget_selection();
	struct picosystem_garden_world world;
	assert(toy_factory_garden_evaluation_reset(&world, &toy_factory_garden_rainfed_scenarios[1],
						   0x940cfdc4U) == 0);
	struct toy_factory_garden_landing_model model;
	const struct toy_factory_garden_landing_feature_config features = {.version = 1U,
									   .mode = 1U};
	assert(toy_factory_garden_landing_model_import(picosystem_garden_neural_reference_model(),
						       &features, &model) == 0);
	observed(&world, &model);
	struct toy_factory_garden_landing_growth_run off, on;
	struct toy_factory_garden_landing_water_run eligible;
	const struct toy_factory_garden_landing_water_config water = {
		.version = 2U, .enabled = 1U, .eligible = 1U};
	assert(toy_factory_garden_landing_growth_init(&world, &model, 0U, &off) == 0);
	assert(toy_factory_garden_landing_growth_init(&world, &model, 32U, &on) == 0);
	assert(toy_factory_garden_landing_water_init(&world, &model, &water, &eligible) == 0);
	uint32_t a, b;
	assert(toy_factory_garden_landing_growth_hash(&off, &a) == 0);
	assert(toy_factory_garden_landing_growth_hash(&on, &b) == 0 && a != b);
	struct toy_factory_garden_landing_growth_run plain = on;
	struct picosystem_garden_death_audit deaths, other_deaths;
	struct picosystem_garden_seed_audit seeds, other_seeds;
	struct picosystem_garden_resource_audit resources;
	bool reached_limit = false, control_exceeded = false;
	for (uint32_t t = 0U; t < 32U * 3840U; ++t) {
		assert(toy_factory_garden_landing_growth_step(&off, &deaths, &seeds, NULL) == 0);
		assert(toy_factory_garden_landing_water_step(&eligible, &other_deaths, &other_seeds,
							     NULL, NULL) == 0);
		assert(memcmp(&off.base, &eligible.base, sizeof(off.base)) == 0);
		assert(memcmp(&deaths, &other_deaths, sizeof(deaths)) == 0);
		assert(memcmp(&seeds, &other_seeds, sizeof(seeds)) == 0);
		assert(toy_factory_garden_landing_growth_step(&on, &deaths, &seeds, &resources) ==
		       0);
		assert(toy_factory_garden_landing_growth_step(&plain, &other_deaths, &other_seeds,
							      NULL) == 0);
		assert(memcmp(&on, &plain, sizeof(on)) == 0);
		assert(memcmp(&deaths, &other_deaths, sizeof(deaths)) == 0);
		assert(memcmp(&seeds, &other_seeds, sizeof(seeds)) == 0);
		for (uint8_t p = 0U; p < on.base.world.plant_count; ++p) {
			assert(on.base.world.plants[p].node_count <= 32U);
			reached_limit |= on.base.world.plants[p].node_count == 32U;
		}
		for (uint8_t p = 0U; p < off.base.world.plant_count; ++p) {
			control_exceeded |= off.base.world.plants[p].node_count > 32U;
		}
	}
	assert(reached_limit && control_exceeded);
	assert(memcmp(&model, &on.base.model, sizeof(model)) == 0);
	const struct toy_factory_garden_landing_growth_run saved = on;
	assert(toy_factory_garden_landing_budget_init(&world, &model, 2U, &on) == -ERANGE);
	assert(memcmp(&saved, &on, sizeof(on)) == 0);
	assert(toy_factory_garden_landing_budget_init(&world, &model, 1U, NULL) == -EINVAL);
	on.budget_mode = TOY_FACTORY_GARDEN_BUDGET_COUNT;
	a = 0xabcdef01U;
	assert(toy_factory_garden_landing_growth_hash(&on, &a) == -ERANGE && a == 0xabcdef01U);
	on = saved;
	assert(toy_factory_garden_landing_growth_init(&world, &model, 33U, &on) == -ERANGE);
	assert(memcmp(&saved, &on, sizeof(on)) == 0);
	assert(toy_factory_garden_landing_growth_step(NULL, &deaths, &seeds, NULL) == -EINVAL);
	assert(toy_factory_garden_landing_growth_step(&on, NULL, &seeds, NULL) == -EINVAL);
	assert(toy_factory_garden_landing_growth_step(&on, &deaths, NULL, NULL) == -EINVAL);
	/* Real world-step failure must preserve checkpoint and all receipts. */
	assert(toy_factory_garden_landing_growth_init(&world, &model, 32U, &on) == 0);
	on.base.world.logic_tick_count = 14U;
	on.base.world.nodes[1].x = 0U;
	const struct toy_factory_garden_landing_growth_run failing = on;
	memset(&deaths, 0xa5, sizeof(deaths));
	memset(&seeds, 0xa5, sizeof(seeds));
	memset(&resources, 0xa5, sizeof(resources));
	other_deaths = deaths;
	other_seeds = seeds;
	const struct picosystem_garden_resource_audit saved_resources = resources;
	assert(toy_factory_garden_landing_growth_step(&on, &deaths, &seeds, &resources) != 0);
	assert(memcmp(&failing, &on, sizeof(on)) == 0);
	assert(memcmp(&deaths, &other_deaths, sizeof(deaths)) == 0);
	assert(memcmp(&seeds, &other_seeds, sizeof(seeds)) == 0);
	assert(memcmp(&resources, &saved_resources, sizeof(resources)) == 0);
	on = saved;
	assert(toy_factory_garden_landing_growth_step(&on, &deaths, &seeds, &resources) == 0);
	return 0;
}
