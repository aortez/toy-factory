/*
 * Copyright (c) 2026 Toy Factory contributors
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/linker/sections.h>

#if defined(CONFIG_TOY_FACTORY_CORE1_RUNTIME)
SECTION_DATA_PROLOGUE(.core1_ram, (NOLOAD), SUBALIGN(8))
{
	__core1_ram_start = .;
	KEEP(*(.core1_ram))
	__core1_ram_end = .;
} GROUP_LINK_IN(CORE1_RAM)

ASSERT((__core1_ram_end - __core1_ram_start) <= LENGTH(CORE1_RAM),
       "core 1 storage exceeds the reserved SRAM banks")
#endif
