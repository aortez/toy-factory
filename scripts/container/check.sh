#!/usr/bin/env bash

set -euo pipefail

readonly app_dir=/workspace/app

cd "$app_dir"
clang-format --dry-run --Werror src/*.c src/*.h scripts/tests/*.c
bash -n scripts/*.sh scripts/container/*.sh scripts/tests/*.sh
./scripts/tests/fixed-rate-scheduler-test.sh
./scripts/tests/game-scene-selector-test.sh
./scripts/tests/physics-world-test.sh
./scripts/tests/granular-world-test.sh
./scripts/tests/game-world-test.sh
./scripts/tests/mount-uf2-volume-test.sh
python3 - <<'PY'
from pathlib import Path

for path in sorted(Path("scripts/container").glob("*.py")):
    compile(path.read_text(), str(path), "exec")
PY
for profile in benchmarks/physics-profile/*.json; do
	python3 -m json.tool "$profile" >/dev/null
done
for profile in benchmarks/display-throughput/*.json; do
	python3 -m json.tool "$profile" >/dev/null
done
python3 scripts/tests/framebuffer-capture-test.py
python3 scripts/tests/profile-compare-test.py
python3 scripts/tests/render-profile-test.py
python3 scripts/tests/sequence-runner-test.py
python3 scripts/tests/serial-command-test.py
git diff --check
./scripts/container/build.sh --pristine
