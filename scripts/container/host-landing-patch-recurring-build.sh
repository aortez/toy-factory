#!/usr/bin/env bash
set -euo pipefail
readonly app_dir=/workspace/app
cd "$app_dir"
source "$app_dir/scripts/container/host-garden-defaults.sh"
cmake -S sim -B build-host-patch-recurring -G Ninja \
	"${garden_default_cmake_options[@]}" \
	-DTOY_FACTORY_GARDEN_LATE_UPTAKE_LIMIT=ON \
	-DTOY_FACTORY_GARDEN_LATE_DISPERSAL=ON \
	-DTOY_FACTORY_SIMULATOR_SANITIZERS=ON \
	-DTOY_FACTORY_SIMULATOR_PROFILING=ON
cmake --build build-host-patch-recurring --target toy-factory-garden-landing \
	toy-factory-garden-patch-sweep-test toy-factory-garden-seed-cursor-test \
	toy-factory-garden-seed-wait-test toy-factory-garden-order-test
ctest --test-dir build-host-patch-recurring --output-on-failure \
	-R '^garden-landing-(patch-sweep-native|seed-cursor-native|seed-wait-native|order-native)$'
