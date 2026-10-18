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
SCENE ?= hourglass
ACTION ?= primary
OUT ?= artifacts/screenshot.png
SEQUENCE ?= scripts/sequences/deterministic-smoke.json
FAIL_SCREENSHOT ?= artifacts/sequence-failure.png
PROFILE_TICKS ?= 1000
PROFILE_OUT ?= artifacts/physics-profile.json
GRANULAR_PROFILE_TICKS ?= 120
SLEEP_PROFILE_OUT ?= artifacts/physics-sleep-profile.json
CHAIN_PROFILE_TICKS ?= 500
CHAIN_LINKS ?= 4,6,8
CHAIN_PROFILE_OUT ?= artifacts/physics-chain-profile.json
RENDER_PROFILE_SAMPLES ?= 16
RENDER_PROFILE_OUT ?= artifacts/render-profile.json
HOST_SIMULATOR ?= build-host/toy-factory-sim
HOST_PLAYER ?= build-host-player/toy-factory-player
HOST_RESEARCH_PLAYER ?= artifacts/garden-research-player-build-v1/research-player
HOST_OUT ?= artifacts/host-screenshot.png
HOST_GARDEN_PROFILE ?= build-host-profile/toy-factory-garden-profile
HOST_GARDEN_EVALUATOR ?= build-host/toy-factory-garden-eval
HOST_GARDEN_TRAINER ?= build-host/toy-factory-garden-train
GARDEN_PROFILE_REPETITIONS ?= 32
GARDEN_PROFILE_OUT ?= artifacts/garden-host-profile.json
GARDEN_EVAL_TRIALS ?= 8
GARDEN_EVAL_TICKS ?= 7680
GARDEN_EVAL_SEED ?= 0x6576616c
GARDEN_EVAL_OUT ?= artifacts/garden-evaluation.json
GARDEN_EVAL_RAINFED ?= 0
GARDEN_EVAL_MODEL ?=
GARDEN_EVAL_CLIMATE ?= steady
GARDEN_EXPERIMENT_OUT ?= artifacts/garden-experiment
GARDEN_EXPERIMENT_ARGS ?=
GARDEN_GALLERY_BUNDLE ?= artifacts/garden-experiment
GARDEN_GALLERY_OUT ?= artifacts/garden-gallery
GARDEN_GALLERY_ARGS ?=
GARDEN_LANDING_OUT ?= artifacts/garden-landing-evaluation
GARDEN_LANDING_ARGS ?=
GARDEN_LANDING_TRAIN_OUT ?= artifacts/garden-landing-training-v1
GARDEN_LANDING_TRAIN_ARGS ?=
GARDEN_LANDING_VALIDATE_OUT ?= artifacts/garden-landing-validation-v1
GARDEN_LANDING_VALIDATE_ARGS ?=
GARDEN_LANDING_SIGNALS_OUT ?= artifacts/garden-landing-signals-v1
GARDEN_LANDING_SIGNALS_ARGS ?=
GARDEN_LANDING_DECISIONS_OUT ?= artifacts/garden-landing-decisions-v1
GARDEN_LANDING_DECISIONS_ARGS ?=
GARDEN_LANDING_CONTROLS_OUT ?= artifacts/garden-landing-controls-v1
GARDEN_LANDING_CONTROLS_ARGS ?=
GARDEN_LANDING_MULTISEED_OUT ?= artifacts/garden-landing-multiseed-v1
GARDEN_LANDING_MULTISEED_ARGS ?=
GARDEN_LANDING_RENEWAL_OUT ?= artifacts/garden-landing-renewal-audit-v1
GARDEN_LANDING_RENEWAL_ARGS ?=
GARDEN_LANDING_RECRUITMENT_OUT ?= artifacts/garden-landing-recruitment-v1
GARDEN_LANDING_RECRUITMENT_ARGS ?=
GARDEN_LANDING_REACH_OUT ?= artifacts/garden-landing-reach-v1
GARDEN_LANDING_REACH_ARGS ?=
GARDEN_LANDING_RANGE_OUT ?= artifacts/garden-landing-range-v1
GARDEN_LANDING_RANGE_ARGS ?=
GARDEN_LANDING_ESTABLISHMENT_OUT ?= artifacts/garden-landing-establishment.json.gz
GARDEN_LANDING_WATER_OUT ?= artifacts/garden-landing-water-v1
GARDEN_LANDING_WATER_ARGS ?=
GARDEN_LANDING_STALLS_OUT ?= artifacts/garden-landing-stalls.json.gz
GARDEN_LANDING_ARBITRATION_OUT ?= artifacts/garden-landing-arbitration-v1
GARDEN_LANDING_TURNOVER_OUT ?= artifacts/garden-landing-turnover.json.gz
GARDEN_LANDING_ADULT_OUT ?= artifacts/garden-landing-adult-resources-v1
GARDEN_LANDING_GROWTH_OUT ?= artifacts/garden-landing-growth-v1
GARDEN_LANDING_SPECIES_OUT ?= artifacts/garden-landing-species.json.gz
GARDEN_LANDING_FOUNDERS_OUT ?= artifacts/garden-landing-founders-v1
GARDEN_LANDING_BUDGET_OUT ?= artifacts/garden-landing-budget-v1
GARDEN_LANDING_GERMINATION_OUT ?= artifacts/garden-landing-budget-germination.json.gz
GARDEN_LANDING_BUDGET_REACH_OUT ?= artifacts/garden-landing-budget-reach-v1
GARDEN_LANDING_PLACEMENT_OUT ?= artifacts/garden-landing-placement-v1
GARDEN_LANDING_PLACEMENT_TURNOVER_OUT ?= artifacts/garden-landing-placement-turnover.json.gz
GARDEN_LANDING_VACANCY_OUT ?= artifacts/garden-landing-vacancy-v1
GARDEN_LANDING_RECOVERY_OUT ?= artifacts/garden-landing-recovery-gates-v1
GARDEN_LANDING_BANK_ACCESS_OUT ?= artifacts/garden-landing-bank-access-v1.json.gz
GARDEN_LANDING_ORDER_OUT ?= artifacts/garden-landing-order-v1
GARDEN_LANDING_ORDER_REGRESSIONS_OUT ?= artifacts/garden-landing-order-regressions.json.gz
GARDEN_LANDING_LATE_OUT ?= artifacts/garden-landing-late-v1
GARDEN_LANDING_ROOT_CHOICE_OUT ?= artifacts/garden-landing-root-choice-v1
GARDEN_LANDING_ROOT_ENERGY_OUT ?= artifacts/garden-landing-root-energy-v1
GARDEN_LANDING_ENERGY_AUDIT_OUT ?= artifacts/garden-landing-energy-audit-v1
GARDEN_LANDING_AFTERNOON_OUT ?= artifacts/garden-landing-afternoon-v1
GARDEN_LANDING_CONTINUOUS_ENERGY_OUT ?= artifacts/garden-landing-continuous-energy-v1
GARDEN_LANDING_LIGHT_AUDIT_OUT ?= artifacts/garden-landing-light-audit-v1
GARDEN_LANDING_DAYLIGHT_OUT ?= artifacts/garden-landing-daylight-v1
GARDEN_LANDING_DAWN_OUT ?= artifacts/garden-landing-dawn-v1
GARDEN_LANDING_POPULATION_OUT ?= artifacts/garden-landing-population-v1
GARDEN_LANDING_POPULATION_AUDIT_OUT ?= artifacts/garden-landing-population-audit-v1
GARDEN_LANDING_UPTAKE_OUT ?= artifacts/garden-landing-uptake-v1
GARDEN_LANDING_DIRECTIONS_OUT ?= artifacts/garden-landing-directions-v1
GARDEN_LANDING_ROOT_DIRECTION_OUT ?= artifacts/garden-landing-root-direction-v1
GARDEN_LANDING_ROOT_DIRECTION_AUDIT_OUT ?= artifacts/garden-landing-root-direction-audit-v1.json.gz
GARDEN_LANDING_ROOT_ALLOCATION_OUT ?= artifacts/garden-landing-root-allocation-v1
GARDEN_LANDING_ROOT_ALLOCATION_AUDIT_OUT ?= artifacts/garden-landing-root-allocation-audit-v1.json.gz
GARDEN_LANDING_SEED_SPENDING_AUDIT_OUT ?= artifacts/garden-landing-seed-spending-audit-v1.json.gz
GARDEN_LANDING_DRYDOWN_OUT ?= artifacts/garden-landing-drydown-v1
GARDEN_LANDING_SOIL_AUDIT_OUT ?= artifacts/garden-landing-soil-audit-v1.json.gz
GARDEN_LANDING_ROOT_REACHABILITY_OUT ?= artifacts/garden-landing-root-reachability-v1.json.gz
GARDEN_LANDING_WICKING_OUT ?= artifacts/garden-landing-wicking-v1
GARDEN_LANDING_WICKING_RESULTS ?= artifacts/garden-landing-wicking-v1.json.gz
GARDEN_LANDING_UPTAKE_LIMIT_OUT ?= artifacts/garden-landing-uptake-limit-v1
GARDEN_LANDING_UPTAKE_LIMIT_RESULTS ?= artifacts/garden-landing-uptake-limit-v1.json.gz
GARDEN_LANDING_RENEWAL_GATES_OUT ?= artifacts/garden-landing-renewal-gates-v1
GARDEN_LANDING_DISPERSAL_TIMING_OUT ?= artifacts/garden-landing-dispersal-timing-v1.json.gz
GARDEN_LANDING_LATE_DISPERSAL_OUT ?= artifacts/garden-landing-late-dispersal-v1
GARDEN_LANDING_LATE_DISPERSAL_RESULTS ?= artifacts/garden-landing-late-dispersal-v1.json.gz
GARDEN_LANDING_DISPERSAL_ENERGY_AUDIT_OUT ?= artifacts/garden-landing-dispersal-energy-audit-v1.json.gz
GARDEN_LANDING_ENERGY_HISTORY_OUT ?= artifacts/garden-landing-energy-history-v1.json.gz
GARDEN_LANDING_WINTER_LIGHT_OUT ?= artifacts/garden-landing-winter-light-v1
GARDEN_LANDING_WINTER_LIGHT_RESULTS ?= artifacts/garden-landing-winter-light-audited-v1.json.gz
GARDEN_LANDING_PLACEMENT_INFORMATION_OUT ?= artifacts/garden-landing-placement-information-final-v1.json.gz
GARDEN_LANDING_VACANCY_SEQUENCE_OUT ?= artifacts/garden-landing-vacancy-sequence-v1.json.gz
GARDEN_LANDING_FOLLOWUP_OUT ?= artifacts/garden-landing-followup-v1
GARDEN_LANDING_FOLLOWUP_RESULTS ?= artifacts/garden-landing-followup-results-v1.json.gz
GARDEN_LANDING_REPRODUCTIVE_ACCESS_OUT ?= artifacts/garden-landing-reproductive-access-v1.json.gz
GARDEN_LANDING_DISTURBANCE_OUT ?= artifacts/garden-landing-disturbance-v1
GARDEN_LANDING_DISTURBANCE_CAPTURE ?= artifacts/garden-landing-disturbance-capture-v1.json.gz
GARDEN_LANDING_DISTURBANCE_AUDIT ?= artifacts/garden-landing-disturbance-audit-v1.json.gz
GARDEN_LANDING_SECOND_OPENING_OUT ?= artifacts/garden-landing-second-opening-v1
GARDEN_LANDING_SECOND_OPENING_CAPTURE ?= artifacts/garden-landing-second-opening-capture-v1.json.gz
GARDEN_LANDING_SECOND_OPENING_AUDIT ?= artifacts/garden-landing-second-opening-audit-v1.json.gz
GARDEN_LANDING_OPENING_OPPORTUNITIES_OUT ?= artifacts/garden-landing-opening-opportunities-v1.json.gz
GARDEN_LANDING_SEED_REPLACEMENT_OUT ?= artifacts/garden-landing-seed-replacement-v1
GARDEN_LANDING_SEED_REPLACEMENT_CAPTURE ?= artifacts/garden-landing-seed-replacement-v1.json.gz
GARDEN_LANDING_SEED_COMPETITION_OUT ?= artifacts/garden-landing-seed-competition-v1.json.gz
GARDEN_LANDING_PATCH_SWEEP_OUT ?= artifacts/garden-landing-patch-sweep-v1
GARDEN_LANDING_PATCH_SWEEP_CAPTURE ?= artifacts/garden-landing-patch-sweep-v1.json.gz
GARDEN_LANDING_PATCH_CONFIRMATION_OUT ?= artifacts/garden-landing-patch-confirmation-v1
GARDEN_LANDING_PATCH_CONFIRMATION_CAPTURE ?= artifacts/garden-landing-patch-confirmation-v1.json.gz
GARDEN_LANDING_PATCH_FOLLOWUP_OUT ?= artifacts/garden-landing-patch-followup-v1
GARDEN_LANDING_PATCH_FOLLOWUP_CAPTURE ?= artifacts/garden-landing-patch-followup-v1.json.gz
GARDEN_LANDING_PATCH_RENEWAL_OUT ?= artifacts/garden-landing-patch-renewal-v1.json.gz
GARDEN_LANDING_SEED_CURSOR_OUT ?= artifacts/garden-landing-seed-cursor-v1
GARDEN_LANDING_SEED_CURSOR_CAPTURE ?= artifacts/garden-landing-seed-cursor-v1.json.gz
GARDEN_LANDING_COMPETITIVE_RENEWAL_OUT ?= artifacts/garden-landing-competitive-renewal-v1
GARDEN_LANDING_COMPETITIVE_RENEWAL_CAPTURE ?= artifacts/garden-landing-competitive-renewal-v1.json.gz
GARDEN_LANDING_RECRUIT_SEEDS_OUT ?= artifacts/garden-landing-recruit-seeds-v1.json.gz
GARDEN_LANDING_SEED_HANDOFF_OUT ?= artifacts/garden-landing-seed-handoff-v1
GARDEN_LANDING_SEED_HANDOFF_RESULTS ?= artifacts/garden-landing-seed-handoff-v1.json.gz
GARDEN_LANDING_NONBUYER_OUT ?= artifacts/garden-landing-nonbuyer-v1
GARDEN_LANDING_NONBUYER_RESULTS ?= artifacts/garden-landing-nonbuyer-v1.json.gz
GARDEN_LANDING_SEED_WAIT_OUT ?= artifacts/garden-landing-seed-wait-v1
GARDEN_LANDING_SEED_WAIT_CAPTURE ?= artifacts/garden-landing-seed-wait-v1.json.gz
GARDEN_LANDING_PATCH_RECURRING_OUT ?= artifacts/garden-landing-patch-recurring-v1
GARDEN_LANDING_PATCH_RECURRING_CAPTURE ?= artifacts/garden-landing-patch-recurring-v1.json.gz
GARDEN_LANDING_RECURRING_FOLLOWUP_OUT ?= artifacts/garden-landing-recurring-followup-v1
GARDEN_LANDING_RECURRING_FOLLOWUP_CAPTURE ?= artifacts/garden-landing-recurring-followup-v1.json.gz
GARDEN_LANDING_RECURRING_FRESH_OUT ?= artifacts/garden-landing-recurring-fresh-v1
GARDEN_LANDING_RECURRING_FRESH_CAPTURE ?= artifacts/garden-landing-recurring-fresh-v1.json.gz
GARDEN_LANDING_DAWN_AUDIT_OUT ?= artifacts/garden-landing-dawn-audit-v1
GARDEN_LANDING_ARBITRATION_ARGS ?=
GARDEN_AUDIT_BUNDLE ?= artifacts/garden-experiment
GARDEN_AUDIT_OUT ?= artifacts/garden-establishment
GARDEN_AUDIT_ARGS ?=
GARDEN_SEASONS_OUT ?= artifacts/garden-seasons
GARDEN_SEASONS_ARGS ?= --days 64 --trials 2 --jobs 2
GARDEN_RECRUITMENT_PANEL ?= artifacts/garden-seasons-fresh-128/results.json
GARDEN_RECRUITMENT_OUT ?= artifacts/garden-season-recruitment
GARDEN_RECRUITMENT_JOBS ?= 4
GARDEN_TRAIN_GENERATIONS ?= 8
GARDEN_TRAIN_POPULATION ?= 16
GARDEN_TRAIN_TRIALS ?= 2
GARDEN_TRAIN_TICKS ?= 7680
GARDEN_TRAIN_MUTATIONS ?= 32
GARDEN_TRAIN_SEED ?= 0x74726169
GARDEN_TRAIN_INPUT ?=
GARDEN_TRAIN_OUT ?= artifacts/garden-training.json
GARDEN_MODEL_OUT ?= artifacts/garden-champion.tgm
GARDEN_MODEL_C_OUT ?= artifacts/garden-champion.c
DISPLAY_TRANSPORT ?= pio-dma
DISPLAY_HZ ?= 20000000
CORE1_CHALLENGE ?= 0x01234567
CORE1_FRAME ?= 37
RENDER_PROFILE_BUILD_DIR = build-render-profile-$(DISPLAY_TRANSPORT)-$(DISPLAY_HZ)
RENDER_PROFILE_UF2 = $(RENDER_PROFILE_BUILD_DIR)/zephyr/zephyr.uf2

