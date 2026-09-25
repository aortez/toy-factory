#!/usr/bin/env bash

set -euo pipefail

if (( $# != 0 )); then
	echo "usage: $0" >&2
	exit 2
fi

readonly app_dir=/workspace/app
# Separate from all ordinary builds and from immutable experiment bundles.
readonly build_dir="$app_dir/artifacts/build-host-research-check"
cd "$app_dir"
source "$app_dir/scripts/container/host-garden-defaults.sh"

# This is a representative maximal dependency chain, not every incompatible
# research combination. It runs regressions, not a new ecology/training trial.
cmake -S sim -B "$build_dir" -G Ninja \
	"${garden_default_cmake_options[@]}" \
	-DCMAKE_BUILD_TYPE=RelWithDebInfo \
	-DTOY_FACTORY_SIMULATOR_SANITIZERS=ON \
	-DTOY_FACTORY_SIMULATOR_PLAYER=OFF \
	-DTOY_FACTORY_SIMULATOR_PROFILING=OFF \
	-DTOY_FACTORY_GARDEN_WIDE_DISPERSAL=ON \
	-DTOY_FACTORY_GARDEN_WATER_HEADROOM=ON \
	-DTOY_FACTORY_GARDEN_COMBINED_EXPERIMENT=ON \
	-DTOY_FACTORY_GARDEN_LARGE_POOL=ON \
	-DTOY_FACTORY_GARDEN_LEAF_MAINTENANCE=ON \
	-DTOY_FACTORY_GARDEN_DARK_GUARD=ON \
	-DTOY_FACTORY_GARDEN_NIGHT_CAPACITY=ON \
	-DTOY_FACTORY_GARDEN_WET_GERMINATION=ON \
	-DTOY_FACTORY_GARDEN_DAWN_FINISH=ON \
	-DTOY_FACTORY_GARDEN_SEED_ORDER=ON \
	-DTOY_FACTORY_GARDEN_SEED_SPACING=ON \
	-DTOY_FACTORY_GARDEN_CANOPY_TRANSMISSION=ON \
	-DTOY_FACTORY_GARDEN_PLANT_SLOTS=ON \
	-DTOY_FACTORY_GARDEN_FULL_POOL=ON
cmake --build "$build_dir" --parallel 2
ctest --test-dir "$build_dir" --output-on-failure --parallel 2
