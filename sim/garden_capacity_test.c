/* SPDX-License-Identifier: Apache-2.0 */

#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include "game_snapshot.h"
#include "graphics_raster.h"

static void mark_for_reclamation(struct picosystem_garden_world *world, uint8_t plant_index)
{
	struct picosystem_garden_plant *const plant = &world->plants[plant_index];
	plant->flags = PICOSYSTEM_GARDEN_PLANT_DEAD;
	plant->stress = PICOSYSTEM_GARDEN_STRESS_DEATH_THRESHOLD;
	plant->stored_energy = 0U;
	plant->stored_water = 0U;
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	plant->leaf_energy_remainder = 0U;
#endif
	for (uint16_t index = 0U; index < world->node_count; ++index) {
		if (world->nodes[index].plant_index == plant_index) {
			world->nodes[index].growth_progress = 1U;
			world->nodes[index].flags = 0U;
#if defined(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
			world->leaf_condition[index] = 0U;
#endif
		}
	}
}

static void step_ecology(struct picosystem_garden_world *world)
{
	for (uint8_t tick = 0U; tick < PICOSYSTEM_GARDEN_ECOLOGY_TICK_DIVISOR; ++tick) {
		assert(picosystem_garden_world_step(world) == 0);
	}
}

static void seed_capacity(void)
{
	struct picosystem_game_world game = {.scene_id = PICOSYSTEM_GAME_SCENE_GARDEN};
	struct picosystem_garden_world *const world = &game.garden;
	assert(picosystem_garden_world_reset(world, 123U) == 0);
	world->auto_gardener_enabled = false;
	assert(picosystem_garden_world_plant_seed(world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 0U) ==
	       0);
	world->seed_count = PICOSYSTEM_GARDEN_MAX_SEEDS;
	for (uint8_t i = 0U; i < world->seed_count; ++i) {
		world->seeds[i] = (struct picosystem_garden_seed){
			.parent_lineage_id = 1U,
			.generation = 1U,
			.column = i,
			.age_ecology_ticks = PICOSYSTEM_GARDEN_SEED_LIFETIME_TICKS - 1U,
		};
	}
	const uint32_t hash = picosystem_garden_world_hash(world);
	assert(hash != 0U);
	struct picosystem_scene_snapshot snapshot;
	assert(picosystem_game_snapshot_build(&game, 1U, 0U, 0, &snapshot) == 0);
	assert(snapshot.payload.garden.seed_count == PICOSYSTEM_GARDEN_MAX_SEEDS);
	assert(picosystem_scene_render_full(&snapshot) == 0);
	const uint32_t crc = picosystem_graphics_raster_crc32();
	world->seeds[PICOSYSTEM_GARDEN_MAX_SEEDS - 1U].column = 27U;
	assert(picosystem_garden_world_hash(world) != hash);
	assert(picosystem_game_snapshot_build(&game, 1U, 0U, 0, &snapshot) == 0);
	assert(picosystem_scene_render_full(&snapshot) == 0);
	assert(picosystem_graphics_raster_crc32() != crc);
	world->seed_count = PICOSYSTEM_GARDEN_MAX_SEEDS + 1U;
	const struct picosystem_garden_world invalid = *world;
	assert(picosystem_game_snapshot_build(&game, 1U, 0U, 0, &snapshot) == -ENOSPC);
	assert(picosystem_garden_world_step(world) == -EINVAL);
	assert(memcmp(world, &invalid, sizeof(invalid)) == 0);
	world->seed_count = PICOSYSTEM_GARDEN_MAX_SEEDS;
	step_ecology(world);
	assert(world->seed_count == 0U);
	assert(world->seed_expiration_count == PICOSYSTEM_GARDEN_MAX_SEEDS);
	printf("PASS seed_capacity=%u world=%zu garden_snapshot=%zu seed=%zu snapshot_seed=%zu\n",
	       PICOSYSTEM_GARDEN_MAX_SEEDS, sizeof(*world), sizeof(snapshot.payload.garden),
	       sizeof(world->seeds[0]), sizeof(snapshot.payload.garden.seeds[0]));
}

