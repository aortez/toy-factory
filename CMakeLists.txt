# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20.0)

list(APPEND BOARD_ROOT ${CMAKE_CURRENT_SOURCE_DIR})
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(toy_factory)

target_sources(app PRIVATE
	src/battery.c
	src/diagnostic_shell.c
	src/display_sync.c
	src/fixed_rate_scheduler.c
	src/game_demo.c
	src/graphics.c
	src/main.c
	src/piezo.c
	src/power_status.c
)
