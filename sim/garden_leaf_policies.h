/* SPDX-License-Identifier: Apache-2.0 */
#ifndef TOY_FACTORY_GARDEN_LEAF_POLICIES_H_
#define TOY_FACTORY_GARDEN_LEAF_POLICIES_H_

#include "garden_leaf.h"

/* NULL for an unknown name; returned immutable policies have process lifetime. */
const struct picosystem_garden_leaf_policy *toy_factory_garden_leaf_policy(const char *name);
#endif
