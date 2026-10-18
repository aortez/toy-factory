/* SPDX-License-Identifier: Apache-2.0 */
#include "research_session.h"
#include "garden_leaf_family.h"
#include "garden_landing_ledger.h"

#include <assert.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>

static bool fail_allocation;
static bool fail_owned_allocation;
static bool fail_audit;
static unsigned int allocations;

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
	options.model = 3U;
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
	puts("Research session: ownership, stepping, rendering, reset and latched failures pass.");
	return 0;
}
