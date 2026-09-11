# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20)
project(toy_factory_simulator C)

option(TOY_FACTORY_SIMULATOR_SANITIZERS "Enable host undefined-behavior checks" ON)
option(TOY_FACTORY_SIMULATOR_PLAYER "Build the interactive SDL3 player" OFF)
option(TOY_FACTORY_SIMULATOR_PROFILING "Build host profiling tools" OFF)
option(TOY_FACTORY_GARDEN_WIDE_DISPERSAL "Experimental host-only 3-9 cell seed scattering" OFF)
option(TOY_FACTORY_GARDEN_WATER_HEADROOM "Experimental host-only storage-limited root uptake" OFF)
option(TOY_FACTORY_GARDEN_COMBINED_EXPERIMENT "Explicit opt-in to the combined host ecology trial" OFF)
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
	garden_policy_probe.c
	simulator.c
)

add_library(toy_factory_simulator_core STATIC ${toy_factory_sources})
if(TOY_FACTORY_GARDEN_WIDE_DISPERSAL)
	target_compile_definitions(toy_factory_simulator_core PUBLIC TOY_FACTORY_GARDEN_WIDE_DISPERSAL=1)
endif()
if(TOY_FACTORY_GARDEN_WATER_HEADROOM)
	target_compile_definitions(toy_factory_simulator_core PUBLIC TOY_FACTORY_GARDEN_WATER_HEADROOM=1)
endif()
if(TOY_FACTORY_GARDEN_COMBINED_EXPERIMENT)
	target_compile_definitions(toy_factory_simulator_core PUBLIC TOY_FACTORY_GARDEN_COMBINED_EXPERIMENT=1)
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

add_test(NAME garden-damage-unit COMMAND toy-factory-garden-damage-test)
add_test(NAME garden-neural-unit COMMAND toy-factory-garden-neural-test)
add_test(NAME garden-lifetimes-unit COMMAND toy-factory-garden-lifetimes-test)
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
add_test(NAME garden-water-uptake-unit COMMAND toy-factory-garden-water-uptake-test)
add_test(NAME garden-factorial-unit
	COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_LIST_DIR}/test_garden_factorial.py)
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
