#!/usr/bin/env bash

set -euo pipefail

readonly app_dir=/workspace/app
readonly build_dir="$app_dir/build-host-profile"

cd "$app_dir"

if [[ "${1:-}" == "--pristine" ]]; then
	rm -rf -- "$build_dir"
elif [[ $# -ne 0 ]]; then
	echo "usage: $0 [--pristine]" >&2
	exit 2
fi

cmake -S sim -B "$build_dir" -G Ninja \
	-DCMAKE_BUILD_TYPE=Release \
	-DTOY_FACTORY_SIMULATOR_SANITIZERS=OFF \
	-DTOY_FACTORY_SIMULATOR_PROFILING=ON
cmake --build "$build_dir" --target toy-factory-garden-profile
