#!/usr/bin/env bash
set -euo pipefail
readonly app_dir=/workspace/app
cd "$app_dir"
source "$app_dir/scripts/container/host-garden-defaults.sh"
for variant in uptake-limit uptake-limit-wicking; do
	wicking=OFF
	if [[ "$variant" == uptake-limit-wicking ]]; then wicking=ON; fi
	cmake -S sim -B "build-host-$variant" -G Ninja \
		"${garden_default_cmake_options[@]}" \
		-DTOY_FACTORY_GARDEN_LATE_UPTAKE_LIMIT=ON \
		-DTOY_FACTORY_GARDEN_SOIL_WICKING="$wicking" \
		-DTOY_FACTORY_SIMULATOR_SANITIZERS=ON \
		-DTOY_FACTORY_SIMULATOR_PROFILING=ON
	cmake --build "build-host-$variant" --target toy-factory-garden-landing \
		toy-factory-garden-water-uptake-test toy-factory-garden-wicking-test
	ctest --test-dir "build-host-$variant" -R '^garden-(water-uptake-unit|wicking-native)$' --output-on-failure
done
