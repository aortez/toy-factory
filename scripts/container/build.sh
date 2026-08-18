#!/usr/bin/env bash

set -euo pipefail

readonly workspace_dir=/workspace
readonly app_dir=/workspace/app
readonly manifest_stamp="$workspace_dir/.picosystem-west-manifest.sha256"

pristine_mode=auto
variant=default
display_frequency=

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
		--display-frequency)
			if (( $# < 2 )); then
				echo "--display-frequency requires a value" >&2
				exit 2
			fi
			display_frequency=$2
			shift 2
			;;
		*)
			echo "usage: $0 [--pristine] [--variant default|pio|pio-dma|pl022-dma]" \
				"[--display-frequency 20000000|31250000|41666667|62500000]" >&2
			exit 2
			;;
	esac
done

readonly pristine_mode
readonly variant
readonly display_frequency

build_dir=$app_dir/build
cmake_options=(-DCMAKE_EXPORT_COMPILE_COMMANDS=ON)
display_transport_overlay=

case "$variant" in
	default)
		;;
	pio)
		build_dir=$app_dir/build-pio
		display_transport_overlay=$app_dir/benchmarks/pio-dma/picosystem-pio-dma.overlay
		;;
	pio-dma)
		build_dir=$app_dir/build-pio-dma
		display_transport_overlay=$app_dir/benchmarks/pio-dma/picosystem-pio-dma.overlay
		cmake_options+=(-DEXTRA_CONF_FILE=$app_dir/benchmarks/pio-dma/pio-dma.conf)
		;;
	pl022-dma)
		build_dir=$app_dir/build-pl022-dma
		display_transport_overlay=$app_dir/benchmarks/pl022-dma/picosystem-pl022-dma.overlay
		cmake_options+=(-DEXTRA_CONF_FILE=$app_dir/benchmarks/pl022-dma/pl022-dma.conf)
		;;
	*)
		echo "unknown build variant: $variant" >&2
		exit 2
		;;
esac

display_frequency_overlay=
if [[ -n "$display_frequency" ]]; then
	case "$display_frequency" in
		20000000|31250000|41666667|62500000)
			;;
		*)
			echo "unsupported display frequency: $display_frequency" >&2
			exit 2
			;;
	esac
	if [[ "$variant" == pio || "$variant" == pio-dma ]] &&
		(( display_frequency > 31250000 )); then
		echo "PIO SPI is limited to 31250000 Hz by its four-cycle transfer program" >&2
		exit 2
	fi
	display_frequency_overlay="$app_dir/benchmarks/display-throughput/frequency-$display_frequency.overlay"
	build_dir=$app_dir/build-render-profile-$variant-$display_frequency
fi

if [[ -n "$display_transport_overlay" ]] && [[ -n "$display_frequency_overlay" ]]; then
	cmake_options+=(
		"-DDTC_OVERLAY_FILE=$display_transport_overlay;$display_frequency_overlay"
	)
elif [[ -n "$display_transport_overlay" ]]; then
	cmake_options+=("-DDTC_OVERLAY_FILE=$display_transport_overlay")
elif [[ -n "$display_frequency_overlay" ]]; then
	cmake_options+=("-DDTC_OVERLAY_FILE=$display_frequency_overlay")
fi

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
