.DEFAULT_GOAL := build

COMPOSE := docker compose
DOCKER := docker
FIRMWARE_IMAGE := picosystem-zephyr-builder:local
UF2 := build/zephyr/zephyr.uf2
SERIAL_PORT_HELPER := ./scripts/find-serial-port.sh

.PHONY: image setup build format check container-shell shell flash update console monitor status

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

container-shell:
	$(COMPOSE) run --rm firmware bash

shell: container-shell

flash: build
	./scripts/flash.sh "$(UF2_MOUNT)" "$(UF2)"

update: flash

console: image
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")"; \
		echo "opening PicoSystem console on $$port (exit with Ctrl+])"; \
		exec $(DOCKER) run --rm --interactive --tty --user 0:0 \
			--device "$$port:$$port" "$(FIRMWARE_IMAGE)" \
			python3 -m serial.tools.miniterm "$$port" 115200

monitor: console

status: image
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")"; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py "$$port" picosystem status
