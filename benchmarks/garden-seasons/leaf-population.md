# Repair policies across whole garden populations

Both frozen learned repair controllers retain higher mean generational renewal
when every family uses the same controller. Through day 1376, Search 1's late
renewal score is 5.50 times the fixed-wear control; Search 2's is 3.35 times the
control. None of the 24 gardens becomes empty or extinct.

The benefit comes with a substantial diversity cost. Search 1 loses 19 of 32
founder families and ends with one species in four of its eight gardens. The
control loses 11 families and retains at least two species in every garden.
These are viable, renewing populations under the tested conditions, not evidence
that either learned policy is an unqualified replacement default.

## Matched comparison

The [fixed protocol](../../docs/garden-population-comparison.md) specifies three
policies, four existing weather seeds, and two layouts. All plants and descendants
use `initial` (fixed wear), `s1-g3-c4` (Search 1), or `s2-g3-c1` (Search 2).
W2 growth, its recurrent memory, seasonal ecology, and deterministic rain are
unchanged. There is no gardener, intervention, new training, or model selection.

Each of 24 primary runs advances once through days 0, 32, 192, 608, 992, and
1376, saving complete state/history records and native pixels. All 24 unrendered
repeats match their primary's complete final JSON after excluding only the
framebuffer CRC. Initial conditions match across policies, and each intermediate
history matches the corresponding prefix of the final ledger.

The earlier [family durability comparison](leaf-family-durability.md) assigned
the candidate controller to one founder family against selective residents.
This comparison assigns it to everyone. Scores use the same arithmetic, but
their absolute levels describe different competitive settings.

## Renewal persists but declines over time

Children of non-founder parents qualify when both parent and child survive
strictly beyond age 32 days. Each family receives at most two credits in each
64-day birth window. Each period has six windows and 32 days of final follow-up.
All initial families, including extinct ones, remain in the denominator.
Families have equal weight within a world; the eight seed/layout worlds have
equal weight within a policy. Families sharing a world are not independent
replicates.

| Birth period | Fixed wear | Search 1 | Search 2 |
|---|---:|---:|---:|
| Early, (192,576] | 11/144 = 0.076389 | 17/90 = 0.188889 | 187/1440 = 0.129861 |
| Middle, (576,960] | 31/720 = 0.043056 | 7/48 = 0.145833 | 19/180 = 0.105556 |
| Late, (960,1344] | 17/720 = 0.023611 | 187/1440 = 0.129861 | 19/240 = 0.079167 |

Search 1 improves late renewal in all eight matched seed/layout worlds.
Search 2 improves six, ties one, and regresses in one. Both improve all four
weather means after averaging the two layouts equally:

| Weather seed | Fixed wear | Search 1 | Search 2 |
|---|---:|---:|---:|
| `58d7d6ca` | 0.069444 | 0.177778 | 0.108333 |
| `9a903368` | 0.000000 | 0.205556 | 0.008333 |
| `6b9c1a3e` | 0.000000 | 0.044444 | 0.158333 |
| `59818bc3` | 0.025000 | 0.091667 | 0.041667 |

These are the existing weather seeds, not new held-out generalization evidence.
All three mean scores decline across periods; the endpoint does not establish
indefinite renewal.

## Populated gardens can lose diversity

Counts below combine eight gardens and 32 initial founder families per policy.
Each garden has eight live-plant slots. Retained species include living plants
and pending seeds; a family is extinct only when neither remains.

| Day 1376 measurement | Fixed wear | Search 1 | Search 2 |
|---|---:|---:|---:|
| Living plants across 64 slots | 64 | 63 | 63 |
| Pending seeds | 64 | 64 | 64 |
| Living founder families | 21/32 | 13/32 | 17/32 |
| Extinct founder families | 11/32 | 19/32 | 15/32 |
| Seed-only founder families | 0 | 0 | 0 |
| Mean retained species per garden | 2.125 | 1.500 | 1.875 |
| Gardens retaining only one species | 0/8 | 4/8 | 1/8 |
| Families with any late renewal | 4/32 | 11/32 | 9/32 |
| Families renewing in the final birth window | 1/32 | 7/32 | 4/32 |

No policy has a whole-world extinction or an interval without living plants.
Family losses happen much earlier than the final observation:

