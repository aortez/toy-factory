/* SPDX-License-Identifier: Apache-2.0 */
#include "research_session.h"
#include "research_models.h"
#include "garden_leaf_family.h"
#include "garden_leaf_owned.h"
#include "garden_landing_ledger.h"

#include <assert.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>

static bool fail_allocation;
static bool fail_owned_allocation;
static bool fail_audit;
static unsigned int allocations;
static struct toy_factory_leaf_family observed;

int __real_toy_factory_leaf_owned_snapshot(const struct toy_factory_leaf_owned *run,
					   struct toy_factory_leaf_family *out);
int __wrap_toy_factory_leaf_owned_snapshot(const struct toy_factory_leaf_owned *run,
					   struct toy_factory_leaf_family *out)
{
	const int err = __real_toy_factory_leaf_owned_snapshot(run, out);
	if (err == 0) {
		observed = *out;
	}
	return err;
}

void *__real_malloc(size_t size);
void *__wrap_malloc(size_t size)
{
	++allocations;
	return (fail_allocation || fail_owned_allocation) ? NULL : __real_malloc(size);
}

void *__real_calloc(size_t count, size_t size);
void *__wrap_calloc(size_t count, size_t size)
{
	++allocations;
	return fail_allocation ? NULL : __real_calloc(count, size);
}

int __real_toy_factory_garden_landing_ledger_step(
	struct toy_factory_garden_landing_ledger *out, const struct picosystem_garden_world *world,
	const struct toy_factory_garden_lifetimes *lifetimes,
	const struct picosystem_garden_seed_audit *audit);
int __wrap_toy_factory_garden_landing_ledger_step(
	struct toy_factory_garden_landing_ledger *out, const struct picosystem_garden_world *world,
	const struct toy_factory_garden_lifetimes *lifetimes,
	const struct picosystem_garden_seed_audit *audit)
{
	const int err = __real_toy_factory_garden_landing_ledger_step(out, world, lifetimes, audit);
	return ((err == 0) && fail_audit) ? -ENOSPC : err;
}

static void equal(struct research_session *a, struct research_session *b)
{
	uint8_t first[TOY_FACTORY_LEAF_FAMILY_MAX_STATE_BYTES];
	uint8_t second[TOY_FACTORY_LEAF_FAMILY_MAX_STATE_BYTES];
	size_t first_size, second_size;
	assert(research_session_encode(a, first, sizeof(first), &first_size) == 0);
	assert(research_session_encode(b, second, sizeof(second), &second_size) == 0);
	assert(first_size == second_size);
	assert(memcmp(first, second, first_size) == 0);
	FILE *const a_file = tmpfile();
	FILE *const b_file = tmpfile();
	assert(a_file != NULL && b_file != NULL);
	assert(research_session_write_json(a, a_file, NULL) == 0);
	assert(research_session_write_json(b, b_file, NULL) == 0);
	rewind(a_file);
	rewind(b_file);
	int c;
	do {
		c = fgetc(a_file);
		assert(c == fgetc(b_file));
	} while (c != EOF);
	assert(ferror(a_file) == 0 && ferror(b_file) == 0);
	assert(fclose(a_file) == 0 && fclose(b_file) == 0);
}

static void verify_family(struct research_session *session)
{
	const struct picosystem_garden_world *const world =
		&observed.candidate.base.growth.base.world;
	struct research_family_view view;
	struct research_status status;
	assert(research_session_family_view(session, &view) == 0);
	assert(research_session_status(session, &status) == 0);
	assert(view.tick == world->logic_tick_count && view.tick == status.tick);
	assert(view.living == status.living && view.seed_count == status.pending);
	uint16_t next = 0U;
	uint8_t bases = 0U;
	for (uint16_t i = 0U; i < world->node_count; ++i) {
		const struct picosystem_garden_node *const node = &world->nodes[i];
		const struct picosystem_garden_plant *const plant =
			&world->plants[node->plant_index];
		if ((observed.owners.root[plant->lineage_id] !=
		     observed.owners.candidate_founder) ||
		    ((plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) != 0U)) {
			continue;
		}
		assert(next < view.segment_count);
		const struct research_family_segment *const segment = &view.segments[next++];
		assert(segment->lineage == plant->lineage_id);
		assert(segment->base == (node->parent_index == PICOSYSTEM_GARDEN_NODE_NONE));
		if (segment->base) {
			assert(segment->start_x == node->x && segment->end_x == node->x);
			assert(segment->start_y == node->y && segment->end_y == node->y);
			++bases;
		} else {
			const struct picosystem_garden_node *const parent =
				&world->nodes[node->parent_index];
			assert(segment->start_x == parent->x && segment->start_y == parent->y);
			assert(segment->end_x == parent->x + ((int)node->x - parent->x) *
								     node->growth_progress / 255);
			assert(segment->end_y == parent->y + ((int)node->y - parent->y) *
								     node->growth_progress / 255);
		}
	}
	assert(next == view.segment_count && bases == view.living);
	next = 0U;
	for (uint8_t i = 0U; i < world->seed_count; ++i) {
		const struct picosystem_garden_seed *const seed = &world->seeds[i];
		if (observed.owners.root[seed->parent_lineage_id] !=
		    observed.owners.candidate_founder) {
			continue;
		}
		assert(next < view.seed_count);
		const struct research_family_seed *const marker = &view.seeds[next++];
		assert(marker->parent == seed->parent_lineage_id);
		assert(marker->x == 12 + 8 * seed->column + seed->visual_offset);
		assert(marker->y == 146U);
	}
	assert(next == view.seed_count);
}

