#!/usr/bin/env bash

set -euo pipefail

readonly app_dir=/workspace/app

cd "$app_dir"
clang-format --dry-run --Werror src/*.c src/*.h
bash -n scripts/*.sh scripts/container/*.sh scripts/tests/*.sh
./scripts/tests/fixed-rate-scheduler-test.sh
./scripts/tests/mount-uf2-volume-test.sh
python3 - <<'PY'
from pathlib import Path

path = Path("scripts/container/serial-command.py")
compile(path.read_text(), str(path), "exec")
PY
git diff --check
./scripts/container/build.sh --pristine
