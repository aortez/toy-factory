.DEFAULT_GOAL := help

COMPOSE := docker compose
DOCKER := docker
FIRMWARE_IMAGE := toy-factory-builder:local
UF2 := build/zephyr/zephyr.uf2
PIO_UF2 := build-pio/zephyr/zephyr.uf2
PIO_DMA_UF2 := build-pio-dma/zephyr/zephyr.uf2
PL022_DMA_UF2 := build-pl022-dma/zephyr/zephyr.uf2
SERIAL_PORT_HELPER := ./scripts/find-serial-port.sh
STEPS ?= 1
INPUT ?= none
OUT ?= artifacts/screenshot.png
SEQUENCE ?= scripts/sequences/deterministic-smoke.json
FAIL_SCREENSHOT ?= artifacts/sequence-failure.png
PROFILE_TICKS ?= 2000
PROFILE_OUT ?= artifacts/physics-profile.json
SLEEP_PROFILE_OUT ?= artifacts/physics-sleep-profile.json
CHAIN_PROFILE_TICKS ?= 1000
CHAIN_LINKS ?= 4,6,8
CHAIN_PROFILE_OUT ?= artifacts/physics-chain-profile.json
RENDER_PROFILE_SAMPLES ?= 16
RENDER_PROFILE_OUT ?= artifacts/render-profile.json
DISPLAY_TRANSPORT ?= pio-dma
DISPLAY_HZ ?= 20000000
CORE1_CHALLENGE ?= 0x01234567
CORE1_FRAME ?= 37
RENDER_PROFILE_BUILD_DIR = build-render-profile-$(DISPLAY_TRANSPORT)-$(DISPLAY_HZ)
RENDER_PROFILE_UF2 = $(RENDER_PROFILE_BUILD_DIR)/zephyr/zephyr.uf2

.PHONY: help image setup build build-fast build-pio build-pio-dma build-pl022-dma \
	build-render-profile format check check-pio-dma check-pl022-dma check-render-profile \
	container-shell update update-fast update-pio update-pio-dma update-pl022-dma \
	bootloader console status game-stats \
	game-redraw core1-status core1-ping core1-raster core1-scene \
	display-sync display-checksum screenshot sim-pause sim-run sim-step sim-input \
	sim-reset sim-state sim-test \
	profile profile-ab profile-sleep profile-chain render-profile update-render-profile \
	flash monitor shell

##@ General

help: ## Show this list of targets
	@printf 'Toy Factory\n\n'
	@printf 'Usage:\n  make <target> [PORT=/dev/ttyACM0] [UF2_MOUNT=/path/to/RPI-RP2]\n'
	@printf '                    [STEPS=1] [INPUT=none] [OUT=artifacts/screenshot.png]\n'
	@printf '                    [SEQUENCE=path.json] [FAIL_SCREENSHOT=artifacts/failure.png]\n'
	@printf '                    [PROFILE_TICKS=2000] [PROFILE_OUT=artifacts/physics-profile.json]\n'
	@printf '                    [SLEEP_PROFILE_OUT=artifacts/physics-sleep-profile.json]\n'
	@printf '                    [CHAIN_PROFILE_TICKS=1000] [CHAIN_LINKS=4,6,8]\n'
	@printf '                    [CHAIN_PROFILE_OUT=artifacts/physics-chain-profile.json]\n'
	@printf '                    [RENDER_PROFILE_SAMPLES=16] [RENDER_PROFILE_OUT=artifacts/render-profile.json]\n'
	@printf '                    [DISPLAY_TRANSPORT=pio-dma] [DISPLAY_HZ=20000000]\n'
	@awk 'BEGIN { FS = ":.*## " } \
		/^##@ / { printf "\n%s:\n", substr($$0, 5); next } \
		/^[a-zA-Z0-9_-]+:.*## / { printf "  %-24s %s\n", $$1, $$2 }' \
		$(MAKEFILE_LIST)

##@ Build and development

image: ## Build or refresh the Docker builder image
	$(COMPOSE) build firmware

setup: ## Refresh the pinned Zephyr dependencies
	$(COMPOSE) run --rm firmware ./scripts/container/setup.sh

build: ## Build the firmware in Docker
	$(COMPOSE) run --rm firmware

