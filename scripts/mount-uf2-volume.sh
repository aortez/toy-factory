#!/usr/bin/env bash

set -euo pipefail

if (( $# != 0 )); then
	echo "usage: $0" >&2
	exit 2
fi

readonly lsblk_command=${PICOSYSTEM_LSBLK_COMMAND:-lsblk}
readonly udevadm_command=${PICOSYSTEM_UDEVADM_COMMAND:-udevadm}
readonly udisksctl_command=${PICOSYSTEM_UDISKSCTL_COMMAND:-udisksctl}
readonly allow_non_block_devices=${PICOSYSTEM_TEST_ALLOW_NON_BLOCK_DEVICES:-0}
host_os=${PICOSYSTEM_HOST_OS:-$(uname -s)}
readonly host_os

if [[ "$host_os" != Linux ]]; then
	echo "automatic RPI-RP2 mounting is available only on Linux" >&2
	exit 1
fi

for required_command in "$lsblk_command" "$udevadm_command" "$udisksctl_command"; do
	if ! command -v "$required_command" >/dev/null 2>&1; then
		echo "automatic RPI-RP2 mounting requires $required_command" >&2
		exit 1
	fi
done

has_property()
{
	local properties=$1
	local expected=$2
	local property

	while IFS= read -r property; do
		[[ "$property" == "$expected" ]] && return 0
	done <<<"$properties"

	return 1
}

candidate_devices=()

add_candidate()
{
	local device=$1
	local existing
	local properties

	if [[ "$allow_non_block_devices" != 1 ]] && [[ ! -b "$device" ]]; then
		return 0
	fi

	if ! properties=$("$udevadm_command" info --query=property --name="$device" 2>/dev/null); then
		return 0
	fi

	has_property "$properties" "ID_BUS=usb" || return 0
	has_property "$properties" "ID_VENDOR=RPI" || return 0
	has_property "$properties" "ID_MODEL=RP2" || return 0
	has_property "$properties" "ID_FS_LABEL=RPI-RP2" || return 0
	has_property "$properties" "ID_FS_TYPE=vfat" || return 0

	for existing in "${candidate_devices[@]:-}"; do
		[[ "$existing" == "$device" ]] && return 0
	done

	candidate_devices+=("$device")
}

while IFS= read -r device_record; do
	if [[ "$device_record" =~ ^PATH=\"([^\"]+)\"[[:space:]]+LABEL=\"RPI-RP2\"[[:space:]]+FSTYPE=\"vfat\"[[:space:]]+TYPE=\"part\"[[:space:]]+RM=\"1\"$ ]]; then
		add_candidate "${BASH_REMATCH[1]}"
	fi
done < <("$lsblk_command" --paths --pairs --output PATH,LABEL,FSTYPE,TYPE,RM)

case ${#candidate_devices[@]} in
	0)
		echo "no unmounted RPI-RP2 USB block device found" >&2
		exit 1
		;;
	1)
		;;
	*)
		echo "multiple unmounted RPI-RP2 USB block devices found:" >&2
		printf '  %s\n' "${candidate_devices[@]}" >&2
		echo "mount one manually and select it with UF2_MOUNT=/path/to/RPI-RP2" >&2
		exit 2
		;;
esac

readonly block_device=${candidate_devices[0]}
echo "mounting verified RPI-RP2 device $block_device"
if ! "$udisksctl_command" mount --no-user-interaction --block-device "$block_device"; then
	echo "failed to mount verified RPI-RP2 device $block_device" >&2
	exit 1
fi
