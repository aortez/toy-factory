#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
readonly script_dir
readonly requested_mount=${1:-}
readonly artifact=${2:-build/zephyr/zephyr.uf2}

if [[ ! -f "$artifact" ]]; then
	echo "UF2 artifact not found: $artifact" >&2
	exit 1
fi

uf2_mount=$("$script_dir/find-uf2-mount.sh" "$requested_mount")
readonly uf2_mount

cp "$artifact" "$uf2_mount/zephyr.uf2"
sync "$uf2_mount/zephyr.uf2" 2>/dev/null || sync
echo "flashed $artifact to $uf2_mount"
