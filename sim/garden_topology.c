/* SPDX-License-Identifier: Apache-2.0 */
#include <errno.h>
#include <inttypes.h>

#include "garden_topology.h"

static bool owned_reference(const struct picosystem_garden_world *world, uint16_t node,
			    uint8_t owner)
{
	return (node == PICOSYSTEM_GARDEN_NODE_NONE) ||
	       ((node < world->node_count) && (world->nodes[node].plant_index == owner));
}

static bool topology_is_valid(const struct picosystem_garden_world *world)
{
	if ((world == NULL) || (world->node_count > PICOSYSTEM_GARDEN_MAX_NODES) ||
	    (world->plant_count > PICOSYSTEM_GARDEN_MAX_PLANTS)) {
		return false;
	}
	uint16_t children[PICOSYSTEM_GARDEN_MAX_NODES] = {0};
	uint16_t owned[PICOSYSTEM_GARDEN_MAX_PLANTS] = {0};
	for (uint16_t i = 0U; i < world->node_count; ++i) {
		const struct picosystem_garden_node *node = &world->nodes[i];
		if ((node->plant_index >= world->plant_count) ||
		    (node->kind >= PICOSYSTEM_GARDEN_NODE_KIND_COUNT) ||
		    ((node->flags & (uint8_t)~PICOSYSTEM_GARDEN_NODE_VALID_FLAGS) != 0U)) {
			return false;
		}
		if (node->parent_index != PICOSYSTEM_GARDEN_NODE_NONE) {
			if ((node->parent_index >= i) ||
			    !owned_reference(world, node->parent_index, node->plant_index)) {
				return false;
			}
			++children[node->parent_index];
		} else if (world->plants[node->plant_index].base_node_index != i) {
			return false;
		}
		++owned[node->plant_index];
	}
	for (uint16_t i = 0U; i < world->node_count; ++i) {
		if (children[i] != world->nodes[i].child_count) {
			return false;
		}
	}
	for (uint8_t i = 0U; i < world->plant_count; ++i) {
		const struct picosystem_garden_plant *plant = &world->plants[i];
		if ((plant->node_count == 0U) || (plant->node_count != owned[i]) ||
		    (plant->base_node_index >= world->node_count) ||
		    !owned_reference(world, plant->base_node_index, i) ||
		    (world->nodes[plant->base_node_index].parent_index !=
		     PICOSYSTEM_GARDEN_NODE_NONE) ||
		    !owned_reference(world, plant->last_shoot_tip_index, i) ||
		    !owned_reference(world, plant->last_root_tip_index, i)) {
			return false;
		}
	}
	return true;
}

int toy_factory_garden_topology_print(const struct picosystem_garden_world *world, FILE *output)
{
	if ((output == NULL) || !topology_is_valid(world)) {
		return -EINVAL;
	}
	if (fprintf(output,
		    "{\"type\":\"topology\",\"schema_version\":1,\"tick\":%" PRIu32
		    ",\"hash\":\"%08" PRIx32 "\",\"node_capacity\":%u,\"plants\":[",
		    world->logic_tick_count, picosystem_garden_world_hash(world),
		    PICOSYSTEM_GARDEN_MAX_NODES) < 0) {
		return -EIO;
	}
	for (uint8_t i = 0U; i < world->plant_count; ++i) {
		const struct picosystem_garden_plant *p = &world->plants[i];
		if (fprintf(output,
			    "%s{\"index\":%u,\"id\":%" PRIu32 ",\"flags\":%u,\"base\":%u,"
			    "\"last_shoot_tip\":%u,\"last_root_tip\":%u}",
			    i == 0U ? "" : ",", i, p->lineage_id, p->flags, p->base_node_index,
			    p->last_shoot_tip_index, p->last_root_tip_index) < 0) {
			return -EIO;
		}
	}
	if (fprintf(output, "],\"nodes\":[") < 0) {
		return -EIO;
	}
	for (uint16_t i = 0U; i < world->node_count; ++i) {
		const struct picosystem_garden_node *n = &world->nodes[i];
		if (fprintf(output,
			    "%s{\"index\":%u,\"owner\":%u,\"parent\":%u,\"x\":%u,\"y\":%u,"
			    "\"kind\":%u,\"flags\":%u,\"progress\":%u,\"depth\":%u,"
			    "\"children\":%u,\"condition\":",
			    i == 0U ? "" : ",", i, n->plant_index, n->parent_index, n->x, n->y,
			    n->kind, n->flags, n->growth_progress, n->depth, n->child_count) < 0) {
			return -EIO;
		}
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
		if (fprintf(output, "%u}", world->leaf_condition[i]) < 0) {
			return -EIO;
		}
#else
		if (fprintf(output, "null}") < 0) {
			return -EIO;
		}
#endif
	}
	return fprintf(output, "]}\n") < 0 ? -EIO : 0;
}
