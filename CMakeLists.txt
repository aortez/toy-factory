# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20.0)

list(APPEND BOARD_ROOT ${CMAKE_CURRENT_SOURCE_DIR})
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(toy_factory)

if(CONFIG_TOY_FACTORY_CORE1_RUNTIME)
	zephyr_linker_sources(SECTIONS src/core1_ram.ld)
endif()

target_sources(app PRIVATE
	src/battery.c
	src/dense_scene.c
	src/diagnostic_shell.c
	src/display_profile.c
	src/display_sync.c
	src/fixed_rate_scheduler.c
	src/game_control.c
	src/game_demo.c
	src/game_world.c
	src/graphics.c
	src/main.c
	src/physics_chain_fixture.c
	src/physics_world.c
	src/physics_profile.c
	src/piezo.c
	src/power_status.c
	src/scene_renderer.c
)

target_sources_ifdef(CONFIG_TOY_FACTORY_CORE1_RUNTIME app PRIVATE src/core1_runtime.c)

if(CONFIG_SOC_SERIES_RP2040)
	# Zephyr otherwise uses software AEABI division. The pinned Pico SDK wrappers
	# preserve compiler semantics and save/restore each core's divider across IRQs.
	set(pico_divider_dir
		${ZEPHYR_HAL_RPI_PICO_MODULE_DIR}/src/rp2_common/pico_divider)
	target_sources(app PRIVATE ${pico_divider_dir}/divider_hardware.S)
	target_include_directories(app PRIVATE
		${ZEPHYR_HAL_RPI_PICO_MODULE_DIR}/src/rp2_common/hardware_divider/include)
	foreach(divider_symbol
		__aeabi_idiv
		__aeabi_idivmod
		__aeabi_ldivmod
		__aeabi_uidiv
		__aeabi_uidivmod
		__aeabi_uldivmod)
		target_link_options(app PUBLIC "-Wl,--wrap=${divider_symbol}")
	endforeach()
endif()
