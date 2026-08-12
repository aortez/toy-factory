#!/usr/bin/env bash

set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
readonly script_dir
readonly helper=$script_dir/../mount-uf2-volume.sh
test_dir=$(mktemp -d)
readonly test_dir
trap 'rm -rf -- "$test_dir"' EXIT

test_lsblk()
{
	printf '%s' "$PICOSYSTEM_TEST_LSBLK_OUTPUT"
}

test_udevadm()
{
	local argument
	local device=

	for argument in "$@"; do
		case "$argument" in
			--name=*) device=${argument#--name=} ;;
		esac
	done

	if [[ " $PICOSYSTEM_TEST_VALID_DEVICES " != *" $device "* ]]; then
		printf '%s\n' ID_BUS=usb ID_VENDOR=NOT_RPI ID_MODEL=RP2 \
			ID_FS_LABEL=RPI-RP2 ID_FS_TYPE=vfat
		return 0
	fi

	printf '%s\n' ID_BUS=usb ID_VENDOR=RPI ID_MODEL=RP2 ID_FS_LABEL=RPI-RP2 \
		ID_FS_TYPE=vfat
}

test_udisksctl()
{
	printf '%s\n' "$*" >>"$PICOSYSTEM_TEST_MOUNT_LOG"
	if [[ "$PICOSYSTEM_TEST_MOUNT_FAIL" == 1 ]]; then
		return 1
	fi

	echo "Mounted test device"
}

export -f test_lsblk test_udevadm test_udisksctl
export PICOSYSTEM_HOST_OS=Linux
export PICOSYSTEM_LSBLK_COMMAND=test_lsblk
export PICOSYSTEM_UDEVADM_COMMAND=test_udevadm
export PICOSYSTEM_UDISKSCTL_COMMAND=test_udisksctl
export PICOSYSTEM_TEST_ALLOW_NON_BLOCK_DEVICES=1
export PICOSYSTEM_TEST_MOUNT_LOG=$test_dir/mount.log

run_helper()
{
	set +e
	helper_output=$($helper 2>&1)
	helper_status=$?
	set -e
}

reset_case()
{
	: >"$PICOSYSTEM_TEST_MOUNT_LOG"
	export PICOSYSTEM_TEST_LSBLK_OUTPUT=
	export PICOSYSTEM_TEST_VALID_DEVICES=
	export PICOSYSTEM_TEST_MOUNT_FAIL=0
}

assert_status()
{
	local expected=$1

	if (( helper_status != expected )); then
		echo "expected status $expected, got $helper_status" >&2
		echo "$helper_output" >&2
		exit 1
	fi
}

assert_contains()
{
	local expected=$1

	if [[ "$helper_output" != *"$expected"* ]]; then
		echo "expected output to contain: $expected" >&2
		echo "$helper_output" >&2
		exit 1
	fi
}

assert_mount_log()
{
	local expected=$1
	local actual

	actual=$(<"$PICOSYSTEM_TEST_MOUNT_LOG")
	if [[ "$actual" != "$expected" ]]; then
		echo "expected mount invocation: $expected" >&2
		echo "actual mount invocation: $actual" >&2
		exit 1
	fi
}

readonly valid_sdb='PATH="/dev/sdb1" LABEL="RPI-RP2" FSTYPE="vfat" TYPE="part" RM="1"'
readonly valid_sdc='PATH="/dev/sdc1" LABEL="RPI-RP2" FSTYPE="vfat" TYPE="part" RM="1"'

reset_case
export PICOSYSTEM_TEST_LSBLK_OUTPUT="$valid_sdb"$'\n'
export PICOSYSTEM_TEST_VALID_DEVICES=/dev/sdb1
run_helper
assert_status 0
assert_contains "mounting verified RPI-RP2 device /dev/sdb1"
assert_mount_log "mount --no-user-interaction --block-device /dev/sdb1"

reset_case
export PICOSYSTEM_TEST_LSBLK_OUTPUT="$valid_sdb"$'\n'
run_helper
assert_status 1
assert_contains "no unmounted RPI-RP2 USB block device found"
assert_mount_log ""

reset_case
export PICOSYSTEM_TEST_LSBLK_OUTPUT="$valid_sdb"$'\n'"$valid_sdc"$'\n'
export PICOSYSTEM_TEST_VALID_DEVICES="/dev/sdb1 /dev/sdc1"
run_helper
assert_status 2
assert_contains "multiple unmounted RPI-RP2 USB block devices found"
assert_mount_log ""

reset_case
export PICOSYSTEM_HOST_OS=Darwin
run_helper
assert_status 1
assert_contains "available only on Linux"
export PICOSYSTEM_HOST_OS=Linux

reset_case
export PICOSYSTEM_TEST_LSBLK_OUTPUT="$valid_sdb"$'\n'
export PICOSYSTEM_TEST_VALID_DEVICES=/dev/sdb1
export PICOSYSTEM_TEST_MOUNT_FAIL=1
run_helper
assert_status 1
assert_contains "failed to mount verified RPI-RP2 device /dev/sdb1"
assert_mount_log "mount --no-user-interaction --block-device /dev/sdb1"

echo "mount-uf2-volume tests passed"
