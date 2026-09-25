# Storage-limited root uptake experiment

## Hypothesis and fixed protocol

The [scattering-width test](dispersal.md) improved establishment without
consistently improving durable lineages. Earlier resource traces also showed
substantial root extraction discarded when plant storage was full. Test whether
leaving that water in the soil helps seedlings acquire resources and sustain
descendants.

The host-only `TOY_FACTORY_GARDEN_WATER_HEADROOM` variant changes each root's
uptake from `min(soil, species root rate)` to
`min(soil, species root rate, 512 - current plant water)`, **before** removing
water from the soil. Storage updates after every root. Plant and root order,
photosynthesis, upkeep, growth, reproduction, rainfall and evaporation remain
unchanged; no extra capacity is reserved for later spending in the step.
`last_water_income` continues to report actual extraction, so controllers can
observe lower income at full storage. We hold model weights and input schema
fixed, not the resulting observations or decisions.

Use **original narrow scattering**, not the previous wider variant. Combined
options are rejected by both CMake and the collector. The default host build
explicitly disables both experiments; firmware rejects the experimental define.
No world RAM is added and no on-device deployment is part of this investigation.

Fixed panel: model `dc5e849d`, original NN / NN + existing night-growth veto /
adaptive, eight seeds from batch `0x6d617463`, both rainfed layouts, 24 cycles
(92,160 ticks), with renewal examined over the final eight cycles. No gardener,
training or retuning. The weather/layout seeds have already been examined and
are exploratory, not untouched test data. Evaluate full-cycle offspring and
durable parent/child outcomes, seed establishment, death causes, resource
accounting and capacity pressure; births or final population alone are not wins.

Visual panel: seeds `6f47c12c` and `9c530b07`, both layouts, all three policies,
ticks 68,760 and 92,160, matching the scattering investigation. Inspect soil
accumulation too: host censuses now include an exact `soil.water` sum and
`soil.saturated_cells`, because the existing uint16 `moisture` summary saturates
at 65,535. These fields are read-only and do not change world hashes.

## Reproduce

Use new output paths for reruns; collectors refuse existing directories and
reject source changes while collecting. All binaries/models/source provenance
and selected replays are frozen in each bundle.

```sh
make host-build
docker compose run --rm firmware cmake -S sim \
  -B artifacts/build-host-water-headroom -G Ninja \
  -DTOY_FACTORY_GARDEN_WATER_HEADROOM=ON \
  -DTOY_FACTORY_GARDEN_WIDE_DISPERSAL=OFF \
  -DTOY_FACTORY_SIMULATOR_SANITIZERS=ON
docker compose run --rm firmware cmake --build artifacts/build-host-water-headroom
docker compose run --rm firmware python3 sim/test_garden_dispersal.py \
  --narrow-build build-host --water-build artifacts/build-host-water-headroom

docker compose run --rm firmware python3 sim/garden_experiments.py \
  --output artifacts/garden-water-control \
  --candidate-model artifacts/garden-lifetimes/champion.tgm \
  --control-model artifacts/garden-lifetimes/champion.tgm \
  --candidate-probe no-night-growth-v1 \
  --training-report artifacts/garden-lifetimes/training.json \
  --split exploratory --cycles 24 --trials 8 --seed 0x6d617463
docker compose run --rm firmware python3 sim/garden_experiments.py \
  --output artifacts/garden-water-capped --water-uptake headroom-v1 \
  --evaluator artifacts/build-host-water-headroom/toy-factory-garden-eval \
  --inspector artifacts/build-host-water-headroom/toy-factory-garden-inspect \
  --candidate-model artifacts/garden-lifetimes/champion.tgm \
  --control-model artifacts/garden-lifetimes/champion.tgm \
  --candidate-probe no-night-growth-v1 \
  --training-report artifacts/garden-lifetimes/training.json \
  --split exploratory --cycles 24 --trials 8 --seed 0x6d617463
docker compose run --rm firmware python3 sim/garden_ecology.py \
  --control artifacts/garden-water-control --candidate artifacts/garden-water-capped \
  --change water-headroom --late-cycles 8 \
  --output artifacts/garden-water-comparison.json
```

Run each bundle through `sim/garden_establishment.py --bundle BUNDLE --output NEW`
and `sim/garden_gallery.py --bundle BUNDLE --output NEW --include-adaptive
--seed 6f47c12c --seed 9c530b07 --checkpoint 68760 --checkpoint 92160`.
For the capped build supply `--inspector
artifacts/build-host-water-headroom/toy-factory-garden-inspect` to the audit and
the corresponding `--replayer .../toy-factory-garden-replay` to the gallery.
The control tools default to `build-host/`.

After those audits, reproduce exact soil statistics and checked live-step
water budgets (audit directories must be named `BUNDLE-audit`):