.PHONY: host-audit-landing-soil host-trace-landing-drydown host-audit-landing-seed-spending host-audit-landing-root-allocation host-probe-landing-root-allocation host-audit-landing-root-direction host-probe-landing-root-direction host-probe-landing-directions host-probe-landing-uptake host-audit-landing-population host-probe-landing-population host-probe-landing-dawn host-probe-landing-daylight host-audit-landing-dawn help image setup build build-fast build-pio build-pio-dma build-pl022-dma \
	build-render-profile format check check-source check-pio-dma check-pl022-dma check-render-profile \
	host-build host-check host-research-check host-run host-cli host-profile-build host-profile-garden \
	host-evaluate-garden host-train-garden host-experiment-garden host-gallery-garden host-audit-garden \
	host-seasons-garden host-recruitment-garden host-landing-garden host-evaluate-landing-garden \
	host-train-landing-garden host-validate-landing-garden host-probe-landing-garden \
	host-trace-landing-garden host-train-landing-controls host-train-landing-multiseed host-audit-landing-renewal \
	host-trace-landing-recruitment host-trace-landing-reach host-screen-landing-range host-audit-landing-establishment host-screen-landing-water host-audit-landing-stalls host-screen-landing-arbitration host-audit-landing-turnover host-trace-landing-adults host-screen-landing-growth host-audit-landing-species \
	host-trace-landing-founders \
	host-screen-landing-budget host-audit-landing-germination host-trace-landing-budget-reach host-screen-landing-placement host-audit-placement-turnover host-screen-landing-vacancy host-trace-landing-recovery host-audit-landing-bank-access host-screen-landing-order host-audit-landing-order-regressions host-trace-landing-late host-probe-landing-root-choice host-probe-landing-root-energy host-audit-landing-energy host-probe-landing-afternoon host-probe-landing-continuous-energy host-audit-landing-light \
	host-image host-player-build host-player-check host-play \
	host-research-player-build host-research-player-check host-play-research \
	container-shell update update-fast update-pio update-pio-dma update-pl022-dma \
	bootloader console status game-stats \
	game-redraw core1-status core1-ping core1-raster core1-scene \
	display-sync display-checksum screenshot sim-pause sim-run sim-step sim-input \
	sim-reset sim-scene sim-action sim-flip sim-state sim-test \
	profile profile-ab profile-sleep profile-chain render-profile update-render-profile \
	profile-granular \
	flash monitor shell

