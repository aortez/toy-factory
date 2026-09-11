# Garden longevity investigation

This is the pre-renewal baseline (Garden hash version 4). The subsequent
[renewable-flower comparison](renewal.md) uses the same frozen model and seeds
with the corrected lifecycle. The original observations below remain unchanged.

The first trained neural champion keeps every watered held-out garden alive
through 24 day/night cycles. Reproduction stops before the end of the test,
however, and most surviving plants are founders. Survival alone overstates
progress toward an ecosystem with continuing generational turnover.

## Reproduce

The baseline champion was produced from the repository root with:

```sh
make host-train-garden
```

This investigation used model payload CRC-32 `dc5e849d`, model-file SHA-256
`bd9f9c6ba7f5fd17309f917972da5f759c305c077798e1d4ba9a52701e2cd48b`.
The training settings were 8 generations, population 16, 2 trials per scenario,
7,680 ticks per trial, 32 mutations per offspring, and base seed `0x74726169`.
Running that command with changed ecology can produce different weights. Keep
the saved model/training report for a paired comparison instead of overwriting
them. The model was frozen throughout the investigation; held-out results were never
used to select another model.

```sh
docker compose run --rm firmware python3 benchmarks/garden-longevity/run.py \
  --output artifacts/garden-longevity-heldout \
  --trials 32 --seed 0x686f6c64 --jobs 3
```

The runner refuses an existing output directory. Choose a new directory for a
rerun. It verifies the model envelope/CRC against the training report, checks
that held-out seeds exclude both training seeds, freezes the model and training
report, and records source/binary/model hashes in `provenance.json`. Complete
evaluator reports are `cycles-02.json` through `cycles-24.json`; `summary.json`
contains aggregates and differences between horizons. Raw outputs remain under
the ignored `artifacts/` directory.

One Garden cycle is 256 ecology steps, 3,840 authoritative ticks, or 64 simulated
seconds. Thus the longest trial covers 92,160 ticks and 25 minutes 36 seconds.
The 32 seeds are paired across all three policies and all three existing scene
layouts. Shorter horizons replay prefixes of the same trajectories; the 1,440
runs are not 1,440 independent environments. The entire sweep took about 79
seconds on this host using three concurrent evaluator processes under UBSan.
This is host throughput, not a PicoSystem performance measurement.

## Results

At 24 cycles:

| Scenario | Policy | Gardens with living plants | Mean final living plants | Highest generation reached |
| --- | --- | ---: | ---: | ---: |
| Unassisted | Baseline | 0/32 | 0 | 0 |
| Unassisted | Adaptive | 0/32 | 0 | 0 |
| Unassisted | Neural champion | 0/32 | 0 | 0 |
| Irrigated | Baseline | 30/32 | 1.97 | 2 |
| Irrigated | Adaptive | 32/32 | 3.69 | 2 |
| Irrigated | Neural champion | 32/32 | 1.13 | 11 |
| Crowded, irrigated | Baseline | 31/32 | 2.50 | 2 |
| Crowded, irrigated | Adaptive | 32/32 | 4.19 | 1 |
| Crowded, irrigated | Neural champion | 32/32 | 2.00 | 1 |

There were no seed-only survivors at these final checkpoints. All unassisted
trials were already extinct by cycle 2, for all policies. These plots receive
initial watering but no ongoing external water. Irrigated plots receive 8 water
units at every column every 960 ticks, independent of policy and population.

The neural irrigated lineage progression was:

| Cycles | Mean living plants | Cumulative established offspring, all 32 trials | Maximum generation | Trials with new births since previous checkpoint |
| ---: | ---: | ---: | ---: | ---: |
| 2 | 1.28 | 67 | 2 | 32 |
| 4 | 1.25 | 88 | 4 | 13 |
| 8 | 1.19 | 109 | 8 | 8 |
| 16 | 1.13 | 116 | 11 | 2 |
| 24 | 1.13 | 116 | 11 | 0 |

Crowded neural gardens reach 71 established offspring in aggregate by cycle 2,
then produce no more births. By cycle 24 every crowded neural garden contains
exactly two founder flowers. Irrigated neural gardens retain all 32 founder
flowers and just four descendant ground-cover plants across three trials.
No neural shrubs survive. Adaptive irrigated gardens retain all three species
in every trial, although their reproduction also stops.

Between cycles 16 and 24, **all three policies in all scenarios** record zero
new births, deaths, seeds, and policy decisions. Maintenance and resource/light
updates still run; plants with no remaining growth tips have no policy decisions
to make. No late activity was hidden by sampling only the final population.

