#!/usr/bin/env bash

set -euo pipefail

readonly app_dir=/workspace/app
readonly build_dir="$app_dir/build-host"

cd "$app_dir"

if [[ "${1:-}" == "--pristine" ]]; then
	rm -rf -- "$build_dir"
elif [[ $# -ne 0 ]]; then
	echo "usage: $0 [--pristine]" >&2
	exit 2
fi

cmake -S sim -B "$build_dir" -G Ninja \
	-DTOY_FACTORY_GARDEN_WIDE_DISPERSAL=OFF \
	-DTOY_FACTORY_GARDEN_WATER_HEADROOM=OFF \
	-DTOY_FACTORY_GARDEN_COMBINED_EXPERIMENT=OFF \
	-DTOY_FACTORY_GARDEN_LARGE_POOL=OFF \
	-DTOY_FACTORY_GARDEN_LEAF_MAINTENANCE=OFF \
	-DTOY_FACTORY_GARDEN_BOTTOM_DRAINAGE=OFF \
	-DTOY_FACTORY_GARDEN_LARGE_SEED_BANK=OFF \
	-DTOY_FACTORY_GARDEN_SEED_RESERVE=OFF \
	-DTOY_FACTORY_SIMULATOR_SANITIZERS=ON \
	-DTOY_FACTORY_SIMULATOR_PROFILING=ON
cmake --build "$build_dir"
