.DEFAULT_GOAL := help

COMPOSE := docker compose
DOCKER := docker
FIRMWARE_IMAGE := picosystem-zephyr-builder:local
UF2 := build/zephyr/zephyr.uf2
PIO_UF2 := build-pio/zephyr/zephyr.uf2
PIO_DMA_UF2 := build-pio-dma/zephyr/zephyr.uf2
SERIAL_PORT_HELPER := ./scripts/find-serial-port.sh

.PHONY: help image setup build build-pio build-pio-dma format check check-pio-dma \
	container-shell update update-pio update-pio-dma bootloader console status flash monitor shell

##@ General

help: ## Show this list of targets
	@printf 'PicoSystem Zephyr playground\n\n'
	@printf 'Usage:\n  make <target> [PORT=/dev/ttyACM0] [UF2_MOUNT=/path/to/RPI-RP2]\n'
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

##@ Compatibility aliases

flash: update ## Alias for update

monitor: console ## Alias for console

shell: container-shell ## Alias for container-shell
