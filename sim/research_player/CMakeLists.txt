# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.20)
project(toy_factory_research_player C)
enable_testing()
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)
set(TOY_FACTORY_RESEARCH_RUNTIME "" CACHE PATH "Verified archive preparation")
if(NOT EXISTS "${TOY_FACTORY_RESEARCH_RUNTIME}/manifest.json")
    message(FATAL_ERROR "Run sim/research_player/prepare.py first")
endif()
find_package(Python3 REQUIRED COMPONENTS Interpreter)
execute_process(COMMAND "${Python3_EXECUTABLE}" -B "${CMAKE_CURRENT_LIST_DIR}/prepare.py"
    --check --out "${TOY_FACTORY_RESEARCH_RUNTIME}" RESULT_VARIABLE verified)
if(NOT verified EQUAL 0)
    message(FATAL_ERROR "Research runtime verification failed")
endif()
set(TOY_FACTORY_LEAF_CORE "${TOY_FACTORY_RESEARCH_RUNTIME}/source" CACHE PATH "Frozen core" FORCE)
add_subdirectory("${TOY_FACTORY_RESEARCH_RUNTIME}/modules/leaf_replay" frozen-replay EXCLUDE_FROM_ALL)
# Add observation and an explicit placement route in build-directory copies.
# Verification above authenticates all frozen inputs; evidence pins the adapters.
set(purchase_runner "${CMAKE_CURRENT_BINARY_DIR}/research_purchase_runner.c")
execute_process(COMMAND "${Python3_EXECUTABLE}" -B
    "${CMAKE_CURRENT_LIST_DIR}/stage_fallback.py"
    "${TOY_FACTORY_RESEARCH_RUNTIME}" "${CMAKE_CURRENT_BINARY_DIR}"
    RESULT_VARIABLE staged)
if(NOT staged EQUAL 0)
    message(FATAL_ERROR "Research placement adapter failed")
endif()
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS stage_purchase_observer.py stage_fallback.py)
set(canopy_world "${CMAKE_CURRENT_BINARY_DIR}/research_canopy_world.c")
execute_process(COMMAND "${Python3_EXECUTABLE}" -B
    "${CMAKE_CURRENT_LIST_DIR}/stage_canopy.py"
    "${TOY_FACTORY_RESEARCH_RUNTIME}/source/src/garden_world.c" "${canopy_world}"
    RESULT_VARIABLE canopy_staged)
if(NOT canopy_staged EQUAL 0)
    message(FATAL_ERROR "Research canopy adapter failed")
endif()
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS stage_canopy.py)
get_target_property(core_sources maintenance_core SOURCES)
set(world_originals "${core_sources}")
list(FILTER world_originals INCLUDE REGEX "/garden_world\\.c$")
list(LENGTH world_originals world_original_count)
if(NOT world_original_count EQUAL 1)
    message(FATAL_ERROR "Expected exactly one frozen garden world")
endif()
list(FILTER core_sources EXCLUDE REGEX "/garden_world\\.c$")
set_property(TARGET maintenance_core PROPERTY SOURCES "${core_sources}")
target_sources(maintenance_core PRIVATE "${canopy_world}")
target_include_directories(maintenance_core PRIVATE "${CMAKE_CURRENT_LIST_DIR}")
set_source_files_properties("${canopy_world}" PROPERTIES COMPILE_OPTIONS "-Wconversion;-Wsign-conversion")
get_target_property(runner_sources maintenance_runner SOURCES)
set(purchase_originals "${runner_sources}")
list(FILTER purchase_originals INCLUDE REGEX "/garden_landing_run\\.c$")
list(LENGTH purchase_originals purchase_original_count)
if(NOT purchase_original_count EQUAL 1)
    message(FATAL_ERROR "Expected exactly one frozen landing runner")
endif()
list(FILTER runner_sources EXCLUDE REGEX "/garden_landing_run\\.c$")
set_property(TARGET maintenance_runner PROPERTY SOURCES "${runner_sources}")
target_sources(maintenance_runner PRIVATE "${purchase_runner}" research_purchase.c research_fallback.c)
target_include_directories(maintenance_runner PRIVATE "${CMAKE_CURRENT_LIST_DIR}"
    "${TOY_FACTORY_RESEARCH_RUNTIME}/modules/leaf_neural")
get_target_property(replay_sources leaf_replay SOURCES)
if(NOT replay_sources STREQUAL "garden_leaf_replay.c")
    message(FATAL_ERROR "Expected the frozen replay wrapper")
