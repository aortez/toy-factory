# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20)
project(toy_factory_simulator C)

option(TOY_FACTORY_SIMULATOR_SANITIZERS "Enable host undefined-behavior checks" ON)
option(TOY_FACTORY_SIMULATOR_PLAYER "Build the interactive SDL3 player" OFF)
option(TOY_FACTORY_SIMULATOR_PROFILING "Build host profiling tools" OFF)
option(TOY_FACTORY_GARDEN_WIDE_DISPERSAL "Experimental host-only 3-9 cell seed scattering" OFF)
option(TOY_FACTORY_GARDEN_WATER_HEADROOM "Experimental host-only storage-limited root uptake" OFF)
option(TOY_FACTORY_GARDEN_COMBINED_EXPERIMENT "Explicit opt-in to the combined host ecology trial" OFF)
option(TOY_FACTORY_GARDEN_LARGE_POOL "Experimental host-only 512-node combined ecology control" OFF)
option(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE "Host-only mature leaf wear and paid renewal" OFF)
option(TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE "Host-only bounded bottom-drainage comparison" OFF)
option(TOY_FACTORY_GARDEN_LARGE_SEED_BANK "Host-only 16-seed bank comparison" OFF)
option(TOY_FACTORY_GARDEN_SEED_RESERVE "Host-only sunset-aware seed energy check" OFF)
if(TOY_FACTORY_GARDEN_SEED_RESERVE AND
	(NOT TOY_FACTORY_GARDEN_LEAF_MAINTENANCE OR NOT TOY_FACTORY_GARDEN_LARGE_POOL OR
	 TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE))
	message(FATAL_ERROR "Seed reserve requires the undrained 512-node host maintenance experiment")
endif()
if(TOY_FACTORY_GARDEN_LARGE_SEED_BANK AND
	(NOT TOY_FACTORY_GARDEN_LEAF_MAINTENANCE OR NOT TOY_FACTORY_GARDEN_LARGE_POOL OR
	 TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE))
	message(FATAL_ERROR "Large seed bank requires the undrained 512-node host maintenance experiment")
