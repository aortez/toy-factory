# Controlled nighttime-growth probe

2026-09-11. Follow-up to the [fixed-panel visual review](visual-review.md),
tracked in [Garden roadmap issue #30](https://github.com/aortez/toy-factory/issues/30).

## Question and controlled change

Does the frozen neural policy's nighttime growth contribute to its poor early
survival, and does preventing that spending improve **continued renewal**, not
just the first reproductive burst?

The shared host-only `no-night-growth-v1` adapter changes paid `EXTEND` and
`FINISH_TIP` proposals into `WAIT` at sun phases 128–255. It preserves tip
identity, priority, arbitration, and proposed recurrent memory. All other
mechanics—including maintenance, maturation, seed production, weather and
inheritance—remain unchanged. The ordinary neural model and adaptive policy
are controls. No training, firmware change, or new fitness was introduced.

The late window was chosen before running: cycles 16–24, ticks 61440–92160.
This is an exploratory diagnostic, not a new acceptance threshold or an
untouched test set. The same eight previously inspected world seeds and two
rain-fed layouts are used. The layouts share seeds, not independent replicates.

## Reproduce

```sh
make host-experiment-garden \
    GARDEN_EXPERIMENT_OUT=artifacts/garden-night-growth-probe \
    GARDEN_EXPERIMENT_ARGS="--candidate-model artifacts/garden-lifetimes/champion.tgm --control-model artifacts/garden-lifetimes/champion.tgm --candidate-probe no-night-growth-v1 --training-report artifacts/garden-lifetimes/training.json --split exploratory --cycles 24 --trials 8 --seed 0x6d617463"

docker compose run --rm firmware python3 sim/garden_renewal.py \
    --bundle artifacts/garden-night-growth-probe --late-cycles 8 \
    --output artifacts/garden-night-growth-probe-renewal.json

make host-gallery-garden \
    GARDEN_GALLERY_BUNDLE=artifacts/garden-night-growth-probe \
    GARDEN_GALLERY_OUT=artifacts/garden-night-growth-gallery \
    GARDEN_GALLERY_ARGS="--include-adaptive --checkpoint 480 --checkpoint 1920 --checkpoint 2880 --checkpoint 92160"
```

Output paths are ignored local artifacts, not published assets. Use new paths
to repeat a run. The maintained [experiment workflow](../../docs/garden-experiments.md)
describes the probe contract, capture, provenance, and frozen replay.

- Model CRC32: `dc5e849d` on both neural sides.
- Model file SHA256: `bd9f9c6ba7f5fd17309f917972da5f759c305c077798e1d4ba9a52701e2cd48b`.
- World seeds: `6f47c12c`, `9c530b07`, `c92854df`, `7a6a1f51`, `e59eb9eb`,
  `d08c20c0`, `c7f54e18`, `b61837dc`.
- Both rain-fed layouts, fixed startup resources, rain-v1, gardener/irrigation off.
- 24 cycles = 92160 logic ticks = 25 minutes 36 seconds of device time per world.
- Two evaluator jobs perform 96 trials including repeated baseline/adaptive
  controls. The analysis counts only the 48 unique relevant three-way outcomes.

## Whole-run results

Counts below are totals across 16 worlds per policy, except rows labeled otherwise.
Births are germinated offspring, not initial founders or newly produced seeds.

| Measure | Ordinary neural | Neural, no night growth | Adaptive |
|---|---:|---:|---:|
| Nonviable worlds at end (no living plants or seeds) | 3/16 | 0/16 | 0/16 |
| Initial founders alive at first dawn | 16/64 | 64/64 | 64/64 |
| Mean final living plants | 3.44 | 4.94 | 4.94 |
| Offspring born | 138 | 181 | 78 |
| Full-cycle offspring survivors / eligible | 44/137 | 78/180 | 44/78 |
| Durable offspring parents | 23 | 33 | 11 |
| Deaths, including founders | 147 | 166 | 63 |

A durable offspring parent and at least one child each survived a full cycle.
They need not still be alive or have overlapped for that full cycle. Recent
births without a full cycle of potential follow-up are excluded from the
survival denominator, not counted as failures. These are cumulative counts,
not a fitness score. More deaths with the probe accompany more births and
living-plant exposure; raw death counts are not comparable mortality rates.

The diagnostic paired ordering favors the probe in 11/16 worlds and the original
in 5/16 (rainfed 7/1, crowded 4/4). Durable-parent deltas range from -4 to +4,
median +0.5; full-cycle-survivor deltas range -3 to +7, median +2. This is not
uniform superiority. In rainfed seed `c7f54e18`, for example, durable parents
fall from 6 to 2 despite both worlds ending viable.

The intervention establishes a decision-level opportunity under these fixed
conditions: preventing this nighttime spending changes early survival and
aggregate outcomes. It does not prove a universally optimal rule, a learned
annual strategy, or the adequacy of the unchanged training objective.

## Does renewal continue late?

| Cycles 16–24 | Ordinary neural | Neural, no night growth | Adaptive |
|---|---:|---:|---:|
| Worlds with any new births | 5/16 | 5/16 | 2/16 |
| New births | 12 | 8 | 5 |
| New deaths | 10 | 5 | 5 |
| Newly qualified full-cycle offspring survivors | 2 | 5 | 2 |
| Newly qualified durable parents | 2 | 5 | 1 |
| Seeds created | 436 | 855 | 977 |
| Seeds expired | 423 | 842 | 971 |

The probe helps survival, but **broad sustained renewal is not demonstrated**.
Eleven of its sixteen worlds have no late births. Late qualification deltas
are thresholds reached during the window, not survival rates for offspring
born in that window; qualification can lag birth by a cycle.

Seed production continues. Expirations closely track production while very few
seeds germinate. The created/expired counts are window totals, not the same seed
cohort, so their ratio is not a measured seed survival probability.

## Resource and capacity checks

Ten selected detailed traces (five matched pairs) reproduced all 16150 recorded
timeline checkpoints. The resource reconciler verified committed bids and live
resource updates. All probed first-lifetime-cycle night budgets show zero paid
growth; original neural actions and suppressed bids remain visible in the trace.
Death clears telemetry, so terminal-step income/spending is still explicitly
unreconstructed.

For the representative rainfed seed `6f47c12c`, original founder flower/shrub/
ground-cover first-night growth consumed 24/140/105 energy with zero night
income. The probe spends zero on those actions; maintenance still costs
144/128/153 energy. Original founders die during the night, so those original
budgets have shorter exposure and exclude their cleared death steps. They are
not paired estimates of total energy saved over an equal lifetime.

| Late sampled capacity occupancy | Ordinary neural | Neural, no night growth | Adaptive |
|---|---:|---:|---:|
| Worlds reaching all 256 nodes | 0/16 | 4/16 | 3/16 |
| Mean fraction of time with all 256 nodes | 0% | 24.0% | 18.8% |
| Mean fraction of time with all 8 seed slots | 0% | 62.4% | 86.8% |
| Mean fraction of time with all 8 plant slots | 0% | 0% | 0% |

Occupancy estimates hold each at-most-one-second sample until the next sample.
The literal full-node statistic is not the entire germination-capacity limit:
a seedling needs four free nodes and can be blocked before all 256 are occupied.
The evaluator separately counts actual node-capacity blockers.

Across the full horizon, seed blockers often overlap moisture, light and spacing;
some probe/adaptive worlds also encounter node capacity. Night itself explains
many light-blocked samples, so all-phase blocker totals cannot isolate shade as
a cause. Looking only at the selected rainfed `9c530b07` late trace, every one
of 3408 mature-seed observations during sun phases 16–112 has spacing blocked;
3142 also have insufficient local surface moisture. That world's final five
plants have no growth tips. This is a useful example, not a batch-wide causal
attribution or 3408 independent seeds.

Large mature plants can retain substantial water while the local surface where
seeds land is unsuitable. The observed blockers concern those seed locations;
they do not establish that every potential location in the plot is unavailable.
Increasing node capacity alone would not resolve the original neural worlds,
which never reach that capacity in the late window.

## Visual review and invariance

The fixed panel uses the first recorded seed `6f47c12c`, not a newly selected
best seed: both layouts × three policies × ticks 480, 1920, 2880, 92160.
The 24 native images use the production renderer and match evaluator hashes.
Frozen replay subsequently reproduced all framebuffer bytes exactly.

The ordinary neural panel has dead founders at first dawn, then living
descendants late. The probe retains founders through dawn and later produces
denser shrub/ground-cover structures. Adaptive also retains its early plants.
The late pictures alone do not reveal the scarcity of new births.

| Probe frame, seed `6f47c12c` | Living / seeds | Garden hash | Framebuffer CRC32 |
|---|---:|---|---|
| rainfed, first dawn | 3 / 2 | `2ded26bf` | `8b704d1c` |
| rainfed, cycle 24 | 5 / 8 | `46813faf` | `f47bdd58` |
| crowded, first dawn | 5 / 4 | `a63f1fd3` | `2c9381ed` |
| crowded, cycle 24 | 5 / 8 | `c05c9da1` | `a330ba61` |

The unchanged neural/control evaluator report is byte-for-byte identical to
`garden-matches-baseline/reports/candidate.json`, SHA256
`456d034b25ed39973adc46ac8ebe17a24230d3b860fa34b55261cc89f9d530df`.
The new probe report SHA256 is
`c62096c25c7a40a5dda9e097479b29d4a292d112e8e8a89701322fdd89ce554f`.
The completed experiment manifest SHA256 is
`73976d15901ec284a3155af6a2101ecac2df25ce56094aea8e83718bbd5d1559`.

All 20 host CTests pass under the pristine strict-warning/UBSan build, including
all-phase action-contract tests, unchanged pre-night worlds, observational
capture, resource reconciliation, frozen probe replay, renewal-window accounting,
and three-way visual replay. No device deployment was needed.

## Next discussion

Keep this veto as a diagnostic control, not an installed requirement on agents.
Next audit **seed establishment opportunities**: actual landing positions versus
available sites through daylight/rain, separating spacing, moisture, shade and
allocation limits. Use the existing matched worlds and explicit seed age/expiry
follow-up. Then discuss controlled changes to dispersal, seed persistence or
ecology, if the evidence calls for them. Do not start broad training or add
forced deaths merely to make the plots look busy.
