#!/usr/bin/env bash

set -euo pipefail

readonly test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT

gcc -std=c11 -Wall -Wextra -Werror -Isrc \
	src/fixed_rate_scheduler.c scripts/tests/fixed-rate-scheduler-test.c \
	-o "$test_dir/fixed-rate-scheduler-test"
"$test_dir/fixed-rate-scheduler-test"