endif()
if(TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE AND NOT TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	message(FATAL_ERROR "Bottom drainage requires the host maintenance experiment")
endif()
if(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE AND NOT TOY_FACTORY_GARDEN_COMBINED_EXPERIMENT)
	message(FATAL_ERROR "Leaf maintenance requires the combined host experiment")
endif()
if(TOY_FACTORY_GARDEN_LARGE_POOL AND NOT TOY_FACTORY_GARDEN_COMBINED_EXPERIMENT)
	message(FATAL_ERROR "Large node pool requires the combined host experiment")
endif()
if(TOY_FACTORY_GARDEN_COMBINED_EXPERIMENT)
	if(NOT TOY_FACTORY_GARDEN_WIDE_DISPERSAL OR NOT TOY_FACTORY_GARDEN_WATER_HEADROOM)
		message(FATAL_ERROR "Combined experiment requires both ecology options")
	endif()
elseif(TOY_FACTORY_GARDEN_WIDE_DISPERSAL AND TOY_FACTORY_GARDEN_WATER_HEADROOM)
	message(FATAL_ERROR "Combined ecology requires TOY_FACTORY_GARDEN_COMBINED_EXPERIMENT=ON")
endif()

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

set(toy_factory_root "${CMAKE_CURRENT_LIST_DIR}/..")
set(toy_factory_sources
	${toy_factory_root}/src/game_snapshot.c
	${toy_factory_root}/src/garden_damage.c
	${toy_factory_root}/src/garden_agent.c
	${toy_factory_root}/src/garden_agent_neural.c
	${toy_factory_root}/src/garden_agent_neural_codec.c
	${toy_factory_root}/src/garden_light.c
	${toy_factory_root}/src/garden_world.c
	${toy_factory_root}/src/game_scene_clockwork.c
	${toy_factory_root}/src/game_scene_hourglass.c
	${toy_factory_root}/src/game_scene_machine_lab.c
	${toy_factory_root}/src/game_scene_marble_machine.c
	${toy_factory_root}/src/game_world.c
	${toy_factory_root}/src/granular_world.c
	${toy_factory_root}/src/graphics_raster.c
	${toy_factory_root}/src/physics_chain_fixture.c
	${toy_factory_root}/src/physics_world.c
	${toy_factory_root}/src/scene_renderer.c
	garden_evaluation.c
	garden_model_file.c
	garden_model_mutation.c
	garden_policy_probe.c
	garden_reserve_policy.c
	garden_root_bootstrap.c
	simulator.c
)

add_library(toy_factory_simulator_core STATIC ${toy_factory_sources})
if(TOY_FACTORY_GARDEN_SEED_RESERVE)
	target_compile_definitions(toy_factory_simulator_core PUBLIC TOY_FACTORY_GARDEN_SEED_RESERVE=1)
endif()
if(TOY_FACTORY_GARDEN_LARGE_SEED_BANK)
	target_compile_definitions(toy_factory_simulator_core PUBLIC TOY_FACTORY_GARDEN_LARGE_SEED_BANK=1)
endif()
set_source_files_properties(garden_reserve_policy.c garden_root_bootstrap.c garden_model_mutation.c PROPERTIES
	COMPILE_OPTIONS "-Wconversion;-Wsign-conversion")
if(TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE)
	target_compile_definitions(toy_factory_simulator_core PUBLIC TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE=1)
endif()
if(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	target_compile_definitions(toy_factory_simulator_core PUBLIC TOY_FACTORY_GARDEN_LEAF_MAINTENANCE=1)
	target_sources(toy_factory_simulator_core PRIVATE garden_leaf_policies.c garden_gap.c garden_disturbance.c)
endif()
if(TOY_FACTORY_GARDEN_WIDE_DISPERSAL)
	target_compile_definitions(toy_factory_simulator_core PUBLIC TOY_FACTORY_GARDEN_WIDE_DISPERSAL=1)
endif()
if(TOY_FACTORY_GARDEN_WATER_HEADROOM)
	target_compile_definitions(toy_factory_simulator_core PUBLIC TOY_FACTORY_GARDEN_WATER_HEADROOM=1)
endif()
if(TOY_FACTORY_GARDEN_COMBINED_EXPERIMENT)
	target_compile_definitions(toy_factory_simulator_core PUBLIC TOY_FACTORY_GARDEN_COMBINED_EXPERIMENT=1)
endif()
if(TOY_FACTORY_GARDEN_LARGE_POOL)
	target_compile_definitions(toy_factory_simulator_core PUBLIC TOY_FACTORY_GARDEN_LARGE_POOL=1)
endif()
target_include_directories(toy_factory_simulator_core PUBLIC
	${toy_factory_root}/src
	${CMAKE_CURRENT_LIST_DIR}
)
target_compile_options(toy_factory_simulator_core PRIVATE
	-Wall
	-Wextra
	-Werror
	-Wno-sign-compare
)

add_executable(toy-factory-sim main.c)
target_link_libraries(toy-factory-sim PRIVATE toy_factory_simulator_core)
target_compile_options(toy-factory-sim PRIVATE
	-Wall
	-Wextra
	-Werror
	-Wconversion
	-Wsign-conversion
)

add_executable(toy-factory-garden-eval garden_experiment.c garden_lifetimes.c)
target_link_libraries(toy-factory-garden-eval PRIVATE toy_factory_simulator_core)
target_compile_options(toy-factory-garden-eval PRIVATE
	-Wall
	-Wextra
	-Werror
	-Wconversion
	-Wsign-conversion
)

add_executable(toy-factory-garden-train garden_train.c)
target_link_libraries(toy-factory-garden-train PRIVATE toy_factory_simulator_core)
target_compile_options(toy-factory-garden-train PRIVATE
	-Wall
	-Wextra
	-Werror
	-Wconversion
	-Wsign-conversion
)

add_executable(toy-factory-garden-inspect garden_inspect.c)
target_link_libraries(toy-factory-garden-inspect PRIVATE toy_factory_simulator_core)
target_compile_options(toy-factory-garden-inspect PRIVATE
	-Wall -Wextra -Werror -Wconversion -Wsign-conversion
)

add_executable(toy-factory-garden-replay garden_replay.c)
target_link_libraries(toy-factory-garden-replay PRIVATE toy_factory_simulator_core)
target_compile_options(toy-factory-garden-replay PRIVATE
	-Wall -Wextra -Werror -Wconversion -Wsign-conversion
)

add_executable(toy-factory-garden-capacity-test garden_capacity_test.c)
target_link_libraries(toy-factory-garden-capacity-test PRIVATE toy_factory_simulator_core)
target_compile_options(toy-factory-garden-capacity-test PRIVATE
	-Wall -Wextra -Werror -Wconversion -Wsign-conversion -UNDEBUG)

add_executable(toy-factory-garden-lifetimes-test garden_lifetimes_test.c garden_lifetimes.c)
target_link_libraries(toy-factory-garden-lifetimes-test PRIVATE toy_factory_simulator_core)
target_compile_options(toy-factory-garden-lifetimes-test PRIVATE
	-Wall -Wextra -Werror -Wconversion -Wsign-conversion
)

add_executable(toy-factory-garden-policy-probe-test garden_policy_probe_test.c)
target_link_libraries(toy-factory-garden-policy-probe-test PRIVATE toy_factory_simulator_core)
target_compile_options(toy-factory-garden-policy-probe-test PRIVATE
	-Wall -Wextra -Werror -Wconversion -Wsign-conversion -UNDEBUG
)

add_executable(toy-factory-garden-reserve-policy-test garden_reserve_policy_test.c)
target_link_libraries(toy-factory-garden-reserve-policy-test PRIVATE toy_factory_simulator_core)
target_compile_options(toy-factory-garden-reserve-policy-test PRIVATE
	-Wall -Wextra -Werror -Wconversion -Wsign-conversion -UNDEBUG)
if(TOY_FACTORY_SIMULATOR_SANITIZERS AND CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
	target_compile_options(toy-factory-garden-reserve-policy-test PRIVATE -fsanitize=undefined -fno-sanitize-recover=undefined)
	target_link_options(toy-factory-garden-reserve-policy-test PRIVATE -fsanitize=undefined -fno-sanitize-recover=undefined)
endif()

add_executable(toy-factory-garden-seed-sites-test garden_seed_sites_test.c)
target_link_libraries(toy-factory-garden-seed-sites-test PRIVATE toy_factory_simulator_core)
target_compile_options(toy-factory-garden-seed-sites-test PRIVATE
	-Wall -Wextra -Werror -Wconversion -Wsign-conversion -UNDEBUG
)

add_executable(toy-factory-garden-water-uptake-test garden_water_uptake_test.c)
target_link_libraries(toy-factory-garden-water-uptake-test PRIVATE toy_factory_simulator_core)
target_compile_options(toy-factory-garden-water-uptake-test PRIVATE
	-Wall -Wextra -Werror -Wconversion -Wsign-conversion -UNDEBUG
)

add_executable(toy-factory-garden-damage-test garden_damage_test.c)
target_link_libraries(toy-factory-garden-damage-test PRIVATE toy_factory_simulator_core)
target_compile_options(toy-factory-garden-damage-test PRIVATE
	-Wall
	-Wextra
	-Werror
	-Wconversion
	-Wsign-conversion
)

add_executable(toy-factory-garden-neural-test
	${toy_factory_root}/scripts/tests/garden-neural-test.c
)
target_link_libraries(toy-factory-garden-neural-test PRIVATE toy_factory_simulator_core)
target_compile_options(toy-factory-garden-neural-test PRIVATE
	-Wall
	-Wextra
	-Werror
	-Wconversion
	-Wsign-conversion
)

if(TOY_FACTORY_SIMULATOR_PROFILING)
	target_compile_definitions(toy_factory_simulator_core PUBLIC
		TOY_FACTORY_RASTER_WORK_COUNTERS=1
	)
	add_executable(toy-factory-garden-profile garden_profile.c)
	target_link_libraries(toy-factory-garden-profile PRIVATE toy_factory_simulator_core)
	target_compile_options(toy-factory-garden-profile PRIVATE
		-Wall
		-Wextra
		-Werror
		-Wconversion
		-Wsign-conversion
	)
endif()

if(TOY_FACTORY_SIMULATOR_SANITIZERS AND CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
	target_compile_options(toy-factory-garden-capacity-test PRIVATE
		-fsanitize=undefined -fno-sanitize-recover=undefined)
	target_link_options(toy-factory-garden-capacity-test PRIVATE
		-fsanitize=undefined -fno-sanitize-recover=undefined)
	target_compile_options(toy-factory-garden-water-uptake-test PRIVATE
		-fsanitize=undefined -fno-sanitize-recover=undefined
	)
	target_link_options(toy-factory-garden-water-uptake-test PRIVATE
		-fsanitize=undefined -fno-sanitize-recover=undefined
	)
	target_compile_options(toy-factory-garden-seed-sites-test PRIVATE
		-fsanitize=undefined -fno-sanitize-recover=undefined
	)
	target_link_options(toy-factory-garden-seed-sites-test PRIVATE
		-fsanitize=undefined -fno-sanitize-recover=undefined
	)
	target_compile_options(toy-factory-garden-policy-probe-test PRIVATE
		-fsanitize=undefined -fno-sanitize-recover=undefined
	)
	target_link_options(toy-factory-garden-policy-probe-test PRIVATE
		-fsanitize=undefined -fno-sanitize-recover=undefined
	)
	target_compile_options(toy-factory-garden-replay PRIVATE
		-fsanitize=undefined -fno-sanitize-recover=undefined
	)
	target_link_options(toy-factory-garden-replay PRIVATE
		-fsanitize=undefined -fno-sanitize-recover=undefined
	)
	target_compile_options(toy-factory-garden-inspect PRIVATE
		-fsanitize=undefined -fno-sanitize-recover=undefined
	)
	target_link_options(toy-factory-garden-inspect PRIVATE
		-fsanitize=undefined -fno-sanitize-recover=undefined
	)
	target_compile_options(toy-factory-garden-lifetimes-test PRIVATE
		-fsanitize=undefined -fno-sanitize-recover=undefined
	)
	target_link_options(toy-factory-garden-lifetimes-test PRIVATE
		-fsanitize=undefined -fno-sanitize-recover=undefined
	)
	target_compile_options(toy_factory_simulator_core PRIVATE
		-fsanitize=undefined
		-fno-sanitize-recover=undefined
	)
	target_link_options(toy-factory-sim PRIVATE
		-fsanitize=undefined
		-fno-sanitize-recover=undefined
	)
	target_compile_options(toy-factory-garden-eval PRIVATE
		-fsanitize=undefined
		-fno-sanitize-recover=undefined
	)
	target_link_options(toy-factory-garden-eval PRIVATE
		-fsanitize=undefined
		-fno-sanitize-recover=undefined
	)
	target_compile_options(toy-factory-garden-train PRIVATE
		-fsanitize=undefined
		-fno-sanitize-recover=undefined
	)
	target_link_options(toy-factory-garden-train PRIVATE
		-fsanitize=undefined
		-fno-sanitize-recover=undefined
	)
	target_compile_options(toy-factory-garden-damage-test PRIVATE
		-fsanitize=undefined
		-fno-sanitize-recover=undefined
	)
	target_link_options(toy-factory-garden-damage-test PRIVATE
		-fsanitize=undefined
		-fno-sanitize-recover=undefined
	)
	target_compile_options(toy-factory-garden-neural-test PRIVATE
		-fsanitize=undefined
		-fno-sanitize-recover=undefined
	)
	target_link_options(toy-factory-garden-neural-test PRIVATE
		-fsanitize=undefined
		-fno-sanitize-recover=undefined
	)
	if(TOY_FACTORY_SIMULATOR_PROFILING)
		target_compile_options(toy-factory-garden-profile PRIVATE
			-fsanitize=undefined
			-fno-sanitize-recover=undefined
		)
		target_link_options(toy-factory-garden-profile PRIVATE
			-fsanitize=undefined
			-fno-sanitize-recover=undefined
		)
	endif()
endif()

if(TOY_FACTORY_SIMULATOR_PLAYER)
	include(FetchContent)

	# Keep SDL out of the repository and pin both its version and source archive.
	set(SDL_SHARED OFF CACHE BOOL "" FORCE)
	set(SDL_STATIC ON CACHE BOOL "" FORCE)
	set(SDL_TEST_LIBRARY OFF CACHE BOOL "" FORCE)
	set(SDL_TESTS OFF CACHE BOOL "" FORCE)
	set(SDL_EXAMPLES OFF CACHE BOOL "" FORCE)
	set(SDL_DISABLE_INSTALL ON CACHE BOOL "" FORCE)
	set(SDL_AUDIO OFF CACHE BOOL "" FORCE)
	set(SDL_CAMERA OFF CACHE BOOL "" FORCE)
	set(SDL_DIALOG OFF CACHE BOOL "" FORCE)
	set(SDL_GPU OFF CACHE BOOL "" FORCE)
	set(SDL_HAPTIC OFF CACHE BOOL "" FORCE)
	set(SDL_HIDAPI OFF CACHE BOOL "" FORCE)
	set(SDL_JOYSTICK OFF CACHE BOOL "" FORCE)
	set(SDL_POWER OFF CACHE BOOL "" FORCE)
	set(SDL_SENSOR OFF CACHE BOOL "" FORCE)
	set(SDL_TRAY OFF CACHE BOOL "" FORCE)
	set(SDL_DBUS OFF CACHE BOOL "" FORCE)
	set(SDL_IBUS OFF CACHE BOOL "" FORCE)
	set(SDL_KMSDRM OFF CACHE BOOL "" FORCE)
	set(SDL_LIBUDEV OFF CACHE BOOL "" FORCE)
	set(SDL_RENDER_GPU OFF CACHE BOOL "" FORCE)
	set(SDL_RENDER_VULKAN OFF CACHE BOOL "" FORCE)
	set(SDL_VULKAN OFF CACHE BOOL "" FORCE)
	set(SDL_WAYLAND OFF CACHE BOOL "" FORCE)
	FetchContent_Declare(
		SDL3
		URL https://github.com/libsdl-org/SDL/releases/download/release-3.4.10/SDL3-3.4.10.tar.gz
		URL_HASH SHA256=12b34280415ec8418c864408b93d008a20a6530687ee613d60bfbd20411f2785
		DOWNLOAD_EXTRACT_TIMESTAMP TRUE
	)
	FetchContent_MakeAvailable(SDL3)

	add_executable(toy-factory-player player.c)
	target_link_libraries(toy-factory-player PRIVATE toy_factory_simulator_core SDL3::SDL3)
	target_compile_options(toy-factory-player PRIVATE
		-Wall
		-Wextra
		-Werror
		-Wconversion
		-Wsign-conversion
	)
	if(TOY_FACTORY_SIMULATOR_SANITIZERS AND CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
		target_link_options(toy-factory-player PRIVATE
			-fsanitize=undefined
			-fno-sanitize-recover=undefined
		)
	endif()
endif()

find_package(Python3 REQUIRED COMPONENTS Interpreter)
enable_testing()
add_test(NAME garden-allocation-objectives-unit COMMAND ${Python3_EXECUTABLE}
	-W error ${CMAKE_CURRENT_LIST_DIR}/test_garden_allocation_objectives.py)
add_test(NAME garden-allocation-survival-unit COMMAND ${Python3_EXECUTABLE}
	-W error ${CMAKE_CURRENT_LIST_DIR}/test_garden_allocation_survival.py)
add_test(NAME garden-descendants-unit COMMAND ${Python3_EXECUTABLE}
	-W error ${CMAKE_CURRENT_LIST_DIR}/test_garden_descendants.py)
add_test(NAME garden-lineage-fitness-unit COMMAND ${Python3_EXECUTABLE}
	-W error ${CMAKE_CURRENT_LIST_DIR}/test_garden_lineage_fitness.py)
add_test(NAME garden-lineage-persistence-unit COMMAND ${Python3_EXECUTABLE}
	-W error ${CMAKE_CURRENT_LIST_DIR}/test_garden_lineage_persistence.py)
add_test(NAME garden-pilot-validation-unit COMMAND ${Python3_EXECUTABLE}
	-W error ${CMAKE_CURRENT_LIST_DIR}/test_garden_pilot_validation.py)
add_test(NAME garden-mixed-training-unit COMMAND ${Python3_EXECUTABLE}
	-W error ${CMAKE_CURRENT_LIST_DIR}/test_garden_mixed_training.py)
add_test(NAME garden-window-stability-unit COMMAND ${Python3_EXECUTABLE}
	-W error ${CMAKE_CURRENT_LIST_DIR}/test_garden_window_stability.py)
add_test(NAME garden-sustained-renewal-unit COMMAND ${Python3_EXECUTABLE}
	-W error ${CMAKE_CURRENT_LIST_DIR}/test_garden_sustained_renewal.py)
add_test(NAME garden-individual-renewal-unit COMMAND ${Python3_EXECUTABLE}
	-W error ${CMAKE_CURRENT_LIST_DIR}/test_garden_individual_renewal.py)
add_test(NAME garden-renewal-stalls-unit COMMAND ${Python3_EXECUTABLE}
	-W error ${CMAKE_CURRENT_LIST_DIR}/test_garden_renewal_stalls.py)
add_test(NAME garden-recruitment-recovery-unit COMMAND ${Python3_EXECUTABLE}
	-W error ${CMAKE_CURRENT_LIST_DIR}/test_garden_recruitment_recovery.py)
add_executable(toy-factory-garden-model-mutate garden_model_mutate.c)
add_executable(toy-factory-garden-persistence-check garden_persistence_check.c garden_persistence.c)
set(persistence_targets toy-factory-garden-model-mutate toy-factory-garden-persistence-check)
if(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE AND TOY_FACTORY_GARDEN_LARGE_POOL
	AND NOT TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE AND NOT TOY_FACTORY_GARDEN_LARGE_SEED_BANK
	AND NOT TOY_FACTORY_GARDEN_SEED_RESERVE)
	add_executable(toy-factory-garden-persistence-trial garden_persistence_trial.c garden_persistence.c)
	list(APPEND persistence_targets toy-factory-garden-persistence-trial)
endif()
foreach(target IN LISTS persistence_targets)
	target_link_libraries(${target} PRIVATE toy_factory_simulator_core)
	target_compile_options(${target} PRIVATE -Wall -Wextra -Werror -Wconversion -Wsign-conversion)
	if(TOY_FACTORY_SIMULATOR_SANITIZERS AND CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
		target_compile_options(${target} PRIVATE -fsanitize=undefined -fno-sanitize-recover=undefined)
		target_link_options(${target} PRIVATE -fsanitize=undefined -fno-sanitize-recover=undefined)
	endif()
endforeach()
add_test(NAME garden-persistence-native-unit COMMAND ${Python3_EXECUTABLE}
	-W error ${CMAKE_CURRENT_LIST_DIR}/test_garden_persistence_native.py --build ${CMAKE_BINARY_DIR})
add_executable(toy-factory-garden-allocation-policy-test
	garden_allocation_policy_test.c garden_allocation_policy.c)
set(allocation_targets toy-factory-garden-allocation-policy-test)
if(TOY_FACTORY_GARDEN_SEED_RESERVE)
	add_executable(toy-factory-garden-allocation garden_allocation.c garden_allocation_policy.c)
	list(APPEND allocation_targets toy-factory-garden-allocation)
endif()
foreach(target IN LISTS allocation_targets)
	target_link_libraries(${target} PRIVATE toy_factory_simulator_core)
	target_compile_options(${target} PRIVATE -Wall -Wextra -Werror -Wconversion -Wsign-conversion -UNDEBUG)
	if(TOY_FACTORY_SIMULATOR_SANITIZERS AND CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
		target_compile_options(${target} PRIVATE -fsanitize=undefined -fno-sanitize-recover=undefined)
		target_link_options(${target} PRIVATE -fsanitize=undefined -fno-sanitize-recover=undefined)
	endif()
endforeach()
add_test(NAME garden-allocation-policy-unit COMMAND toy-factory-garden-allocation-policy-test)
add_test(NAME garden-allocation-analysis COMMAND ${Python3_EXECUTABLE}
	${CMAKE_CURRENT_LIST_DIR}/test_garden_allocation.py --build ${CMAKE_BINARY_DIR})
add_executable(toy-factory-garden-root-bootstrap-test garden_root_bootstrap_test.c)
target_link_libraries(toy-factory-garden-root-bootstrap-test PRIVATE toy_factory_simulator_core)
target_compile_options(toy-factory-garden-root-bootstrap-test PRIVATE
	-Wall -Wextra -Werror -Wconversion -Wsign-conversion -UNDEBUG)
if(TOY_FACTORY_SIMULATOR_SANITIZERS AND CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
	target_compile_options(toy-factory-garden-root-bootstrap-test PRIVATE -fsanitize=undefined -fno-sanitize-recover=undefined)
	target_link_options(toy-factory-garden-root-bootstrap-test PRIVATE -fsanitize=undefined -fno-sanitize-recover=undefined)
endif()
add_test(NAME garden-root-bootstrap-unit COMMAND toy-factory-garden-root-bootstrap-test)
add_test(NAME garden-root-bootstrap-audit COMMAND ${Python3_EXECUTABLE}
	${CMAKE_CURRENT_LIST_DIR}/test_garden_root_bootstrap.py --build ${CMAKE_BINARY_DIR})
add_test(NAME garden-seedling-water-unit COMMAND ${Python3_EXECUTABLE}
	${CMAKE_CURRENT_LIST_DIR}/test_garden_seedling_water.py)
add_test(NAME garden-seed-reserve-analysis-unit COMMAND ${Python3_EXECUTABLE}
	${CMAKE_CURRENT_LIST_DIR}/test_garden_seed_reserve.py)
if(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE AND TOY_FACTORY_GARDEN_LARGE_POOL
	AND NOT TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE)
	add_executable(toy-factory-garden-seed-reserve-test garden_seed_reserve_test.c)
	target_link_libraries(toy-factory-garden-seed-reserve-test PRIVATE toy_factory_simulator_core)
	target_compile_options(toy-factory-garden-seed-reserve-test PRIVATE
		-Wall -Wextra -Werror -Wconversion -Wsign-conversion -UNDEBUG)
	if(TOY_FACTORY_SIMULATOR_SANITIZERS AND CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
		target_compile_options(toy-factory-garden-seed-reserve-test PRIVATE -fsanitize=undefined -fno-sanitize-recover=undefined)
		target_link_options(toy-factory-garden-seed-reserve-test PRIVATE -fsanitize=undefined -fno-sanitize-recover=undefined)
	endif()
	add_test(NAME garden-seed-reserve-unit COMMAND toy-factory-garden-seed-reserve-test)
endif()
add_test(NAME garden-reserve-policy-unit COMMAND toy-factory-garden-reserve-policy-test)
add_test(NAME garden-policy-panel-unit COMMAND ${Python3_EXECUTABLE}
	${CMAKE_CURRENT_LIST_DIR}/test_garden_policy_panel.py)
add_test(NAME garden-turnover-unit COMMAND ${Python3_EXECUTABLE}
	${CMAKE_CURRENT_LIST_DIR}/test_garden_turnover.py)
add_test(NAME garden-recruitment-unit COMMAND ${Python3_EXECUTABLE}
	${CMAKE_CURRENT_LIST_DIR}/test_garden_recruitment.py)
if(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE AND NOT TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE
	AND NOT TOY_FACTORY_GARDEN_LARGE_SEED_BANK AND NOT TOY_FACTORY_GARDEN_SEED_RESERVE)
	add_test(NAME garden-recruitment-integration COMMAND ${Python3_EXECUTABLE}
		${CMAKE_CURRENT_LIST_DIR}/test_garden_recruitment.py --build ${CMAKE_BINARY_DIR})
endif()

add_test(NAME garden-damage-unit COMMAND toy-factory-garden-damage-test)
add_test(NAME garden-neural-unit COMMAND toy-factory-garden-neural-test)
add_test(NAME garden-lifetimes-unit COMMAND toy-factory-garden-lifetimes-test)
add_test(NAME garden-water-uptake-unit COMMAND toy-factory-garden-water-uptake-test)
add_test(NAME garden-leaf-guards COMMAND ${Python3_EXECUTABLE}
	${CMAKE_CURRENT_LIST_DIR}/test_garden_leaf_guards.py --cc ${CMAKE_C_COMPILER})
add_test(NAME garden-leaf-competition-unit COMMAND ${Python3_EXECUTABLE}
	${CMAKE_CURRENT_LIST_DIR}/test_garden_leaf_competition.py)

if(TOY_FACTORY_GARDEN_LEAF_MAINTENANCE)
	add_executable(toy-factory-garden-water-budget garden_water_budget.c)
	add_executable(toy-factory-garden-water-audit-test garden_water_audit_test.c)
	add_executable(toy-factory-garden-seed-attempts garden_seed_attempts.c)
	add_executable(toy-factory-garden-seed-audit-test garden_seed_audit_test.c)
	foreach(target toy-factory-garden-water-budget toy-factory-garden-water-audit-test
		toy-factory-garden-seed-attempts toy-factory-garden-seed-audit-test)
		target_link_libraries(${target} PRIVATE toy_factory_simulator_core)
		target_compile_options(${target} PRIVATE -Wall -Wextra -Werror -Wconversion -Wsign-conversion -UNDEBUG)
		if(TOY_FACTORY_SIMULATOR_SANITIZERS AND CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
			target_compile_options(${target} PRIVATE -fsanitize=undefined -fno-sanitize-recover=undefined)
			target_link_options(${target} PRIVATE -fsanitize=undefined -fno-sanitize-recover=undefined)
		endif()
	endforeach()
	add_test(NAME garden-water-audit-unit COMMAND toy-factory-garden-water-audit-test)
	add_test(NAME garden-seed-audit-unit COMMAND toy-factory-garden-seed-audit-test)
	if(TOY_FACTORY_GARDEN_SEED_RESERVE)
		add_test(NAME garden-capacity-unit COMMAND toy-factory-garden-capacity-test)
		add_test(NAME garden-seed-sites-unit COMMAND toy-factory-garden-seed-sites-test)
		# Old ecology smoke fixtures intentionally reject the new rule identity.
		return()
	endif()
	add_test(NAME garden-seed-attempts-smoke COMMAND ${Python3_EXECUTABLE}
		${CMAKE_CURRENT_LIST_DIR}/test_garden_seed_attempts.py --build ${CMAKE_BINARY_DIR})
	if(NOT TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE)
		add_test(NAME garden-seed-bank-smoke COMMAND ${Python3_EXECUTABLE}
			${CMAKE_CURRENT_LIST_DIR}/test_garden_seed_bank.py --build ${CMAKE_BINARY_DIR})
	endif()
	if(TOY_FACTORY_GARDEN_LARGE_SEED_BANK)
		add_test(NAME garden-capacity-unit COMMAND toy-factory-garden-capacity-test)
		add_test(NAME garden-seed-sites-unit COMMAND toy-factory-garden-seed-sites-test)
		# Eight-seed ecology expectations are not the new experiment's contract.
		return()
	endif()
	set(water_budget_args)
	if(TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE)
		list(APPEND water_budget_args --drainage)
	endif()
	add_test(NAME garden-water-budget-smoke COMMAND ${Python3_EXECUTABLE}
		${CMAKE_CURRENT_LIST_DIR}/test_garden_water_budget.py --build ${CMAKE_BINARY_DIR} ${water_budget_args})
	add_test(NAME garden-policy-diagnostic-smoke COMMAND ${Python3_EXECUTABLE}
		${CMAKE_CURRENT_LIST_DIR}/test_garden_policy_diagnostic.py --build ${CMAKE_BINARY_DIR})
	add_test(NAME garden-reserve-policy-smoke COMMAND ${Python3_EXECUTABLE}
		${CMAKE_CURRENT_LIST_DIR}/test_garden_reserve_policy.py --build ${CMAKE_BINARY_DIR})
	if(TOY_FACTORY_GARDEN_BOTTOM_DRAINAGE)
		add_test(NAME garden-drainage-smoke COMMAND ${Python3_EXECUTABLE}
			${CMAKE_CURRENT_LIST_DIR}/test_garden_drainage.py --build ${CMAKE_BINARY_DIR})
		# The previous ecology's frozen census expectations are not drainage fixtures.
		return()
	endif()
	add_executable(toy-factory-garden-leaf-test garden_leaf_test.c)
	add_executable(toy-factory-garden-disturbance-test garden_disturbance_test.c)
	target_link_libraries(toy-factory-garden-disturbance-test PRIVATE toy_factory_simulator_core)
	target_compile_options(toy-factory-garden-disturbance-test PRIVATE
		-Wall -Wextra -Werror -Wconversion -Wsign-conversion -UNDEBUG)
	if(TOY_FACTORY_SIMULATOR_SANITIZERS AND CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
		target_compile_options(toy-factory-garden-disturbance-test PRIVATE
			-fsanitize=undefined -fno-sanitize-recover=undefined)
		target_link_options(toy-factory-garden-disturbance-test PRIVATE
			-fsanitize=undefined -fno-sanitize-recover=undefined)
	endif()
	add_test(NAME garden-disturbance-unit COMMAND toy-factory-garden-disturbance-test)
	add_test(NAME garden-disturbance-smoke COMMAND ${Python3_EXECUTABLE}
		${CMAKE_CURRENT_LIST_DIR}/test_garden_disturbance.py --build ${CMAKE_BINARY_DIR})
	add_test(NAME garden-diversity-smoke COMMAND ${Python3_EXECUTABLE}
		${CMAKE_CURRENT_LIST_DIR}/test_garden_diversity.py --build ${CMAKE_BINARY_DIR})
	add_executable(toy-factory-garden-gap-test garden_gap_test.c)
	target_link_libraries(toy-factory-garden-gap-test PRIVATE toy_factory_simulator_core)
	target_compile_options(toy-factory-garden-gap-test PRIVATE
		-Wall -Wextra -Werror -Wconversion -Wsign-conversion -UNDEBUG)
	target_link_libraries(toy-factory-garden-leaf-test PRIVATE toy_factory_simulator_core)
	target_compile_options(toy-factory-garden-leaf-test PRIVATE
		-Wall -Wextra -Werror -Wconversion -Wsign-conversion -UNDEBUG)
	if(TOY_FACTORY_SIMULATOR_SANITIZERS AND CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
		target_compile_options(toy-factory-garden-gap-test PRIVATE
			-fsanitize=undefined -fno-sanitize-recover=undefined)
		target_link_options(toy-factory-garden-gap-test PRIVATE
			-fsanitize=undefined -fno-sanitize-recover=undefined)
		target_compile_options(toy-factory-garden-leaf-test PRIVATE
			-fsanitize=undefined -fno-sanitize-recover=undefined)
		target_link_options(toy-factory-garden-leaf-test PRIVATE
			-fsanitize=undefined -fno-sanitize-recover=undefined)
	endif()
	add_test(NAME garden-leaf-unit COMMAND toy-factory-garden-leaf-test)
	add_test(NAME garden-gap-unit COMMAND toy-factory-garden-gap-test)
	add_test(NAME garden-gap-smoke COMMAND ${Python3_EXECUTABLE}
		${CMAKE_CURRENT_LIST_DIR}/test_garden_gap_experiment.py --build ${CMAKE_BINARY_DIR})
	add_test(NAME garden-leaf-smoke COMMAND ${Python3_EXECUTABLE}
		${CMAKE_CURRENT_LIST_DIR}/test_garden_leaf_experiment.py --build ${CMAKE_BINARY_DIR})
	add_test(NAME garden-leaf-competition-smoke COMMAND ${Python3_EXECUTABLE}
		${CMAKE_CURRENT_LIST_DIR}/test_garden_leaf_competition.py --build ${CMAKE_BINARY_DIR})
	# Default-ecology golden hashes and the trainer are not this experiment's contract.
	return()
endif()

add_test(
	NAME garden-resources-unit
	COMMAND ${Python3_EXECUTABLE} -W error
		${toy_factory_root}/benchmarks/garden-longevity/test_resources.py
)
add_test(
	NAME garden-experiment-smoke
	COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_LIST_DIR}/test_garden_experiment.py
		--binary $<TARGET_FILE:toy-factory-garden-eval>
		--summary ${CMAKE_CURRENT_LIST_DIR}/summarize_garden_experiment.py
)
add_test(
	NAME garden-rainfall-smoke
	COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_LIST_DIR}/test_garden_rainfall.py
		--binary $<TARGET_FILE:toy-factory-garden-eval>
)
add_test(
	NAME garden-experiment-bundle
	COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_LIST_DIR}/test_garden_experiments.py
		--evaluator $<TARGET_FILE:toy-factory-garden-eval>
		--inspector $<TARGET_FILE:toy-factory-garden-inspect>
		--trainer $<TARGET_FILE:toy-factory-garden-train>
)
add_test(
	NAME garden-train-smoke
	COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_LIST_DIR}/test_garden_train.py
		--binary $<TARGET_FILE:toy-factory-garden-train>
		--evaluator $<TARGET_FILE:toy-factory-garden-eval>
		--source-root ${toy_factory_root}
		--cc ${CMAKE_C_COMPILER}
)

add_test(
	NAME garden-gallery-smoke
	COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_LIST_DIR}/test_garden_gallery.py
		--replayer $<TARGET_FILE:toy-factory-garden-replay>
		--evaluator $<TARGET_FILE:toy-factory-garden-eval>
		--inspector $<TARGET_FILE:toy-factory-garden-inspect>
		--trainer $<TARGET_FILE:toy-factory-garden-train>
)

add_test(NAME garden-policy-probe-unit COMMAND toy-factory-garden-policy-probe-test)
add_test(NAME garden-seed-sites-unit COMMAND toy-factory-garden-seed-sites-test)
add_test(NAME garden-factorial-unit
	COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_LIST_DIR}/test_garden_factorial.py)
add_test(NAME garden-capacity-unit COMMAND toy-factory-garden-capacity-test)
add_test(NAME garden-tip-audit-unit
	COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_LIST_DIR}/test_garden_tip_audit.py)
add_test(NAME garden-capacity-guards
	COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_LIST_DIR}/test_garden_capacity.py
		--cc ${CMAKE_C_COMPILER})
add_test(NAME garden-node-audit-smoke
	COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_LIST_DIR}/test_garden_node_audit.py
		--evaluator $<TARGET_FILE:toy-factory-garden-eval>
		--inspector $<TARGET_FILE:toy-factory-garden-inspect>)
add_test(
	NAME garden-establishment-smoke
	COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_LIST_DIR}/test_garden_establishment.py
		--evaluator $<TARGET_FILE:toy-factory-garden-eval>
		--inspector $<TARGET_FILE:toy-factory-garden-inspect>
)
add_test(
	NAME garden-policy-probe-smoke
	COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_LIST_DIR}/test_garden_policy_probe.py
		--replayer $<TARGET_FILE:toy-factory-garden-replay>
		--evaluator $<TARGET_FILE:toy-factory-garden-eval>
		--inspector $<TARGET_FILE:toy-factory-garden-inspect>
		--trainer $<TARGET_FILE:toy-factory-garden-train>
)

foreach(sequence IN ITEMS
	clockwork-smoke.json
	deterministic-smoke.json
	garden-generations.json
	garden-lifecycle.json
	garden-smoke.json
	garden-mature.json
	hourglass-neutral-smoke.json
	marble-machine-smoke.json
)
	string(REPLACE ".json" "" test_name "${sequence}")
	add_test(
		NAME "sequence-${test_name}"
		COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_LIST_DIR}/run_sequence.py
			--binary $<TARGET_FILE:toy-factory-sim>
			--sequence ${toy_factory_root}/scripts/sequences/${sequence}
	)
endforeach()

if(TOY_FACTORY_SIMULATOR_PROFILING)
	add_test(
		NAME garden-profile-smoke
		COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_LIST_DIR}/test_garden_profile.py
			--binary $<TARGET_FILE:toy-factory-garden-profile>
	)
endif()

if(TOY_FACTORY_SIMULATOR_PLAYER)
	add_test(NAME player-smoke COMMAND toy-factory-player --frames 1 --paused)
	set_tests_properties(player-smoke PROPERTIES ENVIRONMENT "SDL_VIDEODRIVER=dummy")
endif()
