# Controlled scattering-width experiment

## Hypothesis and fixed comparison

The [establishment audit](establishment.md) found open soil columns outside
parents' narrow scattering support. Test whether widening that support improves
establishment and continuing offspring survival, rather than just producing more
short-lived seedlings.

The host-only `TOY_FACTORY_GARDEN_WIDE_DISPERSAL` build changes attempted distance
from `5 + trait + ((random >> 1) % 3)` to `3 + trait + ((random >> 1) % 7)`.
Both keep the direction bit, one RNG draw, inherited offset, reflection and
clamping. For a zero trait this is 5–7 versus 3–9 cells, with the same nominal
midpoint; this is not a claim of identical realized mean distance near edges.
Traits still range from -2 to +2. Wide scattering can also waste attempts within
the existing three-column spacing exclusion. No targeting of open sites is added.

Hold model `dc5e849d`, rain-v1, capacities, light, uptake, spacing, germination
requirements and seed lifetime fixed. Run original NN, the same NN with the
existing nighttime-growth veto, and adaptive on eight paired seeds and two
layouts, through 24 cycles (92,160 ticks). Retain the previous seed batch
`0x6d617463`; these are exploratory cases, not an untouched evaluation set.
Primary diagnostics are full-cycle offspring survivors, durable parents,
nonviable worlds and renewal in the final eight cycles, alongside seed
germination/expiry and reachable-site audits. Do not call raw births alone a win.
Layouts sharing a weather seed are not independent statistical replicates.

Fixed visual review: seeds `6f47c12c` and `9c530b07`, both layouts and all three
policies, at ticks 68,760 and 92,160. The second seed is the previously identified
spatial counterexample, not a fresh random example.

## Reproduce

Normal `make host-build` explicitly selects narrow scattering, and firmware
rejects the experimental define. Wide uses a separate ignored build directory;
world storage, hashes and normal device behavior are unchanged by the option
when it is off. State hashes alone do not identify ecology rules: manifests,
native report metadata and frozen executable hashes identify the variant.

```sh
make host-build
docker compose run --rm firmware cmake -S sim \
  -B artifacts/build-host-wide-dispersal -G Ninja \
  -DTOY_FACTORY_GARDEN_WIDE_DISPERSAL=ON \
  -DTOY_FACTORY_SIMULATOR_SANITIZERS=ON
docker compose run --rm firmware cmake --build artifacts/build-host-wide-dispersal
docker compose run --rm firmware python3 sim/test_garden_dispersal.py \
  --narrow-build build-host --wide-build artifacts/build-host-wide-dispersal

docker compose run --rm firmware python3 sim/garden_experiments.py \
  --output artifacts/garden-dispersal-narrow \
  --candidate-model artifacts/garden-lifetimes/champion.tgm \
  --control-model artifacts/garden-lifetimes/champion.tgm \
  --candidate-probe no-night-growth-v1 \
  --training-report artifacts/garden-lifetimes/training.json \
  --split exploratory --cycles 24 --trials 8 --seed 0x6d617463
docker compose run --rm firmware python3 sim/garden_experiments.py \
  --output artifacts/garden-dispersal-wide --dispersal wide-v1 \
  --evaluator artifacts/build-host-wide-dispersal/toy-factory-garden-eval \
  --inspector artifacts/build-host-wide-dispersal/toy-factory-garden-inspect \
  --candidate-model artifacts/garden-lifetimes/champion.tgm \
  --control-model artifacts/garden-lifetimes/champion.tgm \
  --candidate-probe no-night-growth-v1 \
  --training-report artifacts/garden-lifetimes/training.json \
  --split exploratory --cycles 24 --trials 8 --seed 0x6d617463
docker compose run --rm firmware python3 sim/garden_dispersal.py \
  --narrow artifacts/garden-dispersal-narrow --wide artifacts/garden-dispersal-wide \
  --late-cycles 8 --output artifacts/garden-dispersal-comparison.json
```