build-fast: DISPLAY_TRANSPORT = pl022-dma
build-fast: DISPLAY_HZ = 62500000
build-fast: build-render-profile ## Build the recommended core-1/full-frame image

build-pio: ## Build the PIO SPI benchmark variant
	$(COMPOSE) run --rm firmware ./scripts/container/build.sh --variant pio

build-pio-dma: ## Build the PIO SPI plus DMA benchmark variant
	$(COMPOSE) run --rm firmware ./scripts/container/build.sh --variant pio-dma

build-pl022-dma: ## Build the hardware SPI0/PL022 plus DMA benchmark variant
	$(COMPOSE) run --rm firmware ./scripts/container/build.sh --variant pl022-dma

build-render-profile: ## Build DISPLAY_TRANSPORT=<default|pio|pio-dma|pl022-dma> at DISPLAY_HZ=<Hz>
	$(COMPOSE) run --rm firmware ./scripts/container/build.sh \
		--variant "$(DISPLAY_TRANSPORT)" --display-frequency "$(DISPLAY_HZ)"

format: ## Format application and native-test C source
	$(COMPOSE) run --rm firmware clang-format -i src/*.c src/*.h scripts/tests/*.c

check: ## Run checks and a pristine firmware build
	$(COMPOSE) run --rm firmware ./scripts/container/check.sh

check-pio-dma: ## Pristine-build the PIO SPI plus DMA benchmark
	$(COMPOSE) run --rm firmware ./scripts/container/build.sh --pristine --variant pio-dma

check-pl022-dma: ## Pristine-build the hardware SPI0/PL022 plus DMA benchmark
	$(COMPOSE) run --rm firmware ./scripts/container/build.sh --pristine --variant pl022-dma

check-render-profile: ## Pristine-build the selected display transport/frequency image
	$(COMPOSE) run --rm firmware ./scripts/container/build.sh --pristine \
		--variant "$(DISPLAY_TRANSPORT)" --display-frequency "$(DISPLAY_HZ)"

container-shell: ## Open a shell in the builder container
	$(COMPOSE) run --rm firmware bash

##@ Device

update: build ## Build, enter the ROM bootloader, and flash firmware
	./scripts/update.sh "$(UF2_MOUNT)" "$(PORT)" "$(UF2)" "$(FIRMWARE_IMAGE)"

update-fast: DISPLAY_TRANSPORT = pl022-dma
update-fast: DISPLAY_HZ = 62500000
update-fast: update-render-profile ## Build and flash the recommended core-1/full-frame image

update-pio: build-pio ## Build and flash the PIO SPI benchmark
	./scripts/update.sh "$(UF2_MOUNT)" "$(PORT)" "$(PIO_UF2)" "$(FIRMWARE_IMAGE)"

update-pio-dma: build-pio-dma ## Build and flash the PIO SPI plus DMA benchmark
	./scripts/update.sh "$(UF2_MOUNT)" "$(PORT)" "$(PIO_DMA_UF2)" "$(FIRMWARE_IMAGE)"

update-pl022-dma: build-pl022-dma ## Build and flash the hardware SPI0/PL022 plus DMA benchmark
	./scripts/update.sh "$(UF2_MOUNT)" "$(PORT)" "$(PL022_DMA_UF2)" "$(FIRMWARE_IMAGE)"

update-render-profile: build-render-profile ## Build and flash selected display profile image
	./scripts/update.sh "$(UF2_MOUNT)" "$(PORT)" "$(RENDER_PROFILE_UF2)" "$(FIRMWARE_IMAGE)"

bootloader: image ## Reboot the running app into the RP2040 ROM bootloader
	./scripts/reboot-to-bootloader.sh "$(PORT)" "$(FIRMWARE_IMAGE)"

console: image ## Open the interactive device shell and log stream
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		echo "opening PicoSystem console on $$port (exit with Ctrl+])"; \
		exec $(DOCKER) run --rm --interactive --tty --user 0:0 \
			--device "$$port:$$port" "$(FIRMWARE_IMAGE)" \
			python3 -m serial.tools.miniterm --filter direct "$$port" 115200

status: image ## Print one device status snapshot and exit
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py "$$port" picosystem status

core1-status: image ## Print auxiliary-core protocol and stack health
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py --require-prefix "core1:" "$$port" \
				picosystem core1 status

core1-ping: image ## Round-trip CORE1_CHALLENGE=<number> through shared SRAM
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py --require-prefix "challenge=" "$$port" \
				picosystem core1 ping "$(CORE1_CHALLENGE)"

core1-raster: image ## Compare deterministic frame CORE1_FRAME=<index> on both cores (pause first)
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py --require-prefix \
				"CORE1_RASTER_VERIFY" "$$port" picosystem core1 raster "$(CORE1_FRAME)"

core1-scene: image ## Compare the current live scene on both cores (pause first)
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py --require-prefix \
				"CORE1_SCENE_VERIFY" "$$port" picosystem core1 scene

game-stats: image ## Print simulation, snapshot, renderer, and stack metrics
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py "$$port" picosystem game stats

game-redraw: image ## Queue an asynchronous full-screen redraw
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py "$$port" picosystem game redraw

display-sync: image ## Print LCD tearing-effect timing and synchronization metrics
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py "$$port" picosystem display sync

display-checksum: image ## Print the coherent presented-framebuffer checksum
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py --require-prefix "width=" "$$port" \
				picosystem display checksum

screenshot: image ## Capture the coherent presented framebuffer as OUT=<relative PNG path>
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/framebuffer-capture.py \
				--owner-uid "$$(id -u)" --owner-gid "$$(id -g)" \
				"$$port" "/workspace/app/$(OUT)"

sim-pause: image ## Pause simulation at a tick boundary and print exact state
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py --require-prefix "mode=" "$$port" \
				picosystem game pause

sim-run: image ## Resume exact real-time 120 Hz simulation scheduling
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py --require-prefix "mode=" "$$port" \
				picosystem game run

sim-reset: image ## Restore canonical tick-zero state while paused
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py --require-prefix "mode=" "$$port" \
				picosystem game reset

sim-step: image ## Advance a paused simulation by STEPS=<1-120> exact ticks
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py --require-prefix "mode=" "$$port" \
				picosystem game step "$(STEPS)"

sim-input: image ## Select INPUT=physical|none|up|down|left|right|<diagonal>
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py --require-prefix "mode=" "$$port" \
				picosystem game input "$(INPUT)"

sim-state: image ## Print exact simulation state and deterministic hash
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py --require-prefix "mode=" "$$port" \
				picosystem game state

sim-test: image ## Run SEQUENCE=<JSON> with deterministic hash/CRC assertions
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/sequence_runner.py \
				--failure-screenshot "/workspace/app/$(FAIL_SCREENSHOT)" \
				--owner-uid "$$(id -u)" --owner-gid "$$(id -g)" \
				"$$port" "/workspace/app/$(SEQUENCE)"

profile-ab: image ## Compare isolated grid/reference physics and save PROFILE_OUT=<JSON>
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/profile_compare.py \
				--ticks "$(PROFILE_TICKS)" \
				--owner-uid "$$(id -u)" --owner-gid "$$(id -g)" \
				"$$port" "/workspace/app/$(PROFILE_OUT)"

profile: profile-ab ## Alias for profile-ab

profile-sleep: image ## Profile the canonical world settling into sleep
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/profile_compare.py \
				--ticks "$(PROFILE_TICKS)" --neutral \
				--owner-uid "$$(id -u)" --owner-gid "$$(id -g)" \
				"$$port" "/workspace/app/$(SLEEP_PROFILE_OUT)"

profile-chain: image ## Profile CHAIN_LINKS=4,6,8 and save CHAIN_PROFILE_OUT=<JSON>
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/profile_compare.py \
				--ticks "$(CHAIN_PROFILE_TICKS)" --chain-links "$(CHAIN_LINKS)" \
				--owner-uid "$$(id -u)" --owner-gid "$$(id -g)" \
				"$$port" "/workspace/app/$(CHAIN_PROFILE_OUT)"

render-profile: image ## Profile dense display workloads and save RENDER_PROFILE_OUT=<JSON>
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/render_profile.py \
				--samples "$(RENDER_PROFILE_SAMPLES)" \
				--owner-uid "$$(id -u)" --owner-gid "$$(id -g)" \
				"$$port" "/workspace/app/$(RENDER_PROFILE_OUT)"

##@ Compatibility aliases

flash: update ## Alias for update

monitor: console ## Alias for console

shell: container-shell ## Alias for container-shell