static void family_turnover(void)
{
	const struct research_options options = {
		.seed = UINT32_C(0x58d7d6ca), .model = 1U, .layout = 1U, .founder = 4U};
	struct research_session *session = NULL;
	assert(research_session_open(&options, &session) == 0);
	bool descendant = false, dead = false, reused = false, posthumous = false;
	bool founder_dead = false;
	const unsigned int before = allocations;
	for (unsigned int day = 0U; day < 64U; ++day) {
		assert(research_session_step(session, RESEARCH_DAY_TICKS) == 0);
		verify_family(session);
		const struct picosystem_garden_world *const world =
			&observed.candidate.base.growth.base.world;
		for (uint8_t i = 0U; i < world->plant_count; ++i) {
			const struct picosystem_garden_plant *const plant = &world->plants[i];
			if ((plant->lineage_id == options.founder) &&
			    ((plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) != 0U)) {
				founder_dead = true;
			}
			if (observed.owners.root[plant->lineage_id] == options.founder) {
				descendant |= plant->parent_lineage_id != 0U;
				dead |= (plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) != 0U;
				reused |= plant->lineage_id != (uint32_t)i + 1U;
			}
		}
		for (uint8_t i = 0U; i < world->seed_count; ++i) {
			posthumous |= founder_dead &&
				      world->seeds[i].parent_lineage_id == options.founder;
		}
	}
	assert(allocations == before);
	assert(descendant && dead && reused && posthumous);
	research_session_close(session);
}

/* A custom copy of a named model replays identically and accepts any seed. */
static void custom_model(void)
{
	struct research_options named = {.seed = UINT32_C(0x58d7d6ca),
					 .scope = RESEARCH_SCOPE_POPULATION};
	struct research_options custom = named;
	custom.model = RESEARCH_MODEL_CUSTOM;
	struct research_session *a = NULL, *b = NULL;
	assert(research_session_open(&custom, &b) == -EINVAL && b == NULL);
	memcpy(custom.custom_model, research_model_bytes[0], sizeof(custom.custom_model));
	custom.custom_model[12] ^= 1U;
	assert(research_session_open(&custom, &b) == -EBADMSG && b == NULL);
	custom.custom_model[12] ^= 1U;
	assert(strcmp(research_model_name(RESEARCH_MODEL_CUSTOM), "custom") == 0);
	assert(research_model_name(RESEARCH_MODEL_CUSTOM + 1U) == NULL);

	assert(research_session_open(&named, &a) == 0);
	assert(research_session_open(&custom, &b) == 0);
	assert(research_session_shadow_start(b, 1U, 208U, 224U) == -EINVAL);
	assert(research_session_shadow_start(a, 1U, 208U, 224U) == 0);
	research_session_close(a);
	assert(research_session_open(&named, &a) == 0);
	assert(research_session_step(a, RESEARCH_DAY_TICKS) == 0);
	assert(research_session_step(b, RESEARCH_DAY_TICKS) == 0);
	equal(a, b);
	assert(research_session_reset(&b) == 0);
	assert(research_session_step(b, RESEARCH_DAY_TICKS) == 0);
	equal(a, b);
	research_session_close(a);
	research_session_close(b);

	named.seed = custom.seed = 123U;
	assert(research_session_open(&named, &a) == -EINVAL);
	assert(research_session_open(&custom, &b) == 0);
	assert(research_session_step(b, RESEARCH_DAY_TICKS) == 0);
	research_session_close(b);
}

