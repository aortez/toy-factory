#!/usr/bin/env bash

set -euo pipefail

if (( $# > 1 )); then
	echo "usage: $0 [UF2_MOUNT]" >&2
	exit 2
fi

readonly requested_mount=${1:-}

canonical_path()
{
	local path=$1

	(
		cd -- "$path"
		pwd -P
	)
}

validate_mount()
{
	local path=$1

	if [[ ! -d "$path" ]] || [[ ! -f "$path/INFO_UF2.TXT" ]]; then
		echo "not an RP2040 UF2 volume: $path" >&2
		exit 1
	fi
}

if [[ -n "$requested_mount" ]]; then
	validate_mount "$requested_mount"
	canonical_path "$requested_mount"
	exit 0
fi

shopt -s nullglob
candidate_mounts=()

add_candidate()
{
	local candidate=$1
	local resolved

	[[ -d "$candidate" ]] || return 0
	[[ -f "$candidate/INFO_UF2.TXT" ]] || return 0
	resolved=$(canonical_path "$candidate")

	for existing in "${candidate_mounts[@]:-}"; do
		[[ "$existing" == "$resolved" ]] && return 0
	done

	candidate_mounts+=("$resolved")
}

# Cover the conventional desktop automount locations on Linux and macOS, plus
# /mnt for users who mount the UF2 volume themselves.
for candidate in \
	/media/* /media/*/* \
	/run/media/* /run/media/*/* \
	/Volumes/* \
	/mnt/*; do
	add_candidate "$candidate"
done

case ${#candidate_mounts[@]} in
	0)
		echo "no RP2040 UF2 volume found" >&2
		echo "boot while holding X, then retry; or set UF2_MOUNT=/path/to/RPI-RP2" >&2
		exit 1
		;;
	1)
		printf '%s\n' "${candidate_mounts[0]}"
		;;
	*)
		echo "multiple RP2040 UF2 volumes found:" >&2
		printf '  %s\n' "${candidate_mounts[@]}" >&2
		echo "select one with UF2_MOUNT=/path/to/RPI-RP2" >&2
		exit 1
		;;
esac
