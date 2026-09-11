# Newborn resource budgets and targeted policy probes

Following the [lifetime measurements](lifetimes.md), trace the frozen `dc5e849d`
neural candidate through its first day/night cycle. Ecology, trained weights,
resource capacities, and ordinary policies remain unchanged. Seven observational
traces cover all three policies in both watered layouts at world seed `a7b5ccea`,
plus the successful neural irrigated case `cef5afdf`. Three explicitly separate
counterfactual runs override selected bids for individual plants.

## Surface-water trap

In crowded seed `a7b5ccea`, flower lineage 7 is born at tick 3,855. Its two
starting root endpoints share soil cell (8, 0). At birth, viable root extensions
can reach the next soil row, with candidate moisture 15–17. Nevertheless, the
neural shoot bid has priority 34 versus root priorities 22 and 18.

It chooses seven shoot extensions and no roots. At tick 4,050 it spends its last
five water on another shoot; root alternatives remain available with moisture
7–9, but priority 27 for the shoot beats 20 and 17 for roots. Its root cell stays
dry, stores never recover enough to buy an extension, and maintenance stress
kills it at tick 4,680: **13.75 seconds after birth**.

Through its final live sample, the exact water balance is:

```text
24 initial + 21 uptake − 35 growth − 10 paid upkeep = 0 stored water
```

It still has 255 energy immediately before death and never made a seed. This
is not an energy or reproduction-cost failure. The next whole-plot watering is
scheduled after tick 4,800, too late for this seedling.

The engine's minimum-resource gate matters: below the growth price, it cannot
execute a root extension and does not ask the policy for another growth decision.
The useful choice had to happen earlier.

## Water recovery followed by overnight overspending

Flower lineage 8 in the same world narrowly lasts until watering resumes. At
sunset (tick 4,800) it holds 249 energy and zero water, with stress 6 and an
11-node body. At tick 4,815 it finally begins growing roots.

Its first night has zero photosynthetic income, yet it commits 24 extensions
and two tip finishes, spending **208 energy on growth actions**. Its body reaches
35 nodes, increasing maintenance from two to five energy per second. It runs
out at tick 5,580 and dies at tick 6,000, age **35.75 seconds**, with 274 water
still stored at the preceding live sample. No seed costs contributed.

The night histogram includes the sunset step: 251 energy immediately before
that step funds 208 growth and 43 actual upkeep debits. Once stores are empty,
further unpaid upkeep increments stress rather than producing a negative store.

Adaptive irrigated lineage 4 at the same seed makes only one paid extension
during its first night (nine energy), waits 126 times, and survives the cycle.
This comparison is not an isolated causal intervention: their worlds differ.

Successful neural flower lineage 7 at irrigated seed `cef5afdf` completes its
body before night and makes no night-time growth purchases. It still reaches
stress 6 around dawn before photosynthesis recovers. Cycle survival alone does
not imply a comfortable resource margin.

## Same-world counterfactuals

Each probe starts from exactly the same crowded seed and neural model as its
unmodified control. Only the named plant's proposals are overridden; every
other plant keeps the original policy. Growth still uses ordinary resources,
collisions, timing, seed rules, and world mutation paths. Neural inference still
runs; original and overridden actions/priorities are both logged.

| Target | Intervention | Outcome |
| --- | --- | --- |
| Lineage 7 | None | Water death at age 13.75 s |
| Lineage 7 | Give its first root-extension bid priority | No water failure; energy death at age 48.75 s |
| Lineage 7 | First root priority plus wait during night | Alive at cycle 24; 11 children germinated |
| Lineage 8 | None | Energy death at age 35.75 s |
| Lineage 8 | Wait during night | Alive at cycle 24; 14 children germinated |

“Night” is sun phase 128–255. These are diagnostic overrides, not a validated
replacement policy: resuming growth at dawn can still spend energy before useful
light returns. Children counted here have germinated, not necessarily survived
a cycle. Outcomes run through tick 92,160, not indefinitely.

The root override diverges from its control precisely at tick 3,855. The wait-only
probe first changes a bid/world hash at tick 4,815. All earlier samples match.
Subsequent effects on neighbors are expected: resource competition and shading
couple the garden even when just one policy is overridden.