endif()
set_property(TARGET leaf_replay PROPERTY SOURCES "${CMAKE_CURRENT_BINARY_DIR}/research_fallback_replay.c")
target_include_directories(leaf_replay PRIVATE "${CMAKE_CURRENT_LIST_DIR}")
add_library(research_session STATIC research_session.c research_trace.c research_shadow.c research_gate.c research_reproduction.c research_budget.c research_foliage.c
    "${TOY_FACTORY_RESEARCH_RUNTIME}/source/maintenance-fixture/garden_maintenance_step.c"
    "${TOY_FACTORY_RESEARCH_RUNTIME}/source/sim/garden_resource_step.c")
target_link_libraries(research_session PUBLIC leaf_owned)
target_include_directories(research_session PUBLIC "${CMAKE_CURRENT_LIST_DIR}"
    PRIVATE "${TOY_FACTORY_RESEARCH_RUNTIME}/generated")
add_executable(research-replay research_cli.c)
add_executable(research-session-test research_session_test.c)
add_executable(research-population-test research_population_test.c research_gate_test.c research_purchase_test.c research_fallback_test.c research_reproduction_test.c research_budget_test.c research_foliage_test.c)
target_link_libraries(research-replay PRIVATE research_session)
target_link_libraries(research-session-test PRIVATE research_session)
target_link_libraries(research-population-test PRIVATE research_session)
target_link_options(research-population-test PRIVATE -Wl,--wrap=malloc -Wl,--wrap=calloc
	-Wl,--wrap=research_canopy_project
    -Wl,--wrap=research_reproduction_record
    -Wl,--wrap=research_fallback_step_owned
    -Wl,--wrap=toy_factory_garden_placement_decide
    -Wl,--wrap=research_shadow_decide
    -Wl,--wrap=toy_factory_maintenance_step_read
    -Wl,--wrap=toy_factory_garden_landing_ledger_step
    -Wl,--wrap=toy_factory_leaf_replay_step_owned)
target_link_options(research-session-test PRIVATE -Wl,--wrap=malloc -Wl,--wrap=calloc
    -Wl,--wrap=toy_factory_garden_landing_ledger_step
    -Wl,--wrap=toy_factory_leaf_owned_snapshot)
foreach(target research_session research-replay research-session-test research-population-test)
    target_compile_options(${target} PRIVATE -Wall -Wextra -Werror -Wconversion -Wsign-conversion
        -UNDEBUG -fsanitize=undefined -fno-sanitize-recover=undefined)
    target_link_options(${target} PRIVATE -fsanitize=undefined -fno-sanitize-recover=undefined)
endforeach()
add_test(NAME research-session COMMAND research-session-test)
add_test(NAME research-population COMMAND research-population-test)
add_test(NAME research-population-cli COMMAND "${Python3_EXECUTABLE}" -B
    "${CMAKE_CURRENT_LIST_DIR}/test_population.py" $<TARGET_FILE:research-replay>)
set_tests_properties(research-population research-population-cli PROPERTIES TIMEOUT 90)
add_test(NAME research-population-analysis COMMAND "${Python3_EXECUTABLE}" -B -m unittest
    discover -s "${CMAKE_CURRENT_LIST_DIR}/../experiments/leaf_population" -p "test_*.py")
# Archive verification now takes about a minute; allow scheduling headroom.
set_tests_properties(research-population-analysis PROPERTIES TIMEOUT 120)

option(TOY_FACTORY_RESEARCH_VIEWER "Build the separate SDL research viewer" OFF)
if(TOY_FACTORY_RESEARCH_VIEWER)
    include(sdl.cmake)
    file(READ "${TOY_FACTORY_RESEARCH_RUNTIME}/manifest.json" manifest)
    string(JSON archive_sha GET "${manifest}" archive_sha256)
    add_executable(research-player player.c)
    target_compile_definitions(research-player PRIVATE RESEARCH_ARCHIVE_SHA="${archive_sha}")
    target_compile_options(research-player PRIVATE -Wall -Wextra -Werror -Wconversion -Wsign-conversion
        -UNDEBUG -fsanitize=undefined -fno-sanitize-recover=undefined)
    target_link_libraries(research-player PRIVATE research_session SDL3::SDL3)
    add_test(NAME research-player-smoke COMMAND research-player --paused --frames 1)
    add_test(NAME research-player-controls COMMAND research-player --test-controls)
    add_test(NAME research-player-parity COMMAND "${Python3_EXECUTABLE}" -B
        "${CMAKE_CURRENT_LIST_DIR}/test_player.py" $<TARGET_FILE:research-player> $<TARGET_FILE:research-replay>)
    set_tests_properties(research-player-parity PROPERTIES TIMEOUT 60)
    set_tests_properties(research-player-smoke research-player-controls PROPERTIES
        ENVIRONMENT "SDL_VIDEODRIVER=dummy" TIMEOUT 20)
endif()
