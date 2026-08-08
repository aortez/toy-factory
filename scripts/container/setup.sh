#!/usr/bin/env bash

set -euo pipefail

readonly workspace_dir=/workspace
readonly app_dir=/workspace/app
readonly manifest_stamp="$workspace_dir/.picosystem-west-manifest.sha256"

cd "$workspace_dir"

if [[ ! -d .west ]]; then
	west init -l "$app_dir"
fi

west update --narrow -o=--depth=1
west zephyr-export
sha256sum "$app_dir/west.yml" > "$manifest_stamp"