Each bundle compares policies **within one ecology**. The final command compares
the same policies **across the two ecologies**, validates paired settings/model
bytes and all frozen artifacts, and retains every paired result. The collector's
`--dispersal` checks expected build identity; it does not switch simulation rules.
Existing output paths are refused. Do not edit sources during collection.

For each bundle, run `sim/garden_establishment.py --bundle BUNDLE --output NEW`
and `sim/garden_gallery.py --bundle BUNDLE --output NEW --include-adaptive
--seed 6f47c12c --seed 9c530b07 --checkpoint 68760 --checkpoint 92160`.
Use `--inspector artifacts/build-host-wide-dispersal/toy-factory-garden-inspect`
for the wide audit and the corresponding `--replayer .../toy-factory-garden-replay`
for the wide gallery. The narrow tools default to `build-host/`.

## Results

Completed 2026-09-11. Entries are **narrow → wide**, totals across 16 worlds per
policy (eight weather seeds × two layouts).

| Policy | Germinations | Full-cycle survivors / eligible offspring | Durable parents | Nonviable worlds |
|---|---:|---:|---:|---:|
| Original NN | 138 → 263 | 44/137 → 51/260 | 23 → 23 | 3 → 3 |
| NN + night-growth veto | 181 → 211 | 78/180 → 81/208 | 33 → 26 | 0 → 0 |
| Adaptive | 78 → 117 | 44/78 → 68/114 | 11 → 15 | 0 → 0 |

Eligible offspring had 3,840 ticks of potential follow-up. A full-cycle
survivor can subsequently die. A durable parent and at least one of its children
each survived a full cycle, not necessarily concurrently. These cumulative
counts do not prove indefinite renewal.

Adaptive improves its full-cycle survivor count in 11 matched worlds, ties in
two and worsens in three. The veto policy improves in six, ties in four and
worsens in six; its durable-parent count worsens in nine. Benefits are not
uniform across layouts: veto-policy births are 85 → 133 in rainfed, but
96 → 78 in crowded. Adaptive durable parents are 6 → 13 in rainfed, but
5 → 2 in crowded. The original NN nearly doubles births while its full-cycle
survival fraction falls from 32.1% to 19.6%.

Final eight cycles (ticks 61,440–92,160):

| Policy | New births | Newly qualified full-cycle survivors | Newly qualified durable parents |
|---|---:|---:|---:|
| Original NN | 12 → 46 | 2 → 7 | 2 → 2 |
| NN + night-growth veto | 8 → 18 | 5 → 4 | 5 → 1 |
| Adaptive | 5 → 17 | 2 → 12 | 1 → 5 |

Qualification deltas count thresholds reached during the window; they are **not
a cohort of offspring born within that window**. First-dawn populations and
final nonviable-world counts are unchanged. No significance/generalization
claim is made from this small exploratory panel.

### Establishment versus survival

Both audits reconciled every seed: 6,629 narrow and 6,865 wide, checked against
77,459 and 77,559 evaluator checkpoints respectively. The narrow audit's
aggregates exactly reproduce the preceding investigation.

For seeds **born after cycle 16 with a full potential seed-lifetime follow-up**
(through birth at cycle 23), germinations / eligible seeds are:

| Policy | Narrow | Wide |
|---|---:|---:|
| Original NN | 10/381 | 39/447 |
| NN + night-growth veto | 6/746 | 16/802 |
| Adaptive | 5/855 | 12/849 |

For late-born *expired* seeds, the number which ever saw an open column but
never one in their birth parent's support drops from 208 → 56 (NN),
288 → 32 (veto), and 342 → 34 (adaptive). Wider placement also changes the
eventual population and availability of sites, so these are different
trajectories/cohorts, not probabilities for a fixed landscape. The support
census records hypothetical **post-step** opportunities; successful germinations
have already left the bank. See the audit's survivor-bias caveat.

The previously identified `rainfed/9c530b07` veto-policy world is instructive:

- Narrow has zero births in the late window; wide has seven, at columns
  14, 20, 20, 26, 14, 0 and 0. Column 0 is reached and germinates twice.