| Families extinct by day | Fixed wear | Search 1 | Search 2 |
|---|---:|---:|---:|
| 192 | 7 | 12 | 13 |
| 608 | 10 | 19 | 15 |
| 992 | 11 | 19 | 15 |
| 1376 | 11 | 19 | 15 |

No founder family is extinct at day 32. Neither learned controller loses another
family after day 608, but the early losses are not recovered. Search 1's larger
renewal score therefore coexists with fewer surviving families and more
single-species gardens.

## More births and more established descendants

| Offspring through day 1376 | Fixed wear | Search 1 | Search 2 |
|---|---:|---:|---:|
| Born | 137 | 465 | 265 |
| Reached establishment | 111 | 293 | 196 |
| Died before or exactly at establishment age | 26 | 166 | 68 |
| Still alive but too young to judge | 0 | 6 | 1 |

Establishment is a lifetime milestone, not a count of survivors at the endpoint.
The learned policies produce more established offspring, not merely more seed
purchases, but also more offspring that fail to establish.

Late established-descendant occupancy of the whole garden averages 74.88% for
fixed wear, 82.87% for Search 1, and 88.32% for Search 2. This sums family
occupancy before averaging worlds and excludes founders and young offspring.
The archived scoring keys also retain the original family-mean occupancy
tie-breaker; it has a different denominator and is not this whole-garden measure.

## Visual evidence

Every matched capture is included in eight contact sheets. Columns are
fixed wear, Search 1, and Search 2. Rows are days 0, 32, 192, 608, 992, and 1376.
Tiles retain their native 240-by-240 pixels without overlays or rescaling.

They stay local in `frames/leaf-population/`, and
`population_evidence.py gallery --sheets-only` regenerates them from the
unpacked evidence.

For interactive playback, use:

```sh
make host-play-research ARGS="--policy s1-g3-c4 --founder all --speed 256"
```

## Verification and retained evidence

All 48 planned calls completed in 340.571 seconds, without a failed call,
retry, substituted condition, or budget extension. Before collection, all seven
host session/viewer suites, ten archive-preparation tests, and nine full archived
family replays passed. The family replays reproduce complete JSON and raw pixels
byte-for-byte, including daily-render runs. The new scorer reproduces all 288
archived family scores exactly.

The 1.74 MiB evidence archive (`leaf-population-results.json.gz`, kept locally)
contains 507 file entries backed by 412 unique blobs: all 144 captures, complete
histories, 48 process receipts, scoring results, test receipts, and the
collection-time protocol and source snapshots. Source/model/binary identities
are pinned; the frozen runtime is supplied by the authenticated durability
archive already in the repo. No archived executable is needed. The largest
histories contain 91 lineages and 397 seed records, within the unchanged ledger
capacities.

The offline verifier recomputes scores, demographics, capture checks, initial
conditions, and all repeat comparisons. Its tests also reject altered results,
failed preflight receipts, wrong commands/models, corrupt captures, extra runs,
unsafe paths, and output overwrite attempts. Packing and unpacking round-trip
every archived file exactly without simulator execution. All seven final host
CTest suites pass, including 20 analysis/evidence tests and exact pixel checks
for the eight published sheets. Gzip output uses a neutral header across Python
versions.

```sh
python3 -B sim/experiments/leaf_population/population_evidence.py unpack \
  benchmarks/garden-seasons/leaf-population-results.json.gz \
  artifacts/garden-population-review-v1
python3 -B sim/experiments/leaf_population/population_evidence.py gallery \
  artifacts/garden-population-review-v1 artifacts/garden-population-review-gallery-v1
```

Open the gallery's `index.html` for individually labeled captures. Output paths
must be fresh. Evidence SHA256:
`3aae48b92ed9787f9dc1601052330cdbf96ed9d72f3d845e0b9932d50112af49`.

## Next question

The bounded population comparison and an
[offline family-loss diagnostic](leaf-population-losses.md) are complete.
Search 1 loses every shrub family, and six of its eight additional family
losses follow successful descendant establishment. Most final living members
die with energy-shortage flags during winter, before the remaining seeds expire.
The next comparison should trace resource balances and actual germination
blockers in a matched early-loss case before changing the objective or ecology.
New training, growth-controller changes, and device deployment remain separate
decisions.
