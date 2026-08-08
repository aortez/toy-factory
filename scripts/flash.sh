#!/usr/bin/env bash

set -euo pipefail

readonly uf2_mount=${1:-}
readonly artifact=${2:-build/zephyr/zephyr.uf2}

if [[ -z "$uf2_mount" ]]; then
	echo "usage: make flash UF2_MOUNT=/path/to/RPI-RP2" >&2
	exit 2
fi

if [[ ! -f "$artifact" ]]; then
	echo "UF2 artifact not found: $artifact" >&2
	exit 1
fi

if [[ ! -d "$uf2_mount" ]] || [[ ! -f "$uf2_mount/INFO_UF2.TXT" ]]; then
	echo "not an RP2040 UF2 volume: $uf2_mount" >&2
	exit 1
fi

cp "$artifact" "$uf2_mount/zephyr.uf2"
sync "$uf2_mount/zephyr.uf2" 2>/dev/null || sync
echo "flashed $artifact to $uf2_mount"