##@ General

help: ## Show this list of targets
	@printf 'Toy Factory\n\n'
	@printf 'Usage:\n  make <target> [PORT=/dev/ttyACM0] [UF2_MOUNT=/path/to/RPI-RP2]\n'
	@printf '                    [STEPS=1] [INPUT=none] [OUT=artifacts/screenshot.png]\n'
	@printf '                    [SCENE=clockwork|hourglass|marble-machine|garden]\n'
	@printf '                    [ACTION=primary|use-tool|cycle-tool]\n'
	@printf '                    [SEQUENCE=path.json] [FAIL_SCREENSHOT=artifacts/failure.png]\n'
	@printf '                    [PROFILE_TICKS=1000] [PROFILE_OUT=artifacts/physics-profile.json]\n'
	@printf '                    [GRANULAR_PROFILE_TICKS=120]\n'
	@printf '                    [SLEEP_PROFILE_OUT=artifacts/physics-sleep-profile.json]\n'
	@printf '                    [CHAIN_PROFILE_TICKS=500] [CHAIN_LINKS=4,6,8]\n'
	@printf '                    [CHAIN_PROFILE_OUT=artifacts/physics-chain-profile.json]\n'
	@printf '                    [RENDER_PROFILE_SAMPLES=16] [RENDER_PROFILE_OUT=artifacts/render-profile.json]\n'
	@printf '                    [DISPLAY_TRANSPORT=pio-dma] [DISPLAY_HZ=20000000]\n'
	@printf '                    [HOST_OUT=artifacts/host-screenshot.png] [ARGS="..."]\n'
	@printf '                    [GARDEN_PROFILE_REPETITIONS=32]\n'
	@printf '                    [GARDEN_PROFILE_OUT=artifacts/garden-host-profile.json]\n'
	@printf '                    [GARDEN_EVAL_TRIALS=8] [GARDEN_EVAL_TICKS=7680]\n'
	@printf '                    [GARDEN_EVAL_SEED=0x6576616c]\n'
	@printf '                    [GARDEN_EVAL_CLIMATE=steady|winter|drought|seasonal]\n'
	@printf '                    [GARDEN_EVAL_RAINFED=1] (seeded rain, no gardener)\n'
	@printf '                    [GARDEN_EXPERIMENT_OUT=artifacts/new-run] [GARDEN_EXPERIMENT_ARGS="--cycles 8"]\n'
	@printf '                    [GARDEN_EVAL_OUT=artifacts/garden-evaluation.json] [GARDEN_EVAL_MODEL=path.tgm]\n'
	@printf '                    [GARDEN_TRAIN_GENERATIONS=8] [GARDEN_TRAIN_POPULATION=16]\n'
	@printf '                    [GARDEN_TRAIN_TRIALS=2] [GARDEN_TRAIN_TICKS=7680]\n'
	@printf '                    [GARDEN_TRAIN_MUTATIONS=32] [GARDEN_TRAIN_SEED=0x74726169]\n'
	@printf '                    [GARDEN_TRAIN_INPUT=path.tgm] [GARDEN_MODEL_OUT=path.tgm]\n'
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

