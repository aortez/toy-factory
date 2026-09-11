# Seeded environmental rainfall

## Contract

Rain-v1 is an open environmental input, independent of gardener decisions and
plant random streams. Each 128-ecology-step (32-second) window contains a single
16--32-step shower at a seed-dependent offset, with 2--4 units per surface column
per step. All other ecology rules, policy observations, and existing model
weights are unchanged. The world gains 12 bytes (4,340 to 4,352); snapshots carry
one rain-rate byte, and dirty rendering tracks the small `RAIN` indicator.

Training switches to the rain-fed three- and five-founder environments. The
gardener is off and no gardener actions or periodic irrigation are permitted.
Both retain the previous fixed startup watering. The historical three-scenario
diagnostic suite remains rain-disabled: all 288 trial outcomes, including the
complete schema-4 reports, exactly matched the earlier two-cycle/32-seed batch.

## Initial long-run check

Eight seeds from a new batch seed `0x7261696e`, 92,160 logic ticks per trial
(24 cycles; 25 minutes 36 seconds). The frozen neural model is still CRC
`dc5e849d`; these are not newly trained weights. No weather parameters were tuned
against this batch. Each policy sees identical weather for a given world seed.

| Environment | Policy | Extinctions | Full-cycle offspring survivors / eligible |
|---|---|---:|---:|
| Rain-fed | Baseline | 1/8 | 35/80 |
| Rain-fed | Adaptive | 0/8 | 33/46 |
| Rain-fed | Frozen neural | 1/8 | 24/82 |
| Rain-fed crowded | Baseline | 1/8 | 39/61 |
| Rain-fed crowded | Adaptive | 0/8 | 15/19 |
| Rain-fed crowded | Frozen neural | 1/8 | 20/55 |

This demonstrates viable gardener-free populations and continuing reproduction,
not a balanced climate or generalization guarantee. The seeds and water delivery
differ from the earlier irrigation experiments: this is **not** a controlled
claim that rain improved the neural policy. Longer dry gaps, a conserved water
cycle, spatial weather, cloud shading, and seasons are not implemented.

Reproduce after `make host-build`:

```sh
docker compose run --rm firmware build-host/toy-factory-garden-eval \
    --rainfed --trials 8 --ticks 92160 --seed 0x7261696e \
    --model artifacts/garden-lifetimes/champion.tgm \
    > artifacts/garden-rainfall-24cycles.json
python3 sim/summarize_garden_experiment.py artifacts/garden-rainfall-24cycles.json
```

Model SHA-256:
`bd9f9c6ba7f5fd17309f917972da5f759c305c077798e1d4ba9a52701e2cd48b`.
Report SHA-256:
`06a850e778cfd4c846bd7c201838f2dd7ab5d217b15ec1ad31291187fb9850e3`.
The model is a local artifact from the prior longevity experiment, not a tracked
repository dependency; omit `--model` to exercise the untrained reference.

## Validation

- Strict-warning/UBSan world tests: repeatability, seed variation, wet/dry bounds,
  cadence, surface-only injection, diffusion, saturation/runoff, counter overflow,
  reset, RNG independence, and weather hash participation.
- Host checks compare repeated rain-fed reports and independently reconstruct
  offered rainfall for every policy/seed. Every field of the ordinary rain-disabled
  reports exactly matches the saved JSON reports.
- The trainer runs twice with byte-identical model/report outputs; a reloaded
  champion matches the evaluator's resources, lineage metrics, and world digest.
- Full versus dirty framebuffer reconstruction covers rain starting/stopping
  and intensity changes. Four playable Garden goldens now include rain.
- The PIM559 was flashed with the normal 62.5 MHz PL022/DMA, core-1-render image.
  Static RAM is 255,700 bytes (97.92% of the Zephyr region), up 88 bytes from the
  preceding build. The rain-on 930-tick replay matches host hash `28489ef5` and
  framebuffer CRC `fc95584f`. The 8,430-tick generation replay also matches host
  hash `08d270fc` and framebuffer CRC `bd42bea8`.
