# Family losses under uniform repair policies

Search 1's higher renewal rate accompanies the loss of every shrub family in
the tested gardens. Six of its eight additional losses relative to fixed wear
occur after descendants have already reached adulthood. This is not solely a
failure to produce or establish the first generation.

The existing [population comparison](leaf-population.md) histories identify a
common terminal sequence: the last living family member dies with an energy
shortage flag during winter, then the remaining seeds expire. They do not yet
identify the resource imbalance or the barriers that prevented those seeds
from germinating. The next diagnostic should measure those two mechanisms
before changing seed lifespan, training rewards, or ecological rules.

## Which families disappear

Each policy covers eight gardens and 32 founder families through day 1376. The
derived records (`leaf-population-losses.json`, kept locally) retain all 96
families across the three policies, including survivors. A family is extinct
only when both its living plants and pending seeds are gone.

| Extinct founder families | Fixed wear | Search 1 | Search 2 |
|---|---:|---:|---:|
| Flower, out of 12 | 1 | 3 | 3 |
| Shrub, out of 12 | 8 | 12 | 11 |
| Ground cover, out of 8 | 2 | 4 | 1 |
| All species, out of 32 | 11 | 19 | 15 |

Matching each original founder role across policies, Search 1 loses eight
families retained by fixed wear and rescues none. Search 2 loses five additional
families but rescues one ground-cover family lost by fixed wear. These are
paired outcomes under different whole-world policies, not isolated controller
effects on an otherwise unchanged family. Families sharing a garden are not
independent replicates.

## Loss after reproduction and establishment

The categories below describe the furthest historical stage of each extinct
family. Establishment requires reaching age 32 days without dying at or before
that boundary; it does not require that the descendant later reproduces.

| Stage reached by extinct families | Fixed wear | Search 1 | Search 2 |
|---|---:|---:|---:|
| Never purchased a seed | 0 | 0 | 0 |
| Purchased seeds but never produced offspring | 8 | 8 | 9 |
| Produced offspring but none established | 1 | 2 | 2 |
| Established descendants existed before eventual loss | 2 | 9 | 4 |

Six of Search 1's eight additional losses are in the last category. One never
produces offspring; the other produces offspring that fail to establish.
Improving first-generation establishment alone would therefore leave much of
the additional loss unexplained.

## Winter deaths precede the final seed expiries

Across the three policies, 41 of 45 extinct families lose their final living
member with an energy-shortage flag during calendar winter. Forty of these
deaths occur on day 14 of the 16-day year; one occurs on day 13. The remaining
four final deaths have water-shortage flags on year days 6 or 7.

| Final living member | Fixed wear | Search 1 | Search 2 |
|---|---:|---:|---:|
| Winter death with energy-shortage flag | 9 | 17 | 15 |
| Death with water-shortage flag | 2 | 2 | 0 |
| Family retains seeds after that death | 11 | 16 | 15 |

The flags describe insufficient upkeep resources on the final maintenance
step. Death follows accumulated stress, so they do not establish what caused
the preceding deficit. Calendar winter is also not a measurement of the cold
or light gate at a particular seed check.

For 42 of the 45 extinct families, seeds remain after the final living member
dies. All 58 of those terminal pending seeds eventually expire. The other
three families, all under Search 1, have no pending seed after the final death.
Expiry is the recorded final event, not proof that a longer seed lifetime
would restore recruitment.

The retained histories contain seed purchases, germinations, and expiries, but
not each attempted germination's blockers. The frozen kernel checks dormancy,
moisture, light, cold, spacing, plant capacity, and node capacity. It can retain
dead plants until decomposition, so a ledger count below eight living plants
does not prove that a plant slot or planting site was available. Sequential
seed checks can also consume resources or capacity needed by later seeds.

## The selected trace case

The first additional Search 1 shrub loss in the fixed comparison order is
founder 2 at column 13, in the rainfed layout with weather seed `58d7d6ca`.
Both policies purchase the family's first seed around day 0.91.

| Family event | Fixed wear | Search 1 |
|---|---:|---:|
| First offspring born | Day 223.07 | Day 64.98 |
| First offspring established | Day 255.07 | Day 96.98 |
| Original founder dies | Day 526.72 | Day 222.72 |
| Family becomes extinct | Not by day 1376 | Day 225.19 |

Search 1 produces three offspring, two of which establish, but all die before
the original founder. The founder's final maintenance step records an energy
shortage on winter day 14. Two seeds remain: a descendant's seed at column 15
expires on day 224.97, followed by the founder's seed at column 19 on day
225.19. The family survives only as seeds for its final 2.47 days.

The follow-up [six-replay trace](leaf-population-trace.md) is now complete,
covering all three policies through day 256 with tracing enabled and disabled.
It confirms the winter energy deficit and finds that both terminal seeds are
blocked by spacing on every actual check. Tracing preserves complete state,
history, and pixels. This case covers the Search 1 loss and the control's first
establishment; it cannot explain every family loss in the panel. The offline
analysis above still uses only the original histories.

## Reproduce the offline diagnostic

The diagnostic authenticates and verifies the original population archive,
then derives all family outcomes without executing the simulator. It records
the 24 input-history hashes and the frozen runtime archive identity. The
original 48-run evidence is unchanged.

```sh
python3 -B sim/experiments/leaf_population/population_losses.py \
  --check benchmarks/garden-seasons/leaf-population-losses.json
```

Use `--out` with a fresh filename to save a separate derivation; existing
outputs are refused. Ten new tests cover age and same-tick boundaries,
posthumous germination, seed-only censoring, tied final deaths, incomplete
histories, the complete paired roster, and exact published regeneration.
The combined population analysis suite passes all 30 tests.
