#!/usr/bin/env bash

set -euo pipefail

readonly test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT

gcc -std=c11 -Wall -Wextra -Werror -Wconversion -Wsign-conversion \
	-fsanitize=undefined -fno-sanitize-recover=undefined -Isrc \
	src/physics_world.c src/game_world.c src/physics_chain_fixture.c \
	scripts/tests/game-world-test.c \
	-o "$test_dir/game-world-test"
"$test_dir/game-world-test"
