/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef TOY_FACTORY_GARDEN_POLICY_PROBE_H_
#define TOY_FACTORY_GARDEN_POLICY_PROBE_H_

#include "garden_agent.h"

#define TOY_FACTORY_GARDEN_NIGHT_PROBE_NAME   "no-night-growth-v1"
#define TOY_FACTORY_GARDEN_NIGHT_PROBE_POLICY "neural-no-night-growth"

/* Host-only counterfactual: veto paid growth during sun phases 128..255.
 * Priority, tip identity, arbitration, and proposed recurrent memory are preserved.
 * Automatic maintenance, maturation, and reproduction remain world mechanics.
 * The caller owns base; it must remain immutable and outlive the returned policy.
 * Invalid arguments return -EINVAL and leave policy untouched.
 */
int toy_factory_garden_no_night_growth_init(const struct picosystem_garden_agent_policy *base,
					    struct picosystem_garden_agent_policy *policy);

#endif /* TOY_FACTORY_GARDEN_POLICY_PROBE_H_ */