format: ## Format application, simulator, and native-test C source
	$(COMPOSE) run --rm firmware clang-format -i src/*.c src/*.h sim/*.c sim/*.h scripts/tests/*.c

check: ## Run checks and a pristine firmware build
	$(COMPOSE) run --rm firmware ./scripts/container/check.sh

check-source: ## Run formatting, standalone tests, and CI tooling checks without the long replay suite
	$(COMPOSE) run --rm -T firmware ./scripts/container/check.sh --source-only

check-pio-dma: ## Pristine-build the PIO SPI plus DMA benchmark
	$(COMPOSE) run --rm firmware ./scripts/container/build.sh --pristine --variant pio-dma

check-pl022-dma: ## Pristine-build the hardware SPI0/PL022 plus DMA benchmark
	$(COMPOSE) run --rm firmware ./scripts/container/build.sh --pristine --variant pl022-dma

check-render-profile: ## Pristine-build the selected display transport/frequency image
	$(COMPOSE) run --rm firmware ./scripts/container/build.sh --pristine \
		--variant "$(DISPLAY_TRANSPORT)" --display-frequency "$(DISPLAY_HZ)"

host-build: ## Build the deterministic native simulator in Docker
	$(COMPOSE) run --rm firmware ./scripts/container/host-build.sh

host-check: ## Pristine-build and test the native simulator against device goldens
	$(COMPOSE) run --rm firmware ./scripts/container/host-build.sh --pristine
	$(COMPOSE) run --rm firmware ctest --test-dir build-host --output-on-failure

host-research-check: ## Build and test opt-in Garden research code separately from device defaults
	$(COMPOSE) run --rm -T firmware bash ./scripts/container/host-research-check.sh

host-run: host-build ## Run SEQUENCE locally and write its final PNG to HOST_OUT
	$(COMPOSE) run --rm firmware python3 sim/run_sequence.py \
		--binary "$(HOST_SIMULATOR)" --sequence "$(SEQUENCE)" --output "$(HOST_OUT)"

host-cli: host-build ## Run the native simulator directly with ARGS="..."
	$(COMPOSE) run --rm firmware "$(HOST_SIMULATOR)" $(ARGS)

host-profile-build: ## Build the optimized Garden profiler in Docker
	$(COMPOSE) run --rm firmware ./scripts/container/host-profile-build.sh

host-profile-garden: host-profile-build ## Profile initial, growing, and established Garden checkpoints
	@mkdir -p "$(dir $(GARDEN_PROFILE_OUT))"
	@$(COMPOSE) run --rm firmware "$(HOST_GARDEN_PROFILE)" \
		--repetitions "$(GARDEN_PROFILE_REPETITIONS)" > "$(GARDEN_PROFILE_OUT)"
	@$(COMPOSE) run --rm firmware python3 -m json.tool "$(GARDEN_PROFILE_OUT)"

host-evaluate-garden: host-build ## Compare Garden policies over deterministic scenario batches
	@mkdir -p "$(dir $(GARDEN_EVAL_OUT))"
	@$(COMPOSE) run --rm firmware "$(HOST_GARDEN_EVALUATOR)" \
		--trials "$(GARDEN_EVAL_TRIALS)" --ticks "$(GARDEN_EVAL_TICKS)" \
		--seed "$(GARDEN_EVAL_SEED)" \
		$(if $(strip $(GARDEN_EVAL_MODEL)),--model "$(GARDEN_EVAL_MODEL)",) \
		$(if $(filter 1,$(GARDEN_EVAL_RAINFED)),--rainfed,) \
		$(if $(filter-out steady,$(GARDEN_EVAL_CLIMATE)),--climate "$(GARDEN_EVAL_CLIMATE)",) \
		> "$(GARDEN_EVAL_OUT)"
	@$(COMPOSE) run --rm firmware python3 -m json.tool "$(GARDEN_EVAL_OUT)" >/dev/null
	@$(COMPOSE) run --rm firmware python3 sim/summarize_garden_experiment.py \
		"$(GARDEN_EVAL_OUT)"

host-seasons-garden: host-build ## Compare steady, winter, drought, and combined climates (new GARDEN_SEASONS_OUT)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_seasons.py \
		--out "$(GARDEN_SEASONS_OUT)" $(GARDEN_SEASONS_ARGS)

host-recruitment-garden: host-build ## Audit exact seed checks against the retained fresh-128 seasonal panel
	$(COMPOSE) run --rm -T firmware python3 sim/garden_season_recruitment.py \
		--panel "$(GARDEN_RECRUITMENT_PANEL)" --out "$(GARDEN_RECRUITMENT_OUT)" \
		--jobs "$(GARDEN_RECRUITMENT_JOBS)"

host-experiment-garden: host-build ## Collect matched rain-fed trials, report, and verified diagnostic replays
	$(COMPOSE) run --rm firmware python3 sim/garden_experiments.py \
		--output "$(GARDEN_EXPERIMENT_OUT)" $(GARDEN_EXPERIMENT_ARGS)

host-gallery-garden: host-build ## Capture a fixed visual-review panel from a completed experiment bundle
	$(COMPOSE) run --rm firmware python3 sim/garden_gallery.py \
		--bundle "$(GARDEN_GALLERY_BUNDLE)" --output "$(GARDEN_GALLERY_OUT)" $(GARDEN_GALLERY_ARGS)

host-landing-garden: host-build ## Inspect/import/mutate/ablate/replay experimental landing models (ARGS="--help")
	$(COMPOSE) run --rm -T firmware build-host/toy-factory-garden-landing $(if $(strip $(ARGS)),$(ARGS),--help)

host-evaluate-landing-garden: host-build ## Save matched TGL2 outcomes/screenshots (GARDEN_LANDING_ARGS="--model label=path.tgl")
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_evaluate.py \
		--out "$(GARDEN_LANDING_OUT)" $(GARDEN_LANDING_ARGS)

host-train-landing-garden: host-build ## Run the fixed 63-candidate renewal pilot (requires frozen initial model; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_training.py \
		--out "$(GARDEN_LANDING_TRAIN_OUT)" $(GARDEN_LANDING_TRAIN_ARGS)

host-validate-landing-garden: host-build ## Replay 19 frozen controller variants on 16 fixed conditions (no training; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_validation.py \
		--out "$(GARDEN_LANDING_VALIDATE_OUT)" $(GARDEN_LANDING_VALIDATE_ARGS)

host-probe-landing-garden: host-build ## Probe live versus fixed occupancy/resource inputs (480 frozen worlds; no training)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_signals.py \
		--out "$(GARDEN_LANDING_SIGNALS_OUT)" $(GARDEN_LANDING_SIGNALS_ARGS)

host-trace-landing-garden: host-build ## Compare same-state neural proposals in 48 unchanged worlds (no training; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_decisions.py \
		--out "$(GARDEN_LANDING_DECISIONS_OUT)" $(GARDEN_LANDING_DECISIONS_ARGS)

host-train-landing-controls: host-build ## Run 42 paired live/fixed-input candidates and fixed evaluation (fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_controls.py \
		--out "$(GARDEN_LANDING_CONTROLS_OUT)" $(GARDEN_LANDING_CONTROLS_ARGS)

host-train-landing-multiseed: host-build ## Train 42 candidates on five seeds; compare frozen one-seed finalists (fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_multiseed.py \
		--out "$(GARDEN_LANDING_MULTISEED_OUT)" $(GARDEN_LANDING_MULTISEED_ARGS)

host-audit-landing-renewal: image ## Diagnose saved landing-training seed/renewal ledgers (no native runs; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_renewal_audit.py \
		--out "$(GARDEN_LANDING_RENEWAL_OUT)" $(GARDEN_LANDING_RENEWAL_ARGS)

host-trace-landing-recruitment: host-build ## Trace matched seed blockers and first-day budgets (host-only; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_recruitment.py \
		--out "$(GARDEN_LANDING_RECRUITMENT_OUT)" $(GARDEN_LANDING_RECRUITMENT_ARGS)

host-trace-landing-reach: host-build ## Diagnose parent-specific seed reach in twelve unchanged worlds (fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_reach.py \
		--out "$(GARDEN_LANDING_REACH_OUT)" $(GARDEN_LANDING_REACH_ARGS)

host-screen-landing-range: image ## Build isolated narrow/wide hosts and compare frozen models (no promotion; fresh output)
	$(COMPOSE) run --rm -T firmware bash scripts/container/host-landing-range-build.sh
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_range.py \
		--narrow-build artifacts/build-host-landing-range/narrow \
		--wide-build artifacts/build-host-landing-range/wide \
		--out "$(GARDEN_LANDING_RANGE_OUT)" $(GARDEN_LANDING_RANGE_ARGS)

host-audit-landing-establishment: image ## Diagnose saved first-day resource allocation (no simulation; fresh output file)
	@mkdir -p "$(dir $(GARDEN_LANDING_ESTABLISHMENT_OUT))"
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_establishment.py \
		--out "$(GARDEN_LANDING_ESTABLISHMENT_OUT)"

host-screen-landing-water: host-build ## Compare first-day water reserve on frozen models (host-only; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_water.py \
		--out "$(GARDEN_LANDING_WATER_OUT)" $(GARDEN_LANDING_WATER_ARGS)

host-audit-landing-stalls: image ## Diagnose saved water-refusal streaks and observed continuations (no simulation)
	@mkdir -p "$(dir $(GARDEN_LANDING_STALLS_OUT))"
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_stalls.py \
		--out "$(GARDEN_LANDING_STALLS_OUT)"

host-screen-landing-arbitration: host-build ## Compare water-eligible arbitration on frozen models (host-only; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_arbitration.py \
		--out "$(GARDEN_LANDING_ARBITRATION_OUT)" $(GARDEN_LANDING_ARBITRATION_ARGS)

host-audit-landing-turnover: image ## Diagnose saved recruitment and established-descendant gaps (no simulation)
	@mkdir -p "$(dir $(GARDEN_LANDING_TURNOVER_OUT))"
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_turnover.py \
		--out "$(GARDEN_LANDING_TURNOVER_OUT)"

host-trace-landing-adults: host-build ## Trace the frozen seasonal pair's adult budgets and seed blockers (read-only; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_adults.py \
		--out "$(GARDEN_LANDING_ADULT_OUT)"

host-screen-landing-growth: host-build ## Compare a host-only 32-node growth cap with frozen controllers (fresh output; no training)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_growth.py \
		--out "$(GARDEN_LANDING_GROWTH_OUT)"

host-audit-landing-species: image ## Audit species, survival and allocation in saved construction runs (no simulation)
	@mkdir -p "$(dir $(GARDEN_LANDING_SPECIES_OUT))"
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_species.py \
		--out "$(GARDEN_LANDING_SPECIES_OUT)"

host-trace-landing-founders: host-build ## Trace frozen founders' construction and reproduction gates (read-only; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_founders.py \
		--out "$(GARDEN_LANDING_FOUNDERS_OUT)"

host-screen-landing-budget: host-build ## Compare reserved shoot space at 32 nodes with frozen controls (host-only; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_budget.py \
		--out "$(GARDEN_LANDING_BUDGET_OUT)"

host-audit-landing-germination: image ## Audit saved shoot-budget seed checks and final-period renewal (no simulation)
	@mkdir -p "$(dir $(GARDEN_LANDING_GERMINATION_OUT))"
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_germination.py \
		--out "$(GARDEN_LANDING_GERMINATION_OUT)"

host-trace-landing-budget-reach: host-build ## Trace parent-reachable seed alternatives in frozen budget worlds (read-only; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_budget_reach.py \
		--out "$(GARDEN_LANDING_BUDGET_REACH_OUT)"

host-screen-landing-placement: host-build ## Compare spacing-aware seed placement within unchanged parent reach (host-only; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_placement.py \
		--out "$(GARDEN_LANDING_PLACEMENT_OUT)"

host-audit-placement-turnover: image ## Audit saved placement credit expiry, occupants and seed blockers (no simulation)
	@mkdir -p "$(dir $(GARDEN_LANDING_PLACEMENT_TURNOVER_OUT))"
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_placement_turnover.py \
		--out "$(GARDEN_LANDING_PLACEMENT_TURNOVER_OUT)"

host-screen-landing-vacancy: host-build ## Test one fixed vacancy and subsequent reproduction (host-only; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_vacancy.py \
		--out "$(GARDEN_LANDING_VACANCY_OUT)"

host-trace-landing-recovery: host-build ## Trace replacement reproduction and adult losses (read-only; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_recovery.py \
		--out "$(GARDEN_LANDING_RECOVERY_OUT)"

host-audit-landing-bank-access: image ## Audit saved seed-bank ownership and ordered access (no simulation; fresh output)
	@mkdir -p "$(dir $(GARDEN_LANDING_BANK_ACCESS_OUT))"
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_bank_access.py \
		--out "$(GARDEN_LANDING_BANK_ACCESS_OUT)"

host-screen-landing-order: host-build ## Compare post-day-158 reproduction order with frozen controls (host-only; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_order.py \
		--out "$(GARDEN_LANDING_ORDER_OUT)"

host-audit-landing-order-regressions: image ## Diagnose saved rotation regressions (no simulation; fresh output)
	@mkdir -p "$(dir $(GARDEN_LANDING_ORDER_REGRESSIONS_OUT))"
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_order_regressions.py \
		--out "$(GARDEN_LANDING_ORDER_REGRESSIONS_OUT)"

host-trace-landing-late: host-build ## Trace unchanged S35 late seedling budgets (four replays; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_late.py \
		--out "$(GARDEN_LANDING_LATE_OUT)"

host-probe-landing-root-choice: host-build ## Test one early root choice in five fixed cases (40 calls; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_root_choice.py \
		--out "$(GARDEN_LANDING_ROOT_CHOICE_OUT)"

host-probe-landing-root-energy: host-build ## Test first-day energy after the same root purchase (40 calls; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_root_energy.py \
		--out "$(GARDEN_LANDING_ROOT_ENERGY_OUT)"

host-audit-landing-energy: image ## Audit saved maintenance forecasts and successful growth (no simulation; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_energy_audit.py \
		--out "$(GARDEN_LANDING_ENERGY_AUDIT_OUT)"

host-audit-landing-light: image ## Audit saved daylight income and dawn budgets (no simulation; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_light_audit.py \
		--out "$(GARDEN_LANDING_LIGHT_AUDIT_OUT)"

host-probe-landing-daylight: host-build ## Test productive afternoon income credit (40 calls; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_daylight.py \
		--build /workspace/app/build-host --out "$(GARDEN_LANDING_DAYLIGHT_OUT)"

host-audit-landing-dawn: image ## Audit saved night/dawn funding and growth costs (no simulation; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_dawn_audit.py \
		--out "$(GARDEN_LANDING_DAWN_AUDIT_OUT)"

host-probe-landing-dawn: host-build ## Test an afternoon dawn-upkeep reserve (40 calls; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_dawn.py \
		--build /workspace/app/build-host --out "$(GARDEN_LANDING_DAWN_OUT)"

host-probe-landing-population: host-build ## Test all-offspring dawn protection across weather/order (32 calls; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_population.py \
		--build /workspace/app/build-host --out "$(GARDEN_LANDING_POPULATION_OUT)"

host-audit-landing-population: ## Audit saved regression receipts (no simulation; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_population_audit.py \
		--bundle "$(GARDEN_LANDING_POPULATION_OUT)" --out "$(GARDEN_LANDING_POPULATION_AUDIT_OUT)"

host-probe-landing-uptake: host-build ## Attribute light/water uptake with observer neutrality (8 calls; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_uptake.py \
		--build /workspace/app/build-host --out "$(GARDEN_LANDING_UPTAKE_OUT)"

host-probe-landing-directions: host-build ## Audit legal construction alternatives (8 passive calls; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_directions.py \
		--build /workspace/app/build-host --out "$(GARDEN_LANDING_DIRECTIONS_OUT)"

host-probe-landing-root-direction: host-build ## Compare affordable wetter root directions (16 calls; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_root_direction.py \
		--build /workspace/app/build-host --out "$(GARDEN_LANDING_ROOT_DIRECTION_OUT)"

host-probe-landing-root-allocation: host-build ## Test focal root priority with unchanged spending guards (16 calls; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_root_allocation.py \
		--build /workspace/app/build-host --out "$(GARDEN_LANDING_ROOT_ALLOCATION_OUT)"

host-audit-landing-root-allocation: ## Decompose saved population regressions (offline; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_root_allocation_audit.py \
		--bundle "$(GARDEN_LANDING_ROOT_ALLOCATION_OUT)" --out "$(GARDEN_LANDING_ROOT_ALLOCATION_AUDIT_OUT)"

host-audit-landing-seed-spending: ## Audit saved seed gates and water refills (offline; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_seed_spending_audit.py \
		--bundle "$(GARDEN_LANDING_ROOT_ALLOCATION_OUT)" --out "$(GARDEN_LANDING_SEED_SPENDING_AUDIT_OUT)"

host-trace-landing-drydown: ## Trace drying roots with the archived executable (16 calls; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_drydown.py \
		--bundle "$(GARDEN_LANDING_ROOT_ALLOCATION_OUT)" --out "$(GARDEN_LANDING_DRYDOWN_OUT)"

host-audit-landing-soil: ## Reconstruct saved soil flow and evaporation (offline; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_soil_audit.py \
		--bundle "$(GARDEN_LANDING_DRYDOWN_OUT)" --out "$(GARDEN_LANDING_SOIL_AUDIT_OUT)"

.PHONY: host-audit-landing-root-reachability
host-audit-landing-root-reachability: ## Audit saved root reach and construction limits (offline; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_root_reachability.py \
		--bundle "$(GARDEN_LANDING_ROOT_ALLOCATION_OUT)" --native "$(GARDEN_LANDING_DRYDOWN_OUT)/native" \
		--out "$(GARDEN_LANDING_ROOT_REACHABILITY_OUT)"

.PHONY: host-probe-landing-wicking host-audit-landing-wicking
host-probe-landing-wicking: host-build ## Capture late soil wicking vs ordinary worlds (24 calls; fresh output)
	$(COMPOSE) run --rm -T firmware bash scripts/container/host-wicking-build.sh
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_wicking.py --out "$(GARDEN_LANDING_WICKING_OUT)"

host-audit-landing-wicking: ## Reconcile saved wicking receipts (offline; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_wicking.py \
		--analyze "$(GARDEN_LANDING_WICKING_OUT)" --out "$(GARDEN_LANDING_WICKING_RESULTS)"

.PHONY: host-probe-landing-uptake-limit host-audit-landing-uptake-limit
host-probe-landing-uptake-limit: host-build ## Capture late uptake cap with/without wicking (48 calls; fresh output)
	$(COMPOSE) run --rm -T firmware bash scripts/container/host-wicking-build.sh
	$(COMPOSE) run --rm -T firmware bash scripts/container/host-uptake-limit-build.sh
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_uptake_limit.py --out "$(GARDEN_LANDING_UPTAKE_LIMIT_OUT)"

host-audit-landing-uptake-limit: ## Reconcile saved uptake cap trials (offline; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_uptake_limit.py \
		--analyze "$(GARDEN_LANDING_UPTAKE_LIMIT_OUT)" --out "$(GARDEN_LANDING_UPTAKE_LIMIT_RESULTS)"

.PHONY: host-audit-landing-renewal-gates
host-audit-landing-renewal-gates: ## Explain saved seed/reproduction bottlenecks (offline; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_renewal_gates.py \
		--bundle "$(GARDEN_LANDING_UPTAKE_LIMIT_OUT)" --out "$(GARDEN_LANDING_RENEWAL_GATES_OUT)"

.PHONY: host-audit-landing-dispersal-timing
host-audit-landing-dispersal-timing: ## Audit saved landing reach and crowding timing (offline; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_dispersal_timing.py \
		--out "$(GARDEN_LANDING_DISPERSAL_TIMING_OUT)"

.PHONY: host-probe-landing-late-dispersal host-audit-landing-late-dispersal
host-probe-landing-late-dispersal: image ## Test wider late dispersal on capped histories (48 calls; fresh output)
	$(COMPOSE) run --rm -T firmware bash scripts/container/host-late-dispersal-build.sh
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_late_dispersal.py --out "$(GARDEN_LANDING_LATE_DISPERSAL_OUT)"

host-audit-landing-late-dispersal: ## Reconcile saved wider dispersal trials (offline; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_late_dispersal.py \
		--analyze "$(GARDEN_LANDING_LATE_DISPERSAL_OUT)" --out "$(GARDEN_LANDING_LATE_DISPERSAL_RESULTS)"

.PHONY: host-audit-landing-dispersal-energy
host-audit-landing-dispersal-energy: ## Split saved energy regressions by cohort/exposure (offline; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_dispersal_energy_audit.py \
		--out "$(GARDEN_LANDING_DISPERSAL_ENERGY_AUDIT_OUT)"

.PHONY: host-audit-landing-energy-history
host-audit-landing-energy-history: ## Trace saved mature-plant energy income and spending (offline; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_energy_history.py \
		--bundle "$(GARDEN_LANDING_LATE_DISPERSAL_OUT)" --out "$(GARDEN_LANDING_ENERGY_HISTORY_OUT)"

.PHONY: host-trace-landing-winter-light host-audit-landing-winter-light
host-trace-landing-winter-light: ## Replay archived pair with passive winter-light observations (2 calls; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_winter_light_capture.py \
		--native "$(GARDEN_LANDING_LATE_DISPERSAL_OUT)" --out "$(GARDEN_LANDING_WINTER_LIGHT_OUT)"

host-audit-landing-winter-light: ## Explain saved winter shade and leaf income (offline; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_winter_light.py \
		--bundle "$(GARDEN_LANDING_WINTER_LIGHT_OUT)" --out "$(GARDEN_LANDING_WINTER_LIGHT_RESULTS)"

.PHONY: host-audit-landing-placement-information
host-audit-landing-placement-information: ## Audit saved seed-choice information and family renewal (offline; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_placement_information.py \
		--bundle "$(GARDEN_LANDING_LATE_DISPERSAL_OUT)" --out "$(GARDEN_LANDING_PLACEMENT_INFORMATION_OUT)"

.PHONY: host-audit-landing-vacancy-sequence
host-audit-landing-vacancy-sequence: ## Trace saved deaths, decomposition and replacement opportunities (offline; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_vacancy_sequence.py \
		--bundle "$(GARDEN_LANDING_LATE_DISPERSAL_OUT)" --out "$(GARDEN_LANDING_VACANCY_SEQUENCE_OUT)"

.PHONY: host-probe-landing-followup
host-probe-landing-followup: ## Follow the frozen 32-world panel to day 288 (68 native calls; fresh outputs)
	$(COMPOSE) run --rm -T firmware bash scripts/container/host-late-dispersal-build.sh
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_followup.py \
		--collect "$(GARDEN_LANDING_FOLLOWUP_OUT)" --out "$(GARDEN_LANDING_FOLLOWUP_RESULTS)" \
		--original "$(GARDEN_LANDING_LATE_DISPERSAL_OUT)"

.PHONY: host-audit-landing-reproductive-access
host-audit-landing-reproductive-access: ## Audit saved late survivors' readiness, bank access and seeds (offline; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_reproductive_access.py \
		--bundle "$(GARDEN_LANDING_FOLLOWUP_OUT)" --out "$(GARDEN_LANDING_REPRODUCTIVE_ACCESS_OUT)"

.PHONY: host-probe-landing-disturbance host-audit-landing-disturbance
host-probe-landing-disturbance: image ## Test one death with natural decomposition (20 native calls; fresh outputs)
	$(COMPOSE) run --rm -T firmware bash scripts/container/host-landing-disturbance-build.sh
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_disturbance.py \
		--collect "$(GARDEN_LANDING_DISTURBANCE_OUT)" --out "$(GARDEN_LANDING_DISTURBANCE_CAPTURE)" \
		--original "$(GARDEN_LANDING_FOLLOWUP_OUT)"

host-audit-landing-disturbance: ## Reconcile the saved paired vacancy response (offline; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_disturbance_audit.py \
		--extract-from "$(GARDEN_LANDING_DISTURBANCE_OUT)" --out "$(GARDEN_LANDING_DISTURBANCE_AUDIT)"

.PHONY: host-probe-landing-second-opening host-audit-landing-second-opening
host-probe-landing-second-opening: image ## Test a second death at day 288 through day 320 (25 calls; fresh outputs)
	$(COMPOSE) run --rm -T firmware bash scripts/container/host-landing-disturbance-build.sh
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_second_opening.py \
		--collect "$(GARDEN_LANDING_SECOND_OPENING_OUT)" --out "$(GARDEN_LANDING_SECOND_OPENING_CAPTURE)" \
		--original "$(GARDEN_LANDING_DISTURBANCE_OUT)"

host-audit-landing-second-opening: ## Reconcile second-opening descendants/resources (offline; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_second_opening_audit.py \
		--extract-from "$(GARDEN_LANDING_SECOND_OPENING_OUT)" --out "$(GARDEN_LANDING_SECOND_OPENING_AUDIT)"

.PHONY: host-audit-landing-opening-opportunities
host-audit-landing-opening-opportunities: ## Audit reachable sites, affordability and bank access (offline; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_opening_opportunities.py \
		--out "$(GARDEN_LANDING_OPENING_OPPORTUNITIES_OUT)"

.PHONY: host-probe-landing-seed-replacement
host-probe-landing-seed-replacement: image ## Test paid own-seed replacement (20 calls; fresh outputs)
	$(COMPOSE) run --rm -T firmware bash scripts/container/host-landing-seed-replacement-build.sh
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_seed_replacement.py \
		--collect "$(GARDEN_LANDING_SEED_REPLACEMENT_OUT)" --out "$(GARDEN_LANDING_SEED_REPLACEMENT_CAPTURE)" \
		--original "$(GARDEN_LANDING_SECOND_OPENING_OUT)"

.PHONY: host-audit-landing-seed-competition
host-audit-landing-seed-competition: ## Audit pending seeds and opening capacity (offline; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_seed_competition.py \
		--bundle "$(GARDEN_LANDING_SEED_REPLACEMENT_OUT)" --out "$(GARDEN_LANDING_SEED_COMPETITION_OUT)"

.PHONY: host-probe-landing-patch-sweep
host-probe-landing-patch-sweep: image ## Test fixed repeated spatial dieback (25 calls; fresh outputs)
	$(COMPOSE) run --rm -T firmware bash scripts/container/host-landing-patch-sweep-build.sh
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_patch_sweep.py \
		--collect "$(GARDEN_LANDING_PATCH_SWEEP_OUT)" --out "$(GARDEN_LANDING_PATCH_SWEEP_CAPTURE)"

.PHONY: host-continue-landing-patch-sweep
host-continue-landing-patch-sweep: ## Complete the pinned interrupted sweep (13 missing calls; no rebuild)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_patch_sweep_continue.py \
		--continue-bundle "$(GARDEN_LANDING_PATCH_SWEEP_OUT)" --out "$(GARDEN_LANDING_PATCH_SWEEP_CAPTURE)"

.PHONY: host-confirm-landing-patch-sweep
host-confirm-landing-patch-sweep: ## Confirm dieback on six fresh seed/layout pairs (26 calls; frozen binary)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_patch_confirmation.py \
		--collect "$(GARDEN_LANDING_PATCH_CONFIRMATION_OUT)" --out "$(GARDEN_LANDING_PATCH_CONFIRMATION_CAPTURE)"

.PHONY: host-followup-landing-patch-sweep
host-followup-landing-patch-sweep: ## Follow six dieback pairs to day 352 (36 calls; no added events)
	$(COMPOSE) run --rm -T firmware bash scripts/container/host-landing-patch-followup-build.sh
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_patch_followup.py \
		--collect "$(GARDEN_LANDING_PATCH_FOLLOWUP_OUT)" --out "$(GARDEN_LANDING_PATCH_FOLLOWUP_CAPTURE)"

.PHONY: host-audit-landing-patch-renewal
host-audit-landing-patch-renewal: ## Audit saved day-352 winter deaths and recruitment gates (offline; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_patch_renewal.py \
		--bundle "$(GARDEN_LANDING_PATCH_FOLLOWUP_OUT)" --out "$(GARDEN_LANDING_PATCH_RENEWAL_OUT)"

.PHONY: host-probe-landing-seed-cursor
host-probe-landing-seed-cursor: ## Compare purchase-driven seed priority (36 calls; host only; fresh output)
	$(COMPOSE) run --rm -T firmware bash scripts/container/host-landing-seed-cursor-build.sh
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_seed_cursor.py \
		--collect "$(GARDEN_LANDING_SEED_CURSOR_OUT)" --out "$(GARDEN_LANDING_SEED_CURSOR_CAPTURE)"

.PHONY: host-follow-landing-competitive-renewal
host-follow-landing-competitive-renewal: ## Follow competitive renewal through day 512 (60 calls; fresh output)
	$(COMPOSE) run --rm -T firmware bash scripts/container/host-landing-competitive-renewal-build.sh
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_competitive_renewal_capture.py \
		--collect "$(GARDEN_LANDING_COMPETITIVE_RENEWAL_OUT)" --out "$(GARDEN_LANDING_COMPETITIVE_RENEWAL_CAPTURE)"

.PHONY: host-audit-landing-recruit-seeds
host-audit-landing-recruit-seeds: ## Audit saved recruit seeds and living headcount (offline; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_recruit_seeds.py \
		--out "$(GARDEN_LANDING_RECRUIT_SEEDS_OUT)"

.PHONY: host-trace-landing-seed-handoff host-audit-landing-seed-handoff
host-trace-landing-seed-handoff: ## Trace the frozen seed handoff (two replays; 66-step logs; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_seed_handoff_capture.py \
		--out "$(GARDEN_LANDING_SEED_HANDOFF_OUT)"

host-audit-landing-seed-handoff: ## Verify the completed seed handoff bundle (offline; fresh export)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_seed_handoff.py \
		--bundle "$(GARDEN_LANDING_SEED_HANDOFF_OUT)" --out "$(GARDEN_LANDING_SEED_HANDOFF_RESULTS)"

.PHONY: host-trace-landing-nonbuyer host-audit-landing-nonbuyer
.PHONY: host-compare-landing-seed-wait
.PHONY: host-compare-landing-patch-recurring
.PHONY: host-followup-landing-recurring
.PHONY: host-compare-landing-recurring-fresh
host-compare-landing-recurring-fresh: ## Compare fresh winter renewal pairs to day 608 (66 calls; fresh output)
	$(COMPOSE) run --rm -T firmware bash scripts/container/host-landing-patch-recurring-build.sh
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_recurring_fresh.py \
		--collect "$(GARDEN_LANDING_RECURRING_FRESH_OUT)" --out "$(GARDEN_LANDING_RECURRING_FRESH_CAPTURE)"

host-followup-landing-recurring: ## Follow winter offspring to day 544 (24 calls; host only; fresh output)
	$(COMPOSE) run --rm -T firmware bash scripts/container/host-landing-patch-recurring-build.sh
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_recurring_followup.py \
		--collect "$(GARDEN_LANDING_RECURRING_FOLLOWUP_OUT)" --out "$(GARDEN_LANDING_RECURRING_FOLLOWUP_CAPTURE)"

host-compare-landing-patch-recurring: ## Compare recurring winter openings (48 calls; host only; fresh output)
	$(COMPOSE) run --rm -T firmware bash scripts/container/host-landing-patch-recurring-build.sh
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_patch_recurring.py \
		--collect "$(GARDEN_LANDING_PATCH_RECURRING_OUT)" --out "$(GARDEN_LANDING_PATCH_RECURRING_CAPTURE)"

host-compare-landing-seed-wait: ## Compare waiting-time purchase priority (48 calls; host only; fresh output)
	$(COMPOSE) run --rm -T firmware bash scripts/container/host-landing-seed-wait-build.sh
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_seed_wait.py \
		--collect "$(GARDEN_LANDING_SEED_WAIT_OUT)" --out "$(GARDEN_LANDING_SEED_WAIT_CAPTURE)"

host-trace-landing-nonbuyer: ## Trace a frozen non-buyer's full life (two passive replays; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_nonbuyer_capture.py \
		--out "$(GARDEN_LANDING_NONBUYER_OUT)"

host-audit-landing-nonbuyer: ## Audit saved reproduction gates and bank access (offline; fresh export)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_nonbuyer.py \
		--bundle "$(GARDEN_LANDING_NONBUYER_OUT)" --out "$(GARDEN_LANDING_NONBUYER_RESULTS)"

host-audit-landing-root-direction: ## Explain saved first-day water and seed timing (offline; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_root_direction_audit.py \
		--bundle "$(GARDEN_LANDING_ROOT_DIRECTION_OUT)" --out "$(GARDEN_LANDING_ROOT_DIRECTION_AUDIT_OUT)"

host-probe-landing-continuous-energy: host-build ## Test energy protection without the one-day cutoff (40 calls; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_continuous_energy.py \
		--build /workspace/app/build-host --out "$(GARDEN_LANDING_CONTINUOUS_ENERGY_OUT)"

host-probe-landing-afternoon: host-build ## Test stored reserves for afternoon maintenance increases (40 calls; fresh output)
	$(COMPOSE) run --rm -T firmware python3 sim/garden_landing_afternoon.py \
		--out "$(GARDEN_LANDING_AFTERNOON_OUT)"

host-audit-garden: host-build ## Audit seed lifetimes and planting sites against a completed experiment
	$(COMPOSE) run --rm firmware python3 sim/garden_establishment.py \
		--bundle "$(GARDEN_AUDIT_BUNDLE)" --output "$(GARDEN_AUDIT_OUT)" $(GARDEN_AUDIT_ARGS)

host-train-garden: host-build ## Evolve and export a deterministic Garden neural policy
	@mkdir -p "$(dir $(GARDEN_TRAIN_OUT))" "$(dir $(GARDEN_MODEL_OUT))" \
		"$(dir $(GARDEN_MODEL_C_OUT))"
	@$(COMPOSE) run --rm firmware "$(HOST_GARDEN_TRAINER)" \
		--generations "$(GARDEN_TRAIN_GENERATIONS)" \
		--population "$(GARDEN_TRAIN_POPULATION)" \
		--trials "$(GARDEN_TRAIN_TRIALS)" --ticks "$(GARDEN_TRAIN_TICKS)" \
		--mutations "$(GARDEN_TRAIN_MUTATIONS)" --seed "$(GARDEN_TRAIN_SEED)" \
		$(if $(strip $(GARDEN_TRAIN_INPUT)),--input "$(GARDEN_TRAIN_INPUT)",) \
		--output "$(GARDEN_MODEL_OUT)" --c-output "$(GARDEN_MODEL_C_OUT)" \
		> "$(GARDEN_TRAIN_OUT)"
	@$(COMPOSE) run --rm firmware python3 -m json.tool "$(GARDEN_TRAIN_OUT)" >/dev/null
	@$(COMPOSE) run --rm firmware python3 sim/summarize_garden_training.py \
		"$(GARDEN_TRAIN_OUT)"

host-image: ## Build or refresh the pinned SDL host-player image
	$(COMPOSE) build host-player

host-player-build: host-image ## Build the interactive native player without host dependencies
	$(COMPOSE) run --rm host-player

host-player-check: host-player-build ## Smoke-test the SDL player using its off-screen driver
	$(COMPOSE) run --rm --env SDL_VIDEODRIVER=dummy host-player \
		ctest --test-dir build-host-player --output-on-failure -R player-smoke

host-play: host-player-build ## Launch the interactive player on the host; pass ARGS="..."
	"$(HOST_PLAYER)" $(ARGS)

host-research-player-build: host-image ## Build the separate frozen-policy Garden viewer
	$(COMPOSE) run --rm host-player bash scripts/container/host-research-player-build.sh

host-research-player-check: host-research-player-build ## Check research ownership, playback, and capture parity
	$(COMPOSE) run --rm -T host-player \
		ctest --test-dir artifacts/garden-research-player-build-v1 --output-on-failure -R '^research-'
	$(COMPOSE) run --rm -T host-player python3 -B -m unittest discover \
		-s sim/research_player -p 'test_prepare.py'

host-play-research: host-research-player-build ## Watch frozen repair policies; ARGS="--policy s1-g3-c4 --speed 256"
	"$(HOST_RESEARCH_PLAYER)" $(ARGS)

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

sim-run: image ## Resume exact real-time 60 Hz simulation scheduling
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py --require-prefix "mode=" "$$port" \
				picosystem game run

sim-reset: image ## Restore the playable scene to tick zero while paused
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py --require-prefix "mode=" "$$port" \
				picosystem game reset

sim-scene: image ## Select SCENE=clockwork|hourglass|marble-machine|garden while paused
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py --require-prefix "scene=" "$$port" \
				picosystem game scene "$(SCENE)"

sim-action: image ## Apply ACTION=primary|use-tool|cycle-tool while paused
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py --require-prefix "mode=" "$$port" \
				picosystem game action "$(ACTION)"

sim-flip: ACTION = primary
sim-flip: sim-action ## Compatibility alias for sim-action

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

profile-granular: image ## Profile Hourglass stages for GRANULAR_PROFILE_TICKS=<count>
	@port="$$($(SERIAL_PORT_HELPER) "$(PORT)")" || exit $$?; \
		$(DOCKER) run --rm --user 0:0 \
			--device "$$port:$$port" \
			--volume "$(CURDIR):/workspace/app:ro" \
			"$(FIRMWARE_IMAGE)" \
			python3 ./scripts/container/serial-command.py --timeout 60 \
				--require-prefix "GRANULAR_PROFILE_END" "$$port" \
				picosystem profile granular "$(GRANULAR_PROFILE_TICKS)"

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
