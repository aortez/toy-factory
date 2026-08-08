#!/usr/bin/env bash

set -euo pipefail

readonly app_dir=/workspace/app

cd "$app_dir"
clang-format --dry-run --Werror src/main.c
git diff --check
./scripts/container/build.sh --pristine