int main(void)
{
	struct research_options options = {.seed = UINT32_C(0x58d7d6ca), .founder = 1U};
	struct research_session *a = NULL, *b = NULL;
	assert(research_session_open(&options, &a) == 0);
	assert(research_session_open(&options, &b) == 0);
	struct research_status status;
	assert(research_session_status(a, &status) == 0);
	assert(status.tick == 0U && status.living == 1U && status.pending == 0U);
	equal(a, b);

	struct research_session *saved = a;
	options.founder = 0U;
	assert(research_session_open(&options, &a) == -EINVAL && a == saved);
	options.founder = 4U;
	assert(research_session_open(&options, &a) == -EINVAL && a == saved);
	options.founder = 1U;
	options.model = RESEARCH_MODEL_CUSTOM; /* All-zero bytes are not a model file. */
	assert(research_session_open(&options, &a) == -EINVAL && a == saved);
	options.model = RESEARCH_MODEL_CUSTOM + 1U;
	assert(research_session_open(&options, &a) == -EINVAL && a == saved);
	options.model = 0U;
	options.seed = 123U;
	assert(research_session_open(&options, &a) == -EINVAL && a == saved);
	options.seed = UINT32_C(0x58d7d6ca);
	fail_allocation = true;
	assert(research_session_reset(&a) == -ENOMEM && a == saved);
	fail_allocation = false;
	fail_owned_allocation = true;
	assert(research_session_reset(&a) == -ENOMEM && a == saved);
	fail_owned_allocation = false;
	assert(research_session_step(a, UINT32_MAX) == -ERANGE);
	assert(research_session_step(a, RESEARCH_STOP_TICK + 1U) == -ERANGE);
	assert(research_session_step(a, 0U) == 0);
	equal(a, b);

	uint8_t pixels[RESEARCH_FRAME_BYTES];
	uint32_t crc = 123U;
	const unsigned int prior_allocations = allocations;
	for (uint32_t i = 0U; i < 300U; ++i) {
		assert(research_session_step(a, 1U) == 0);
		verify_family(a);
		assert(research_session_render(a, pixels, sizeof(pixels), &crc) == 0);
	}
	assert(allocations == prior_allocations);
	assert(research_session_status(b, &status) == 0 && status.tick == 0U);
	assert(research_session_step(b, 300U) == 0);
	equal(a, b);
	const uint32_t expected_crc = crc;
	assert(research_session_render(b, pixels, sizeof(pixels), &crc) == 0 &&
	       crc == expected_crc);
	assert(research_session_render(b, pixels, 0U, &crc) == -EINVAL && crc == expected_crc);
	equal(a, b);
	assert(research_session_reset(&a) == 0);
	assert(research_session_step(a, 300U) == 0);
	equal(a, b);

	fail_audit = true;
	assert(research_session_step(a, 15U) == -ENOSPC);
	fail_audit = false;
	assert(research_session_step(a, 0U) == -ENOSPC);
	assert(research_session_render(a, pixels, sizeof(pixels), &crc) == -ENOSPC);
	assert(research_session_status(a, &status) == -ENOSPC);
	struct research_family_view view;
	memset(&view, 0xa5, sizeof(view));
	const struct research_family_view untouched = view;
	assert(research_session_family_view(a, &view) == -ENOSPC);
	assert(memcmp(&view, &untouched, sizeof(view)) == 0);
	FILE *const output = tmpfile();
	assert(output != NULL);
	assert(research_session_write_json(a, output, NULL) == -ENOSPC);
	assert(ftell(output) == 0L);
	assert(fclose(output) == 0);
	assert(research_session_reset(&a) == 0);
	assert(research_session_step(a, 300U) == 0);
	equal(a, b);
	research_session_close(a);
	research_session_close(b);
	research_session_close(NULL);
	assert(research_session_open(NULL, NULL) == -EINVAL);
	assert(research_session_step(NULL, 1U) == -EINVAL);
	assert(research_session_reset(NULL) == -EINVAL);
	assert(research_session_family_view(NULL, &view) == -EINVAL);
	assert(memcmp(&view, &untouched, sizeof(view)) == 0);
	family_turnover();
	custom_model();
	puts("Research session: ownership, stepping, rendering, reset, custom models and latched "
	     "failures pass.");
	return 0;
}
