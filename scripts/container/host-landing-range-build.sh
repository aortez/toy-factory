#!/usr/bin/env bash
set -euo pipefail

cd /workspace/app
source scripts/container/host-garden-defaults.sh

# Keep this research pair separate from build-host and from frozen collections.
for range_arm in narrow wide; do
	range_setting=OFF
	if [[ "$range_arm" == wide ]]; then
		range_setting=ON
	fi
	cmake -S sim -B "artifacts/build-host-landing-range/$range_arm" -G Ninja \
		"${garden_default_cmake_options[@]}" \
		-DTOY_FACTORY_GARDEN_WIDE_DISPERSAL="$range_setting" \
		-DCMAKE_BUILD_TYPE=RelWithDebInfo \
		-DTOY_FACTORY_SIMULATOR_SANITIZERS=ON \
		-DTOY_FACTORY_SIMULATOR_PROFILING=ON
	cmake --build "artifacts/build-host-landing-range/$range_arm"
done
