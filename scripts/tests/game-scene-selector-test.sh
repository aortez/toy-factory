#!/usr/bin/env bash

set -euo pipefail

readonly test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT

gcc -std=c11 -Wall -Wextra -Werror -Wconversion -Wsign-conversion -Isrc \
	src/game_scene_selector.c scripts/tests/game-scene-selector-test.c \
	-o "$test_dir/game-scene-selector-test"
"$test_dir/game-scene-selector-test"
