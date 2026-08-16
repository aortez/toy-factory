#!/usr/bin/env bash

set -euo pipefail

if (( $# > 1 )); then
	echo "usage: $0 [PORT]" >&2
	exit 2
fi

readonly requested_port=${1:-}

canonical_path()
{
	local path=$1

	if command -v realpath >/dev/null 2>&1; then
		realpath -- "$path"
	elif readlink -f / >/dev/null 2>&1; then
		readlink -f -- "$path"
	else
		printf '%s\n' "$path"
	fi
}

validate_port()
{
	local path=$1

	if [[ ! -e "$path" ]]; then
		echo "serial port does not exist: $path" >&2
		exit 1
	fi

	if [[ ! -c "$path" ]]; then
		echo "not a character device: $path" >&2
		exit 1
	fi
}

if [[ -n "$requested_port" ]]; then
	validate_port "$requested_port"
	canonical_path "$requested_port"
	exit 0
fi

shopt -s nullglob
candidate_ports=()

add_candidate()
{
	local candidate=$1
	local resolved

	[[ -c "$candidate" ]] || return 0
	resolved=$(canonical_path "$candidate")

	for existing in "${candidate_ports[@]:-}"; do
		[[ "$existing" == "$resolved" ]] && return 0
	done

	candidate_ports+=("$resolved")
}

# A Toy Factory by-id link is more specific than an arbitrary ACM device. Keep
# the generic Zephyr identity for upgrading older firmware, then fall back to
# common ACM names when udev has not created persistent links.
for candidate in /dev/serial/by-id/usb-Toy_Factory_Toy_Factory_PicoSystem* \
	/dev/serial/by-id/usb-Zephyr_Project_CDC_ACM*; do
	add_candidate "$candidate"
done

if (( ${#candidate_ports[@]} == 0 )); then
	for candidate in /dev/ttyACM* /dev/cu.usbmodem*; do
		add_candidate "$candidate"
	done
fi

case ${#candidate_ports[@]} in
	0)
		echo "no Toy Factory USB serial port found" >&2
		echo "boot the application and reconnect USB, or set PORT=/dev/ttyACM0" >&2
		exit 1
		;;
	1)
		printf '%s\n' "${candidate_ports[0]}"
		;;
	*)
		echo "multiple Toy Factory USB serial ports found:" >&2
		printf '  %s\n' "${candidate_ports[@]}" >&2
		echo "select one with PORT=/dev/ttyACM0" >&2
		exit 1
		;;
esac
