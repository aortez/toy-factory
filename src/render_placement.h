/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PICOSYSTEM_RENDER_PLACEMENT_H_
#define PICOSYSTEM_RENDER_PLACEMENT_H_

#if defined(CONFIG_TOY_FACTORY_CORE1_FULL_FRAME_RENDERER)
#include <zephyr/toolchain.h>
#define PICOSYSTEM_RENDER_RAMFUNC __ramfunc
#else
#define PICOSYSTEM_RENDER_RAMFUNC
#endif

#endif /* PICOSYSTEM_RENDER_PLACEMENT_H_ */
