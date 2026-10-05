/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_LANDING_PLACEMENT_H_
#define TOY_FACTORY_GARDEN_LANDING_PLACEMENT_H_

#include "garden_agent.h"
#include <stdio.h>

#if defined(__ZEPHYR__)
#error "Seed placement is an unqualified host-only experiment"
#endif

#define TOY_FACTORY_GARDEN_PLACEMENT_VERSION 1U

struct toy_factory_garden_placement_config {
	uint8_t version;
	uint8_t enabled;
	/* Separate tagged identity; zero preserves every old placement run. */
	uint32_t replace_after;
};

struct toy_factory_garden_placement_receipt {
	struct picosystem_garden_seed_placement observation;
	uint8_t selected;
};

struct toy_factory_garden_placement_audit {
	bool ecology_step;
	uint8_t count;
	struct toy_factory_garden_placement_receipt purchases[PICOSYSTEM_GARDEN_MAX_SEEDS];
};

struct toy_factory_garden_placement_context {
	const struct toy_factory_garden_placement_config *config;
	/* Optional borrowed per-step output; discard on callback/step failure. */
	struct toy_factory_garden_placement_audit *audit;
};

/* Keep an unblocked original choice. Otherwise select a clear entry using
 * (random / active_choices) % clear_count, retaining aliases. All blocked falls back to
 * the original. Pure, bounded, no mutation/RNG; output unchanged on error.
 */
int toy_factory_garden_placement_choose(const struct picosystem_garden_seed_placement *observation,
					uint8_t enabled, uint8_t *choice);
int toy_factory_garden_placement_decide(const struct picosystem_garden_seed_placement *observation,
					uint8_t *choice, const void *context);
int toy_factory_garden_placement_print(FILE *stream, uint32_t tick,
				       const struct toy_factory_garden_placement_audit *audit);

#endif