```sh
python3 benchmarks/garden-longevity/water-headroom.py \
  --control artifacts/garden-water-control --capped artifacts/garden-water-capped \
  --output artifacts/garden-water-resources.json
```

The resource analysis validates frozen input artifacts and the matched ecology
pair before reading them. Selected resource traces differ between batches and
are not an unbiased panel; soil summaries cover all 48 relevant worlds per side.

## Results

Completed 2026-09-11. Counts below are **legacy extraction → capped extraction**,
over 16 worlds per policy (eight paired seeds × two layouts). No training occurred.

| Policy | Germinations | Full-cycle survivors / eligible offspring | Durable parents | Water-only deaths |
|---|---:|---:|---:|---:|
| Original NN | 138 → 108 | 44/137 → 54/108 | 23 → 32 | 33 → 12 |
| NN + night-growth veto | 181 → 135 | 78/180 → 77/135 | 33 → 26 | 68 → 21 |
| Adaptive | 78 → 65 | 44/78 → 45/65 | 11 → 11 | 10 → 0 |

Eligible offspring have a full 3,840-tick potential follow-up; a qualified
survivor may subsequently die. Durable parents and at least one child each
survive a full cycle, not necessarily concurrently. All three policies improve
their full-cycle survival *fraction*, but only original NN gains substantially
in cumulative survivor/durable-parent counts. Original NN's survivor count
improves in eight matched worlds, ties in seven and worsens in one. The veto's
count improves in eight, ties in one and worsens in seven.

Water-only deaths fall 111 → 33 over the 48 relevant worlds; combined
energy/water deaths fall 20 → 4. These are counts, not exposure-normalized death
risks. First-dawn populations and nonviable-world counts are unchanged: original
NN still ends nonviable in 3/16 worlds, the other policies in 0/16. Final living
plants rise 55 → 68 (NN), 79 → 90 (veto), 79 → 89 (adaptive).

The benefit is not uniform across layouts. Veto-policy durable parents fall
22 → 13 in rainfed, while rising 11 → 13 in crowded. No generalization or
statistical significance claim is made from this small exploratory panel.

## More survival, less renewal

Final eight cycles (61,440 < tick ≤ 92,160):

| Policy | New births | Newly qualified full-cycle survivors | Newly qualified durable parents |
|---|---:|---:|---:|
| Original NN | 12 → 2 | 2 → 1 | 2 → 1 |
| NN + night-growth veto | 8 → 4 | 5 → 3 | 5 → 3 |
| Adaptive | 5 → 4 | 2 → 1 | 1 → 0 |

Qualification deltas are thresholds reached in the window, not a late-born
offspring cohort. Total late births fall 25 → 10, despite more seeds being
created (NN 436 → 578, veto 855 → 955, adaptive 977 → 986).

For seeds born after cycle 16 but early enough for a full seed-lifetime
follow-up (birth through cycle 23), germinations / eligible seeds are
10/381 → 2/506 (NN), 6/746 → 4/835 (veto), 5/855 → 4/862 (adaptive).
These seed cohorts are distinct from the offspring-survival cohorts above.

The audit describes a change in the constraints. Among *remaining mature-seed
snapshots* during the final eight cycles' bright daylight:

| Policy | Moisture blocked | Spacing blocked | Light blocked | Fewer than four free nodes |
|---|---:|---:|---:|---:|
| Original NN | 96.1% → 0.8% | 96.5% → 100.0% | 14.6% → 25.7% | 0.0% → 11.3% |
| NN + night-growth veto | 96.7% → 12.8% | 97.9% → 98.3% | 56.8% → 65.5% | 29.0% → 58.1% |
| Adaptive | 96.2% → 9.5% | 85.4% → 87.8% | 64.4% → 67.5% | 26.3% → 59.2% |

Denominators are 27,138 → 36,324 (NN), 54,168 → 60,798 (veto), and
62,397 → 62,524 (adaptive). Constraints overlap; these are repeated,
survivor-biased post-step observations, **not independent failure probabilities**.
Successful germinations already left the bank. See [the audit](establishment.md).

Over all times in the late window, the 256-node pool is completely full on
average 24.0% → 54.6% of the time for veto and 18.8% → 44.8% for adaptive.
Original NN never reaches 256 in that window but sometimes leaves fewer than
the four nodes needed to germinate. This distinguishes a hard storage constraint
from soil spacing/shade. Neither limit was raised in this experiment.

The fixed `rainfed/9c530b07` veto example ends with six living plants instead
of five, a fuller canopy, and a node pool full throughout the late window;
neither variant has late births there. The wetter plot is not evidence of
continuing renewal. Conversely, `rainfed/6f47c12c` veto ends with four plants
instead of five: the cap does not monotonically increase each world's population.

## Water accounting and accumulation

