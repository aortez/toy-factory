#!/usr/bin/env bash

set -euo pipefail

if (( $# > 4 )); then
	echo "usage: $0 [UF2_MOUNT] [PORT] [UF2_ARTIFACT] [FIRMWARE_IMAGE]" >&2
	exit 2
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
readonly script_dir
readonly requested_mount=${1:-}
readonly requested_port=${2:-}
readonly artifact=${3:-build/zephyr/zephyr.uf2}
readonly firmware_image=${4:-toy-factory-builder:local}
readonly update_timeout_seconds=${PICOSYSTEM_UPDATE_TIMEOUT_SECONDS:-15}

if [[ ! "$update_timeout_seconds" =~ ^[1-9][0-9]*$ ]]; then
	echo "PICOSYSTEM_UPDATE_TIMEOUT_SECONDS must be a positive integer" >&2
	exit 2
fi

if [[ ! -f "$artifact" ]]; then
	echo "UF2 artifact not found: $artifact" >&2
	exit 1
fi

find_mount_quietly()
{
	"$script_dir/find-uf2-mount.sh" "$requested_mount" 2>/dev/null
}

find_or_mount_quietly()
{
	local mounted_path

	if mounted_path=$(find_mount_quietly); then
		printf '%s\n' "$mounted_path"
		return 0
	fi

	[[ -z "$requested_mount" ]] || return 1
	"$script_dir/mount-uf2-volume.sh" >/dev/null 2>&1 || return 1
	find_mount_quietly
}

if uf2_mount=$(find_or_mount_quietly); then
	"$script_dir/flash.sh" "$uf2_mount" "$artifact"
	exit 0
fi

if ! port=$("$script_dir/find-serial-port.sh" "$requested_port"); then
	echo "cannot request update mode because neither the application shell nor a UF2 volume is available" >&2
	echo "close any open console, or use the hold-X power-on recovery sequence and retry" >&2
	exit 1
fi
readonly port

"$script_dir/reboot-to-bootloader.sh" "$port" "$firmware_image"

echo "waiting up to $update_timeout_seconds seconds for the RPI-RP2 volume"
start_seconds=$SECONDS
readonly start_seconds
while (( SECONDS - start_seconds < update_timeout_seconds )); do
	if uf2_mount=$(find_or_mount_quietly); then
		"$script_dir/flash.sh" "$uf2_mount" "$artifact"
		exit 0
	fi

	sleep 0.1
done

if uf2_mount=$(find_or_mount_quietly); then
	"$script_dir/flash.sh" "$uf2_mount" "$artifact"
	exit 0
fi

if [[ -z "$requested_mount" ]] && "$script_dir/mount-uf2-volume.sh"; then
	if uf2_mount=$(find_mount_quietly); then
		"$script_dir/flash.sh" "$uf2_mount" "$artifact"
		exit 0
	fi
fi

echo "timed out waiting for the RP2040 UF2 volume" >&2
echo "use the hold-X power-on recovery sequence, then retry make update" >&2
exit 1
