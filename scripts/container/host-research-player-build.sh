#!/usr/bin/env bash
set -euo pipefail

cd /workspace/app
readonly runtime=/workspace/app/artifacts/garden-research-runtime-v1
readonly build_dir=/workspace/app/artifacts/garden-research-player-build-v1

python3 -B sim/research_player/prepare.py --out "$runtime"
cmake -S sim/research_player -B "$build_dir" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS=-O2 \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
    -DTOY_FACTORY_RESEARCH_RUNTIME="$runtime" -DTOY_FACTORY_RESEARCH_VIEWER=ON
cmake --build "$build_dir" --parallel 2 \
    --target research-player research-replay research-session-test
