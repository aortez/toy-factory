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

source "$app_dir/scripts/container/host-garden-defaults.sh"
cmake -S sim -B "$build_dir" -G Ninja \
	"${garden_default_cmake_options[@]}" \
	-DTOY_FACTORY_SIMULATOR_SANITIZERS=ON \
	-DTOY_FACTORY_SIMULATOR_PROFILING=ON
cmake --build "$build_dir"