## Why the populations become quiet

`inspect.c` is a host-only observer linked to the existing pure simulation core.
It prints JSONL at initial state, cycle boundaries, and birth/death changes,
including plant ancestry, resources, growth tips, flowers, and spent flowers.
It does not change the simulation or policy. Build it after `make host-build`:

```sh
docker compose run --rm firmware cc \
  -std=c11 -Wall -Wextra -Werror -Wconversion -Wsign-conversion \
  -fsanitize=undefined -fno-sanitize-recover=undefined \
  -Isrc -Isim benchmarks/garden-longevity/inspect.c \
  build-host/libtoy_factory_simulator_core.a \
  -o artifacts/garden-longevity-heldout/inspect

docker compose run --rm firmware artifacts/garden-longevity-heldout/inspect \
  artifacts/garden-longevity-heldout/champion.tgm \
  irrigated neural-candidate 0xa7b5ccea \
  > artifacts/garden-longevity-heldout/trace-irrigated-neural-a7b5ccea.jsonl
```

The representative seed `a7b5ccea` was also traced with the crowded neural
scenario and the irrigated adaptive policy. All 15 trace checkpoint hashes
(three trajectories times five horizons) match the corresponding evaluator
reports exactly.

A further replay of all 64 watered neural trials matched every terminal hash.
All 100 surviving plants have zero growth tips: 96 founder flowers and four
descendant ground-cover plants. The two 37-node ground-cover survivors have
used all four flowers each. The other two have 43 and 45 nodes, retain unused
flowers, and require 288 and 264 reproduction energy respectively, exceeding
the 256-unit storage cap with their own reserve traits. Thus both terminal
conditions below also occur among the neural survivors.

The deepest lineage, irrigated neural seed `a7b5ccea`, has its generation-11
ground-cover birth at tick 41,520 (cycle 10.8125). That plant dies at tick 44,220
(cycle 11.515625). Its generation-12 seed never germinates; the lineage's final
seed expires at tick 46,680 (cycle 12.15625). Later survival belongs to the
original founder flower, not that ground-cover lineage.

The surviving founder has 36 nodes, 20 root nodes, 8 leaves, zero growth tips,
and one flower that has already produced its seed. At cycle 24 it has 251
energy, 510 water, and zero stress. Both founder flowers in the crowded trace
have the same structure and resources. Two existing mechanics explain these
terminal structures:

1. A flower produces only one seed, tracked by `FLOWER_SEEDED`. There is no
   automatic flower renewal or regrowth after all tips finish. Resource-funded
   maintenance can keep that fully grown plant alive without age-driven death.
2. Larger plants can require more energy to reproduce than they can ever store.
   With the default reserve trait, reproduction requires
   `48 + max(96, ceil(node_count / 8) * 40)` energy, while storage caps at 256.
   The adaptive trace's 57-node shrub and 59-node ground-cover each require 368
   energy. Both retain unspent flowers, but the energy gate is unreachable at
   those body sizes. A default-trait plant crosses this limit above 40 nodes.

These conclusions follow from `update_reproduction`, `plant_can_reproduce`,
`unseeded_flower_index`, and `update_plant_maintenance` in
[`garden_world.c`](../../src/garden_world.c), plus the traced structures. They
are not evidence of a host stall or a neural-only failure.

## Implications for the next experiment

The champion has useful early reproductive behavior, but is not generally
better than adaptive: it preserves fewer plants and loses species diversity.
Generation depth describes historical progress and does not prove continued
reproduction. Likewise, the existing "established offspring" gate only requires
age 5 ecology steps (1.25 seconds), no stress, and an active leaf. It does not
require that offspring survive a complete day/night cycle or reproduce.

Before a longer training search, discuss lifecycle changes that permit ongoing,
resource-funded reproduction and review the reserve/storage mismatch. Possible
choices include flower renewal, bounded regrowth, and eventual tissue turnover;
they change the ecology and should be designed explicitly. Then evaluate
late-window births, descendants surviving a complete cycle, and surviving
founder/species lineages alongside total survival. Keep a separate held-out
seed set when tuning or selecting models.

This baseline investigation left ecology, fitness ordering, neural weights, firmware,
and device state unchanged. It tested unseen seeds in the existing layouts,
through 24 cycles; it does not establish behavior in arbitrary layouts or
indefinitely long runs.

Validation: all 13 existing host CTests passed. The inspector compiled with
strict conversion warnings and UBSan, and passed the repository formatter.
