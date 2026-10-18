/* SPDX-License-Identifier: Apache-2.0 */
#include "garden_capture.h"
#include "game_snapshot.h"
#include "graphics_raster.h"

#include <errno.h>
#include <stdio.h>

int toy_factory_garden_capture(const struct picosystem_garden_world *world, const char *path,
			       uint32_t *framebuffer_crc)
{
	if ((world == NULL) || (path == NULL) || (*path == '\0') || (framebuffer_crc == NULL)) {
		return -EINVAL;
	}
	/* Do not reset via a playable scene or advance its default policy. */
	const struct picosystem_game_world render_world = {
		.garden = *world,
		.logic_tick_count = world->logic_tick_count,
		.scene_id = PICOSYSTEM_GAME_SCENE_GARDEN,
	};
	struct picosystem_scene_snapshot snapshot;
	int err = picosystem_game_snapshot_build(&render_world, 1U, 0U,
						 (int64_t)world->logic_tick_count, &snapshot);
	if (err == 0) {
		err = picosystem_scene_render_full(&snapshot);
	}
	if (err != 0) {
		return err;
	}
	if (picosystem_garden_world_hash(&render_world.garden) !=
	    picosystem_garden_world_hash(world)) {
		return -EFAULT;
	}
	const uint32_t crc = picosystem_graphics_raster_crc32();
	FILE *const stream = fopen(path, "wbx");
	if (stream == NULL) {
		return errno != 0 ? -errno : -EIO;
	}
	const size_t length = picosystem_graphics_raster_byte_count();
	const size_t written = fwrite(picosystem_graphics_raster_bytes(), 1U, length, stream);
	const int closed = fclose(stream);
	if ((written != length) || (closed != 0)) {
		(void)remove(path);
		return -EIO;
	}
	*framebuffer_crc = crc;
	return 0;
}