## Next learning experiment

Keep the mechanics fixed. Existing neural features already include resource
stores, maintenance-reserve margins, recent income, sunlight, and candidate
moisture. These cases do not demand a bigger network or resource buffers yet.

Discuss an initial eight-cycle training horizon and scoring durable offspring
and descendant persistence rather than relying on two-cycle final survival and
1.25-second establishment. Retain extinction protection, but avoid rewarding
only surviving founders or doomed seedlings. Reserve fresh validation seeds when
selecting new weights; these inspected seeds are now diagnostic cases. Do not
bake the targeted overrides into the default policy.

## Reproduce and validate

Build the ordinary host core and standalone observer; none of this tracing is
linked into firmware:

```sh
make host-build
docker compose run --rm firmware cc \
  -std=c11 -Wall -Wextra -Werror -Wconversion -Wsign-conversion \
  -fsanitize=undefined -fno-sanitize-recover=undefined \
  -Isrc -Isim sim/garden_inspect.c \
  build-host/libtoy_factory_simulator_core.a -o artifacts/garden-resource-inspect
docker compose run --rm firmware python3 benchmarks/garden-longevity/run-resources.py \
  --reference artifacts/garden-lifetimes --output artifacts/garden-resources-validated
```

Choose a new output directory on reruns. The runner refuses an existing directory,
requires the frozen model's SHA-256, records commands/source/binary/model/reference
hashes, and saves ten JSONL traces plus summaries/provenance under ignored
artifacts. Traces 00–06 are observations; 07–09 are the targeted probes.

Inspect one plant with:

```sh
python3 benchmarks/garden-longevity/resources.py \
  artifacts/garden-resources-validated/trace-05.jsonl --lineage 8 \
  --reference artifacts/garden-lifetimes --scenario crowded \
  --policy neural-candidate --seed a7b5ccea
```

`inspect --ecology` logs every ecology state and actual tip bid. It preserves
arbitration order and returns original decisions unless explicit `--root-first ID`
or `--night-wait ID` flags are supplied. Sparse mode remains available without
those options. `root_cells` entries are column, row, depth, and post-uptake soil
moisture; duplicated entries expose roots sharing a cell, not separate water.

Accounting mirrors hash-v5 debit order and requires reconstructed stores to equal
actual live stores. It separates clamping, paid upkeep, growth (including paid
finishes/failed extensions), and seed costs. Saturated income telemetry is rejected
rather than guessed. Death clears stores and income, so terminal steps are
explicitly excluded from reconstructed budgets; their preceding live states and
actual death flags remain visible.

The observational traces verify **175,079 live plant-steps**, **12,834 committed
winning bids**, and all **35 saved evaluation checkpoints** (2/4/8/16/24 cycles).
All budgets, winners, and hashes agree. The probes also pass accounting and
diverge exactly at their first overridden bid. Six resource-unit tests cover
saturation, newborn ordering, paid finishes/failed extensions, depletion,
malformed/truncated traces, and terminal zeroing. Invalid inspector options and
missing models are rejected.

## Hardware check

On 2026-09-11, rebuilt and flashed the normal `make build-fast` configuration
(PL022 DMA at 62.5 MHz with core-1 rendering), not an experimental policy.
The USB bootloader request and UF2 transfer both succeeded. The committed
`garden-generations.json` sequence reproduced host results on the PicoSystem:

- tick 4,530: `46691dd0` (death/decomposition stage);
- tick 8,430: `4e6d7dda`, framebuffer CRC-32 `fd71309b` (reproduction stage).

The runner restored physical input and real-time simulation. A subsequent Garden
status sample showed 60.0 Hz simulation, 29.6 fps presentation, no skipped or
over-budget updates in the post-replay window, and core 1 ready with no error.
The auto-gardener remained enabled. The fast firmware uses 255,612 bytes of its
255 KiB main RAM region and a separately reserved 8 KiB core-1 region; the host
tracing does not add firmware storage. All 15 host CTests passed, including the
new six-case resource-accounting suite.