int main(void)
{
	seed_capacity();
	struct picosystem_garden_world world;
	assert(picosystem_garden_world_reset(&world, 123U) == 0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 0U) ==
	       0);
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 20U) ==
	       0);
	/* Controlled topology at the exact boundary. The final node has a long edge
	 * to its base, while the retained chain exercises large remap destinations.
	 */
	for (uint16_t index = world.node_count; index < PICOSYSTEM_GARDEN_MAX_NODES; ++index) {
		const uint16_t parent =
			(uint16_t)((index == PICOSYSTEM_GARDEN_MAX_NODES - 1U) ? 4U : index - 1U);
		world.nodes[index] = (struct picosystem_garden_node){
			.parent_index = parent,
			.plant_index = 1U,
			.x = 200U,
			.y = 70U,
			.depth = 1U,
			.growth_progress = UINT8_MAX,
			.kind = PICOSYSTEM_GARDEN_NODE_STEM,
		};
		++world.nodes[parent].child_count;
	}
	world.node_count = PICOSYSTEM_GARDEN_MAX_NODES;
	world.plants[1].node_count = PICOSYSTEM_GARDEN_MAX_NODES - 4U;
	world.plants[1].last_shoot_tip_index = PICOSYSTEM_GARDEN_MAX_NODES - 1U;
	world.plants[1].growth_cooldown = UINT8_MAX;
	world.plants[1].stored_energy = 256U;
	world.plants[1].stored_water = 512U;
	assert(picosystem_garden_world_hash(&world) != 0U);
	struct picosystem_garden_world before = world;
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 10U) ==
	       -ENOSPC);
	assert(memcmp(&world, &before, sizeof(world)) == 0);

	struct picosystem_game_world game = {.garden = world,
					     .scene_id = PICOSYSTEM_GAME_SCENE_GARDEN};
	struct picosystem_scene_snapshot snapshot;
	assert(picosystem_game_snapshot_build(&game, 1U, 0U, 0, &snapshot) == 0);
	const uint16_t last = PICOSYSTEM_GARDEN_MAX_NODES - 1U;
	assert(snapshot.payload.garden.node_count == PICOSYSTEM_GARDEN_MAX_NODES);
	assert(snapshot.payload.garden.nodes[last].parent_distance == last - 4U);
	assert(picosystem_scene_render_full(&snapshot) == 0);
	const uint32_t first_crc = picosystem_graphics_raster_crc32();
	snapshot.payload.garden.nodes[last].x = 170U;
	assert(picosystem_scene_render_full(&snapshot) == 0);
	assert(picosystem_graphics_raster_crc32() != first_crc);
	assert(memcmp(&world, &before, sizeof(world)) == 0);
	game.garden.node_count = PICOSYSTEM_GARDEN_MAX_NODES + 1U;
	assert(picosystem_game_snapshot_build(&game, 1U, 0U, 0, &snapshot) == -ENOSPC);
	before = game.garden;
	assert(picosystem_garden_world_step(&game.garden) == -EINVAL);
	assert(memcmp(&game.garden, &before, sizeof(before)) == 0);

	mark_for_reclamation(&world, 0U);
	before = world;
	step_ecology(&world);
	assert(world.node_count == PICOSYSTEM_GARDEN_MAX_NODES - 4U);
	assert(world.plant_count == 1U && world.reclaimed_node_count == 4U);
	assert(world.plants[0].base_node_index == 0U);
	assert(world.plants[0].last_shoot_tip_index == PICOSYSTEM_GARDEN_MAX_NODES - 5U);
	for (uint16_t index = 0U; index < world.node_count; ++index) {
		const struct picosystem_garden_node *const old = &before.nodes[index + 4U];
		assert(world.nodes[index].plant_index == 0U);
		assert(world.nodes[index].parent_index ==
		       (old->parent_index == PICOSYSTEM_GARDEN_NODE_NONE
				? PICOSYSTEM_GARDEN_NODE_NONE
				: old->parent_index - 4U));
	}
	/* Exactly four slots remain. The new seedling's base/tips also cross 255 in
	 * the large build, then must remap back to zero when the big plant is removed.
	 */
	assert(picosystem_garden_world_plant_seed(&world, PICOSYSTEM_GARDEN_SPECIES_FLOWER, 0U) ==
	       0);
	assert(world.node_count == PICOSYSTEM_GARDEN_MAX_NODES);
	assert(world.plants[1].base_node_index == PICOSYSTEM_GARDEN_MAX_NODES - 4U);
	mark_for_reclamation(&world, 0U);
	world.plants[1].growth_cooldown = UINT8_MAX;
	step_ecology(&world);
	assert(world.node_count == 4U && world.plant_count == 1U);
	assert(world.plants[0].base_node_index == 0U);
	assert(world.reclaimed_node_count == PICOSYSTEM_GARDEN_MAX_NODES);
	assert(picosystem_garden_world_hash(&world) != 0U);
	printf("PASS capacity=%u world=%zu node=%zu snapshot=%zu snapshot_node=%zu\n",
	       PICOSYSTEM_GARDEN_MAX_NODES, sizeof(world), sizeof(world.nodes[0]), sizeof(snapshot),
	       sizeof(snapshot.payload.garden.nodes[0]));
	return 0;
}
