/* SPDX-License-Identifier: Apache-2.0 */
#include <errno.h>

#include "garden_focal_policy.h"

#if defined(__ZEPHYR__)
#error "Focal founder routing is a host diagnostic, not a firmware policy"
#endif

const struct picosystem_garden_agent_policy *
toy_factory_garden_focal_policy_select(const struct toy_factory_garden_focal_context *context,
				       uint8_t plant_index)
{
	if ((context == NULL) || (context->world == NULL) ||
	    (context->world->plant_count > PICOSYSTEM_GARDEN_MAX_PLANTS) ||
	    (plant_index >= context->world->plant_count)) {
		return NULL;
	}
	const struct picosystem_garden_plant *const plant = &context->world->plants[plant_index];
	return ((plant->lineage_id == context->founder_id) && (plant->parent_lineage_id == 0U) &&
		(plant->generation == 0U))
		       ? context->focal
		       : context->background;
}

static int decide(const struct picosystem_garden_agent_observation *observation,
		  const struct picosystem_garden_agent_memory *memory,
		  struct picosystem_garden_agent_decision *decision, const void *context)
{
	if (observation == NULL) {
		return -EINVAL;
	}
	const struct picosystem_garden_agent_policy *const selected =
		toy_factory_garden_focal_policy_select(context, observation->plant_index);
	if (selected == NULL) {
		return -EINVAL;
	}
	/* Preserve the selected model's entire decision and private memory proposal.
	 * Only the ordinary world arbitration is allowed to commit that proposal.
	 */
	return picosystem_garden_agent_decide(selected, observation, memory, decision);
}

int toy_factory_garden_focal_policy_init(const struct picosystem_garden_world *world,
					 const struct picosystem_garden_agent_policy *background,
					 const struct picosystem_garden_agent_policy *focal,
					 uint32_t founder_id,
					 struct toy_factory_garden_focal_context *context,
					 struct picosystem_garden_agent_policy *policy)
{
	if ((world == NULL) || (background == NULL) || (focal == NULL) || (context == NULL) ||
	    (policy == NULL) || (policy == background) || (policy == focal) ||
	    (background->decide == NULL) || (focal->decide == NULL) ||
	    (background->decide == decide) || (focal->decide == decide) ||
	    (background->context == context) || (focal->context == context) ||
	    (background->arbitration != PICOSYSTEM_GARDEN_AGENT_ARBITRATION_ALL_TIPS) ||
	    (focal->arbitration != background->arbitration) || (founder_id == 0U) ||
	    (world->logic_tick_count != 0U) ||
	    (world->plant_count > PICOSYSTEM_GARDEN_MAX_PLANTS)) {
		return -EINVAL;
	}
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	if (background->leaf_policy != focal->leaf_policy) {
		return -EINVAL;
	}
#endif
	bool found = false;
	for (uint8_t i = 0U; i < world->plant_count; ++i) {
		const struct picosystem_garden_plant *const plant = &world->plants[i];
		if (plant->lineage_id == founder_id) {
			if (found || (plant->parent_lineage_id != 0U) ||
			    (plant->generation != 0U) ||
			    ((plant->flags & PICOSYSTEM_GARDEN_PLANT_DEAD) != 0U)) {
				return -EINVAL;
			}
			found = true;
		}
	}
	if (!found) {
		return -ENOENT;
	}
	*context = (struct toy_factory_garden_focal_context){
		.world = world, .background = background, .focal = focal, .founder_id = founder_id};
	*policy = *background;
	policy->decide = decide;
	policy->context = context;
	return 0;
}