Unit tests cover each species, empty/dry/full soil, water stores up through
512, multi-root accumulation, and competition for a shared cell. If the earlier
plant is full, capped uptake leaves the cell available for the next plant;
when both need water, the original processing order remains. Photosynthesis
continues at full water, upkeep still runs, and uptake replenishes its debit on
the following ecology step. Invalid stored water 513 is rejected without mutation.

All 216,843 checked live plant-steps in the eight selected capped traces have
zero water-overflow discard and reconcile the existing resource budgets. The
53 terminal steps are excluded because death clears income telemetry. This
does not claim a complete terminal or whole-world water balance.

For the matched `rainfed/c7f54e18` veto trace, late extraction drops
27,618 → 13,312 while discarded overflow drops 22,720 → 0. There are more
living-plant observations in the capped trajectory, so these are matched-world
totals, not equal-exposure rates.

Exact mean soil water over the final eight cycles, averaged over all ecology
steps and all 16 worlds per policy:

| Policy | Legacy | Capped |
|---|---:|---:|
| Original NN | 9,524.6 | 30,397.3 |
| NN + night-growth veto | 1,301.3 | 19,409.8 |
| Adaptive | 706.0 | 19,470.2 |

The NN means include the three extinct worlds, which naturally have no living
roots withdrawing water. No soil cell reaches 255 in any of the 96 relevant
censuses, and no exact total exceeds 65,535 within this horizon. Therefore the
reported accumulation is not a clipped-counter artifact, but longer unattended
runs could still behave differently. Retaining water changes the effective
water budget; this experiment does not model transpiration or a complete cycle.

## Evidence and validation

- Fresh control reports are byte-identical to the previous narrow-scattering
  reports. Model SHA remains
  `bd9f9c6ba7f5fd17309f917972da5f759c305c077798e1d4ba9a52701e2cd48b`.
- Reconciled all 6,629 control and 7,270 capped seeds against 77,459 and 77,361
  evaluator checkpoints. All trials were retained, including extinct worlds.
- Captured the predeclared 24-image panel for each variant, then reproduced all
  48 images' state hashes and framebuffer bytes using frozen executables.
  The long counterexample census also reproduces exactly for each variant.
- All 23 normal CTests pass under strict warnings/UBSan, including device
  sequence goldens. Two-build integration covers wrong-ecology rejection,
  mixed-experiment rejection, paired settings, audits, screenshots, frozen
  replay and refusal to overwrite outputs.
- Placement and water-uptake comparisons share matched-pair validation and
  metric pairing in `sim/garden_ecology.py`; the existing dispersal command is
  retained. No unrelated firmware architecture changes were made.

Local bundles are `artifacts/garden-water-{control,capped}/`, with corresponding
`-audit/index.md` and `-gallery/index.md` outputs. They are ignored local evidence,
not published assets; this versioned note preserves the numeric findings.

| Artifact | SHA-256 |
|---|---|
| Control bundle manifest | `3223ca779afa9e47be5d8f8b8f071295d915949c6f344303f24348521d730f95` |
| Capped bundle manifest | `cf7a731fc97196a8ca3ecde4a30a015002b5542eb36e98f45489b3bfc4f75a42` |
| Control audit manifest | `e0fd71f2e340423a6ac9f90109e567292d711f2a6a67bfcad93202e51a6bc217` |
| Capped audit manifest | `95c757f1833bb60db23dce0a33e69e4bec63cfe087ad218d1783d1d338e0a49a` |
| Control gallery manifest | `ca591fd463088444fe4717d7dc7b2a71356ce69ccca4b14ff6f0975042d4a3d4` |
| Capped gallery manifest | `df6ec337614fb8451ff2c8ffed4b6a5d2b6cbc324fb27e491c3023a2d23c9dcf` |
| Paired comparison JSON | `f35a158279bbb3ff8cabdebd5e49e57fd69c3ac06174a1464876e0738ff5b089` |
| Resource analysis JSON | `80cd84ec53b9698cf5bee85f9e7e50727a8ffa63da62fd571523ed2653a1fa58` |

## Decision and next discussion

The cap does what was intended: it prevents discarded root extraction, reduces
water stress and improves offspring survival fractions. It does **not** by
itself establish sustained renewal. Longer survival also means fewer vacancies,
and larger surviving bodies compete for a fixed node pool. Lower birth counts
alone are not grounds for calling healthier survivors a regression.

Keep this as a host experiment pending the mechanics discussion; no firmware
flash, default uptake change, commit or push. A useful next controlled test is
the missing combination, capped uptake **plus** wider scattering, completing the
2×2 comparison against the three measured conditions. That would need an
explicitly labeled combined condition rather than removing safeguards silently.
Check space/node pressure before changing capacities or introducing new turnover
mechanisms; do not add forced deaths merely to improve a reproduction score.

Follow-up: the [combined experiment](combined-ecology.md) is now measured with
explicit opt-in. The isolated findings and frozen controls above are unchanged.