- All seven die in 12–46 simulated seconds, before a complete 64-second cycle.
  Death flags attribute four to energy shortage and three to water shortage.
- One column-0 seedling lives from tick 91,440 to 92,160. Its last living
  checkpoint has four active leaves, energy 256, water 0 and only two root
  nodes. Reaching open soil did not establish a sustainable resource budget.
- In contrast, adaptive on this same layout/seed has full-cycle offspring
  survivors 5 → 10 and durable parents 2 → 5.

Whole-panel water-only death counts rise 33 → 113 for original NN, 68 → 85
for veto and 10 → 29 for adaptive. These are counts, not exposure-normalized
death risks. Resource competition and controller behavior still matter after
spatial access improves. Terminal-step resource budgets remain partially
unreconstructed; death flags/lifetime timestamps support the classifications,
not an invented full terminal accounting balance.

### Visual and reproducibility checks

Captured the predeclared 24-frame panel for each ecology and reran all 48
frames from frozen executables: every state hash and raw framebuffer byte
reproduced. The `9c530b07` final veto frame remains a sparse set of survivors
with a dead edge seedling in wide; the adaptive wide frame fills more columns.
Static images alone do not reveal the unsuccessful intervening births.

Local galleries are `artifacts/garden-dispersal-{narrow,wide}-gallery/index.md`;
audit indexes use the corresponding `-audit/index.md` paths. Raw artifacts are
ignored, not published assets. These versioned findings are the portable evidence
summary. Detailed `01.resources.json` in each bundle and `analyses/02.json` in
each audit reproduce the veto-policy counterexample above.

Validation:

- All 22 normal CTests pass with strict warnings and UBSan, including existing
  device sequence goldens. The two-build integration test also passes.
- Support enumeration covers all 28 base columns × five inherited offsets in
  each build, including reflection and read-only state preservation.
- Cross-build tests reject incorrect declared ecology and wrong replay binaries
  even at tick zero, exercise audits/galleries/frozen replays, reject mismatched
  settings and overwrites, and verify identical pre-scattering worlds.
- Both fresh narrow evaluator reports are byte-identical to the original
  night-growth probe reports, not merely similar aggregate metrics.
- The long-run counterexample census was replayed from frozen tools for each
  variant, with identical trace bytes and reanalysis.

SHA-256 identifiers:

| Artifact | SHA-256 |
|---|---|
| Narrow bundle manifest | `1fd69ed8c2dc146d24b8f17a7faab8dac7edb856b2a3a8434ec20914cc2f44ff` |
| Wide bundle manifest | `4e6c55005908ac23320d807cbe1d6defce3a385428ba12c375a096ab55454742` |
| Narrow audit manifest | `c38cc9c1e7c1a162e3db522bf51105e4ba198838b90c40053e56042062adbe4f` |
| Wide audit manifest | `ab33a223f91d4f12af0f78c25eeb826953e8c7fc1ff98ca5686b76149255b740` |
| Narrow gallery manifest | `d65438a1aebe88336c09d6fd40fa070e22bb9b322bf97fe33a991fa864df114e` |
| Wide gallery manifest | `d2936e4188bf9373964ebe4739dc3bc8d35b12d62c521ed9220fbdd7ae35b920` |
| Paired comparison JSON | `1d4269fa54ce3f659fcc479b07be55cd9f612c427594f16e4219744b815a48b3` |

## Decision and next question

Keep wide scattering as an explicitly labeled host experiment. It removes
some spatial blind spots and helps adaptive, but does **not** reliably improve
durable lineages across policies/layouts. No firmware flash, default ecology
change, model training, commit or push was performed.

Next, discuss an isolated resource experiment: test uptake capped by available
plant water-storage headroom against current root extraction followed by
overflow discard, under **narrow** scattering first. This asks whether mature
plants are unnecessarily draining water needed by seedlings; it does not assume
that water alone explains the energy deaths or guarantees renewal. Keep broad
scattering and water uptake separate until their individual effects are clear.
