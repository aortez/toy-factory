#!/usr/bin/env bash
set -euo pipefail
readonly app_dir=/workspace/app
cd "$app_dir"
source "$app_dir/scripts/container/host-garden-defaults.sh"
cmake -S sim -B build-host-wicking -G Ninja \
	"${garden_default_cmake_options[@]}" \
	-DTOY_FACTORY_GARDEN_SOIL_WICKING=ON \
	-DTOY_FACTORY_SIMULATOR_SANITIZERS=ON \
	-DTOY_FACTORY_SIMULATOR_PROFILING=ON
cmake --build build-host-wicking --target toy-factory-garden-landing toy-factory-garden-wicking-test
ctest --test-dir build-host-wicking -R '^garden-wicking-native$' --output-on-failure
