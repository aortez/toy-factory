.DEFAULT_GOAL := help

COMPOSE := docker compose
DOCKER := docker
FIRMWARE_IMAGE := toy-factory-builder:local
UF2 := build/zephyr/zephyr.uf2
PIO_UF2 := build-pio/zephyr/zephyr.uf2
PIO_DMA_UF2 := build-pio-dma/zephyr/zephyr.uf2
SERIAL_PORT_HELPER := ./scripts/find-serial-port.sh
STEPS ?= 1
INPUT ?= none
OUT ?= artifacts/screenshot.png
SEQUENCE ?= scripts/sequences/deterministic-smoke.json
FAIL_SCREENSHOT ?= artifacts/sequence-failure.png

.PHONY: help image setup build build-pio build-pio-dma format check check-pio-dma \
	container-shell update update-pio update-pio-dma bootloader console status game-stats \
	game-redraw display-sync display-checksum screenshot sim-pause sim-run sim-step sim-input \
	sim-reset sim-state sim-test \
	flash monitor shell

##@ General

help: ## Show this list of targets
	@printf 'Toy Factory\n\n'
	@printf 'Usage:\n  make <target> [PORT=/dev/ttyACM0] [UF2_MOUNT=/path/to/RPI-RP2]\n'
	@printf '                    [STEPS=1] [INPUT=none] [OUT=artifacts/screenshot.png]\n'
	@printf '                    [SEQUENCE=path.json] [FAIL_SCREENSHOT=artifacts/failure.png]\n'
	@awk 'BEGIN { FS = ":.*## " } \
		/^##@ / { printf "\n%s:\n", substr($$0, 5); next } \
		/^[a-zA-Z0-9_-]+:.*## / { printf "  %-18s %s\n", $$1, $$2 }' \
		$(MAKEFILE_LIST)

##@ Build and development

image: ## Build or refresh the Docker builder image
	$(COMPOSE) build firmware

setup: ## Refresh the pinned Zephyr dependencies
	$(COMPOSE) run --rm firmware ./scripts/container/setup.sh

build: ## Build the firmware in Docker
	$(COMPOSE) run --rm firmware

build-pio: ## Build the PIO SPI benchmark variant
	$(COMPOSE) run --rm firmware ./scripts/container/build.sh --variant pio

build-pio-dma: ## Build the PIO SPI plus DMA benchmark variant
	$(COMPOSE) run --rm firmware ./scripts/container/build.sh --variant pio-dma

format: ## Format the application C source
	$(COMPOSE) run --rm firmware clang-format -i src/*.c src/*.h

check: ## Run checks and a pristine firmware build
	$(COMPOSE) run --rm firmware ./scripts/container/check.sh

check-pio-dma: ## Pristine-build the PIO SPI plus DMA benchmark
	$(COMPOSE) run --rm firmware ./scripts/container/build.sh --pristine --variant pio-dma

container-shell: ## Open a shell in the builder container
	$(COMPOSE) run --rm firmware bash

##@ Device

update: build ## Build, enter the ROM bootloader, and flash firmware
	./scripts/update.sh "$(UF2_MOUNT)" "$(PORT)" "$(UF2)" "$(FIRMWARE_IMAGE)"

update-pio: build-pio ## Build and flash the PIO SPI benchmark
	./scripts/update.sh "$(UF2_MOUNT)" "$(PORT)" "$(PIO_UF2)" "$(FIRMWARE_IMAGE)"

update-pio-dma: build-pio-dma ## Build and flash the PIO SPI plus DMA benchmark
	./scripts/update.sh "$(UF2_MOUNT)" "$(PORT)" "$(PIO_DMA_UF2)" "$(FIRMWARE_IMAGE)"

bootloader: image ## Reboot the running app into the RP2040 ROM bootloader
	./scripts/reboot-to-bootloader.sh "$(PORT)" "$(FIRMWARE_IMAGE)"

console: image ## Open the interactive device shell and log stream
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")"; \
		echo "opening PicoSystem console on $$port (exit with Ctrl+])"; \
		exec $(DOCKER) run --rm --interactive --tty --user 0:0 \
			--device "$$port:$$port" "$(FIRMWARE_IMAGE)" \
			python3 -m serial.tools.miniterm --filter direct "$$port" 115200

status: image ## Print one device status snapshot and exit
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")"; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py "$$port" picosystem status

game-stats: image ## Print simulation, snapshot, renderer, and stack metrics
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")"; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py "$$port" picosystem game stats

game-redraw: image ## Queue an asynchronous full-screen redraw
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")"; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py "$$port" picosystem game redraw

display-sync: image ## Print LCD tearing-effect timing and synchronization metrics
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")"; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py "$$port" picosystem display sync

display-checksum: image ## Print the coherent presented-framebuffer checksum
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")"; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py --require-prefix "width=" "$$port" \
				picosystem display checksum

screenshot: image ## Capture the coherent presented framebuffer as OUT=<relative PNG path>
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")"; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/framebuffer-capture.py \
				--owner-uid "$$(id -u)" --owner-gid "$$(id -g)" \
				"$$port" "/workspace/app/$(OUT)"

sim-pause: image ## Pause simulation at a tick boundary and print exact state
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")"; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py --require-prefix "mode=" "$$port" \
				picosystem game pause

sim-run: image ## Resume exact real-time 120 Hz simulation scheduling
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")"; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py --require-prefix "mode=" "$$port" \
				picosystem game run

sim-reset: image ## Restore canonical tick-zero state while paused
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")"; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py --require-prefix "mode=" "$$port" \
				picosystem game reset

sim-step: image ## Advance a paused simulation by STEPS=<1-120> exact ticks
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")"; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py --require-prefix "mode=" "$$port" \
				picosystem game step "$(STEPS)"

sim-input: image ## Select INPUT=physical|none|up|down|left|right|<diagonal>
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")"; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py --require-prefix "mode=" "$$port" \
				picosystem game input "$(INPUT)"

sim-state: image ## Print exact simulation state and deterministic hash
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")"; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py --require-prefix "mode=" "$$port" \
				picosystem game state

sim-test: image ## Run SEQUENCE=<JSON> with deterministic hash/CRC assertions
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")"; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/sequence_runner.py \
				--failure-screenshot "/workspace/app/$(FAIL_SCREENSHOT)" \
				--owner-uid "$$(id -u)" --owner-gid "$$(id -g)" \
				"$$port" "/workspace/app/$(SEQUENCE)"

##@ Compatibility aliases

flash: update ## Alias for update

monitor: console ## Alias for console

shell: container-shell ## Alias for container-shell
