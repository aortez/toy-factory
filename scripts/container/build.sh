#!/usr/bin/env bash

set -euo pipefail

readonly workspace_dir=/workspace
readonly app_dir=/workspace/app
readonly manifest_stamp="$workspace_dir/.picosystem-west-manifest.sha256"

pristine_mode=auto
variant=default

while (( $# > 0 )); do
	case "$1" in
		--pristine)
			pristine_mode=always
			shift
			;;
		--variant)
			if (( $# < 2 )); then
				echo "--variant requires a value" >&2
				exit 2
			fi
			variant=$2
			shift 2
			;;
		*)
			echo "usage: $0 [--pristine] [--variant default|pio|pio-dma]" >&2
			exit 2
			;;
	esac
done

readonly pristine_mode
readonly variant

build_dir=$app_dir/build
cmake_options=(-DCMAKE_EXPORT_COMPILE_COMMANDS=ON)

case "$variant" in
	default)
		;;
	pio)
		build_dir=$app_dir/build-pio
		cmake_options+=(
			-DDTC_OVERLAY_FILE=$app_dir/benchmarks/pio-dma/picosystem-pio-dma.overlay
		)
		;;
	pio-dma)
		build_dir=$app_dir/build-pio-dma
		cmake_options+=(
			-DDTC_OVERLAY_FILE=$app_dir/benchmarks/pio-dma/picosystem-pio-dma.overlay
			-DEXTRA_CONF_FILE=$app_dir/benchmarks/pio-dma/pio-dma.conf
		)
		;;
	*)
		echo "unknown build variant: $variant" >&2
		exit 2
		;;
esac

readonly build_dir

if [[ ! -f "$manifest_stamp" ]] || ! sha256sum --check --status "$manifest_stamp"; then
	"$app_dir/scripts/container/setup.sh"
fi

cd "$workspace_dir"
west build \
	--board picosystem \
	--build-dir "$build_dir" \
	--pristine="$pristine_mode" \
	"$app_dir" \
	-- "${cmake_options[@]}"
