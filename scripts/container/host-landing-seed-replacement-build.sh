#!/usr/bin/env bash
set -euo pipefail
readonly app_dir=/workspace/app
cd "$app_dir"
bash scripts/container/host-landing-disturbance-build.sh
for variant in late-dispersal late-dispersal-wicking; do
	cmake --build "build-host-$variant" --target toy-factory-garden-seed-replacement-test
	ctest --test-dir "build-host-$variant" --output-on-failure \
		-R '^garden-landing-seed-replacement(-native)?$'
done
