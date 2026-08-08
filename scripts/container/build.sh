#!/usr/bin/env bash

set -euo pipefail

readonly workspace_dir=/workspace
readonly app_dir=/workspace/app
readonly manifest_stamp="$workspace_dir/.picosystem-west-manifest.sha256"

pristine_mode=auto
if [[ ${1:-} == "--pristine" ]]; then
	pristine_mode=always
	shift
fi

if (( $# != 0 )); then
	echo "usage: $0 [--pristine]" >&2
	exit 2
fi

if [[ ! -f "$manifest_stamp" ]] || ! sha256sum --check --status "$manifest_stamp"; then
	"$app_dir/scripts/container/setup.sh"
fi

cd "$workspace_dir"
west build \
	--board picosystem \
	--build-dir "$app_dir/build" \
	--pristine="$pristine_mode" \
	"$app_dir" \
	-- \
	-DCMAKE_EXPORT_COMPILE_COMMANDS=ON
