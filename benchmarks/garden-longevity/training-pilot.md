# Persistence v2: first learning-signal pilot

The end-to-end loop works, but the development winner does **not** win the
separate review panel. Keep this as a diagnostic result, not a promoted model.
No ecology, observations/actions, firmware or device state changed in this pilot.

[Frozen protocol](training-pilot-protocol.md) ·
[Generation gallery, including 18 native PNGs](training-pilot-gallery.md) ·
[Portable scores, models' identities and replay hashes](training-pilot-summary.json)

## Fixed experiment

Seven candidate models: unchanged `dc5e849d`, then three offspring in each of two
generations. Each offspring receives 32 parameter mutations from that generation's
starting champion. A strictly better score replaces it; ties retain the incumbent.
The search RNG is independent of the world/schedule RNG. One controller is shared
by the plants in each trial; this is host-side model search, not inherited neural
mutation within a garden.

Each model is evaluated on development seeds `13579bdf` and `2468ace1`. Generation
champions are also evaluated on review seeds `6c696665` and `72657632`, which never
affect automated selection. No untouched final test set or qualification claim.
Rainfed-crowded, selective leaf maintenance, no-night-growth adapter, 512 nodes,
eight seeds, wide dispersal and water headroom; drainage/seed-reserve OFF. The
same fresh-1 patch schedule is used everywhere. No gardener or irrigation.

The score window is (day 158, day 190], followed by a common two-day terminal
check. World key: terminal tier, recent renewing-child live ticks, all-descendant
live ticks, renewing parents, new establishments. Aggregate key: minimum tier,
sum of tiers, then the four summed measures. All endpoints here retain established
descendants, so recent renewing-child time determines selection.

## What changed

| Generation | Champion CRC | Development renewal ticks | Review renewal ticks |
|---:|---|---:|---:|
| 0, unchanged control | `dc5e849d` | 361,560 | 293,130 |
| 1 | `fa0c2cd8` | 449,295 | 247,050 |
| 2, unchanged champion | `fa0c2cd8` | 449,295 | 247,050 |

Development improves **24.27%**, but review falls **15.72%**. These percentages
describe one component, not a scalar conversion of the lexicographic fitness.
The two review worlds disagree: `6c696665` improves 77,460 → 166,065 renewal ticks;
`72657632` falls 215,670 → 80,985. Review descendant occupancy actually rises
11.02%, and final living counts go from 7/6 to 7/7. More living plant time or
a fuller-looking endpoint does not imply more recent productive succession.

| Candidate | Parent | Development aggregate key | Result |
|---|---|---|---|
| initial | — | `[1, 2, 361560, 1866180, 6, 8]` | Control |
| g1-c1 | initial | `[1, 2, 301500, 1874070, 5, 8]` | Rejected |
| g1-c2 | initial | `[1, 2, 247995, 1915515, 4, 7]` | Rejected |
| g1-c3 | initial | `[1, 2, 449295, 1908750, 6, 9]` | Generation 1 winner |
| g2-c1 | g1-c3 | `[1, 2, 333795, 1924530, 4, 6]` | Rejected |
| g2-c2 | g1-c3 | `[1, 2, 424455, 1816725, 8, 10]` | Rejected |
| g2-c3 | g1-c3 | `[1, 2, 328950, 1901520, 6, 7]` | Rejected |

`g2-c2` has more renewing parents and establishments than the incumbent, but less
recent offspring live time. The ordering is doing what v2 specifies; there is
no reason to change it simply because that rejected candidate wins a lower-priority
metric. The pilot demonstrates sensitivity and selectable variation, not a reliable
learning curve from two generations.

## Pictures and diversity

The [gallery](training-pilot-gallery.md) keeps generation zero and both completed
generations, including the duplicate generation-2 winner. Each row is one generation
and review seed; columns show early daylight, first dawn, and day 192. Early growth
and late plant structures differ between controllers. Brown tissue remains visible
alongside living plants; a still image is not evidence of an active lineage by itself.

At day 192, review seed `6c696665` changes from seven ground-cover plants from one
founder family to five ground-cover plus two flowers from two families. The other
review world changes from ground-cover/shrub across two families to seven
ground-cover plants from a single family. The winner also leaves only one founder
family in development seed `2468ace1`, versus two under the control. There is no
consistent diversity improvement, and diversity is diagnostic, not rewarded by v2.

## Correctness, cost and limits

- C scoring matches all 18 Python arithmetic fixtures. Native compact records match
  all four frozen 512-node recruitment histories: complete lifetimes, seed outcomes,
  full Python scores and final hashes, including retained ancestry after reclamation.
- Shared mutation code matches the pre-extraction trainer byte-for-byte for six
  RNG/count cases. Three reference-model golden cases remain in the regression suite.
  The old trainer's experimental-ecology guard and original fitness remain intact.
- The complete seven-model search repeats with identical candidate bytes, RNG states,
  all development scores/hashes, and champion history. Both searches finish before
  review capture; separate replay processes never share mutable search/world state.
- All 18 screenshots match compact evaluator checkpoints and framebuffer CRC/length;
  independent reset/process re-renders reproduce every pixel and hash. Review model
  files exist separately for generations 0, 1 and 2 even when their bytes are equal.
- 139 CTests pass: default 46, pilot 39, seed-reserve bank-8 27, bank-16 27. Strict
  conversion warnings, UBSan and assertions remain enabled; formatter/diff checks pass.
- The serial bundle takes **107.10 seconds** including preflight, repeated search,
  review, double rendering and verification during collection. The 14 development
  trials total **27.04 seconds**: median **1.72 s**, range **1.47–3.38 s** per 192-day
  native trial, including compact JSON output. This is optimized host throughput,
  not a PicoSystem frame-rate measurement. Each trial represents 737,280 logic ticks.
- The bundle holds 143 files / **18.14 MiB**, excluding the manifest itself: 38 full
  compact ledgers (four preflight, 14 development, 14 repeat, six review), frozen
  binaries/source/model/config, results, and all raw/native images. The scorer caps
  histories at 4,096 lineages and 65,536 seed purchases; overflow fails the trial.
  This is host memory, not added firmware RAM. There is no capture queue or worker pool.

Weak review performance is consistent with seed-specific selection, but two review
seeds and one search RNG do not establish statistical overfitting or a broken score.
Neither native terminal extinction nor seed-only recovery occurred here; those
scoring branches still have synthetic tests, not new native validation. The finite
window, single terminal sample, population-time preference, fixed patch schedule,
and species/family loss remain known limitations. Do not extend beyond 192 days
without addressing the existing plant-age wrap at 256 days.

## Next decision

Keep both controllers frozen. Before more evolution, propose a larger **paired
evaluation**, not more mutations: predeclare additional world seeds and a second
patch schedule, compare control versus `fa0c2cd8`, and inspect which offspring
cohorts explain the gains/losses. That distinguishes a narrow two-world win from
a repeatable improvement without adjusting the objective to fit this result.
Do not promote the model or change ecology based on this pilot.

## Reproduce

From the repository root, use a dedicated optimized build, keeping assertions and
UBSan enabled. The full frozen recruitment input bundle is required, not just its
portable summary; the runner verifies its manifest and each consumed history/model.

```sh
docker compose run --rm firmware bash -lc '
cmake -S sim -B artifacts/persistence-pilot-build -G Ninja \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_C_FLAGS_RELWITHDEBINFO="-O2 -g" \
  -DTOY_FACTORY_SIMULATOR_SANITIZERS=ON \
  -DTOY_FACTORY_GARDEN_WIDE_DISPERSAL=ON \
  -DTOY_FACTORY_GARDEN_WATER_HEADROOM=ON \
  -DTOY_FACTORY_GARDEN_COMBINED_EXPERIMENT=ON \
  -DTOY_FACTORY_GARDEN_LARGE_POOL=ON \
  -DTOY_FACTORY_GARDEN_LEAF_MAINTENANCE=ON \
  -DTOY_FACTORY_GARDEN_BOTTOM_DRAINAGE=OFF \
  -DTOY_FACTORY_GARDEN_LARGE_SEED_BANK=OFF \
  -DTOY_FACTORY_GARDEN_SEED_RESERVE=OFF &&
cmake --build artifacts/persistence-pilot-build -j 4 &&
ctest --test-dir artifacts/persistence-pilot-build --output-on-failure -j 4 &&
python3 -W error sim/garden_training_pilot.py --output artifacts/garden-training-pilot-repeat'
```

To verify the saved bundle without running more simulations, or export a new gallery:

```sh
python3 -W error sim/garden_training_pilot.py \
  --output artifacts/garden-training-pilot-v1 --verify
python3 -W error benchmarks/garden-longevity/review-training-pilot.py \
  --bundle artifacts/garden-training-pilot-v1 --export artifacts/pilot-review
```

Exports and collection refuse existing targets. The unchanged captured source is
in `artifacts/garden-training-pilot-v1/source.tar.gz`; reports/gallery export were
added afterward. Data and machinery are local uncommitted work on `green-garden`.
No commit, push, model deployment or default-ecology change is part of this result.

Bundle manifest SHA-256:
`9c9dc94e44cee155b4d8a83276339936d17e97cce4b995259faed4cd31059950`.
