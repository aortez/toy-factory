.DEFAULT_GOAL := build

COMPOSE := docker compose
DOCKER := docker
FIRMWARE_IMAGE := picosystem-zephyr-builder:local
UF2 := build/zephyr/zephyr.uf2

.PHONY: image setup build format check shell flash monitor

image:
	$(COMPOSE) build firmware

setup:
	$(COMPOSE) run --rm firmware ./scripts/container/setup.sh

build:
	$(COMPOSE) run --rm firmware

format:
	$(COMPOSE) run --rm firmware clang-format -i src/*.c src/*.h

check:
	$(COMPOSE) run --rm firmware ./scripts/container/check.sh

shell:
	$(COMPOSE) run --rm firmware bash

flash: build
	./scripts/flash.sh "$(UF2_MOUNT)" "$(UF2)"

monitor:
	@test -n "$(PORT)" || (echo "usage: make monitor PORT=/dev/ttyACM0" >&2; exit 2)
	$(COMPOSE) build firmware
	$(DOCKER) run --rm --interactive --tty --user 0:0 \
		--device "$(PORT):$(PORT)" "$(FIRMWARE_IMAGE)" \
		python3 -m serial.tools.miniterm "$(PORT)" 115200
