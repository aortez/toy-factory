#!/usr/bin/env bash

set -euo pipefail

if (( $# > 2 )); then
	echo "usage: $0 [PORT] [FIRMWARE_IMAGE]" >&2
	exit 2
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
readonly script_dir
repository_dir=$(cd -- "$script_dir/.." && pwd -P)
readonly repository_dir
readonly requested_port=${1:-}
readonly firmware_image=${2:-toy-factory-builder:local}

port=$("$script_dir/find-serial-port.sh" "$requested_port")
readonly port

echo "requesting RP2040 ROM bootloader on $port"
exec docker run --rm --user 0:0 \
	--device "$port:$port" \
	--volume "$repository_dir:/workspace/app:ro" \
	"$firmware_image" \
	python3 ./scripts/container/serial-command.py \
		--expect-disconnect --timeout 5 \
		"$port" picosystem reboot bootloader
