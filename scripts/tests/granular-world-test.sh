#!/usr/bin/env bash

set -euo pipefail

readonly test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT

gcc -std=c11 -Wall -Wextra -Werror -Wconversion -Wsign-conversion \
	-fsanitize=undefined -fno-sanitize-recover=undefined -Isrc \
	src/granular_world.c scripts/tests/granular-world-test.c \
	-o "$test_dir/granular-world-test"
"$test_dir/granular-world-test"
